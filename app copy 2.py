import os
import json
import tempfile
import streamlit as st
from datetime import datetime
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from PyPDF2 import PdfReader
from openai import OpenAI
import logging
from dotenv import load_dotenv

# LangGraph imports (left as-is in case you want the agentic ReAct flow)
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

# ---------------------------------------------------------
# Logging & env
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('agentic_payroll.log')
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("No GEMINI_API_KEY or OPENAI_API_KEY found in environment. Set GEMINI_API_KEY in .env")

# ---------------------------------------------------------
# OpenAI / Gemini client initialization
# (keep your base_url if using google's OpenAI-compat endpoint)
# ---------------------------------------------------------
client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

llm = ChatOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model="gemini-2.0-flash-exp",
    temperature=0.1
)

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def _clean_codeblock(text: str) -> str:
    """Remove triple-backtick fences and optional language markers."""
    if text.startswith("```"):
        # remove leading fence + possible language
        parts = text.split("\n")
        # remove first line fence
        parts = parts[1:]
        # if last line is fence, drop it
        if parts and parts[-1].strip().endswith("```"):
            parts = parts[:-1]
        return "\n".join(parts).strip()
    return text.strip()

def _safe_load_json(s: str) -> Optional[dict]:
    s = s.strip()
    s = _clean_codeblock(s)
    try:
        return json.loads(s)
    except Exception as e:
        # Try some minor fixes (single quotes -> double)
        try:
            return json.loads(s.replace("'", '"'))
        except Exception:
            logger.error("Failed to parse JSON: %s", e)
            return None

# ---------------------------------------------------------
# Tool: extract PDF text
# ---------------------------------------------------------
@tool
def extract_pdf_text_tool(file_path: str) -> str:
    """Extract text content from a PDF file for contract analysis."""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        logger.info(f"Successfully extracted {len(text)} characters from PDF")
        return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return f"Error: {str(e)}"

# ---------------------------------------------------------
# Tool: parse contract data (LLM)
# ---------------------------------------------------------
@tool
def parse_contract_data_tool(contract_text: str) -> str:
    """
    Use LLM to extract structured contract fields.
    Return a JSON string matching the expected schema.
    """
    try:
        prompt = """Extract employee salary details from this employment contract.
Return ONLY a valid JSON object with this exact structure (fields may be null if not present):
{
  "employee_name": "string or null",
  "employee_id": "string or null", 
  "department": "string or null",
  "designation": "string or null",
  "location": "string or null",
  "salary_structure": {
    "basic": number or null,
    "hra": number or null,
    "allowances": number or null,
    "gross": number or null
  }
}
If a numeric field is present as an annual amount, convert it to monthly (divide by 12) and document that in a 'notes' field inside the top-level object.
Respond with JSON only (no explanation)."""
        response = client.chat.completions.create(
            model="gemini-2.0-flash-exp",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Contract text: {contract_text[:15000]}"}  # cap length
            ],
            temperature=0.0,
            max_tokens=1500
        )
        result = response.choices[0].message.content.strip()
        result = _clean_codeblock(result)
        # validate JSON
        parsed = _safe_load_json(result)
        if parsed is None:
            logger.error("parse_contract_data_tool: LLM output not valid JSON")
            return json.dumps({"error": "LLM output not valid JSON", "raw": result})
        logger.info("Successfully parsed contract data")
        return json.dumps(parsed)
    except Exception as e:
        logger.error(f"Contract parsing failed: {e}")
        return json.dumps({"error": str(e)})

# ---------------------------------------------------------
# Deterministic salary calculation (local) - more reliable
# ---------------------------------------------------------
def _as_monthly(value: Optional[float], assume_annual: bool = False) -> Optional[float]:
    """If value is None, return None. If assume_annual True, divide by 12."""
    if value is None:
        return None
    try:
        v = float(value)
        return v / 12.0 if assume_annual else v
    except:
        return None

@tool
def calculate_salary_breakdown_tool(contract_data: str) -> str:
    """
    Deterministic calculator for Indian payroll monthly values.
    Expects contract_data to be a JSON string matching parse output.
    """
    try:
        parsed = _safe_load_json(contract_data)
        if parsed is None:
            return json.dumps({"error": "Invalid contract_data JSON"})

        # salary_structure may be missing or partial
        ss = parsed.get("salary_structure", {}) if isinstance(parsed, dict) else {}
        # prefer provided gross, otherwise sum components
        basic = ss.get("basic")
        hra = ss.get("hra")
        allowances = ss.get("allowances")
        gross = ss.get("gross")

        # Some contracts provide annual amounts; user prompt/LLM may have converted that.
        # Assume the values are monthly if reasonable; if any value > 200000 treat as annual and divide by 12.
        def to_monthly_if_needed(x):
            if x is None:
                return None
            try:
                v = float(x)
                if v > 200000:  # heuristic: >2 lakh likely annual
                    return v / 12.0
                return v
            except:
                return None

        basic_m = to_monthly_if_needed(basic)
        hra_m = to_monthly_if_needed(hra)
        allowances_m = to_monthly_if_needed(allowances)
        gross_m = to_monthly_if_needed(gross)

        # If gross missing but components present, compute sum
        if gross_m is None and any(v is not None for v in (basic_m, hra_m, allowances_m)):
            gross_m = sum(v or 0.0 for v in (basic_m, hra_m, allowances_m))

        if gross_m is None:
            return json.dumps({"error": "Insufficient salary data to compute gross salary"})

        # Deductions
        # PF: 12% of basic (cap per month 1800)
        pf = 0.0
        if basic_m is not None:
            pf_calc = 0.12 * basic_m
            pf = min(pf_calc, 1800.0)
        else:
            # if basic missing, try assume 40% of gross as basic (common heuristic) then compute PF
            estimated_basic = 0.4 * gross_m
            pf = min(0.12 * estimated_basic, 1800.0)

        # ESI: 0.75% of gross if gross <= 21,000
        esi = 0.0
        if gross_m <= 21000:
            esi = 0.0075 * gross_m

        # Professional Tax: Rs.200/month if salary > 15,000 (simple rule; actual rates vary by state)
        professional_tax = 200.0 if gross_m > 15000 else 0.0

        # TDS: Simple estimate — compute annual gross and apply a conservative 10% on taxable portion above 250,000.
        annual_gross = gross_m * 12.0
        taxable = max(0.0, annual_gross - 250000.0)
        tds_annual_est = taxable * 0.10  # simplified slab
        tds = tds_annual_est / 12.0

        deductions = {
            "pf": round(pf, 2),
            "esi": round(esi, 2),
            "professional_tax": round(professional_tax, 2),
            "tds": round(tds, 2)
        }

        total_deductions = sum(deductions.values())
        net_salary = round(max(0.0, gross_m - total_deductions), 2)

        result = {
            "gross_salary": round(gross_m, 2),
            "deductions": deductions,
            "net_salary": net_salary,
            "notes": "Estimates: PF cap=₹1800, ESI applicable if gross<=21000, professional tax simplified, TDS a rough estimate."
        }
        logger.info("Successfully calculated salary breakdown")
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Salary calculation failed: {e}")
        return json.dumps({"error": str(e)})

# ---------------------------------------------------------
# Deterministic compliance validation (local)
# ---------------------------------------------------------
@tool
def validate_compliance_tool(salary_data: str) -> str:
    """Check PF limits, ESI eligibility, professional tax applicability, and TDS reasonableness."""
    try:
        sd = _safe_load_json(salary_data)
        if sd is None:
            return json.dumps({"error": "Invalid salary_data JSON"})

        gross = sd.get("gross_salary", 0) or 0
        deductions = sd.get("deductions", {})
        issues = []
        recs = []

        # PF check: PF <= 1800
        pf = deductions.get("pf", 0)
        if pf > 1800.0 + 1e-6:
            issues.append("PF exceeds statutory monthly cap of ₹1800.")
            recs.append("Reduce PF to statutory cap calculation or verify basic salary amount.")

        # ESI: check eligibility
        esi = deductions.get("esi", 0)
        if gross > 21000 and esi > 0.0:
            issues.append("ESI deducted even though gross > ₹21,000; ESI shouldn't apply.")
            recs.append("Remove ESI for this employee or verify gross salary.")

        if gross <= 21000 and esi == 0.0:
            # maybe ESI missing (but some employers may not enroll)
            recs.append("Verify whether employee is enrolled for ESI if gross <= ₹21,000.")

        # Professional tax: check simple rule used
        prof_tax = deductions.get("professional_tax", 0)
        if gross > 15000 and prof_tax < 200.0 - 1e-6:
            issues.append("Professional tax appears too low (expected ≈ ₹200 for gross > 15,000 in this simplified check).")
            recs.append("Verify state professional tax rules; rates differ by state.")

        # TDS: check crude reasonableness: if monthly TDS > 0.2 * net salary -> suspicious
        tds = deductions.get("tds", 0)
        net = sd.get("net_salary", 0) or 0
        if net > 0 and tds > 0.2 * net:
            issues.append("TDS is unusually high compared to net salary; re-check tax estimates.")
            recs.append("Recompute TDS using exact tax slabs and exemptions for the employee (use Form 16-like computation).")

        compliance = "COMPLIANT" if len(issues) == 0 else "NON_COMPLIANT"

        validated = {
            "pf": round(pf, 2),
            "esi": round(esi, 2),
            "professional_tax": round(prof_tax, 2),
            "tds": round(tds, 2)
        }

        result = {
            "compliance_status": compliance,
            "issues": issues,
            "validated_deductions": validated,
            "recommendations": recs
        }
        logger.info("Compliance validation done: %s", compliance)
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Compliance validation failed: {e}")
        return json.dumps({"error": str(e)})

# ---------------------------------------------------------
# Deterministic anomaly detection (local)
# ---------------------------------------------------------
@tool
def detect_anomalies_tool(combined_data: str) -> str:
    """
    Check for negative numbers, mismatches, missing deductions, and big differences between computed vs provided gross.
    combined_data is expected to be a JSON string with keys: contract, salary, compliance
    """
    try:
        cd = _safe_load_json(combined_data)
        if cd is None:
            return json.dumps({"error": "Invalid combined_data JSON"})

        contract = cd.get("contract", {})
        salary = cd.get("salary", {})
        compliance = cd.get("compliance", {})

        anomalies = []
        overall_status = "NORMAL"
        confidence = 0.9

        gross = salary.get("gross_salary", 0) or 0
        deductions = salary.get("deductions", {})
        # Check negative or zero gross
        if gross <= 0:
            anomalies.append({
                "type": "calculation_error",
                "description": "Gross salary is zero or negative.",
                "severity": "HIGH",
                "affected_field": "gross_salary"
            })
            overall_status = "CRITICAL"

        # Check deduction sums
        total_deds = sum(deductions.values())
        if total_deds < 0:
            anomalies.append({
                "type": "calculation_error",
                "description": "Total deductions negative.",
                "severity": "HIGH",
                "affected_field": "deductions"
            })
            overall_status = "CRITICAL"

        # Check mismatch between gross and provided components if any
        ss = contract.get("salary_structure", {}) or {}
        comps_sum = 0
        present_components = False
        for k in ("basic", "hra", "allowances"):
            v = ss.get(k)
            if v is not None:
                present_components = True
                try:
                    numeric = float(v)
                    # If contract gave annual amounts, this might be much larger; we attempt to normalize:
                    if numeric > 200000:
                        numeric = numeric / 12.0
                    comps_sum += numeric
                except:
                    pass

        if present_components and comps_sum > 0:
            diff_pct = abs(comps_sum - gross) / max(1.0, gross)
            if diff_pct > 0.05:  # >5% mismatch
                anomalies.append({
                    "type": "data_inconsistency",
                    "description": f"Sum of components (basic+hra+allowances = {comps_sum:.2f}) differs from gross ({gross:.2f}) by {diff_pct*100:.2f}%.",
                    "severity": "MEDIUM" if diff_pct <= 0.2 else "HIGH",
                    "affected_field": "gross vs components"
                })
                overall_status = "REVIEW_REQUIRED"

        # Add compliance issues as anomalies if NON_COMPLIANT
        if compliance.get("compliance_status") == "NON_COMPLIANT":
            anomalies.append({
                "type": "data_inconsistency",
                "description": "Compliance validation flagged non-compliance: " + "; ".join(compliance.get("issues", [])),
                "severity": "MEDIUM",
                "affected_field": "compliance"
            })
            if overall_status != "CRITICAL":
                overall_status = "REVIEW_REQUIRED"

        result = {
            "has_anomalies": len(anomalies) > 0,
            "anomalies": anomalies,
            "overall_status": overall_status,
            "confidence_score": round(confidence, 2)
        }
        logger.info("Anomaly detection completed. Found %d anomalies", len(anomalies))
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        return json.dumps({"error": str(e)})

# ---------------------------------------------------------
# Tools list (same as before)
# ---------------------------------------------------------
tools = [
    extract_pdf_text_tool,
    parse_contract_data_tool,
    calculate_salary_breakdown_tool,
    validate_compliance_tool,
    detect_anomalies_tool
]

# ---------------------------------------------------------
# System prompt (kept for LangGraph agent)
# ---------------------------------------------------------
system_prompt = SystemMessage(content="""You are a payroll agent that uses tools for each step:
1) extract_pdf_text_tool
2) parse_contract_data_tool
3) calculate_salary_breakdown_tool
4) validate_compliance_tool
5) detect_anomalies_tool

Follow that sequence. Return a single JSON output at the end with keys:
{
  "success": boolean,
  "contract_data": {},
  "salary_data": {},
  "compliance_data": {},
  "anomalies_data": {},
  "errors": []
}
""")

