# app.py
import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType
import tempfile
import os
import nest_asyncio
import asyncio

# Set Google API key
os.environ["GOOGLE_API_KEY"] = "AIzaSyBiMIZleZzmhkJBuld1s1ATDUK7JVELV_0"

st.set_page_config(page_title="PDF Agent", layout="wide")
st.title("📄 PDF Agentic QA")

# Step 1: Upload PDF
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    st.success("✅ PDF uploaded successfully!")

    # Step 2: Load PDF
    loader = PyPDFLoader(tmp_path)
    documents = loader.load()

    # Step 3: Split text
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    docs = text_splitter.split_documents(documents)

    # Step 4: Create vectorstore
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore = Chroma.from_documents(docs, embeddings)

    nest_asyncio.apply()  # allow nested loops in Streamlit

    # Ensure an event loop exists for this thread
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


    retriever = vectorstore.as_retriever()

    # Step 5: Create retrieval tool
    def retrieve_info(query):
        results = retriever.get_relevant_documents(query)
        return "\n\n".join([doc.page_content for doc in results])

    retrieval_tool = Tool(
        name="PDF Retriever",
        func=retrieve_info,
        description="Use this to find information inside the uploaded PDF."
    )

    # Step 6: Initialize the real agent
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
    agent = initialize_agent(
        tools=[retrieval_tool],
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )

    # Step 7: User query
    query = st.text_input("Ask me something about the PDF:")
    if query:
        with st.spinner("Thinking..."):
            answer = agent.run(query)
        st.markdown(f"**Answer:** {answer}")


# import os
# import json
# import tempfile
# import streamlit as st
# from datetime import datetime
# from typing import TypedDict, Annotated, List, Dict, Any, Optional
# from PyPDF2 import PdfReader
# from openai import OpenAI
# import logging
# from dotenv import load_dotenv

# # LangGraph imports (left as-is in case you want the agentic ReAct flow)
# from langgraph.prebuilt import create_react_agent
# from langgraph.checkpoint.memory import MemorySaver
# from langchain_core.tools import tool
# from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage, AIMessage
# from langchain_openai import ChatOpenAI

# # ---------------------------------------------------------
# # Logging & env
# # ---------------------------------------------------------
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
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
# if not GEMINI_API_KEY:
#     logger.warning("No GEMINI_API_KEY or OPENAI_API_KEY found in environment. Set GEMINI_API_KEY in .env")

# # ---------------------------------------------------------
# # OpenAI / Gemini client initialization
# # (keep your base_url if using google's OpenAI-compat endpoint)
# # ---------------------------------------------------------
# client = OpenAI(
#     api_key=GEMINI_API_KEY,
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# )

# llm = ChatOpenAI(
#     api_key=GEMINI_API_KEY,
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
#     model="gemini-2.0-flash-exp",
#     temperature=0.1
# )

# # ---------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------
# def _clean_codeblock(text: str) -> str:
#     """Remove triple-backtick fences and optional language markers."""
#     if text.startswith("```"):
#         # remove leading fence + possible language
#         parts = text.split("\n")
#         # remove first line fence
#         parts = parts[1:]
#         # if last line is fence, drop it
#         if parts and parts[-1].strip().endswith("```"):
#             parts = parts[:-1]
#         return "\n".join(parts).strip()
#     return text.strip()

# def _safe_load_json(s: str) -> Optional[dict]:
#     s = s.strip()
#     s = _clean_codeblock(s)
#     try:
#         return json.loads(s)
#     except Exception as e:
#         # Try some minor fixes (single quotes -> double)
#         try:
#             return json.loads(s.replace("'", '"'))
#         except Exception:
#             logger.error("Failed to parse JSON: %s", e)
#             return None

# # ---------------------------------------------------------
# # Tool: extract PDF text
# # ---------------------------------------------------------
# @tool
# def extract_pdf_text_tool(file_path: str) -> str:
#     """Extract text content from a PDF file for contract analysis."""
#     try:
#         reader = PdfReader(file_path)
#         text = ""
#         for page in reader.pages:
#             page_text = page.extract_text()
#             if page_text:
#                 text += page_text + "\n"
#         logger.info(f"Successfully extracted {len(text)} characters from PDF")
#         return text.strip()
#     except Exception as e:
#         logger.error(f"PDF extraction failed: {e}")
#         return f"Error: {str(e)}"

