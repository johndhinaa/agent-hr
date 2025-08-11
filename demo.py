#!/usr/bin/env python3
"""
AgenticAI Payroll System - Command Line Demo

This script demonstrates how to use the payroll system programmatically
without the Streamlit interface.
"""

import os
import sys
import json
import time
from typing import List

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def demo_single_contract(api_key: str, contract_path: str):
    """Demonstrate processing a single contract"""
    
    try:
        from payroll_workflow import process_single_contract
        
        print(f"🔄 Processing contract: {contract_path}")
        print("   This may take 15-30 seconds...")
        
        start_time = time.time()
        result = process_single_contract(contract_path, api_key)
        end_time = time.time()
        
        print(f"⏱️  Processing completed in {end_time - start_time:.2f} seconds")
        print()
        
        # Display results
        if result.success:
            print("✅ Processing SUCCESSFUL!")
            print(f"   Employee: {result.employee_id}")
            
            if result.contract_data:
                emp_info = result.contract_data.employee_info
                print(f"   Name: {emp_info.employee_name}")
                print(f"   Department: {emp_info.department}")
                print(f"   Designation: {emp_info.designation}")
            
            if result.salary_data:
                salary = result.salary_data
                print(f"   Gross Salary: ₹{salary.gross_salary:,.2f}")
                print(f"   Net Salary: ₹{salary.net_salary:,.2f}")
                print(f"   Total Deductions: ₹{sum(salary.deductions.dict().values()):,.2f}")
            
            if result.compliance_data:
                print(f"   Compliance Status: {result.compliance_data.compliance_status}")
                print(f"   Issues Found: {len(result.compliance_data.issues)}")
            
            if result.anomalies_data:
                print(f"   Anomaly Status: {result.anomalies_data.overall_status}")
                print(f"   Anomalies Detected: {len(result.anomalies_data.anomalies)}")
            
        else:
            print("❌ Processing FAILED!")
            print("   Errors:")
            for error in result.errors:
                print(f"   - {error}")
        
        print()
        return result
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return None

def demo_batch_processing(api_key: str, contract_paths: List[str]):
    """Demonstrate batch processing of multiple contracts"""
    
    try:
        from payroll_workflow import batch_process_contracts
        
        print(f"🔄 Batch processing {len(contract_paths)} contracts...")
        print("   This may take several minutes...")
        
        start_time = time.time()
        results = batch_process_contracts(contract_paths, api_key)
        end_time = time.time()
        
        print(f"⏱️  Batch processing completed in {end_time - start_time:.2f} seconds")
        print()
        
        # Summary statistics
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        avg_time = sum(r.processing_time or 0 for r in results) / len(results)
        
        print("📊 Batch Processing Summary:")
        print(f"   Total Processed: {len(results)}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        print(f"   Success Rate: {successful/len(results)*100:.1f}%")
        print(f"   Average Time: {avg_time:.2f}s per contract")
        print()
        
        # Individual results
        for i, result in enumerate(results, 1):
            status = "✅" if result.success else "❌"
            employee_id = result.employee_id if result.employee_id != "unknown" else f"Contract {i}"
            print(f"   {status} {employee_id}")
        
        print()
        return results
        
    except Exception as e:
        print(f"❌ Batch processing failed: {e}")
        return []

def export_results_to_json(results: List, filename: str):
    """Export processing results to JSON file"""
    
    try:
        export_data = []
        
        for result in results:
            if result and result.success:
                data = {
                    "employee_id": result.employee_id,
                    "success": result.success,
                    "processing_time": result.processing_time,
                    "employee_info": result.contract_data.employee_info.dict() if result.contract_data else None,
                    "salary_breakdown": result.salary_data.dict() if result.salary_data else None,
                    "compliance_status": result.compliance_data.compliance_status if result.compliance_data else None,
                    "anomaly_count": len(result.anomalies_data.anomalies) if result.anomalies_data else 0,
                    "errors": result.errors
                }
                export_data.append(data)
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        print(f"📄 Results exported to: {filename}")
        print()
        
    except Exception as e:
        print(f"❌ Export failed: {e}")

def main():
    """Main demo function"""
    
    print("=" * 60)
    print("🤖 AgenticAI Payroll System - Command Line Demo")
    print("=" * 60)
    print()
    
    # Check for API key
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY environment variable not set")
        print("   Set your API key with: export GOOGLE_API_KEY='your_key_here'")
        print("   Get your API key from: https://makersuite.google.com/app/apikey")
        sys.exit(1)
    
    print("✅ Google API key found")
    
    # Check for sample contracts
    if not os.path.exists('sample_contracts'):
        print("❌ Error: Sample contracts not found")
        print("   Generate sample contracts with: python sample_contract.py")
        sys.exit(1)
    
    contract_files = [
        f for f in os.listdir('sample_contracts') 
        if f.endswith('.pdf')
    ]
    
    if not contract_files:
        print("❌ Error: No PDF files found in sample_contracts directory")
        sys.exit(1)
    
    print(f"✅ Found {len(contract_files)} sample contracts")
    print()
    
    # Demo options
    print("Demo Options:")
    print("1. Process single contract")
    print("2. Batch process all contracts")
    print("3. Interactive selection")
    print()
    
    try:
        choice = input("Enter your choice (1-3): ").strip()
        print()
        
        if choice == "1":
            # Single contract demo
            contract_path = os.path.join('sample_contracts', contract_files[0])
            result = demo_single_contract(api_key, contract_path)
            
            if result:
                export_results_to_json([result], "single_contract_result.json")
        
        elif choice == "2":
            # Batch processing demo
            contract_paths = [
                os.path.join('sample_contracts', f) 
                for f in contract_files
            ]
            results = demo_batch_processing(api_key, contract_paths)
            
            if results:
                export_results_to_json(results, "batch_processing_results.json")
        
        elif choice == "3":
            # Interactive selection
            print("Available contracts:")
            for i, file in enumerate(contract_files, 1):
                print(f"   {i}. {file}")
            print()
            
            try:
                selection = int(input("Enter contract number: ")) - 1
                if 0 <= selection < len(contract_files):
                    contract_path = os.path.join('sample_contracts', contract_files[selection])
                    result = demo_single_contract(api_key, contract_path)
                    
                    if result:
                        export_results_to_json([result], f"contract_{selection+1}_result.json")
                else:
                    print("❌ Invalid selection")
            except ValueError:
                print("❌ Invalid input")
        
        else:
            print("❌ Invalid choice")
    
    except KeyboardInterrupt:
        print("\n🛑 Demo stopped by user")
    except Exception as e:
        print(f"❌ Demo error: {e}")

if __name__ == "__main__":
    main()