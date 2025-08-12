#!/usr/bin/env python3

def create_simple_contract(filename="test_contract.txt"):
    """Create a simple text-based contract for testing"""
    
    contract_content = """
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

Special Clauses:
• PF contribution is capped at ₹15,000 as per government regulations
• Variable pay is performance-based and subject to quarterly review
• HRA exemption is subject to actual rent paid and city classification
• Professional tax varies by state and salary bracket

Terms and Conditions:
• This contract is governed by Indian labor laws
• All statutory deductions will be made as per applicable laws
• Salary will be paid on the last working day of each month
• Any changes to salary structure will be communicated in writing
"""
    
    with open(filename, 'w') as f:
        f.write(contract_content)
    
    print(f"Created test contract: {filename}")
    return filename

def create_sample_contracts():
    """Create multiple sample contracts for testing"""
    
    import os
    
    # Create sample contracts directory
    os.makedirs("sample_contracts", exist_ok=True)
    
    # Sample contracts with different scenarios
    contracts = [
        {
            "filename": "sample_contracts/contract_1.txt",
            "employee_name": "John Doe",
            "employee_id": "EMP001",
            "basic_salary": 50000,
            "hra": 20000,
            "special_allowance": 15000,
            "variable_pay": 10000,
            "location": "Bangalore, Karnataka"
        },
        {
            "filename": "sample_contracts/contract_2.txt",
            "employee_name": "Jane Smith",
            "employee_id": "EMP002",
            "basic_salary": 75000,
            "hra": 30000,
            "special_allowance": 25000,
            "variable_pay": 15000,
            "location": "Mumbai, Maharashtra"
        },
        {
            "filename": "sample_contracts/contract_3.txt",
            "employee_name": "Mike Johnson",
            "employee_id": "EMP003",
            "basic_salary": 35000,
            "hra": 14000,
            "special_allowance": 10000,
            "variable_pay": 5000,
            "location": "Chennai, Tamil Nadu"
        }
    ]
    
    for contract in contracts:
        create_custom_contract(
            filename=contract["filename"],
            employee_name=contract["employee_name"],
            employee_id=contract["employee_id"],
            basic_salary=contract["basic_salary"],
            hra=contract["hra"],
            special_allowance=contract["special_allowance"],
            variable_pay=contract["variable_pay"],
            location=contract["location"]
        )
    
    print(f"Created {len(contracts)} sample contracts in sample_contracts/ directory")

def create_custom_contract(filename, employee_name, employee_id, basic_salary, hra, special_allowance, variable_pay, location):
    """Create a custom employment contract with specified parameters"""
    
    contract_content = f"""
EMPLOYMENT CONTRACT

Employee Information:
Employee Name: {employee_name}
Employee ID: {employee_id}
Department: Engineering
Designation: Software Engineer
Location: {location}
Joining Date: January 15, 2024
PAN Number: ABCDE1234F
PF Number: PF123456789
ESI Number: ESI987654321

Salary Structure:
Basic Salary: ₹{basic_salary:,} per month
House Rent Allowance (HRA): ₹{hra:,} per month
Special Allowance: ₹{special_allowance:,} per month
Medical Allowance: ₹1,250 per month
Transport Allowance: ₹1,600 per month
Meal Allowance: ₹2,200 per month
Variable Pay: ₹{variable_pay:,} per month (performance-based)
Annual Bonus: ₹60,000 (paid annually)

Benefits:
• Provident Fund (PF): 12% of Basic Salary (capped at ₹15,000)
• Employee State Insurance (ESI): 1.75% of Gross Salary
• Professional Tax: As per state rules
• Income Tax: As per applicable tax slabs
• Gratuity: As per Payment of Gratuity Act, 1972

Special Clauses:
• PF contribution is capped at ₹15,000 as per government regulations
• Variable pay is performance-based and subject to quarterly review
• HRA exemption is subject to actual rent paid and city classification
• Professional tax varies by state and salary bracket

Terms and Conditions:
• This contract is governed by Indian labor laws
• All statutory deductions will be made as per applicable laws
• Salary will be paid on the last working day of each month
• Any changes to salary structure will be communicated in writing
"""
    
    with open(filename, 'w') as f:
        f.write(contract_content)
    
    print(f"Created contract: {filename}")
    return filename

if __name__ == "__main__":
    # Create a single test contract
    create_simple_contract()
    
    # Create multiple sample contracts
    create_sample_contracts()