# # ---------------------------------------------------------
# # Tool: parse contract data (LLM)
# # ---------------------------------------------------------
# @tool
# def parse_contract_data_tool(contract_text: str) -> str:
#     """
#     Use LLM to extract structured contract fields.
#     Return a JSON string matching the expected schema.
#     """
#     try:
#         prompt = """Extract employee salary details from this employment contract.
# Return ONLY a valid JSON object with this exact structure (fields may be null if not present):
# {
#   "employee_name": "string or null",
#   "employee_id": "string or null", 
#   "department": "string or null",
#   "designation": "string or null",
#   "location": "string or null",
#   "salary_structure": {
#     "basic": number or null,
#     "hra": number or null,
#     "allowances": number or null,
#     "gross": number or null
#   }
# }
# If a numeric field is present as an annual amount, convert it to monthly (divide by 12) and document that in a 'notes' field inside the top-level object.
# Respond with JSON only (no explanation)."""
#         response = client.chat.completions.create(
#             model="gemini-2.0-flash-exp",
#             messages=[
#                 {"role": "system", "content": prompt},
#                 {"role": "user", "content": f"Contract text: {contract_text[:15000]}"}  # cap length
#             ],
#             temperature=0.0,
#             max_tokens=1500
#         )
#         result = response.choices[0].message.content.strip()
#         result = _clean_codeblock(result)

#         logger.info(f"LLM returned for ========parse_contract_data_tool=========: {result}")

#         # validate JSON
#         parsed = _safe_load_json(result)
#         if parsed is None:
#             logger.error("parse_contract_data_tool: LLM output not valid JSON")
#             return json.dumps({"error": "LLM output not valid JSON", "raw": result})
#         logger.info("Successfully parsed contract data")
#         return json.dumps(parsed)
#     except Exception as e:
#         logger.error(f"Contract parsing failed: {e}")
#         return json.dumps({"error": str(e)})

# # ---------------------------------------------------------
# # Deterministic salary calculation (local) - more reliable
# # ---------------------------------------------------------
# def _as_monthly(value: Optional[float], assume_annual: bool = False) -> Optional[float]:
#     """If value is None, return None. If assume_annual True, divide by 12."""
#     if value is None:
#         return None
#     try:
#         v = float(value)
#         return v / 12.0 if assume_annual else v
#     except:
#         return None

# @tool
# def calculate_salary_breakdown_tool(contract_data: str) -> str:
#     """
#     Deterministic calculator for Indian payroll monthly values.
#     Expects contract_data to be a JSON string matching parse output.
#     """
#     try:
#         parsed = _safe_load_json(contract_data)
#         if parsed is None:
#             return json.dumps({"error": "Invalid contract_data JSON"})

#         # salary_structure may be missing or partial
#         ss = parsed.get("salary_structure", {}) if isinstance(parsed, dict) else {}
#         # prefer provided gross, otherwise sum components
#         basic = ss.get("basic")
#         hra = ss.get("hra")
#         allowances = ss.get("allowances")
#         gross = ss.get("gross")

#         # Some contracts provide annual amounts; user prompt/LLM may have converted that.
#         # Assume the values are monthly if reasonable; if any value > 200000 treat as annual and divide by 12.
#         def to_monthly_if_needed(x):
#             if x is None:
#                 return None
#             try:
#                 v = float(x)
#                 if v > 200000:  # heuristic: >2 lakh likely annual
#                     return v / 12.0
#                 return v
#             except:
#                 return None

#         basic_m = to_monthly_if_needed(basic)
#         hra_m = to_monthly_if_needed(hra)
#         allowances_m = to_monthly_if_needed(allowances)
#         gross_m = to_monthly_if_needed(gross)

