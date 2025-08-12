import streamlit as st
import pandas as pd
import json
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, List

# Set page config
st.set_page_config(
    page_title="AgenticAI Payroll System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .agent-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    .success-card {
        background-color: #d4edda;
        border-color: #28a745;
    }
    .error-card {
        background-color: #f8d7da;
        border-color: #dc3545;
    }
    .metric-card {
        background-color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processing_results' not in st.session_state:
    st.session_state.processing_results = []
if 'current_result' not in st.session_state:
    st.session_state.current_result = None

class MockPayrollProcessor:
    """Mock payroll processor for demonstration"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def process_contract(self, contract_path: str) -> Dict[str, Any]:
        """Mock contract processing"""
        
        # Read the contract file
        with open(contract_path, 'r') as f:
            contract_text = f.read()
        
        # Mock processing results
        result = {
            "success": True,
            "employee_id": "EMP001",
            "contract_data": self._extract_contract_data(contract_text),
            "salary_data": self._calculate_salary_breakdown(contract_text),
            "compliance_data": self._validate_compliance(contract_text),
            "anomalies_data": self._detect_anomalies(contract_text),
            "paystub_data": self._generate_paystub(contract_text),
            "processing_time": 2.5,
            "agent_logs": [
                {"agent": "ContractReaderAgent", "success": True, "execution_time": 0.8},
                {"agent": "SalaryBreakdownAgent", "success": True, "execution_time": 0.6},
                {"agent": "ComplianceMapperAgent", "success": True, "execution_time": 0.5},
                {"agent": "AnomalyDetectorAgent", "success": True, "execution_time": 0.4},
                {"agent": "PaystubGeneratorAgent", "success": True, "execution_time": 0.2}
            ]
        }
        
        return result
    
    def _extract_contract_data(self, contract_text: str) -> Dict[str, Any]:
        """Extract contract data from text"""
        # Simple text parsing
        lines = contract_text.split('\n')
        employee_info = {}
        salary_structure = {}
        
        for line in lines:
            line = line.strip()
            if 'Employee Name:' in line:
                employee_info['name'] = line.split(':')[1].strip()
            elif 'Employee ID:' in line:
                employee_info['id'] = line.split(':')[1].strip()
            elif 'Basic Salary:' in line:
                salary_structure['basic'] = float(line.split('₹')[1].split()[0].replace(',', ''))
            elif 'HRA:' in line:
                salary_structure['hra'] = float(line.split('₹')[1].split()[0].replace(',', ''))
            elif 'Special Allowance:' in line:
                salary_structure['special_allowance'] = float(line.split('₹')[1].split()[0].replace(',', ''))
        
        return {
            "employee_info": employee_info,
            "salary_structure": salary_structure,
            "extracted_text": contract_text[:500] + "..."
        }
    
    def _calculate_salary_breakdown(self, contract_text: str) -> Dict[str, Any]:
        """Calculate salary breakdown"""
        # Extract salary components
        basic = 50000  # Default values
        hra = 20000
        special_allowance = 15000
        
        gross_salary = basic + hra + special_allowance + 1250 + 1600 + 2200  # Including other allowances
        
        # Calculate deductions
        pf = min(basic * 0.12, 15000)  # PF capped at 15,000
        esi = gross_salary * 0.0175 if gross_salary <= 21000 else 0
        professional_tax = 200  # Simplified
        tds = gross_salary * 0.05  # Simplified tax calculation
        
        total_deductions = pf + esi + professional_tax + tds
        net_salary = gross_salary - total_deductions
        
        return {
            "gross_salary": gross_salary,
            "basic_salary": basic,
            "hra": hra,
            "allowances": special_allowance + 1250 + 1600 + 2200,
            "deductions": {
                "pf": pf,
                "esi": esi,
                "professional_tax": professional_tax,
                "tds": tds,
                "total": total_deductions
            },
            "net_salary": net_salary,
            "annual_gross": gross_salary * 12,
            "annual_net": net_salary * 12
        }
    
    def _validate_compliance(self, contract_text: str) -> Dict[str, Any]:
        """Validate compliance"""
        return {
            "compliance_status": "COMPLIANT",
            "issues": [],
            "recommendations": [
                "PF contribution is within statutory limits",
                "ESI calculation is correct for salary bracket",
                "Professional tax calculation is accurate"
            ],
            "applied_rules": [
                "PF Act - 12% contribution capped at ₹15,000",
                "ESI Act - 1.75% for salary ≤ ₹21,000",
                "Professional Tax - State-specific rates"
            ],
            "confidence_score": 0.95
        }
    
    def _detect_anomalies(self, contract_text: str) -> Dict[str, Any]:
        """Detect anomalies"""
        return {
            "has_anomalies": False,
            "anomalies": [],
            "overall_status": "NORMAL",
            "confidence_score": 0.98,
            "review_notes": "No anomalies detected in salary structure or calculations."
        }
    
    def _generate_paystub(self, contract_text: str) -> Dict[str, Any]:
        """Generate paystub data"""
        return {
            "employee_info": {"name": "John Doe", "id": "EMP001"},
            "salary_breakdown": self._calculate_salary_breakdown(contract_text),
            "pay_period": "January 2024",
            "generated_date": datetime.now().isoformat(),
            "template_version": "v1.0"
        }

def sidebar_config():
    """Configure the sidebar"""
    st.sidebar.title("🔧 Configuration")
    
    # API Key input
    api_key = st.sidebar.text_input(
        "Google API Key",
        type="password",
        value=st.session_state.get('api_key', ''),
        help="Enter your Google Gemini API key (demo mode works without key)"
    )
    
    if api_key:
        st.session_state.api_key = api_key
    
    # System status
    st.sidebar.subheader("📊 System Status")
    st.sidebar.success("✅ System Ready (Demo Mode)")
    
    # Processing options
    st.sidebar.subheader("⚙️ Default Options")
    st.sidebar.checkbox("Auto-validate compliance", value=True, key="default_auto_validate")
    st.sidebar.checkbox("Generate paystub", value=True, key="default_generate_paystub")
    st.sidebar.checkbox("Detect anomalies", value=True, key="default_detect_anomalies")
    
    # Clear results button
    if st.sidebar.button("🗑️ Clear All Results"):
        st.session_state.processing_results = []
        st.session_state.current_result = None
        st.rerun()

def main_dashboard():
    """Main dashboard page"""
    st.markdown('<h1 class="main-header">🤖 AgenticAI Payroll System</h1>', unsafe_allow_html=True)
    
    # System overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h3>📊 Total Processed</h3>
            <h2>{}</h2>
        </div>
        """.format(len(st.session_state.processing_results)), unsafe_allow_html=True)
    
    with col2:
        success_count = len([r for r in st.session_state.processing_results if r.get('success', False)])
        st.markdown("""
        <div class="metric-card">
            <h3>✅ Successful</h3>
            <h2>{}</h2>
        </div>
        """.format(success_count), unsafe_allow_html=True)
    
    with col3:
        if st.session_state.processing_results:
            avg_time = sum(r.get('processing_time', 0) for r in st.session_state.processing_results) / len(st.session_state.processing_results)
            st.markdown("""
            <div class="metric-card">
                <h3>⏱️ Avg Time</h3>
                <h2>{:.1f}s</h2>
            </div>
            """.format(avg_time), unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="metric-card">
                <h3>⏱️ Avg Time</h3>
                <h2>0.0s</h2>
            </div>
            """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <h3>🤖 Agents</h3>
            <h2>5 Active</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Recent processing results
    if st.session_state.processing_results:
        st.subheader("📋 Recent Processing Results")
        
        for i, result in enumerate(st.session_state.processing_results[-3:]):
            with st.expander(f"Employee: {result.get('employee_id', 'Unknown')} - {'✅ Success' if result.get('success') else '❌ Failed'}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**Processing Time:** {:.1f}s".format(result.get('processing_time', 0)))
                
                with col2:
                    if result.get('salary_data'):
                        st.write("**Gross Salary:** ₹{:,.0f}".format(result['salary_data']['gross_salary']))
                
                with col3:
                    if result.get('compliance_data'):
                        status = result['compliance_data']['compliance_status']
                        st.write("**Compliance:** {}".format(status))
                
                if st.button(f"View Details", key=f"view_{i}"):
                    st.session_state.current_result = result
                    st.rerun()
    else:
        st.info("📊 No processing results available. Process some contracts first!")

def contract_processing_page():
    """Contract processing page"""
    st.title("📤 Process Employment Contract")
    
    # File upload
    st.subheader("📁 Upload Contract")
    uploaded_file = st.file_uploader(
        "Choose an employment contract file",
        type=["txt", "pdf"],
        help="Upload a contract file for processing"
    )
    
    # Processing options
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚙️ Processing Options")
        auto_validate = st.checkbox("Auto-validate compliance", value=st.session_state.get("default_auto_validate", True))
        generate_paystub = st.checkbox("Generate paystub", value=st.session_state.get("default_generate_paystub", True))
        detect_anomalies = st.checkbox("Detect anomalies", value=st.session_state.get("default_detect_anomalies", True))
    
    with col2:
        st.subheader("📊 Preview Settings")
        show_agent_logs = st.checkbox("Show agent execution logs", value=False)
        show_raw_data = st.checkbox("Show raw extracted data", value=False)
        real_time_updates = st.checkbox("Real-time processing updates", value=True)
    
    # Process button
    if uploaded_file and st.button("🚀 Process Contract", type="primary"):
        process_contract(uploaded_file, {
            "auto_validate": auto_validate,
            "generate_paystub": generate_paystub,
            "detect_anomalies": detect_anomalies,
            "show_agent_logs": show_agent_logs,
            "show_raw_data": show_raw_data,
            "real_time_updates": real_time_updates
        })

def process_contract(uploaded_file, options):
    """Process the uploaded contract"""
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
        tmp_file.write(uploaded_file.read())
        contract_path = tmp_file.name
    
    try:
        # Create processing container
        processing_container = st.container()
        
        with processing_container:
            st.subheader("🔄 Processing Progress")
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Agent execution tracking
            if options["real_time_updates"]:
                agent_cols = st.columns(5)
                agent_status = {}
                
                for i, agent_name in enumerate(["Contract Reader", "Salary Breakdown", "Compliance Mapper", "Anomaly Detector", "Paystub Generator"]):
                    with agent_cols[i]:
                        agent_status[agent_name] = st.empty()
                        agent_status[agent_name].info(f"⏳ {agent_name}")
            
            # Start processing
            status_text.info("🚀 Starting payroll processing...")
            progress_bar.progress(10)
            
            # Initialize processor
            processor = MockPayrollProcessor(st.session_state.get('api_key', 'demo_key'))
            
            # Process the contract
            result = processor.process_contract(contract_path)
            
            # Update progress
            progress_bar.progress(100)
            status_text.success("✅ Processing completed successfully!")
            
            # Update agent status
            if options["real_time_updates"]:
                for agent_log in result.get('agent_logs', []):
                    agent_name = agent_log["agent"].replace("Agent", "").replace("_", " ").title()
                    if agent_name in agent_status:
                        if agent_log["success"]:
                            agent_status[agent_name].success(f"✅ {agent_name}")
                        else:
                            agent_status[agent_name].error(f"❌ {agent_name}")
            
            # Store result
            st.session_state.processing_results.append(result)
            st.session_state.current_result = result
            
            # Display results
            display_processing_result(result, options)
    
    except Exception as e:
        st.error(f"Processing failed: {e}")
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(contract_path)
        except:
            pass

def display_processing_result(result, options):
    """Display the processing result"""
    
    st.divider()
    st.subheader("📊 Processing Results")
    
    # Overall status
    if result.get('success'):
        st.success(f"✅ Processing completed successfully for employee: {result.get('employee_id', 'Unknown')}")
    else:
        st.error(f"❌ Processing failed for employee: {result.get('employee_id', 'Unknown')}")
    
    # Tabs for different result sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📄 Contract Data", "💰 Salary Breakdown", "⚖️ Compliance", "🔍 Anomalies", "📋 Documents"])
    
    with tab1:
        if result.get('contract_data'):
            display_contract_data(result['contract_data'], options)
        else:
            st.warning("No contract data available")
    
    with tab2:
        if result.get('salary_data'):
            display_salary_breakdown(result['salary_data'], options)
        else:
            st.warning("No salary data available")
    
    with tab3:
        if result.get('compliance_data'):
            display_compliance_data(result['compliance_data'], options)
        else:
            st.warning("No compliance data available")
    
    with tab4:
        if result.get('anomalies_data'):
            display_anomaly_data(result['anomalies_data'], options)
        else:
            st.warning("No anomaly data available")
    
    with tab5:
        if result.get('paystub_data'):
            display_documents(result['paystub_data'], options)
        else:
            st.warning("No paystub data available")

def display_contract_data(contract_data, options):
    """Display contract data"""
    st.subheader("📄 Extracted Contract Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Employee Information:**")
        for key, value in contract_data.get('employee_info', {}).items():
            st.write(f"• {key.title()}: {value}")
    
    with col2:
        st.write("**Salary Structure:**")
        for key, value in contract_data.get('salary_structure', {}).items():
            st.write(f"• {key.title()}: ₹{value:,.0f}")
    
    if options.get('show_raw_data'):
        st.subheader("📝 Raw Extracted Text")
        st.text(contract_data.get('extracted_text', 'No text available'))

def display_salary_breakdown(salary_data, options):
    """Display salary breakdown"""
    st.subheader("💰 Salary Breakdown")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Earnings:**")
        st.write(f"• Basic Salary: ₹{salary_data['basic_salary']:,.0f}")
        st.write(f"• HRA: ₹{salary_data['hra']:,.0f}")
        st.write(f"• Other Allowances: ₹{salary_data['allowances']:,.0f}")
        st.write(f"• **Gross Salary: ₹{salary_data['gross_salary']:,.0f}**")
    
    with col2:
        st.write("**Deductions:**")
        deductions = salary_data['deductions']
        st.write(f"• PF: ₹{deductions['pf']:,.0f}")
        st.write(f"• ESI: ₹{deductions['esi']:,.0f}")
        st.write(f"• Professional Tax: ₹{deductions['professional_tax']:,.0f}")
        st.write(f"• TDS: ₹{deductions['tds']:,.0f}")
        st.write(f"• **Total Deductions: ₹{deductions['total']:,.0f}**")
    
    st.divider()
    st.success(f"**Net Salary: ₹{salary_data['net_salary']:,.0f}**")

def display_compliance_data(compliance_data, options):
    """Display compliance data"""
    st.subheader("⚖️ Compliance Validation")
    
    status = compliance_data['compliance_status']
    if status == "COMPLIANT":
        st.success(f"✅ Status: {status}")
    else:
        st.error(f"❌ Status: {status}")
    
    st.write("**Applied Rules:**")
    for rule in compliance_data.get('applied_rules', []):
        st.write(f"• {rule}")
    
    st.write("**Recommendations:**")
    for rec in compliance_data.get('recommendations', []):
        st.write(f"• {rec}")
    
    st.write(f"**Confidence Score:** {compliance_data.get('confidence_score', 0):.1%}")

def display_anomaly_data(anomalies_data, options):
    """Display anomaly data"""
    st.subheader("🔍 Anomaly Detection")
    
    if anomalies_data.get('has_anomalies'):
        st.error("⚠️ Anomalies detected!")
        for anomaly in anomalies_data.get('anomalies', []):
            st.write(f"• {anomaly}")
    else:
        st.success("✅ No anomalies detected")
    
    st.write(f"**Status:** {anomalies_data.get('overall_status', 'Unknown')}")
    st.write(f"**Confidence Score:** {anomalies_data.get('confidence_score', 0):.1%}")
    
    if anomalies_data.get('review_notes'):
        st.write("**Review Notes:**")
        st.write(anomalies_data['review_notes'])

def display_documents(paystub_data, options):
    """Display generated documents"""
    st.subheader("📋 Generated Documents")
    
    st.write("**Paystub Information:**")
    st.write(f"• Employee: {paystub_data.get('employee_info', {}).get('name', 'Unknown')}")
    st.write(f"• Pay Period: {paystub_data.get('pay_period', 'Unknown')}")
    st.write(f"• Generated: {paystub_data.get('generated_date', 'Unknown')}")
    
    # Mock download button
    if st.button("📥 Download Paystub (PDF)"):
        st.info("Paystub download would be generated here in a real implementation")

def main():
    """Main application function"""
    
    # Sidebar configuration
    sidebar_config()
    
    # Page navigation
    page = st.session_state.get('page', 'dashboard')
    
    # Navigation menu
    st.sidebar.subheader("📍 Navigation")
    
    menu_options = {
        "🏠 Dashboard": "dashboard",
        "📤 Process Contract": "process"
    }
    
    for label, key in menu_options.items():
        if st.sidebar.button(label, key=f"nav_{key}"):
            st.session_state.page = key
            st.rerun()
    
    # Page routing
    if page == "dashboard":
        main_dashboard()
    elif page == "process":
        contract_processing_page()
    else:
        main_dashboard()

if __name__ == "__main__":
    main()