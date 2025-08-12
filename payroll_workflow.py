import os
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

# Local imports
from models import (
    WorkflowState, ProcessingResult, AgentResult, 
    ContractData, SalaryBreakdown, ComplianceValidation, 
    AnomalyDetection, PaystubData
)
from agents import (
    ContractReaderAgent, SalaryBreakdownAgent, ComplianceMapperAgent,
    AnomalyDetectorAgent, PaystubGeneratorAgent
)
from rag_system import PayrollRAGSystem

logger = logging.getLogger(__name__)

class PayrollAgenticWorkflow:
    """Simplified workflow for autonomous payroll processing without LangGraph"""
    
    def __init__(self, api_key: str, persist_directory: str = "./chroma_db"):
        self.api_key = api_key
        self.rag_system = PayrollRAGSystem(persist_directory)
        
        # Initialize agents
        self.agents = self._initialize_agents()
        
        logger.info("PayrollAgenticWorkflow initialized successfully")
    
    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize all payroll agents"""
        return {
            "contract_reader": ContractReaderAgent(self.api_key),
            "salary_breakdown": SalaryBreakdownAgent(self.api_key),
            "compliance_mapper": ComplianceMapperAgent(self.api_key, self.rag_system),
            "anomaly_detector": AnomalyDetectorAgent(self.api_key),
            "paystub_generator": PaystubGeneratorAgent(self.api_key)
        }
    
    def process_contract_sync(self, contract_path: str, config: Optional[Dict[str, Any]] = None) -> ProcessingResult:
        """Process a contract through the full pipeline synchronously"""
        
        start_time = datetime.now()
        agent_logs = []
        errors = []
        
        try:
            logger.info(f"Starting payroll processing for contract: {contract_path}")
            
            # Step 1: Contract Reader Agent
            logger.info("Step 1: Contract Reader Agent")
            contract_result = self.agents["contract_reader"].execute(contract_path)
            agent_logs.append({
                "agent": "ContractReaderAgent",
                "success": contract_result.success,
                "execution_time": contract_result.execution_time,
                "error": contract_result.error_message if not contract_result.success else None
            })
            
            if not contract_result.success:
                errors.append(f"Contract Reader failed: {contract_result.error_message}")
                return ProcessingResult(
                    success=False,
                    employee_id="unknown",
                    errors=errors,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_logs=agent_logs
                )
            
            contract_data = contract_result.output
            employee_id = contract_data.employee_info.employee_id if contract_data.employee_info.employee_id else "unknown"
            
            # Step 2: Salary Breakdown Agent
            logger.info("Step 2: Salary Breakdown Agent")
            salary_result = self.agents["salary_breakdown"].execute(contract_data)
            agent_logs.append({
                "agent": "SalaryBreakdownAgent",
                "success": salary_result.success,
                "execution_time": salary_result.execution_time,
                "error": salary_result.error_message if not salary_result.success else None
            })
            
            if not salary_result.success:
                errors.append(f"Salary Breakdown failed: {salary_result.error_message}")
                return ProcessingResult(
                    success=False,
                    employee_id=employee_id,
                    errors=errors,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    agent_logs=agent_logs
                )
            
            salary_data = salary_result.output
            
            # Step 3: Compliance Mapper Agent
            logger.info("Step 3: Compliance Mapper Agent")
            compliance_result = self.agents["compliance_mapper"].execute(salary_data)
            agent_logs.append({
                "agent": "ComplianceMapperAgent",
                "success": compliance_result.success,
                "execution_time": compliance_result.execution_time,
                "error": compliance_result.error_message if not compliance_result.success else None
            })
            
            if not compliance_result.success:
                errors.append(f"Compliance Mapper failed: {compliance_result.error_message}")
                # Continue processing even if compliance fails
            
            compliance_data = compliance_result.output if compliance_result.success else None
            
            # Step 4: Anomaly Detector Agent
            logger.info("Step 4: Anomaly Detector Agent")
            anomaly_input = {
                "contract_data": contract_data,
                "salary_data": salary_data,
                "compliance_data": compliance_data
            }
            anomaly_result = self.agents["anomaly_detector"].execute(anomaly_input)
            agent_logs.append({
                "agent": "AnomalyDetectorAgent",
                "success": anomaly_result.success,
                "execution_time": anomaly_result.execution_time,
                "error": anomaly_result.error_message if not anomaly_result.success else None
            })
            
            if not anomaly_result.success:
                errors.append(f"Anomaly Detector failed: {anomaly_result.error_message}")
                # Continue processing even if anomaly detection fails
            
            anomaly_data = anomaly_result.output if anomaly_result.success else None
            
            # Step 5: Paystub Generator Agent
            logger.info("Step 5: Paystub Generator Agent")
            paystub_input = {
                "contract_data": contract_data,
                "salary_data": salary_data,
                "compliance_data": compliance_data,
                "anomaly_data": anomaly_data
            }
            paystub_result = self.agents["paystub_generator"].execute(paystub_input)
            agent_logs.append({
                "agent": "PaystubGeneratorAgent",
                "success": paystub_result.success,
                "execution_time": paystub_result.execution_time,
                "error": paystub_result.error_message if not paystub_result.success else None
            })
            
            if not paystub_result.success:
                errors.append(f"Paystub Generator failed: {paystub_result.error_message}")
                # Continue processing even if paystub generation fails
            
            paystub_data = paystub_result.output if paystub_result.success else None
            
            # Create final result
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = ProcessingResult(
                success=True,
                employee_id=employee_id,
                contract_data=contract_data,
                salary_data=salary_data,
                compliance_data=compliance_data,
                anomalies_data=anomaly_data,
                paystub_data=paystub_data,
                errors=errors,
                processing_time=processing_time,
                agent_logs=agent_logs
            )
            
            logger.info(f"Payroll processing completed for employee: {employee_id}")
            return result
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ProcessingResult(
                success=False,
                employee_id="unknown",
                errors=[f"Workflow execution failed: {str(e)}"],
                processing_time=processing_time,
                agent_logs=agent_logs
            )
    
    def get_workflow_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get the current state of a workflow thread (simplified)"""
        return {
            "thread_id": thread_id,
            "status": "completed",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_workflow_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get the execution history of a workflow thread (simplified)"""
        return [{
            "thread_id": thread_id,
            "timestamp": datetime.now().isoformat(),
            "status": "completed"
        }]
    
    def update_rag_rules(self, url: str, doc_type: str, title: str):
        """Update RAG system with new compliance rules"""
        try:
            self.rag_system.update_rules_from_url(url, doc_type, title)
            logger.info(f"Updated RAG rules from {url}")
        except Exception as e:
            logger.error(f"Failed to update RAG rules: {e}")
    
    def get_compliance_rules(self, employee_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get applicable compliance rules for an employee"""
        try:
            return self.rag_system.get_all_applicable_rules(employee_data)
        except Exception as e:
            logger.error(f"Failed to get compliance rules: {e}")
            return {}

# Utility functions for workflow management
def create_payroll_workflow(api_key: str, persist_directory: str = "./chroma_db") -> PayrollAgenticWorkflow:
    """Factory function to create a payroll workflow"""
    return PayrollAgenticWorkflow(api_key, persist_directory)

def process_single_contract(contract_path: str, api_key: str, config: Optional[Dict[str, Any]] = None) -> ProcessingResult:
    """Process a single contract through the complete workflow"""
    workflow = create_payroll_workflow(api_key)
    return workflow.process_contract_sync(contract_path, config)

def batch_process_contracts(contract_paths: List[str], api_key: str) -> List[ProcessingResult]:
    """Process multiple contracts in batch"""
    workflow = create_payroll_workflow(api_key)
    results = []
    
    for i, contract_path in enumerate(contract_paths):
        logger.info(f"Processing contract {i+1}/{len(contract_paths)}: {contract_path}")
        config = {"configurable": {"thread_id": f"batch_{i}_{int(time.time())}"}}
        result = workflow.process_contract_sync(contract_path, config)
        results.append(result)
    
    return results