# ---------------------------------------------------------
# Deterministic pipeline class (recommended to call from Streamlit)
# ---------------------------------------------------------
class PayrollAgenticAI:
    """Pure Agentic AI container. Provide a deterministic pipeline runner and keep agentic graph for optional use."""
    def __init__(self):
        memory = MemorySaver()
        try:
            self.graph = create_react_agent(
                llm,
                tools,
                state_modifier=system_prompt,
                checkpointer=memory
            )
        except Exception as e:
            logger.warning("Failed to create ReAct agent (LangGraph) — continuing with deterministic pipeline. Error: %s", e)
            self.graph = None
        self.thread_id = "payroll_thread_1"

    def process_contract_pipeline(self, contract_path: str) -> Dict[str, Any]:
        """
        Deterministic sequential pipeline calling the tools directly.
        This is recommended for predictable results (what Streamlit should call).
        """
        errors = []
        output = {
            "success": False,
            "contract_data": None,
            "salary_data": None,
            "compliance_data": None,
            "anomalies_data": None,
            "errors": []
        }
        try:
            # 1) extract text
            text = extract_pdf_text_tool(contract_path)
            if text.startswith("Error:") or (isinstance(text, str) and text.strip() == ""):
                errors.append(f"extract_pdf_text_tool failed: {text}")
                output["errors"] = errors
                return output
            # 2) parse contract via LLM tool (returns JSON string or error JSON)
            parsed_json_string = parse_contract_data_tool(text)
            parsed = _safe_load_json(parsed_json_string)
            if parsed is None or parsed.get("error"):
                errors.append(f"parse_contract_data_tool failed or invalid JSON: {parsed_json_string}")
                output["errors"] = errors
                output["contract_data"] = parsed_json_string
                return output
            output["contract_data"] = parsed

            # 3) calculate salary deterministically
            salary_json_str = calculate_salary_breakdown_tool(json.dumps(parsed))
            salary = _safe_load_json(salary_json_str)
            if salary is None or salary.get("error"):
                errors.append(f"calculate_salary_breakdown_tool failed: {salary_json_str}")
                output["errors"] = errors
                output["salary_data"] = salary_json_str
                return output
            output["salary_data"] = salary

            # 4) compliance
            compliance_str = validate_compliance_tool(json.dumps(salary))
            compliance = _safe_load_json(compliance_str)
            if compliance is None or compliance.get("error"):
                errors.append(f"validate_compliance_tool failed: {compliance_str}")
                output["errors"] = errors
                output["compliance_data"] = compliance_str
                return output
            output["compliance_data"] = compliance

            # 5) anomalies
            combined = json.dumps({
                "contract": parsed,
                "salary": salary,
                "compliance": compliance
            })
            anomalies_str = detect_anomalies_tool(combined)
            anomalies = _safe_load_json(anomalies_str)
            if anomalies is None or anomalies.get("error"):
                errors.append(f"detect_anomalies_tool failed: {anomalies_str}")
                output["errors"] = errors
                output["anomalies_data"] = anomalies_str
                return output
            output["anomalies_data"] = anomalies

            output["success"] = len(errors) == 0
            output["errors"] = errors
            return output

        except Exception as e:
            logger.exception("Workflow execution failed")
            output["errors"].append(str(e))
            return output

    def process_contract_with_agent(self, contract_path: str) -> Dict[str, Any]:
        """
        Optional: invoke the LangGraph agentic ReAct flow. Not recommended as the primary
        method for deterministic payroll math. Kept for experiments only.
        """
        if not self.graph:
            return {"success": False, "errors": ["Agent not initialized"], "messages": []}
        try:
            config = {"configurable": {"thread_id": self.thread_id}}
            input_message = HumanMessage(content=f"Process the employment contract at: {contract_path}")
            final_state = self.graph.invoke({"messages": [input_message]}, config)
            messages = final_state.get("messages", [])
            last_message = messages[-1] if messages else None
            # Expect last_message.content to be the JSON result
            if isinstance(last_message, AIMessage):
                try:
                    result = json.loads(last_message.content)
                    result["messages"] = [msg.content for msg in messages if isinstance(msg, (HumanMessage, AIMessage))]
                    return result
                except Exception as e:
                    return {"success": False, "errors": [f"Failed to parse final output: {e}"], "messages": [msg.content for msg in messages]}
            else:
                return {"success": False, "errors": ["Agent did not return an AI message"], "messages": [msg.content for msg in messages]}
        except Exception as e:
            logger.exception("Agentic execution failed")
            return {"success": False, "errors": [str(e)], "messages": []}

# ---------------------------------------------------------
# Streamlit integration (call deterministic pipeline)
# ---------------------------------------------------------
def main():
    st.set_page_config(page_title="AgenticAI Payroll System", page_icon="🤖", layout="wide")
    st.title("🤖 AgenticAI Payroll Processing System")
    st.markdown("**Deterministic payroll pipeline (LLM for parsing only)**")

    if 'agentic_ai' not in st.session_state:
        st.session_state.agentic_ai = PayrollAgenticAI()
        st.session_state.processing_result = None

    contract_file = st.file_uploader("Upload Employee Contract PDF", type=["pdf"])
    if st.button("🚀 Process (Deterministic Pipeline)", disabled=not contract_file):
        if contract_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(contract_file.read())
                path = tmp.name
            with st.spinner("Processing..."):
                result = st.session_state.agentic_ai.process_contract_pipeline(path)
                st.session_state.processing_result = result
            try:
                os.unlink(path)
            except:
                pass

    if st.session_state.processing_result:
        result = st.session_state.processing_result
        if result.get("success"):
            st.success("✅ Processing completed successfully")
        else:
            st.error(f"❌ Processing finished with errors: {result.get('errors', [])}")

        with st.expander("Result JSON", expanded=True):
            st.json(result)

    else:
        st.info("Upload a contract PDF and press 'Process' to run the deterministic pipeline.")
        st.markdown("""
        **Notes**
        - Parsing (structure extraction) still uses the LLM. Salary math, compliance checks and anomalies detection are deterministic Python logic (more reliable).
        - The deterministic pipeline is recommended for production. The LangGraph agentic ReAct flow is available for experimentation but not required.
        """)

if __name__ == "__main__":
    main()




















# import os
# import json
# import tempfile
# import streamlit as st
# from datetime import datetime
# from typing import TypedDict, Annotated, List, Dict, Any
# from PyPDF2 import PdfReader
# from openai import OpenAI
# import logging
# from dotenv import load_dotenv

# # LangGraph imports
# from langgraph.prebuilt import create_react_agent
# from langgraph.checkpoint.memory import MemorySaver
# from langchain_core.tools import tool
# from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage, AIMessage
# from langchain_openai import ChatOpenAI

# # Configuration
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(),
#         logging.FileHandler('agentic_payroll.log')
#     ]
# )
# logger = logging.getLogger(__name__)

# load_dotenv()
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # Initialize OpenAI client for Gemini
# client = OpenAI(
#     api_key=GEMINI_API_KEY,
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# )

# # Initialize ChatOpenAI for LangGraph (using Gemini via OpenAI API)
# llm = ChatOpenAI(
#     api_key=GEMINI_API_KEY,
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
#     model="gemini-2.0-flash-exp",
#     temperature=0.1
# )

# # Tools that the agent can use
# @tool
# def extract_pdf_text_tool(file_path: str) -> str:
#     """Extract text content from a PDF file for contract analysis."""
#     try:
#         reader = PdfReader(file_path)
#         text = ""
#         for page in reader.pages:
#             text += page.extract_text() or ""
#         logger.info(f"Successfully extracted {len(text)} characters from PDF")
#         return text.strip()
#     except Exception as e:
#         logger.error(f"PDF extraction failed: {e}")
#         return f"Error: {str(e)}"

# @tool
# def parse_contract_data_tool(contract_text: str) -> str:
#     """Parse employee contract data using LLM analysis."""
#     try:
#         prompt = """Extract employee salary details from this employment contract.
#         Return ONLY a valid JSON object with this exact structure:
#         {
#           "employee_name": "string",
#           "employee_id": "string or null", 
#           "department": "string or null",
#           "designation": "string or null",
#           "location": "string",
#           "salary_structure": {
#             "basic": number,
#             "hra": number,
#             "allowances": number,
#             "gross": number
#           }
#         }"""
        
#         response = client.chat.completions.create(
#             model="gemini-2.0-flash-exp",
#             messages=[
#                 {"role": "system", "content": prompt},
#                 {"role": "user", "content": f"Contract text: {contract_text}"}
#             ],
#             temperature=0.1,
#             max_tokens=1000
#         )
        
#         result = response.choices[0].message.content.strip()
#         # Clean JSON response
#         if result.startswith("```json"):
#             result = result[7:]
#         if result.startswith("```"):
#             result = result[3:]
#         if result.endswith("```"):
#             result = result[:-3]
        
#         logger.info("Successfully parsed contract data")
#         return result.strip()
#     except Exception as e:
#         logger.error(f"Contract parsing failed: {e}")
#         return f"Error: {str(e)}"

# @tool
# def calculate_salary_breakdown_tool(contract_data: str) -> str:
#     """Calculate detailed salary breakdown with Indian payroll deductions."""
#     try:
#         prompt = """Calculate monthly salary breakdown for Indian payroll based on the contract data.
#         Apply standard Indian deductions:
#         - PF: 12% of basic (max Rs.1,800)
#         - ESI: 0.75% of gross (if gross <= Rs.21,000)
#         - Professional Tax: Rs.200/month (if salary > Rs.15,000)
#         - TDS: Estimate based on annual salary
        
#         Return ONLY a valid JSON object:
#         {
#           "gross_salary": number,
#           "deductions": {
#             "pf": number,
#             "esi": number,
#             "professional_tax": number,
#             "tds": number
#           },
#           "net_salary": number
#         }"""
        
#         response = client.chat.completions.create(
#             model="gemini-2.0-flash-exp",
#             messages=[
#                 {"role": "system", "content": prompt},
#                 {"role": "user", "content": f"Contract data: {contract_data}"}
#             ],
#             temperature=0.1,
#             max_tokens=1000
#         )
        
#         result = response.choices[0].message.content.strip()
#         # Clean JSON response
#         if result.startswith("```json"):
#             result = result[7:]
#         if result.startswith("```"):
#             result = result[3:]
#         if result.endswith("```"):
#             result = result[:-3]
        
#         logger.info("Successfully calculated salary breakdown")
#         return result.strip()
#     except Exception as e:
#         logger.error(f"Salary calculation failed: {e}")
#         return f"Error: {str(e)}"

# @tool
# def validate_compliance_tool(salary_data: str) -> str:
#     """Validate salary calculations against Indian labor law compliance."""
#     try:
#         prompt = """Validate salary calculations against Indian labor law compliance.
#         Check PF limits, ESI eligibility, Professional tax rates, TDS calculations.
        
#         Return ONLY a valid JSON object:
#         {
#           "compliance_status": "COMPLIANT" or "NON_COMPLIANT",
#           "issues": ["list of specific issues if any"],
#           "validated_deductions": {
#             "pf": number,
#             "esi": number,
#             "professional_tax": number,
#             "tds": number
#           },
#           "recommendations": ["list of recommendations if needed"]
#         }"""
        
#         response = client.chat.completions.create(
#             model="gemini-2.0-flash-exp",
#             messages=[
#                 {"role": "system", "content": prompt},
#                 {"role": "user", "content": f"Salary data: {salary_data}"}
#             ],
#             temperature=0.1,
#             max_tokens=1000
#         )
        
#         result = response.choices[0].message.content.strip()
#         # Clean JSON response
#         if result.startswith("```json"):
#             result = result[7:]
#         if result.startswith("```"):
#             result = result[3:]
#         if result.endswith("```"):
#             result = result[:-3]
        
#         logger.info("Successfully validated compliance")
#         return result.strip()
#     except Exception as e:
#         logger.error(f"Compliance validation failed: {e}")
#         return f"Error: {str(e)}"

# @tool
# def detect_anomalies_tool(combined_data: str) -> str:
#     """Detect anomalies and inconsistencies in payroll calculations."""
#     try:
#         prompt = """Analyze payroll data for anomalies and inconsistencies.
#         Check for calculation errors, unusual amounts, missing deductions, data inconsistencies.
        
#         Return ONLY a valid JSON object:
#         {
#           "has_anomalies": boolean,
#           "anomalies": [
#             {
#               "type": "calculation_error|missing_deduction|unusual_amount|data_inconsistency",
#               "description": "detailed description",
#               "severity": "LOW|MEDIUM|HIGH",
#               "affected_field": "field name"
#             }
#           ],
#           "overall_status": "NORMAL|REVIEW_REQUIRED|CRITICAL",
#           "confidence_score": number_between_0_and_1
#         }"""
        
#         response = client.chat.completions.create(
#             model="gemini-2.0-flash-exp",
#             messages=[
#                 {"role": "system", "content": prompt},
#                 {"role": "user", "content": f"Combined payroll data: {combined_data}"}
#             ],
#             temperature=0.1,
#             max_tokens=1000
#         )
        
#         result = response.choices[0].message.content.strip()
#         # Clean JSON response
#         if result.startswith("```json"):
#             result = result[7:]
#         if result.startswith("```"):
#             result = result[3:]
#         if result.endswith("```"):
#             result = result[:-3]
        
#         logger.info("Successfully detected anomalies")
#         return result.strip()
#     except Exception as e:
#         logger.error(f"Anomaly detection failed: {e}")
#         return f"Error: {str(e)}"

# # List of tools
# tools = [
#     extract_pdf_text_tool,
#     parse_contract_data_tool,
#     calculate_salary_breakdown_tool,
#     validate_compliance_tool,
#     detect_anomalies_tool
# ]

# # System prompt for the agent
# system_prompt = SystemMessage(content="""You are a pure agentic AI for payroll processing using tools.

# To process an employment contract, follow these steps strictly:

# 1. Extract the file_path from the user message and use extract_pdf_text_tool to get the contract_text.

# 2. If successful, use parse_contract_data_tool with the contract_text to get contract_data as JSON string. Parse it to dict if needed for later.

# 3. If successful, use calculate_salary_breakdown_tool with the contract_data JSON string to get salary_data as JSON string.

# 4. If successful, use validate_compliance_tool with the salary_data JSON string to get compliance_data as JSON string.

# 5. If successful, combine the data into a JSON string: json.dumps({"contract": contract_data_dict, "salary": salary_data_dict, "compliance": compliance_data_dict}), then use detect_anomalies_tool with that combined_data string to get anomalies_data as JSON string.

# After obtaining anomalies_data, or if any step fails with 'Error:', stop and output the final answer as a single valid JSON object:
# {
#   "success": boolean,
#   "contract_data": {} or parsed JSON,
#   "salary_data": {} or parsed JSON,
#   "compliance_data": {} or parsed JSON,
#   "anomalies_data": {} or parsed JSON,
#   "errors": ["list of errors if any"]
# }

# Think step by step, recall previous tool results from the conversation history, and only call one tool at a time when needed. Do not use direct LLM for tasks; always use the provided tools.""")
    
# # Main AgenticAI class
# class PayrollAgenticAI:
#     """Pure Agentic AI system for payroll processing using LangGraph ReAct Agent."""
    
#     def __init__(self):
#         memory = MemorySaver()
#         self.graph = create_react_agent(
#             llm, 
#             tools, 
#             state_modifier=system_prompt,
#             checkpointer=memory
#         )
#         self.thread_id = "payroll_thread_1"
    
#     def process_contract(self, contract_path: str) -> Dict[str, Any]:
#         """Process employment contract through the agentic workflow."""
#         logger.info("🚀 AGENTIC_AI: Starting agentic payroll processing...")
        
#         try:
#             config = {"configurable": {"thread_id": self.thread_id}}
#             input_message = HumanMessage(content=f"Process the employment contract at: {contract_path}")
            
#             # Invoke the ReAct agent
#             final_state = self.graph.invoke({"messages": [input_message]}, config)
            
#             # Get the last message
#             messages = final_state["messages"]
#             last_message = messages[-1]
            
#             if isinstance(last_message, AIMessage) and last_message.tool_calls == []:
#                 # Parse the final JSON
#                 try:
#                     result = json.loads(last_message.content)
#                     result["messages"] = [msg.content for msg in messages if isinstance(msg, (HumanMessage, AIMessage)) and msg.tool_calls == []]
#                     if result.get("success", False):
#                         logger.info("🎉 AGENTIC_AI: Agent completed successfully!")
#                     else:
#                         logger.error(f"🚫 AGENTIC_AI: Agent reported errors - {result.get('errors', [])}")
#                     return result
#                 except json.JSONDecodeError as e:
#                     logger.error(f"🚫 AGENTIC_AI: Failed to parse final JSON - {str(e)}")
#                     return {
#                         "success": False,
#                         "errors": [f"Failed to parse final output: {str(e)}"],
#                         "messages": [msg.content for msg in messages if isinstance(msg, (HumanMessage, AIMessage)) and msg.tool_calls == []]
#                     }
#             else:
#                 logger.error("🚫 AGENTIC_AI: Agent did not produce a final answer")
#                 return {
#                     "success": False,
#                     "errors": ["Agent did not complete processing"],
#                     "messages": [msg.content for msg in messages if isinstance(msg, (HumanMessage, AIMessage)) and msg.tool_calls == []]
#                 }
                
#         except Exception as e:
#             logger.error(f"🚫 AGENTIC_AI: Workflow execution failed - {str(e)}")
#             return {
#                 "success": False,
#                 "errors": [str(e)],
#                 "messages": []
#             }
    
