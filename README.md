# 🤖 AgenticAI Payroll & Tax Planner

An autonomous AI-powered payroll automation system that processes employee contracts, computes earnings and deductions, ensures compliance with tax policies, and generates complete payroll outputs with minimal human oversight.

## 🎯 Project Overview

This system implements a 5-agent pipeline for end-to-end payroll processing:

1. **Employee Contract Reader Agent** - Parses uploaded contract files to extract salary components and benefits
2. **Salary Breakdown Agent** - Computes full monthly salary and calculates fixed/statutory deductions
3. **Compliance Mapper Agent** - Aligns deductions with latest government rules using RAG
4. **Anomaly & Flag Detector Agent** - Flags discrepancies in calculations and tax treatment
5. **Paystub & Form Generator Agent** - Generates downloadable payslips and statutory forms

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Google Gemini API key (optional for demo mode)

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd agentic-payroll-system
```

2. **Install dependencies:**
```bash
pip install --break-system-packages -r requirements.txt
```

3. **Run the application:**
```bash
streamlit run simple_payroll_app.py
```

4. **Access the application:**
   - Open your browser and go to `http://localhost:8501`
   - The app will be available in demo mode without requiring an API key

## 📋 Features

### Core Functionality

- **📄 Contract Processing**: Upload and parse employment contracts (PDF/TXT)
- **💰 Salary Calculation**: Automatic breakdown of earnings and deductions
- **⚖️ Compliance Validation**: Real-time validation against tax rules and regulations
- **🔍 Anomaly Detection**: Intelligent flagging of calculation errors and inconsistencies
- **📋 Document Generation**: Generate downloadable payslips and tax forms
- **📊 Analytics Dashboard**: Visual insights into processing results and trends

### Agent Pipeline

1. **Contract Reader Agent**
   - Extracts key fields (Basic, HRA, LTA, Variable Pay, Bonuses)
   - Identifies statutory obligations (PF, Gratuity, etc.)
   - Outputs structured JSON mapped to employee ID

2. **Salary Breakdown Agent**
   - Accurate breakdown of earnings and deductions
   - Adjusts prorated amounts for mid-month joiners
   - Logs calculation justification for each line item

3. **Compliance Mapper Agent (RAG-Enabled)**
   - Uses RAG to pull official tax PDFs and rules
   - Maps rules like PF caps, income tax slabs, Section 80C deductions
   - Explains compliance mismatches and suggests corrections

4. **Anomaly Detector Agent**
   - Detects anomalies (excessive HRA, missing TDS entry)
   - Flags calculation gaps and incorrect exemptions
   - Provides context-aware flags with reasons for finance review

5. **Paystub Generator Agent**
   - Includes all relevant salary heads and deductions
   - Uses templated structure for consistency and compliance
   - Embeds verification codes for document authenticity

## 🎮 Usage Guide

### For HR Users

1. **Upload Contract**
   - Navigate to "📤 Process Contract" page
   - Upload an employment contract (PDF or TXT format)
   - Configure processing options as needed

2. **Monitor Processing**
   - Watch real-time progress updates
   - View agent execution status
   - Track processing time and success rates

3. **Review Results**
   - Examine extracted contract data
   - Review salary breakdown and calculations
   - Check compliance validation results
   - Download generated payslips

4. **Dashboard Analytics**
   - View processing statistics
   - Monitor system performance
   - Track employee data trends

### Sample Contracts

The system includes sample contracts for testing:

- `test_contract.txt` - Basic employment contract
- `sample_contracts/contract_1.txt` - John Doe (₹50,000 basic)
- `sample_contracts/contract_2.txt` - Jane Smith (₹75,000 basic)
- `sample_contracts/contract_3.txt` - Mike Johnson (₹35,000 basic)

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   AI Agents     │
│   (Streamlit)   │◄──►│   (Python)      │◄──►│   (LangChain)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dashboard     │    │   Workflow      │    │   RAG System    │
│   Analytics     │    │   Orchestration │    │   Compliance    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow

1. **Contract Upload** → File validation and temporary storage
2. **Text Extraction** → PDF parsing and text extraction
3. **Agent Processing** → Sequential execution of 5 agents
4. **Result Compilation** → Aggregation of agent outputs
5. **Document Generation** → Paystub and form creation
6. **Dashboard Update** → Analytics and reporting

## 🔧 Configuration

### Environment Variables

```bash
# Google Gemini API Key (optional for demo mode)
GOOGLE_API_KEY=your_api_key_here

# Database Configuration
DATABASE_URL=your_database_url

# RAG System Configuration
RAG_PERSIST_DIRECTORY=./chroma_db
```

### Processing Options

- **Auto-validate compliance**: Enable real-time compliance checking
- **Generate paystub**: Create downloadable payslip PDFs
- **Detect anomalies**: Run intelligent anomaly detection
- **Show agent logs**: Display detailed agent execution logs
- **Show raw data**: Include extracted text in results

## 📊 Compliance Features

### Tax Calculations

- **Provident Fund (PF)**: 12% of basic salary (capped at ₹15,000)
- **Employee State Insurance (ESI)**: 1.75% of gross salary (if ≤ ₹21,000)
- **Professional Tax**: State-specific rates and slabs
- **Income Tax (TDS)**: As per applicable tax slabs
- **HRA Exemption**: Based on actual rent paid and city classification

### Validation Rules

- PF contribution limits and caps
- ESI eligibility and calculation accuracy
- Professional tax compliance by state
- Income tax slab validation
- HRA exemption verification

## 🧪 Testing

### Test Scenarios

1. **PF Cap Enforcement**
   - Upload contract with "PF capped at ₹15,000"
   - Verify cap enforcement in calculations

2. **Variable Pay Processing**
   - Add bonus entry as "performance-based"
   - Ensure proper variable pay treatment

3. **Regional Compliance**
   - Test contracts with state-specific clauses
   - Verify RAG mapping for regional rules

4. **Incomplete Contract Handling**
   - Upload incomplete contract
   - Check anomaly detection triggers

### Running Tests

```bash
# Create test contracts
python3 create_test_contract.py

# Run the application
streamlit run simple_payroll_app.py

# Upload test contracts and verify processing
```

## 🚀 Deployment

### Local Development

```bash
# Install dependencies
pip install --break-system-packages -r requirements.txt

# Run development server
streamlit run simple_payroll_app.py --server.port 8501
```

### Production Deployment

```bash
# Using Docker (recommended)
docker build -t agentic-payroll .
docker run -p 8501:8501 agentic-payroll

# Using Streamlit Cloud
# Deploy to streamlit.io for cloud hosting
```

## 📈 Roadmap

### Phase 1 (Current)
- ✅ Basic contract processing
- ✅ Salary calculation engine
- ✅ Compliance validation
- ✅ Anomaly detection
- ✅ Paystub generation

### Phase 2 (Planned)
- 🔄 Advanced PDF parsing
- 🔄 Multi-language support
- 🔄 Batch processing
- 🔄 API endpoints
- 🔄 Database integration

### Phase 3 (Future)
- 📋 Machine learning optimization
- 📋 Advanced analytics
- 📋 Mobile application
- 📋 Integration with HR systems
- 📋 Real-time compliance updates

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

- Create an issue in the GitHub repository
- Check the documentation in the `/docs` folder
- Review the sample contracts for usage examples

## 🙏 Acknowledgments

- Built with Streamlit for the web interface
- Powered by Google Gemini AI for intelligent processing
- Uses LangChain for agent orchestration
- Implements RAG for compliance rule retrieval

---

**Note**: This is a demonstration system. For production use, ensure proper security measures, data privacy compliance, and thorough testing with real payroll data.