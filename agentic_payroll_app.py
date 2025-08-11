import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import tempfile
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Local imports
from payroll_workflow import PayrollAgenticWorkflow, create_payroll_workflow
from models import ProcessingResult

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
if 'workflow' not in st.session_state:
    st.session_state.workflow = None
if 'processing_results' not in st.session_state:
    st.session_state.processing_results = []
if 'current_result' not in st.session_state:
    st.session_state.current_result = None

def initialize_workflow():
    """Initialize the payroll workflow"""
    try:
        api_key = st.session_state.get('api_key')
        if not api_key:
            st.error("Please enter your Google API key in the sidebar")
            return None
        
        if st.session_state.workflow is None:
            with st.spinner("Initializing AgenticAI Payroll System..."):
                st.session_state.workflow = create_payroll_workflow(api_key)
        
        return st.session_state.workflow
    except Exception as e:
        st.error(f"Failed to initialize workflow: {e}")
        return None

def sidebar_config():
    """Configure the sidebar with settings and controls"""
    st.sidebar.title("🔧 Configuration")
    
    # API Key input
    api_key = st.sidebar.text_input(
        "Google API Key",
        type="password",
        value=st.session_state.get('api_key', ''),
        help="Enter your Google Gemini API key"
    )
    
    if api_key:
        st.session_state.api_key = api_key
        os.environ["GOOGLE_API_KEY"] = api_key
    
    st.sidebar.divider()
    
    # System status
    st.sidebar.subheader("📊 System Status")
    
    if st.session_state.workflow:
        st.sidebar.success("✅ System Ready")
        st.sidebar.info(f"📁 RAG Database: Available")
        st.sidebar.info(f"🤖 Agents: 5 Active")
    else:
        st.sidebar.warning("⚠️ System Not Initialized")
    
    st.sidebar.divider()
    
    # Quick Actions
    st.sidebar.subheader("🚀 Quick Actions")
    
    if st.sidebar.button("🔄 Reset System"):
        st.session_state.workflow = None
        st.session_state.processing_results = []
        st.session_state.current_result = None
        st.rerun()
    
    if st.sidebar.button("📊 View Analytics"):
        st.session_state.page = "analytics"
        st.rerun()
    
    # Recent Processing History
    st.sidebar.subheader("📋 Recent Processes")
    
    if st.session_state.processing_results:
        for i, result in enumerate(st.session_state.processing_results[-5:]):
            status_icon = "✅" if result.success else "❌"
            employee_id = result.employee_id if result.employee_id != "unknown" else f"Process {i+1}"
            
            if st.sidebar.button(f"{status_icon} {employee_id}", key=f"recent_{i}"):
                st.session_state.current_result = result
                st.session_state.page = "result_detail"
                st.rerun()

