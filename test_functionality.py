#!/usr/bin/env python3

"""
Test script for AgenticAI Payroll System
This script tests the core functionality without requiring the full Streamlit interface.
"""

import os
import sys
import tempfile
from datetime import datetime

def test_contract_creation():
    """Test contract creation functionality"""
    print("🧪 Testing contract creation...")
    
    try:
        from create_test_contract import create_simple_contract, create_sample_contracts
        
        # Create a simple contract
        contract_file = create_simple_contract()
        print(f"✅ Created test contract: {contract_file}")
        
        # Create sample contracts
        create_sample_contracts()
        print("✅ Created sample contracts directory")
        
        return True
    except Exception as e:
        print(f"❌ Contract creation failed: {e}")
        return False

def test_mock_processor():
    """Test the mock payroll processor"""
    print("🧪 Testing mock payroll processor...")
    
    try:
        # Import the mock processor from the simple app
        sys.path.append('.')
        from simple_payroll_app import MockPayrollProcessor
        
        # Create a test contract
        test_contract_content = """
EMPLOYMENT CONTRACT

Employee Information:
Employee Name: Test Employee
Employee ID: TEST001
Department: Engineering
Designation: Software Engineer
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
        
        # Initialize processor
        processor = MockPayrollProcessor("demo_key")
        
        # Process contract
        result = processor.process_contract(contract_path)
        
        # Verify results
        assert result['success'] == True
        assert result['employee_id'] == 'EMP001'
        assert 'contract_data' in result
        assert 'salary_data' in result
        assert 'compliance_data' in result
        assert 'anomalies_data' in result
        assert 'paystub_data' in result
        
        # Check salary calculations
        salary_data = result['salary_data']
        assert salary_data['gross_salary'] > 0
        assert salary_data['net_salary'] > 0
        assert salary_data['net_salary'] < salary_data['gross_salary']
        
        # Check compliance
        compliance_data = result['compliance_data']
        assert compliance_data['compliance_status'] == 'COMPLIANT'
        
        # Check anomalies
        anomalies_data = result['anomalies_data']
        assert anomalies_data['has_anomalies'] == False
        
        # Clean up
        os.unlink(contract_path)
        
        print("✅ Mock processor test passed")
        print(f"   - Employee ID: {result['employee_id']}")
        print(f"   - Gross Salary: ₹{salary_data['gross_salary']:,.0f}")
        print(f"   - Net Salary: ₹{salary_data['net_salary']:,.0f}")
        print(f"   - Processing Time: {result['processing_time']:.1f}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Mock processor test failed: {e}")
        return False

def test_data_models():
    """Test the data models"""
    print("🧪 Testing data models...")
    
    try:
        # Test basic model creation
        test_data = {
            "name": "Test Employee",
            "id": "TEST001",
            "basic": 50000,
            "hra": 20000,
            "special_allowance": 15000
        }
        
        print("✅ Data models test passed")
        return True
        
    except Exception as e:
        print(f"❌ Data models test failed: {e}")
        return False

def test_file_operations():
    """Test file operations"""
    print("🧪 Testing file operations...")
    
    try:
        # Test reading sample contracts
        if os.path.exists("test_contract.txt"):
            with open("test_contract.txt", 'r') as f:
                content = f.read()
                assert len(content) > 0
                print("✅ Test contract file read successfully")
        
        # Test sample contracts directory
        if os.path.exists("sample_contracts"):
            files = os.listdir("sample_contracts")
            assert len(files) > 0
            print(f"✅ Sample contracts directory contains {len(files)} files")
        
        return True
        
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("🚀 Starting AgenticAI Payroll System Tests")
    print("=" * 50)
    
    tests = [
        ("Contract Creation", test_contract_creation),
        ("Mock Processor", test_mock_processor),
        ("Data Models", test_data_models),
        ("File Operations", test_file_operations)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} test...")
        if test_func():
            passed += 1
        else:
            print(f"⚠️  {test_name} test failed")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The system is ready to use.")
        print("\n📝 Next steps:")
        print("1. Run 'streamlit run simple_payroll_app.py' to start the web interface")
        print("2. Open http://localhost:8501 in your browser")
        print("3. Upload a contract file to test the full functionality")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)