#     def get_processing_history(self) -> List[str]:
#         """Get the processing history from the workflow."""
#         try:
#             config = {"configurable": {"thread_id": self.thread_id}}
#             state = self.graph.get_state(config)
#             return [msg.content for msg in state.values.get("messages", []) if isinstance(msg, (HumanMessage, AIMessage)) and msg.tool_calls == []]
#         except:
#             return []

# # Streamlit Integration
# def main():
#     """Main Streamlit application."""
#     st.set_page_config(
#         page_title="AgenticAI Payroll System",
#         page_icon="🤖", 
#         layout="wide"
#     )
    
#     st.title("🤖 AgenticAI Payroll Processing System")
#     st.markdown("**Pure Agentic AI using LangGraph ReAct Agent**")
    
#     # Initialize AgenticAI system
#     if 'agentic_ai' not in st.session_state:
#         st.session_state.agentic_ai = PayrollAgenticAI()
#         st.session_state.processing_result = None
    
#     # File upload
#     col1, col2 = st.columns([3, 1])
    
#     with col1:
#         contract_file = st.file_uploader(
#             "Upload Employee Contract PDF",
#             type=["pdf"],
#             help="Upload employment contract for agentic AI processing"
#         )
    
#     with col2:
#         if st.button("🚀 Process with AgenticAI", type="primary", disabled=not contract_file):
#             if contract_file:
#                 st.session_state.processing_result = None
                
#                 with st.spinner("🤖 AgenticAI agent is processing..."):
#                     try:
#                         # Save uploaded file
#                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#                             tmp.write(contract_file.read())
#                             contract_path = tmp.name
                        
#                         # Process through AgenticAI
#                         result = st.session_state.agentic_ai.process_contract(contract_path)
#                         st.session_state.processing_result = result
                        
#                         if result["success"]:
#                             st.success("✅ AgenticAI processing completed successfully!")
#                         else:
#                             st.error(f"❌ AgenticAI processing failed: {result.get('errors', [])}")
                        
#                         # Clean up temp file
#                         os.unlink(contract_path)
                        
#                     except Exception as e:
#                         st.error(f"❌ Unexpected error: {str(e)}")
    
#     # Display results
#     if st.session_state.processing_result:
#         result = st.session_state.processing_result
        
#         if result["success"]:
#             st.header("📊 AgenticAI Processing Results")
            
#             # Agent Messages
#             with st.expander("🤖 Agent Communications", expanded=False):
#                 for i, message in enumerate(result.get("messages", []), 1):
#                     st.write(f"**Step {i}:** {message}")
            
#             # Employee Info
#             if result.get("contract_data"):
#                 st.subheader("👤 Employee Information") 
#                 contract_data = result["contract_data"]
#                 col1, col2, col3 = st.columns(3)
#                 with col1:
#                     st.metric("Name", contract_data.get("employee_name", "N/A"))
#                 with col2:
#                     st.metric("Department", contract_data.get("department", "N/A"))
#                 with col3:
#                     st.metric("Designation", contract_data.get("designation", "N/A"))
            
#             # Salary Breakdown
#             if result.get("salary_data"):
#                 st.subheader("💰 Salary Breakdown")
#                 salary_data = result["salary_data"]
#                 col1, col2, col3 = st.columns(3)
                
#                 gross = salary_data.get('gross_salary', 0)
#                 net = salary_data.get('net_salary', 0)
#                 total_deductions = sum(salary_data.get('deductions', {}).values())
                
#                 with col1:
#                     st.metric("Gross Salary", f"₹{gross:,.2f}")
#                 with col2:
#                     st.metric("Total Deductions", f"₹{total_deductions:,.2f}")  
#                 with col3:
#                     st.metric("Net Salary", f"₹{net:,.2f}")
            
#             # Compliance & Anomalies
#             col1, col2 = st.columns(2)
            
#             with col1:
#                 if result.get("compliance_data"):
#                     st.subheader("⚖️ Compliance Status")
#                     compliance_data = result["compliance_data"]
#                     status = compliance_data.get('compliance_status', 'UNKNOWN')
#                     if status == 'COMPLIANT':
#                         st.success("✅ All calculations compliant")
#                     else:
#                         st.warning("⚠️ Compliance issues detected")
#                         issues = compliance_data.get('issues', [])
#                         for issue in issues:
#                             st.write(f"• {issue}")
            
#             with col2:
#                 if result.get("anomalies_data"):
#                     st.subheader("🔍 Anomaly Detection")
#                     anomalies_data = result["anomalies_data"]
#                     if anomalies_data.get('has_anomalies'):
#                         anomaly_count = len(anomalies_data.get('anomalies', []))
#                         st.warning(f"⚠️ {anomaly_count} issues found")
#                         for anomaly in anomalies_data.get('anomalies', []):
#                             severity = anomaly.get('severity', 'LOW')
#                             description = anomaly.get('description', 'Unknown')
#                             st.write(f"• **{severity}**: {description}")
#                     else:
#                         st.success("✅ No anomalies detected")
        
#         else:
#             st.header("❌ AgenticAI Processing Failed")
#             for error in result.get("errors", []):
#                 st.error(f"Error: {error}")
            
#             # Show agent messages even on failure
#             if result.get("messages"):
#                 with st.expander("🤖 Agent Communications", expanded=True):
#                     for i, message in enumerate(result["messages"], 1):
#                         st.write(f"**Step {i}:** {message}")
    
#     else:
#         st.info("👆 Upload a contract PDF to start AgenticAI processing")
#         st.markdown("""
#         **🤖 How AgenticAI Works:**
        
#         A single ReAct agent autonomously processes the contract by deciding which tools to use step-by-step, following the defined workflow. The agent thinks, acts by calling tools, observes results, and continues until completion or error.
        
#         Pure agentic decision-making powered by LangGraph!
#         """)
    
#     # Footer
#     st.markdown("---")
#     st.markdown("*Pure AgenticAI System powered by LangGraph • Autonomous Tool-Using Agent*")

# if __name__ == "__main__":
#     main()


# # import os
# # import json
# # import tempfile
# # import streamlit as st
# # from datetime import datetime
# # from typing import TypedDict, Annotated, List, Dict, Any
# # from PyPDF2 import PdfReader
# # from openai import OpenAI
# # import logging
# # from dotenv import load_dotenv

# # # LangGraph imports
# # from langgraph.prebuilt import create_react_agent
# # from langgraph.checkpoint.memory import MemorySaver
# # from langchain_core.tools import tool
# # from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage, AIMessage
# # from langchain_openai import ChatOpenAI

# # # Configuration
# # logging.basicConfig(
# #     level=logging.INFO,
# #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
# #     handlers=[
# #         logging.StreamHandler(),
# #         logging.FileHandler('agentic_payroll.log')
# #     ]
# # )
# # logger = logging.getLogger(__name__)

# # load_dotenv()
# # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # # Initialize OpenAI client for Gemini
# # client = OpenAI(
# #     api_key=GEMINI_API_KEY,
# #     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# # )

# # # Initialize ChatOpenAI for LangGraph (using Gemini via OpenAI API)
# # llm = ChatOpenAI(
# #     api_key=GEMINI_API_KEY,
# #     base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
# #     model="gemini-2.0-flash-exp",
# #     temperature=0.1
# # )

# # # Tools that the agent can use
# # @tool
# # def extract_pdf_text_tool(file_path: str) -> str:
# #     """Extract text content from a PDF file for contract analysis."""
# #     try:
# #         reader = PdfReader(file_path)
# #         text = ""
# #         for page in reader.pages:
# #             text += page.extract_text() or ""
# #         logger.info(f"Successfully extracted {len(text)} characters from PDF")
# #         return text.strip()
# #     except Exception as e:
# #         logger.error(f"PDF extraction failed: {e}")
# #         return f"Error: {str(e)}"

# # @tool
# # def parse_contract_data_tool(contract_text: str) -> str:
# #     """Parse employee contract data using LLM analysis."""
# #     try:
# #         prompt = """Extract employee salary details from this employment contract.
# #         Return ONLY a valid JSON object with this exact structure:
# #         {
# #           "employee_name": "string",
# #           "employee_id": "string or null", 
# #           "department": "string or null",
# #           "designation": "string or null",
# #           "location": "string",
# #           "salary_structure": {
# #             "basic": number,
# #             "hra": number,
# #             "allowances": number,
# #             "gross": number
# #           }
# #         }"""
        
# #         response = client.chat.completions.create(
# #             model="gemini-2.0-flash-exp",
# #             messages=[
# #                 {"role": "system", "content": prompt},
# #                 {"role": "user", "content": f"Contract text: {contract_text}"}
# #             ],
# #             temperature=0.1,
# #             max_tokens=1000
# #         )
        
# #         result = response.choices[0].message.content.strip()
# #         # Clean JSON response
# #         if result.startswith("```json"):
# #             result = result[7:]
# #         if result.startswith("```"):
# #             result = result[3:]
# #         if result.endswith("```"):
# #             result = result[:-3]
        
# #         logger.info("Successfully parsed contract data")
# #         return result.strip()
# #     except Exception as e:
# #         logger.error(f"Contract parsing failed: {e}")
# #         return f"Error: {str(e)}"

# # @tool
# # def calculate_salary_breakdown_tool(contract_data: str) -> str:
# #     """Calculate detailed salary breakdown with Indian payroll deductions."""
# #     try:
# #         prompt = """Calculate monthly salary breakdown for Indian payroll based on the contract data.
# #         Apply standard Indian deductions:
# #         - PF: 12% of basic (max Rs.1,800)
# #         - ESI: 0.75% of gross (if gross <= Rs.21,000)
# #         - Professional Tax: Rs.200/month (if salary > Rs.15,000)
# #         - TDS: Estimate based on annual salary
        
# #         Return ONLY a valid JSON object:
# #         {
# #           "gross_salary": number,
# #           "deductions": {
# #             "pf": number,
# #             "esi": number,
# #             "professional_tax": number,
# #             "tds": number
# #           },
# #           "net_salary": number
# #         }"""
        
# #         response = client.chat.completions.create(
# #             model="gemini-2.0-flash-exp",
# #             messages=[
# #                 {"role": "system", "content": prompt},
# #                 {"role": "user", "content": f"Contract data: {contract_data}"}
# #             ],
# #             temperature=0.1,
# #             max_tokens=1000
# #         )
        
# #         result = response.choices[0].message.content.strip()
# #         # Clean JSON response
# #         if result.startswith("```json"):
# #             result = result[7:]
# #         if result.startswith("```"):
# #             result = result[3:]
# #         if result.endswith("```"):
# #             result = result[:-3]
        
# #         logger.info("Successfully calculated salary breakdown")
# #         return result.strip()
# #     except Exception as e:
# #         logger.error(f"Salary calculation failed: {e}")
# #         return f"Error: {str(e)}"

# # @tool
# # def validate_compliance_tool(salary_data: str) -> str:
# #     """Validate salary calculations against Indian labor law compliance."""
# #     try:
# #         prompt = """Validate salary calculations against Indian labor law compliance.
# #         Check PF limits, ESI eligibility, Professional tax rates, TDS calculations.
        
# #         Return ONLY a valid JSON object:
# #         {
# #           "compliance_status": "COMPLIANT" or "NON_COMPLIANT",
# #           "issues": ["list of specific issues if any"],
# #           "validated_deductions": {
# #             "pf": number,
# #             "esi": number,
# #             "professional_tax": number,
# #             "tds": number
# #           },
# #           "recommendations": ["list of recommendations if needed"]
# #         }"""
        
# #         response = client.chat.completions.create(
# #             model="gemini-2.0-flash-exp",
# #             messages=[
# #                 {"role": "system", "content": prompt},
# #                 {"role": "user", "content": f"Salary data: {salary_data}"}
# #             ],
# #             temperature=0.1,
# #             max_tokens=1000
# #         )
        
# #         result = response.choices[0].message.content.strip()
# #         # Clean JSON response
# #         if result.startswith("```json"):
# #             result = result[7:]
# #         if result.startswith("```"):
# #             result = result[3:]
# #         if result.endswith("```"):
# #             result = result[:-3]
        
# #         logger.info("Successfully validated compliance")
# #         return result.strip()
# #     except Exception as e:
# #         logger.error(f"Compliance validation failed: {e}")
# #         return f"Error: {str(e)}"

# # @tool
# # def detect_anomalies_tool(combined_data: str) -> str:
# #     """Detect anomalies and inconsistencies in payroll calculations."""
# #     try:
# #         prompt = """Analyze payroll data for anomalies and inconsistencies.
# #         Check for calculation errors, unusual amounts, missing deductions, data inconsistencies.
        
# #         Return ONLY a valid JSON object:
# #         {
# #           "has_anomalies": boolean,
# #           "anomalies": [
# #             {
# #               "type": "calculation_error|missing_deduction|unusual_amount|data_inconsistency",
# #               "description": "detailed description",
# #               "severity": "LOW|MEDIUM|HIGH",
# #               "affected_field": "field name"
# #             }
# #           ],
# #           "overall_status": "NORMAL|REVIEW_REQUIRED|CRITICAL",
# #           "confidence_score": number_between_0_and_1
# #         }"""
        
# #         response = client.chat.completions.create(
# #             model="gemini-2.0-flash-exp",
# #             messages=[
# #                 {"role": "system", "content": prompt},
# #                 {"role": "user", "content": f"Combined payroll data: {combined_data}"}
# #             ],
# #             temperature=0.1,
# #             max_tokens=1000
# #         )
        
# #         result = response.choices[0].message.content.strip()
# #         # Clean JSON response
# #         if result.startswith("```json"):
# #             result = result[7:]
# #         if result.startswith("```"):
# #             result = result[3:]
# #         if result.endswith("```"):
# #             result = result[:-3]
        
# #         logger.info("Successfully detected anomalies")
# #         return result.strip()
# #     except Exception as e:
# #         logger.error(f"Anomaly detection failed: {e}")
# #         return f"Error: {str(e)}"

# # # List of tools
# # tools = [
# #     extract_pdf_text_tool,
# #     parse_contract_data_tool,
# #     calculate_salary_breakdown_tool,
# #     validate_compliance_tool,
# #     detect_anomalies_tool
# # ]

# # # System prompt for the agent
# # system_prompt = SystemMessage(content="""You are a pure agentic AI for payroll processing using tools.

# # To process an employment contract, follow these steps strictly:

# # 1. Extract the file_path from the user message and use extract_pdf_text_tool to get the contract_text.

# # 2. If successful, use parse_contract_data_tool with the contract_text to get contract_data as JSON string. Parse it to dict if needed for later.

# # 3. If successful, use calculate_salary_breakdown_tool with the contract_data JSON string to get salary_data as JSON string.

# # 4. If successful, use validate_compliance_tool with the salary_data JSON string to get compliance_data as JSON string.

# # 5. If successful, combine the data into a JSON string: json.dumps({"contract": contract_data_dict, "salary": salary_data_dict, "compliance": compliance_data_dict}), then use detect_anomalies_tool with that combined_data string to get anomalies_data as JSON string.

# # After obtaining anomalies_data, or if any step fails with 'Error:', stop and output the final answer as a single valid JSON object:
# # {
# #   "success": boolean,
# #   "contract_data": {} or parsed JSON,
# #   "salary_data": {} or parsed JSON,
# #   "compliance_data": {} or parsed JSON,
# #   "anomalies_data": {} or parsed JSON,
# #   "errors": ["list of errors if any"]
# # }

# # Think step by step, recall previous tool results from the conversation history, and only call one tool at a time when needed. Do not use direct LLM for tasks; always use the provided tools.""")
    
# # # Main AgenticAI class
# # class PayrollAgenticAI:
# #     """Pure Agentic AI system for payroll processing using LangGraph ReAct Agent."""
    
