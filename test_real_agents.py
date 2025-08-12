#!/usr/bin/env python3

"""
Test script for Real AgenticAI Payroll System
This script tests the real AI agents using Gemini LLM and LangGraph workflow.
"""

import os
import sys
import tempfile
import json
from datetime import datetime

def test_real_agents():
    """Test the real AI agents with Gemini LLM"""
    print("🧪 Testing Real AI Agents with Gemini LLM...")
    
    try:
        # Import the real agents
        from real_agents import ContractReaderAgent, SalaryBreakdownAgent
        from real_workflow import create_real_payroll_workflow
        
        # Check if API key is available
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            print("❌ No Google API key found. Set GOOGLE_API_KEY environment variable.")
            print("   You can get a free API key from: https://makersuite.google.com/app/apikey")
            return False
        
        # Create a test contract
        test_contract_content = """
EMPLOYMENT CONTRACT

Employee Information:
Employee Name: John Doe
Employee ID: EMP001
Department: Engineering
Designation: Senior Software Engineer
Location: Bangalore, Karnataka
Joining Date: January 15, 2024
PAN Number: ABCDE1234F
PF Number: PF123456789
ESI Number: ESI987654321

Salary Structure:
Basic Salary: ₹50,000 per month
House Rent Allowance (HRA): ₹20,000 per month
Special Allowance: ₹15,000 per month
Medical Allowance: ₹1,250 per month
Transport Allowance: ₹1,600 per month
Meal Allowance: ₹2,200 per month
Variable Pay: ₹10,000 per month (performance-based)
Annual Bonus: ₹60,000 (paid annually)

Benefits:
• Provident Fund (PF): 12% of Basic Salary (capped at ₹15,000)
• Employee State Insurance (ESI): 1.75% of Gross Salary
• Professional Tax: As per Karnataka state rules
• Income Tax: As per applicable tax slabs
• Gratuity: As per Payment of Gratuity Act, 1972
"""
        
        # Create temporary contract file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_contract_content)
            contract_path = f.name
        
        print("✅ Created test contract file")
        
        # Test individual agents
        print("\n📄 Testing Contract Reader AI Agent...")
        contract_agent = ContractReaderAgent(api_key)
        contract_result = contract_agent.execute(contract_path)
        
        if contract_result.success:
            print("✅ Contract Reader AI Agent successful!")
            print(f"   - Employee: {contract_result.output.employee_info.employee_name}")
            print(f"   - Employee ID: {contract_result.output.employee_info.employee_id}")
            print(f"   - Basic Salary: ₹{contract_result.output.salary_structure.basic:,.0f}")
            print(f"   - Execution Time: {contract_result.execution_time:.2f}s")
            print(f"   - Confidence: {contract_result.confidence_score:.1%}")
        else:
            print(f"❌ Contract Reader AI Agent failed: {contract_result.error_message}")
            return False
        
        # Test salary breakdown agent
        print("\n💰 Testing Salary Breakdown AI Agent...")
        salary_agent = SalaryBreakdownAgent(api_key)
        salary_result = salary_agent.execute(contract_result.output)
        
        if salary_result.success:
            print("✅ Salary Breakdown AI Agent successful!")
            print(f"   - Gross Salary: ₹{salary_result.output.gross_salary:,.0f}")
            print(f"   - Net Salary: ₹{salary_result.output.net_salary:,.0f}")
            print(f"   - PF Deduction: ₹{salary_result.output.deductions.pf:,.0f}")
            print(f"   - Execution Time: {salary_result.execution_time:.2f}s")
            print(f"   - Confidence: {salary_result.confidence_score:.1%}")
        else:
            print(f"❌ Salary Breakdown AI Agent failed: {salary_result.error_message}")
            return False
        
        # Test full workflow
        print("\n🔄 Testing Full LangGraph Workflow...")
        workflow = create_real_payroll_workflow(api_key)
        workflow_result = workflow.process_contract_sync(contract_path)
        
        if workflow_result.success:
            print("✅ Full AI Agent Workflow successful!")
            print(f"   - Employee ID: {workflow_result.employee_id}")
            print(f"   - Total Processing Time: {workflow_result.processing_time:.2f}s")
            print(f"   - Success: {workflow_result.success}")
            
            # Show agent performance
            print("\n🤖 AI Agent Performance Summary:")
            for log in workflow_result.agent_logs:
                status = "✅ Success" if log['success'] else "❌ Failed"
                confidence = f"{log.get('confidence_score', 0):.1%}" if log.get('confidence_score') else "N/A"
                print(f"   • {log['agent']}: {status} ({log['execution_time']:.2f}s, {confidence})")
        else:
            print(f"❌ Full AI Agent Workflow failed: {workflow_result.errors}")
            return False
        
        # Clean up
        os.unlink(contract_path)
        
        print("\n🎉 All Real AI Agent tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Real AI Agent test failed: {e}")
        return False

def test_workflow_components():
    """Test individual workflow components"""
    print("🧪 Testing Workflow Components...")
    
    try:
        # Test imports
        from real_workflow import RealPayrollAgenticWorkflow
        from real_agents import (
            ContractReaderAgent, SalaryBreakdownAgent, ComplianceMapperAgent,
            AnomalyDetectorAgent, PaystubGeneratorAgent
        )
        
        print("✅ All workflow components imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Workflow component test failed: {e}")
        return False

def run_all_tests():
    """Run all tests for the real AI agent system"""
    print("🚀 Starting Real AgenticAI Payroll System Tests")
    print("=" * 60)
    
    tests = [
        ("Workflow Components", test_workflow_components),
        ("Real AI Agents", test_real_agents)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} test...")
        if test_func():
            passed += 1
        else:
            print(f"⚠️  {test_name} test failed")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Real AI Agent tests passed! The system is ready to use.")
        print("\n📝 Next steps:")
        print("1. Set your Google API key: export GOOGLE_API_KEY='your_key_here'")
        print("2. Run 'streamlit run real_agentic_app.py' to start the AI agent interface")
        print("3. Open http://localhost:8501 in your browser")
        print("4. Upload a contract file to test the real AI agents")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("\n💡 Make sure you have:")
        print("   - Google Gemini API key set as GOOGLE_API_KEY environment variable")
        print("   - All required dependencies installed")
        print("   - Internet connection for API calls")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)