from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"

class AnomalyStatus(str, Enum):
    NORMAL = "NORMAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CRITICAL = "CRITICAL"

class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class EmployeeInfo(BaseModel):
    employee_name: Optional[str] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    location: Optional[str] = None
    joining_date: Optional[str] = None
    pan_number: Optional[str] = None
    pf_number: Optional[str] = None
    esi_number: Optional[str] = None

class SalaryStructure(BaseModel):
    basic: Optional[float] = None
    hra: Optional[float] = None
    allowances: Optional[float] = None
    special_allowance: Optional[float] = None
    medical_allowance: Optional[float] = None
    transport_allowance: Optional[float] = None
    meal_allowance: Optional[float] = None
    gross: Optional[float] = None
    variable_pay: Optional[float] = None
    bonus: Optional[float] = None
    is_annual: Optional[bool] = False

class Deductions(BaseModel):
    pf: float = 0.0
    esi: float = 0.0
    professional_tax: float = 0.0
    tds: float = 0.0
    advance: float = 0.0
    loan_deduction: float = 0.0
    other_deductions: float = 0.0

class ContractData(BaseModel):
    employee_info: EmployeeInfo
    salary_structure: SalaryStructure
    benefits: Optional[Dict[str, Any]] = {}
    special_clauses: Optional[List[str]] = []
    extracted_text: Optional[str] = None
    parsing_confidence: Optional[float] = None
    notes: Optional[str] = None

class SalaryBreakdown(BaseModel):
    gross_salary: float
    basic_salary: float
    hra: float
    allowances: float
    deductions: Deductions
    net_salary: float
    annual_gross: float
    annual_net: float
    calculation_notes: Optional[str] = None

class ComplianceRule(BaseModel):
    rule_name: str
    rule_type: str  # "PF", "ESI", "TDS", "Professional_Tax"
    applicable_range: Dict[str, float]  # min/max salary ranges
    rate: Optional[float] = None
    cap_amount: Optional[float] = None
    exemption_limit: Optional[float] = None
    description: str
    last_updated: datetime
    source_url: Optional[str] = None

class ComplianceValidation(BaseModel):
    compliance_status: ComplianceStatus
    issues: List[str] = []
    validated_deductions: Deductions
    recommendations: List[str] = []
    applied_rules: List[str] = []
    confidence_score: float

class Anomaly(BaseModel):
    type: str  # "calculation_error", "data_inconsistency", "compliance_issue"
    description: str
    severity: SeverityLevel
    affected_field: str
    suggested_action: Optional[str] = None
    confidence: float

class AnomalyDetection(BaseModel):
    has_anomalies: bool
    anomalies: List[Anomaly]
    overall_status: AnomalyStatus
    confidence_score: float
    review_notes: Optional[str] = None

class PaystubData(BaseModel):
    employee_info: EmployeeInfo
    salary_breakdown: SalaryBreakdown
    compliance_info: ComplianceValidation
    pay_period: str
    generated_date: datetime
    template_version: str = "v1.0"

class ProcessingResult(BaseModel):
    success: bool
    employee_id: str
    contract_data: Optional[ContractData] = None
    salary_data: Optional[SalaryBreakdown] = None
    compliance_data: Optional[ComplianceValidation] = None
    anomalies_data: Optional[AnomalyDetection] = None
    paystub_data: Optional[PaystubData] = None
    errors: List[str] = []
    processing_time: Optional[float] = None
    agent_logs: List[Dict[str, Any]] = []

class RAGDocument(BaseModel):
    doc_id: str
    title: str
    content: str
    doc_type: str  # "tax_rule", "pf_rule", "esi_rule", "state_rule"
    source: str
    last_updated: datetime
    metadata: Dict[str, Any] = {}

class AgentResult(BaseModel):
    agent_name: str
    success: bool
    output: Any
    error_message: Optional[str] = None
    execution_time: float
    confidence_score: Optional[float] = None

class WorkflowState(BaseModel):
    contract_path: str
    employee_id: Optional[str] = None
    current_step: str = "start"
    agent_results: Dict[str, AgentResult] = {}
    final_result: Optional[ProcessingResult] = None
    errors: List[str] = []
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None