#         # If gross missing but components present, compute sum
#         if gross_m is None and any(v is not None for v in (basic_m, hra_m, allowances_m)):
#             gross_m = sum(v or 0.0 for v in (basic_m, hra_m, allowances_m))

#         if gross_m is None:
#             return json.dumps({"error": "Insufficient salary data to compute gross salary"})

#         # Deductions
#         # PF: 12% of basic (cap per month 1800)
#         pf = 0.0
#         if basic_m is not None:
#             pf_calc = 0.12 * basic_m
#             pf = min(pf_calc, 1800.0)
#         else:
#             # if basic missing, try assume 40% of gross as basic (common heuristic) then compute PF
#             estimated_basic = 0.4 * gross_m
#             pf = min(0.12 * estimated_basic, 1800.0)

#         # ESI: 0.75% of gross if gross <= 21,000
#         esi = 0.0
#         if gross_m <= 21000:
#             esi = 0.0075 * gross_m

#         # Professional Tax: Rs.200/month if salary > 15,000 (simple rule; actual rates vary by state)
#         professional_tax = 200.0 if gross_m > 15000 else 0.0

#         # TDS: Simple estimate — compute annual gross and apply a conservative 10% on taxable portion above 250,000.
#         annual_gross = gross_m * 12.0
#         taxable = max(0.0, annual_gross - 250000.0)
#         tds_annual_est = taxable * 0.10  # simplified slab
#         tds = tds_annual_est / 12.0

#         deductions = {
#             "pf": round(pf, 2),
#             "esi": round(esi, 2),
#             "professional_tax": round(professional_tax, 2),
#             "tds": round(tds, 2)
#         }

#         total_deductions = sum(deductions.values())
#         net_salary = round(max(0.0, gross_m - total_deductions), 2)

#         result = {
#             "gross_salary": round(gross_m, 2),
#             "deductions": deductions,
#             "net_salary": net_salary,
#             "notes": "Estimates: PF cap=₹1800, ESI applicable if gross<=21000, professional tax simplified, TDS a rough estimate."
#         }
#         logger.info("Successfully calculated salary breakdown")
#         return json.dumps(result)
#     except Exception as e:
#         logger.error(f"Salary calculation failed: {e}")
#         return json.dumps({"error": str(e)})

# # ---------------------------------------------------------
# # Deterministic compliance validation (local)
# # ---------------------------------------------------------
# @tool
# def validate_compliance_tool(salary_data: str) -> str:
#     """Check PF limits, ESI eligibility, professional tax applicability, and TDS reasonableness."""
#     try:
#         sd = _safe_load_json(salary_data)
#         if sd is None:
#             return json.dumps({"error": "Invalid salary_data JSON"})

#         gross = sd.get("gross_salary", 0) or 0
#         deductions = sd.get("deductions", {})
#         issues = []
#         recs = []

#         # PF check: PF <= 1800
#         pf = deductions.get("pf", 0)
#         if pf > 1800.0 + 1e-6:
#             issues.append("PF exceeds statutory monthly cap of ₹1800.")
#             recs.append("Reduce PF to statutory cap calculation or verify basic salary amount.")

#         # ESI: check eligibility
#         esi = deductions.get("esi", 0)
#         if gross > 21000 and esi > 0.0:
#             issues.append("ESI deducted even though gross > ₹21,000; ESI shouldn't apply.")
#             recs.append("Remove ESI for this employee or verify gross salary.")

#         if gross <= 21000 and esi == 0.0:
#             # maybe ESI missing (but some employers may not enroll)
#             recs.append("Verify whether employee is enrolled for ESI if gross <= ₹21,000.")

#         # Professional tax: check simple rule used
#         prof_tax = deductions.get("professional_tax", 0)
#         if gross > 15000 and prof_tax < 200.0 - 1e-6:
#             issues.append("Professional tax appears too low (expected ≈ ₹200 for gross > 15,000 in this simplified check).")
#             recs.append("Verify state professional tax rules; rates differ by state.")

