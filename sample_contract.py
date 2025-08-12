import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

def create_sample_contract(filename="sample_employment_contract.pdf"):
    """Create a sample employment contract PDF for testing"""
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title = Paragraph("EMPLOYMENT CONTRACT", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Employee Information
    story.append(Paragraph("Employee Information:", styles['Heading2']))
    story.append(Paragraph("Employee Name: John Doe", styles['Normal']))
    story.append(Paragraph("Employee ID: EMP001", styles['Normal']))
    story.append(Paragraph("Department: Engineering", styles['Normal']))
    story.append(Paragraph("Designation: Senior Software Engineer", styles['Normal']))
    story.append(Paragraph("Location: Bangalore, Karnataka", styles['Normal']))
    story.append(Paragraph("Joining Date: January 15, 2024", styles['Normal']))
    story.append(Paragraph("PAN Number: ABCDE1234F", styles['Normal']))
    story.append(Paragraph("PF Number: PF123456789", styles['Normal']))
    story.append(Paragraph("ESI Number: ESI987654321", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Salary Structure
    story.append(Paragraph("Salary Structure:", styles['Heading2']))
    story.append(Paragraph("Basic Salary: ₹50,000 per month", styles['Normal']))
    story.append(Paragraph("House Rent Allowance (HRA): ₹20,000 per month", styles['Normal']))
    story.append(Paragraph("Special Allowance: ₹15,000 per month", styles['Normal']))
    story.append(Paragraph("Medical Allowance: ₹1,250 per month", styles['Normal']))
    story.append(Paragraph("Transport Allowance: ₹1,600 per month", styles['Normal']))
    story.append(Paragraph("Meal Allowance: ₹2,200 per month", styles['Normal']))
    story.append(Paragraph("Variable Pay: ₹10,000 per month (performance-based)", styles['Normal']))
    story.append(Paragraph("Annual Bonus: ₹60,000 (paid annually)", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Benefits
    story.append(Paragraph("Benefits:", styles['Heading2']))
    story.append(Paragraph("• Provident Fund (PF): 12% of Basic Salary (capped at ₹15,000)", styles['Normal']))
    story.append(Paragraph("• Employee State Insurance (ESI): 1.75% of Gross Salary", styles['Normal']))
    story.append(Paragraph("• Professional Tax: As per Karnataka state rules", styles['Normal']))
    story.append(Paragraph("• Income Tax: As per applicable tax slabs", styles['Normal']))
    story.append(Paragraph("• Gratuity: As per Payment of Gratuity Act, 1972", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Special Clauses
    story.append(Paragraph("Special Clauses:", styles['Heading2']))
    story.append(Paragraph("• PF contribution is capped at ₹15,000 as per government regulations", styles['Normal']))
    story.append(Paragraph("• Variable pay is performance-based and subject to quarterly review", styles['Normal']))
    story.append(Paragraph("• HRA exemption is subject to actual rent paid and city classification", styles['Normal']))
    story.append(Paragraph("• Professional tax varies by state and salary bracket", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Terms and Conditions
    story.append(Paragraph("Terms and Conditions:", styles['Heading2']))
    story.append(Paragraph("• This contract is governed by Indian labor laws", styles['Normal']))
    story.append(Paragraph("• All statutory deductions will be made as per applicable laws", styles['Normal']))
    story.append(Paragraph("• Salary will be paid on the last working day of each month", styles['Normal']))
    story.append(Paragraph("• Any changes to salary structure will be communicated in writing", styles['Normal']))
    
    # Build the PDF
    doc.build(story)
    return filename

def create_sample_contracts_directory():
    """Create a directory with sample contracts for testing"""
    
    # Create sample contracts directory
    os.makedirs("sample_contracts", exist_ok=True)
    
    # Create multiple sample contracts with different scenarios
    contracts = [
        {
            "filename": "sample_contracts/contract_1.pdf",
            "employee_name": "John Doe",
            "employee_id": "EMP001",
            "basic_salary": 50000,
            "hra": 20000,
            "special_allowance": 15000,
            "variable_pay": 10000,
            "location": "Bangalore, Karnataka"
        },
        {
            "filename": "sample_contracts/contract_2.pdf",
            "employee_name": "Jane Smith",
            "employee_id": "EMP002",
            "basic_salary": 75000,
            "hra": 30000,
            "special_allowance": 25000,
            "variable_pay": 15000,
            "location": "Mumbai, Maharashtra"
        },
        {
            "filename": "sample_contracts/contract_3.pdf",
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
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title = Paragraph("EMPLOYMENT CONTRACT", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Employee Information
    story.append(Paragraph("Employee Information:", styles['Heading2']))
    story.append(Paragraph(f"Employee Name: {employee_name}", styles['Normal']))
    story.append(Paragraph(f"Employee ID: {employee_id}", styles['Normal']))
    story.append(Paragraph("Department: Engineering", styles['Normal']))
    story.append(Paragraph("Designation: Software Engineer", styles['Normal']))
    story.append(Paragraph(f"Location: {location}", styles['Normal']))
    story.append(Paragraph("Joining Date: January 15, 2024", styles['Normal']))
    story.append(Paragraph("PAN Number: ABCDE1234F", styles['Normal']))
    story.append(Paragraph("PF Number: PF123456789", styles['Normal']))
    story.append(Paragraph("ESI Number: ESI987654321", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Salary Structure
    story.append(Paragraph("Salary Structure:", styles['Heading2']))
    story.append(Paragraph(f"Basic Salary: ₹{basic_salary:,} per month", styles['Normal']))
    story.append(Paragraph(f"House Rent Allowance (HRA): ₹{hra:,} per month", styles['Normal']))
    story.append(Paragraph(f"Special Allowance: ₹{special_allowance:,} per month", styles['Normal']))
    story.append(Paragraph("Medical Allowance: ₹1,250 per month", styles['Normal']))
    story.append(Paragraph("Transport Allowance: ₹1,600 per month", styles['Normal']))
    story.append(Paragraph("Meal Allowance: ₹2,200 per month", styles['Normal']))
    story.append(Paragraph(f"Variable Pay: ₹{variable_pay:,} per month (performance-based)", styles['Normal']))
    story.append(Paragraph("Annual Bonus: ₹60,000 (paid annually)", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Benefits
    story.append(Paragraph("Benefits:", styles['Heading2']))
    story.append(Paragraph("• Provident Fund (PF): 12% of Basic Salary (capped at ₹15,000)", styles['Normal']))
    story.append(Paragraph("• Employee State Insurance (ESI): 1.75% of Gross Salary", styles['Normal']))
    story.append(Paragraph("• Professional Tax: As per state rules", styles['Normal']))
    story.append(Paragraph("• Income Tax: As per applicable tax slabs", styles['Normal']))
    story.append(Paragraph("• Gratuity: As per Payment of Gratuity Act, 1972", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Special Clauses
    story.append(Paragraph("Special Clauses:", styles['Heading2']))
    story.append(Paragraph("• PF contribution is capped at ₹15,000 as per government regulations", styles['Normal']))
    story.append(Paragraph("• Variable pay is performance-based and subject to quarterly review", styles['Normal']))
    story.append(Paragraph("• HRA exemption is subject to actual rent paid and city classification", styles['Normal']))
    story.append(Paragraph("• Professional tax varies by state and salary bracket", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Terms and Conditions
    story.append(Paragraph("Terms and Conditions:", styles['Heading2']))
    story.append(Paragraph("• This contract is governed by Indian labor laws", styles['Normal']))
    story.append(Paragraph("• All statutory deductions will be made as per applicable laws", styles['Normal']))
    story.append(Paragraph("• Salary will be paid on the last working day of each month", styles['Normal']))
    story.append(Paragraph("• Any changes to salary structure will be communicated in writing", styles['Normal']))
    
    # Build the PDF
    doc.build(story)
    return filename

if __name__ == "__main__":
    # Create a single sample contract
    create_sample_contract()
    print("Created sample_employment_contract.pdf")
    
    # Create multiple sample contracts
    create_sample_contracts_directory()