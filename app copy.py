# app.py
import os
import json
import tempfile
import streamlit as st
from datetime import datetime
from PyPDF2 import PdfReader
from openai import OpenAI
import logging
import sys

# Fix Unicode encoding for Windows console (Streamlit-safe)
if sys.platform.startswith('win'):
    try:
        import codecs
        if hasattr(sys.stdout, 'detach'):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
        else:
            # For Streamlit environment, set console code page to UTF-8
            os.system('chcp 65001 >nul 2>&1')
    except:
        # Fallback: just continue without encoding changes
        pass

# Configure logging with safer Unicode handling
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('agent_communication.log', encoding='utf-8', errors='replace')
    ]
)
logger = logging.getLogger(__name__)

# Environment setup
from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize OpenAI client with Gemini
client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

class PayrollAgentSystem:
    def __init__(self):
        self.contract_data = {}
        self.salary_data = {}
        self.compliance_data = {}
        self.anomalies = {}
        
    def extract_pdf_text(self, file_path):
        """Extract text from PDF file"""
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text.strip()
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""
    
    def llm_call(self, prompt, content):
        """Make LLM call with error handling"""
        try:
            response = client.chat.completions.create(
                model="gemini-2.0-flash-exp",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""
    
    def safe_json_parse(self, text):
        """Safely parse JSON from LLM response"""
        try:
            # Clean up common JSON formatting issues
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            return json.loads(text)
        except:
            logger.error(f"JSON parsing failed for: {text[:100]}...")
            return {}

class PayrollAgent:
    def __init__(self, name, agent_system):
        self.name = name
        self.agent_system = agent_system
    
    def log_agent_communication(self, message):
        """Log agent communication without emojis for Windows compatibility"""
        logger.info(f"[{self.name}] {message}")

class ContractReaderAgent(PayrollAgent):
    def __init__(self, agent_system):
        super().__init__("CONTRACT_READER_AGENT", agent_system)
    
    def process(self, file_path):
        self.log_agent_communication("Starting contract analysis...")
        
        text = self.agent_system.extract_pdf_text(file_path)
        if not text:
            self.log_agent_communication("FAILED - Could not extract text from PDF")
            return {"success": False, "error": "Failed to extract PDF text"}
        
        prompt = """Extract employee salary details from this employment contract.
        Return ONLY JSON with this structure:
        {
          "employee_name": "string",
          "employee_id": "string or null", 
          "department": "string or null",
          "designation": "string or null",
          "location": "string",
          "salary_structure": {
            "basic": number,
            "hra": number,
            "allowances": number,
            "gross": number
          }
        }"""
        
        response = self.agent_system.llm_call(prompt, f"Contract text: {text}")
        self.agent_system.contract_data = self.agent_system.safe_json_parse(response)
        
        employee_name = self.agent_system.contract_data.get('employee_name', 'Unknown')
        gross_salary = self.agent_system.contract_data.get('salary_structure', {}).get('gross', 0)
        
        self.log_agent_communication(f"SUCCESS - Extracted data for {employee_name}")
        self.log_agent_communication(f"Gross salary identified as Rs.{gross_salary}")
        self.log_agent_communication("Passing data to SALARY_CALCULATOR_AGENT...")
        
        return {"success": True, "data": self.agent_system.contract_data}

class SalaryCalculatorAgent(PayrollAgent):
    def __init__(self, agent_system):
        super().__init__("SALARY_CALCULATOR_AGENT", agent_system)
    
    def process(self):
        self.log_agent_communication("Received contract data, starting salary calculations...")
        
        if not self.agent_system.contract_data:
            self.log_agent_communication("FAILED - No contract data available")
            return {"success": False, "error": "No contract data available"}
        
        prompt = """Calculate monthly salary breakdown for Indian payroll.
        Apply standard deductions:
        - PF: 12% of basic (max Rs.1,800)
        - ESI: 0.75% of gross (if gross <= Rs.21,000)
        - Professional Tax: Rs.200/month (if salary > Rs.15,000)
        - TDS: Estimate based on annual salary
        
        Return ONLY JSON:
        {
          "gross_salary": number,
          "deductions": {
            "pf": number,
            "esi": number,
            "professional_tax": number,
            "tds": number
          },
          "net_salary": number
        }"""
        
        response = self.agent_system.llm_call(prompt, json.dumps(self.agent_system.contract_data))
        self.agent_system.salary_data = self.agent_system.safe_json_parse(response)
        
        gross = self.agent_system.salary_data.get('gross_salary', 0)
        net = self.agent_system.salary_data.get('net_salary', 0)
        total_deductions = sum(self.agent_system.salary_data.get('deductions', {}).values())
        
        self.log_agent_communication(f"SUCCESS - Calculated salary breakdown")
        self.log_agent_communication(f"Gross: Rs.{gross:,.2f}, Net: Rs.{net:,.2f}, Deductions: Rs.{total_deductions:,.2f}")
        self.log_agent_communication("Passing data to COMPLIANCE_CHECKER_AGENT...")
        
        return {"success": True, "data": self.agent_system.salary_data}

class ComplianceCheckerAgent(PayrollAgent):
    def __init__(self, agent_system):
        super().__init__("COMPLIANCE_CHECKER_AGENT", agent_system)
    
    def process(self):
        self.log_agent_communication("Received salary data, validating compliance...")
        
        if not self.agent_system.salary_data:
            self.log_agent_communication("FAILED - No salary data available")
            return {"success": False, "error": "No salary data available"}
        
        prompt = """Validate salary calculations against Indian labor law compliance.
        Check PF limits, ESI eligibility, Professional tax rates.
        
        Return ONLY JSON:
        {
          "compliance_status": "COMPLIANT" or "NON_COMPLIANT",
          "issues": ["list of issues if any"],
          "validated_deductions": {
            "pf": number,
            "esi": number,
            "professional_tax": number,
            "tds": number
          }
        }"""
        
        response = self.agent_system.llm_call(prompt, json.dumps(self.agent_system.salary_data))
        self.agent_system.compliance_data = self.agent_system.safe_json_parse(response)
        
        status = self.agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
        issues = self.agent_system.compliance_data.get('issues', [])
        
        if status == 'COMPLIANT':
            self.log_agent_communication("SUCCESS - All calculations are compliant with Indian labor laws")
        else:
            self.log_agent_communication(f"WARNING - Compliance issues found: {issues}")
        
        self.log_agent_communication("Passing data to ANOMALY_DETECTOR_AGENT...")
        return {"success": True, "data": self.agent_system.compliance_data}

class AnomalyDetectorAgent(PayrollAgent):
    def __init__(self, agent_system):
        super().__init__("ANOMALY_DETECTOR_AGENT", agent_system)
    
    def process(self):
        self.log_agent_communication("Received compliance data, scanning for anomalies...")
        
        prompt = """Detect payroll anomalies in the calculations.
        Check for calculation errors, unusual amounts, missing deductions.
        
        Return ONLY JSON:
        {
          "has_anomalies": boolean,
          "anomalies": [
            {
              "type": "string",
              "description": "string", 
              "severity": "LOW|MEDIUM|HIGH"
            }
          ],
          "overall_status": "NORMAL" or "REVIEW_REQUIRED"
        }"""
        
        combined_data = {
            "contract": self.agent_system.contract_data,
            "salary": self.agent_system.salary_data,
            "compliance": self.agent_system.compliance_data
        }
        
        response = self.agent_system.llm_call(prompt, json.dumps(combined_data))
        self.agent_system.anomalies = self.agent_system.safe_json_parse(response)
        
        has_anomalies = self.agent_system.anomalies.get('has_anomalies', False)
        anomaly_count = len(self.agent_system.anomalies.get('anomalies', []))
        
        if has_anomalies:
            self.log_agent_communication(f"WARNING - {anomaly_count} anomalies detected")
            for anomaly in self.agent_system.anomalies.get('anomalies', []):
                severity = anomaly.get('severity', 'LOW')
                description = anomaly.get('description', 'Unknown')
                self.log_agent_communication(f"  - {severity}: {description}")
        else:
            self.log_agent_communication("SUCCESS - No anomalies found")
        
        self.log_agent_communication("Processing completed successfully!")
        return {"success": True, "data": self.agent_system.anomalies}

class PayrollAgentOrchestrator:
    def __init__(self, agent_system):
        self.agent_system = agent_system
        self.contract_reader = ContractReaderAgent(agent_system)
        self.salary_calculator = SalaryCalculatorAgent(agent_system)
        self.compliance_checker = ComplianceCheckerAgent(agent_system)
        self.anomaly_detector = AnomalyDetectorAgent(agent_system)
    
    def process_contract(self, file_path):
        """Orchestrate the entire payroll processing pipeline"""
        logger.info("MAIN_COORDINATOR: Starting multi-agent payroll processing pipeline...")
        
        try:
            # Step 1: Contract Reader Agent
            result1 = self.contract_reader.process(file_path)
            if not result1["success"]:
                return {"success": False, "error": result1["error"]}
            
            # Step 2: Salary Calculator Agent
            result2 = self.salary_calculator.process()
            if not result2["success"]:
                return {"success": False, "error": result2["error"]}
            
            # Step 3: Compliance Checker Agent
            result3 = self.compliance_checker.process()
            if not result3["success"]:
                return {"success": False, "error": result3["error"]}
            
            # Step 4: Anomaly Detector Agent
            result4 = self.anomaly_detector.process()
            if not result4["success"]:
                return {"success": False, "error": result4["error"]}
            
            logger.info("MAIN_COORDINATOR: All agents completed successfully!")
            return {"success": True, "message": "Processing completed successfully"}
            
        except Exception as e:
            logger.error(f"MAIN_COORDINATOR: Processing failed - {str(e)}")
            return {"success": False, "error": str(e)}

# Main Streamlit App
def main():
    st.set_page_config(
        page_title="HR Payroll Agent System",
        page_icon="💼", 
        layout="wide"
    )
    
    st.title("💼 HR Payroll Agent System")
    st.markdown("**Multi-Agent Payroll Processing with Terminal Logging**")
    
    # Initialize agent system
    if 'agent_system' not in st.session_state:
        st.session_state.agent_system = PayrollAgentSystem()
        st.session_state.orchestrator = PayrollAgentOrchestrator(st.session_state.agent_system)
        st.session_state.processing_complete = False
    
    # File upload
    col1, col2 = st.columns([3, 1])
    
    with col1:
        contract_file = st.file_uploader(
            "Upload Employee Contract PDF",
            type=["pdf"],
            help="Upload employment contract for payroll processing"
        )
    
    with col2:
        if st.button("🚀 Process with Agents", type="primary", disabled=not contract_file):
            if contract_file:
                st.session_state.processing_complete = False
                
                with st.spinner("🤖 Agents are processing..."):
                    try:
                        # Save uploaded file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(contract_file.read())
                            contract_path = tmp.name
                        
                        # Process through agent orchestrator
                        result = st.session_state.orchestrator.process_contract(contract_path)
                        
                        if result["success"]:
                            st.session_state.processing_complete = True
                            st.success("✅ Processing completed! Check terminal for detailed agent communication logs.")
                        else:
                            st.error(f"❌ Processing failed: {result['error']}")
                        
                        # Clean up temp file
                        os.unlink(contract_path)
                        
                    except Exception as e:
                        st.error(f"❌ Unexpected error: {str(e)}")
    
    # Display results
    if st.session_state.processing_complete:
        agent_system = st.session_state.agent_system
        
        st.header("📊 Processing Results")
        
        # Employee Info
        if agent_system.contract_data:
            st.subheader("👤 Employee Information") 
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Name", agent_system.contract_data.get("employee_name", "N/A"))
            with col2:
                st.metric("Department", agent_system.contract_data.get("department", "N/A"))
            with col3:
                st.metric("Designation", agent_system.contract_data.get("designation", "N/A"))
        
        # Salary Breakdown
        if agent_system.salary_data:
            st.subheader("💰 Salary Breakdown")
            col1, col2, col3 = st.columns(3)
            
            gross = agent_system.salary_data.get('gross_salary', 0)
            net = agent_system.salary_data.get('net_salary', 0)
            total_deductions = sum(agent_system.salary_data.get('deductions', {}).values())
            
            with col1:
                st.metric("Gross Salary", f"₹{gross:,.2f}")
            with col2:
                st.metric("Total Deductions", f"₹{total_deductions:,.2f}")  
            with col3:
                st.metric("Net Salary", f"₹{net:,.2f}")
            
            # Detailed breakdown
            with st.expander("View Detailed Breakdown"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Earnings:**")
                    if agent_system.contract_data and agent_system.contract_data.get("salary_structure"):
                        salary_struct = agent_system.contract_data["salary_structure"]
                        for component, amount in salary_struct.items():
                            if amount > 0:
                                st.write(f"• {component.replace('_', ' ').title()}: ₹{amount:,.2f}")
                
                with col2:
                    st.write("**Deductions:**")
                    deductions = agent_system.salary_data.get("deductions", {})
                    for deduction, amount in deductions.items():
                        if amount > 0:
                            st.write(f"• {deduction.replace('_', ' ').title()}: ₹{amount:,.2f}")
        
        # Compliance & Anomalies
        col1, col2 = st.columns(2)
        
        with col1:
            if agent_system.compliance_data:
                st.subheader("⚖️ Compliance Status")
                status = agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
                if status == 'COMPLIANT':
                    st.success("✅ All calculations compliant")
                else:
                    st.warning("⚠️ Compliance issues detected")
                    issues = agent_system.compliance_data.get('issues', [])
                    for issue in issues:
                        st.write(f"• {issue}")
        
        with col2:
            if agent_system.anomalies:
                st.subheader("🔍 Anomaly Detection")
                if agent_system.anomalies.get('has_anomalies'):
                    anomaly_count = len(agent_system.anomalies.get('anomalies', []))
                    st.warning(f"⚠️ {anomaly_count} issues found")
                    for anomaly in agent_system.anomalies.get('anomalies', []):
                        severity = anomaly.get('severity', 'LOW')
                        description = anomaly.get('description', 'Unknown')
                        st.write(f"• **{severity}**: {description}")
                else:
                    st.success("✅ No anomalies detected")
    
    else:
        st.info("👆 Upload a contract PDF to start multi-agent processing")
        st.markdown("**💡 Real-time agent communication will appear in your terminal/console!**")
    
    # Footer
    st.markdown("---")
    st.markdown("*Multi-Agent Payroll System • Real-time Agent Logging*")

if __name__ == "__main__":
    main()
    


# # app.py
# import os
# import json
# import tempfile
# import streamlit as st
# from datetime import datetime
# from PyPDF2 import PdfReader
# from openai import OpenAI
# import logging
# import sys

# # Fix Unicode encoding for Windows console
# if sys.platform.startswith('win'):
#     import codecs
#     sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
#     sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

# # Configure logging without emojis for Windows compatibility
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(),
#         logging.FileHandler('agent_communication.log', encoding='utf-8')
#     ]
# )
# logger = logging.getLogger(__name__)

# # Environment setup
# from dotenv import load_dotenv
# load_dotenv()
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # Initialize OpenAI client with Gemini
# client = OpenAI(
#     api_key=GEMINI_API_KEY,
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# )

# class PayrollAgentSystem:
#     def __init__(self):
#         self.contract_data = {}
#         self.salary_data = {}
#         self.compliance_data = {}
#         self.anomalies = {}
        
#     def extract_pdf_text(self, file_path):
#         """Extract text from PDF file"""
#         try:
#             reader = PdfReader(file_path)
#             text = ""
#             for page in reader.pages:
#                 text += page.extract_text() or ""
#             return text.strip()
#         except Exception as e:
#             logger.error(f"PDF extraction failed: {e}")
#             return ""
    
#     def llm_call(self, prompt, content):
#         """Make LLM call with error handling"""
#         try:
#             response = client.chat.completions.create(
#                 model="gemini-2.0-flash-exp",
#                 messages=[
#                     {"role": "system", "content": prompt},
#                     {"role": "user", "content": content}
#                 ],
#                 temperature=0.1,
#                 max_tokens=2000
#             )
#             return response.choices[0].message.content.strip()
#         except Exception as e:
#             logger.error(f"LLM call failed: {e}")
#             return ""
    
#     def safe_json_parse(self, text):
#         """Safely parse JSON from LLM response"""
#         try:
#             # Clean up common JSON formatting issues
#             text = text.strip()
#             if text.startswith("```json"):
#                 text = text[7:]
#             if text.startswith("```"):
#                 text = text[3:]
#             if text.endswith("```"):
#                 text = text[:-3]
#             text = text.strip()
#             return json.loads(text)
#         except:
#             logger.error(f"JSON parsing failed for: {text[:100]}...")
#             return {}

# class PayrollAgent:
#     def __init__(self, name, agent_system):
#         self.name = name
#         self.agent_system = agent_system
    
#     def log_agent_communication(self, message):
#         """Log agent communication without emojis for Windows compatibility"""
#         logger.info(f"[{self.name}] {message}")

# class ContractReaderAgent(PayrollAgent):
#     def __init__(self, agent_system):
#         super().__init__("CONTRACT_READER_AGENT", agent_system)
    
#     def process(self, file_path):
#         self.log_agent_communication("Starting contract analysis...")
        
#         text = self.agent_system.extract_pdf_text(file_path)
#         if not text:
#             self.log_agent_communication("FAILED - Could not extract text from PDF")
#             return {"success": False, "error": "Failed to extract PDF text"}
        
#         prompt = """Extract employee salary details from this employment contract.
#         Return ONLY JSON with this structure:
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
        
#         response = self.agent_system.llm_call(prompt, f"Contract text: {text}")
#         self.agent_system.contract_data = self.agent_system.safe_json_parse(response)
        
#         employee_name = self.agent_system.contract_data.get('employee_name', 'Unknown')
#         gross_salary = self.agent_system.contract_data.get('salary_structure', {}).get('gross', 0)
        
#         self.log_agent_communication(f"SUCCESS - Extracted data for {employee_name}")
#         self.log_agent_communication(f"Gross salary identified as Rs.{gross_salary}")
#         self.log_agent_communication("Passing data to SALARY_CALCULATOR_AGENT...")
        
#         return {"success": True, "data": self.agent_system.contract_data}

# class SalaryCalculatorAgent(PayrollAgent):
#     def __init__(self, agent_system):
#         super().__init__("SALARY_CALCULATOR_AGENT", agent_system)
    
#     def process(self):
#         self.log_agent_communication("Received contract data, starting salary calculations...")
        
#         if not self.agent_system.contract_data:
#             self.log_agent_communication("FAILED - No contract data available")
#             return {"success": False, "error": "No contract data available"}
        
#         prompt = """Calculate monthly salary breakdown for Indian payroll.
#         Apply standard deductions:
#         - PF: 12% of basic (max Rs.1,800)
#         - ESI: 0.75% of gross (if gross <= Rs.21,000)
#         - Professional Tax: Rs.200/month (if salary > Rs.15,000)
#         - TDS: Estimate based on annual salary
        
#         Return ONLY JSON:
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
        
#         response = self.agent_system.llm_call(prompt, json.dumps(self.agent_system.contract_data))
#         self.agent_system.salary_data = self.agent_system.safe_json_parse(response)
        
#         gross = self.agent_system.salary_data.get('gross_salary', 0)
#         net = self.agent_system.salary_data.get('net_salary', 0)
#         total_deductions = sum(self.agent_system.salary_data.get('deductions', {}).values())
        
#         self.log_agent_communication(f"SUCCESS - Calculated salary breakdown")
#         self.log_agent_communication(f"Gross: Rs.{gross:,.2f}, Net: Rs.{net:,.2f}, Deductions: Rs.{total_deductions:,.2f}")
#         self.log_agent_communication("Passing data to COMPLIANCE_CHECKER_AGENT...")
        
#         return {"success": True, "data": self.agent_system.salary_data}

# class ComplianceCheckerAgent(PayrollAgent):
#     def __init__(self, agent_system):
#         super().__init__("COMPLIANCE_CHECKER_AGENT", agent_system)
    
#     def process(self):
#         self.log_agent_communication("Received salary data, validating compliance...")
        
#         if not self.agent_system.salary_data:
#             self.log_agent_communication("FAILED - No salary data available")
#             return {"success": False, "error": "No salary data available"}
        
#         prompt = """Validate salary calculations against Indian labor law compliance.
#         Check PF limits, ESI eligibility, Professional tax rates.
        
#         Return ONLY JSON:
#         {
#           "compliance_status": "COMPLIANT" or "NON_COMPLIANT",
#           "issues": ["list of issues if any"],
#           "validated_deductions": {
#             "pf": number,
#             "esi": number,
#             "professional_tax": number,
#             "tds": number
#           }
#         }"""
        
#         response = self.agent_system.llm_call(prompt, json.dumps(self.agent_system.salary_data))
#         self.agent_system.compliance_data = self.agent_system.safe_json_parse(response)
        
#         status = self.agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
#         issues = self.agent_system.compliance_data.get('issues', [])
        
#         if status == 'COMPLIANT':
#             self.log_agent_communication("SUCCESS - All calculations are compliant with Indian labor laws")
#         else:
#             self.log_agent_communication(f"WARNING - Compliance issues found: {issues}")
        
#         self.log_agent_communication("Passing data to ANOMALY_DETECTOR_AGENT...")
#         return {"success": True, "data": self.agent_system.compliance_data}

# class AnomalyDetectorAgent(PayrollAgent):
#     def __init__(self, agent_system):
#         super().__init__("ANOMALY_DETECTOR_AGENT", agent_system)
    
#     def process(self):
#         self.log_agent_communication("Received compliance data, scanning for anomalies...")
        
#         prompt = """Detect payroll anomalies in the calculations.
#         Check for calculation errors, unusual amounts, missing deductions.
        
#         Return ONLY JSON:
#         {
#           "has_anomalies": boolean,
#           "anomalies": [
#             {
#               "type": "string",
#               "description": "string", 
#               "severity": "LOW|MEDIUM|HIGH"
#             }
#           ],
#           "overall_status": "NORMAL" or "REVIEW_REQUIRED"
#         }"""
        
#         combined_data = {
#             "contract": self.agent_system.contract_data,
#             "salary": self.agent_system.salary_data,
#             "compliance": self.agent_system.compliance_data
#         }
        
#         response = self.agent_system.llm_call(prompt, json.dumps(combined_data))
#         self.agent_system.anomalies = self.agent_system.safe_json_parse(response)
        
#         has_anomalies = self.agent_system.anomalies.get('has_anomalies', False)
#         anomaly_count = len(self.agent_system.anomalies.get('anomalies', []))
        
#         if has_anomalies:
#             self.log_agent_communication(f"WARNING - {anomaly_count} anomalies detected")
#             for anomaly in self.agent_system.anomalies.get('anomalies', []):
#                 severity = anomaly.get('severity', 'LOW')
#                 description = anomaly.get('description', 'Unknown')
#                 self.log_agent_communication(f"  - {severity}: {description}")
#         else:
#             self.log_agent_communication("SUCCESS - No anomalies found")
        
#         self.log_agent_communication("Processing completed successfully!")
#         return {"success": True, "data": self.agent_system.anomalies}

# class PayrollAgentOrchestrator:
#     def __init__(self, agent_system):
#         self.agent_system = agent_system
#         self.contract_reader = ContractReaderAgent(agent_system)
#         self.salary_calculator = SalaryCalculatorAgent(agent_system)
#         self.compliance_checker = ComplianceCheckerAgent(agent_system)
#         self.anomaly_detector = AnomalyDetectorAgent(agent_system)
    
#     def process_contract(self, file_path):
#         """Orchestrate the entire payroll processing pipeline"""
#         logger.info("MAIN_COORDINATOR: Starting multi-agent payroll processing pipeline...")
        
#         try:
#             # Step 1: Contract Reader Agent
#             result1 = self.contract_reader.process(file_path)
#             if not result1["success"]:
#                 return {"success": False, "error": result1["error"]}
            
#             # Step 2: Salary Calculator Agent
#             result2 = self.salary_calculator.process()
#             if not result2["success"]:
#                 return {"success": False, "error": result2["error"]}
            
#             # Step 3: Compliance Checker Agent
#             result3 = self.compliance_checker.process()
#             if not result3["success"]:
#                 return {"success": False, "error": result3["error"]}
            
#             # Step 4: Anomaly Detector Agent
#             result4 = self.anomaly_detector.process()
#             if not result4["success"]:
#                 return {"success": False, "error": result4["error"]}
            
#             logger.info("MAIN_COORDINATOR: All agents completed successfully!")
#             return {"success": True, "message": "Processing completed successfully"}
            
#         except Exception as e:
#             logger.error(f"MAIN_COORDINATOR: Processing failed - {str(e)}")
#             return {"success": False, "error": str(e)}

# # Main Streamlit App
# def main():
#     st.set_page_config(
#         page_title="HR Payroll Agent System",
#         page_icon="💼", 
#         layout="wide"
#     )
    
#     st.title("💼 HR Payroll Agent System")
#     st.markdown("**Multi-Agent Payroll Processing with Terminal Logging**")
    
#     # Initialize agent system
#     if 'agent_system' not in st.session_state:
#         st.session_state.agent_system = PayrollAgentSystem()
#         st.session_state.orchestrator = PayrollAgentOrchestrator(st.session_state.agent_system)
#         st.session_state.processing_complete = False
    
#     # File upload
#     col1, col2 = st.columns([3, 1])
    
#     with col1:
#         contract_file = st.file_uploader(
#             "Upload Employee Contract PDF",
#             type=["pdf"],
#             help="Upload employment contract for payroll processing"
#         )
    
#     with col2:
#         if st.button("🚀 Process with Agents", type="primary", disabled=not contract_file):
#             if contract_file:
#                 st.session_state.processing_complete = False
                
#                 with st.spinner("🤖 Agents are processing..."):
#                     try:
#                         # Save uploaded file
#                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#                             tmp.write(contract_file.read())
#                             contract_path = tmp.name
                        
#                         # Process through agent orchestrator
#                         result = st.session_state.orchestrator.process_contract(contract_path)
                        
#                         if result["success"]:
#                             st.session_state.processing_complete = True
#                             st.success("✅ Processing completed! Check terminal for detailed agent communication logs.")
#                         else:
#                             st.error(f"❌ Processing failed: {result['error']}")
                        
#                         # Clean up temp file
#                         os.unlink(contract_path)
                        
#                     except Exception as e:
#                         st.error(f"❌ Unexpected error: {str(e)}")
    
#     # Display results
#     if st.session_state.processing_complete:
#         agent_system = st.session_state.agent_system
        
#         st.header("📊 Processing Results")
        
#         # Employee Info
#         if agent_system.contract_data:
#             st.subheader("👤 Employee Information") 
#             col1, col2, col3 = st.columns(3)
#             with col1:
#                 st.metric("Name", agent_system.contract_data.get("employee_name", "N/A"))
#             with col2:
#                 st.metric("Department", agent_system.contract_data.get("department", "N/A"))
#             with col3:
#                 st.metric("Designation", agent_system.contract_data.get("designation", "N/A"))
        
#         # Salary Breakdown
#         if agent_system.salary_data:
#             st.subheader("💰 Salary Breakdown")
#             col1, col2, col3 = st.columns(3)
            
#             gross = agent_system.salary_data.get('gross_salary', 0)
#             net = agent_system.salary_data.get('net_salary', 0)
#             total_deductions = sum(agent_system.salary_data.get('deductions', {}).values())
            
#             with col1:
#                 st.metric("Gross Salary", f"₹{gross:,.2f}")
#             with col2:
#                 st.metric("Total Deductions", f"₹{total_deductions:,.2f}")  
#             with col3:
#                 st.metric("Net Salary", f"₹{net:,.2f}")
            
#             # Detailed breakdown
#             with st.expander("View Detailed Breakdown"):
#                 col1, col2 = st.columns(2)
                
#                 with col1:
#                     st.write("**Earnings:**")
#                     if agent_system.contract_data and agent_system.contract_data.get("salary_structure"):
#                         salary_struct = agent_system.contract_data["salary_structure"]
#                         for component, amount in salary_struct.items():
#                             if amount > 0:
#                                 st.write(f"• {component.replace('_', ' ').title()}: ₹{amount:,.2f}")
                
#                 with col2:
#                     st.write("**Deductions:**")
#                     deductions = agent_system.salary_data.get("deductions", {})
#                     for deduction, amount in deductions.items():
#                         if amount > 0:
#                             st.write(f"• {deduction.replace('_', ' ').title()}: ₹{amount:,.2f}")
        
#         # Compliance & Anomalies
#         col1, col2 = st.columns(2)
        
#         with col1:
#             if agent_system.compliance_data:
#                 st.subheader("⚖️ Compliance Status")
#                 status = agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
#                 if status == 'COMPLIANT':
#                     st.success("✅ All calculations compliant")
#                 else:
#                     st.warning("⚠️ Compliance issues detected")
#                     issues = agent_system.compliance_data.get('issues', [])
#                     for issue in issues:
#                         st.write(f"• {issue}")
        
#         with col2:
#             if agent_system.anomalies:
#                 st.subheader("🔍 Anomaly Detection")
#                 if agent_system.anomalies.get('has_anomalies'):
#                     anomaly_count = len(agent_system.anomalies.get('anomalies', []))
#                     st.warning(f"⚠️ {anomaly_count} issues found")
#                     for anomaly in agent_system.anomalies.get('anomalies', []):
#                         severity = anomaly.get('severity', 'LOW')
#                         description = anomaly.get('description', 'Unknown')
#                         st.write(f"• **{severity}**: {description}")
#                 else:
#                     st.success("✅ No anomalies detected")
    
#     else:
#         st.info("👆 Upload a contract PDF to start multi-agent processing")
#         st.markdown("**💡 Real-time agent communication will appear in your terminal/console!**")
    
#     # Footer
#     st.markdown("---")
#     st.markdown("*Multi-Agent Payroll System • Real-time Agent Logging*")

# if __name__ == "__main__":
#     main()


# # # app.py
# # import os
# # import json
# # import tempfile
# # import streamlit as st
# # from datetime import datetime
# # from PyPDF2 import PdfReader
# # from openai import OpenAI
# # from langchain.agents import AgentExecutor, create_openai_functions_agent
# # from langchain.tools import Tool
# # from langchain_openai import ChatOpenAI
# # from langchain.prompts import ChatPromptTemplate
# # from langchain.schema import SystemMessage, HumanMessage
# # import logging

# # # Configure logging to show agent communication
# # logging.basicConfig(
# #     level=logging.INFO,
# #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
# #     handlers=[
# #         logging.StreamHandler(),
# #         logging.FileHandler('agent_communication.log')
# #     ]
# # )
# # logger = logging.getLogger(__name__)

# # # Environment setup
# # from dotenv import load_dotenv
# # load_dotenv()
# # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # # Initialize OpenAI client with Gemini
# # client = OpenAI(
# #     api_key=GEMINI_API_KEY,
# #     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# # )

# # # Initialize LangChain ChatOpenAI with Gemini
# # llm = ChatOpenAI(
# #     model="gemini-2.0-flash-exp",
# #     openai_api_key=GEMINI_API_KEY,
# #     openai_api_base="https://generativelanguage.googleapis.com/v1beta/openai/",
# #     temperature=0.1
# # )

# # class PayrollAgentSystem:
# #     def __init__(self):
# #         self.contract_data = {}
# #         self.salary_data = {}
# #         self.compliance_data = {}
# #         self.anomalies = {}
        
# #     def extract_pdf_text(self, file_path):
# #         """Extract text from PDF file"""
# #         try:
# #             reader = PdfReader(file_path)
# #             text = ""
# #             for page in reader.pages:
# #                 text += page.extract_text() or ""
# #             return text.strip()
# #         except Exception as e:
# #             logger.error(f"PDF extraction failed: {e}")
# #             return ""
    
# #     def llm_call(self, prompt, content):
# #         """Make LLM call with error handling"""
# #         try:
# #             response = client.chat.completions.create(
# #                 model="gemini-2.0-flash-exp",
# #                 messages=[
# #                     {"role": "system", "content": prompt},
# #                     {"role": "user", "content": content}
# #                 ],
# #                 temperature=0.1,
# #                 max_tokens=2000
# #             )
# #             return response.choices[0].message.content.strip()
# #         except Exception as e:
# #             logger.error(f"LLM call failed: {e}")
# #             return ""
    
# #     def safe_json_parse(self, text):
# #         """Safely parse JSON from LLM response"""
# #         try:
# #             # Clean up common JSON formatting issues
# #             text = text.strip()
# #             if text.startswith("```json"):
# #                 text = text[7:]
# #             if text.startswith("```"):
# #                 text = text[3:]
# #             if text.endswith("```"):
# #                 text = text[:-3]
# #             text = text.strip()
# #             return json.loads(text)
# #         except:
# #             logger.error(f"JSON parsing failed for: {text[:100]}...")
# #             return {}

# # # Create Agent Tools
# # def create_contract_reader_tool(agent_system):
# #     def contract_reader(file_path: str) -> str:
# #         """Extract employee details from contract PDF"""
# #         logger.info("🤖 CONTRACT READER AGENT: Starting contract analysis...")
        
# #         text = agent_system.extract_pdf_text(file_path)
# #         if not text:
# #             logger.error("❌ CONTRACT READER AGENT: Failed to extract text from PDF")
# #             return "Failed to extract PDF text"
        
# #         prompt = """Extract employee salary details from this employment contract.
# #         Return ONLY JSON with this structure:
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
        
# #         response = agent_system.llm_call(prompt, f"Contract text: {text}")
# #         agent_system.contract_data = agent_system.safe_json_parse(response)
        
# #         logger.info(f"✅ CONTRACT READER AGENT: Extracted data for {agent_system.contract_data.get('employee_name', 'Unknown')}")
# #         logger.info(f"📊 CONTRACT READER AGENT: Gross salary identified as ₹{agent_system.contract_data.get('salary_structure', {}).get('gross', 0)}")
        
# #         return f"Contract processed successfully for {agent_system.contract_data.get('employee_name', 'Employee')}"
    
# #     return Tool(
# #         name="contract_reader",
# #         description="Read and extract employee details from contract PDF",
# #         func=contract_reader
# #     )

# # def create_salary_calculator_tool(agent_system):
# #     def salary_calculator(employee_data: str) -> str:
# #         """Calculate salary breakdown with deductions"""
# #         logger.info("🧮 SALARY CALCULATOR AGENT: Starting salary calculations...")
        
# #         if not agent_system.contract_data:
# #             logger.error("❌ SALARY CALCULATOR AGENT: No contract data available")
# #             return "No contract data available for calculation"
        
# #         prompt = """Calculate monthly salary breakdown for Indian payroll.
# #         Apply standard deductions:
# #         - PF: 12% of basic (max ₹1,800)
# #         - ESI: 0.75% of gross (if gross ≤ ₹21,000)
# #         - Professional Tax: ₹200/month (if salary > ₹15,000)
# #         - TDS: Estimate based on annual salary
        
# #         Return ONLY JSON:
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
        
# #         response = agent_system.llm_call(prompt, json.dumps(agent_system.contract_data))
# #         agent_system.salary_data = agent_system.safe_json_parse(response)
        
# #         gross = agent_system.salary_data.get('gross_salary', 0)
# #         net = agent_system.salary_data.get('net_salary', 0)
# #         total_deductions = sum(agent_system.salary_data.get('deductions', {}).values())
        
# #         logger.info(f"💰 SALARY CALCULATOR AGENT: Gross: ₹{gross:,.2f}, Net: ₹{net:,.2f}")
# #         logger.info(f"📉 SALARY CALCULATOR AGENT: Total deductions: ₹{total_deductions:,.2f}")
        
# #         return f"Salary calculated - Gross: ₹{gross:,.2f}, Net: ₹{net:,.2f}"
    
# #     return Tool(
# #         name="salary_calculator",
# #         description="Calculate salary breakdown with deductions",
# #         func=salary_calculator
# #     )

# # def create_compliance_checker_tool(agent_system):
# #     def compliance_checker(salary_data: str) -> str:
# #         """Check compliance with Indian labor laws"""
# #         logger.info("⚖️ COMPLIANCE CHECKER AGENT: Validating calculations...")
        
# #         if not agent_system.salary_data:
# #             logger.error("❌ COMPLIANCE CHECKER AGENT: No salary data available")
# #             return "No salary data available for compliance check"
        
# #         prompt = """Validate salary calculations against Indian labor law compliance.
# #         Check PF limits, ESI eligibility, Professional tax rates.
        
# #         Return ONLY JSON:
# #         {
# #           "compliance_status": "COMPLIANT" or "NON_COMPLIANT",
# #           "issues": ["list of issues if any"],
# #           "validated_deductions": {
# #             "pf": number,
# #             "esi": number,
# #             "professional_tax": number,
# #             "tds": number
# #           }
# #         }"""
        
# #         response = agent_system.llm_call(prompt, json.dumps(agent_system.salary_data))
# #         agent_system.compliance_data = agent_system.safe_json_parse(response)
        
# #         status = agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
# #         issues = agent_system.compliance_data.get('issues', [])
        
# #         if status == 'COMPLIANT':
# #             logger.info("✅ COMPLIANCE CHECKER AGENT: All calculations are compliant")
# #         else:
# #             logger.warning(f"⚠️ COMPLIANCE CHECKER AGENT: Issues found: {issues}")
        
# #         return f"Compliance check completed - Status: {status}"
    
# #     return Tool(
# #         name="compliance_checker", 
# #         description="Check compliance with Indian labor laws",
# #         func=compliance_checker
# #     )

# # def create_anomaly_detector_tool(agent_system):
# #     def anomaly_detector(all_data: str) -> str:
# #         """Detect payroll anomalies"""
# #         logger.info("🔍 ANOMALY DETECTOR AGENT: Scanning for irregularities...")
        
# #         prompt = """Detect payroll anomalies in the calculations.
# #         Check for calculation errors, unusual amounts, missing deductions.
        
# #         Return ONLY JSON:
# #         {
# #           "has_anomalies": boolean,
# #           "anomalies": [
# #             {
# #               "type": "string",
# #               "description": "string", 
# #               "severity": "LOW|MEDIUM|HIGH"
# #             }
# #           ],
# #           "overall_status": "NORMAL" or "REVIEW_REQUIRED"
# #         }"""
        
# #         combined_data = {
# #             "contract": agent_system.contract_data,
# #             "salary": agent_system.salary_data,
# #             "compliance": agent_system.compliance_data
# #         }
        
# #         response = agent_system.llm_call(prompt, json.dumps(combined_data))
# #         agent_system.anomalies = agent_system.safe_json_parse(response)
        
# #         has_anomalies = agent_system.anomalies.get('has_anomalies', False)
# #         anomaly_count = len(agent_system.anomalies.get('anomalies', []))
        
# #         if has_anomalies:
# #             logger.warning(f"⚠️ ANOMALY DETECTOR AGENT: {anomaly_count} anomalies detected")
# #             for anomaly in agent_system.anomalies.get('anomalies', []):
# #                 logger.warning(f"   • {anomaly.get('severity', 'LOW')}: {anomaly.get('description', 'Unknown')}")
# #         else:
# #             logger.info("✅ ANOMALY DETECTOR AGENT: No anomalies found")
        
# #         return f"Anomaly detection completed - {anomaly_count} issues found"
    
# #     return Tool(
# #         name="anomaly_detector",
# #         description="Detect anomalies in payroll calculations", 
# #         func=anomaly_detector
# #     )

# # # Main Streamlit App
# # def main():
# #     st.set_page_config(
# #         page_title="HR Payroll Agent System",
# #         page_icon="💼", 
# #         layout="wide"
# #     )
    
# #     st.title("💼 HR Payroll Agent System")
# #     st.markdown("**Multi-Agent Payroll Processing with Terminal Logging**")
    
# #     # Initialize agent system
# #     if 'agent_system' not in st.session_state:
# #         st.session_state.agent_system = PayrollAgentSystem()
# #         st.session_state.processing_complete = False
    
# #     # File upload
# #     col1, col2 = st.columns([3, 1])
    
# #     with col1:
# #         contract_file = st.file_uploader(
# #             "Upload Employee Contract PDF",
# #             type=["pdf"],
# #             help="Upload employment contract for payroll processing"
# #         )
    
# #     with col2:
# #         if st.button("🚀 Process with Agents", type="primary", disabled=not contract_file):
# #             if contract_file:
# #                 st.session_state.processing_complete = False
                
# #                 with st.spinner("🤖 Agents are processing..."):
# #                     try:
# #                         # Save uploaded file
# #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# #                             tmp.write(contract_file.read())
# #                             contract_path = tmp.name
                        
# #                         # Create agent system and tools
# #                         agent_system = st.session_state.agent_system
                        
# #                         tools = [
# #                             create_contract_reader_tool(agent_system),
# #                             create_salary_calculator_tool(agent_system), 
# #                             create_compliance_checker_tool(agent_system),
# #                             create_anomaly_detector_tool(agent_system)
# #                         ]
                        
# #                         # Create agent prompt
# #                         prompt = ChatPromptTemplate.from_messages([
# #                             SystemMessage(content="""You are a payroll processing coordinator.
# #                             Process the contract through these agents in sequence:
# #                             1. contract_reader - to extract employee details
# #                             2. salary_calculator - to calculate salary breakdown  
# #                             3. compliance_checker - to validate compliance
# #                             4. anomaly_detector - to detect issues
                            
# #                             Call each tool with appropriate data and summarize results."""),
# #                             ("human", "{input}"),
# #                             ("placeholder", "{agent_scratchpad}")
# #                         ])
                        
# #                         # Create and execute agent
# #                         agent = create_openai_functions_agent(llm, tools, prompt)
# #                         agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
                        
# #                         logger.info("🚀 MAIN COORDINATOR: Starting multi-agent payroll processing...")
                        
# #                         # Execute agent workflow
# #                         result = agent_executor.invoke({
# #                             "input": f"Process the contract PDF at path: {contract_path}"
# #                         })
                        
# #                         logger.info("✅ MAIN COORDINATOR: All agents completed successfully!")
                        
# #                         st.session_state.processing_complete = True
# #                         st.success("✅ Processing completed! Check terminal for agent communication logs.")
                        
# #                     except Exception as e:
# #                         logger.error(f"❌ MAIN COORDINATOR: Processing failed - {e}")
# #                         st.error(f"Processing failed: {str(e)}")
    
# #     # Display results
# #     if st.session_state.processing_complete:
# #         agent_system = st.session_state.agent_system
        
# #         st.header("📊 Processing Results")
        
# #         # Employee Info
# #         if agent_system.contract_data:
# #             st.subheader("👤 Employee Information") 
# #             col1, col2, col3 = st.columns(3)
# #             with col1:
# #                 st.metric("Name", agent_system.contract_data.get("employee_name", "N/A"))
# #             with col2:
# #                 st.metric("Department", agent_system.contract_data.get("department", "N/A"))
# #             with col3:
# #                 st.metric("Designation", agent_system.contract_data.get("designation", "N/A"))
        
# #         # Salary Breakdown
# #         if agent_system.salary_data:
# #             st.subheader("💰 Salary Breakdown")
# #             col1, col2, col3 = st.columns(3)
            
# #             gross = agent_system.salary_data.get('gross_salary', 0)
# #             net = agent_system.salary_data.get('net_salary', 0)
# #             total_deductions = sum(agent_system.salary_data.get('deductions', {}).values())
            
# #             with col1:
# #                 st.metric("Gross Salary", f"₹{gross:,.2f}")
# #             with col2:
# #                 st.metric("Total Deductions", f"₹{total_deductions:,.2f}")  
# #             with col3:
# #                 st.metric("Net Salary", f"₹{net:,.2f}")
        
# #         # Compliance & Anomalies
# #         col1, col2 = st.columns(2)
        
# #         with col1:
# #             if agent_system.compliance_data:
# #                 st.subheader("⚖️ Compliance Status")
# #                 status = agent_system.compliance_data.get('compliance_status', 'UNKNOWN')
# #                 if status == 'COMPLIANT':
# #                     st.success("✅ All calculations compliant")
# #                 else:
# #                     st.warning("⚠️ Compliance issues detected")
        
# #         with col2:
# #             if agent_system.anomalies:
# #                 st.subheader("🔍 Anomaly Detection")
# #                 if agent_system.anomalies.get('has_anomalies'):
# #                     st.warning(f"⚠️ {len(agent_system.anomalies.get('anomalies', []))} issues found")
# #                 else:
# #                     st.success("✅ No anomalies detected")
    
# #     else:
# #         st.info("👆 Upload a contract PDF to start multi-agent processing")
# #         st.markdown("**Check your terminal/console for real-time agent communication logs!**")
    
# #     # Footer
# #     st.markdown("---")
# #     st.markdown("*Multi-Agent Payroll System • Real-time Agent Logging*")

# # if __name__ == "__main__":
# #     main()



# # # # app.py
# # # import os
# # # import io
# # # import json
# # # import base64
# # # import pdfkit
# # # import tempfile
# # # import streamlit as st
# # # import logging
# # # from datetime import datetime
# # # from pymongo import MongoClient
# # # from openai import OpenAI   
# # # from PyPDF2 import PdfReader
# # # from langchain_community.vectorstores import Chroma
# # # from langchain_community.document_loaders import PyPDFLoader
# # # from langchain_text_splitters import RecursiveCharacterTextSplitter
# # # from langchain_google_genai import GoogleGenerativeAIEmbeddings
# # # from langgraph.graph import StateGraph, END
# # # import asyncio
# # # from typing import TypedDict, Optional, Dict, Any, List
# # # from dotenv import load_dotenv
# # # import ast
# # # import traceback

# # # # Load environment variables
# # # load_dotenv()
# # # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # # # Configure minimal logging (backend only)
# # # logging.basicConfig(level=logging.WARNING)
# # # logger = logging.getLogger(__name__)

# # # # Handle asyncio event loop
# # # try:
# # #     asyncio.get_running_loop()
# # # except RuntimeError:
# # #     asyncio.set_event_loop(asyncio.new_event_loop())

# # # class PayrollState(TypedDict):
# # #     contract_path: str
# # #     contract_data: Optional[Dict[str, Any]]
# # #     salary_breakdown: Optional[Dict[str, Any]]
# # #     compliance_data: Optional[Dict[str, Any]]
# # #     anomalies: Optional[Dict[str, Any]]
# # #     payslip_path: Optional[str]

# # # # =====================
# # # # CONFIGURATION
# # # # =====================
# # # MONGO_URI = "mongodb+srv://Naveen:Qwe%401234567890@cluster0.u8t9s.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# # # DB_NAME = "payroll_db"
# # # CHROMA_DIR = "./chroma_db"
# # # PAYSPLIP_DIR = "./payslips"
# # # os.makedirs(PAYSPLIP_DIR, exist_ok=True)
# # # os.makedirs(CHROMA_DIR, exist_ok=True)

# # # # Initialize connections (silent)
# # # try:
# # #     mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
# # #     db = mongo_client[DB_NAME]
# # #     mongo_client.admin.command('ping')
# # # except:
# # #     db = None

# # # try:
# # #     client = OpenAI(
# # #         api_key=GEMINI_API_KEY,
# # #         base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# # #     )
# # # except:
# # #     client = None

# # # try:
# # #     embedding_fn = GoogleGenerativeAIEmbeddings(
# # #         model="models/embedding-001",
# # #         google_api_key=GEMINI_API_KEY
# # #     )
# # # except:
# # #     embedding_fn = None

# # # # =====================
# # # # AGENT PROMPTS
# # # # =====================
# # # CONTRACT_READER_PROMPT = """
# # # You are an HR payroll assistant. Extract employee salary details from this employment contract.

# # # Return ONLY JSON with this structure:
# # # {
# # #   "employee_name": "string",
# # #   "employee_id": "string or null",
# # #   "joining_date": "YYYY-MM-DD or null",
# # #   "location": "string",
# # #   "department": "string or null",
# # #   "designation": "string or null",
# # #   "salary_structure": {
# # #     "basic": number,
# # #     "hra": number,
# # #     "lta": number,
# # #     "conveyance": number,
# # #     "medical": number,
# # #     "special_allowance": number,
# # #     "bonus": number,
# # #     "variable_pay": number
# # #   },
# # #   "statutory_components": {
# # #     "pf_applicable": boolean,
# # #     "esi_applicable": boolean,
# # #     "professional_tax_applicable": boolean
# # #   }
# # # }

# # # Extract amounts as numbers only. If not mentioned, use 0 for salary components and null for other fields.
# # # """

# # # SALARY_BREAKDOWN_PROMPT = """
# # # Calculate monthly salary breakdown for this employee based on Indian payroll standards.

# # # Apply these deduction rules:
# # # - PF: 12% of basic salary (max ₹1,800 if basic > ₹15,000)
# # # - ESI: 0.75% of gross salary (only if gross ≤ ₹21,000)
# # # - Professional Tax: ₹200/month (if salary > ₹15,000 in Karnataka)
# # # - TDS: Estimate based on annual salary

# # # Return ONLY JSON:
# # # {
# # #   "gross_salary": number,
# # #   "deductions": {
# # #     "pf": number,
# # #     "esi": number,
# # #     "professional_tax": number,
# # #     "tds": number
# # #   },
# # #   "net_salary": number,
# # #   "annual_gross": number,
# # #   "annual_net": number
# # # }
# # # """

# # # COMPLIANCE_MAPPER_PROMPT = """
# # # Validate salary calculations against Indian labor law compliance.

# # # Check for:
# # # - PF contribution limits
# # # - ESI eligibility thresholds  
# # # - Professional tax rates
# # # - Minimum wage compliance

# # # Return ONLY JSON:
# # # {
# # #   "validated_deductions": {
# # #     "pf": number,
# # #     "esi": number,
# # #     "professional_tax": number,
# # #     "tds": number
# # #   },
# # #   "compliance_status": "COMPLIANT" or "NON_COMPLIANT",
# # #   "issues": ["list of compliance issues if any"]
# # # }
# # # """

# # # ANOMALY_DETECTOR_PROMPT = """
# # # Detect any payroll anomalies or irregularities in this salary calculation.

# # # Check for:
# # # - Calculation errors
# # # - Unusual allowance amounts
# # # - Missing mandatory deductions
# # # - Overpayment/underpayment

# # # Return ONLY JSON:
# # # {
# # #   "has_anomalies": boolean,
# # #   "anomalies": [
# # #     {
# # #       "type": "string",
# # #       "description": "string",
# # #       "severity": "LOW|MEDIUM|HIGH"
# # #     }
# # #   ],
# # #   "overall_status": "NORMAL" or "REVIEW_REQUIRED"
# # # }
# # # """

# # # PAYSTUB_GENERATOR_PROMPT = """
# # # Generate a professional HTML payslip for this employee.

# # # Include:
# # # - Company header
# # # - Employee details
# # # - Earnings breakdown
# # # - Deductions breakdown
# # # - Net pay
# # # - Current month/year

# # # Return clean HTML only - no JSON wrapper.
# # # """

# # # # =====================
# # # # UTILITY FUNCTIONS
# # # # =====================
# # # def extract_text_from_pdf(file_path):
# # #     try:
# # #         reader = PdfReader(file_path)
# # #         text = ""
# # #         for page in reader.pages:
# # #             text += page.extract_text() or ""
# # #         return text.strip()
# # #     except:
# # #         return ""

# # # def embed_tax_pdf(file_path):
# # #     try:
# # #         loader = PyPDFLoader(file_path)
# # #         docs = loader.load()
# # #         splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
# # #         chunks = splitter.split_documents(docs)
# # #         vectordb = Chroma.from_documents(chunks, embedding_fn, persist_directory=CHROMA_DIR)
# # #         vectordb.persist()
# # #         return len(chunks)
# # #     except:
# # #         return 0

# # # def query_tax_rules(query, k=3):
# # #     try:
# # #         vectordb = Chroma(persist_directory=CHROMA_DIR, embedding_function=embedding_fn)
# # #         results = vectordb.similarity_search(query, k=k)
# # #         return "\n\n".join([doc.page_content for doc in results])
# # #     except:
# # #         return ""

# # # def llm_call(prompt, content):
# # #     try:
# # #         resp = client.chat.completions.create(
# # #             model="gemini-2.0-flash-exp",
# # #             messages=[
# # #                 {"role": "system", "content": prompt},
# # #                 {"role": "user", "content": content}
# # #             ],
# # #             temperature=0.1,
# # #             max_tokens=4000
# # #         )
        
# # #         msg = resp.choices[0].message
# # #         if hasattr(msg, "content"):
# # #             output = msg.content
# # #         else:
# # #             output = msg.get("content", "")
        
# # #         return (output or "").strip()
# # #     except:
# # #         return ""

# # # def safe_json_loads(text):
# # #     try:
# # #         text = text.strip()
# # #         if text.startswith("```json"):
# # #             text = text[7:]
# # #         if text.startswith("```"):
# # #             text = text[3:]
# # #         if text.endswith("```"):
# # #             text = text[:-3]
# # #         text = text.strip()
        
# # #         return json.loads(text)
# # #     except:
# # #         try:
# # #             return ast.literal_eval(text)
# # #         except:
# # #             return {}

# # # def save_payslip_html_to_pdf(html_content, filename):
# # #     try:
# # #         pdf_path = os.path.join(PAYSPLIP_DIR, filename)
# # #         options = {
# # #             'page-size': 'A4',
# # #             'margin-top': '0.75in',
# # #             'margin-right': '0.75in',
# # #             'margin-bottom': '0.75in',
# # #             'margin-left': '0.75in',
# # #             'encoding': "UTF-8",
# # #             'no-outline': None
# # #         }
# # #         pdfkit.from_string(html_content, pdf_path, options=options)
# # #         return pdf_path
# # #     except:
# # #         return None

# # # def initialize_tax_knowledge():
# # #     """Initialize with comprehensive tax rules for Indian payroll"""
# # #     sample_html = """
# # #     <html><body>
# # #     <h1>Indian Payroll Tax Rules 2024-25</h1>
    
# # #     <h2>Provident Fund (PF)</h2>
# # #     <p>Applicable to organizations with 20+ employees. Employee contribution: 12% of basic salary. 
# # #     Employer contribution: 12% of basic salary. PF contribution is capped at Rs. 15,000 basic salary per month. 
# # #     Maximum employee PF deduction: Rs. 1,800 per month.</p>
    
# # #     <h2>Employee State Insurance (ESI)</h2>
# # #     <p>ESI applies if gross monthly salary is Rs. 21,000 or below. Employee contribution: 0.75% of gross salary. 
# # #     Employer contribution: 3.25% of gross salary. Provides medical benefits to employees.</p>
    
# # #     <h2>Professional Tax</h2>
# # #     <p>State-specific tax. Karnataka: Rs. 200 per month if monthly salary exceeds Rs. 15,000. 
# # #     Maharashtra: Rs. 175 for salary Rs. 5,000-10,000, Rs. 300 for above Rs. 10,000.
# # #     Tamil Nadu: Rs. 208.33 per month if annual salary exceeds Rs. 2.5 lakhs.</p>
    
# # #     <h2>Income Tax (TDS) 2024-25</h2>
# # #     <p>New Tax Regime Slabs:
# # #     Up to Rs. 3,00,000: Nil
# # #     Rs. 3,00,001 to Rs. 7,00,000: 5%
# # #     Rs. 7,00,001 to Rs. 10,00,000: 10%
# # #     Rs. 10,00,001 to Rs. 12,00,000: 15%
# # #     Rs. 12,00,001 to Rs. 15,00,000: 20%
# # #     Above Rs. 15,00,000: 30%</p>
    
# # #     <h2>Gratuity</h2>
# # #     <p>Applicable for organizations with 10+ employees. Payable after 5 years of continuous service. 
# # #     Calculation: (Basic + DA) × 15/26 × Years of Service. Maximum gratuity: Rs. 20,00,000.</p>
    
# # #     <h2>Minimum Wages</h2>
# # #     <p>Varies by state and skill category. Ensure compliance with state minimum wage notifications.
# # #     Karnataka: Rs. 458 per day for unskilled workers (2024).</p>
# # #     </body></html>
# # #     """
    
# # #     try:
# # #         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # #             pdfkit.from_string(sample_html, tmp.name)
# # #             return embed_tax_pdf(tmp.name) > 0
# # #     except:
# # #         return False

# # # # =====================
# # # # AGENTIC AI AGENTS
# # # # =====================
# # # def contract_reader_agent(state):
# # #     text = extract_text_from_pdf(state["contract_path"])
# # #     if not text:
# # #         state["contract_data"] = {}
# # #         return state
    
# # #     parsed_json = llm_call(CONTRACT_READER_PROMPT, text)
# # #     state["contract_data"] = safe_json_loads(parsed_json)
# # #     return state

# # # def salary_breakdown_agent(state):
# # #     if not state.get("contract_data"):
# # #         state["salary_breakdown"] = {}
# # #         return state
    
# # #     parsed_json = llm_call(SALARY_BREAKDOWN_PROMPT, json.dumps(state["contract_data"]))
# # #     state["salary_breakdown"] = safe_json_loads(parsed_json)
# # #     return state

# # # def compliance_mapper_agent(state):
# # #     if not state.get("salary_breakdown"):
# # #         state["compliance_data"] = {}
# # #         return state
    
# # #     tax_rules = query_tax_rules("PF ESI Professional Tax Income Tax rules compliance")
# # #     payload = {
# # #         "salary_data": state["salary_breakdown"],
# # #         "tax_rules": tax_rules
# # #     }
    
# # #     parsed_json = llm_call(COMPLIANCE_MAPPER_PROMPT, json.dumps(payload))
# # #     state["compliance_data"] = safe_json_loads(parsed_json)
# # #     return state

# # # def anomaly_detector_agent(state):
# # #     if not state.get("compliance_data"):
# # #         state["anomalies"] = {}
# # #         return state
    
# # #     analysis_data = {
# # #         "contract_data": state.get("contract_data", {}),
# # #         "salary_breakdown": state.get("salary_breakdown", {}),
# # #         "compliance_data": state["compliance_data"]
# # #     }
    
# # #     parsed_json = llm_call(ANOMALY_DETECTOR_PROMPT, json.dumps(analysis_data))
# # #     state["anomalies"] = safe_json_loads(parsed_json)
# # #     return state

# # # def paystub_generator_agent(state):
# # #     if not all(key in state for key in ["contract_data", "salary_breakdown", "compliance_data"]):
# # #         state["payslip_path"] = None
# # #         return state
    
# # #     employee_name = state["contract_data"].get("employee_name", "Employee")
    
# # #     payslip_data = {
# # #         "employee_details": state["contract_data"],
# # #         "salary_breakdown": state["salary_breakdown"],
# # #         "compliance_data": state["compliance_data"],
# # #         "pay_period": datetime.now().strftime("%B %Y"),
# # #         "generation_date": datetime.now().strftime("%d/%m/%Y"),
# # #         "company_details": {
# # #             "name": "Your Company Name",
# # #             "address": "Company Address"
# # #         }
# # #     }
    
# # #     html_content = llm_call(PAYSTUB_GENERATOR_PROMPT, json.dumps(payslip_data))
    
# # #     if html_content:
# # #         safe_name = "".join(c for c in employee_name if c.isalnum() or c in (' ', '-', '_')).strip()
# # #         filename = f"payslip_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
# # #         pdf_path = save_payslip_html_to_pdf(html_content, filename)
# # #         state["payslip_path"] = pdf_path
        
# # #         # Save to database
# # #         if db:
# # #             try:
# # #                 db.contracts.insert_one({**state["contract_data"], "processed_date": datetime.now()})
# # #                 db.payroll.insert_one({**state["salary_breakdown"], "employee_name": employee_name, "processed_date": datetime.now()})
# # #             except:
# # #                 pass
# # #     else:
# # #         state["payslip_path"] = None
    
# # #     return state

# # # # =====================
# # # # LANGGRAPH WORKFLOW
# # # # =====================
# # # graph = StateGraph(PayrollState)
# # # graph.add_node("contract_reader_agent", contract_reader_agent)
# # # graph.add_node("salary_breakdown_agent", salary_breakdown_agent)
# # # graph.add_node("compliance_mapper_agent", compliance_mapper_agent)
# # # graph.add_node("anomaly_detector_agent", anomaly_detector_agent)
# # # graph.add_node("paystub_generator_agent", paystub_generator_agent)

# # # graph.set_entry_point("contract_reader_agent")
# # # graph.add_edge("contract_reader_agent", "salary_breakdown_agent")
# # # graph.add_edge("salary_breakdown_agent", "compliance_mapper_agent")
# # # graph.add_edge("compliance_mapper_agent", "anomaly_detector_agent")
# # # graph.add_edge("anomaly_detector_agent", "paystub_generator_agent")
# # # graph.add_edge("paystub_generator_agent", END)

# # # workflow = graph.compile()

# # # # =====================
# # # # HR-FOCUSED STREAMLIT UI
# # # # =====================
# # # # def main():
# # # #     st.set_page_config(
# # # #         page_title="HR Payroll Processing System",
# # # #         page_icon="💼",
# # # #         layout="wide"
# # # #     )
    
# # # #     # Header
# # # #     st.title("💼 HR Payroll Processing System")
# # # #     st.markdown("**Process employee contracts and generate payslips automatically**")
    
# # # #     # Initialize session state
# # # #     if 'processing_complete' not in st.session_state:
# # # #         st.session_state.processing_complete = False
# # # #     if 'final_state' not in st.session_state:
# # # #         st.session_state.final_state = None
# # # #     if 'tax_rules_loaded' not in st.session_state:
# # # #         st.session_state.tax_rules_loaded = False
    
# # # #     # Auto-initialize tax rules on first load
# # # #     if not st.session_state.tax_rules_loaded:
# # # #         with st.spinner("Initializing tax knowledge base..."):
# # # #             if initialize_tax_knowledge():
# # # #                 st.session_state.tax_rules_loaded = True
# # # #                 st.success("✅ Tax rules loaded successfully!")
# # # #             else:
# # # #                 st.error("❌ Failed to load tax rules. Some features may not work properly.")
    
# # # #     # Main processing section
# # # #     st.header("📄 Process Employee Contract")
    
# # # #     col1, col2 = st.columns([2, 1])
    
# # # #     with col1:
# # # #         contract_file = st.file_uploader(
# # # #             "Upload Employee Contract PDF", 
# # # #             type=["pdf"],
# # # #             help="Upload the employment contract PDF to process salary calculations"
# # # #         )
    
# # # #     with col2:
# # # #         if st.button("🚀 Process Contract", type="primary", disabled=not contract_file):
# # # #             if contract_file:
# # # #                 st.session_state.processing_complete = False
# # # #                 st.session_state.final_state = None
                
# # # #                 with st.spinner("🤖 Processing contract through AI agents..."):
# # # #                     progress_bar = st.progress(0)
# # # #                     status_text = st.empty()
                    
# # # #                     try:
# # # #                         # Save uploaded file
# # # #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # # #                             tmp.write(contract_file.read())
# # # #                             initial_state = {"contract_path": tmp.name}
                        
# # # #                         # Process through agents
# # # #                         status_text.text("Reading contract details...")
# # # #                         progress_bar.progress(20)
                        
# # # #                         final_state = workflow.invoke(initial_state)
                        
# # # #                         progress_bar.progress(100)
# # # #                         status_text.text("Processing complete!")
                        
# # # #                         st.session_state.final_state = final_state
# # # #                         st.session_state.processing_complete = True
                        
# # # #                         st.success("✅ Contract processed successfully!")
                        
# # # #                     except Exception as e:
# # # #                         st.error(f"❌ Processing failed: {str(e)}")
    
# # # #     # Results section
# # # #     if st.session_state.processing_complete and st.session_state.final_state:
# # # #         final_state = st.session_state.final_state
        
# # # #         st.header("📊 Processing Results")
        
# # # #         # Employee Information Card
# # # #         if final_state.get("contract_data"):
# # # #             contract_data = final_state["contract_data"]
            
# # # #             with st.container():
# # # #                 st.subheader("👤 Employee Information")
                
# # # #                 col1, col2, col3, col4 = st.columns(4)
# # # #                 with col1:
# # # #                     st.metric("Name", contract_data.get("employee_name", "N/A"))
# # # #                 with col2:
# # # #                     st.metric("Employee ID", contract_data.get("employee_id", "N/A"))
# # # #                 with col3:
# # # #                     st.metric("Department", contract_data.get("department", "N/A"))
# # # #                 with col4:
# # # #                     st.metric("Designation", contract_data.get("designation", "N/A"))
        
# # # #         # Salary Overview
# # # #         if final_state.get("salary_breakdown"):
# # # #             salary_data = final_state["salary_breakdown"]
            
# # # #             st.subheader("💰 Salary Breakdown")
            
# # # #             col1, col2, col3 = st.columns(3)
# # # #             with col1:
# # # #                 st.metric(
# # # #                     "Monthly Gross Salary", 
# # # #                     f"₹{salary_data.get('gross_salary', 0):,.2f}",
# # # #                     help="Total salary before deductions"
# # # #                 )
# # # #             with col2:
# # # #                 total_deductions = sum(salary_data.get("deductions", {}).values())
# # # #                 st.metric(
# # # #                     "Total Deductions", 
# # # #                     f"₹{total_deductions:,.2f}",
# # # #                     help="PF, ESI, Professional Tax, TDS"
# # # #                 )
# # # #             with col3:
# # # #                 st.metric(
# # # #                     "Monthly Net Salary", 
# # # #                     f"₹{salary_data.get('net_salary', 0):,.2f}",
# # # #                     help="Take-home salary after deductions"
# # # #                 )
            
# # # #             # Detailed breakdown
# # # #             with st.expander("View Detailed Breakdown"):
# # # #                 col1, col2 = st.columns(2)
                
# # # #                 with col1:
# # # #                     st.write("**Earnings:**")
# # # #                     if contract_data and contract_data.get("salary_structure"):
# # # #                         salary_struct = contract_data["salary_structure"]
# # # #                         for component, amount in salary_struct.items():
# # # #                             if amount > 0:
# # # #                                 st.write(f"• {component.replace('_', ' ').title()}: ₹{amount:,.2f}")
                
# # # #                 with col2:
# # # #                     st.write("**Deductions:**")
# # # #                     deductions = salary_data.get("deductions", {})
# # # #                     for deduction, amount in deductions.items():
# # # #                         if amount > 0:
# # # #                             st.write(f"• {deduction.replace('_', ' ').title()}: ₹{amount:,.2f}")
        
# # # #         # Compliance Status
# # # #         if final_state.get("compliance_data"):
# # # #             compliance_data = final_state["compliance_data"]
            
# # # #             col1, col2 = st.columns(2)
            
# # # #             with col1:
# # # #                 st.subheader("⚖️ Compliance Status")
# # # #                 status = compliance_data.get("compliance_status", "UNKNOWN")
# # # #                 if status == "COMPLIANT":
# # # #                     st.success("✅ All calculations are compliant with Indian labor laws")
# # # #                 else:
# # # #                     st.warning("⚠️ Some compliance issues detected")
# # # #                     issues = compliance_data.get("issues", [])
# # # #                     for issue in issues:
# # # #                         st.write(f"• {issue}")
            
# # # #             # Anomaly Detection
# # # #             if final_state.get("anomalies"):
# # # #                 with col2:
# # # #                     anomaly_data = final_state["anomalies"]
# # # #                     st.subheader("🔍 Quality Check")
                    
# # # #                     if anomaly_data.get("has_anomalies"):
# # # #                         st.warning("⚠️ Issues detected - Review recommended")
# # # #                         for anomaly in anomaly_data.get("anomalies", []):
# # # #                             severity_icons = {"LOW": "🟡", "MEDIUM": "🟠", "HIGH": "🔴"}
# # # #                             icon = severity_icons.get(anomaly.get("severity", "LOW"), "🟡")
# # # #                             st.write(f"{icon} {anomaly.get('description', '')}")
# # # #                     else:
# # # #                         st.success("✅ No issues detected")
        
# # # #         # Annual Projection
# # # #         if salary_data:
# # # #             st.subheader("📈 Annual Projection")
# # # #             col1, col2, col3 = st.columns(3)
# # # #             with col1:
# # # #                 annual_gross = salary_data.get("annual_gross", salary_data.get("gross_salary", 0) * 12)
# # # #                 st.metric("Annual Gross", f"₹{annual_gross:,.2f}")
# # # #             with col2:
# # # #                 annual_deductions = sum(salary_data.get("deductions", {}).values()) * 12
# # # #                 st.metric("Annual Deductions", f"₹{annual_deductions:,.2f}")
# # # #             with col3:
# # # #                 annual_net = salary_data.get("annual_net", salary_data.get("net_salary", 0) * 12)
# # # #                 st.metric("Annual Net", f"₹{annual_net:,.2f}")
        
# # # #         # Download Payslip
# # # #         if final_state.get("payslip_path") and os.path.exists(final_state["payslip_path"]):
# # # #             st.subheader("📄 Generated Payslip")
            
# # # #             col1, col2 = st.columns([3, 1])
# # # #             with col1:
# # # #                 st.info("Payslip has been generated and is ready for download")
# # # #             with col2:
# # # #                 with open(final_state["payslip_path"], "rb") as f:
# # # #                     st.download_button(
# # # #                         label="📥 Download Payslip",
# # # #                         data=f.read(),
# # # #                         file_name=os.path.basename(final_state["payslip_path"]),
# # # #                         mime="application/pdf",
# # # #                         type="primary"
# # # #                     )
    
# # # #     else:
# # # #         # Welcome message when no processing has been done
# # # #         st.info("👆 Upload an employee contract PDF to get started with payroll processing")
        
# # # #         # Recent processing history (if available)
# # # #         if db:
# # # #             try:
# # # #                 recent_contracts = list(db.contracts.find().sort("processed_date", -1).limit(5))
# # # #                 if recent_contracts:
# # # #                     st.subheader("📋 Recent Processed Contracts")
# # # #                     for contract in recent_contracts:
# # # #                         processed_date = contract.get("processed_date", datetime.now()).strftime("%d/%m/%Y %I:%M %p")
# # # #                         st.write(f"• **{contract.get('employee_name', 'Unknown')}** - {contract.get('department', 'N/A')} - *Processed: {processed_date}*")
# # # #             except:
# # # #                 pass
    
# # # #     # Footer
# # # #     st.markdown("---")
# # # #     st.markdown("*Powered by Agentic AI • Compliant with Indian Labor Laws*")

# # # def main():
# # #     st.set_page_config(
# # #         page_title="HR Payroll Processing System",
# # #         page_icon="💼",
# # #         layout="wide"
# # #     )
    
# # #     # Header
# # #     st.title("💼 HR Payroll Processing System")
# # #     st.markdown("**Process employee contracts and generate payslips automatically**")
    
# # #     # Initialize session state
# # #     if 'processing_complete' not in st.session_state:
# # #         st.session_state.processing_complete = False
# # #     if 'final_state' not in st.session_state:
# # #         st.session_state.final_state = None
# # #     if 'tax_rules_loaded' not in st.session_state:
# # #         st.session_state.tax_rules_loaded = False
    
# # #     # Tax Rule PDF Upload Section
# # #     st.header("📚 Initialize Tax Rules (RAG)")
# # #     tax_rule_file = st.file_uploader(
# # #         "Upload Tax Rule PDF", 
# # #         type=["pdf"],
# # #         key="tax_rule_uploader",
# # #         help="Upload the Tax Rule PDF to initialize the RAG system for compliance checks"
# # #     )
    
# # #     if tax_rule_file:
# # #         with st.spinner("🤖 Processing Tax Rule PDF for RAG..."):
# # #             try:
# # #                 # Save uploaded Tax Rule PDF
# # #                 with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # #                     tmp.write(tax_rule_file.read())
# # #                     success = embed_tax_pdf(tmp.name)
                
# # #                 if success:
# # #                     st.session_state.tax_rules_loaded = True
# # #                     st.success("✅ Tax Rule PDF processed successfully! RAG system initialized.")
# # #                 else:
# # #                     st.error("❌ Failed to process Tax Rule PDF. Compliance checks may be affected.")
# # #             except Exception as e:
# # #                 st.error(f"❌ Error processing Tax Rule PDF: {str(e)}")
    
# # #     # Employee Contract PDF Upload Section
# # #     st.header("📄 Process Employee Contract")
# # #     col1, col2 = st.columns([2, 1])
    
# # #     with col1:
# # #         contract_file = st.file_uploader(
# # #             "Upload Employee Contract PDF", 
# # #             type=["pdf"],
# # #             key="contract_uploader",
# # #             help="Upload the employment contract PDF to process salary calculations"
# # #         )
    
# # #     with col2:
# # #         if st.button("🚀 Process Contract", type="primary", disabled=not contract_file or not st.session_state.tax_rules_loaded):
# # #             if contract_file:
# # #                 st.session_state.processing_complete = False
# # #                 st.session_state.final_state = None
                
# # #                 with st.spinner("🤖 Processing contract through AI agents..."):
# # #                     progress_bar = st.progress(0)
# # #                     status_text = st.empty()
                    
# # #                     try:
# # #                         # Save uploaded Contract PDF
# # #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # #                             tmp.write(contract_file.read())
# # #                             initial_state = {"contract_path": tmp.name}
                        
# # #                         # Process through agents
# # #                         status_text.text("Reading contract details...")
# # #                         progress_bar.progress(20)
                        
# # #                         final_state = workflow.invoke(initial_state)
                        
# # #                         progress_bar.progress(100)
# # #                         status_text.text("Processing complete!")
                        
# # #                         st.session_state.final_state = final_state
# # #                         st.session_state.processing_complete = True
                        
# # #                         st.success("✅ Contract processed successfully!")
                        
# # #                     except Exception as e:
# # #                         st.error(f"❌ Processing failed: {str(e)}")
    
# # #     # Results section
# # #     if st.session_state.processing_complete and st.session_state.final_state:
# # #         final_state = st.session_state.final_state
        
# # #         st.header("📊 Processing Results")
        
# # #         # Employee Information Card
# # #         if final_state.get("contract_data"):
# # #             contract_data = final_state["contract_data"]
            
# # #             with st.container():
# # #                 st.subheader("👤 Employee Information")
                
# # #                 col1, col2, col3, col4 = st.columns(4)
# # #                 with col1:
# # #                     st.metric("Name", contract_data.get("employee_name", "N/A"))
# # #                 with col2:
# # #                     st.metric("Employee ID", contract_data.get("employee_id", "N/A"))
# # #                 with col3:
# # #                     st.metric("Department", contract_data.get("department", "N/A"))
# # #                 with col4:
# # #                     st.metric("Designation", contract_data.get("designation", "N/A"))
        
# # #         # Salary Overview
# # #         if final_state.get("salary_breakdown"):
# # #             salary_data = final_state["salary_breakdown"]
            
# # #             st.subheader("💰 Salary Breakdown")
            
# # #             col1, col2, col3 = st.columns(3)
# # #             with col1:
# # #                 st.metric(
# # #                     "Monthly Gross Salary", 
# # #                     f"₹{salary_data.get('gross_salary', 0):,.2f}",
# # #                     help="Total salary before deductions"
# # #                 )
# # #             with col2:
# # #                 total_deductions = sum(salary_data.get("deductions", {}).values())
# # #                 st.metric(
# # #                     "Total Deductions", 
# # #                     f"₹{total_deductions:,.2f}",
# # #                     help="PF, ESI, Professional Tax, TDS"
# # #                 )
# # #             with col3:
# # #                 st.metric(
# # #                     "Monthly Net Salary", 
# # #                     f"₹{salary_data.get('net_salary', 0):,.2f}",
# # #                     help="Take-home salary after deductions"
# # #                 )
            
# # #             # Detailed breakdown
# # #             with st.expander("View Detailed Breakdown"):
# # #                 col1, col2 = st.columns(2)
                
# # #                 with col1:
# # #                     st.write("**Earnings:**")
# # #                     if contract_data and contract_data.get("salary_structure"):
# # #                         salary_struct = contract_data["salary_structure"]
# # #                         for component, amount in salary_struct.items():
# # #                             if amount > 0:
# # #                                 st.write(f"• {component.replace('_', ' ').title()}: ₹{amount:,.2f}")
                
# # #                 with col2:
# # #                     st.write("**Deductions:**")
# # #                     deductions = salary_data.get("deductions", {})
# # #                     for deduction, amount in deductions.items():
# # #                         if amount > 0:
# # #                             st.write(f"• {deduction.replace('_', ' ').title()}: ₹{amount:,.2f}")
        
# # #         # Compliance Status
# # #         if final_state.get("compliance_data"):
# # #             compliance_data = final_state["compliance_data"]
            
# # #             col1, col2 = st.columns(2)
            
# # #             with col1:
# # #                 st.subheader("⚖️ Compliance Status")
# # #                 status = compliance_data.get("compliance_status", "UNKNOWN")
# # #                 if status == "COMPLIANT":
# # #                     st.success("✅ All calculations are compliant with Indian labor laws")
# # #                 else:
# # #                     st.warning("⚠️ Some compliance issues detected")
# # #                     issues = compliance_data.get("issues", [])
# # #                     for issue in issues:
# # #                         st.write(f"• {issue}")
            
# # #             # Anomaly Detection
# # #             if final_state.get("anomalies"):
# # #                 with col2:
# # #                     anomaly_data = final_state["anomalies"]
# # #                     st.subheader("🔍 Quality Check")
                    
# # #                     if anomaly_data.get("has_anomalies"):
# # #                         st.warning("⚠️ Issues detected - Review recommended")
# # #                         for anomaly in anomaly_data.get("anomalies", []):
# # #                             severity_icons = {"LOW": "🟡", "MEDIUM": "🟠", "HIGH": "🔴"}
# # #                             icon = severity_icons.get(anomaly.get("severity", "LOW"), "🟡")
# # #                             st.write(f"{icon} {anomaly.get('description', '')}")
# # #                     else:
# # #                         st.success("✅ No issues detected")
        
# # #         # Annual Projection
# # #         if salary_data:
# # #             st.subheader("📈 Annual Projection")
# # #             col1, col2, col3 = st.columns(3)
# # #             with col1:
# # #                 annual_gross = salary_data.get("annual_gross", salary_data.get("gross_salary", 0) * 12)
# # #                 st.metric("Annual Gross", f"₹{annual_gross:,.2f}")
# # #             with col2:
# # #                 annual_deductions = sum(salary_data.get("deductions", {}).values()) * 12
# # #                 st.metric("Annual Deductions", f"₹{annual_deductions:,.2f}")
# # #             with col3:
# # #                 annual_net = salary_data.get("annual_net", salary_data.get("net_salary", 0) * 12)
# # #                 st.metric("Annual Net", f"₹{annual_net:,.2f}")
        
# # #         # Download Payslip
# # #         if final_state.get("payslip_path") and os.path.exists(final_state["payslip_path"]):
# # #             st.subheader("📄 Generated Payslip")
            
# # #             col1, col2 = st.columns([3, 1])
# # #             with col1:
# # #                 st.info("Payslip has been generated and is ready for download")
# # #             with col2:
# # #                 with open(final_state["payslip_path"], "rb") as f:
# # #                     st.download_button(
# # #                         label="📥 Download Payslip",
# # #                         data=f.read(),
# # #                         file_name=os.path.basename(final_state["payslip_path"]),
# # #                         mime="application/pdf",
# # #                         type="primary"
# # #                     )
    
# # #     else:
# # #         # Welcome message when no processing has been done
# # #         st.info("👆 Upload a Tax Rule PDF to initialize the RAG system, then upload an Employee Contract PDF and click Process to generate payroll details")
        
# # #         # Recent processing history (if available)
# # #         if db:
# # #             try:
# # #                 recent_contracts = list(db.contracts.find().sort("processed_date", -1).limit(5))
# # #                 if recent_contracts:
# # #                     st.subheader("📋 Recent Processed Contracts")
# # #                     for contract in recent_contracts:
# # #                         processed_date = contract.get("processed_date", datetime.now()).strftime("%d/%m/%Y %I:%M %p")
# # #                         st.write(f"• **{contract.get('employee_name', 'Unknown')}** - {contract.get('department', 'N/A')} - *Processed: {processed_date}*")
# # #             except:
# # #                 pass
    
# # #     # Footer
# # #     st.markdown("---")
# # #     st.markdown("*Powered by Agentic AI • Compliant with Indian Labor Laws*")

# # # if __name__ == "__main__":
# # #     main()

# # # # # app.py
# # # # import os
# # # # import io
# # # # import json
# # # # import base64
# # # # import pdfkit
# # # # import tempfile
# # # # import streamlit as st
# # # # import logging
# # # # from datetime import datetime
# # # # from pymongo import MongoClient
# # # # from openai import OpenAI
# # # # from PyPDF2 import PdfReader
# # # # from langchain_community.vectorstores import Chroma
# # # # from langchain_community.document_loaders import PyPDFLoader
# # # # from langchain_text_splitters import RecursiveCharacterTextSplitter
# # # # from langchain_google_genai import GoogleGenerativeAIEmbeddings
# # # # from langgraph.graph import StateGraph, END
# # # # import asyncio
# # # # from typing import TypedDict, Optional, Dict, Any, List
# # # # from dotenv import load_dotenv
# # # # import ast
# # # # import traceback

# # # # # Load environment variables
# # # # load_dotenv()
# # # # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # # # # Configure logging for debugging
# # # # logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# # # # logger = logging.getLogger(__name__)

# # # # # Streamlit logging configuration
# # # # if 'logger_handler' not in st.session_state:
# # # #     st.session_state.logger_handler = []

# # # # def log_to_streamlit(message, level="INFO"):
# # # #     """Custom logger that displays in Streamlit interface"""
# # # #     timestamp = datetime.now().strftime("%H:%M:%S")
# # # #     log_entry = f"[{timestamp}] {level}: {message}"
# # # #     st.session_state.logger_handler.append(log_entry)
# # # #     logger.info(message)

# # # # # Handle asyncio event loop
# # # # try:
# # # #     asyncio.get_running_loop()
# # # # except RuntimeError:
# # # #     asyncio.set_event_loop(asyncio.new_event_loop())

# # # # class PayrollState(TypedDict):
# # # #     contract_path: str
# # # #     contract_data: Optional[Dict[str, Any]]
# # # #     salary_breakdown: Optional[Dict[str, Any]]
# # # #     compliance_data: Optional[Dict[str, Any]]
# # # #     anomalies: Optional[Dict[str, Any]]
# # # #     payslip_path: Optional[str]
# # # #     agent_communications: Optional[List[Dict[str, Any]]]  # Track agent communications
# # # #     verbose: Optional[bool]

# # # # # =====================
# # # # # CONFIGURATION
# # # # # =====================
# # # # MONGO_URI = "mongodb+srv://Naveen:Qwe%401234567890@cluster0.u8t9s.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# # # # DB_NAME = "payroll_db"
# # # # CHROMA_DIR = "./chroma_db"
# # # # PAYSPLIP_DIR = "./payslips"
# # # # os.makedirs(PAYSPLIP_DIR, exist_ok=True)
# # # # os.makedirs(CHROMA_DIR, exist_ok=True)

# # # # # MongoDB connection with error handling
# # # # try:
# # # #     mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
# # # #     db = mongo_client[DB_NAME]
# # # #     # Test connection
# # # #     mongo_client.admin.command('ping')
# # # #     log_to_streamlit("✅ MongoDB connection established", "SUCCESS")
# # # # except Exception as e:
# # # #     log_to_streamlit(f"❌ MongoDB connection failed: {str(e)}", "ERROR")
# # # #     db = None

# # # # # OpenAI-compatible Gemini client
# # # # try:
# # # #     client = OpenAI(
# # # #         api_key=GEMINI_API_KEY,
# # # #         base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# # # #     )
# # # #     log_to_streamlit("✅ Gemini API client initialized", "SUCCESS")
# # # # except Exception as e:
# # # #     log_to_streamlit(f"❌ Gemini API client initialization failed: {str(e)}", "ERROR")
# # # #     client = None

# # # # # ChromaDB embeddings
# # # # try:
# # # #     embedding_fn = GoogleGenerativeAIEmbeddings(
# # # #         model="models/embedding-001",
# # # #         google_api_key=GEMINI_API_KEY
# # # #     )
# # # #     log_to_streamlit("✅ Embedding function initialized", "SUCCESS")
# # # # except Exception as e:
# # # #     log_to_streamlit(f"❌ Embedding function initialization failed: {str(e)}", "ERROR")
# # # #     embedding_fn = None

# # # # # =====================
# # # # # ENHANCED PROMPTS FOR AGENTS
# # # # # =====================
# # # # CONTRACT_READER_PROMPT = """
# # # # You are an AI payroll contract parser with expert knowledge in employment contracts and salary structures.

# # # # ROLE: Contract Reading Agent
# # # # TASK: Extract structured salary and statutory details from the given employment contract text.

# # # # INSTRUCTIONS:
# # # # 1. Carefully read and analyze the entire contract text
# # # # 2. Extract ALL salary components mentioned
# # # # 3. Identify statutory requirements and compliance details
# # # # 4. Return ONLY valid JSON with the following structure:

# # # # {
# # # #   "employee_name": "string",
# # # #   "employee_id": "string or null",
# # # #   "joining_date": "YYYY-MM-DD or null",
# # # #   "location": "string",
# # # #   "department": "string or null",
# # # #   "designation": "string or null",
# # # #   "salary_structure": {
# # # #     "basic": "number",
# # # #     "hra": "number", 
# # # #     "lta": "number",
# # # #     "conveyance": "number",
# # # #     "medical": "number",
# # # #     "special_allowance": "number",
# # # #     "bonus": "number",
# # # #     "variable_pay": "number",
# # # #     "other_allowances": "number"
# # # #   },
# # # #   "statutory_components": {
# # # #     "pf_capped": "boolean",
# # # #     "gratuity_applicable": "boolean", 
# # # #     "esi_applicable": "boolean",
# # # #     "professional_tax_applicable": "boolean",
# # # #     "income_tax_regime": "old or new or null"
# # # #   },
# # # #   "additional_benefits": ["list of strings"],
# # # #   "proration_rules": "string or null",
# # # #   "region_specific_clauses": ["list of strings"],
# # # #   "contract_type": "permanent or contract or probation",
# # # #   "notice_period": "string or null"
# # # # }

# # # # CRITICAL REQUIREMENTS:
# # # # - Read monetary amounts as numbers without commas or currency symbols
# # # # - If a salary component is not mentioned, set it to 0 (not null)
# # # # - If other information is missing, set it to null
# # # # - Ensure all amounts are in INR per month
# # # # - Output ONLY valid JSON, no additional text or commentary
# # # # """

# # # # SALARY_BREAKDOWN_PROMPT = """
# # # # You are a salary computation expert specializing in Indian payroll calculations.

# # # # ROLE: Salary Breakdown Agent
# # # # TASK: Calculate comprehensive monthly salary breakdown with accurate deductions.

# # # # INSTRUCTIONS:
# # # # 1. Calculate gross salary from all salary components
# # # # 2. Apply standard deduction calculations based on Indian labor laws
# # # # 3. Provide detailed justification for each calculation
# # # # 4. Consider employee eligibility for each deduction

# # # # CALCULATION RULES:
# # # # - PF: 12% of basic salary (capped at ₹1,800 if basic > ₹15,000)
# # # # - ESI: 0.75% of gross salary (only if gross ≤ ₹21,000)
# # # # - Professional Tax: Based on location (Karnataka: ₹200 if salary > ₹15,000)
# # # # - TDS: Estimated based on annual salary projection

# # # # Return ONLY this JSON structure:
# # # # {
# # # #   "gross_salary": "number",
# # # #   "deductions": {
# # # #     "pf": "number",
# # # #     "esi": "number", 
# # # #     "professional_tax": "number",
# # # #     "tds": "number",
# # # #     "other": "number"
# # # #   },
# # # #   "net_salary": "number",
# # # #   "calculation_justification": {
# # # #     "gross_calculation": "explanation",
# # # #     "pf": "calculation explanation",
# # # #     "esi": "calculation explanation", 
# # # #     "professional_tax": "calculation explanation",
# # # #     "tds": "calculation explanation",
# # # #     "other": "calculation explanation"
# # # #   },
# # # #   "annual_projection": {
# # # #     "gross_annual": "number",
# # # #     "total_deductions_annual": "number",
# # # #     "net_annual": "number"
# # # #   }
# # # # }
# # # # """

# # # # COMPLIANCE_MAPPER_PROMPT = """
# # # # You are a payroll compliance validation expert with deep knowledge of Indian labor laws and tax regulations.

# # # # ROLE: Compliance Mapper Agent  
# # # # TASK: Validate salary calculations against official tax and compliance rules, then provide corrected calculations.

# # # # INSTRUCTIONS:
# # # # 1. Review the current salary breakdown and deductions
# # # # 2. Cross-reference with provided official tax rules
# # # # 3. Identify any compliance violations or calculation errors
# # # # 4. Provide corrected deductions with detailed explanations
# # # # 5. Flag any regulatory non-compliance issues

# # # # VALIDATION AREAS:
# # # # - PF contribution limits and eligibility
# # # # - ESI threshold compliance
# # # # - Professional Tax regional variations
# # # # - Income Tax deduction accuracy
# # # # - Minimum wage compliance
# # # # - Overtime calculations (if applicable)

# # # # Return ONLY this JSON structure:
# # # # {
# # # #   "validated_deductions": {
# # # #     "pf": "number",
# # # #     "esi": "number",
# # # #     "professional_tax": "number", 
# # # #     "tds": "number",
# # # #     "other": "number"
# # # #   },
# # # #   "corrections_made": [
# # # #     {
# # # #       "component": "string",
# # # #       "original_value": "number",
# # # #       "corrected_value": "number", 
# # # #       "reason": "detailed explanation"
# # # #     }
# # # #   ],
# # # #   "compliance_status": {
# # # #     "overall_compliant": "boolean",
# # # #     "pf_compliant": "boolean",
# # # #     "esi_compliant": "boolean",
# # # #     "tax_compliant": "boolean",
# # # #     "minimum_wage_compliant": "boolean"
# # # #   },
# # # #   "compliance_notes": ["list of compliance observations"],
# # # #   "regulatory_warnings": ["list of potential issues"],
# # # #   "recommended_actions": ["list of recommended actions"]
# # # # }
# # # # """

# # # # ANOMALY_DETECTOR_PROMPT = """
# # # # You are a payroll anomaly detection specialist with expertise in identifying payroll irregularities and fraud patterns.

# # # # ROLE: Anomaly Detection Agent
# # # # TASK: Analyze payroll calculations for anomalies, inconsistencies, and potential issues.

# # # # INSTRUCTIONS:
# # # # 1. Compare salary components against industry standards
# # # # 2. Identify unusual patterns in deductions or allowances
# # # # 3. Check for mathematical inconsistencies
# # # # 4. Flag potential compliance risks
# # # # 5. Assess reasonableness of total compensation

# # # # ANOMALY CATEGORIES:
# # # # - Overpayment/Underpayment
# # # # - Missing mandatory deductions
# # # # - Unusually high allowances
# # # # - Calculation errors
# # # # - Compliance violations
# # # # - Fraud indicators

# # # # Return ONLY this JSON structure:
# # # # {
# # # #   "anomalies_detected": "boolean",
# # # #   "risk_score": "number (0-10 scale)",
# # # #   "anomalies": [
# # # #     {
# # # #       "type": "string",
# # # #       "category": "overpayment|underpayment|missing_deduction|unusual_allowance|calculation_error|compliance|fraud",
# # # #       "description": "detailed description",
# # # #       "severity": "low|medium|high|critical",
# # # #       "affected_component": "string",
# # # #       "recommended_action": "string",
# # # #       "financial_impact": "number"
# # # #     }
# # # #   ],
# # # #   "summary": {
# # # #     "total_anomalies": "number",
# # # #     "critical_issues": "number",
# # # #     "estimated_financial_impact": "number",
# # # #     "requires_immediate_attention": "boolean"
# # # #   },
# # # #   "benchmarking": {
# # # #     "salary_percentile": "string",
# # # #     "industry_comparison": "above|below|within_range",
# # # #     "regional_comparison": "above|below|within_range"
# # # #   }
# # # # }
# # # # """

# # # # PAYSTUB_GENERATOR_PROMPT = """
# # # # You are a professional payslip generator creating compliant Indian payslips.

# # # # ROLE: Payslip Generation Agent
# # # # TASK: Generate a professional, compliant HTML payslip document.

# # # # INSTRUCTIONS:
# # # # 1. Create a clean, professional payslip layout
# # # # 2. Include all required statutory information
# # # # 3. Ensure compliance with Indian payroll documentation standards
# # # # 4. Make it printer-friendly and PDF-ready
# # # # 5. Include proper formatting and company branding placeholder

# # # # REQUIRED ELEMENTS:
# # # # - Company header with logo placeholder
# # # # - Employee details section
# # # # - Earnings breakdown table
# # # # - Deductions breakdown table  
# # # # - Net pay calculation
# # # # - Statutory compliance statements
# # # # - Payment date and period
# # # # - Digital signature placeholder

# # # # Generate clean HTML with embedded CSS. No external dependencies.
# # # # Return ONLY the HTML content - no JSON wrapper or additional text.
# # # # """

# # # # # =====================
# # # # # ENHANCED UTILITY FUNCTIONS
# # # # # =====================
# # # # def extract_text_from_pdf(file_path):
# # # #     """Extract text from PDF with enhanced error handling"""
# # # #     try:
# # # #         log_to_streamlit(f"📄 Extracting text from PDF: {file_path}")
# # # #         reader = PdfReader(file_path)
# # # #         text = ""
# # # #         for i, page in enumerate(reader.pages):
# # # #             page_text = page.extract_text() or ""
# # # #             text += page_text
# # # #             log_to_streamlit(f"📄 Extracted {len(page_text)} characters from page {i+1}")
        
# # # #         log_to_streamlit(f"✅ Successfully extracted {len(text)} total characters from PDF")
# # # #         return text.strip()
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Error extracting text from PDF: {str(e)}", "ERROR")
# # # #         return ""

# # # # def embed_tax_pdf(file_path):
# # # #     """Embed tax rules into ChromaDB with enhanced logging"""
# # # #     try:
# # # #         log_to_streamlit(f"🔄 Starting tax PDF embedding: {file_path}")
# # # #         loader = PyPDFLoader(file_path)
# # # #         docs = loader.load()
# # # #         log_to_streamlit(f"📚 Loaded {len(docs)} documents from PDF")
        
# # # #         splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
# # # #         chunks = splitter.split_documents(docs)
# # # #         log_to_streamlit(f"✂️ Split into {len(chunks)} chunks")
        
# # # #         vectordb = Chroma.from_documents(chunks, embedding_fn, persist_directory=CHROMA_DIR)
# # # #         vectordb.persist()
# # # #         log_to_streamlit(f"✅ Successfully embedded {len(chunks)} chunks into ChromaDB")
# # # #         return len(chunks)
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Error embedding tax PDF: {str(e)}", "ERROR")
# # # #         return 0

# # # # def query_tax_rules(query, k=3):
# # # #     """Query tax rules from ChromaDB with logging"""
# # # #     try:
# # # #         log_to_streamlit(f"🔍 Querying tax rules: {query}")
# # # #         vectordb = Chroma(persist_directory=CHROMA_DIR, embedding_function=embedding_fn)
# # # #         results = vectordb.similarity_search(query, k=k)
        
# # # #         combined_content = "\n\n".join([doc.page_content for doc in results])
# # # #         log_to_streamlit(f"✅ Retrieved {len(results)} relevant tax rule chunks")
# # # #         return combined_content
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Error querying tax rules: {str(e)}", "ERROR")
# # # #         return ""

# # # # def llm_call(prompt, content, agent_name="Unknown", state=None):
# # # #     """Enhanced LLM call with comprehensive logging and error handling"""
# # # #     try:
# # # #         log_to_streamlit(f"🤖 {agent_name} - Making LLM call")
# # # #         log_to_streamlit(f"📤 {agent_name} - Prompt length: {len(prompt)} chars")
# # # #         log_to_streamlit(f"📤 {agent_name} - Content length: {len(content)} chars")
        
# # # #         if state and state.get("verbose", False):
# # # #             log_to_streamlit(f"🔍 {agent_name} - PROMPT:\n{prompt[:500]}...")
# # # #             log_to_streamlit(f"🔍 {agent_name} - CONTENT:\n{content[:500]}...")
        
# # # #         resp = client.chat.completions.create(
# # # #             model="gemini-2.0-flash-exp",
# # # #             messages=[
# # # #                 {"role": "system", "content": prompt},
# # # #                 {"role": "user", "content": content}
# # # #             ],
# # # #             temperature=0.1,
# # # #             max_tokens=4000
# # # #         )
        
# # # #         msg = resp.choices[0].message
# # # #         if hasattr(msg, "content"):
# # # #             output = msg.content
# # # #         else:
# # # #             output = msg.get("content", "")
        
# # # #         output = (output or "").strip()
# # # #         log_to_streamlit(f"📥 {agent_name} - Response length: {len(output)} chars")
        
# # # #         if state and state.get("verbose", False):
# # # #             log_to_streamlit(f"🔍 {agent_name} - RESPONSE:\n{output[:500]}...")
        
# # # #         # Track agent communication
# # # #         if state and "agent_communications" not in state:
# # # #             state["agent_communications"] = []
        
# # # #         if state:
# # # #             state["agent_communications"].append({
# # # #                 "agent": agent_name,
# # # #                 "timestamp": datetime.now().isoformat(),
# # # #                 "prompt_preview": prompt[:200] + "...",
# # # #                 "content_preview": content[:200] + "...", 
# # # #                 "response_preview": output[:200] + "...",
# # # #                 "response_length": len(output)
# # # #             })
        
# # # #         log_to_streamlit(f"✅ {agent_name} - LLM call completed successfully")
# # # #         return output
        
# # # #     except Exception as e:
# # # #         error_msg = f"❌ {agent_name} - LLM call failed: {str(e)}"
# # # #         log_to_streamlit(error_msg, "ERROR")
# # # #         log_to_streamlit(f"❌ {agent_name} - Traceback: {traceback.format_exc()}", "ERROR")
# # # #         return ""

# # # # def safe_json_loads(text, agent_name="Unknown"):
# # # #     """Safe JSON parsing with enhanced error handling and logging"""
# # # #     try:
# # # #         log_to_streamlit(f"🔧 {agent_name} - Parsing JSON response")
        
# # # #         # Clean the text first
# # # #         text = text.strip()
        
# # # #         # Remove markdown code blocks if present
# # # #         if text.startswith("```json"):
# # # #             text = text[7:]
# # # #         if text.startswith("```"):
# # # #             text = text[3:]
# # # #         if text.endswith("```"):
# # # #             text = text[:-3]
        
# # # #         text = text.strip()
        
# # # #         # Try standard JSON parsing
# # # #         result = json.loads(text)
# # # #         log_to_streamlit(f"✅ {agent_name} - Successfully parsed JSON")
# # # #         return result
        
# # # #     except json.JSONDecodeError as e:
# # # #         log_to_streamlit(f"⚠️ {agent_name} - JSON decode failed, trying ast.literal_eval", "WARNING")
# # # #         try:
# # # #             result = ast.literal_eval(text)
# # # #             log_to_streamlit(f"✅ {agent_name} - Successfully parsed with ast.literal_eval")
# # # #             return result
# # # #         except Exception as e2:
# # # #             log_to_streamlit(f"❌ {agent_name} - Both JSON and ast parsing failed", "ERROR")
# # # #             log_to_streamlit(f"❌ {agent_name} - Original text:\n{text[:500]}...", "ERROR")
# # # #             return {}

# # # # def save_payslip_html_to_pdf(html_content, filename):
# # # #     """Save HTML payslip as PDF with error handling"""
# # # #     try:
# # # #         log_to_streamlit(f"📄 Generating PDF: {filename}")
# # # #         pdf_path = os.path.join(PAYSPLIP_DIR, filename)
        
# # # #         # Configure pdfkit options for better PDF generation
# # # #         options = {
# # # #             'page-size': 'A4',
# # # #             'margin-top': '0.75in',
# # # #             'margin-right': '0.75in',
# # # #             'margin-bottom': '0.75in',
# # # #             'margin-left': '0.75in',
# # # #             'encoding': "UTF-8",
# # # #             'no-outline': None
# # # #         }
        
# # # #         pdfkit.from_string(html_content, pdf_path, options=options)
# # # #         log_to_streamlit(f"✅ PDF generated successfully: {pdf_path}")
# # # #         return pdf_path
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Error generating PDF: {str(e)}", "ERROR")
# # # #         return None

# # # # def load_sample_tax_rules():
# # # #     """Load comprehensive sample tax rules for testing"""
# # # #     sample_html = """
# # # #     <html>
# # # #     <head><title>Indian Tax Rules 2024-25</title></head>
# # # #     <body>
# # # #     <h1>Provident Fund (PF) Rules</h1>
# # # #     <p>PF is mandatory for organizations with 20+ employees. Employee contribution: 12% of basic salary. 
# # # #     Employer contribution: 12% of basic salary. PF is capped at Rs. 15,000 basic salary per month. 
# # # #     Maximum PF deduction: Rs. 1,800 per month.</p>
    
# # # #     <h1>Employee State Insurance (ESI) Rules</h1>
# # # #     <p>ESI applies if gross monthly salary is Rs. 21,000 or below. Employee contribution: 0.75% of gross salary. 
# # # #     Employer contribution: 3.25% of gross salary.</p>
    
# # # #     <h1>Professional Tax Rules</h1>
# # # #     <p>Karnataka Professional Tax: Rs. 200 per month if monthly salary exceeds Rs. 15,000. 
# # # #     Maharashtra: Rs. 175 for salary Rs. 5,000-10,000, Rs. 300 for above Rs. 10,000.</p>
    
# # # #     <h1>Income Tax Slabs 2024-25</h1>
# # # #     <p>New Tax Regime: 0-Rs.3,00,000: 0%, Rs.3,00,001-Rs.7,00,000: 5%, Rs.7,00,001-Rs.10,00,000: 10%, 
# # # #     Rs.10,00,001-Rs.12,00,000: 15%, Rs.12,00,001-Rs.15,00,000: 20%, Above Rs.15,00,000: 30%</p>
    
# # # #     <h1>Gratuity Rules</h1>
# # # #     <p>Applicable for organizations with 10+ employees. Payable after 5 years of service. 
# # # #     Calculation: (Basic + DA) * 15/26 * Years of Service. Maximum: Rs. 20,00,000.</p>
# # # #     </body>
# # # #     </html>
# # # #     """
    
# # # #     try:
# # # #         log_to_streamlit("📚 Loading sample tax rules")
# # # #         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # # #             pdfkit.from_string(sample_html, tmp.name)
# # # #             chunks = embed_tax_pdf(tmp.name)
# # # #         log_to_streamlit(f"✅ Sample tax rules loaded with {chunks} chunks")
# # # #         return chunks
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Error loading sample tax rules: {str(e)}", "ERROR")
# # # #         return 0

# # # # # =====================
# # # # # ENHANCED LANGGRAPH AGENTS
# # # # # =====================
# # # # def contract_reader_agent(state):
# # # #     """Enhanced Contract Reader Agent with comprehensive logging"""
# # # #     log_to_streamlit("🚀 AGENT: Contract Reader Agent Started", "AGENT")
    
# # # #     try:
# # # #         # Extract text from contract
# # # #         text = extract_text_from_pdf(state["contract_path"])
# # # #         if not text:
# # # #             log_to_streamlit("❌ No text extracted from contract PDF", "ERROR")
# # # #             state["contract_data"] = {}
# # # #             return state
        
# # # #         log_to_streamlit(f"📄 Contract text preview: {text[:200]}...")
        
# # # #         # Call LLM to parse contract
# # # #         parsed_json = llm_call(CONTRACT_READER_PROMPT, text, "Contract Reader", state)
        
# # # #         if not parsed_json:
# # # #             log_to_streamlit("❌ No response from LLM", "ERROR")
# # # #             state["contract_data"] = {}
# # # #             return state
            
# # # #         # Parse JSON response
# # # #         contract_data = safe_json_loads(parsed_json, "Contract Reader")
# # # #         state["contract_data"] = contract_data
        
# # # #         log_to_streamlit(f"✅ Contract parsing completed. Employee: {contract_data.get('employee_name', 'Unknown')}", "SUCCESS")
# # # #         log_to_streamlit("🏁 AGENT: Contract Reader Agent Completed", "AGENT")
        
# # # #         return state
        
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Contract Reader Agent failed: {str(e)}", "ERROR")
# # # #         state["contract_data"] = {}
# # # #         return state

# # # # def salary_breakdown_agent(state):
# # # #     """Enhanced Salary Breakdown Agent with detailed calculations"""
# # # #     log_to_streamlit("🚀 AGENT: Salary Breakdown Agent Started", "AGENT")
    
# # # #     try:
# # # #         if not state.get("contract_data"):
# # # #             log_to_streamlit("❌ No contract data available for salary breakdown", "ERROR")
# # # #             state["salary_breakdown"] = {}
# # # #             return state
        
# # # #         contract_data = state["contract_data"]
# # # #         employee_name = contract_data.get("employee_name", "Unknown")
# # # #         log_to_streamlit(f"💰 Calculating salary breakdown for: {employee_name}")
        
# # # #         # Prepare detailed input for LLM
# # # #         input_data = {
# # # #             "employee_details": contract_data,
# # # #             "calculation_instructions": "Calculate comprehensive salary breakdown with Indian compliance standards"
# # # #         }
        
# # # #         parsed_json = llm_call(SALARY_BREAKDOWN_PROMPT, json.dumps(input_data, indent=2), "Salary Breakdown", state)
        
# # # #         if not parsed_json:
# # # #             log_to_streamlit("❌ No response from Salary Breakdown Agent", "ERROR")
# # # #             state["salary_breakdown"] = {}
# # # #             return state
        
# # # #         salary_data = safe_json_loads(parsed_json, "Salary Breakdown")
# # # #         state["salary_breakdown"] = salary_data
        
# # # #         gross_salary = salary_data.get("gross_salary", 0)
# # # #         net_salary = salary_data.get("net_salary", 0)
# # # #         log_to_streamlit(f"💰 Salary calculated - Gross: ₹{gross_salary:,.2f}, Net: ₹{net_salary:,.2f}", "SUCCESS")
# # # #         log_to_streamlit("🏁 AGENT: Salary Breakdown Agent Completed", "AGENT")
        
# # # #         return state
        
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Salary Breakdown Agent failed: {str(e)}", "ERROR")
# # # #         state["salary_breakdown"] = {}
# # # #         return state

# # # # def compliance_mapper_agent(state):
# # # #     """Enhanced Compliance Mapper Agent with RAG integration"""
# # # #     log_to_streamlit("🚀 AGENT: Compliance Mapper Agent Started", "AGENT")
    
# # # #     try:
# # # #         if not state.get("salary_breakdown"):
# # # #             log_to_streamlit("❌ No salary breakdown available for compliance mapping", "ERROR")
# # # #             state["compliance_data"] = {}
# # # #             return state
        
# # # #         # Query tax rules using RAG
# # # #         log_to_streamlit("🔍 Retrieving relevant tax rules from knowledge base")
# # # #         tax_rules = query_tax_rules("PF ESI Professional Tax Income Tax compliance rules deduction limits")
        
# # # #         if not tax_rules:
# # # #             log_to_streamlit("⚠️ No tax rules found in knowledge base, using built-in rules", "WARNING")
# # # #             tax_rules = "Standard Indian tax rules: PF 12% capped at Rs.1800, ESI 0.75% if gross<=21000, PT location-based"
        
# # # #         # Prepare compliance validation input
# # # #         payload = {
# # # #             "salary_data": state["salary_breakdown"],
# # # #             "contract_data": state.get("contract_data", {}),
# # # #             "tax_rules": tax_rules,
# # # #             "validation_requirements": "Ensure full compliance with Indian labor laws and tax regulations"
# # # #         }
        
# # # #         log_to_streamlit(f"⚖️ Validating compliance for employee: {state.get('contract_data', {}).get('employee_name', 'Unknown')}")
        
# # # #         parsed_json = llm_call(COMPLIANCE_MAPPER_PROMPT, json.dumps(payload, indent=2), "Compliance Mapper", state)
        
# # # #         if not parsed_json:
# # # #             log_to_streamlit("❌ No response from Compliance Mapper Agent", "ERROR")
# # # #             state["compliance_data"] = {}
# # # #             return state
        
# # # #         compliance_data = safe_json_loads(parsed_json, "Compliance Mapper")
# # # #         state["compliance_data"] = compliance_data
        
# # # #         # Log compliance status
# # # #         compliance_status = compliance_data.get("compliance_status", {})
# # # #         overall_compliant = compliance_status.get("overall_compliant", False)
# # # #         corrections_count = len(compliance_data.get("corrections_made", []))
        
# # # #         log_to_streamlit(f"⚖️ Compliance check completed - Status: {'✅ Compliant' if overall_compliant else '❌ Non-compliant'}")
# # # #         log_to_streamlit(f"🔧 Corrections made: {corrections_count}")
# # # #         log_to_streamlit("🏁 AGENT: Compliance Mapper Agent Completed", "AGENT")
        
# # # #         return state
        
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Compliance Mapper Agent failed: {str(e)}", "ERROR")
# # # #         state["compliance_data"] = {}
# # # #         return state

# # # # def anomaly_detector_agent(state):
# # # #     """Enhanced Anomaly Detector Agent with comprehensive analysis"""
# # # #     log_to_streamlit("🚀 AGENT: Anomaly Detector Agent Started", "AGENT")
    
# # # #     try:
# # # #         if not state.get("compliance_data"):
# # # #             log_to_streamlit("❌ No compliance data available for anomaly detection", "ERROR")
# # # #             state["anomalies"] = {}
# # # #             return state
        
# # # #         # Prepare comprehensive analysis input
# # # #         analysis_data = {
# # # #             "contract_data": state.get("contract_data", {}),
# # # #             "salary_breakdown": state.get("salary_breakdown", {}),
# # # #             "compliance_data": state["compliance_data"],
# # # #             "analysis_scope": "Comprehensive payroll anomaly detection and risk assessment"
# # # #         }
        
# # # #         employee_name = state.get("contract_data", {}).get("employee_name", "Unknown")
# # # #         log_to_streamlit(f"🔍 Analyzing payroll anomalies for: {employee_name}")
        
# # # #         parsed_json = llm_call(ANOMALY_DETECTOR_PROMPT, json.dumps(analysis_data, indent=2), "Anomaly Detector", state)
        
# # # #         if not parsed_json:
# # # #             log_to_streamlit("❌ No response from Anomaly Detector Agent", "ERROR")
# # # #             state["anomalies"] = {}
# # # #             return state
        
# # # #         anomaly_data = safe_json_loads(parsed_json, "Anomaly Detector")
# # # #         state["anomalies"] = anomaly_data
        
# # # #         # Log anomaly detection results
# # # #         anomalies_detected = anomaly_data.get("anomalies_detected", False)
# # # #         risk_score = anomaly_data.get("risk_score", 0)
# # # #         total_anomalies = len(anomaly_data.get("anomalies", []))
        
# # # #         log_to_streamlit(f"🔍 Anomaly detection completed - Found: {total_anomalies} anomalies")
# # # #         log_to_streamlit(f"⚠️ Risk Score: {risk_score}/10")
        
# # # #         if anomalies_detected:
# # # #             log_to_streamlit("🚨 ANOMALIES DETECTED - Review required", "WARNING")
# # # #         else:
# # # #             log_to_streamlit("✅ No significant anomalies detected", "SUCCESS")
        
# # # #         log_to_streamlit("🏁 AGENT: Anomaly Detector Agent Completed", "AGENT")
        
# # # #         return state
        
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Anomaly Detector Agent failed: {str(e)}", "ERROR")
# # # #         state["anomalies"] = {}
# # # #         return state

# # # # def paystub_generator_agent(state):
# # # #     """Enhanced Payslip Generator Agent with professional formatting"""
# # # #     log_to_streamlit("🚀 AGENT: Payslip Generator Agent Started", "AGENT")
    
# # # #     try:
# # # #         if not all(key in state for key in ["contract_data", "salary_breakdown", "compliance_data"]):
# # # #             log_to_streamlit("❌ Insufficient data for payslip generation", "ERROR")
# # # #             state["payslip_path"] = None
# # # #             return state
        
# # # #         # Prepare comprehensive payslip data
# # # #         employee_name = state["contract_data"].get("employee_name", "Unknown Employee")
# # # #         employee_id = state["contract_data"].get("employee_id", "N/A")
        
# # # #         log_to_streamlit(f"📄 Generating payslip for: {employee_name} (ID: {employee_id})")
        
# # # #         payslip_data = {
# # # #             "employee_details": state["contract_data"],
# # # #             "salary_breakdown": state["salary_breakdown"],
# # # #             "compliance_data": state["compliance_data"],
# # # #             "anomaly_info": state.get("anomalies", {}),
# # # #             "generation_date": datetime.now().strftime("%Y-%m-%d"),
# # # #             "pay_period": datetime.now().strftime("%B %Y"),
# # # #             "company_details": {
# # # #                 "name": "Sample Company Pvt Ltd",
# # # #                 "address": "123 Business District, City, State - 560001",
# # # #                 "pan": "AAACI1681G",
# # # #                 "pf_code": "KR/BGE/12345"
# # # #             }
# # # #         }
        
# # # #         # Generate HTML payslip
# # # #         html_content = llm_call(PAYSTUB_GENERATOR_PROMPT, json.dumps(payslip_data, indent=2), "Payslip Generator", state)
        
# # # #         if not html_content:
# # # #             log_to_streamlit("❌ Failed to generate payslip HTML", "ERROR")
# # # #             state["payslip_path"] = None
# # # #             return state
        
# # # #         # Save payslip as PDF
# # # #         safe_employee_name = "".join(c for c in employee_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
# # # #         filename = f"payslip_{safe_employee_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
# # # #         pdf_path = save_payslip_html_to_pdf(html_content, filename)
# # # #         state["payslip_path"] = pdf_path
        
# # # #         # Save data to MongoDB if available
# # # #         if db:
# # # #             try:
# # # #                 log_to_streamlit("💾 Saving data to MongoDB")
                
# # # #                 # Save contract data
# # # #                 contract_record = {
# # # #                     **state["contract_data"],
# # # #                     "processed_date": datetime.now(),
# # # #                     "processing_id": datetime.now().strftime("%Y%m%d_%H%M%S")
# # # #                 }
# # # #                 db.contracts.insert_one(contract_record)
                
# # # #                 # Save payroll calculation
# # # #                 payroll_record = {
# # # #                     **state["salary_breakdown"],
# # # #                     "employee_name": employee_name,
# # # #                     "processed_date": datetime.now(),
# # # #                     "processing_id": datetime.now().strftime("%Y%m%d_%H%M%S")
# # # #                 }
# # # #                 db.payroll.insert_one(payroll_record)
                
# # # #                 # Save compliance data
# # # #                 compliance_record = {
# # # #                     **state["compliance_data"],
# # # #                     "employee_name": employee_name,
# # # #                     "processed_date": datetime.now(),
# # # #                     "processing_id": datetime.now().strftime("%Y%m%d_%H%M%S")
# # # #                 }
# # # #                 db.compliance.insert_one(compliance_record)
                
# # # #                 # Save payslip record
# # # #                 payslip_record = {
# # # #                     "employee_name": employee_name,
# # # #                     "employee_id": employee_id,
# # # #                     "file_path": pdf_path,
# # # #                     "generated_date": datetime.now(),
# # # #                     "processing_id": datetime.now().strftime("%Y%m%d_%H%M%S")
# # # #                 }
# # # #                 db.payslips.insert_one(payslip_record)
                
# # # #                 log_to_streamlit("✅ All data saved to MongoDB successfully", "SUCCESS")
                
# # # #             except Exception as e:
# # # #                 log_to_streamlit(f"⚠️ MongoDB save failed: {str(e)}", "WARNING")
        
# # # #         log_to_streamlit(f"📄 Payslip generated successfully: {filename}", "SUCCESS")
# # # #         log_to_streamlit("🏁 AGENT: Payslip Generator Agent Completed", "AGENT")
        
# # # #         return state
        
# # # #     except Exception as e:
# # # #         log_to_streamlit(f"❌ Payslip Generator Agent failed: {str(e)}", "ERROR")
# # # #         state["payslip_path"] = None
# # # #         return state

# # # # # =====================
# # # # # ENHANCED LANGGRAPH PIPELINE WITH LOGGING
# # # # # =====================
# # # # def log_agent_transition(from_agent, to_agent):
# # # #     """Log agent transitions for workflow visibility"""
# # # #     log_to_streamlit(f"🔄 WORKFLOW: Transitioning from {from_agent} → {to_agent}", "WORKFLOW")

# # # # # Build enhanced StateGraph with logging
# # # # graph = StateGraph(PayrollState)

# # # # # Add nodes with enhanced logging
# # # # graph.add_node("contract_reader_agent", contract_reader_agent)
# # # # graph.add_node("salary_breakdown_agent", salary_breakdown_agent) 
# # # # graph.add_node("compliance_mapper_agent", compliance_mapper_agent)
# # # # graph.add_node("anomaly_detector_agent", anomaly_detector_agent)
# # # # graph.add_node("paystub_generator_agent", paystub_generator_agent)

# # # # # Set entry point and edges
# # # # graph.set_entry_point("contract_reader_agent")
# # # # graph.add_edge("contract_reader_agent", "salary_breakdown_agent")
# # # # graph.add_edge("salary_breakdown_agent", "compliance_mapper_agent")
# # # # graph.add_edge("compliance_mapper_agent", "anomaly_detector_agent")
# # # # graph.add_edge("anomaly_detector_agent", "paystub_generator_agent")
# # # # graph.add_edge("paystub_generator_agent", END)

# # # # # Compile workflow
# # # # workflow = graph.compile()

# # # # # =====================
# # # # # ENHANCED STREAMLIT UI
# # # # # =====================
# # # # def display_logs():
# # # #     """Display real-time logs in Streamlit"""
# # # #     if st.session_state.logger_handler:
# # # #         st.subheader("🔍 Real-time Processing Logs")
# # # #         with st.expander("View Detailed Logs", expanded=False):
# # # #             for log_entry in st.session_state.logger_handler[-50:]:  # Show last 50 logs
# # # #                 if "ERROR" in log_entry:
# # # #                     st.error(log_entry)
# # # #                 elif "WARNING" in log_entry:
# # # #                     st.warning(log_entry)
# # # #                 elif "SUCCESS" in log_entry:
# # # #                     st.success(log_entry)
# # # #                 elif "AGENT" in log_entry or "WORKFLOW" in log_entry:
# # # #                     st.info(log_entry)
# # # #                 else:
# # # #                     st.text(log_entry)

# # # # def display_agent_communications(state):
# # # #     """Display agent-to-agent communications"""
# # # #     if state and "agent_communications" in state and state["agent_communications"]:
# # # #         st.subheader("🤖 Agent Communications")
# # # #         for i, comm in enumerate(state["agent_communications"]):
# # # #             with st.expander(f"Agent {i+1}: {comm['agent']} - {comm['timestamp'][:19]}", expanded=False):
# # # #                 col1, col2 = st.columns(2)
# # # #                 with col1:
# # # #                     st.text_area("Prompt Preview", comm['prompt_preview'], height=100, key=f"prompt_{i}")
# # # #                     st.text_area("Content Preview", comm['content_preview'], height=100, key=f"content_{i}")
# # # #                 with col2:
# # # #                     st.text_area("Response Preview", comm['response_preview'], height=100, key=f"response_{i}")
# # # #                     st.metric("Response Length", f"{comm['response_length']} chars")

# # # # # Main Streamlit Application
# # # # def main():
# # # #     st.set_page_config(
# # # #         page_title="Agentic AI Payroll & Tax Planner",
# # # #         page_icon="💼",
# # # #         layout="wide",
# # # #         initial_sidebar_state="expanded"
# # # #     )
    
# # # #     st.title("🤖 Agentic AI-Based Payroll & Tax Planner")
# # # #     st.markdown("**Powered by LangGraph, Gemini AI, and RAG Technology**")
    
# # # #     # Initialize session state
# # # #     if 'processing_complete' not in st.session_state:
# # # #         st.session_state.processing_complete = False
# # # #     if 'final_state' not in st.session_state:
# # # #         st.session_state.final_state = None
    
# # # #     # Sidebar for configuration
# # # #     with st.sidebar:
# # # #         st.header("⚙️ Configuration")
        
# # # #         # Verbose mode toggle
# # # #         verbose_mode = st.checkbox("Enable Verbose Logging", value=True, help="Show detailed agent communications and debugging info")
        
# # # #         # System status
# # # #         st.subheader("📊 System Status")
# # # #         st.success("✅ Gemini AI Connected" if client else "❌ Gemini AI Disconnected")
# # # #         st.success("✅ MongoDB Connected" if db else "❌ MongoDB Disconnected") 
# # # #         st.success("✅ Embeddings Ready" if embedding_fn else "❌ Embeddings Failed")
        
# # # #         # Clear logs button
# # # #         if st.button("🗑️ Clear Logs"):
# # # #             st.session_state.logger_handler = []
# # # #             st.rerun()
    
# # # #     # Main content tabs
# # # #     tab1, tab2, tab3, tab4 = st.tabs(["📚 Knowledge Base", "📄 Contract Processing", "📊 Results", "🔍 Debug Logs"])
    
# # # #     with tab1:
# # # #         st.subheader("📂 Upload Tax Rule PDFs (RAG Knowledge Base)")
# # # #         st.markdown("Upload official tax rule documents to build the knowledge base for compliance validation.")
        
# # # #         col1, col2 = st.columns(2)
        
# # # #         with col1:
# # # #             tax_file = st.file_uploader("Upload Tax Rule PDF", type=["pdf"], help="Upload official tax documents")
# # # #             if st.button("🔄 Embed Tax Rules", disabled=not tax_file) and tax_file:
# # # #                 with st.spinner("Processing tax rules..."):
# # # #                     with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # # #                         tmp.write(tax_file.read())
# # # #                         chunk_count = embed_tax_pdf(tmp.name)
                    
# # # #                     if chunk_count > 0:
# # # #                         st.success(f"✅ Tax rules embedded successfully! {chunk_count} chunks processed.")
# # # #                     else:
# # # #                         st.error("❌ Failed to embed tax rules.")
        
# # # #         with col2:
# # # #             if st.button("📋 Load Sample Tax Rules"):
# # # #                 with st.spinner("Loading sample tax rules..."):
# # # #                     chunk_count = load_sample_tax_rules()
# # # #                     if chunk_count > 0:
# # # #                         st.success(f"✅ Sample tax rules loaded! {chunk_count} chunks embedded.")
# # # #                     else:
# # # #                         st.error("❌ Failed to load sample tax rules.")
        
# # # #         # Test RAG functionality
# # # #         st.subheader("🔍 Test Knowledge Base")
# # # #         test_query = st.text_input("Query tax rules:", placeholder="e.g., What is the PF contribution rate?")
# # # #         if st.button("🔍 Search") and test_query:
# # # #             with st.spinner("Searching knowledge base..."):
# # # #                 results = query_tax_rules(test_query)
# # # #                 if results:
# # # #                     st.text_area("Search Results:", results, height=200)
# # # #                 else:
# # # #                     st.warning("No relevant results found in knowledge base.")
    
# # # #     with tab2:
# # # #         st.subheader("📄 Upload Employee Contract PDF")
# # # #         st.markdown("Upload an employment contract to process through the Agentic AI pipeline.")
        
# # # #         contract_file = st.file_uploader("Upload Employment Contract", type=["pdf"])
        
# # # #         col1, col2 = st.columns(2)
        
# # # #         with col1:
# # # #             if st.button("🚀 Process Contract", disabled=not contract_file, type="primary") and contract_file:
# # # #                 # Clear previous logs and results
# # # #                 st.session_state.logger_handler = []
# # # #                 st.session_state.processing_complete = False
# # # #                 st.session_state.final_state = None
                
# # # #                 with st.spinner("🤖 Running Agentic AI Pipeline..."):
# # # #                     try:
# # # #                         log_to_streamlit("🎯 WORKFLOW: Starting Agentic AI Payroll Processing Pipeline", "WORKFLOW")
                        
# # # #                         # Save uploaded file temporarily
# # # #                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # # #                             tmp.write(contract_file.read())
                            
# # # #                             # Initialize state with verbose mode
# # # #                             initial_state = {
# # # #                                 "contract_path": tmp.name,
# # # #                                 "verbose": verbose_mode,
# # # #                                 "agent_communications": []
# # # #                             }
                        
# # # #                         log_to_streamlit("🔧 Invoking LangGraph workflow...", "WORKFLOW")
                        
# # # #                         # Run the agentic workflow
# # # #                         final_state = workflow.invoke(initial_state)
                        
# # # #                         st.session_state.final_state = final_state
# # # #                         st.session_state.processing_complete = True
                        
# # # #                         log_to_streamlit("🎉 WORKFLOW: Agentic AI Pipeline Completed Successfully!", "SUCCESS")
                        
# # # #                     except Exception as e:
# # # #                         st.error(f"❌ Pipeline execution failed: {str(e)}")
# # # #                         log_to_streamlit(f"❌ WORKFLOW: Pipeline failed - {str(e)}", "ERROR")
# # # #                         log_to_streamlit(f"❌ WORKFLOW: Traceback - {traceback.format_exc()}", "ERROR")
        
# # # #         with col2:
# # # #             if st.button("📊 View System Metrics"):
# # # #                 col_a, col_b, col_c = st.columns(3)
# # # #                 with col_a:
# # # #                     st.metric("Total Logs", len(st.session_state.logger_handler))
# # # #                 with col_b:
# # # #                     error_count = len([log for log in st.session_state.logger_handler if "ERROR" in log])
# # # #                     st.metric("Errors", error_count)
# # # #                 with col_c:
# # # #                     success_count = len([log for log in st.session_state.logger_handler if "SUCCESS" in log])
# # # #                     st.metric("Successes", success_count)
    
# # # #     with tab3:
# # # #         if st.session_state.processing_complete and st.session_state.final_state:
# # # #             final_state = st.session_state.final_state
            
# # # #             st.subheader("📊 Processing Results")
            
# # # #             # Display results in organized sections
# # # #             col1, col2 = st.columns(2)
            
# # # #             with col1:
# # # #                 # Contract Data
# # # #                 if final_state.get("contract_data"):
# # # #                     st.subheader("📋 Contract Information")
# # # #                     contract_data = final_state["contract_data"]
# # # #                     st.json(contract_data)
                    
# # # #                     # Key metrics
# # # #                     if contract_data.get("salary_structure"):
# # # #                         salary_structure = contract_data["salary_structure"]
# # # #                         total_fixed = sum([v for v in salary_structure.values() if isinstance(v, (int, float))])
# # # #                         st.metric("Total Fixed Salary", f"₹{total_fixed:,.2f}")
                
# # # #                 # Salary Breakdown
# # # #                 if final_state.get("salary_breakdown"):
# # # #                     st.subheader("💰 Salary Breakdown")
# # # #                     salary_data = final_state["salary_breakdown"]
# # # #                     st.json(salary_data)
                    
# # # #                     # Salary metrics
# # # #                     if salary_data.get("gross_salary") and salary_data.get("net_salary"):
# # # #                         col_a, col_b, col_c = st.columns(3)
# # # #                         with col_a:
# # # #                             st.metric("Gross Salary", f"₹{salary_data['gross_salary']:,.2f}")
# # # #                         with col_b:
# # # #                             total_deductions = sum(salary_data.get("deductions", {}).values())
# # # #                             st.metric("Total Deductions", f"₹{total_deductions:,.2f}")
# # # #                         with col_c:
# # # #                             st.metric("Net Salary", f"₹{salary_data['net_salary']:,.2f}")
            
# # # #             with col2:
# # # #                 # Compliance Data
# # # #                 if final_state.get("compliance_data"):
# # # #                     st.subheader("⚖️ Compliance Validation")
# # # #                     compliance_data = final_state["compliance_data"]
# # # #                     st.json(compliance_data)
                    
# # # #                     # Compliance status indicators
# # # #                     compliance_status = compliance_data.get("compliance_status", {})
# # # #                     if compliance_status:
# # # #                         st.subheader("🎯 Compliance Status")
# # # #                         for key, value in compliance_status.items():
# # # #                             status = "✅ Compliant" if value else "❌ Non-compliant"
# # # #                             st.write(f"**{key.replace('_', ' ').title()}**: {status}")
                
# # # #                 # Anomalies
# # # #                 if final_state.get("anomalies"):
# # # #                     st.subheader("🔍 Anomaly Detection")
# # # #                     anomaly_data = final_state["anomalies"]
# # # #                     st.json(anomaly_data)
                    
# # # #                     # Anomaly summary
# # # #                     if anomaly_data.get("anomalies"):
# # # #                         st.subheader("⚠️ Detected Anomalies")
# # # #                         for anomaly in anomaly_data["anomalies"]:
# # # #                             severity_color = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
# # # #                             severity_icon = severity_color.get(anomaly.get("severity", "low"), "⚪")
# # # #                             st.write(f"{severity_icon} **{anomaly.get('type', 'Unknown')}** ({anomaly.get('severity', 'low')}): {anomaly.get('description', 'No description')}")
            
# # # #             # Payslip Download
# # # #             if final_state.get("payslip_path") and os.path.exists(final_state["payslip_path"]):
# # # #                 st.subheader("📄 Generated Payslip")
# # # #                 with open(final_state["payslip_path"], "rb") as f:
# # # #                     st.download_button(
# # # #                         label="📥 Download Payslip PDF",
# # # #                         data=f.read(),
# # # #                         file_name=os.path.basename(final_state["payslip_path"]),
# # # #                         mime="application/pdf",
# # # #                         type="primary"
# # # #                     )
            
# # # #             # Agent Communications
# # # #             display_agent_communications(final_state)
            
# # # #         else:
# # # #             st.info("👆 Upload and process a contract to see results here.")
    
# # # #     with tab4:
# # # #         st.subheader("🔍 Debug Information")
        
# # # #         # Real-time logs
# # # #         display_logs()
        
# # # #         # System information
# # # #         if st.button("🔧 Show System Info"):
# # # #             st.subheader("⚙️ System Configuration")
# # # #             system_info = {
# # # #                 "GEMINI_API_KEY": "✅ Configured" if GEMINI_API_KEY else "❌ Not configured",
# # # #                 "MONGO_URI": "✅ Configured" if MONGO_URI else "❌ Not configured",
# # # #                 "CHROMA_DIR": CHROMA_DIR,
# # # #                 "PAYSLIP_DIR": PAYSPLIP_DIR,
# # # #                 "ChromaDB exists": os.path.exists(CHROMA_DIR),
# # # #                 "Payslips dir exists": os.path.exists(PAYSPLIP_DIR)
# # # #             }
# # # #             st.json(system_info)

# # # # if __name__ == "__main__":
# # # #     main()

# # # # # # app.py
# # # # # import os
# # # # # import io
# # # # # import json
# # # # # import base64
# # # # # import pdfkit
# # # # # import tempfile
# # # # # import streamlit as st
# # # # # from datetime import datetime
# # # # # from pymongo import MongoClient
# # # # # from openai import OpenAI
# # # # # from PyPDF2 import PdfReader
# # # # # from langchain_community.vectorstores import Chroma
# # # # # from langchain_community.document_loaders import PyPDFLoader
# # # # # from langchain_text_splitters import RecursiveCharacterTextSplitter
# # # # # from langchain_google_genai import GoogleGenerativeAIEmbeddings
# # # # # from langgraph.graph import StateGraph, END
# # # # # import asyncio
# # # # # from typing import TypedDict, Optional, Dict, Any
# # # # # from dotenv import load_dotenv
# # # # # import ast

# # # # # load_dotenv()
# # # # # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# # # # # try:
# # # # #     asyncio.get_running_loop()
# # # # # except RuntimeError:
# # # # #     asyncio.set_event_loop(asyncio.new_event_loop())


# # # # # class PayrollState(TypedDict):
# # # # #     contract_path: str
# # # # #     contract_data: Optional[Dict[str, Any]]
# # # # #     salary_breakdown: Optional[Dict[str, Any]]
# # # # #     compliance_data: Optional[Dict[str, Any]]
# # # # #     anomalies: Optional[Dict[str, Any]]
# # # # #     payslip_path: Optional[str]


# # # # # # =====================
# # # # # # CONFIGURATION
# # # # # # =====================
# # # # # # os.environ["GEMINI_API_KEY"] = "AIzaSyBiMIZleZzmhkJBuld1s1ATDUK7JVELV_0s"
# # # # # MONGO_URI = "mongodb+srv://Naveen:Qwe%401234567890@cluster0.u8t9s.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# # # # # DB_NAME = "payroll_db"
# # # # # CHROMA_DIR = "./chroma_db"
# # # # # PAYSPLIP_DIR = "./payslips"
# # # # # os.makedirs(PAYSPLIP_DIR, exist_ok=True)

# # # # # # MongoDB connection
# # # # # mongo_client = MongoClient(MONGO_URI)
# # # # # db = mongo_client[DB_NAME]

# # # # # # OpenAI-compatible Gemini client
# # # # # client = OpenAI(
# # # # #     api_key=GEMINI_API_KEY,
# # # # #     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# # # # # )

# # # # # # ChromaDB embeddings
# # # # # embedding_fn = GoogleGenerativeAIEmbeddings(
# # # # #     model="models/embedding-001",
# # # # #     google_api_key=GEMINI_API_KEY
# # # # # )

# # # # # # =====================
# # # # # # PROMPTS FOR AGENTS
# # # # # # =====================
# # # # # # CONTRACT_READER_PROMPT = """<your Contract Reader Agent prompt here>"""
# # # # # # SALARY_BREAKDOWN_PROMPT = """<your Salary Breakdown Agent prompt here>"""
# # # # # # COMPLIANCE_MAPPER_PROMPT = """<your Compliance Mapper Agent prompt here>"""
# # # # # # ANOMALY_DETECTOR_PROMPT = """<your Anomaly Detector Agent prompt here>"""
# # # # # # PAYSTUB_GENERATOR_PROMPT = """<your Paystub Generator Agent prompt here>"""

# # # # # CONTRACT_READER_PROMPT = """
# # # # # You are an AI payroll contract parser.

# # # # # TASK:
# # # # # Extract structured salary and statutory details from the given employment contract text.
# # # # # Return ONLY JSON with the following keys:
# # # # # - employee_name
# # # # # - employee_id (if not available, null)
# # # # # - joining_date (YYYY-MM-DD or null)
# # # # # - location
# # # # # - salary_structure: {
# # # # #     basic: number,
# # # # #     hra: number,
# # # # #     lta: number,
# # # # #     conveyance: number,
# # # # #     medical: number,
# # # # #     special_allowance: number,
# # # # #     bonus: number,
# # # # #     variable_pay: number
# # # # # }
# # # # # - statutory_components: {
# # # # #     pf_capped: boolean,
# # # # #     gratuity_applicable: boolean,
# # # # #     esi_applicable: boolean,
# # # # #     professional_tax_applicable: boolean,
# # # # #     income_tax_regime: "old" or "new" or null
# # # # # }
# # # # # - additional_benefits: list of strings
# # # # # - proration_rules: string or null
# # # # # - region_specific_clauses: list of strings

# # # # # REQUIREMENTS:
# # # # # - Read amounts as numbers without commas.
# # # # # - If a value is missing, set it to null.
# # # # # - Output JSON only, no extra commentary.
# # # # # """
# # # # # SALARY_BREAKDOWN_PROMPT = """
# # # # # You are a salary computation expert.

# # # # # TASK:
# # # # # Given the structured salary data for one employee, compute the monthly salary breakdown:
# # # # # - gross_salary: sum of all fixed salary components
# # # # # - deductions: dictionary with PF, ESI, Professional Tax, Income Tax (TDS), and other deductions
# # # # # - net_salary: gross_salary minus total deductions

# # # # # REQUIREMENTS:
# # # # # - Use prorated calculation if proration rules are given.
# # # # # - Do NOT assume tax slabs; those will be fetched from compliance rules.
# # # # # - Provide calculation_justification for each line item.
# # # # # - Return ONLY JSON:
# # # # # {
# # # # #   "gross_salary": number,
# # # # #   "deductions": { "pf": number, "esi": number, "pt": number, "tds": number, "other": number },
# # # # #   "net_salary": number,
# # # # #   "calculation_justification": { "pf": "...", "esi": "...", "pt": "...", "tds": "...", "other": "..." }
# # # # # }
# # # # # """
# # # # # COMPLIANCE_MAPPER_PROMPT = """
# # # # # You are a payroll compliance validation expert.

# # # # # TASK:
# # # # # Given:
# # # # # 1. Employee salary structure and current deductions.
# # # # # 2. Official tax & compliance rules provided below.

# # # # # Validate and adjust deductions:
# # # # # - Apply PF caps, correct PF %, and conditions from the rules.
# # # # # - Apply ESI eligibility based on salary thresholds.
# # # # # - Apply Professional Tax slabs based on location and rules.
# # # # # - Apply Income Tax (TDS) based on applicable slab rates.

# # # # # If a deduction is wrong, adjust it and explain the correction.

# # # # # Return ONLY JSON:
# # # # # {
# # # # #   "validated_deductions": { "pf": number, "esi": number, "pt": number, "tds": number, "other": number },
# # # # #   "compliance_notes": list of strings
# # # # # }
# # # # # """
# # # # # ANOMALY_DETECTOR_PROMPT = """
# # # # # You are a payroll anomaly detection agent.

# # # # # TASK:
# # # # # Given the final payroll calculation for one employee and historical company payroll norms (if available), detect:
# # # # # - Overpayments
# # # # # - Under-deductions
# # # # # - Missing mandatory deductions
# # # # # - Unusually high allowances

# # # # # Return ONLY JSON:
# # # # # {
# # # # #   "anomalies_detected": boolean,
# # # # #   "anomalies": list of { "type": string, "description": string, "severity": "low"|"medium"|"high" }
# # # # # }
# # # # # """
# # # # # PAYSTUB_GENERATOR_PROMPT = """
# # # # # You are a payslip formatting assistant.

# # # # # TASK:
# # # # # Given the final salary breakdown and deductions for an employee, generate a clean HTML payslip:
# # # # # - Include company name, employee name, month/year, and payment date.
# # # # # - Show earnings table (basic, hra, allowances, bonuses).
# # # # # - Show deductions table (pf, esi, pt, tds, other).
# # # # # - Show gross, total deductions, and net pay.
# # # # # - Keep it professional and ready for HTML-to-PDF conversion.
# # # # # - Do not include scripts or external links.

# # # # # Return ONLY HTML.
# # # # # """

# # # # # # =====================
# # # # # # UTILITY FUNCTIONS
# # # # # # =====================
# # # # # def extract_text_from_pdf(file_path):
# # # # #     reader = PdfReader(file_path)
# # # # #     text = ""
# # # # #     for page in reader.pages:
# # # # #         text += page.extract_text() or ""
# # # # #     return text.strip()

# # # # # def embed_tax_pdf(file_path):
# # # # #     loader = PyPDFLoader(file_path)
# # # # #     docs = loader.load()
# # # # #     splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
# # # # #     chunks = splitter.split_documents(docs)
# # # # #     vectordb = Chroma.from_documents(chunks, embedding_fn, persist_directory=CHROMA_DIR)
# # # # #     vectordb.persist()
# # # # #     return len(chunks)

# # # # # def query_tax_rules(query):
# # # # #     vectordb = Chroma(persist_directory=CHROMA_DIR, embedding_function=embedding_fn)
# # # # #     results = vectordb.similarity_search(query, k=3)
# # # # #     return "\n\n".join([doc.page_content for doc in results])

# # # # # def llm_call(prompt, content):
# # # # #     resp = client.chat.completions.create(
# # # # #         model="gemini-2.5-pro",
# # # # #         messages=[
# # # # #             {"role": "system", "content": prompt},
# # # # #             {"role": "user", "content": content}
# # # # #         ]
# # # # #     )
# # # # #     msg = resp.choices[0].message
# # # # #     if hasattr(msg, "content"):  # Newer SDK object
# # # # #         output = msg.content
# # # # #     else:  # Dict style
# # # # #         output = msg.get("content", "")
# # # # #     return (output or "").strip()

# # # # # def safe_json_loads(text):
# # # # #     try:
# # # # #         return json.loads(text)
# # # # #     except json.JSONDecodeError:
# # # # #         try:
# # # # #             return ast.literal_eval(text)  # Sometimes Gemini returns Python dict style
# # # # #         except Exception:
# # # # #             st.error("❌ LLM did not return valid JSON. Got:\n" + str(text))
# # # # #             return {}

# # # # # def save_payslip_html_to_pdf(html_content, filename):
# # # # #     pdf_path = os.path.join(PAYSPLIP_DIR, filename)
# # # # #     pdfkit.from_string(html_content, pdf_path)
# # # # #     return pdf_path

# # # # # def load_sample_tax_rules():
# # # # #     sample_text = """
# # # # # Provident Fund (PF) is capped at 15000 INR per month basic pay. 
# # # # # PF rate: 12% employee, 12% employer.
# # # # # ESI applies if gross monthly salary <= 21000 INR. ESI rate: 0.75% employee, 3.25% employer.
# # # # # Professional Tax in Karnataka: INR 200 per month if salary > 15000 INR.
# # # # # Income Tax slabs: 0-250000: 0%, 250001-500000: 5%, 500001-1000000: 20%, >1000000: 30%.
# # # # # """
# # # # #     with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # # # #         pdfkit.from_string(sample_text, tmp.name)
# # # # #         embed_tax_pdf(tmp.name)

# # # # # # =====================
# # # # # # LANGGRAPH AGENTS
# # # # # # =====================
# # # # # def contract_reader_agent(state):
# # # # #     text = extract_text_from_pdf(state["contract_path"])
# # # # #     parsed_json = llm_call(CONTRACT_READER_PROMPT, text)
# # # # #     state["contract_data"] = safe_json_loads(parsed_json)
# # # # #     return state

# # # # # def salary_breakdown_agent(state):
# # # # #     parsed_json = llm_call(SALARY_BREAKDOWN_PROMPT, json.dumps(state["contract_data"]))
# # # # #     state["salary_breakdown"] = safe_json_loads(parsed_json)
# # # # #     return state

# # # # # def compliance_mapper_agent(state):
# # # # #     tax_rules = query_tax_rules("PF, ESI, Professional Tax, Income Tax rules for payroll compliance")
# # # # #     payload = {
# # # # #         "salary_data": state["salary_breakdown"],
# # # # #         "tax_rules": tax_rules
# # # # #     }
# # # # #     parsed_json = llm_call(COMPLIANCE_MAPPER_PROMPT, json.dumps(payload))
# # # # #     state["compliance_data"] = safe_json_loads(parsed_json)
# # # # #     return state

# # # # # def anomaly_detector_agent(state):
# # # # #     parsed_json = llm_call(ANOMALY_DETECTOR_PROMPT, json.dumps(state["compliance_data"]))
# # # # #     state["anomalies"] = safe_json_loads(parsed_json)
# # # # #     return state

# # # # # def paystub_generator_agent(state):
# # # # #     payload = {
# # # # #         "salary_data": state["salary_breakdown"],
# # # # #         "compliance_data": state["compliance_data"]
# # # # #     }
# # # # #     html_content = llm_call(PAYSTUB_GENERATOR_PROMPT, json.dumps(payload))
# # # # #     filename = f"payslip_{state['contract_data']['employee_name']}_{datetime.now().strftime('%Y%m%d')}.pdf"
# # # # #     pdf_path = save_payslip_html_to_pdf(html_content, filename)
# # # # #     state["payslip_path"] = pdf_path
# # # # #     # Save in MongoDB
# # # # #     db.contracts.insert_one(state["contract_data"])
# # # # #     db.payroll.insert_one(state["salary_breakdown"])
# # # # #     db.payslips.insert_one({"employee": state["contract_data"]["employee_name"], "file_path": pdf_path})
# # # # #     return state

# # # # # # =====================
# # # # # # BUILD LANGGRAPH PIPELINE
# # # # # # =====================
# # # # # graph = StateGraph(PayrollState)
# # # # # graph.add_node("contract_reader_agent", contract_reader_agent)
# # # # # graph.add_node("salary_breakdown_agent", salary_breakdown_agent)
# # # # # graph.add_node("compliance_mapper_agent", compliance_mapper_agent)
# # # # # graph.add_node("anomaly_detector_agent", anomaly_detector_agent)
# # # # # graph.add_node("paystub_generator_agent", paystub_generator_agent)

# # # # # graph.set_entry_point("contract_reader_agent")
# # # # # graph.add_edge("contract_reader_agent", "salary_breakdown_agent")
# # # # # graph.add_edge("salary_breakdown_agent", "compliance_mapper_agent")
# # # # # graph.add_edge("compliance_mapper_agent", "anomaly_detector_agent")
# # # # # graph.add_edge("anomaly_detector_agent", "paystub_generator_agent")
# # # # # graph.add_edge("paystub_generator_agent", END)

# # # # # workflow = graph.compile()

# # # # # # =====================
# # # # # # STREAMLIT UI
# # # # # # =====================
# # # # # st.title("Agentic AI-Based Payroll & Tax Planner")

# # # # # st.subheader("📂 Upload Tax Rule PDFs (RAG Knowledge Base)")
# # # # # tax_file = st.file_uploader("Upload tax rule PDF", type=["pdf"])
# # # # # if st.button("Embed Tax Rules") and tax_file:
# # # # #     with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # # # #         tmp.write(tax_file.read())
# # # # #         chunk_count = embed_tax_pdf(tmp.name)
# # # # #     st.success(f"Tax rules embedded into ChromaDB with {chunk_count} chunks.")

# # # # # if st.button("Load Sample Tax Rules"):
# # # # #     load_sample_tax_rules()
# # # # #     st.success("Sample tax rules embedded successfully.")

# # # # # st.subheader("📄 Upload Employee Contract PDF")
# # # # # contract_file = st.file_uploader("Upload contract", type=["pdf"])
# # # # # if st.button("Process Contract") and contract_file:
    
# # # # #     with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
# # # # #         tmp.write(contract_file.read())
# # # # #         state = {"contract_path": tmp.name}
# # # # #     final_state = workflow.invoke(state)
# # # # #     st.json(final_state["contract_data"])
# # # # #     st.json(final_state["salary_breakdown"])
# # # # #     st.json(final_state["compliance_data"])
# # # # #     st.json(final_state["anomalies"])
# # # # #     with open(final_state["payslip_path"], "rb") as f:
# # # # #         st.download_button(
# # # # #             label="Download Payslip",
# # # # #             data=f,
# # # # #             file_name=os.path.basename(final_state["payslip_path"]),
# # # # #             mime="application/pdf"
# # # # #         )
