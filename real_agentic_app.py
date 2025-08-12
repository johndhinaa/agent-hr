import streamlit as st
import pandas as pd
import json
import tempfile
import os
import asyncio
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
    .ai-agent {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processing_results' not in st.session_state:
    st.session_state.processing_results = []
if 'current_result' not in st.session_state:
    st.session_state.current_result = None
if 'workflow' not in st.session_state:
    st.session_state.workflow = None

def initialize_workflow():
    """Initialize the real AI agent workflow"""
    try:
        api_key = st.session_state.get('api_key')
        if not api_key:
            st.error("Please enter your Google API key in the sidebar")
            return None
        
        if st.session_state.workflow is None:
            with st.spinner("Initializing Real AgenticAI Payroll System..."):
                try:
                    from real_workflow import create_real_payroll_workflow
                    st.session_state.workflow = create_real_payroll_workflow(api_key)
                    st.success("✅ Real AgenticAI Payroll System initialized successfully!")
                except Exception as e:
                    st.error(f"Failed to initialize workflow: {e}")
                    return None
        
        return st.session_state.workflow
    except Exception as e:
        st.error(f"Failed to initialize workflow: {e}")
        return None

def sidebar_config():
    """Configure the sidebar"""
    st.sidebar.title("🔧 Configuration")
    
    # API Key input
    api_key = st.sidebar.text_input(
        "Google API Key",
        type="password",
        value=st.session_state.get('api_key', ''),
        help="Enter your Google Gemini API key (required for AI agents)"
    )
    
    if api_key:
        st.session_state.api_key = api_key
        # Reset workflow when API key changes
        if api_key != st.session_state.get('previous_api_key'):
            st.session_state.workflow = None
            st.session_state.previous_api_key = api_key
    
    # System status
    st.sidebar.subheader("📊 System Status")
    
    if st.session_state.workflow:
        st.sidebar.success("✅ Real AI Agents Active")
        st.sidebar.info("🤖 5 AI Agents Ready")
        st.sidebar.info("🔄 LangGraph Workflow Active")
    else:
        st.sidebar.warning("⚠️ AI Agents Not Initialized")
    
    # Processing options
    st.sidebar.subheader("⚙️ AI Agent Options")
    st.sidebar.checkbox("Use RAG for compliance", value=True, key="use_rag")
    st.sidebar.checkbox("Show agent confidence scores", value=True, key="show_confidence")
    st.sidebar.checkbox("Real-time agent updates", value=True, key="real_time_updates")
    
    # Clear results button
    if st.sidebar.button("🗑️ Clear All Results"):
        st.session_state.processing_results = []
        st.session_state.current_result = None
        st.rerun()

def main_dashboard():
    """Main dashboard page"""
    st.markdown('<h1 class="main-header">🤖 Real AgenticAI Payroll System</h1>', unsafe_allow_html=True)
    
    # AI Agent Overview
    st.markdown("""
    <div class="ai-agent">
        <h3>🤖 Real AI Agents Powered by Gemini LLM</h3>
        <p>This system uses 5 specialized AI agents with LangGraph workflow orchestration:</p>
        <ul>
            <li>📄 Contract Reader Agent - Extracts structured data from contracts</li>
            <li>💰 Salary Breakdown Agent - Calculates earnings and deductions</li>
            <li>⚖️ Compliance Mapper Agent - Validates against tax rules (RAG-enabled)</li>
            <li>🔍 Anomaly Detector Agent - Identifies calculation errors</li>
            <li>📋 Paystub Generator Agent - Creates professional documents</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
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
            <h3>🤖 AI Agents</h3>
            <h2>5 Active</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Recent processing results
    if st.session_state.processing_results:
        st.subheader("📋 Recent AI Agent Processing Results")
        
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
                
                # Show agent confidence scores
                if st.session_state.get('show_confidence') and result.get('agent_logs'):
                    st.write("**AI Agent Confidence Scores:**")
                    for log in result['agent_logs']:
                        if log.get('confidence_score'):
                            st.write(f"• {log['agent']}: {log['confidence_score']:.1%}")
                
                if st.button(f"View Details", key=f"view_{i}"):
                    st.session_state.current_result = result
                    st.rerun()
    else:
        st.info("📊 No processing results available. Process some contracts with AI agents first!")

def contract_processing_page():
    """Contract processing page with real AI agents"""
    st.title("📤 Process Employment Contract with AI Agents")
    
    workflow = initialize_workflow()
    if not workflow:
        st.warning("Please enter your Google API key in the sidebar to initialize the AI agents.")
        return
    
    # File upload
    st.subheader("📁 Upload Contract")
    uploaded_file = st.file_uploader(
        "Choose an employment contract file",
        type=["txt", "pdf"],
        help="Upload a contract file for AI agent processing"
    )
    
    # Processing options
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚙️ AI Agent Options")
        auto_validate = st.checkbox("Auto-validate compliance", value=True, help="Use AI agent for compliance validation")
        generate_paystub = st.checkbox("Generate paystub", value=True, help="Use AI agent for paystub generation")
        detect_anomalies = st.checkbox("Detect anomalies", value=True, help="Use AI agent for anomaly detection")
    
    with col2:
        st.subheader("📊 Preview Settings")
        show_agent_logs = st.checkbox("Show agent execution logs", value=True)
        show_raw_data = st.checkbox("Show raw extracted data", value=False)
        real_time_updates = st.checkbox("Real-time agent updates", value=st.session_state.get("real_time_updates", True))
    
    # Process button
    if uploaded_file and st.button("🚀 Process with AI Agents", type="primary"):
        process_contract_with_ai(uploaded_file, {
            "auto_validate": auto_validate,
            "generate_paystub": generate_paystub,
            "detect_anomalies": detect_anomalies,
            "show_agent_logs": show_agent_logs,
            "show_raw_data": show_raw_data,
            "real_time_updates": real_time_updates
        })

def process_contract_with_ai(uploaded_file, options):
    """Process the uploaded contract with real AI agents"""
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
        tmp_file.write(uploaded_file.read())
        contract_path = tmp_file.name
    
    try:
        # Create processing container
        processing_container = st.container()
        
        with processing_container:
            st.subheader("🔄 AI Agent Processing Progress")
            
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
            status_text.info("🚀 Starting AI agent payroll processing...")
            progress_bar.progress(10)
            
            # Process with real AI agents
            workflow = st.session_state.workflow
            result = workflow.process_contract_sync(contract_path)
            
            # Update progress
            progress_bar.progress(100)
            
            if result and result.success:
                status_text.success("✅ AI agent processing completed successfully!")
                
                # Update agent status
                if options["real_time_updates"] and result.agent_logs:
                    for agent_log in result.agent_logs:
                        agent_name = agent_log["agent"].replace("Agent", "").replace("_", " ").title()
                        if agent_name in agent_status:
                            if agent_log["success"]:
                                confidence = agent_log.get("confidence_score", 0)
                                agent_status[agent_name].success(f"✅ {agent_name} ({confidence:.1%})")
                            else:
                                agent_status[agent_name].error(f"❌ {agent_name}")
            else:
                status_text.error("❌ AI agent processing failed!")
                if result and result.errors:
                    for error in result.errors:
                        st.error(f"Error: {error}")
            
            # Store result
            if result:
                st.session_state.processing_results.append(result)
                st.session_state.current_result = result
                
                # Display results
                display_ai_processing_result(result, options)
    
    except Exception as e:
        st.error(f"AI agent processing failed: {e}")
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(contract_path)
        except:
            pass

def display_ai_processing_result(result, options):
    """Display the AI agent processing result"""
    
    st.divider()
    st.subheader("📊 AI Agent Processing Results")
    
    # Overall status
    if result.get('success'):
        st.success(f"✅ AI agent processing completed successfully for employee: {result.get('employee_id', 'Unknown')}")
    else:
        st.error(f"❌ AI agent processing failed for employee: {result.get('employee_id', 'Unknown')}")
    
    # AI Agent Performance
    if result.get('agent_logs'):
        st.subheader("🤖 AI Agent Performance")
        
        agent_data = []
        for log in result['agent_logs']:
            agent_data.append({
                "Agent": log['agent'].replace("Agent", "").replace("_", " ").title(),
                "Status": "✅ Success" if log['success'] else "❌ Failed",
                "Execution Time": f"{log['execution_time']:.2f}s",
                "Confidence": f"{log.get('confidence_score', 0):.1%}" if log.get('confidence_score') else "N/A"
            })
        
        df_agents = pd.DataFrame(agent_data)
        st.dataframe(df_agents, use_container_width=True)
    
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
    """Display contract data extracted by AI agent"""
    st.subheader("📄 AI-Extracted Contract Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Employee Information:**")
        for key, value in contract_data.get('employee_info', {}).items():
            if value:
                st.write(f"• {key.title()}: {value}")
    
    with col2:
        st.write("**Salary Structure:**")
        for key, value in contract_data.get('salary_structure', {}).items():
            if value:
                if isinstance(value, (int, float)):
                    st.write(f"• {key.title()}: ₹{value:,.0f}")
                else:
                    st.write(f"• {key.title()}: {value}")
    
    if options.get('show_raw_data'):
        st.subheader("📝 Raw Extracted Text")
        st.text(contract_data.get('extracted_text', 'No text available'))

def display_salary_breakdown(salary_data, options):
    """Display salary breakdown calculated by AI agent"""
    st.subheader("💰 AI-Calculated Salary Breakdown")
    
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
    
    if salary_data.get('calculation_notes'):
        st.info(f"**AI Calculation Notes:** {salary_data['calculation_notes']}")

def display_compliance_data(compliance_data, options):
    """Display compliance validation by AI agent"""
    st.subheader("⚖️ AI Compliance Validation")
    
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
    
    st.write(f"**AI Confidence Score:** {compliance_data.get('confidence_score', 0):.1%}")

def display_anomaly_data(anomalies_data, options):
    """Display anomaly detection by AI agent"""
    st.subheader("🔍 AI Anomaly Detection")
    
    if anomalies_data.get('has_anomalies'):
        st.error("⚠️ AI detected anomalies!")
        for anomaly in anomalies_data.get('anomalies', []):
            st.write(f"• **{anomaly.type}** ({anomaly.severity}): {anomaly.description}")
            if anomaly.suggested_action:
                st.write(f"  → Suggested: {anomaly.suggested_action}")
    else:
        st.success("✅ AI found no anomalies")
    
    st.write(f"**Overall Status:** {anomalies_data.get('overall_status', 'Unknown')}")
    st.write(f"**AI Confidence Score:** {anomalies_data.get('confidence_score', 0):.1%}")
    
    if anomalies_data.get('review_notes'):
        st.write("**AI Review Notes:**")
        st.write(anomalies_data['review_notes'])

def display_documents(paystub_data, options):
    """Display generated documents by AI agent"""
    st.subheader("📋 AI-Generated Documents")
    
    st.write("**Paystub Information:**")
    st.write(f"• Employee: {paystub_data.get('employee_info', {}).get('name', 'Unknown')}")
    st.write(f"• Pay Period: {paystub_data.get('pay_period', 'Unknown')}")
    st.write(f"• Generated: {paystub_data.get('generated_date', 'Unknown')}")
    st.write(f"• Template Version: {paystub_data.get('template_version', 'Unknown')}")
    
    # Mock download button
    if st.button("📥 Download AI-Generated Paystub (PDF)"):
        st.info("AI-generated paystub download would be created here")

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
        "📤 Process with AI": "process"
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