import os
import logging
import time
from typing import Dict, Any, Optional, TypedDict, Annotated, List
from datetime import datetime

# LangGraph imports
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage

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

class PayrollWorkflowState(TypedDict):
    """State for the payroll processing workflow"""
    contract_path: str
    employee_id: Optional[str]
    current_step: str
    agent_results: Dict[str, AgentResult]
    final_result: Optional[ProcessingResult]
    errors: list[str]
    started_at: datetime
    completed_at: Optional[datetime]
    messages: Annotated[list[BaseMessage], add_messages]

class PayrollAgenticWorkflow:
    """LangGraph-powered workflow for autonomous payroll processing"""
    
    def __init__(self, api_key: str, persist_directory: str = "./chroma_db"):
        self.api_key = api_key
        self.rag_system = PayrollRAGSystem(persist_directory)
        
        # Initialize agents
        self.agents = self._initialize_agents()
        
        # Create workflow graph
        self.workflow = self._create_workflow_graph()
        
        # Setup memory checkpointer
        self.memory = MemorySaver()
        
        # Compile the graph
        self.app = self.workflow.compile(checkpointer=self.memory)
        
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
    
    def _create_workflow_graph(self) -> StateGraph:
        """Create the LangGraph workflow"""
        
        # Define the workflow graph
        workflow = StateGraph(PayrollWorkflowState)
        
        # Add nodes for each agent
        workflow.add_node("contract_reader", self._contract_reader_node)
        workflow.add_node("salary_breakdown", self._salary_breakdown_node)
        workflow.add_node("compliance_mapper", self._compliance_mapper_node)
        workflow.add_node("anomaly_detector", self._anomaly_detector_node)
        workflow.add_node("paystub_generator", self._paystub_generator_node)
        workflow.add_node("finalize_result", self._finalize_result_node)
        
        # Define the workflow edges (sequential processing)
        workflow.add_edge(START, "contract_reader")
        workflow.add_edge("contract_reader", "salary_breakdown")
        workflow.add_edge("salary_breakdown", "compliance_mapper")
        workflow.add_edge("compliance_mapper", "anomaly_detector")
        workflow.add_edge("anomaly_detector", "paystub_generator")
        workflow.add_edge("paystub_generator", "finalize_result")
        workflow.add_edge("finalize_result", END)
        
        return workflow
    
    def _contract_reader_node(self, state: PayrollWorkflowState) -> PayrollWorkflowState:
        """Node for contract reading agent"""
        logger.info("Starting contract reader agent")
        
        try:
            # Execute contract reader agent
            agent_result = self.agents["contract_reader"].execute(state["contract_path"])
            
            # Update state
            state["agent_results"]["contract_reader"] = agent_result
            state["current_step"] = "contract_reader"
            
            if not agent_result.success:
                state["errors"].append(f"Contract Reader failed: {agent_result.error_message}")
                logger.error(f"Contract Reader failed: {agent_result.error_message}")
            else:
                # Extract employee ID if available
                contract_data = agent_result.output
                if contract_data and contract_data.employee_info.employee_id:
                    state["employee_id"] = contract_data.employee_info.employee_id
                
                logger.info("Contract reader agent completed successfully")
            
        except Exception as e:
            error_msg = f"Contract Reader node failed: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg)
        
        return state
    
    def _salary_breakdown_node(self, state: PayrollWorkflowState) -> PayrollWorkflowState:
        """Node for salary breakdown agent"""
        logger.info("Starting salary breakdown agent")
        
        try:
            # Check if previous step succeeded
            contract_result = state["agent_results"].get("contract_reader")
            if not contract_result or not contract_result.success:
                error_msg = "Cannot proceed with salary breakdown - contract reading failed"
                state["errors"].append(error_msg)
                logger.error(error_msg)
                return state
            
            # Execute salary breakdown agent
            contract_data = contract_result.output
            agent_result = self.agents["salary_breakdown"].execute(contract_data)
            
            # Update state
            state["agent_results"]["salary_breakdown"] = agent_result
            state["current_step"] = "salary_breakdown"
            
            if not agent_result.success:
                state["errors"].append(f"Salary Breakdown failed: {agent_result.error_message}")
                logger.error(f"Salary Breakdown failed: {agent_result.error_message}")
            else:
                logger.info("Salary breakdown agent completed successfully")
            
        except Exception as e:
            error_msg = f"Salary Breakdown node failed: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg)
        
        return state
    
    def _compliance_mapper_node(self, state: PayrollWorkflowState) -> PayrollWorkflowState:
        """Node for compliance mapper agent"""
        logger.info("Starting compliance mapper agent")
        
        try:
            # Check if previous step succeeded
            salary_result = state["agent_results"].get("salary_breakdown")
            if not salary_result or not salary_result.success:
                error_msg = "Cannot proceed with compliance mapping - salary breakdown failed"
                state["errors"].append(error_msg)
                logger.error(error_msg)
                return state
            
            # Execute compliance mapper agent
            salary_data = salary_result.output
            agent_result = self.agents["compliance_mapper"].execute(salary_data)
            
            # Update state
            state["agent_results"]["compliance_mapper"] = agent_result
            state["current_step"] = "compliance_mapper"
            
            if not agent_result.success:
                state["errors"].append(f"Compliance Mapper failed: {agent_result.error_message}")
                logger.error(f"Compliance Mapper failed: {agent_result.error_message}")
            else:
                logger.info("Compliance mapper agent completed successfully")
            
        except Exception as e:
            error_msg = f"Compliance Mapper node failed: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg)
        
        return state
    
    def _anomaly_detector_node(self, state: PayrollWorkflowState) -> PayrollWorkflowState:
        """Node for anomaly detector agent"""
        logger.info("Starting anomaly detector agent")
        
        try:
            # Gather data from previous agents
            contract_result = state["agent_results"].get("contract_reader")
            salary_result = state["agent_results"].get("salary_breakdown")
            compliance_result = state["agent_results"].get("compliance_mapper")
            
            # Prepare data for anomaly detection
            anomaly_input = {
                "contract_data": contract_result.output if contract_result and contract_result.success else None,
                "salary_data": salary_result.output if salary_result and salary_result.success else None,
                "compliance_data": compliance_result.output if compliance_result and compliance_result.success else None
            }
            
            # Execute anomaly detector agent
            agent_result = self.agents["anomaly_detector"].execute(anomaly_input)
            
            # Update state
            state["agent_results"]["anomaly_detector"] = agent_result
            state["current_step"] = "anomaly_detector"
            
            if not agent_result.success:
                state["errors"].append(f"Anomaly Detector failed: {agent_result.error_message}")
                logger.error(f"Anomaly Detector failed: {agent_result.error_message}")
            else:
                logger.info("Anomaly detector agent completed successfully")
            
        except Exception as e:
            error_msg = f"Anomaly Detector node failed: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg)
        
        return state
    
    def _paystub_generator_node(self, state: PayrollWorkflowState) -> PayrollWorkflowState:
        """Node for paystub generator agent"""
        logger.info("Starting paystub generator agent")
        
        try:
            # Gather data from previous agents
            contract_result = state["agent_results"].get("contract_reader")
            salary_result = state["agent_results"].get("salary_breakdown")
            compliance_result = state["agent_results"].get("compliance_mapper")
            
            # Check if we have minimum required data
            if not (contract_result and contract_result.success and 
                   salary_result and salary_result.success):
                error_msg = "Cannot generate paystub - missing required data"
                state["errors"].append(error_msg)
                logger.error(error_msg)
                return state
            
            # Prepare data for paystub generation
            paystub_input = {
                "contract_data": contract_result.output,
                "salary_data": salary_result.output,
                "compliance_data": compliance_result.output if compliance_result and compliance_result.success else None
            }
            
            # Execute paystub generator agent
            agent_result = self.agents["paystub_generator"].execute(paystub_input)
            
            # Update state
            state["agent_results"]["paystub_generator"] = agent_result
            state["current_step"] = "paystub_generator"
            
            if not agent_result.success:
                state["errors"].append(f"Paystub Generator failed: {agent_result.error_message}")
                logger.error(f"Paystub Generator failed: {agent_result.error_message}")
            else:
                logger.info("Paystub generator agent completed successfully")
            
        except Exception as e:
            error_msg = f"Paystub Generator node failed: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg)
        
        return state
    
    def _finalize_result_node(self, state: PayrollWorkflowState) -> PayrollWorkflowState:
        """Node to finalize the processing result"""
        logger.info("Finalizing processing result")
        
        try:
            # Set completion time
            state["completed_at"] = datetime.now()
            state["current_step"] = "completed"
            
            # Gather results from all agents
            contract_result = state["agent_results"].get("contract_reader")
            salary_result = state["agent_results"].get("salary_breakdown")
            compliance_result = state["agent_results"].get("compliance_mapper")
            anomaly_result = state["agent_results"].get("anomaly_detector")
            paystub_result = state["agent_results"].get("paystub_generator")
            
            # Determine overall success
            critical_agents = ["contract_reader", "salary_breakdown"]
            success = all(
                state["agent_results"].get(agent) and 
                state["agent_results"][agent].success 
                for agent in critical_agents
            )
            
            # Create final processing result
            processing_time = (state["completed_at"] - state["started_at"]).total_seconds()
            
            final_result = ProcessingResult(
                success=success,
                employee_id=state.get("employee_id", "unknown"),
                contract_data=contract_result.output if contract_result and contract_result.success else None,
                salary_data=salary_result.output if salary_result and salary_result.success else None,
                compliance_data=compliance_result.output if compliance_result and compliance_result.success else None,
                anomalies_data=anomaly_result.output if anomaly_result and anomaly_result.success else None,
                paystub_data=paystub_result.output if paystub_result and paystub_result.success else None,
                errors=state["errors"],
                processing_time=processing_time,
                agent_logs=[
                    {
                        "agent": name,
                        "success": result.success,
                        "execution_time": result.execution_time,
                        "error": result.error_message
                    }
                    for name, result in state["agent_results"].items()
                ]
            )
            
            state["final_result"] = final_result
            
            logger.info(f"Processing completed successfully: {success}, Total time: {processing_time:.2f}s")
            
        except Exception as e:
            error_msg = f"Failed to finalize result: {str(e)}"
            state["errors"].append(error_msg)
            logger.error(error_msg)
        
        return state
    
    async def process_contract(self, contract_path: str, config: Optional[Dict[str, Any]] = None) -> ProcessingResult:
        """Process a contract through the full pipeline"""
        
        # Create initial state
        initial_state = PayrollWorkflowState(
            contract_path=contract_path,
            employee_id=None,
            current_step="start",
            agent_results={},
            final_result=None,
            errors=[],
            started_at=datetime.now(),
            completed_at=None,
            messages=[]
        )
        
        # Set default config
        if config is None:
            config = {"configurable": {"thread_id": f"payroll_{int(time.time())}"}}
        
        try:
            logger.info(f"Starting payroll processing for contract: {contract_path}")
            
            # Run the workflow
            final_state = await self.app.ainvoke(initial_state, config)
            
            # Return the final result
            result = final_state.get("final_result")
            if result:
                logger.info(f"Payroll processing completed for employee: {result.employee_id}")
                return result
            else:
                # Create error result if no final result was generated
                return ProcessingResult(
                    success=False,
                    employee_id="unknown",
                    errors=final_state.get("errors", ["Unknown error occurred"]),
                    processing_time=(datetime.now() - initial_state["started_at"]).total_seconds()
                )
                
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return ProcessingResult(
                success=False,
                employee_id="unknown",
                errors=[f"Workflow execution failed: {str(e)}"],
                processing_time=(datetime.now() - initial_state["started_at"]).total_seconds()
            )
    
    def process_contract_sync(self, contract_path: str, config: Optional[Dict[str, Any]] = None) -> ProcessingResult:
        """Synchronous version of contract processing"""
        
        # Create initial state
        initial_state = PayrollWorkflowState(
            contract_path=contract_path,
            employee_id=None,
            current_step="start",
            agent_results={},
            final_result=None,
            errors=[],
            started_at=datetime.now(),
            completed_at=None,
            messages=[]
        )
        
        # Set default config
        if config is None:
            config = {"configurable": {"thread_id": f"payroll_{int(time.time())}"}}
        
        try:
            logger.info(f"Starting payroll processing for contract: {contract_path}")
            
            # Run the workflow synchronously
            final_state = self.app.invoke(initial_state, config)
            
            # Return the final result
            result = final_state.get("final_result")
            if result:
                logger.info(f"Payroll processing completed for employee: {result.employee_id}")
                return result
            else:
                # Create error result if no final result was generated
                return ProcessingResult(
                    success=False,
                    employee_id="unknown",
                    errors=final_state.get("errors", ["Unknown error occurred"]),
                    processing_time=(datetime.now() - initial_state["started_at"]).total_seconds()
                )
                
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return ProcessingResult(
                success=False,
                employee_id="unknown",
                errors=[f"Workflow execution failed: {str(e)}"],
                processing_time=(datetime.now() - initial_state["started_at"]).total_seconds()
            )
    
    def get_workflow_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get the current state of a workflow thread"""
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.app.get_state(config)
            return state.values if state else None
        except Exception as e:
            logger.error(f"Failed to get workflow state: {e}")
            return None
    
    def get_workflow_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get the execution history of a workflow thread"""
        try:
            config = {"configurable": {"thread_id": thread_id}}
            history = []
            
            for state in self.app.get_state_history(config):
                history.append({
                    "timestamp": state.created_at,
                    "step": state.values.get("current_step", "unknown"),
                    "errors": state.values.get("errors", []),
                    "agent_results": {
                        name: {
                            "success": result.success,
                            "execution_time": result.execution_time
                        }
                        for name, result in state.values.get("agent_results", {}).items()
                    }
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get workflow history: {e}")
            return []
    
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