#         # TDS: check crude reasonableness: if monthly TDS > 0.2 * net salary -> suspicious
#         tds = deductions.get("tds", 0)
#         net = sd.get("net_salary", 0) or 0
#         if net > 0 and tds > 0.2 * net:
#             issues.append("TDS is unusually high compared to net salary; re-check tax estimates.")
#             recs.append("Recompute TDS using exact tax slabs and exemptions for the employee (use Form 16-like computation).")

#         compliance = "COMPLIANT" if len(issues) == 0 else "NON_COMPLIANT"

#         validated = {
#             "pf": round(pf, 2),
#             "esi": round(esi, 2),
#             "professional_tax": round(prof_tax, 2),
#             "tds": round(tds, 2)
#         }

#         result = {
#             "compliance_status": compliance,
#             "issues": issues,
#             "validated_deductions": validated,
#             "recommendations": recs
#         }
#         logger.info("Compliance validation done: %s", compliance)
#         return json.dumps(result)
#     except Exception as e:
#         logger.error(f"Compliance validation failed: {e}")
#         return json.dumps({"error": str(e)})

# # ---------------------------------------------------------
# # Deterministic anomaly detection (local)
# # ---------------------------------------------------------
# @tool
# def detect_anomalies_tool(combined_data: str) -> str:
#     """
#     Check for negative numbers, mismatches, missing deductions, and big differences between computed vs provided gross.
#     combined_data is expected to be a JSON string with keys: contract, salary, compliance
#     """
#     try:
#         cd = _safe_load_json(combined_data)
#         if cd is None:
#             return json.dumps({"error": "Invalid combined_data JSON"})

#         contract = cd.get("contract", {})
#         salary = cd.get("salary", {})
#         compliance = cd.get("compliance", {})

#         anomalies = []
#         overall_status = "NORMAL"
#         confidence = 0.9

#         gross = salary.get("gross_salary", 0) or 0
#         deductions = salary.get("deductions", {})
#         # Check negative or zero gross
#         if gross <= 0:
#             anomalies.append({
#                 "type": "calculation_error",
#                 "description": "Gross salary is zero or negative.",
#                 "severity": "HIGH",
#                 "affected_field": "gross_salary"
#             })
#             overall_status = "CRITICAL"

#         # Check deduction sums
#         total_deds = sum(deductions.values())
#         if total_deds < 0:
#             anomalies.append({
#                 "type": "calculation_error",
#                 "description": "Total deductions negative.",
#                 "severity": "HIGH",
#                 "affected_field": "deductions"
#             })
#             overall_status = "CRITICAL"

#         # Check mismatch between gross and provided components if any
#         ss = contract.get("salary_structure", {}) or {}
#         comps_sum = 0
#         present_components = False
#         for k in ("basic", "hra", "allowances"):
#             v = ss.get(k)
#             if v is not None:
#                 present_components = True
#                 try:
#                     numeric = float(v)
#                     # If contract gave annual amounts, this might be much larger; we attempt to normalize:
#                     if numeric > 200000:
#                         numeric = numeric / 12.0
#                     comps_sum += numeric
#                 except:
#                     pass

#         if present_components and comps_sum > 0:
#             diff_pct = abs(comps_sum - gross) / max(1.0, gross)
#             if diff_pct > 0.05:  # >5% mismatch
#                 anomalies.append({
#                     "type": "data_inconsistency",
#                     "description": f"Sum of components (basic+hra+allowances = {comps_sum:.2f}) differs from gross ({gross:.2f}) by {diff_pct*100:.2f}%.",
#                     "severity": "MEDIUM" if diff_pct <= 0.2 else "HIGH",
#                     "affected_field": "gross vs components"
#                 })
#                 overall_status = "REVIEW_REQUIRED"

#         # Add compliance issues as anomalies if NON_COMPLIANT
#         if compliance.get("compliance_status") == "NON_COMPLIANT":
#             anomalies.append({
#                 "type": "data_inconsistency",
#                 "description": "Compliance validation flagged non-compliance: " + "; ".join(compliance.get("issues", [])),
#                 "severity": "MEDIUM",
#                 "affected_field": "compliance"
#             })
#             if overall_status != "CRITICAL":
#                 overall_status = "REVIEW_REQUIRED"