# #     def __init__(self):
# #         memory = MemorySaver()
# #         self.graph = create_react_agent(
# #             llm, 
# #             tools, 
# #             messages_modifier=system_prompt,
# #             checkpointer=memory
# #         )
# #         self.thread_id = "payroll_thread_1"
    
# #     def process_contract(self, contract_path: str) -> Dict[str, Any]:
# #         """Process employment contract through the agentic workflow."""
# #         logger.info("🚀 AGENTIC_AI: Starting agentic payroll processing...")
        
# #         try:
# #             config = {"configurable": {"thread_id": self.thread_id}}
# #             input_message = HumanMessage(content=f"Process the employment contract at: {contract_path}")
            
# #             # Invoke the ReAct agent
# #             final_state = self.graph.invoke({"messages": [input_message]}, config)
            
# #             # Get the last message
# #             messages = final_state["messages"]
# #             last_message = messages[-1]
            
# #             if isinstance(last_message, AIMessage) and last_message.tool_calls == []:
# #                 # Parse the final JSON
# #                 try:
# #                     result = json.loads(last_message.content)
# #                     result["messages"] = [msg.content for msg in messages if isinstance(msg, (HumanMessage, AIMessage)) and msg.tool_calls == []]
# #                     if result.get("success", False):
# #                         logger.info("🎉 AGENTIC_AI: Agent completed successfully!")
# #                     else:
# #                         logger.error(f"🚫 AGENTIC_AI: Agent reported errors - {result.get('errors', [])}")
# #                     return result
# #                 except json.JSONDecodeError as e:
# #                     logger.error(f"🚫 AGENTIC_AI: Failed to parse final JSON - {str(e)}")
# #                     return {
# #                         "success": False,
# #                         "errors": [f"Failed to parse final output: {str(e)}"],
# #                         "messages": [msg.content for msg in messages if isinstance(msg, (HumanMessage, AIMessage)) and msg.tool_calls == []]
# #                     }
# #             else:
# #                 logger.error("🚫 AGENTIC_AI: Agent did not produce a final answer")
# #                 return {
# #                     "success": False,
# #                     "errors": ["Agent did not complete processing"],
# #                     "messages": [msg.content for msg in messages if isinstance(msg, (HumanMessage, AIMessage)) and msg.tool_calls == []]
# #                 }
                
# #         except Exception as e:
# #             logger.error(f"🚫 AGENTIC_AI: Workflow execution failed - {str(e)}")
# #             return {
# #                 "success": False,
# #                 "errors": [str(e)],
# #                 "messages": []
# #             }
    
# #     def get_processing_history(self) -> List[str]:
# #         """Get the processing history from the workflow."""
# #         try:
# #             config = {"configurable": {"thread_id": self.thread_id}}
# #             state = self.graph.get_state(config)
# #             return [msg.content for msg in state.values.get("messages", []) if isinstance(msg, (HumanMessage, AIMessage)) and msg.tool_calls == []]
# #         except:
# #             return []

# # # Streamlit Integration
# # def main():
# #     """Main Streamlit application."""
# #     st.set_page_config(
# #         page_title="AgenticAI Payroll System",
# #         page_icon="🤖", 
# #         layout="wide"
# #     )
    
# #     st.title("🤖 AgenticAI Payroll Processing System")
# #     st.markdown("**Pure Agentic AI using LangGraph ReAct Agent**")
    
# #     # Initialize AgenticAI system
# #     if 'agentic_ai' not in st.session_state:
# #         st.session_state.agentic_ai = PayrollAgenticAI()
# #         st.session_state.processing_result = None
    
# #     # File upload
# #     col1, col2 = st.columns([3, 1])
    
# #     with col1:
# #         contract_file = st.file_uploader(
# #             "Upload Employee Contract PDF",
# #             type=["pdf"],
# #             help="Upload employment contract for agentic AI processing"
# #         )
    
# #     with col2:
# #         if st.button("🚀 Process with AgenticAI", type="primary", disabled=not contract_file):
# #             if contract_file:
# #                 st.session_state.processing_result = None
                
# #                 with st.spinner("🤖 AgenticAI agent is processing..."):
# #                     try:
# #                         # Save uploaded file
# #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# #                             tmp.write(contract_file.read())
# #                             contract_path = tmp.name
                        
# #                         # Process through AgenticAI
# #                         result = st.session_state.agentic_ai.process_contract(contract_path)
# #                         st.session_state.processing_result = result
                        
# #                         if result["success"]:
# #                             st.success("✅ AgenticAI processing completed successfully!")
# #                         else:
# #                             st.error(f"❌ AgenticAI processing failed: {result.get('errors', [])}")
                        
# #                         # Clean up temp file
# #                         os.unlink(contract_path)
                        
# #                     except Exception as e:
# #                         st.error(f"❌ Unexpected error: {str(e)}")
    
# #     # Display results
# #     if st.session_state.processing_result:
# #         result = st.session_state.processing_result
        
# #         if result["success"]:
# #             st.header("📊 AgenticAI Processing Results")
            
# #             # Agent Messages
# #             with st.expander("🤖 Agent Communications", expanded=False):
# #                 for i, message in enumerate(result.get("messages", []), 1):
# #                     st.write(f"**Step {i}:** {message}")
            
# #             # Employee Info
# #             if result.get("contract_data"):
# #                 st.subheader("👤 Employee Information") 
# #                 contract_data = result["contract_data"]
# #                 col1, col2, col3 = st.columns(3)
# #                 with col1:
# #                     st.metric("Name", contract_data.get("employee_name", "N/A"))
# #                 with col2:
# #                     st.metric("Department", contract_data.get("department", "N/A"))
# #                 with col3:
# #                     st.metric("Designation", contract_data.get("designation", "N/A"))
            
# #             # Salary Breakdown
# #             if result.get("salary_data"):
# #                 st.subheader("💰 Salary Breakdown")
# #                 salary_data = result["salary_data"]
# #                 col1, col2, col3 = st.columns(3)
                
# #                 gross = salary_data.get('gross_salary', 0)
# #                 net = salary_data.get('net_salary', 0)
# #                 total_deductions = sum(salary_data.get('deductions', {}).values())
                
# #                 with col1:
# #                     st.metric("Gross Salary", f"₹{gross:,.2f}")
# #                 with col2:
# #                     st.metric("Total Deductions", f"₹{total_deductions:,.2f}")  
# #                 with col3:
# #                     st.metric("Net Salary", f"₹{net:,.2f}")
            
# #             # Compliance & Anomalies
# #             col1, col2 = st.columns(2)
            
# #             with col1:
# #                 if result.get("compliance_data"):
# #                     st.subheader("⚖️ Compliance Status")
# #                     compliance_data = result["compliance_data"]
# #                     status = compliance_data.get('compliance_status', 'UNKNOWN')
# #                     if status == 'COMPLIANT':
# #                         st.success("✅ All calculations compliant")
# #                     else:
# #                         st.warning("⚠️ Compliance issues detected")
# #                         issues = compliance_data.get('issues', [])
# #                         for issue in issues:
# #                             st.write(f"• {issue}")
            
# #             with col2:
# #                 if result.get("anomalies_data"):
# #                     st.subheader("🔍 Anomaly Detection")
# #                     anomalies_data = result["anomalies_data"]
# #                     if anomalies_data.get('has_anomalies'):
# #                         anomaly_count = len(anomalies_data.get('anomalies', []))
# #                         st.warning(f"⚠️ {anomaly_count} issues found")
# #                         for anomaly in anomalies_data.get('anomalies', []):
# #                             severity = anomaly.get('severity', 'LOW')
# #                             description = anomaly.get('description', 'Unknown')
# #                             st.write(f"• **{severity}**: {description}")
# #                     else:
# #                         st.success("✅ No anomalies detected")
        
# #         else:
# #             st.header("❌ AgenticAI Processing Failed")
# #             for error in result.get("errors", []):
# #                 st.error(f"Error: {error}")
            
# #             # Show agent messages even on failure
# #             if result.get("messages"):
# #                 with st.expander("🤖 Agent Communications", expanded=True):
# #                     for i, message in enumerate(result["messages"], 1):
# #                         st.write(f"**Step {i}:** {message}")
    
# #     else:
# #         st.info("👆 Upload a contract PDF to start AgenticAI processing")
# #         st.markdown("""
# #         **🤖 How AgenticAI Works:**
        
# #         A single ReAct agent autonomously processes the contract by deciding which tools to use step-by-step, following the defined workflow. The agent thinks, acts by calling tools, observes results, and continues until completion or error.
        
# #         Pure agentic decision-making powered by LangGraph!
# #         """)
    
# #     # Footer
# #     st.markdown("---")
# #     st.markdown("*Pure AgenticAI System powered by LangGraph • Autonomous Tool-Using Agent*")

# # if __name__ == "__main__":
# #     main()




# # # import os
# # # import json
# # # import tempfile
# # # import streamlit as st
# # # from datetime import datetime
# # # from typing import TypedDict, Annotated, List, Dict, Any
# # # from PyPDF2 import PdfReader
# # # from openai import OpenAI
# # # import logging
# # # from dotenv import load_dotenv

# # # # LangGraph imports
# # # from langgraph.graph import StateGraph, END
# # # from langgraph.prebuilt import ToolNode
# # # from langgraph.checkpoint.memory import MemorySaver
# # # from langchain_core.tools import tool
# # # from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
# # # from langchain_openai import ChatOpenAI

# # # # Configuration
# # # logging.basicConfig(
# # #     level=logging.INFO,
# # #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
# # #     handlers=[
# # #         logging.StreamHandler(),
# # #         logging.FileHandler('agentic_payroll.log')
# # #     ]
# # # )
# # # logger = logging.getLogger(__name__)

# # # load_dotenv()
# # # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # # # Initialize OpenAI client for Gemini
# # # client = OpenAI(
# # #     api_key=GEMINI_API_KEY,
# # #     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# # # )

# # # # Initialize ChatOpenAI for LangGraph (using Gemini via OpenAI API)
# # # llm = ChatOpenAI(
# # #     api_key=GEMINI_API_KEY,
# # #     base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
# # #     model="gemini-2.0-flash-exp",
# # #     temperature=0.1
# # # )

# # # # State definition for the agent system
# # # class PayrollState(TypedDict):
# # #     messages: Annotated[List[BaseMessage], "The conversation messages"]
# # #     contract_path: str
# # #     contract_data: Dict[str, Any]
# # #     salary_data: Dict[str, Any]
# # #     compliance_data: Dict[str, Any]
# # #     anomalies_data: Dict[str, Any]
# # #     current_agent: str
# # #     processing_complete: bool
# # #     errors: List[str]

# # # # Tools that agents can use
# # # @tool
# # # def extract_pdf_text_tool(file_path: str) -> str:
# # #     """Extract text content from a PDF file for contract analysis."""
# # #     try:
# # #         reader = PdfReader(file_path)
# # #         text = ""
# # #         for page in reader.pages:
# # #             text += page.extract_text() or ""
# # #         logger.info(f"Successfully extracted {len(text)} characters from PDF")
# # #         return text.strip()
# # #     except Exception as e:
# # #         logger.error(f"PDF extraction failed: {e}")
# # #         return f"Error: {str(e)}"

# # # @tool
# # # def parse_contract_data_tool(contract_text: str) -> str:
# # #     """Parse employee contract data using LLM analysis."""
# # #     try:
# # #         prompt = """Extract employee salary details from this employment contract.
# # #         Return ONLY a valid JSON object with this exact structure:
# # #         {
# # #           "employee_name": "string",
# # #           "employee_id": "string or null", 
# # #           "department": "string or null",
# # #           "designation": "string or null",
# # #           "location": "string",
# # #           "salary_structure": {
# # #             "basic": number,
# # #             "hra": number,
# # #             "allowances": number,
# # #             "gross": number
# # #           }
# # #         }"""
        
# # #         response = client.chat.completions.create(
# # #             model="gemini-2.0-flash-exp",
# # #             messages=[
# # #                 {"role": "system", "content": prompt},
# # #                 {"role": "user", "content": f"Contract text: {contract_text}"}
# # #             ],
# # #             temperature=0.1,
# # #             max_tokens=1000
# # #         )
        
# # #         result = response.choices[0].message.content.strip()
# # #         # Clean JSON response
# # #         if result.startswith("```json"):
# # #             result = result[7:]
# # #         if result.startswith("```"):
# # #             result = result[3:]
# # #         if result.endswith("```"):
# # #             result = result[:-3]
        
# # #         logger.info("Successfully parsed contract data")
# # #         return result.strip()
# # #     except Exception as e:
# # #         logger.error(f"Contract parsing failed: {e}")
# # #         return f"Error: {str(e)}"

# # # @tool
# # # def calculate_salary_breakdown_tool(contract_data: str) -> str:
# # #     """Calculate detailed salary breakdown with Indian payroll deductions."""
# # #     try:
# # #         prompt = """Calculate monthly salary breakdown for Indian payroll based on the contract data.
# # #         Apply standard Indian deductions:
# # #         - PF: 12% of basic (max Rs.1,800)
# # #         - ESI: 0.75% of gross (if gross <= Rs.21,000)
# # #         - Professional Tax: Rs.200/month (if salary > Rs.15,000)
# # #         - TDS: Estimate based on annual salary
        
# # #         Return ONLY a valid JSON object:
# # #         {
# # #           "gross_salary": number,
# # #           "deductions": {
# # #             "pf": number,
# # #             "esi": number,
# # #             "professional_tax": number,
# # #             "tds": number
# # #           },
# # #           "net_salary": number
# # #         }"""
        
# # #         response = client.chat.completions.create(
# # #             model="gemini-2.0-flash-exp",
# # #             messages=[
# # #                 {"role": "system", "content": prompt},
# # #                 {"role": "user", "content": f"Contract data: {contract_data}"}
# # #             ],
# # #             temperature=0.1,
# # #             max_tokens=1000
# # #         )
        
# # #         result = response.choices[0].message.content.strip()
# # #         # Clean JSON response
# # #         if result.startswith("```json"):
# # #             result = result[7:]
# # #         if result.startswith("```"):
# # #             result = result[3:]
# # #         if result.endswith("```"):
# # #             result = result[:-3]
        
# # #         logger.info("Successfully calculated salary breakdown")
# # #         return result.strip()
# # #     except Exception as e:
# # #         logger.error(f"Salary calculation failed: {e}")
# # #         return f"Error: {str(e)}"

# # # @tool
# # # def validate_compliance_tool(salary_data: str) -> str:
# # #     """Validate salary calculations against Indian labor law compliance."""
# # #     try:
# # #         prompt = """Validate salary calculations against Indian labor law compliance.
# # #         Check PF limits, ESI eligibility, Professional tax rates, TDS calculations.
        
# # #         Return ONLY a valid JSON object:
# # #         {
# # #           "compliance_status": "COMPLIANT" or "NON_COMPLIANT",
# # #           "issues": ["list of specific issues if any"],
# # #           "validated_deductions": {
# # #             "pf": number,
# # #             "esi": number,
# # #             "professional_tax": number,
# # #             "tds": number
# # #           },
# # #           "recommendations": ["list of recommendations if needed"]
# # #         }"""
        
# # #         response = client.chat.completions.create(
# # #             model="gemini-2.0-flash-exp",
# # #             messages=[
# # #                 {"role": "system", "content": prompt},
# # #                 {"role": "user", "content": f"Salary data: {salary_data}"}
# # #             ],
# # #             temperature=0.1,
# # #             max_tokens=1000
# # #         )
        
# # #         result = response.choices[0].message.content.strip()
# # #         # Clean JSON response
# # #         if result.startswith("```json"):
# # #             result = result[7:]
# # #         if result.startswith("```"):
# # #             result = result[3:]
# # #         if result.endswith("```"):
# # #             result = result[:-3]
        
