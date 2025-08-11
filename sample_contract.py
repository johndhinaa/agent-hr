import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from datetime import datetime, timedelta
import random

def create_sample_contract(employee_data, filename):
    """Create a sample employment contract PDF"""
    
    doc = SimpleDocTemplate(filename, pagesize=letter, topMargin=0.5*inch)
    story = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    # Contract header
    story.append(Paragraph("EMPLOYMENT CONTRACT", title_style))
    story.append(Spacer(1, 20))
    
    # Company information
    story.append(Paragraph("TechCorp Solutions Pvt. Ltd.", header_style))
    story.append(Paragraph("123 Technology Park, Bangalore, Karnataka - 560001", styles['Normal']))
    story.append(Paragraph("CIN: U72200KA2020PTC134567", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Contract date
    contract_date = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"Date: {contract_date}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Employee information section
    story.append(Paragraph("EMPLOYEE INFORMATION", header_style))
    
    emp_info_data = [
        ['Field', 'Details'],
        ['Full Name', employee_data['name']],
        ['Employee ID', employee_data['employee_id']],
        ['Department', employee_data['department']],
        ['Designation', employee_data['designation']],
        ['Date of Joining', employee_data['joining_date']],
        ['Work Location', employee_data['location']],
        ['PAN Number', employee_data.get('pan_number', 'To be provided')],
        ['Reporting Manager', employee_data.get('manager', 'Mr. Rajesh Kumar')]
    ]
    
    emp_table = Table(emp_info_data, colWidths=[2*inch, 3*inch])
    emp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(emp_table)
    story.append(Spacer(1, 20))
    
    # Salary information section
    story.append(Paragraph("COMPENSATION PACKAGE", header_style))
    
    salary_data = employee_data['salary']
    
    # Annual vs Monthly indicator
    if salary_data.get('is_annual', False):
        story.append(Paragraph("The following compensation is specified on an ANNUAL basis:", styles['Normal']))
        story.append(Spacer(1, 10))
    else:
        story.append(Paragraph("The following compensation is specified on a MONTHLY basis:", styles['Normal']))
        story.append(Spacer(1, 10))
    
    salary_info_data = [
        ['Component', 'Amount (₹)'],
        ['Basic Salary', f"{salary_data['basic']:,.2f}"],
        ['House Rent Allowance (HRA)', f"{salary_data['hra']:,.2f}"],
        ['Special Allowance', f"{salary_data.get('special_allowance', 0):,.2f}"],
        ['Medical Allowance', f"{salary_data.get('medical_allowance', 0):,.2f}"],
        ['Transport Allowance', f"{salary_data.get('transport_allowance', 0):,.2f}"],
        ['', ''],
        ['GROSS SALARY', f"{salary_data['gross']:,.2f}"]
    ]
    
    salary_table = Table(salary_info_data, colWidths=[3*inch, 2*inch])
    salary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgreen),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(salary_table)
    story.append(Spacer(1, 20))
    
    # Terms and conditions
    story.append(Paragraph("TERMS AND CONDITIONS", header_style))
    
    terms = [
        "1. Provident Fund (PF): As per statutory requirements, 12% of basic salary will be deducted as employee contribution to PF.",
        "2. Employee State Insurance (ESI): If applicable (gross salary ≤ ₹21,000), 0.75% will be deducted as per ESI regulations.",
        "3. Professional Tax: State professional tax will be deducted as per applicable state rules.",
        "4. Income Tax (TDS): Tax will be deducted at source as per prevailing income tax slabs and employee's tax declarations.",
        "5. Leave Policy: 21 days casual leave + 7 days sick leave per calendar year.",
        "6. Notice Period: 30 days notice period for resignation.",
        "7. Probation: 6 months probation period from date of joining.",
        "8. Medical Insurance: Company provides medical insurance coverage as per policy.",
        "9. Working Hours: 40 hours per week, flexible timing between 9 AM to 7 PM.",
        "10. Annual Appraisal: Performance review and salary revision annually."
    ]
    
    for term in terms:
        story.append(Paragraph(term, styles['Normal']))
        story.append(Spacer(1, 8))
    
    story.append(Spacer(1, 20))
    
    # Benefits section
    if employee_data.get('benefits'):
        story.append(Paragraph("ADDITIONAL BENEFITS", header_style))
        
        benefits = employee_data['benefits']
        for benefit in benefits:
            story.append(Paragraph(f"• {benefit}", styles['Normal']))
            story.append(Spacer(1, 5))
        
        story.append(Spacer(1, 20))
    
    # Signature section
    story.append(Paragraph("SIGNATURES", header_style))
    
    signature_data = [
        ['Employee Signature', 'Company Representative'],
        ['', ''],
        ['', ''],
        [f"{employee_data['name']}", "Mr. Amit Sharma"],
        ['Date: ___________', 'HR Director'],
        ['', 'Date: ___________']
    ]
    
    signature_table = Table(signature_data, colWidths=[2.5*inch, 2.5*inch])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, 2), 20),
        ('LINEBELOW', (0, 2), (-1, 2), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    
    story.append(signature_table)
    story.append(Spacer(1, 20))
    
    # Footer
    story.append(Paragraph("This contract is subject to company policies and Indian labor laws.", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=1)))
    
    # Build PDF
    doc.build(story)
    print(f"Sample contract created: {filename}")