#         result = {
#             "has_anomalies": len(anomalies) > 0,
#             "anomalies": anomalies,
#             "overall_status": overall_status,
#             "confidence_score": round(confidence, 2)
#         }
#         logger.info("Anomaly detection completed. Found %d anomalies", len(anomalies))
#         return json.dumps(result)
#     except Exception as e:
#         logger.error(f"Anomaly detection failed: {e}")
#         return json.dumps({"error": str(e)})

# # ---------------------------------------------------------
# # Tools list (same as before)
# # ---------------------------------------------------------
# tools = [
#     extract_pdf_text_tool,
#     parse_contract_data_tool,
#     calculate_salary_breakdown_tool,
#     validate_compliance_tool,
#     detect_anomalies_tool
# ]

# # ---------------------------------------------------------
# # System prompt (kept for LangGraph agent)
# # ---------------------------------------------------------
# system_prompt = SystemMessage(content="""You are a payroll agent that uses tools for each step:
# 1) extract_pdf_text_tool
# 2) parse_contract_data_tool
# 3) calculate_salary_breakdown_tool
# 4) validate_compliance_tool
# 5) detect_anomalies_tool

# Follow that sequence. Return a single JSON output at the end with keys:
# {
#   "success": boolean,
#   "contract_data": {},
#   "salary_data": {},
#   "compliance_data": {},
#   "anomalies_data": {},
#   "errors": []
# }
# """)

# # ---------------------------------------------------------
# # Deterministic pipeline class (recommended to call from Streamlit)
# # ---------------------------------------------------------
# class PayrollAgenticAI:
#     """Pure Agentic AI container. Provide a deterministic pipeline runner and keep agentic graph for optional use."""
#     def __init__(self):
#         memory = MemorySaver()
#         try:
#             self.graph = create_react_agent(
#                 llm,
#                 tools,
#                 state_modifier=system_prompt,
#                 checkpointer=memory
#             )
#         except Exception as e:
#             logger.warning("Failed to create ReAct agent (LangGraph) — continuing with deterministic pipeline. Error: %s", e)
#             self.graph = None
#         self.thread_id = "payroll_thread_1"

#     def process_contract_pipeline(self, contract_path: str) -> Dict[str, Any]:
#         """
#         Deterministic sequential pipeline calling the tools directly.
#         This is recommended for predictable results (what Streamlit should call).
#         """
#         errors = []
#         output = {
#             "success": False,
#             "contract_data": None,
#             "salary_data": None,
#             "compliance_data": None,
#             "anomalies_data": None,
#             "errors": []
#         }
#         try:
#             # 1) extract text
#             text = extract_pdf_text_tool(contract_path)
#             if text.startswith("Error:") or (isinstance(text, str) and text.strip() == ""):
#                 errors.append(f"extract_pdf_text_tool failed: {text}")
#                 output["errors"] = errors
#                 return output
#             # 2) parse contract via LLM tool (returns JSON string or error JSON)
#             parsed_json_string = parse_contract_data_tool(text)
#             parsed = _safe_load_json(parsed_json_string)
#             if parsed is None or parsed.get("error"):
#                 errors.append(f"parse_contract_data_tool failed or invalid JSON: {parsed_json_string}")
#                 output["errors"] = errors
#                 output["contract_data"] = parsed_json_string
#                 return output
#             output["contract_data"] = parsed

#             # 3) calculate salary deterministically
#             salary_json_str = calculate_salary_breakdown_tool(json.dumps(parsed))
#             salary = _safe_load_json(salary_json_str)
#             if salary is None or salary.get("error"):
#                 errors.append(f"calculate_salary_breakdown_tool failed: {salary_json_str}")
#                 output["errors"] = errors
#                 output["salary_data"] = salary_json_str
#                 return output
#             output["salary_data"] = salary

#             # 4) compliance
#             compliance_str = validate_compliance_tool(json.dumps(salary))
#             compliance = _safe_load_json(compliance_str)
#             if compliance is None or compliance.get("error"):
#                 errors.append(f"validate_compliance_tool failed: {compliance_str}")
#                 output["errors"] = errors
#                 output["compliance_data"] = compliance_str
#                 return output
#             output["compliance_data"] = compliance