# # #         logger.info("Successfully validated compliance")
# # #         return result.strip()
# # #     except Exception as e:
# # #         logger.error(f"Compliance validation failed: {e}")
# # #         return f"Error: {str(e)}"

# # # @tool
# # # def detect_anomalies_tool(combined_data: str) -> str:
# # #     """Detect anomalies and inconsistencies in payroll calculations."""
# # #     try:
# # #         prompt = """Analyze payroll data for anomalies and inconsistencies.
# # #         Check for calculation errors, unusual amounts, missing deductions, data inconsistencies.
        
# # #         Return ONLY a valid JSON object:
# # #         {
# # #           "has_anomalies": boolean,
# # #           "anomalies": [
# # #             {
# # #               "type": "calculation_error|missing_deduction|unusual_amount|data_inconsistency",
# # #               "description": "detailed description",
# # #               "severity": "LOW|MEDIUM|HIGH",
# # #               "affected_field": "field name"
# # #             }
# # #           ],
# # #           "overall_status": "NORMAL|REVIEW_REQUIRED|CRITICAL",
# # #           "confidence_score": number_between_0_and_1
# # #         }"""
        
# # #         response = client.chat.completions.create(
# # #             model="gemini-2.0-flash-exp",
# # #             messages=[
# # #                 {"role": "system", "content": prompt},
# # #                 {"role": "user", "content": f"Combined payroll data: {combined_data}"}
# # #             ],
# # #             temperature=0.1,
# # #             max_tokens=1000
# # #         )
        
# # #         result = response.choices[0].message.content.strip()
# # #         # Clean JSON response
# # #         if result.startswith("```json"):
# # #             result = result[7:]
# # #         if result.startswith("```"):
# # #             result = result[3:]
# # #         if result.endswith("```"):
# # #             result = result[:-3]
        
# # #         logger.info("Successfully detected anomalies")
# # #         return result.strip()
# # #     except Exception as e:
# # #         logger.error(f"Anomaly detection failed: {e}")
# # #         return f"Error: {str(e)}"

# # # # Create tool node
# # # tools = [
# # #     extract_pdf_text_tool,
# # #     parse_contract_data_tool,
# # #     calculate_salary_breakdown_tool,
# # #     validate_compliance_tool,
# # #     detect_anomalies_tool
# # # ]
# # # tool_node = ToolNode(tools)

# # # # Agent nodes
# # # def contract_reader_agent(state: PayrollState) -> PayrollState:
# # #     """Contract Reader Agent - Extracts and parses contract data."""
# # #     logger.info("[CONTRACT_READER_AGENT] Starting contract analysis...")
    
# # #     messages = state["messages"]
# # #     messages.append(AIMessage(content="I am the Contract Reader Agent. I will extract and analyze the employment contract."))
    
# # #     # Check if we have a contract path
# # #     if not state.get("contract_path"):
# # #         error = "No contract file provided"
# # #         logger.error(f"[CONTRACT_READER_AGENT] {error}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=f"Error: {error}")],
# # #             "errors": state.get("errors", []) + [error]
# # #         }
    
# # #     # Agent decides to use PDF extraction tool
# # #     messages.append(AIMessage(content=f"I will extract text from the PDF contract: {state['contract_path']}"))
    
# # #     # Extract PDF text
# # #     pdf_text = extract_pdf_text_tool.invoke({"file_path": state["contract_path"]})
    
# # #     if pdf_text.startswith("Error:"):
# # #         logger.error(f"[CONTRACT_READER_AGENT] {pdf_text}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=pdf_text)],
# # #             "errors": state.get("errors", []) + [pdf_text]
# # #         }
    
# # #     # Agent decides to parse contract data
# # #     messages.append(AIMessage(content="PDF text extracted successfully. Now I will parse the contract data."))
    
# # #     contract_json = parse_contract_data_tool.invoke({"contract_text": pdf_text})
    
# # #     if contract_json.startswith("Error:"):
# # #         logger.error(f"[CONTRACT_READER_AGENT] {contract_json}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=contract_json)],
# # #             "errors": state.get("errors", []) + [contract_json]
# # #         }
    
# # #     try:
# # #         contract_data = json.loads(contract_json)
# # #         employee_name = contract_data.get('employee_name', 'Unknown')
# # #         gross_salary = contract_data.get('salary_structure', {}).get('gross', 0)
        
# # #         logger.info(f"[CONTRACT_READER_AGENT] Successfully extracted data for {employee_name}")
# # #         logger.info(f"[CONTRACT_READER_AGENT] Gross salary: Rs.{gross_salary}")
        
# # #         success_msg = f"Successfully extracted contract data for {employee_name} with gross salary Rs.{gross_salary:,.2f}"
# # #         messages.append(AIMessage(content=success_msg))
        
# # #         return {
# # #             **state,
# # #             "messages": messages,
# # #             "contract_data": contract_data,
# # #             "current_agent": "salary_calculator"
# # #         }
# # #     except json.JSONDecodeError as e:
# # #         error = f"Failed to parse contract JSON: {str(e)}"
# # #         logger.error(f"[CONTRACT_READER_AGENT] {error}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=error)],
# # #             "errors": state.get("errors", []) + [error]
# # #         }

# # # def salary_calculator_agent(state: PayrollState) -> PayrollState:
# # #     """Salary Calculator Agent - Calculates salary breakdown."""
# # #     logger.info("[SALARY_CALCULATOR_AGENT] Starting salary calculations...")
    
# # #     messages = state["messages"]
# # #     messages.append(AIMessage(content="I am the Salary Calculator Agent. I will calculate the detailed salary breakdown."))
    
# # #     if not state.get("contract_data"):
# # #         error = "No contract data available for salary calculation"
# # #         logger.error(f"[SALARY_CALCULATOR_AGENT] {error}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=f"Error: {error}")],
# # #             "errors": state.get("errors", []) + [error]
# # #         }
    
# # #     # Agent decides to calculate salary breakdown
# # #     contract_json = json.dumps(state["contract_data"])
# # #     messages.append(AIMessage(content="I will calculate the salary breakdown with Indian payroll deductions."))
    
# # #     salary_json = calculate_salary_breakdown_tool.invoke({"contract_data": contract_json})
    
# # #     if salary_json.startswith("Error:"):
# # #         logger.error(f"[SALARY_CALCULATOR_AGENT] {salary_json}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=salary_json)],
# # #             "errors": state.get("errors", []) + [salary_json]
# # #         }
    
# # #     try:
# # #         salary_data = json.loads(salary_json)
# # #         gross = salary_data.get('gross_salary', 0)
# # #         net = salary_data.get('net_salary', 0)
# # #         total_deductions = sum(salary_data.get('deductions', {}).values())
        
# # #         logger.info(f"[SALARY_CALCULATOR_AGENT] Gross: Rs.{gross:,.2f}, Net: Rs.{net:,.2f}")
        
# # #         success_msg = f"Calculated salary breakdown - Gross: Rs.{gross:,.2f}, Net: Rs.{net:,.2f}, Deductions: Rs.{total_deductions:,.2f}"
# # #         messages.append(AIMessage(content=success_msg))
        
# # #         return {
# # #             **state,
# # #             "messages": messages,
# # #             "salary_data": salary_data,
# # #             "current_agent": "compliance_checker"
# # #         }
# # #     except json.JSONDecodeError as e:
# # #         error = f"Failed to parse salary JSON: {str(e)}"
# # #         logger.error(f"[SALARY_CALCULATOR_AGENT] {error}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=error)],
# # #             "errors": state.get("errors", []) + [error]
# # #         }

# # # def compliance_checker_agent(state: PayrollState) -> PayrollState:
# # #     """Compliance Checker Agent - Validates compliance with Indian labor laws."""
# # #     logger.info("[COMPLIANCE_CHECKER_AGENT] Starting compliance validation...")
    
# # #     messages = state["messages"]
# # #     messages.append(AIMessage(content="I am the Compliance Checker Agent. I will validate against Indian labor law compliance."))
    
# # #     if not state.get("salary_data"):
# # #         error = "No salary data available for compliance check"
# # #         logger.error(f"[COMPLIANCE_CHECKER_AGENT] {error}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=f"Error: {error}")],
# # #             "errors": state.get("errors", []) + [error]
# # #         }
    
# # #     # Agent decides to validate compliance
# # #     salary_json = json.dumps(state["salary_data"])
# # #     messages.append(AIMessage(content="I will validate all calculations against Indian labor law requirements."))
    
# # #     compliance_json = validate_compliance_tool.invoke({"salary_data": salary_json})
    
# # #     if compliance_json.startswith("Error:"):
# # #         logger.error(f"[COMPLIANCE_CHECKER_AGENT] {compliance_json}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=compliance_json)],
# # #             "errors": state.get("errors", []) + [compliance_json]
# # #         }
    
# # #     try:
# # #         compliance_data = json.loads(compliance_json)
# # #         status = compliance_data.get('compliance_status', 'UNKNOWN')
# # #         issues = compliance_data.get('issues', [])
        
# # #         if status == 'COMPLIANT':
# # #             logger.info("[COMPLIANCE_CHECKER_AGENT] All calculations are compliant")
# # #             success_msg = "✅ All calculations are compliant with Indian labor laws"
# # #         else:
# # #             logger.warning(f"[COMPLIANCE_CHECKER_AGENT] Compliance issues: {issues}")
# # #             success_msg = f"⚠️ Compliance issues found: {len(issues)} issues"
        
# # #         messages.append(AIMessage(content=success_msg))
        
# # #         return {
# # #             **state,
# # #             "messages": messages,
# # #             "compliance_data": compliance_data,
# # #             "current_agent": "anomaly_detector"
# # #         }
# # #     except json.JSONDecodeError as e:
# # #         error = f"Failed to parse compliance JSON: {str(e)}"
# # #         logger.error(f"[COMPLIANCE_CHECKER_AGENT] {error}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=error)],
# # #             "errors": state.get("errors", []) + [error]
# # #         }

# # # def anomaly_detector_agent(state: PayrollState) -> PayrollState:
# # #     """Anomaly Detector Agent - Detects anomalies in payroll data."""
# # #     logger.info("[ANOMALY_DETECTOR_AGENT] Starting anomaly detection...")
    
# # #     messages = state["messages"]
# # #     messages.append(AIMessage(content="I am the Anomaly Detector Agent. I will scan for any anomalies in the payroll data."))
    
# # #     # Combine all data for analysis
# # #     combined_data = {
# # #         "contract": state.get("contract_data", {}),
# # #         "salary": state.get("salary_data", {}),
# # #         "compliance": state.get("compliance_data", {})
# # #     }
    
# # #     if not any(combined_data.values()):
# # #         error = "No data available for anomaly detection"
# # #         logger.error(f"[ANOMALY_DETECTOR_AGENT] {error}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=f"Error: {error}")],
# # #             "errors": state.get("errors", []) + [error]
# # #         }
    
# # #     # Agent decides to detect anomalies
# # #     combined_json = json.dumps(combined_data)
# # #     messages.append(AIMessage(content="I will analyze all payroll data for anomalies and inconsistencies."))
    
# # #     anomalies_json = detect_anomalies_tool.invoke({"combined_data": combined_json})
    
# # #     if anomalies_json.startswith("Error:"):
# # #         logger.error(f"[ANOMALY_DETECTOR_AGENT] {anomalies_json}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=anomalies_json)],
# # #             "errors": state.get("errors", []) + [anomalies_json]
# # #         }
    
# # #     try:
# # #         anomalies_data = json.loads(anomalies_json)
# # #         has_anomalies = anomalies_data.get('has_anomalies', False)
# # #         anomaly_list = anomalies_data.get('anomalies', [])
        
# # #         if has_anomalies:
# # #             logger.warning(f"[ANOMALY_DETECTOR_AGENT] {len(anomaly_list)} anomalies detected")
# # #             success_msg = f"⚠️ {len(anomaly_list)} anomalies detected"
# # #             for anomaly in anomaly_list:
# # #                 severity = anomaly.get('severity', 'LOW')
# # #                 description = anomaly.get('description', 'Unknown')
# # #                 logger.info(f"[ANOMALY_DETECTOR_AGENT] - {severity}: {description}")
# # #         else:
# # #             logger.info("[ANOMALY_DETECTOR_AGENT] No anomalies found")
# # #             success_msg = "✅ No anomalies detected - all payroll data is consistent"
        
# # #         messages.append(AIMessage(content=success_msg))
        
# # #         logger.info("[ANOMALY_DETECTOR_AGENT] Processing completed successfully!")
        
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content="🎉 All agents completed processing successfully!")],
# # #             "anomalies_data": anomalies_data,
# # #             "processing_complete": True
# # #         }
# # #     except json.JSONDecodeError as e:
# # #         error = f"Failed to parse anomalies JSON: {str(e)}"
# # #         logger.error(f"[ANOMALY_DETECTOR_AGENT] {error}")
# # #         return {
# # #             **state,
# # #             "messages": messages + [AIMessage(content=error)],
# # #             "errors": state.get("errors", []) + [error]
# # #         }

# # # # Router function to determine next agent
# # # def agent_router(state: PayrollState) -> str:
# # #     """Route to the next agent based on current processing stage."""
# # #     current_agent = state.get("current_agent", "contract_reader")
    
# # #     if state.get("processing_complete"):
# # #         return END
    
# # #     if state.get("errors"):
# # #         return END
    
# # #     return current_agent

# # # # Build the LangGraph workflow
# # # def create_payroll_agent_graph():
# # #     """Create the LangGraph workflow for payroll processing."""
# # #     workflow = StateGraph(PayrollState)
    
# # #     # Add agent nodes
# # #     workflow.add_node("contract_reader", contract_reader_agent)
# # #     workflow.add_node("salary_calculator", salary_calculator_agent)
# # #     workflow.add_node("compliance_checker", compliance_checker_agent)
# # #     workflow.add_node("anomaly_detector", anomaly_detector_agent)
    
# # #     # Set entry point
# # #     workflow.set_entry_point("contract_reader")
    
# # #     # Add conditional routing
# # #     workflow.add_conditional_edges("contract_reader", agent_router)
# # #     workflow.add_conditional_edges("salary_calculator", agent_router)
# # #     workflow.add_conditional_edges("compliance_checker", agent_router)
# # #     workflow.add_conditional_edges("anomaly_detector", agent_router)
    
# # #     # Compile the graph
# # #     memory = MemorySaver()
# # #     return workflow.compile(checkpointer=memory)

# # # # Main AgenticAI class
# # # class PayrollAgenticAI:
# # #     """Pure Agentic AI system for payroll processing using LangGraph."""
    
# # #     def __init__(self):
# # #         self.graph = create_payroll_agent_graph()
# # #         self.thread_id = "payroll_thread_1"
    
# # #     def process_contract(self, contract_path: str) -> Dict[str, Any]:
# # #         """Process employment contract through the agentic workflow."""
# # #         logger.info("🚀 AGENTIC_AI: Starting multi-agent payroll processing...")
        
# # #         # Initial state
# # #         initial_state = {
# # #             "messages": [HumanMessage(content=f"Please process the employment contract at: {contract_path}")],
# # #             "contract_path": contract_path,
# # #             "contract_data": {},
# # #             "salary_data": {},
# # #             "compliance_data": {},
# # #             "anomalies_data": {},
# # #             "current_agent": "contract_reader",
# # #             "processing_complete": False,
# # #             "errors": []
# # #         }
        
# # #         try:
# # #             # Run the agentic workflow
# # #             config = {"configurable": {"thread_id": self.thread_id}}
# # #             final_state = self.graph.invoke(initial_state, config)
            
