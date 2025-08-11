import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import chromadb
from chromadb.config import Settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import WebBaseLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models import RAGDocument, ComplianceRule

logger = logging.getLogger(__name__)

class PayrollRAGSystem:
    """RAG system for payroll compliance rules and tax regulations"""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        
        # Create collections for different types of documents
        self.collections = {
            "tax_rules": self._get_or_create_collection("tax_rules"),
            "pf_rules": self._get_or_create_collection("pf_rules"),
            "esi_rules": self._get_or_create_collection("esi_rules"),
            "state_rules": self._get_or_create_collection("state_rules"),
            "general_compliance": self._get_or_create_collection("general_compliance")
        }
        
        # Initialize with default compliance data
        self._initialize_default_rules()
    
    def _get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection"""
        try:
            return self.client.get_collection(name)
        except:
            return self.client.create_collection(name)
    
    def _initialize_default_rules(self):
        """Initialize with basic Indian payroll compliance rules"""
        default_rules = [
            {
                "doc_id": "pf_rule_2024",
                "title": "Provident Fund Contribution Rules 2024",
                "content": """
                Provident Fund (PF) Contribution Rules:
                - Employee Contribution: 12% of basic salary
                - Employer Contribution: 12% of basic salary (3.67% to PF + 8.33% to EPS)
                - Maximum PF contribution cap: ₹1,800 per month (for basic salary > ₹15,000)
                - PF is mandatory for establishments with 20+ employees
                - Basic salary for PF calculation = Basic + DA (if DA is part of retirement benefits)
                - Minimum pension: ₹1,000 per month
                - Maximum pensionable salary: ₹15,000 per month
                """,
                "doc_type": "pf_rule",
                "source": "EPFO Guidelines 2024",
                "metadata": {"rate": 0.12, "cap": 1800, "applicable_from": "2024-01-01"}
            },
            {
                "doc_id": "esi_rule_2024",
                "title": "ESI Contribution Rules 2024",
                "content": """
                Employee State Insurance (ESI) Rules:
                - Employee Contribution: 0.75% of gross salary
                - Employer Contribution: 3.25% of gross salary
                - Applicable for employees earning up to ₹21,000 per month
                - Medical benefits for employee and dependents
                - Cash benefits during sickness and maternity
                - Coverage includes spouse, children up to 26 years, and dependent parents
                """,
                "doc_type": "esi_rule",
                "source": "ESIC Guidelines 2024",
                "metadata": {"employee_rate": 0.0075, "employer_rate": 0.0325, "salary_limit": 21000}
            },
            {
                "doc_id": "tds_rule_2024",
                "title": "TDS on Salary Rules 2024-25",
                "content": """
                Tax Deduction at Source (TDS) on Salary:
                Income Tax Slabs for FY 2024-25:
                - Up to ₹2,50,000: Nil
                - ₹2,50,001 to ₹5,00,000: 5%
                - ₹5,00,001 to ₹10,00,000: 20%
                - Above ₹10,00,000: 30%
                
                Additional Surcharge:
                - 10% if income > ₹50 lakhs and ≤ ₹1 crore
                - 15% if income > ₹1 crore
                
                Health and Education Cess: 4% on income tax + surcharge
                
                Standard Deduction: ₹50,000
                Section 80C Limit: ₹1,50,000
                Section 80D (Health Insurance): ₹25,000 (₹50,000 for senior citizens)
                """,
                "doc_type": "tax_rule",
                "source": "Income Tax Act 2024-25",
                "metadata": {"standard_deduction": 50000, "80c_limit": 150000}
            },
            {
                "doc_id": "professional_tax_2024",
                "title": "Professional Tax Rules by State 2024",
                "content": """
                Professional Tax Rates by State:
                
                Karnataka:
                - Up to ₹15,000: Nil
                - ₹15,001 to ₹25,000: ₹200/month
                - Above ₹25,000: ₹300/month
                
                Maharashtra:
                - Up to ₹5,000: Nil
                - ₹5,001 to ₹10,000: ₹175/month
                - Above ₹10,000: ₹200/month
                
                West Bengal:
                - Up to ₹10,000: ₹110/month
                - ₹10,001 to ₹15,000: ₹130/month
                - Above ₹15,000: ₹200/month
                
                Tamil Nadu:
                - Flat rate: ₹200/month for all salaried employees
                """,
                "doc_type": "state_rule",
                "source": "State Government Notifications 2024",
                "metadata": {"type": "professional_tax", "year": 2024}
            },
            {
                "doc_id": "gratuity_rule_2024",
                "title": "Gratuity Calculation Rules 2024",
                "content": """
                Gratuity Rules:
                - Applicable for employees completing 5+ years of service
                - Formula: (Last drawn salary × 15 days × Years of service) / 26
                - Maximum gratuity: ₹20,00,000
                - Last drawn salary = Basic + DA
                - 26 working days per month for calculation
                - Tax exemption up to ₹20,00,000
                - Gratuity is payable on resignation, retirement, death, or disablement
                """,
                "doc_type": "general_compliance",
                "source": "Payment of Gratuity Act 1972",
                "metadata": {"max_amount": 2000000, "service_years": 5}
            }
        ]
        
        for rule in default_rules:
            self.add_document(rule)
    
    def add_document(self, doc_data: Dict[str, Any]):
        """Add a document to the RAG system"""
        try:
            doc = RAGDocument(
                doc_id=doc_data["doc_id"],
                title=doc_data["title"],
                content=doc_data["content"],
                doc_type=doc_data["doc_type"],
                source=doc_data["source"],
                last_updated=datetime.now(),
                metadata=doc_data.get("metadata", {})
            )
            
            # Get the appropriate collection
            collection_name = doc.doc_type + "s" if not doc.doc_type.endswith("s") else doc.doc_type
            if collection_name not in self.collections:
                collection_name = "general_compliance"
            
            collection = self.collections[collection_name]
            
            # Generate embedding
            embedding = self.embeddings.embed_query(doc.content)
            
            # Add to ChromaDB
            collection.add(
                embeddings=[embedding],
                documents=[doc.content],
                metadatas=[{
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "doc_type": doc.doc_type,
                    "source": doc.source,
                    "last_updated": doc.last_updated.isoformat(),
                    **doc.metadata
                }],
                ids=[doc.doc_id]
            )
            
            logger.info(f"Added document: {doc.doc_id}")
            
        except Exception as e:
            logger.error(f"Error adding document {doc_data.get('doc_id', 'unknown')}: {e}")
    
    def search_compliance_rules(self, query: str, rule_type: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for compliance rules relevant to the query"""
        try:
            results = []
            
            # Determine which collections to search
            collections_to_search = []
            if rule_type:
                collection_name = rule_type + "s" if not rule_type.endswith("s") else rule_type
                if collection_name in self.collections:
                    collections_to_search = [collection_name]
                else:
                    collections_to_search = ["general_compliance"]
            else:
                collections_to_search = list(self.collections.keys())
            
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Search in relevant collections
            for collection_name in collections_to_search:
                collection = self.collections[collection_name]
                search_results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k, 10),
                    include=["documents", "metadatas", "distances"]
                )
                
                for i, doc in enumerate(search_results["documents"][0]):
                    results.append({
                        "content": doc,
                        "metadata": search_results["metadatas"][0][i],
                        "distance": search_results["distances"][0][i],
                        "collection": collection_name
                    })
            
            # Sort by relevance (distance)
            results.sort(key=lambda x: x["distance"])
            
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Error searching compliance rules: {e}")
            return []
    
    def get_pf_rules(self, basic_salary: float) -> Dict[str, Any]:
        """Get specific PF rules for a given basic salary"""
        query = f"PF provident fund contribution rules basic salary {basic_salary}"
        results = self.search_compliance_rules(query, "pf_rule", top_k=3)
        
        # Extract structured PF information
        pf_info = {
            "employee_rate": 0.12,
            "employer_rate": 0.12,
            "max_contribution": 1800,
            "applicable": True,
            "calculation_base": "basic_salary",
            "rules": [r["content"] for r in results]
        }
        
        return pf_info
    
    def get_esi_rules(self, gross_salary: float) -> Dict[str, Any]:
        """Get specific ESI rules for a given gross salary"""
        query = f"ESI employee state insurance contribution rules gross salary {gross_salary}"
        results = self.search_compliance_rules(query, "esi_rule", top_k=3)
        
        # Determine ESI applicability
        applicable = gross_salary <= 21000
        
        esi_info = {
            "employee_rate": 0.0075 if applicable else 0,
            "employer_rate": 0.0325 if applicable else 0,
            "salary_limit": 21000,
            "applicable": applicable,
            "rules": [r["content"] for r in results]
        }
        
        return esi_info
    
    def get_tax_rules(self, annual_income: float) -> Dict[str, Any]:
        """Get specific tax rules for a given annual income"""
        query = f"income tax TDS rules annual income {annual_income} tax slabs"
        results = self.search_compliance_rules(query, "tax_rule", top_k=3)
        
        # Calculate applicable tax slab
        tax_info = {
            "standard_deduction": 50000,
            "section_80c_limit": 150000,
            "applicable_slab": self._get_tax_slab(annual_income),
            "rules": [r["content"] for r in results]
        }
        
        return tax_info
    
    def get_professional_tax_rules(self, state: str, gross_salary: float) -> Dict[str, Any]:
        """Get professional tax rules for a specific state and salary"""
        query = f"professional tax rules {state} salary {gross_salary}"
        results = self.search_compliance_rules(query, "state_rule", top_k=3)
        
        # State-specific professional tax calculation
        pt_amount = self._calculate_professional_tax(state, gross_salary)
        
        pt_info = {
            "state": state,
            "monthly_amount": pt_amount,
            "applicable": pt_amount > 0,
            "rules": [r["content"] for r in results]
        }
        
        return pt_info
    
    def _get_tax_slab(self, annual_income: float) -> str:
        """Determine tax slab for given annual income"""
        if annual_income <= 250000:
            return "0%"
        elif annual_income <= 500000:
            return "5%"
        elif annual_income <= 1000000:
            return "20%"
        else:
            return "30%"
    
    def _calculate_professional_tax(self, state: str, gross_salary: float) -> float:
        """Calculate professional tax based on state and salary"""
        state_lower = state.lower()
        
        if "karnataka" in state_lower:
            if gross_salary <= 15000:
                return 0
            elif gross_salary <= 25000:
                return 200
            else:
                return 300
        elif "maharashtra" in state_lower:
            if gross_salary <= 5000:
                return 0
            elif gross_salary <= 10000:
                return 175
            else:
                return 200
        elif "west bengal" in state_lower or "bengal" in state_lower:
            if gross_salary <= 10000:
                return 110
            elif gross_salary <= 15000:
                return 130
            else:
                return 200
        elif "tamil nadu" in state_lower:
            return 200
        else:
            # Default for states with professional tax
            return 200 if gross_salary > 15000 else 0
    
    def update_rules_from_url(self, url: str, doc_type: str, title: str):
        """Update compliance rules from external URLs"""
        try:
            loader = WebBaseLoader(url)
            documents = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            
            for i, doc in enumerate(documents):
                chunks = text_splitter.split_text(doc.page_content)
                
                for j, chunk in enumerate(chunks):
                    doc_data = {
                        "doc_id": f"{doc_type}_{title}_{i}_{j}",
                        "title": f"{title} - Part {j+1}",
                        "content": chunk,
                        "doc_type": doc_type,
                        "source": url,
                        "metadata": {"url": url, "chunk_index": j}
                    }
                    self.add_document(doc_data)
            
            logger.info(f"Updated rules from URL: {url}")
            
        except Exception as e:
            logger.error(f"Error updating rules from URL {url}: {e}")
    
    def get_all_applicable_rules(self, employee_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get all applicable compliance rules for an employee"""
        try:
            basic_salary = employee_data.get("basic_salary", 0)
            gross_salary = employee_data.get("gross_salary", 0)
            annual_income = gross_salary * 12
            state = employee_data.get("state", "Karnataka")
            
            rules = {
                "pf_rules": self.get_pf_rules(basic_salary),
                "esi_rules": self.get_esi_rules(gross_salary),
                "tax_rules": self.get_tax_rules(annual_income),
                "professional_tax_rules": self.get_professional_tax_rules(state, gross_salary)
            }
            
            return rules
            
        except Exception as e:
            logger.error(f"Error getting applicable rules: {e}")
            return {}