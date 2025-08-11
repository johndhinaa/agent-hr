import os
import json
import logging
import tempfile
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from io import BytesIO
import pandas as pd

# PDF and document processing
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# LangChain and AI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Local imports
from models import (
    ContractData, EmployeeInfo, SalaryStructure, SalaryBreakdown, 
    Deductions, ComplianceValidation, ComplianceStatus, AnomalyDetection, 
    Anomaly, AnomalyStatus, SeverityLevel, PaystubData, AgentResult
)
from rag_system import PayrollRAGSystem

logger = logging.getLogger(__name__)

class BaseAgent:
    """Base class for all payroll agents"""
    
    def __init__(self, name: str, api_key: str):
        self.name = name
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.1,
            google_api_key=api_key
        )
    
    def execute(self, input_data: Any) -> AgentResult:
        """Execute the agent's main function"""
        start_time = time.time()
        try:
            result = self._process(input_data)
            execution_time = time.time() - start_time
            
            return AgentResult(
                agent_name=self.name,
                success=True,
                output=result,
                execution_time=execution_time,
                confidence_score=getattr(result, 'confidence_score', None)
            )
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Agent {self.name} failed: {e}")
            
            return AgentResult(
                agent_name=self.name,
                success=False,
                output=None,
                error_message=str(e),
                execution_time=execution_time
            )
    
    def _process(self, input_data: Any) -> Any:
        """Override this method in subclasses"""
        raise NotImplementedError