# # #             if final_state.get("processing_complete"):
# # #                 logger.info("🎉 AGENTIC_AI: All agents completed successfully!")
# # #                 return {
# # #                     "success": True,
# # #                     "contract_data": final_state.get("contract_data", {}),
# # #                     "salary_data": final_state.get("salary_data", {}),
# # #                     "compliance_data": final_state.get("compliance_data", {}),
# # #                     "anomalies_data": final_state.get("anomalies_data", {}),
# # #                     "messages": [msg.content for msg in final_state.get("messages", [])]
# # #                 }
# # #             else:
# # #                 errors = final_state.get("errors", [])
# # #                 logger.error(f"🚫 AGENTIC_AI: Processing failed - {errors}")
# # #                 return {
# # #                     "success": False,
# # #                     "errors": errors,
# # #                     "messages": [msg.content for msg in final_state.get("messages", [])]
# # #                 }
                
# # #         except Exception as e:
# # #             logger.error(f"🚫 AGENTIC_AI: Workflow execution failed - {str(e)}")
# # #             return {
# # #                 "success": False,
# # #                 "errors": [str(e)],
# # #                 "messages": []
# # #             }
    
# # #     def get_processing_history(self) -> List[str]:
# # #         """Get the processing history from the workflow."""
# # #         try:
# # #             config = {"configurable": {"thread_id": self.thread_id}}
# # #             state = self.graph.get_state(config)
# # #             return [msg.content for msg in state.values.get("messages", [])]
# # #         except:
# # #             return []

# # # # Streamlit Integration
# # # def main():
# # #     """Main Streamlit application."""
# # #     st.set_page_config(
# # #         page_title="AgenticAI Payroll System",
# # #         page_icon="🤖", 
# # #         layout="wide"
# # #     )
    
# # #     st.title("🤖 AgenticAI Payroll Processing System")
# # #     st.markdown("**Pure Agentic AI using LangGraph Multi-Agent Workflow**")
    
# # #     # Initialize AgenticAI system
# # #     if 'agentic_ai' not in st.session_state:
# # #         st.session_state.agentic_ai = PayrollAgenticAI()
# # #         st.session_state.processing_result = None
    
# # #     # File upload
# # #     col1, col2 = st.columns([3, 1])
    
# # #     with col1:
# # #         contract_file = st.file_uploader(
# # #             "Upload Employee Contract PDF",
# # #             type=["pdf"],
# # #             help="Upload employment contract for agentic AI processing"
# # #         )
    
# # #     with col2:
# # #         if st.button("🚀 Process with AgenticAI", type="primary", disabled=not contract_file):
# # #             if contract_file:
# # #                 st.session_state.processing_result = None
                
# # #                 with st.spinner("🤖 AgenticAI agents are processing..."):
# # #                     try:
# # #                         # Save uploaded file
# # #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # #                             tmp.write(contract_file.read())
# # #                             contract_path = tmp.name
                        
# # #                         # Process through AgenticAI
# # #                         result = st.session_state.agentic_ai.process_contract(contract_path)
# # #                         st.session_state.processing_result = result
                        
# # #                         if result["success"]:
# # #                             st.success("✅ AgenticAI processing completed successfully!")
# # #                         else:
# # #                             st.error(f"❌ AgenticAI processing failed: {result.get('errors', [])}")
                        
# # #                         # Clean up temp file
# # #                         os.unlink(contract_path)
                        
# # #                     except Exception as e:
# # #                         st.error(f"❌ Unexpected error: {str(e)}")
    
# # #     # Display results
# # #     if st.session_state.processing_result:
# # #         result = st.session_state.processing_result
        
# # #         if result["success"]:
# # #             st.header("📊 AgenticAI Processing Results")
            
# # #             # Agent Messages
# # #             with st.expander("🤖 Agent Communications", expanded=False):
# # #                 for i, message in enumerate(result.get("messages", []), 1):
# # #                     st.write(f"**Step {i}:** {message}")
            
# # #             # Employee Info
# # #             if result.get("contract_data"):
# # #                 st.subheader("👤 Employee Information") 
# # #                 contract_data = result["contract_data"]
# # #                 col1, col2, col3 = st.columns(3)
# # #                 with col1:
# # #                     st.metric("Name", contract_data.get("employee_name", "N/A"))
# # #                 with col2:
# # #                     st.metric("Department", contract_data.get("department", "N/A"))
# # #                 with col3:
# # #                     st.metric("Designation", contract_data.get("designation", "N/A"))
            
# # #             # Salary Breakdown
# # #             if result.get("salary_data"):
# # #                 st.subheader("💰 Salary Breakdown")
# # #                 salary_data = result["salary_data"]
# # #                 col1, col2, col3 = st.columns(3)
                
# # #                 gross = salary_data.get('gross_salary', 0)
# # #                 net = salary_data.get('net_salary', 0)
# # #                 total_deductions = sum(salary_data.get('deductions', {}).values())
                
# # #                 with col1:
# # #                     st.metric("Gross Salary", f"₹{gross:,.2f}")
# # #                 with col2:
# # #                     st.metric("Total Deductions", f"₹{total_deductions:,.2f}")  
# # #                 with col3:
# # #                     st.metric("Net Salary", f"₹{net:,.2f}")
            
# # #             # Compliance & Anomalies
# # #             col1, col2 = st.columns(2)
            
# # #             with col1:
# # #                 if result.get("compliance_data"):
# # #                     st.subheader("⚖️ Compliance Status")
# # #                     compliance_data = result["compliance_data"]
# # #                     status = compliance_data.get('compliance_status', 'UNKNOWN')
# # #                     if status == 'COMPLIANT':
# # #                         st.success("✅ All calculations compliant")
# # #                     else:
# # #                         st.warning("⚠️ Compliance issues detected")
# # #                         issues = compliance_data.get('issues', [])
# # #                         for issue in issues:
# # #                             st.write(f"• {issue}")
            
# # #             with col2:
# # #                 if result.get("anomalies_data"):
# # #                     st.subheader("🔍 Anomaly Detection")
# # #                     anomalies_data = result["anomalies_data"]
# # #                     if anomalies_data.get('has_anomalies'):
# # #                         anomaly_count = len(anomalies_data.get('anomalies', []))
# # #                         st.warning(f"⚠️ {anomaly_count} issues found")
# # #                         for anomaly in anomalies_data.get('anomalies', []):
# # #                             severity = anomaly.get('severity', 'LOW')
# # #                             description = anomaly.get('description', 'Unknown')
# # #                             st.write(f"• **{severity}**: {description}")
# # #                     else:
# # #                         st.success("✅ No anomalies detected")
        
# # #         else:
# # #             st.header("❌ AgenticAI Processing Failed")
# # #             for error in result.get("errors", []):
# # #                 st.error(f"Error: {error}")
            
# # #             # Show agent messages even on failure
# # #             if result.get("messages"):
# # #                 with st.expander("🤖 Agent Communications", expanded=True):
# # #                     for i, message in enumerate(result["messages"], 1):
# # #                         st.write(f"**Step {i}:** {message}")
    
# # #     else:
# # #         st.info("👆 Upload a contract PDF to start AgenticAI processing")
# # #         st.markdown("""
# # #         **🤖 How AgenticAI Works:**
        
# # #         1. **Contract Reader Agent** - Autonomously extracts and parses PDF contracts
# # #         2. **Salary Calculator Agent** - Independently calculates salary breakdowns 
# # #         3. **Compliance Checker Agent** - Validates against Indian labor laws
# # #         4. **Anomaly Detector Agent** - Detects inconsistencies and issues
        
# # #         Each agent makes its own decisions and uses tools as needed!
# # #         """)
    
# # #     # Footer
# # #     st.markdown("---")
# # #     st.markdown("*Pure AgenticAI System powered by LangGraph • Autonomous Multi-Agent Processing*")

# # # if __name__ == "__main__":
# # #     main()





# # # # # app.py
# # # # import os
# # # # import json
# # # # import tempfile
# # # # import streamlit as st
# # # # from datetime import datetime
# # # # from PyPDF2 import PdfReader
# # # # from openai import OpenAI
# # # # import logging

# # # # # Simple logging configuration without special encoding
# # # # logging.basicConfig(
# # # #     level=logging.INFO,
# # # #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
# # # #     handlers=[
# # # #         logging.StreamHandler(),
# # # #         logging.FileHandler('agent_communication.log')
# # # #     ]
# # # # )
# # # # logger = logging.getLogger(__name__)

# # # # # Environment setup
# # # # from dotenv import load_dotenv
# # # # load_dotenv()
# # # # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # # # # Initialize OpenAI client with Gemini
# # # # client = OpenAI(
# # # #     api_key=GEMINI_API_KEY,
# # # #     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# # # # )

# # # # class PayrollAgentSystem:
# # # #     def __init__(self):
# # # #         self.contract_data = {}
# # # #         self.salary_data = {}
# # # #         self.compliance_data = {}
# # # #         self.anomalies = {}
        
# # # #     def extract_pdf_text(self, file_path):
# # # #         """Extract text from PDF file"""
# # # #         try:
# # # #             reader = PdfReader(file_path)
# # # #             text = ""
# # # #             for page in reader.pages:
# # # #                 text += page.extract_text() or ""
# # # #             return text.strip()
# # # #         except Exception as e:
# # # #             logger.error(f"PDF extraction failed: {e}")
# # # #             return ""
    
# # # #     def llm_call(self, prompt, content):
# # # #         """Make LLM call with error handling"""
# # # #         try:
# # # #             response = client.chat.completions.create(
# # # #                 model="gemini-2.0-flash-exp",
# # # #                 messages=[
# # # #                     {"role": "system", "content": prompt},
# # # #                     {"role": "user", "content": content}
# # # #                 ],
# # # #                 temperature=0.1,
# # # #                 max_tokens=2000
# # # #             )
# # # #             return response.choices[0].message.content.strip()
# # # #         except Exception as e:
# # # #             logger.error(f"LLM call failed: {e}")
# # # #             return ""
    
# # # #     def safe_json_parse(self, text):
# # # #         """Safely parse JSON from LLM response"""
# # # #         try:
# # # #             # Clean up common JSON formatting issues
# # # #             text = text.strip()
# # # #             if text.startswith("```json"):
# # # #                 text = text[7:]
# # # #             if text.startswith("```"):
# # # #                 text = text[3:]
# # # #             if text.endswith("```"):
# # # #                 text = text[:-3]
# # # #             text = text.strip()
# # # #             return json.loads(text)
# # # #         except:
# # # #             logger.error(f"JSON parsing failed for: {text[:100]}...")
# # # #             return {}

# # # # class PayrollAgent:
# # # #     def __init__(self, name, agent_system):
# # # #         self.name = name
# # # #         self.agent_system = agent_system
    
# # # #     def log_agent_communication(self, message):
# # # #         """Log agent communication"""
# # # #         logger.info(f"[{self.name}] {message}")

# # # # class ContractReaderAgent(PayrollAgent):
# # # #     def __init__(self, agent_system):
# # # #         super().__init__("CONTRACT_READER_AGENT", agent_system)
    
# # # #     def process(self, file_path):
# # # #         self.log_agent_communication("Starting contract analysis...")
        
# # # #         text = self.agent_system.extract_pdf_text(file_path)
# # # #         if not text:
# # # #             self.log_agent_communication("FAILED - Could not extract text from PDF")
# # # #             return {"success": False, "error": "Failed to extract PDF text"}
        
# # # #         prompt = """Extract employee salary details from this employment contract.
# # # #         Return ONLY JSON with this structure:
# # # #         {
# # # #           "employee_name": "string",
# # # #           "employee_id": "string or null", 
# # # #           "department": "string or null",
# # # #           "designation": "string or null",
# # # #           "location": "string",
# # # #           "salary_structure": {
# # # #             "basic": number,
# # # #             "hra": number,
# # # #             "allowances": number,
# # # #             "gross": number
# # # #           }
# # # #         }"""
        
# # # #         response = self.agent_system.llm_call(prompt, f"Contract text: {text}")
# # # #         self.agent_system.contract_data = self.agent_system.safe_json_parse(response)
        
# # # #         employee_name = self.agent_system.contract_data.get('employee_name', 'Unknown')
# # # #         gross_salary = self.agent_system.contract_data.get('salary_structure', {}).get('gross', 0)
        
# # # #         self.log_agent_communication(f"SUCCESS - Extracted data for {employee_name}")
# # # #         self.log_agent_communication(f"Gross salary identified as Rs.{gross_salary}")
# # # #         self.log_agent_communication("Passing data to SALARY_CALCULATOR_AGENT...")
        
# # # #         return {"success": True, "data": self.agent_system.contract_data}

# # # # class SalaryCalculatorAgent(PayrollAgent):
# # # #     def __init__(self, agent_system):
# # # #         super().__init__("SALARY_CALCULATOR_AGENT", agent_system)
    
# # # #     def process(self):
# # # #         self.log_agent_communication("Received contract data, starting salary calculations...")
        
# # # #         if not self.agent_system.contract_data:
# # # #             self.log_agent_communication("FAILED - No contract data available")
# # # #             return {"success": False, "error": "No contract data available"}
        
# # # #         prompt = """Calculate monthly salary breakdown for Indian payroll.
# # # #         Apply standard deductions:
# # # #         - PF: 12% of basic (max Rs.1,800)
# # # #         - ESI: 0.75% of gross (if gross <= Rs.21,000)
# # # #         - Professional Tax: Rs.200/month (if salary > Rs.15,000)
# # # #         - TDS: Estimate based on annual salary
        
# # # #         Return ONLY JSON:
# # # #         {
# # # #           "gross_salary": number,
# # # #           "deductions": {
# # # #             "pf": number,
# # # #             "esi": number,
# # # #             "professional_tax": number,
# # # #             "tds": number
# # # #           },
# # # #           "net_salary": number
# # # #         }"""
        
# # # #         response = self.agent_system.llm_call(prompt, json.dumps(self.agent_system.contract_data))
# # # #         self.agent_system.salary_data = self.agent_system.safe_json_parse(response)
        
# # # #         gross = self.agent_system.salary_data.get('gross_salary', 0)
# # # #         net = self.agent_system.salary_data.get('net_salary', 0)
# # # #         total_deductions = sum(self.agent_system.salary_data.get('deductions', {}).values())
        
# # # #         self.log_agent_communication(f"SUCCESS - Calculated salary breakdown")
# # # #         self.log_agent_communication(f"Gross: Rs.{gross:,.2f}, Net: Rs.{net:,.2f}, Deductions: Rs.{total_deductions:,.2f}")
# # # #         self.log_agent_communication("Passing data to COMPLIANCE_CHECKER_AGENT...")
        
# # # #         return {"success": True, "data": self.agent_system.salary_data}

# # # # class ComplianceCheckerAgent(PayrollAgent):
# # # #     def __init__(self, agent_system):
# # # #         super().__init__("COMPLIANCE_CHECKER_AGENT", agent_system)
    
# # # #     def process(self):
# # # #         self.log_agent_communication("Received salary data, validating compliance...")
        
# # # #         if not self.agent_system.salary_data:
# # # #             self.log_agent_communication("FAILED - No salary data available")
# # # #             return {"success": False, "error": "No salary data available"}
        
# # # #         prompt = """Validate salary calculations against Indian labor law compliance.
# # # #         Check PF limits, ESI eligibility, Professional tax rates.
        
# # # #         Return ONLY JSON:
# # # #         {
# # # #           "compliance_status": "COMPLIANT" or "NON_COMPLIANT",
# # # #           "issues": ["list of issues if any"],
# # # #           "validated_deductions": {
# # # #             "pf": number,
# # # #             "esi": number,
# # # #             "professional_tax": number,
# # # #             "tds": number
# # # #           }
# # # #         }"""
        