def main_dashboard():
    """Main dashboard page"""
    st.markdown('<h1 class="main-header">🤖 AgenticAI Payroll Processing System</h1>', unsafe_allow_html=True)
    
    # System overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Total Processed", len(st.session_state.processing_results))
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        successful = sum(1 for r in st.session_state.processing_results if r.success)
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Successful", successful)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        failed = len(st.session_state.processing_results) - successful
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Failed", failed)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        avg_time = sum(r.processing_time or 0 for r in st.session_state.processing_results) / max(len(st.session_state.processing_results), 1)
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Avg Time (s)", f"{avg_time:.1f}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Agent workflow visualization
    st.subheader("🔄 5-Agent Workflow")
    
    agent_info = [
        {
            "name": "Contract Reader Agent",
            "description": "Extracts and parses employee contract data from PDF documents",
            "icon": "📄",
            "status": "ready"
        },
        {
            "name": "Salary Breakdown Agent", 
            "description": "Calculates comprehensive salary breakdown with all deductions",
            "icon": "💰",
            "status": "ready"
        },
        {
            "name": "Compliance Mapper Agent",
            "description": "RAG-enabled validation against latest government rules",
            "icon": "⚖️",
            "status": "ready"
        },
        {
            "name": "Anomaly Detector Agent",
            "description": "Detects calculation errors and data inconsistencies",
            "icon": "🔍",
            "status": "ready"
        },
        {
            "name": "Paystub Generator Agent",
            "description": "Generates professional paystubs and tax documents",
            "icon": "📋",
            "status": "ready"
        }
    ]
    
    for i, agent in enumerate(agent_info):
        with st.container():
            st.markdown(f"""
            <div class="agent-card">
                <h4>{agent['icon']} {agent['name']}</h4>
                <p>{agent['description']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if i < len(agent_info) - 1:
                st.markdown("<div style='text-align: center; margin: 1rem 0;'>⬇️</div>", unsafe_allow_html=True)

def contract_processing_page():
    """Contract processing page"""
    st.title("📤 Process Employment Contract")
    
    workflow = initialize_workflow()
    if not workflow:
        return
    
    # File upload
    st.subheader("📁 Upload Contract")
    uploaded_file = st.file_uploader(
        "Choose an employment contract PDF",
        type=["pdf"],
        help="Upload a PDF employment contract for processing"
    )
    
    # Processing options
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚙️ Processing Options")
        
        auto_validate = st.checkbox("Auto-validate compliance", value=True, help="Automatically validate against compliance rules")
        generate_paystub = st.checkbox("Generate paystub", value=True, help="Generate downloadable paystub PDF")
        detect_anomalies = st.checkbox("Detect anomalies", value=True, help="Run anomaly detection")
    
    with col2:
        st.subheader("📊 Preview Settings")
        
        show_agent_logs = st.checkbox("Show agent execution logs", value=False)
        show_raw_data = st.checkbox("Show raw extracted data", value=False)
        real_time_updates = st.checkbox("Real-time processing updates", value=True)
    
    # Process button
    if uploaded_file and st.button("🚀 Process Contract", type="primary"):
        process_contract(uploaded_file, workflow, {
            "auto_validate": auto_validate,
            "generate_paystub": generate_paystub,
            "detect_anomalies": detect_anomalies,
            "show_agent_logs": show_agent_logs,
            "show_raw_data": show_raw_data,
            "real_time_updates": real_time_updates
        })

def process_contract(uploaded_file, workflow, options):
    """Process the uploaded contract"""
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
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
            agent_status_container = st.container()
            
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
            
            # Process the contract
            result = workflow.process_contract_sync(contract_path)
            
            # Update progress based on result
            if result.success:
                progress_bar.progress(100)
                status_text.success("✅ Processing completed successfully!")
                
                # Update agent status
                if options["real_time_updates"]:
                    for agent_log in result.agent_logs:
                        agent_name = agent_log["agent"].replace("Agent", "").replace("_", " ").title()
                        if agent_name in agent_status:
                            if agent_log["success"]:
                                agent_status[agent_name].success(f"✅ {agent_name}")
                            else:
                                agent_status[agent_name].error(f"❌ {agent_name}")
            else:
                progress_bar.progress(50)
                status_text.error("❌ Processing failed!")
            
            # Store result
            st.session_state.processing_results.append(result)
            st.session_state.current_result = result
            
            # Display results
            display_processing_result(result, options)
    
    except Exception as e:
        st.error(f"Processing failed: {e}")
        logger.error(f"Contract processing error: {e}")
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(contract_path)
        except:
            pass

def display_processing_result(result: ProcessingResult, options: Dict[str, Any]):
    """Display the processing result"""
    
    st.divider()
    st.subheader("📊 Processing Results")
    
    # Overall status
    if result.success:
        st.success(f"✅ Processing completed successfully for employee: {result.employee_id}")
    else:
        st.error(f"❌ Processing failed for employee: {result.employee_id}")
        if result.errors:
            st.error("Errors encountered:")
            for error in result.errors:
                st.write(f"• {error}")
    
    # Tabs for different result sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📄 Contract Data", "💰 Salary Breakdown", "⚖️ Compliance", "🔍 Anomalies", "📋 Documents"])
    
    with tab1:
        if result.contract_data:
            display_contract_data(result.contract_data, options)
        else:
            st.warning("No contract data available")
    
    with tab2:
        if result.salary_data:
            display_salary_breakdown(result.salary_data, options)
        else:
            st.warning("No salary data available")
    
    with tab3:
        if result.compliance_data:
            display_compliance_data(result.compliance_data, options)
        else:
            st.warning("No compliance data available")
    
    with tab4:
        if result.anomalies_data:
            display_anomaly_data(result.anomalies_data, options)
        else:
            st.warning("No anomaly data available")
    
    with tab5:
        if result.paystub_data:
            display_documents(result.paystub_data, options)
        else:
            st.warning("No documents generated")

def display_contract_data(contract_data, options):
    """Display contract data"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👤 Employee Information")
        emp_info = contract_data.employee_info
        
        info_data = {
            "Name": emp_info.employee_name or "N/A",
            "Employee ID": emp_info.employee_id or "N/A",
            "Department": emp_info.department or "N/A",
            "Designation": emp_info.designation or "N/A",
            "Location": emp_info.location or "N/A",
            "Joining Date": emp_info.joining_date or "N/A"
        }
        
        for key, value in info_data.items():
            st.write(f"**{key}:** {value}")
    
    with col2:
        st.subheader("💵 Salary Structure")
        salary_struct = contract_data.salary_structure
        
        if salary_struct.gross:
            st.metric("Gross Salary", f"₹{salary_struct.gross:,.2f}")
        if salary_struct.basic:
            st.metric("Basic Salary", f"₹{salary_struct.basic:,.2f}")
        if salary_struct.hra:
            st.metric("HRA", f"₹{salary_struct.hra:,.2f}")
        if salary_struct.allowances:
            st.metric("Allowances", f"₹{salary_struct.allowances:,.2f}")
    
    # Parsing confidence
    if contract_data.parsing_confidence:
        st.metric("Parsing Confidence", f"{contract_data.parsing_confidence:.2%}")
    
    # Notes
    if contract_data.notes:
        st.subheader("📝 Notes")
        st.info(contract_data.notes)
    
    # Raw data if requested
    if options.get("show_raw_data"):
        st.subheader("🔍 Raw Extracted Text")
        with st.expander("View raw contract text"):
            st.text(contract_data.extracted_text[:2000] + "..." if len(contract_data.extracted_text) > 2000 else contract_data.extracted_text)