def generate_sample_contracts():
    """Generate multiple sample employment contracts for testing"""
    
    # Sample employee data
    employees = [
        {
            "name": "Priya Sharma",
            "employee_id": "EMP001",
            "department": "Software Development",
            "designation": "Senior Software Engineer",
            "joining_date": "January 15, 2024",
            "location": "Bangalore, Karnataka",
            "pan_number": "ABCDE1234F",
            "salary": {
                "basic": 45000,
                "hra": 22500,
                "special_allowance": 12000,
                "medical_allowance": 2500,
                "transport_allowance": 3000,
                "gross": 85000,
                "is_annual": False
            },
            "benefits": [
                "Group medical insurance for self and family",
                "Annual performance bonus",
                "Flexible working hours",
                "Professional development allowance"
            ]
        },
        {
            "name": "Rajesh Kumar",
            "employee_id": "EMP002", 
            "department": "Marketing",
            "designation": "Marketing Manager",
            "joining_date": "March 1, 2024",
            "location": "Mumbai, Maharashtra",
            "pan_number": "FGHIJ5678K",
            "salary": {
                "basic": 600000,
                "hra": 300000,
                "special_allowance": 150000,
                "medical_allowance": 30000,
                "transport_allowance": 36000,
                "gross": 1116000,
                "is_annual": True
            },
            "benefits": [
                "Company car allowance",
                "Mobile phone reimbursement",
                "Travel allowance",
                "Stock options"
            ]
        },
        {
            "name": "Aisha Patel",
            "employee_id": "EMP003",
            "department": "Human Resources",
            "designation": "HR Executive", 
            "joining_date": "February 10, 2024",
            "location": "Pune, Maharashtra",
            "pan_number": "LMNOP9012Q",
            "salary": {
                "basic": 18000,
                "hra": 9000,
                "special_allowance": 3000,
                "medical_allowance": 1500,
                "transport_allowance": 1500,
                "gross": 33000,
                "is_annual": False
            },
            "benefits": [
                "Health insurance",
                "Provident fund",
                "Paid time off",
                "Training programs"
            ]
        },
        {
            "name": "Vikram Singh",
            "employee_id": "EMP004",
            "department": "Finance",
            "designation": "Financial Analyst",
            "joining_date": "April 5, 2024", 
            "location": "Chennai, Tamil Nadu",
            "pan_number": "RSTUV3456W",
            "salary": {
                "basic": 35000,
                "hra": 17500,
                "special_allowance": 8000,
                "medical_allowance": 2000,
                "transport_allowance": 2500,
                "gross": 65000,
                "is_annual": False
            },
            "benefits": [
                "Medical insurance",
                "Annual bonus",
                "Professional certification support",
                "Flexible work arrangements"
            ]
        },
        {
            "name": "Kavya Reddy", 
            "employee_id": "EMP005",
            "department": "Operations",
            "designation": "Operations Head",
            "joining_date": "May 20, 2024",
            "location": "Hyderabad, Telangana",
            "pan_number": "XYZAB7890C",
            "salary": {
                "basic": 1200000,
                "hra": 600000,
                "special_allowance": 300000,
                "medical_allowance": 60000,
                "transport_allowance": 120000,
                "gross": 2280000,
                "is_annual": True
            },
            "benefits": [
                "Executive health checkup",
                "Company vehicle",
                "Club membership",
                "Stock options",
                "Variable pay component"
            ]
        }
    ]
    
    # Create contracts directory if it doesn't exist
    contracts_dir = "sample_contracts"
    if not os.path.exists(contracts_dir):
        os.makedirs(contracts_dir)
    
    # Generate contracts
    for i, employee in enumerate(employees):
        filename = os.path.join(contracts_dir, f"contract_{employee['employee_id']}.pdf")
        create_sample_contract(employee, filename)
    
    print(f"\nGenerated {len(employees)} sample contracts in '{contracts_dir}' directory")
    print("\nYou can use these files to test the AgenticAI Payroll System:")
    for employee in employees:
        print(f"- {employee['name']} ({employee['employee_id']}) - {employee['designation']}")

if __name__ == "__main__":
    generate_sample_contracts()