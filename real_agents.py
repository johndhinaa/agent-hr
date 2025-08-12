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
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.schema import BaseOutputParser
from langchain.tools import tool
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.tools import tool

# Local imports
from models import (
    ContractData, EmployeeInfo, SalaryStructure, SalaryBreakdown, 
    Deductions, ComplianceValidation, ComplianceStatus, AnomalyDetection, 
    Anomaly, AnomalyStatus, SeverityLevel, PaystubData, AgentResult
)
from rag_system import PayrollRAGSystem

logger = logging.getLogger(__name__)

class ContractReaderAgent:
    """Real AI Agent 1: Parse employee contracts using Gemini LLM"""
    
    def __init__(self, api_key: str, verbose: bool = False):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.1,
            google_api_key=api_key
        )
        self.verbose = verbose
        
        self.system_prompt = """You are an expert HR contract parser. Your task is to extract structured information from employment contracts.

Extract the following information in JSON format:
- Employee details (name, ID, department, designation, location, joining date, PAN, PF, ESI numbers)
- Salary structure (basic, HRA, allowances, variable pay, bonuses)
- Benefits and special clauses
- Any statutory obligations mentioned

Be precise and extract exact values. If a value is not mentioned, use null."""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "Parse this employment contract and extract the information:\n\n{contract_text}")
        ])
        
        self.parser = JsonOutputParser()
    
    def execute(self, contract_path: str) -> AgentResult:
        """Execute the contract reading agent"""
        start_time = time.time()
        raw_prompt = None
        raw_response = None
        messages_payload: List[Dict[str, Any]] = []
        usage = None
        
        try:
            # Extract text from PDF
            extracted_text = self._extract_pdf_text(contract_path)
            
            # Build messages
            messages = self.prompt.format_messages(contract_text=extracted_text)
            # For verbose logs, serialize messages to simple dicts
            for m in messages:
                role = getattr(m, 'type', 'unknown')
                content = getattr(m, 'content', '')
                messages_payload.append({"role": role, "content": content})
            raw_prompt = json.dumps(messages_payload, ensure_ascii=False, indent=2)
            
            # Call LLM
            response = self.llm.invoke(messages)
            raw_response = getattr(response, 'content', str(response))
            
            # Parse JSON response
            parsed_data = json.loads(response.content)
            
            # Create structured data
            contract_data = self._create_contract_data(parsed_data, extracted_text)
            
            execution_time = time.time() - start_time
            
            return AgentResult(
                agent_name="ContractReaderAgent",
                success=True,
                output=contract_data,
                execution_time=execution_time,
                confidence_score=0.95,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"ContractReaderAgent failed: {e}")
            
            return AgentResult(
                agent_name="ContractReaderAgent",
                success=False,
                output=None,
                error_message=str(e),
                execution_time=execution_time,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
    
    def _extract_pdf_text(self, contract_path: str) -> str:
        """Extract text from PDF file"""
        try:
            with open(contract_path, 'rb') as file:
                reader = PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logger.warning(f"PDF text extraction failed ({e}), trying as text file")
            with open(contract_path, 'r', encoding='utf-8') as file:
                return file.read()
    
    def _create_contract_data(self, parsed_data: Dict, extracted_text: str) -> ContractData:
        """Create structured contract data from parsed information"""
        
        employee_info = EmployeeInfo(
            employee_name=parsed_data.get('employee_name'),
            employee_id=parsed_data.get('employee_id'),
            department=parsed_data.get('department'),
            designation=parsed_data.get('designation'),
            location=parsed_data.get('location'),
            joining_date=parsed_data.get('joining_date'),
            pan_number=parsed_data.get('pan_number'),
            pf_number=parsed_data.get('pf_number'),
            esi_number=parsed_data.get('esi_number')
        )
        
        salary_structure = SalaryStructure(
            basic=parsed_data.get('basic_salary'),
            hra=parsed_data.get('hra'),
            allowances=parsed_data.get('allowances'),
            special_allowance=parsed_data.get('special_allowance'),
            medical_allowance=parsed_data.get('medical_allowance'),
            transport_allowance=parsed_data.get('transport_allowance'),
            meal_allowance=parsed_data.get('meal_allowance'),
            gross=parsed_data.get('gross_salary'),
            variable_pay=parsed_data.get('variable_pay'),
            bonus=parsed_data.get('bonus'),
            is_annual=parsed_data.get('is_annual', False)
        )
        
        return ContractData(
            employee_info=employee_info,
            salary_structure=salary_structure,
            benefits=parsed_data.get('benefits', {}),
            special_clauses=parsed_data.get('special_clauses', []),
            extracted_text=extracted_text[:1000] + "..." if len(extracted_text) > 1000 else extracted_text,
            parsing_confidence=0.95,
            notes="Parsed using Gemini LLM"
        )

class SalaryBreakdownAgent:
    """Real AI Agent 2: Calculate salary breakdown using Gemini LLM"""
    
    def __init__(self, api_key: str, verbose: bool = False):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.1,
            google_api_key=api_key
        )
        self.verbose = verbose
        
        self.system_prompt = """You are an expert payroll calculator specializing in Indian salary structures. 

Calculate the complete salary breakdown including:
- Gross salary (sum of all earnings)
- Basic salary calculations
- HRA and other allowances
- Statutory deductions (PF, ESI, Professional Tax, TDS)
- Net salary

Use these rules:
- PF: 12% of basic salary (capped at ₹15,000)
- ESI: 1.75% of gross salary (if gross ≤ ₹21,000)
- Professional Tax: ₹200 (simplified)
- TDS: 5% of gross salary (simplified)

Return the calculation in JSON format with detailed breakdown."""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "Calculate salary breakdown for this contract data:\n\n{contract_data}")
        ])
        
        self.parser = JsonOutputParser()
    
    def execute(self, contract_data: ContractData) -> AgentResult:
        """Execute the salary breakdown agent"""
        start_time = time.time()
        raw_prompt = None
        raw_response = None
        messages_payload: List[Dict[str, Any]] = []
        usage = None
        
        try:
            # Prepare contract data for LLM
            contract_json = contract_data.model_dump()
            
            # Build messages
            messages = self.prompt.format_messages(contract_data=json.dumps(contract_json, indent=2))
            for m in messages:
                messages_payload.append({"role": getattr(m, 'type', 'unknown'), "content": getattr(m, 'content', '')})
            raw_prompt = json.dumps(messages_payload, ensure_ascii=False, indent=2)
            
            # Calculate with LLM
            response = self.llm.invoke(messages)
            raw_response = getattr(response, 'content', str(response))
            
            # Parse response
            salary_data = json.loads(response.content)
            
            # Create structured salary breakdown
            salary_breakdown = self._create_salary_breakdown(salary_data)
            
            execution_time = time.time() - start_time
            
            return AgentResult(
                agent_name="SalaryBreakdownAgent",
                success=True,
                output=salary_breakdown,
                execution_time=execution_time,
                confidence_score=0.98,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"SalaryBreakdownAgent failed: {e}")
            
            return AgentResult(
                agent_name="SalaryBreakdownAgent",
                success=False,
                output=None,
                error_message=str(e),
                execution_time=execution_time,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
    
    def _create_salary_breakdown(self, salary_data: Dict) -> SalaryBreakdown:
        """Create structured salary breakdown from LLM response"""
        
        deductions = Deductions(
            pf=salary_data.get('pf', 0),
            esi=salary_data.get('esi', 0),
            professional_tax=salary_data.get('professional_tax', 0),
            tds=salary_data.get('tds', 0),
            advance=salary_data.get('advance', 0),
            loan_deduction=salary_data.get('loan_deduction', 0),
            other_deductions=salary_data.get('other_deductions', 0)
        )
        
        return SalaryBreakdown(
            gross_salary=salary_data.get('gross_salary', 0),
            basic_salary=salary_data.get('basic_salary', 0),
            hra=salary_data.get('hra', 0),
            allowances=salary_data.get('allowances', 0),
            deductions=deductions,
            net_salary=salary_data.get('net_salary', 0),
            annual_gross=salary_data.get('annual_gross', 0),
            annual_net=salary_data.get('annual_net', 0),
            calculation_notes=salary_data.get('calculation_notes', "Calculated using Gemini LLM")
        )

class ComplianceMapperAgent:
    """Real AI Agent 3: Validate compliance using RAG and Gemini LLM"""
    
    def __init__(self, api_key: str, rag_system: PayrollRAGSystem, verbose: bool = False):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.1,
            google_api_key=api_key
        )
        self.rag_system = rag_system
        self.verbose = verbose
        
        self.system_prompt = """You are an expert compliance validator for Indian payroll systems.

Validate the salary structure against:
- PF Act compliance (12% contribution, ₹15,000 cap)
- ESI Act compliance (1.75% for salaries ≤ ₹21,000)
- Professional Tax compliance (state-specific rates)
- Income Tax compliance (TDS calculations)
- HRA exemption rules

Use the provided compliance rules and return validation results in JSON format."""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "Validate compliance for this salary data:\n\n{salary_data}\n\nCompliance Rules:\n{compliance_rules}")
        ])
        
        self.parser = JsonOutputParser()
    
    def execute(self, salary_data: SalaryBreakdown) -> AgentResult:
        """Execute the compliance mapper agent"""
        start_time = time.time()
        raw_prompt = None
        raw_response = None
        messages_payload: List[Dict[str, Any]] = []
        usage = None
        
        try:
            # Get compliance rules from RAG
            compliance_rules = self.rag_system.get_all_applicable_rules({
                'gross_salary': salary_data.gross_salary,
                'basic_salary': salary_data.basic_salary,
                'location': 'Karnataka'  # Default location
            })
            
            # Prepare data for LLM
            salary_json = salary_data.model_dump()
            
            # Validate with LLM
            messages = self.prompt.format_messages(
                salary_data=json.dumps(salary_json, indent=2),
                compliance_rules=json.dumps(compliance_rules, indent=2)
            )
            for m in messages:
                messages_payload.append({"role": getattr(m, 'type', 'unknown'), "content": getattr(m, 'content', '')})
            raw_prompt = json.dumps(messages_payload, ensure_ascii=False, indent=2)
            
            response = self.llm.invoke(messages)
            raw_response = getattr(response, 'content', str(response))
            
            # Parse response
            compliance_data = json.loads(response.content)
            
            # Create structured compliance validation
            compliance_validation = self._create_compliance_validation(compliance_data)
            
            execution_time = time.time() - start_time
            
            return AgentResult(
                agent_name="ComplianceMapperAgent",
                success=True,
                output=compliance_validation,
                execution_time=execution_time,
                confidence_score=0.92,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"ComplianceMapperAgent failed: {e}")
            
            return AgentResult(
                agent_name="ComplianceMapperAgent",
                success=False,
                output=None,
                error_message=str(e),
                execution_time=execution_time,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
    
    def _create_compliance_validation(self, compliance_data: Dict) -> ComplianceValidation:
        """Create structured compliance validation from LLM response"""
        
        return ComplianceValidation(
            compliance_status=ComplianceStatus(compliance_data.get('status', 'COMPLIANT')),
            issues=compliance_data.get('issues', []),
            validated_deductions=Deductions(**compliance_data.get('validated_deductions', {})),
            recommendations=compliance_data.get('recommendations', []),
            applied_rules=compliance_data.get('applied_rules', []),
            confidence_score=compliance_data.get('confidence_score', 0.9)
        )

class AnomalyDetectorAgent:
    """Real AI Agent 4: Detect anomalies using Gemini LLM"""
    
    def __init__(self, api_key: str, verbose: bool = False):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.1,
            google_api_key=api_key
        )
        self.verbose = verbose
        
        self.system_prompt = """You are an expert anomaly detector for payroll systems.

Detect anomalies in:
- Salary calculations (overpayment, underpayment)
- Deduction calculations (incorrect PF, ESI, TDS)
- Data inconsistencies (missing information, invalid values)
- Compliance violations (statutory requirement breaches)
- Outlier values (unusually high/low salaries)

Return anomaly detection results in JSON format with severity levels."""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "Detect anomalies in this payroll data:\n\n{payroll_data}")
        ])
        
        self.parser = JsonOutputParser()
    
    def execute(self, payroll_data: Dict) -> AgentResult:
        """Execute the anomaly detector agent"""
        start_time = time.time()
        raw_prompt = None
        raw_response = None
        messages_payload: List[Dict[str, Any]] = []
        usage = None
        
        try:
            # Prepare data for LLM
            payroll_json = json.dumps(payroll_data, indent=2)
            
            # Detect anomalies with LLM
            messages = self.prompt.format_messages(payroll_data=payroll_json)
            for m in messages:
                messages_payload.append({"role": getattr(m, 'type', 'unknown'), "content": getattr(m, 'content', '')})
            raw_prompt = json.dumps(messages_payload, ensure_ascii=False, indent=2)
            
            response = self.llm.invoke(messages)
            raw_response = getattr(response, 'content', str(response))
            
            # Parse response
            anomaly_data = json.loads(response.content)
            
            # Create structured anomaly detection
            anomaly_detection = self._create_anomaly_detection(anomaly_data)
            
            execution_time = time.time() - start_time
            
            return AgentResult(
                agent_name="AnomalyDetectorAgent",
                success=True,
                output=anomaly_detection,
                execution_time=execution_time,
                confidence_score=0.94,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"AnomalyDetectorAgent failed: {e}")
            
            return AgentResult(
                agent_name="AnomalyDetectorAgent",
                success=False,
                output=None,
                error_message=str(e),
                execution_time=execution_time,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
    
    def _create_anomaly_detection(self, anomaly_data: Dict) -> AnomalyDetection:
        """Create structured anomaly detection from LLM response"""
        
        anomalies = []
        for anomaly in anomaly_data.get('anomalies', []):
            anomalies.append(Anomaly(
                type=anomaly.get('type', 'unknown'),
                description=anomaly.get('description', ''),
                severity=SeverityLevel(anomaly.get('severity', 'LOW')),
                affected_field=anomaly.get('affected_field', ''),
                suggested_action=anomaly.get('suggested_action'),
                confidence=anomaly.get('confidence', 0.8)
            ))
        
        return AnomalyDetection(
            has_anomalies=anomaly_data.get('has_anomalies', False),
            anomalies=anomalies,
            overall_status=AnomalyStatus(anomaly_data.get('overall_status', 'NORMAL')),
            confidence_score=anomaly_data.get('confidence_score', 0.9),
            review_notes=anomaly_data.get('review_notes', '')
        )

class PaystubGeneratorAgent:
    """Real AI Agent 5: Generate paystubs using Gemini LLM"""
    
    def __init__(self, api_key: str, verbose: bool = False):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.1,
            google_api_key=api_key
        )
        self.verbose = verbose
        
        self.system_prompt = """You are an expert paystub generator for Indian payroll systems.

Generate a comprehensive paystub including:
- Employee information
- Salary breakdown (earnings and deductions)
- Compliance information
- Pay period details
- Professional formatting

Return the paystub data in JSON format suitable for PDF generation."""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "Generate a paystub for this employee data:\n\n{employee_data}")
        ])
        
        self.parser = JsonOutputParser()
    
    def execute(self, employee_data: Dict) -> AgentResult:
        """Execute the paystub generator agent"""
        start_time = time.time()
        raw_prompt = None
        raw_response = None
        messages_payload: List[Dict[str, Any]] = []
        usage = None
        
        try:
            # Prepare data for LLM
            employee_json = json.dumps(employee_data, indent=2)
            
            # Generate paystub with LLM
            messages = self.prompt.format_messages(employee_data=employee_json)
            for m in messages:
                messages_payload.append({"role": getattr(m, 'type', 'unknown'), "content": getattr(m, 'content', '')})
            raw_prompt = json.dumps(messages_payload, ensure_ascii=False, indent=2)
            
            response = self.llm.invoke(messages)
            raw_response = getattr(response, 'content', str(response))
            
            # Parse response
            paystub_data = json.loads(response.content)
            
            # Create structured paystub data
            paystub = self._create_paystub_data(paystub_data)
            
            execution_time = time.time() - start_time
            
            return AgentResult(
                agent_name="PaystubGeneratorAgent",
                success=True,
                output=paystub,
                execution_time=execution_time,
                confidence_score=0.96,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"PaystubGeneratorAgent failed: {e}")
            
            return AgentResult(
                agent_name="PaystubGeneratorAgent",
                success=False,
                output=None,
                error_message=str(e),
                execution_time=execution_time,
                prompt_messages=messages_payload if self.verbose else [],
                raw_prompt=raw_prompt if self.verbose else None,
                raw_response=raw_response if self.verbose else None,
                usage=usage
            )
    
    def _create_paystub_data(self, paystub_data: Dict) -> PaystubData:
        """Create structured paystub data from LLM response"""
        
        return PaystubData(
            employee_info=EmployeeInfo(**paystub_data.get('employee_info', {})),
            salary_breakdown=SalaryBreakdown(**paystub_data.get('salary_breakdown', {})),
            compliance_info=ComplianceValidation(**paystub_data.get('compliance_info', {})),
            pay_period=paystub_data.get('pay_period', 'January 2024'),
            generated_date=datetime.now(),
            template_version=paystub_data.get('template_version', 'v1.0')
        )