# # # #         response = self.agent_system.llm_call(prompt, json.dumps(self.agent_system.salary_data))
# # # #         self.agent_system.compliance_data = self.agent_system.safe_json_parse(response)
        
# # # #         status = self.agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
# # # #         issues = self.agent_system.compliance_data.get('issues', [])
        
# # # #         if status == 'COMPLIANT':
# # # #             self.log_agent_communication("SUCCESS - All calculations are compliant with Indian labor laws")
# # # #         else:
# # # #             self.log_agent_communication(f"WARNING - Compliance issues found: {issues}")
        
# # # #         self.log_agent_communication("Passing data to ANOMALY_DETECTOR_AGENT...")
# # # #         return {"success": True, "data": self.agent_system.compliance_data}

# # # # class AnomalyDetectorAgent(PayrollAgent):
# # # #     def __init__(self, agent_system):
# # # #         super().__init__("ANOMALY_DETECTOR_AGENT", agent_system)
    
# # # #     def process(self):
# # # #         self.log_agent_communication("Received compliance data, scanning for anomalies...")
        
# # # #         prompt = """Detect payroll anomalies in the calculations.
# # # #         Check for calculation errors, unusual amounts, missing deductions.
        
# # # #         Return ONLY JSON:
# # # #         {
# # # #           "has_anomalies": boolean,
# # # #           "anomalies": [
# # # #             {
# # # #               "type": "string",
# # # #               "description": "string", 
# # # #               "severity": "LOW|MEDIUM|HIGH"
# # # #             }
# # # #           ],
# # # #           "overall_status": "NORMAL" or "REVIEW_REQUIRED"
# # # #         }"""
        
# # # #         combined_data = {
# # # #             "contract": self.agent_system.contract_data,
# # # #             "salary": self.agent_system.salary_data,
# # # #             "compliance": self.agent_system.compliance_data
# # # #         }
        
# # # #         response = self.agent_system.llm_call(prompt, json.dumps(combined_data))
# # # #         self.agent_system.anomalies = self.agent_system.safe_json_parse(response)
        
# # # #         has_anomalies = self.agent_system.anomalies.get('has_anomalies', False)
# # # #         anomaly_count = len(self.agent_system.anomalies.get('anomalies', []))
        
# # # #         if has_anomalies:
# # # #             self.log_agent_communication(f"WARNING - {anomaly_count} anomalies detected")
# # # #             for anomaly in self.agent_system.anomalies.get('anomalies', []):
# # # #                 severity = anomaly.get('severity', 'LOW')
# # # #                 description = anomaly.get('description', 'Unknown')
# # # #                 self.log_agent_communication(f"  - {severity}: {description}")
# # # #         else:
# # # #             self.log_agent_communication("SUCCESS - No anomalies found")
        
# # # #         self.log_agent_communication("Processing completed successfully!")
# # # #         return {"success": True, "data": self.agent_system.anomalies}

# # # # class PayrollAgentOrchestrator:
# # # #     def __init__(self, agent_system):
# # # #         self.agent_system = agent_system
# # # #         self.contract_reader = ContractReaderAgent(agent_system)
# # # #         self.salary_calculator = SalaryCalculatorAgent(agent_system)
# # # #         self.compliance_checker = ComplianceCheckerAgent(agent_system)
# # # #         self.anomaly_detector = AnomalyDetectorAgent(agent_system)
    
# # # #     def process_contract(self, file_path):
# # # #         """Orchestrate the entire payroll processing pipeline"""
# # # #         logger.info("MAIN_COORDINATOR: Starting multi-agent payroll processing pipeline...")
        
# # # #         try:
# # # #             # Step 1: Contract Reader Agent
# # # #             result1 = self.contract_reader.process(file_path)
# # # #             if not result1["success"]:
# # # #                 return {"success": False, "error": result1["error"]}
            
# # # #             # Step 2: Salary Calculator Agent
# # # #             result2 = self.salary_calculator.process()
# # # #             if not result2["success"]:
# # # #                 return {"success": False, "error": result2["error"]}
            
# # # #             # Step 3: Compliance Checker Agent
# # # #             result3 = self.compliance_checker.process()
# # # #             if not result3["success"]:
# # # #                 return {"success": False, "error": result3["error"]}
            
# # # #             # Step 4: Anomaly Detector Agent
# # # #             result4 = self.anomaly_detector.process()
# # # #             if not result4["success"]:
# # # #                 return {"success": False, "error": result4["error"]}
            
# # # #             logger.info("MAIN_COORDINATOR: All agents completed successfully!")
# # # #             return {"success": True, "message": "Processing completed successfully"}
            
# # # #         except Exception as e:
# # # #             logger.error(f"MAIN_COORDINATOR: Processing failed - {str(e)}")
# # # #             return {"success": False, "error": str(e)}

# # # # # Main Streamlit App
# # # # def main():
# # # #     st.set_page_config(
# # # #         page_title="HR Payroll Agent System",
# # # #         page_icon="💼", 
# # # #         layout="wide"
# # # #     )
    
# # # #     st.title("💼 HR Payroll Agent System")
# # # #     st.markdown("**Multi-Agent Payroll Processing with Terminal Logging**")
    
# # # #     # Initialize agent system
# # # #     if 'agent_system' not in st.session_state:
# # # #         st.session_state.agent_system = PayrollAgentSystem()
# # # #         st.session_state.orchestrator = PayrollAgentOrchestrator(st.session_state.agent_system)
# # # #         st.session_state.processing_complete = False
    
# # # #     # File upload
# # # #     col1, col2 = st.columns([3, 1])
    
# # # #     with col1:
# # # #         contract_file = st.file_uploader(
# # # #             "Upload Employee Contract PDF",
# # # #             type=["pdf"],
# # # #             help="Upload employment contract for payroll processing"
# # # #         )
    
# # # #     with col2:
# # # #         if st.button("🚀 Process with Agents", type="primary", disabled=not contract_file):
# # # #             if contract_file:
# # # #                 st.session_state.processing_complete = False
                
# # # #                 with st.spinner("🤖 Agents are processing..."):
# # # #                     try:
# # # #                         # Save uploaded file
# # # #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # # #                             tmp.write(contract_file.read())
# # # #                             contract_path = tmp.name
                        
# # # #                         # Process through agent orchestrator
# # # #                         result = st.session_state.orchestrator.process_contract(contract_path)
                        
# # # #                         if result["success"]:
# # # #                             st.session_state.processing_complete = True
# # # #                             st.success("✅ Processing completed! Check terminal for detailed agent communication logs.")
# # # #                         else:
# # # #                             st.error(f"❌ Processing failed: {result['error']}")
                        
# # # #                         # Clean up temp file
# # # #                         os.unlink(contract_path)
                        
# # # #                     except Exception as e:
# # # #                         st.error(f"❌ Unexpected error: {str(e)}")
    
# # # #     # Display results
# # # #     if st.session_state.processing_complete:
# # # #         agent_system = st.session_state.agent_system
        
# # # #         st.header("📊 Processing Results")
        
# # # #         # Employee Info
# # # #         if agent_system.contract_data:
# # # #             st.subheader("👤 Employee Information") 
# # # #             col1, col2, col3 = st.columns(3)
# # # #             with col1:
# # # #                 st.metric("Name", agent_system.contract_data.get("employee_name", "N/A"))
# # # #             with col2:
# # # #                 st.metric("Department", agent_system.contract_data.get("department", "N/A"))
# # # #             with col3:
# # # #                 st.metric("Designation", agent_system.contract_data.get("designation", "N/A"))
        
# # # #         # Salary Breakdown
# # # #         if agent_system.salary_data:
# # # #             st.subheader("💰 Salary Breakdown")
# # # #             col1, col2, col3 = st.columns(3)
            
# # # #             gross = agent_system.salary_data.get('gross_salary', 0)
# # # #             net = agent_system.salary_data.get('net_salary', 0)
# # # #             total_deductions = sum(agent_system.salary_data.get('deductions', {}).values())
            
# # # #             with col1:
# # # #                 st.metric("Gross Salary", f"₹{gross:,.2f}")
# # # #             with col2:
# # # #                 st.metric("Total Deductions", f"₹{total_deductions:,.2f}")  
# # # #             with col3:
# # # #                 st.metric("Net Salary", f"₹{net:,.2f}")
            
# # # #             # Detailed breakdown
# # # #             with st.expander("View Detailed Breakdown"):
# # # #                 col1, col2 = st.columns(2)
                
# # # #                 with col1:
# # # #                     st.write("**Earnings:**")
# # # #                     if agent_system.contract_data and agent_system.contract_data.get("salary_structure"):
# # # #                         salary_struct = agent_system.contract_data["salary_structure"]
# # # #                         for component, amount in salary_struct.items():
# # # #                             if amount > 0:
# # # #                                 st.write(f"• {component.replace('_', ' ').title()}: ₹{amount:,.2f}")
                
# # # #                 with col2:
# # # #                     st.write("**Deductions:**")
# # # #                     deductions = agent_system.salary_data.get("deductions", {})
# # # #                     for deduction, amount in deductions.items():
# # # #                         if amount > 0:
# # # #                             st.write(f"• {deduction.replace('_', ' ').title()}: ₹{amount:,.2f}")
        
# # # #         # Compliance & Anomalies
# # # #         col1, col2 = st.columns(2)
        
# # # #         with col1:
# # # #             if agent_system.compliance_data:
# # # #                 st.subheader("⚖️ Compliance Status")
# # # #                 status = agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
# # # #                 if status == 'COMPLIANT':
# # # #                     st.success("✅ All calculations compliant")
# # # #                 else:
# # # #                     st.warning("⚠️ Compliance issues detected")
# # # #                     issues = agent_system.compliance_data.get('issues', [])
# # # #                     for issue in issues:
# # # #                         st.write(f"• {issue}")
        
# # # #         with col2:
# # # #             if agent_system.anomalies:
# # # #                 st.subheader("🔍 Anomaly Detection")
# # # #                 if agent_system.anomalies.get('has_anomalies'):
# # # #                     anomaly_count = len(agent_system.anomalies.get('anomalies', []))
# # # #                     st.warning(f"⚠️ {anomaly_count} issues found")
# # # #                     for anomaly in agent_system.anomalies.get('anomalies', []):
# # # #                         severity = anomaly.get('severity', 'LOW')
# # # #                         description = anomaly.get('description', 'Unknown')
# # # #                         st.write(f"• **{severity}**: {description}")
# # # #                 else:
# # # #                     st.success("✅ No anomalies detected")
    
# # # #     else:
# # # #         st.info("👆 Upload a contract PDF to start multi-agent processing")
# # # #         st.markdown("**💡 Real-time agent communication will appear in your terminal/console!**")
    
# # # #     # Footer
# # # #     st.markdown("---")
# # # #     st.markdown("*Multi-Agent Payroll System • Real-time Agent Logging*")

# # # # if __name__ == "__main__":
# # # #     main()











# # # # # # app.py
# # # # # import os
# # # # # import json
# # # # # import tempfile
# # # # # import streamlit as st
# # # # # from datetime import datetime
# # # # # from PyPDF2 import PdfReader
# # # # # from openai import OpenAI
# # # # # import logging
# # # # # import sys

# # # # # # Fix Unicode encoding for Windows console (Streamlit-safe)
# # # # # if sys.platform.startswith('win'):
# # # # #     try:
# # # # #         import codecs
# # # # #         if hasattr(sys.stdout, 'detach'):
# # # # #             sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
# # # # #             sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
# # # # #         else:
# # # # #             # For Streamlit environment, set console code page to UTF-8
# # # # #             os.system('chcp 65001 >nul 2>&1')
# # # # #     except:
# # # # #         # Fallback: just continue without encoding changes
# # # # #         pass

# # # # # # Configure logging with safer Unicode handling
# # # # # logging.basicConfig(
# # # # #     level=logging.INFO,
# # # # #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
# # # # #     handlers=[
# # # # #         logging.StreamHandler(),
# # # # #         logging.FileHandler('agent_communication.log', encoding='utf-8', errors='replace')
# # # # #     ]
# # # # # )
# # # # # logger = logging.getLogger(__name__)

# # # # # # Environment setup
# # # # # from dotenv import load_dotenv
# # # # # load_dotenv()
# # # # # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # # # # # Initialize OpenAI client with Gemini
# # # # # client = OpenAI(
# # # # #     api_key=GEMINI_API_KEY,
# # # # #     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# # # # # )

# # # # # class PayrollAgentSystem:
# # # # #     def __init__(self):
# # # # #         self.contract_data = {}
# # # # #         self.salary_data = {}
# # # # #         self.compliance_data = {}
# # # # #         self.anomalies = {}
        
# # # # #     def extract_pdf_text(self, file_path):
# # # # #         """Extract text from PDF file"""
# # # # #         try:
# # # # #             reader = PdfReader(file_path)
# # # # #             text = ""
# # # # #             for page in reader.pages:
# # # # #                 text += page.extract_text() or ""
# # # # #             return text.strip()
# # # # #         except Exception as e:
# # # # #             logger.error(f"PDF extraction failed: {e}")
# # # # #             return ""
    
# # # # #     def llm_call(self, prompt, content):
# # # # #         """Make LLM call with error handling"""
# # # # #         try:
# # # # #             response = client.chat.completions.create(
# # # # #                 model="gemini-2.0-flash-exp",
# # # # #                 messages=[
# # # # #                     {"role": "system", "content": prompt},
# # # # #                     {"role": "user", "content": content}
# # # # #                 ],
# # # # #                 temperature=0.1,
# # # # #                 max_tokens=2000
# # # # #             )
# # # # #             return response.choices[0].message.content.strip()
# # # # #         except Exception as e:
# # # # #             logger.error(f"LLM call failed: {e}")
# # # # #             return ""
    
# # # # #     def safe_json_parse(self, text):
# # # # #         """Safely parse JSON from LLM response"""
# # # # #         try:
# # # # #             # Clean up common JSON formatting issues
# # # # #             text = text.strip()
# # # # #             if text.startswith("```json"):
# # # # #                 text = text[7:]
# # # # #             if text.startswith("```"):
# # # # #                 text = text[3:]
# # # # #             if text.endswith("```"):
# # # # #                 text = text[:-3]
# # # # #             text = text.strip()
# # # # #             return json.loads(text)
# # # # #         except:
# # # # #             logger.error(f"JSON parsing failed for: {text[:100]}...")
# # # # #             return {}

# # # # # class PayrollAgent:
# # # # #     def __init__(self, name, agent_system):
# # # # #         self.name = name
# # # # #         self.agent_system = agent_system
    
# # # # #     def log_agent_communication(self, message):
# # # # #         """Log agent communication without emojis for Windows compatibility"""
# # # # #         logger.info(f"[{self.name}] {message}")

# # # # # class ContractReaderAgent(PayrollAgent):
# # # # #     def __init__(self, agent_system):
# # # # #         super().__init__("CONTRACT_READER_AGENT", agent_system)
    
# # # # #     def process(self, file_path):
# # # # #         self.log_agent_communication("Starting contract analysis...")
        
# # # # #         text = self.agent_system.extract_pdf_text(file_path)
# # # # #         if not text:
# # # # #             self.log_agent_communication("FAILED - Could not extract text from PDF")
# # # # #             return {"success": False, "error": "Failed to extract PDF text"}
        