class ContractReaderAgent(BaseAgent):
    """Agent 1: Parse employee contracts to extract salary components and benefits"""
    
    def __init__(self, api_key: str):
        super().__init__("ContractReaderAgent", api_key)
    
    def _process(self, contract_path: str) -> ContractData:
        """Extract and parse contract data from PDF"""
        
        # Step 1: Extract text from PDF
        extracted_text = self._extract_pdf_text(contract_path)
        
        # Step 2: Parse contract using LLM
        parsed_data = self._parse_contract_with_llm(extracted_text)
        
        # Step 3: Validate and structure the data
        contract_data = self._structure_contract_data(parsed_data, extracted_text)
        
        return contract_data
    
    def _extract_pdf_text(self, contract_path: str) -> str:
        """Extract text from PDF file"""
        try:
            with open(contract_path, 'rb') as file:
                reader = PdfReader(file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                if not text.strip():
                    raise ValueError("No text could be extracted from the PDF")
                
                logger.info(f"Extracted {len(text)} characters from PDF")
                return text.strip()
                
        except Exception as e:
            raise Exception(f"PDF extraction failed: {e}")
    
    def _parse_contract_with_llm(self, contract_text: str) -> Dict[str, Any]:
        """Use LLM to extract structured contract information"""
        
        system_prompt = """You are an expert HR document parser. Extract employee salary and contract details from the provided employment contract text.

Return ONLY a valid JSON object with this exact structure:
{
  "employee_info": {
    "employee_name": "string or null",
    "employee_id": "string or null",
    "department": "string or null",
    "designation": "string or null",
    "location": "string or null",
    "joining_date": "string or null",
    "pan_number": "string or null",
    "pf_number": "string or null",
    "esi_number": "string or null"
  },
  "salary_structure": {
    "basic": number or null,
    "hra": number or null,
    "allowances": number or null,
    "special_allowance": number or null,
    "medical_allowance": number or null,
    "transport_allowance": number or null,
    "meal_allowance": number or null,
    "gross": number or null,
    "variable_pay": number or null,
    "bonus": number or null,
    "is_annual": boolean
  },
  "benefits": {},
  "special_clauses": [],
  "parsing_confidence": number_between_0_and_1,
  "notes": "string explaining any assumptions or clarifications"
}

Important guidelines:
1. If amounts appear to be annual (> 200,000), set "is_annual": true
2. Extract all salary components mentioned
3. Include any special allowances or benefits in the appropriate fields
4. Set parsing_confidence based on clarity of the document
5. Add notes explaining any assumptions made during parsing
6. If a field is not found, set it to null
7. Ensure all numeric fields are numbers, not strings

Respond with JSON only, no explanations."""

        try:
            human_prompt = f"Contract text to parse:\n\n{contract_text[:15000]}"  # Limit text length
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = self.llm.invoke(messages)
            result_text = response.content.strip()
            
            # Clean up response (remove code blocks if present)
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            # Parse JSON
            parsed = json.loads(result_text)
            logger.info("Successfully parsed contract with LLM")
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise Exception(f"LLM response was not valid JSON: {e}")
        except Exception as e:
            logger.error(f"Contract parsing with LLM failed: {e}")
            raise Exception(f"Contract parsing failed: {e}")
    
    def _structure_contract_data(self, parsed_data: Dict[str, Any], extracted_text: str) -> ContractData:
        """Structure the parsed data into ContractData model"""
        try:
            # Create employee info
            emp_info_data = parsed_data.get("employee_info", {})
            employee_info = EmployeeInfo(**emp_info_data)
            
            # Create salary structure
            salary_data = parsed_data.get("salary_structure", {})
            salary_structure = SalaryStructure(**salary_data)
            
            # Convert annual to monthly if needed
            if salary_structure.is_annual:
                if salary_structure.basic:
                    salary_structure.basic = salary_structure.basic / 12
                if salary_structure.hra:
                    salary_structure.hra = salary_structure.hra / 12
                if salary_structure.allowances:
                    salary_structure.allowances = salary_structure.allowances / 12
                if salary_structure.gross:
                    salary_structure.gross = salary_structure.gross / 12
                # Update the flag
                salary_structure.is_annual = False
            
            contract_data = ContractData(
                employee_info=employee_info,
                salary_structure=salary_structure,
                benefits=parsed_data.get("benefits", {}),
                special_clauses=parsed_data.get("special_clauses", []),
                extracted_text=extracted_text,
                parsing_confidence=parsed_data.get("parsing_confidence", 0.8),
                notes=parsed_data.get("notes", "")
            )
            
            logger.info(f"Structured contract data for employee: {employee_info.employee_name}")
            return contract_data
            
        except Exception as e:
            logger.error(f"Failed to structure contract data: {e}")
            raise Exception(f"Data structuring failed: {e}")

class SalaryBreakdownAgent(BaseAgent):
    """Agent 2: Compute salary breakdown with all deductions and net pay"""
    
    def __init__(self, api_key: str):
        super().__init__("SalaryBreakdownAgent", api_key)
    
    def _process(self, contract_data: ContractData) -> SalaryBreakdown:
        """Calculate comprehensive salary breakdown"""
        
        salary_structure = contract_data.salary_structure
        employee_info = contract_data.employee_info
        
        # Step 1: Calculate gross salary components
        gross_components = self._calculate_gross_components(salary_structure)
        
        # Step 2: Calculate deductions
        deductions = self._calculate_deductions(gross_components, employee_info)
        
        # Step 3: Calculate net salary
        net_salary = gross_components["total"] - sum(deductions.dict().values())
        
        # Step 4: Create salary breakdown
        salary_breakdown = SalaryBreakdown(
            gross_salary=gross_components["total"],
            basic_salary=gross_components["basic"],
            hra=gross_components["hra"],
            allowances=gross_components["allowances"],
            deductions=deductions,
            net_salary=max(0, net_salary),  # Ensure non-negative
            annual_gross=gross_components["total"] * 12,
            annual_net=max(0, net_salary) * 12,
            calculation_notes=self._generate_calculation_notes(gross_components, deductions)
        )
        
        logger.info(f"Calculated salary breakdown - Gross: ₹{salary_breakdown.gross_salary:,.2f}, Net: ₹{salary_breakdown.net_salary:,.2f}")
        return salary_breakdown
    
    def _calculate_gross_components(self, salary_structure: SalaryStructure) -> Dict[str, float]:
        """Calculate all gross salary components"""
        
        # Start with provided values or calculate defaults
        basic = salary_structure.basic or 0
        hra = salary_structure.hra or 0
        allowances = salary_structure.allowances or 0
        
        # Add other allowances
        special_allowance = salary_structure.special_allowance or 0
        medical_allowance = salary_structure.medical_allowance or 0
        transport_allowance = salary_structure.transport_allowance or 0
        meal_allowance = salary_structure.meal_allowance or 0
        
        # If gross is provided but components are missing, estimate them
        if salary_structure.gross and (basic + hra + allowances) == 0:
            gross = salary_structure.gross
            # Standard breakdown: Basic 40%, HRA 50% of basic, Rest as allowances
            basic = gross * 0.4
            hra = basic * 0.5
            allowances = gross - basic - hra
        
        # If basic is provided but gross is missing, calculate gross
        elif basic > 0 and not salary_structure.gross:
            if hra == 0:
                hra = basic * 0.5  # Standard HRA = 50% of basic
            if allowances == 0:
                allowances = basic * 0.15  # Standard allowances = 15% of basic
        
        total_allowances = (allowances + special_allowance + medical_allowance + 
                          transport_allowance + meal_allowance)
        
        total = basic + hra + total_allowances
        
        return {
            "basic": basic,
            "hra": hra,
            "allowances": total_allowances,
            "total": total
        }
    
    def _calculate_deductions(self, gross_components: Dict[str, float], employee_info: EmployeeInfo) -> Deductions:
        """Calculate all statutory and other deductions"""
        
        basic = gross_components["basic"]
        gross = gross_components["total"]
        
        # PF Calculation (12% of basic, capped at ₹1800)
        pf = min(basic * 0.12, 1800.0) if basic > 0 else 0
        
        # ESI Calculation (0.75% of gross if gross <= ₹21,000)
        esi = gross * 0.0075 if gross <= 21000 else 0
        
        # Professional Tax (state-dependent, defaulting to Karnataka rules)
        location = (employee_info.location or "Karnataka").lower()
        professional_tax = self._calculate_professional_tax(gross, location)
        
        # TDS Calculation (simplified)
        annual_gross = gross * 12
        tds = self._calculate_tds(annual_gross)
        
        return Deductions(
            pf=round(pf, 2),
            esi=round(esi, 2),
            professional_tax=round(professional_tax, 2),
            tds=round(tds, 2),
            advance=0.0,  # These would be provided separately
            loan_deduction=0.0,
            other_deductions=0.0
        )
    
    def _calculate_professional_tax(self, gross_salary: float, location: str) -> float:
        """Calculate professional tax based on location"""
        
        if "karnataka" in location:
            if gross_salary <= 15000:
                return 0
            elif gross_salary <= 25000:
                return 200
            else:
                return 300
        elif "maharashtra" in location:
            if gross_salary <= 5000:
                return 0
            elif gross_salary <= 10000:
                return 175
            else:
                return 200
        elif "west bengal" in location or "bengal" in location:
            if gross_salary <= 10000:
                return 110
            elif gross_salary <= 15000:
                return 130
            else:
                return 200
        elif "tamil nadu" in location:
            return 200
        else:
            # Default calculation for other states
            return 200 if gross_salary > 15000 else 0
    
    def _calculate_tds(self, annual_gross: float) -> float:
        """Calculate TDS based on income tax slabs (simplified)"""
        
        # Standard deduction
        taxable_income = max(0, annual_gross - 50000)
        
        # Income tax calculation (basic slabs)
        tax = 0
        if taxable_income > 250000:
            if taxable_income <= 500000:
                tax = (taxable_income - 250000) * 0.05
            elif taxable_income <= 1000000:
                tax = 250000 * 0.05 + (taxable_income - 500000) * 0.20
            else:
                tax = 250000 * 0.05 + 500000 * 0.20 + (taxable_income - 1000000) * 0.30
        
        # Add cess (4%)
        tax_with_cess = tax * 1.04
        
        # Monthly TDS
        monthly_tds = tax_with_cess / 12
        
        return monthly_tds
    
    def _generate_calculation_notes(self, gross_components: Dict[str, float], deductions: Deductions) -> str:
        """Generate explanation of salary calculations"""
        
        notes = []
        notes.append(f"Gross Salary Breakdown:")
        notes.append(f"- Basic: ₹{gross_components['basic']:,.2f}")
        notes.append(f"- HRA: ₹{gross_components['hra']:,.2f}")
        notes.append(f"- Allowances: ₹{gross_components['allowances']:,.2f}")
        notes.append(f"")
        notes.append(f"Deductions:")
        notes.append(f"- PF (12% of basic, max ₹1800): ₹{deductions.pf}")
        notes.append(f"- ESI (0.75% if gross ≤ ₹21000): ₹{deductions.esi}")
        notes.append(f"- Professional Tax (state-dependent): ₹{deductions.professional_tax}")
        notes.append(f"- TDS (estimated): ₹{deductions.tds}")
        
        return "\n".join(notes)

class ComplianceMapperAgent(BaseAgent):
    """Agent 3: RAG-enabled compliance validation with latest government rules"""
    
    def __init__(self, api_key: str, rag_system: PayrollRAGSystem):
        super().__init__("ComplianceMapperAgent", api_key)
        self.rag_system = rag_system
    
    def _process(self, salary_breakdown: SalaryBreakdown) -> ComplianceValidation:
        """Validate salary breakdown against compliance rules"""
        
        # Get applicable compliance rules
        employee_data = {
            "basic_salary": salary_breakdown.basic_salary,
            "gross_salary": salary_breakdown.gross_salary,
            "annual_income": salary_breakdown.annual_gross,
            "state": "Karnataka"  # Default, could be extracted from employee info
        }
        
        applicable_rules = self.rag_system.get_all_applicable_rules(employee_data)
        
        # Validate each deduction type
        issues = []
        recommendations = []
        applied_rules = []
        
        # Validate PF
        pf_validation = self._validate_pf(salary_breakdown, applicable_rules["pf_rules"])
        issues.extend(pf_validation["issues"])
        recommendations.extend(pf_validation["recommendations"])
        applied_rules.extend(pf_validation["applied_rules"])
        
        # Validate ESI
        esi_validation = self._validate_esi(salary_breakdown, applicable_rules["esi_rules"])
        issues.extend(esi_validation["issues"])
        recommendations.extend(esi_validation["recommendations"])
        applied_rules.extend(esi_validation["applied_rules"])
        
        # Validate Professional Tax
        pt_validation = self._validate_professional_tax(salary_breakdown, applicable_rules["professional_tax_rules"])
        issues.extend(pt_validation["issues"])
        recommendations.extend(pt_validation["recommendations"])
        applied_rules.extend(pt_validation["applied_rules"])
        
        # Validate TDS
        tds_validation = self._validate_tds(salary_breakdown, applicable_rules["tax_rules"])
        issues.extend(tds_validation["issues"])
        recommendations.extend(tds_validation["recommendations"])
        applied_rules.extend(tds_validation["applied_rules"])
        
        # Determine overall compliance status
        compliance_status = ComplianceStatus.COMPLIANT if len(issues) == 0 else ComplianceStatus.NON_COMPLIANT
        if any("review" in issue.lower() for issue in issues):
            compliance_status = ComplianceStatus.REVIEW_REQUIRED
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(issues, applied_rules)
        
        # Create validated deductions (corrected if needed)
        validated_deductions = self._create_validated_deductions(salary_breakdown, applicable_rules)
        
        compliance_validation = ComplianceValidation(
            compliance_status=compliance_status,
            issues=issues,
            validated_deductions=validated_deductions,
            recommendations=recommendations,
            applied_rules=applied_rules,
            confidence_score=confidence_score
        )
        
        logger.info(f"Compliance validation completed - Status: {compliance_status}, Issues: {len(issues)}")
        return compliance_validation
    
    def _validate_pf(self, salary_breakdown: SalaryBreakdown, pf_rules: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate PF deduction"""
        issues = []
        recommendations = []
        applied_rules = ["PF: 12% of basic salary, max ₹1800/month"]
        
        calculated_pf = min(salary_breakdown.basic_salary * 0.12, 1800)
        actual_pf = salary_breakdown.deductions.pf
        
        if abs(calculated_pf - actual_pf) > 1.0:  # Allow ₹1 tolerance
            issues.append(f"PF calculation mismatch: Expected ₹{calculated_pf:.2f}, Got ₹{actual_pf:.2f}")
            recommendations.append("Recalculate PF as 12% of basic salary with ₹1800 monthly cap")
        
        if salary_breakdown.basic_salary > 15000 and actual_pf != 1800:
            recommendations.append("Consider voluntary PF contribution above statutory limit")
        
        return {"issues": issues, "recommendations": recommendations, "applied_rules": applied_rules}
    
    def _validate_esi(self, salary_breakdown: SalaryBreakdown, esi_rules: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate ESI deduction"""
        issues = []
        recommendations = []
        applied_rules = ["ESI: 0.75% of gross salary for employees earning ≤ ₹21,000/month"]
        
        if salary_breakdown.gross_salary <= 21000:
            calculated_esi = salary_breakdown.gross_salary * 0.0075
            actual_esi = salary_breakdown.deductions.esi
            
            if abs(calculated_esi - actual_esi) > 1.0:
                issues.append(f"ESI calculation mismatch: Expected ₹{calculated_esi:.2f}, Got ₹{actual_esi:.2f}")
                recommendations.append("Recalculate ESI as 0.75% of gross salary")
        else:
            if salary_breakdown.deductions.esi > 0:
                issues.append("ESI deducted for employee earning > ₹21,000/month")
                recommendations.append("Remove ESI deduction as employee exceeds salary limit")
        
        return {"issues": issues, "recommendations": recommendations, "applied_rules": applied_rules}
    
    def _validate_professional_tax(self, salary_breakdown: SalaryBreakdown, pt_rules: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Professional Tax deduction"""
        issues = []
        recommendations = []
        state = pt_rules.get("state", "Karnataka")
        applied_rules = [f"Professional Tax: {state} state rules applied"]
        
        expected_pt = pt_rules.get("monthly_amount", 0)
        actual_pt = salary_breakdown.deductions.professional_tax
        
        if abs(expected_pt - actual_pt) > 5.0:  # Allow ₹5 tolerance
            issues.append(f"Professional Tax mismatch: Expected ₹{expected_pt:.2f}, Got ₹{actual_pt:.2f}")
            recommendations.append(f"Apply correct {state} professional tax rates")
        
        return {"issues": issues, "recommendations": recommendations, "applied_rules": applied_rules}
    
    def _validate_tds(self, salary_breakdown: SalaryBreakdown, tax_rules: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate TDS calculation"""
        issues = []
        recommendations = []
        applied_rules = ["TDS: Calculated based on current income tax slabs with standard deduction"]
        
        # This is a simplified validation - actual TDS depends on many factors
        if salary_breakdown.annual_gross > 300000 and salary_breakdown.deductions.tds == 0:
            recommendations.append("Review TDS calculation for income above exemption limit")
        
        if salary_breakdown.deductions.tds > salary_breakdown.gross_salary * 0.3:
            issues.append("TDS appears unusually high - please verify calculation")
            recommendations.append("Check TDS calculation considering all exemptions and deductions")
        
        return {"issues": issues, "recommendations": recommendations, "applied_rules": applied_rules}
    
    def _calculate_confidence_score(self, issues: List[str], applied_rules: List[str]) -> float:
        """Calculate confidence score for compliance validation"""
        base_score = 0.9
        
        # Reduce score for each issue
        score_reduction = len(issues) * 0.1
        confidence = max(0.5, base_score - score_reduction)
        
        # Boost score if many rules were applied successfully
        rule_boost = min(0.1, len(applied_rules) * 0.02)
        confidence = min(1.0, confidence + rule_boost)
        
        return round(confidence, 2)
    
    def _create_validated_deductions(self, salary_breakdown: SalaryBreakdown, applicable_rules: Dict[str, Any]) -> Deductions:
        """Create corrected deductions based on compliance rules"""
        
        # Calculate correct values
        correct_pf = min(salary_breakdown.basic_salary * 0.12, 1800)
        correct_esi = salary_breakdown.gross_salary * 0.0075 if salary_breakdown.gross_salary <= 21000 else 0
        correct_pt = applicable_rules["professional_tax_rules"].get("monthly_amount", 0)
        
        return Deductions(
            pf=round(correct_pf, 2),
            esi=round(correct_esi, 2),
            professional_tax=round(correct_pt, 2),
            tds=salary_breakdown.deductions.tds,  # Keep calculated TDS
            advance=salary_breakdown.deductions.advance,
            loan_deduction=salary_breakdown.deductions.loan_deduction,
            other_deductions=salary_breakdown.deductions.other_deductions
        )

class AnomalyDetectorAgent(BaseAgent):
    """Agent 4: Detect calculation anomalies and data inconsistencies"""
    
    def __init__(self, api_key: str):
        super().__init__("AnomalyDetectorAgent", api_key)
    
    def _process(self, data: Dict[str, Any]) -> AnomalyDetection:
        """Detect anomalies in the payroll data"""
        
        contract_data = data.get("contract_data")
        salary_data = data.get("salary_data")
        compliance_data = data.get("compliance_data")
        
        anomalies = []
        
        # Check for calculation anomalies
        calc_anomalies = self._detect_calculation_anomalies(salary_data)
        anomalies.extend(calc_anomalies)
        
        # Check for data inconsistencies
        data_anomalies = self._detect_data_inconsistencies(contract_data, salary_data)
        anomalies.extend(data_anomalies)
        
        # Check for compliance anomalies
        compliance_anomalies = self._detect_compliance_anomalies(compliance_data)
        anomalies.extend(compliance_anomalies)
        
        # Check for outlier values
        outlier_anomalies = self._detect_outlier_values(salary_data)
        anomalies.extend(outlier_anomalies)
        
        # Determine overall status
        overall_status = self._determine_overall_status(anomalies)
        
        # Calculate confidence score
        confidence_score = self._calculate_anomaly_confidence(anomalies)
        
        anomaly_detection = AnomalyDetection(
            has_anomalies=len(anomalies) > 0,
            anomalies=anomalies,
            overall_status=overall_status,
            confidence_score=confidence_score,
            review_notes=self._generate_review_notes(anomalies)
        )
        
        logger.info(f"Anomaly detection completed - Found {len(anomalies)} anomalies, Status: {overall_status}")
        return anomaly_detection
    
    def _detect_calculation_anomalies(self, salary_data: SalaryBreakdown) -> List[Anomaly]:
        """Detect mathematical calculation errors"""
        anomalies = []
        
        # Check if gross salary matches components
        calculated_gross = salary_data.basic_salary + salary_data.hra + salary_data.allowances
        if abs(calculated_gross - salary_data.gross_salary) > 10.0:  # ₹10 tolerance
            anomalies.append(Anomaly(
                type="calculation_error",
                description=f"Gross salary mismatch: Components sum to ₹{calculated_gross:.2f} but gross is ₹{salary_data.gross_salary:.2f}",
                severity=SeverityLevel.HIGH,
                affected_field="gross_salary",
                suggested_action="Verify salary component calculations",
                confidence=0.95
            ))
        
        # Check if net salary calculation is correct
        total_deductions = sum(salary_data.deductions.dict().values())
        calculated_net = salary_data.gross_salary - total_deductions
        if abs(calculated_net - salary_data.net_salary) > 1.0:  # ₹1 tolerance
            anomalies.append(Anomaly(
                type="calculation_error",
                description=f"Net salary calculation error: Expected ₹{calculated_net:.2f}, Got ₹{salary_data.net_salary:.2f}",
                severity=SeverityLevel.HIGH,
                affected_field="net_salary",
                suggested_action="Recalculate net salary as gross minus total deductions",
                confidence=0.99
            ))
        
        # Check for negative values
        if salary_data.net_salary < 0:
            anomalies.append(Anomaly(
                type="calculation_error",
                description="Net salary is negative",
                severity=SeverityLevel.CRITICAL,
                affected_field="net_salary",
                suggested_action="Review deductions - total deductions exceed gross salary",
                confidence=1.0
            ))
        
        return anomalies
    
    def _detect_data_inconsistencies(self, contract_data: ContractData, salary_data: SalaryBreakdown) -> List[Anomaly]:
        """Detect inconsistencies between contract and calculated data"""
        anomalies = []
        
        if not contract_data:
            return anomalies
        
        # Check if contract gross matches calculated gross
        contract_gross = contract_data.salary_structure.gross
        if contract_gross and abs(contract_gross - salary_data.gross_salary) > 100.0:  # ₹100 tolerance
            anomalies.append(Anomaly(
                type="data_inconsistency",
                description=f"Contract gross (₹{contract_gross:.2f}) differs from calculated gross (₹{salary_data.gross_salary:.2f})",
                severity=SeverityLevel.MEDIUM,
                affected_field="gross_salary",
                suggested_action="Verify contract interpretation and salary calculations",
                confidence=0.85
            ))
        
        # Check basic salary consistency
        contract_basic = contract_data.salary_structure.basic
        if contract_basic and abs(contract_basic - salary_data.basic_salary) > 50.0:  # ₹50 tolerance
            anomalies.append(Anomaly(
                type="data_inconsistency",
                description=f"Contract basic (₹{contract_basic:.2f}) differs from calculated basic (₹{salary_data.basic_salary:.2f})",
                severity=SeverityLevel.MEDIUM,
                affected_field="basic_salary",
                suggested_action="Verify basic salary interpretation from contract",
                confidence=0.80
            ))
        
        return anomalies
    
    def _detect_compliance_anomalies(self, compliance_data: ComplianceValidation) -> List[Anomaly]:
        """Convert compliance issues to anomalies"""
        anomalies = []
        
        if not compliance_data:
            return anomalies
        
        if compliance_data.compliance_status == ComplianceStatus.NON_COMPLIANT:
            for issue in compliance_data.issues:
                anomalies.append(Anomaly(
                    type="compliance_issue",
                    description=f"Compliance violation: {issue}",
                    severity=SeverityLevel.HIGH,
                    affected_field="deductions",
                    suggested_action="Apply correct compliance rules",
                    confidence=0.90
                ))
        
        return anomalies
    
    def _detect_outlier_values(self, salary_data: SalaryBreakdown) -> List[Anomaly]:
        """Detect unusual or outlier salary values"""
        anomalies = []
        
        # Check for unusually high basic salary percentage
        basic_percentage = (salary_data.basic_salary / salary_data.gross_salary) * 100
        if basic_percentage > 70:
            anomalies.append(Anomaly(
                type="data_inconsistency",
                description=f"Basic salary is {basic_percentage:.1f}% of gross (unusually high)",
                severity=SeverityLevel.LOW,
                affected_field="basic_salary",
                suggested_action="Verify salary structure breakdown",
                confidence=0.70
            ))
        elif basic_percentage < 20:
            anomalies.append(Anomaly(
                type="data_inconsistency",
                description=f"Basic salary is only {basic_percentage:.1f}% of gross (unusually low)",
                severity=SeverityLevel.MEDIUM,
                affected_field="basic_salary",
                suggested_action="Verify basic salary calculation",
                confidence=0.75
            ))
        
        # Check for unusually high deductions
        total_deduction_percentage = (sum(salary_data.deductions.dict().values()) / salary_data.gross_salary) * 100
        if total_deduction_percentage > 40:
            anomalies.append(Anomaly(
                type="calculation_error",
                description=f"Total deductions are {total_deduction_percentage:.1f}% of gross salary (unusually high)",
                severity=SeverityLevel.MEDIUM,
                affected_field="deductions",
                suggested_action="Review all deductions for accuracy",
                confidence=0.80
            ))
        
        return anomalies
    
    def _determine_overall_status(self, anomalies: List[Anomaly]) -> AnomalyStatus:
        """Determine overall anomaly status"""
        if not anomalies:
            return AnomalyStatus.NORMAL
        
        critical_count = sum(1 for a in anomalies if a.severity == SeverityLevel.CRITICAL)
        high_count = sum(1 for a in anomalies if a.severity == SeverityLevel.HIGH)
        
        if critical_count > 0:
            return AnomalyStatus.CRITICAL
        elif high_count > 2 or len(anomalies) > 5:
            return AnomalyStatus.CRITICAL
        else:
            return AnomalyStatus.REVIEW_REQUIRED
    
    def _calculate_anomaly_confidence(self, anomalies: List[Anomaly]) -> float:
        """Calculate overall confidence in anomaly detection"""
        if not anomalies:
            return 0.95
        
        # Average confidence of detected anomalies
        avg_confidence = sum(a.confidence for a in anomalies) / len(anomalies)
        return round(avg_confidence, 2)
    
    def _generate_review_notes(self, anomalies: List[Anomaly]) -> str:
        """Generate summary notes for review"""
        if not anomalies:
            return "No anomalies detected. Payroll calculations appear correct."
        
        notes = [f"Detected {len(anomalies)} anomalies requiring attention:"]
        
        for i, anomaly in enumerate(anomalies, 1):
            notes.append(f"{i}. {anomaly.description} (Severity: {anomaly.severity})")
        
        notes.append("\nRecommended actions:")
        for anomaly in anomalies:
            if anomaly.suggested_action:
                notes.append(f"- {anomaly.suggested_action}")
        
        return "\n".join(notes)

class PaystubGeneratorAgent(BaseAgent):
    """Agent 5: Generate professional paystubs and tax documents"""
    
    def __init__(self, api_key: str):
        super().__init__("PaystubGeneratorAgent", api_key)
    
    def _process(self, data: Dict[str, Any]) -> PaystubData:
        """Generate paystub and related documents"""
        
        contract_data = data.get("contract_data")
        salary_data = data.get("salary_data")
        compliance_data = data.get("compliance_data")
        
        # Create paystub data
        paystub_data = PaystubData(
            employee_info=contract_data.employee_info,
            salary_breakdown=salary_data,
            compliance_info=compliance_data,
            pay_period=datetime.now().strftime("%B %Y"),
            generated_date=datetime.now(),
            template_version="v1.0"
        )
        
        # Generate PDF paystub
        pdf_buffer = self._generate_pdf_paystub(paystub_data)
        
        # Save PDF to temporary file and store path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="paystub_") as tmp_file:
            tmp_file.write(pdf_buffer.getvalue())
            paystub_data.pdf_path = tmp_file.name
        
        logger.info(f"Generated paystub for {contract_data.employee_info.employee_name}")
        return paystub_data
    
    def _generate_pdf_paystub(self, paystub_data: PaystubData) -> BytesIO:
        """Generate professional PDF paystub"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12
        )
        
        # Build content
        story = []
        
        # Company header
        story.append(Paragraph("COMPANY PAYSLIP", title_style))
        story.append(Spacer(1, 20))
        
        # Employee information table
        emp_info = paystub_data.employee_info
        employee_data = [
            ['Employee Information', ''],
            ['Name:', emp_info.employee_name or 'N/A'],
            ['Employee ID:', emp_info.employee_id or 'N/A'],
            ['Department:', emp_info.department or 'N/A'],
            ['Designation:', emp_info.designation or 'N/A'],
            ['Pay Period:', paystub_data.pay_period],
        ]
        
        emp_table = Table(employee_data, colWidths=[2*inch, 3*inch])
        emp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(emp_table)
        story.append(Spacer(1, 20))
        
        # Salary breakdown table
        salary = paystub_data.salary_breakdown
        deductions = salary.deductions
        
        salary_data = [
            ['EARNINGS', 'AMOUNT (₹)', 'DEDUCTIONS', 'AMOUNT (₹)'],
            ['Basic Salary', f'{salary.basic_salary:,.2f}', 'Provident Fund', f'{deductions.pf:,.2f}'],
            ['House Rent Allowance', f'{salary.hra:,.2f}', 'ESI', f'{deductions.esi:,.2f}'],
            ['Other Allowances', f'{salary.allowances:,.2f}', 'Professional Tax', f'{deductions.professional_tax:,.2f}'],
            ['', '', 'TDS', f'{deductions.tds:,.2f}'],
            ['', '', 'Advance', f'{deductions.advance:,.2f}'],
            ['', '', 'Loan Deduction', f'{deductions.loan_deduction:,.2f}'],
            ['', '', 'Other Deductions', f'{deductions.other_deductions:,.2f}'],
            ['GROSS SALARY', f'{salary.gross_salary:,.2f}', 'TOTAL DEDUCTIONS', f'{sum(deductions.dict().values()):,.2f}'],
            ['', '', '', ''],
            ['NET SALARY', f'{salary.net_salary:,.2f}', '', ''],
        ]
        
        salary_table = Table(salary_data, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch])
        salary_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            
            # Totals row
            ('BACKGROUND', (0, 8), (-1, 8), colors.lightgrey),
            ('FONTNAME', (0, 8), (-1, 8), 'Helvetica-Bold'),
            
            # Net salary row
            ('BACKGROUND', (0, 10), (1, 10), colors.green),
            ('TEXTCOLOR', (0, 10), (1, 10), colors.whitesmoke),
            ('FONTNAME', (0, 10), (1, 10), 'Helvetica-Bold'),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(salary_table)
        story.append(Spacer(1, 20))
        
        # Compliance information
        compliance = paystub_data.compliance_info
        story.append(Paragraph("Compliance Status", header_style))
        
        compliance_text = f"Status: {compliance.compliance_status}<br/>"
        if compliance.issues:
            compliance_text += f"Issues: {len(compliance.issues)} found<br/>"
        compliance_text += f"Confidence Score: {compliance.confidence_score}"
        
        story.append(Paragraph(compliance_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Footer
        footer_text = f"Generated on: {paystub_data.generated_date.strftime('%d %B %Y %H:%M:%S')}<br/>"
        footer_text += f"Template Version: {paystub_data.template_version}"
        story.append(Paragraph(footer_text, styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer