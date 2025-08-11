#!/usr/bin/env python3
"""
AgenticAI Payroll System - Application Runner

This script sets up the environment and launches the Streamlit application.
"""

import os
import sys
import subprocess
import logging

def setup_environment():
    """Setup the environment for the application"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Check for required environment variables
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  Warning: GOOGLE_API_KEY not found in environment variables.")
        print("   You can set it in the Streamlit sidebar or as an environment variable.")
        print("   Get your API key from: https://makersuite.google.com/app/apikey")
        print()

def check_dependencies():
    """Check if all required dependencies are installed"""
    
    required_packages = [
        'streamlit', 'langchain', 'langgraph', 'chromadb', 
        'langchain-google-genai', 'pydantic', 'plotly', 
        'pandas', 'PyPDF2', 'reportlab'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nInstall missing packages with:")
        print(f"   pip install {' '.join(missing_packages)}")
        print("\nOr install all dependencies with:")
        print("   pip install -r requirements.txt")
        return False
    
    return True

def run_streamlit_app():
    """Launch the Streamlit application"""
    
    print("🚀 Starting AgenticAI Payroll System...")
    print("   Dashboard will open in your default browser")
    print("   Press Ctrl+C to stop the application")
    print()
    
    try:
        # Run streamlit app
        subprocess.run([
            sys.executable, '-m', 'streamlit', 'run', 
            'agentic_payroll_app.py',
            '--server.headless', 'false',
            '--server.port', '8501',
            '--browser.gatherUsageStats', 'false'
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Streamlit application: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user")
        sys.exit(0)

def main():
    """Main application entry point"""
    
    print("=" * 60)
    print("🤖 AgenticAI Payroll Processing System")
    print("   Autonomous 5-Agent Payroll Automation")
    print("=" * 60)
    print()
    
    # Setup environment
    setup_environment()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    print("✅ All dependencies are installed")
    print()
    
    # Check for sample contracts
    if os.path.exists('sample_contracts'):
        contract_count = len([f for f in os.listdir('sample_contracts') if f.endswith('.pdf')])
        print(f"📄 Found {contract_count} sample contracts for testing")
    else:
        print("📄 No sample contracts found. Generate them with:")
        print("   python sample_contract.py")
    
    print()
    
    # Launch application
    run_streamlit_app()

if __name__ == "__main__":
    main()