# # # # #         prompt = """Extract employee salary details from this employment contract.
# # # # #         Return ONLY JSON with this structure:
# # # # #         {
# # # # #           "employee_name": "string",
# # # # #           "employee_id": "string or null", 
# # # # #           "department": "string or null",
# # # # #           "designation": "string or null",
# # # # #           "location": "string",
# # # # #           "salary_structure": {
# # # # #             "basic": number,
# # # # #             "hra": number,
# # # # #             "allowances": number,
# # # # #             "gross": number
# # # # #           }
# # # # #         }"""
        
# # # # #         response = self.agent_system.llm_call(prompt, f"Contract text: {text}")
# # # # #         self.agent_system.contract_data = self.agent_system.safe_json_parse(response)
        
# # # # #         employee_name = self.agent_system.contract_data.get('employee_name', 'Unknown')
# # # # #         gross_salary = self.agent_system.contract_data.get('salary_structure', {}).get('gross', 0)
        
# # # # #         self.log_agent_communication(f"SUCCESS - Extracted data for {employee_name}")
# # # # #         self.log_agent_communication(f"Gross salary identified as Rs.{gross_salary}")
# # # # #         self.log_agent_communication("Passing data to SALARY_CALCULATOR_AGENT...")
        
# # # # #         return {"success": True, "data": self.agent_system.contract_data}

# # # # # class SalaryCalculatorAgent(PayrollAgent):
# # # # #     def __init__(self, agent_system):
# # # # #         super().__init__("SALARY_CALCULATOR_AGENT", agent_system)
    
# # # # #     def process(self):
# # # # #         self.log_agent_communication("Received contract data, starting salary calculations...")
        
# # # # #         if not self.agent_system.contract_data:
# # # # #             self.log_agent_communication("FAILED - No contract data available")
# # # # #             return {"success": False, "error": "No contract data available"}
        
# # # # #         prompt = """Calculate monthly salary breakdown for Indian payroll.
# # # # #         Apply standard deductions:
# # # # #         - PF: 12% of basic (max Rs.1,800)
# # # # #         - ESI: 0.75% of gross (if gross <= Rs.21,000)
# # # # #         - Professional Tax: Rs.200/month (if salary > Rs.15,000)
# # # # #         - TDS: Estimate based on annual salary
        
# # # # #         Return ONLY JSON:
# # # # #         {
# # # # #           "gross_salary": number,
# # # # #           "deductions": {
# # # # #             "pf": number,
# # # # #             "esi": number,
# # # # #             "professional_tax": number,
# # # # #             "tds": number
# # # # #           },
# # # # #           "net_salary": number
# # # # #         }"""
        
# # # # #         response = self.agent_system.llm_call(prompt, json.dumps(self.agent_system.contract_data))
# # # # #         self.agent_system.salary_data = self.agent_system.safe_json_parse(response)
        
# # # # #         gross = self.agent_system.salary_data.get('gross_salary', 0)
# # # # #         net = self.agent_system.salary_data.get('net_salary', 0)
# # # # #         total_deductions = sum(self.agent_system.salary_data.get('deductions', {}).values())
        
# # # # #         self.log_agent_communication(f"SUCCESS - Calculated salary breakdown")
# # # # #         self.log_agent_communication(f"Gross: Rs.{gross:,.2f}, Net: Rs.{net:,.2f}, Deductions: Rs.{total_deductions:,.2f}")
# # # # #         self.log_agent_communication("Passing data to COMPLIANCE_CHECKER_AGENT...")
        
# # # # #         return {"success": True, "data": self.agent_system.salary_data}

# # # # # class ComplianceCheckerAgent(PayrollAgent):
# # # # #     def __init__(self, agent_system):
# # # # #         super().__init__("COMPLIANCE_CHECKER_AGENT", agent_system)
    
# # # # #     def process(self):
# # # # #         self.log_agent_communication("Received salary data, validating compliance...")
        
# # # # #         if not self.agent_system.salary_data:
# # # # #             self.log_agent_communication("FAILED - No salary data available")
# # # # #             return {"success": False, "error": "No salary data available"}
        
# # # # #         prompt = """Validate salary calculations against Indian labor law compliance.
# # # # #         Check PF limits, ESI eligibility, Professional tax rates.
        
# # # # #         Return ONLY JSON:
# # # # #         {
# # # # #           "compliance_status": "COMPLIANT" or "NON_COMPLIANT",
# # # # #           "issues": ["list of issues if any"],
# # # # #           "validated_deductions": {
# # # # #             "pf": number,
# # # # #             "esi": number,
# # # # #             "professional_tax": number,
# # # # #             "tds": number
# # # # #           }
# # # # #         }"""
        
# # # # #         response = self.agent_system.llm_call(prompt, json.dumps(self.agent_system.salary_data))
# # # # #         self.agent_system.compliance_data = self.agent_system.safe_json_parse(response)
        
# # # # #         status = self.agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
# # # # #         issues = self.agent_system.compliance_data.get('issues', [])
        
# # # # #         if status == 'COMPLIANT':
# # # # #             self.log_agent_communication("SUCCESS - All calculations are compliant with Indian labor laws")
# # # # #         else:
# # # # #             self.log_agent_communication(f"WARNING - Compliance issues found: {issues}")
        
# # # # #         self.log_agent_communication("Passing data to ANOMALY_DETECTOR_AGENT...")
# # # # #         return {"success": True, "data": self.agent_system.compliance_data}

# # # # # class AnomalyDetectorAgent(PayrollAgent):
# # # # #     def __init__(self, agent_system):
# # # # #         super().__init__("ANOMALY_DETECTOR_AGENT", agent_system)
    
# # # # #     def process(self):
# # # # #         self.log_agent_communication("Received compliance data, scanning for anomalies...")
        
# # # # #         prompt = """Detect payroll anomalies in the calculations.
# # # # #         Check for calculation errors, unusual amounts, missing deductions.
        
# # # # #         Return ONLY JSON:
# # # # #         {
# # # # #           "has_anomalies": boolean,
# # # # #           "anomalies": [
# # # # #             {
# # # # #               "type": "string",
# # # # #               "description": "string", 
# # # # #               "severity": "LOW|MEDIUM|HIGH"
# # # # #             }
# # # # #           ],
# # # # #           "overall_status": "NORMAL" or "REVIEW_REQUIRED"
# # # # #         }"""
        
# # # # #         combined_data = {
# # # # #             "contract": self.agent_system.contract_data,
# # # # #             "salary": self.agent_system.salary_data,
# # # # #             "compliance": self.agent_system.compliance_data
# # # # #         }
        
# # # # #         response = self.agent_system.llm_call(prompt, json.dumps(combined_data))
# # # # #         self.agent_system.anomalies = self.agent_system.safe_json_parse(response)
        
# # # # #         has_anomalies = self.agent_system.anomalies.get('has_anomalies', False)
# # # # #         anomaly_count = len(self.agent_system.anomalies.get('anomalies', []))
        
# # # # #         if has_anomalies:
# # # # #             self.log_agent_communication(f"WARNING - {anomaly_count} anomalies detected")
# # # # #             for anomaly in self.agent_system.anomalies.get('anomalies', []):
# # # # #                 severity = anomaly.get('severity', 'LOW')
# # # # #                 description = anomaly.get('description', 'Unknown')
# # # # #                 self.log_agent_communication(f"  - {severity}: {description}")
# # # # #         else:
# # # # #             self.log_agent_communication("SUCCESS - No anomalies found")
        
# # # # #         self.log_agent_communication("Processing completed successfully!")
# # # # #         return {"success": True, "data": self.agent_system.anomalies}

# # # # # class PayrollAgentOrchestrator:
# # # # #     def __init__(self, agent_system):
# # # # #         self.agent_system = agent_system
# # # # #         self.contract_reader = ContractReaderAgent(agent_system)
# # # # #         self.salary_calculator = SalaryCalculatorAgent(agent_system)
# # # # #         self.compliance_checker = ComplianceCheckerAgent(agent_system)
# # # # #         self.anomaly_detector = AnomalyDetectorAgent(agent_system)
    
# # # # #     def process_contract(self, file_path):
# # # # #         """Orchestrate the entire payroll processing pipeline"""
# # # # #         logger.info("MAIN_COORDINATOR: Starting multi-agent payroll processing pipeline...")
        
# # # # #         try:
# # # # #             # Step 1: Contract Reader Agent
# # # # #             result1 = self.contract_reader.process(file_path)
# # # # #             if not result1["success"]:
# # # # #                 return {"success": False, "error": result1["error"]}
            
# # # # #             # Step 2: Salary Calculator Agent
# # # # #             result2 = self.salary_calculator.process()
# # # # #             if not result2["success"]:
# # # # #                 return {"success": False, "error": result2["error"]}
            
# # # # #             # Step 3: Compliance Checker Agent
# # # # #             result3 = self.compliance_checker.process()
# # # # #             if not result3["success"]:
# # # # #                 return {"success": False, "error": result3["error"]}
            
# # # # #             # Step 4: Anomaly Detector Agent
# # # # #             result4 = self.anomaly_detector.process()
# # # # #             if not result4["success"]:
# # # # #                 return {"success": False, "error": result4["error"]}
            
# # # # #             logger.info("MAIN_COORDINATOR: All agents completed successfully!")
# # # # #             return {"success": True, "message": "Processing completed successfully"}
            
# # # # #         except Exception as e:
# # # # #             logger.error(f"MAIN_COORDINATOR: Processing failed - {str(e)}")
# # # # #             return {"success": False, "error": str(e)}

# # # # # # Main Streamlit App
# # # # # def main():
# # # # #     st.set_page_config(
# # # # #         page_title="HR Payroll Agent System",
# # # # #         page_icon="💼", 
# # # # #         layout="wide"
# # # # #     )
    
# # # # #     st.title("💼 HR Payroll Agent System")
# # # # #     st.markdown("**Multi-Agent Payroll Processing with Terminal Logging**")
    
# # # # #     # Initialize agent system
# # # # #     if 'agent_system' not in st.session_state:
# # # # #         st.session_state.agent_system = PayrollAgentSystem()
# # # # #         st.session_state.orchestrator = PayrollAgentOrchestrator(st.session_state.agent_system)
# # # # #         st.session_state.processing_complete = False
    
# # # # #     # File upload
# # # # #     col1, col2 = st.columns([3, 1])
    
# # # # #     with col1:
# # # # #         contract_file = st.file_uploader(
# # # # #             "Upload Employee Contract PDF",
# # # # #             type=["pdf"],
# # # # #             help="Upload employment contract for payroll processing"
# # # # #         )
    
# # # # #     with col2:
# # # # #         if st.button("🚀 Process with Agents", type="primary", disabled=not contract_file):
# # # # #             if contract_file:
# # # # #                 st.session_state.processing_complete = False
                
# # # # #                 with st.spinner("🤖 Agents are processing..."):
# # # # #                     try:
# # # # #                         # Save uploaded file
# # # # #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # # # #                             tmp.write(contract_file.read())
# # # # #                             contract_path = tmp.name
                        
# # # # #                         # Process through agent orchestrator
# # # # #                         result = st.session_state.orchestrator.process_contract(contract_path)
                        
# # # # #                         if result["success"]:
# # # # #                             st.session_state.processing_complete = True
# # # # #                             st.success("✅ Processing completed! Check terminal for detailed agent communication logs.")
# # # # #                         else:
# # # # #                             st.error(f"❌ Processing failed: {result['error']}")
                        
# # # # #                         # Clean up temp file
# # # # #                         os.unlink(contract_path)
                        
# # # # #                     except Exception as e:
# # # # #                         st.error(f"❌ Unexpected error: {str(e)}")
    
# # # # #     # Display results
# # # # #     if st.session_state.processing_complete:
# # # # #         agent_system = st.session_state.agent_system
        
# # # # #         st.header("📊 Processing Results")
        
# # # # #         # Employee Info
# # # # #         if agent_system.contract_data:
# # # # #             st.subheader("👤 Employee Information") 
# # # # #             col1, col2, col3 = st.columns(3)
# # # # #             with col1:
# # # # #                 st.metric("Name", agent_system.contract_data.get("employee_name", "N/A"))
# # # # #             with col2:
# # # # #                 st.metric("Department", agent_system.contract_data.get("department", "N/A"))
# # # # #             with col3:
# # # # #                 st.metric("Designation", agent_system.contract_data.get("designation", "N/A"))
        
# # # # #         # Salary Breakdown
# # # # #         if agent_system.salary_data:
# # # # #             st.subheader("💰 Salary Breakdown")
# # # # #             col1, col2, col3 = st.columns(3)
            
# # # # #             gross = agent_system.salary_data.get('gross_salary', 0)
# # # # #             net = agent_system.salary_data.get('net_salary', 0)
# # # # #             total_deductions = sum(agent_system.salary_data.get('deductions', {}).values())
            
# # # # #             with col1:
# # # # #                 st.metric("Gross Salary", f"₹{gross:,.2f}")
# # # # #             with col2:
# # # # #                 st.metric("Total Deductions", f"₹{total_deductions:,.2f}")  
# # # # #             with col3:
# # # # #                 st.metric("Net Salary", f"₹{net:,.2f}")
            
# # # # #             # Detailed breakdown
# # # # #             with st.expander("View Detailed Breakdown"):
# # # # #                 col1, col2 = st.columns(2)
                
# # # # #                 with col1:
# # # # #                     st.write("**Earnings:**")
# # # # #                     if agent_system.contract_data and agent_system.contract_data.get("salary_structure"):
# # # # #                         salary_struct = agent_system.contract_data["salary_structure"]
# # # # #                         for component, amount in salary_struct.items():
# # # # #                             if amount > 0:
# # # # #                                 st.write(f"• {component.replace('_', ' ').title()}: ₹{amount:,.2f}")
                
# # # # #                 with col2:
# # # # #                     st.write("**Deductions:**")
# # # # #                     deductions = agent_system.salary_data.get("deductions", {})
# # # # #                     for deduction, amount in deductions.items():
# # # # #                         if amount > 0:
# # # # #                             st.write(f"• {deduction.replace('_', ' ').title()}: ₹{amount:,.2f}")
        
# # # # #         # Compliance & Anomalies
# # # # #         col1, col2 = st.columns(2)
        
# # # # #         with col1:
# # # # #             if agent_system.compliance_data:
# # # # #                 st.subheader("⚖️ Compliance Status")
# # # # #                 status = agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
# # # # #                 if status == 'COMPLIANT':
# # # # #                     st.success("✅ All calculations compliant")
# # # # #                 else:
# # # # #                     st.warning("⚠️ Compliance issues detected")
# # # # #                     issues = agent_system.compliance_data.get('issues', [])
# # # # #                     for issue in issues:
# # # # #                         st.write(f"• {issue}")
        
# # # # #         with col2:
# # # # #             if agent_system.anomalies:
# # # # #                 st.subheader("🔍 Anomaly Detection")
# # # # #                 if agent_system.anomalies.get('has_anomalies'):
# # # # #                     anomaly_count = len(agent_system.anomalies.get('anomalies', []))
# # # # #                     st.warning(f"⚠️ {anomaly_count} issues found")
# # # # #                     for anomaly in agent_system.anomalies.get('anomalies', []):
# # # # #                         severity = anomaly.get('severity', 'LOW')
# # # # #                         description = anomaly.get('description', 'Unknown')
# # # # #                         st.write(f"• **{severity}**: {description}")
# # # # #                 else:
# # # # #                     st.success("✅ No anomalies detected")
    
# # # # #     else:
# # # # #         st.info("👆 Upload a contract PDF to start multi-agent processing")
# # # # #         st.markdown("**💡 Real-time agent communication will appear in your terminal/console!**")
    
# # # # #     # Footer
# # # # #     st.markdown("---")
# # # # #     st.markdown("*Multi-Agent Payroll System • Real-time Agent Logging*")

# # # # # if __name__ == "__main__":
# # # # #     main()
    