def display_salary_breakdown(salary_data, options):
    """Display salary breakdown with visualizations"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Earnings")
        
        earnings = {
            "Basic Salary": salary_data.basic_salary,
            "HRA": salary_data.hra,
            "Allowances": salary_data.allowances
        }
        
        for component, amount in earnings.items():
            st.metric(component, f"₹{amount:,.2f}")
        
        st.metric("**Gross Salary**", f"₹{salary_data.gross_salary:,.2f}")
    
    with col2:
        st.subheader("💸 Deductions")
        
        deductions = salary_data.deductions
        deduction_items = {
            "PF": deductions.pf,
            "ESI": deductions.esi,
            "Professional Tax": deductions.professional_tax,
            "TDS": deductions.tds,
            "Advance": deductions.advance,
            "Loan": deductions.loan_deduction,
            "Others": deductions.other_deductions
        }
        
        total_deductions = sum(deduction_items.values())
        
        for component, amount in deduction_items.items():
            if amount > 0:
                st.metric(component, f"₹{amount:,.2f}")
        
        st.metric("**Total Deductions**", f"₹{total_deductions:,.2f}")
    
    # Net salary highlight
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.metric(
            "**🎯 Net Salary**", 
            f"₹{salary_data.net_salary:,.2f}",
            delta=f"₹{salary_data.gross_salary - total_deductions:,.2f} from gross"
        )
    
    # Salary visualization
    st.subheader("📊 Salary Breakdown Chart")
    
    # Pie chart for salary components
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "pie"}, {"type": "pie"}]],
        subplot_titles=("Earnings Breakdown", "Deductions Breakdown")
    )
    
    # Earnings pie chart
    earnings_labels = list(earnings.keys())
    earnings_values = list(earnings.values())
    
    fig.add_trace(go.Pie(
        labels=earnings_labels,
        values=earnings_values,
        name="Earnings"
    ), row=1, col=1)
    
    # Deductions pie chart (only non-zero values)
    deduction_labels = [k for k, v in deduction_items.items() if v > 0]
    deduction_values = [v for v in deduction_items.values() if v > 0]
    
    if deduction_values:
        fig.add_trace(go.Pie(
            labels=deduction_labels,
            values=deduction_values,
            name="Deductions"
        ), row=1, col=2)
    
    fig.update_layout(showlegend=True, height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Calculation notes
    if salary_data.calculation_notes:
        st.subheader("📝 Calculation Notes")
        st.info(salary_data.calculation_notes)

def display_compliance_data(compliance_data, options):
    """Display compliance validation results"""
    
    # Compliance status
    status_color = {
        "COMPLIANT": "success",
        "NON_COMPLIANT": "error", 
        "REVIEW_REQUIRED": "warning"
    }
    
    status_icon = {
        "COMPLIANT": "✅",
        "NON_COMPLIANT": "❌",
        "REVIEW_REQUIRED": "⚠️"
    }
    
    status = compliance_data.compliance_status
    getattr(st, status_color[status])(f"{status_icon[status]} Compliance Status: {status}")
    
    # Confidence score
    st.metric("Confidence Score", f"{compliance_data.confidence_score:.2%}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚠️ Issues Found")
        if compliance_data.issues:
            for i, issue in enumerate(compliance_data.issues, 1):
                st.write(f"{i}. {issue}")
        else:
            st.success("No compliance issues found!")
    
    with col2:
        st.subheader("💡 Recommendations")
        if compliance_data.recommendations:
            for i, rec in enumerate(compliance_data.recommendations, 1):
                st.write(f"{i}. {rec}")
        else:
            st.info("No recommendations at this time.")
    
    # Applied rules
    st.subheader("📜 Applied Compliance Rules")
    for rule in compliance_data.applied_rules:
        st.write(f"• {rule}")
    
    # Validated deductions
    st.subheader("✅ Validated Deductions")
    validated = compliance_data.validated_deductions
    
    deduction_comparison = {
        "PF": validated.pf,
        "ESI": validated.esi,
        "Professional Tax": validated.professional_tax,
        "TDS": validated.tds
    }
    
    for component, amount in deduction_comparison.items():
        st.metric(component, f"₹{amount:,.2f}")

def display_anomaly_data(anomalies_data, options):
    """Display anomaly detection results"""
    
    # Overall status
    status_color = {
        "NORMAL": "success",
        "REVIEW_REQUIRED": "warning",
        "CRITICAL": "error"
    }
    
    status_icon = {
        "NORMAL": "✅",
        "REVIEW_REQUIRED": "⚠️", 
        "CRITICAL": "🚨"
    }
    
    status = anomalies_data.overall_status
    getattr(st, status_color[status])(f"{status_icon[status]} Anomaly Status: {status}")
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Anomalies Found", len(anomalies_data.anomalies))
    
    with col2:
        st.metric("Confidence Score", f"{anomalies_data.confidence_score:.2%}")
    
    with col3:
        critical_count = sum(1 for a in anomalies_data.anomalies if a.severity == "CRITICAL")
        st.metric("Critical Issues", critical_count)
    
    # Anomaly details
    if anomalies_data.anomalies:
        st.subheader("🔍 Detected Anomalies")
        
        for i, anomaly in enumerate(anomalies_data.anomalies, 1):
            severity_color = {
                "LOW": "info",
                "MEDIUM": "warning", 
                "HIGH": "error",
                "CRITICAL": "error"
            }
            
            with st.expander(f"Anomaly {i}: {anomaly.description}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Type:** {anomaly.type}")
                    st.write(f"**Severity:** {anomaly.severity}")
                    st.write(f"**Affected Field:** {anomaly.affected_field}")
                
                with col2:
                    st.write(f"**Confidence:** {anomaly.confidence:.2%}")
                    if anomaly.suggested_action:
                        st.write(f"**Suggested Action:** {anomaly.suggested_action}")
    
    # Review notes
    if anomalies_data.review_notes:
        st.subheader("📝 Review Notes")
        st.info(anomalies_data.review_notes)

def display_documents(paystub_data, options):
    """Display generated documents"""
    
    st.subheader("📋 Generated Documents")
    
    # Paystub information
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Employee:** {paystub_data.employee_info.employee_name}")
        st.write(f"**Pay Period:** {paystub_data.pay_period}")
        st.write(f"**Generated:** {paystub_data.generated_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    with col2:
        st.write(f"**Template Version:** {paystub_data.template_version}")
        st.write(f"**Net Salary:** ₹{paystub_data.salary_breakdown.net_salary:,.2f}")
    
    # Download button
    if hasattr(paystub_data, 'pdf_path') and paystub_data.pdf_path:
        try:
            with open(paystub_data.pdf_path, 'rb') as pdf_file:
                pdf_data = pdf_file.read()
            
            st.download_button(
                label="📥 Download Paystub PDF",
                data=pdf_data,
                file_name=f"paystub_{paystub_data.employee_info.employee_id or 'employee'}_{paystub_data.pay_period.replace(' ', '_')}.pdf",
                mime="application/pdf",
                type="primary"
            )
        except Exception as e:
            st.error(f"Error loading PDF: {e}")
    
    # JSON export
    if st.button("📄 Export as JSON"):
        try:
            # Create export data
            export_data = {
                "employee_info": paystub_data.employee_info.dict(),
                "salary_breakdown": paystub_data.salary_breakdown.dict(),
                "compliance_info": paystub_data.compliance_info.dict(),
                "pay_period": paystub_data.pay_period,
                "generated_date": paystub_data.generated_date.isoformat()
            }
            
            json_data = json.dumps(export_data, indent=2, default=str)
            
            st.download_button(
                label="📥 Download JSON Data",
                data=json_data,
                file_name=f"payroll_data_{paystub_data.employee_info.employee_id or 'employee'}.json",
                mime="application/json"
            )
        except Exception as e:
            st.error(f"Error exporting JSON: {e}")

def analytics_page():
    """Analytics and reporting page"""
    st.title("📊 Analytics & Reports")
    
    if not st.session_state.processing_results:
        st.info("No processing results available. Process some contracts first!")
        return
    
    results = st.session_state.processing_results
    
    # Summary metrics
    st.subheader("📈 Summary Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Processed", len(results))
    
    with col2:
        success_rate = sum(1 for r in results if r.success) / len(results) * 100
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    with col3:
        avg_time = sum(r.processing_time or 0 for r in results) / len(results)
        st.metric("Avg Processing Time", f"{avg_time:.1f}s")
    
    with col4:
        total_employees = len([r for r in results if r.success and r.contract_data])
        st.metric("Employees Processed", total_employees)
    
    # Processing trends
    st.subheader("📊 Processing Trends")
    
    if len(results) > 1:
        # Create trend data
        trend_data = []
        for i, result in enumerate(results):
            trend_data.append({
                "Process #": i + 1,
                "Success": result.success,
                "Processing Time": result.processing_time or 0,
                "Employee ID": result.employee_id
            })
        
        df = pd.DataFrame(trend_data)
        
        # Success rate over time
        fig = px.line(df, x="Process #", y="Processing Time", 
                     title="Processing Time Trend",
                     labels={"Processing Time": "Time (seconds)"})
        st.plotly_chart(fig, use_container_width=True)
    
    # Salary analytics
    if any(r.salary_data for r in results if r.success):
        st.subheader("💰 Salary Analytics")
        
        salary_data = []
        for result in results:
            if result.success and result.salary_data:
                salary_data.append({
                    "Employee": result.employee_id,
                    "Gross Salary": result.salary_data.gross_salary,
                    "Net Salary": result.salary_data.net_salary,
                    "Total Deductions": sum(result.salary_data.deductions.dict().values())
                })
        
        if salary_data:
            df_salary = pd.DataFrame(salary_data)
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.box(df_salary, y="Gross Salary", title="Gross Salary Distribution")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.scatter(df_salary, x="Gross Salary", y="Net Salary", 
                               title="Gross vs Net Salary",
                               hover_data=["Employee"])
                st.plotly_chart(fig, use_container_width=True)

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
        "📤 Process Contract": "process",
        "📊 Analytics": "analytics"
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
    elif page == "analytics":
        analytics_page()
    elif page == "result_detail" and st.session_state.current_result:
        st.title("📋 Processing Result Details")
        display_processing_result(st.session_state.current_result, {
            "show_agent_logs": True,
            "show_raw_data": True
        })
    else:
        main_dashboard()

if __name__ == "__main__":
    main()