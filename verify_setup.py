#!/usr/bin/env python3
"""
Verification script for AgenticAI Payroll System

This script checks if all components can be imported without errors.
"""

import sys
import importlib

def test_import(module_name, description):
    """Test importing a module"""
    try:
        importlib.import_module(module_name)
        print(f"✅ {description}")
        return True
    except ImportError as e:
        print(f"❌ {description}: {e}")
        return False
    except Exception as e:
        print(f"⚠️  {description}: {e}")
        return False

def main():
    """Main verification function"""
    
    print("🔍 Verifying AgenticAI Payroll System Setup...")
    print("=" * 50)
    print()
    
    # Test core modules
    tests = [
        ("models", "Data Models"),
        ("rag_system", "RAG System"), 
        ("agents", "AI Agents"),
        ("payroll_workflow", "Workflow Engine"),
    ]
    
    success_count = 0
    total_tests = len(tests)
    
    for module_name, description in tests:
        if test_import(module_name, description):
            success_count += 1
    
    print()
    print("=" * 50)
    
    if success_count == total_tests:
        print("🎉 All components verified successfully!")
        print("✅ The system is ready to use")
        print()
        print("🚀 Run the application with:")
        print("   streamlit run agentic_payroll_app.py")
    else:
        print(f"❌ {total_tests - success_count} components failed verification")
        print("   Please check the error messages above")
    
    print()

if __name__ == "__main__":
    main()