#             # 5) anomalies
#             combined = json.dumps({
#                 "contract": parsed,
#                 "salary": salary,
#                 "compliance": compliance
#             })
#             anomalies_str = detect_anomalies_tool(combined)
#             anomalies = _safe_load_json(anomalies_str)
#             if anomalies is None or anomalies.get("error"):
#                 errors.append(f"detect_anomalies_tool failed: {anomalies_str}")
#                 output["errors"] = errors
#                 output["anomalies_data"] = anomalies_str
#                 return output
#             output["anomalies_data"] = anomalies

#             output["success"] = len(errors) == 0
#             output["errors"] = errors
#             return output

#         except Exception as e:
#             logger.exception("Workflow execution failed")
#             output["errors"].append(str(e))
#             return output

#     def process_contract_with_agent(self, contract_path: str) -> Dict[str, Any]:
#         """
#         Optional: invoke the LangGraph agentic ReAct flow. Not recommended as the primary
#         method for deterministic payroll math. Kept for experiments only.
#         """
#         if not self.graph:
#             return {"success": False, "errors": ["Agent not initialized"], "messages": []}
#         try:
#             config = {"configurable": {"thread_id": self.thread_id}}
#             input_message = HumanMessage(content=f"Process the employment contract at: {contract_path}")
#             final_state = self.graph.invoke({"messages": [input_message]}, config)
#             messages = final_state.get("messages", [])
#             last_message = messages[-1] if messages else None
#             # Expect last_message.content to be the JSON result
#             if isinstance(last_message, AIMessage):
#                 try:
#                     result = json.loads(last_message.content)
#                     result["messages"] = [msg.content for msg in messages if isinstance(msg, (HumanMessage, AIMessage))]
#                     return result
#                 except Exception as e:
#                     return {"success": False, "errors": [f"Failed to parse final output: {e}"], "messages": [msg.content for msg in messages]}
#             else:
#                 return {"success": False, "errors": ["Agent did not return an AI message"], "messages": [msg.content for msg in messages]}
#         except Exception as e:
#             logger.exception("Agentic execution failed")
#             return {"success": False, "errors": [str(e)], "messages": []}

# # ---------------------------------------------------------
# # Streamlit integration (call deterministic pipeline)
# # ---------------------------------------------------------
# def main():
#     st.set_page_config(page_title="AgenticAI Payroll System", page_icon="🤖", layout="wide")
#     st.title("🤖 AgenticAI Payroll Processing System")
#     st.markdown("**Deterministic payroll pipeline (LLM for parsing only)**")

#     if 'agentic_ai' not in st.session_state:
#         st.session_state.agentic_ai = PayrollAgenticAI()
#         st.session_state.processing_result = None

#     contract_file = st.file_uploader("Upload Employee Contract PDF", type=["pdf"])
#     if st.button("🚀 Process (Deterministic Pipeline)", disabled=not contract_file):
#         if contract_file:
#             with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#                 tmp.write(contract_file.read())
#                 path = tmp.name
#             with st.spinner("Processing..."):
#                 result = st.session_state.agentic_ai.process_contract_pipeline(path)
#                 st.session_state.processing_result = result
#             try:
#                 os.unlink(path)
#             except:
#                 pass

#     if st.session_state.processing_result:
#         result = st.session_state.processing_result
#         if result.get("success"):
#             st.success("✅ Processing completed successfully")
#         else:
#             st.error(f"❌ Processing finished with errors: {result.get('errors', [])}")

#         with st.expander("Result JSON", expanded=True):
#             st.json(result)

#     else:
#         st.info("Upload a contract PDF and press 'Process' to run the deterministic pipeline.")
#         st.markdown("""
#         **Notes**
#         - Parsing (structure extraction) still uses the LLM. Salary math, compliance checks and anomalies detection are deterministic Python logic (more reliable).
#         - The deterministic pipeline is recommended for production. The LangGraph agentic ReAct flow is available for experimentation but not required.
#         """)

# if __name__ == "__main__":
#     main()


