#!/usr/bin/env python3
"""
AgenticAI Payroll System - Setup Script

This script helps set up the payroll system environment.
"""

import os
import sys
import subprocess
import platform

def install_dependencies():
    """Install required Python packages"""
    
    print("📦 Installing dependencies...")
    
    try:
        # Upgrade pip first
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], check=True)
        
        # Install requirements
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
        
        print("✅ Dependencies installed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"❌ Python {version.major}.{version.minor} is not supported")
        print("   Please use Python 3.9 or higher")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def create_env_file():
    """Create .env file template"""
    
    env_content = """# AgenticAI Payroll System Environment Variables

# Google Gemini API Key (Required)
# Get your key from: https://makersuite.google.com/app/apikey
GOOGLE_API_KEY=your_api_key_here

# Optional: Logging level
LOG_LEVEL=INFO

# Optional: ChromaDB persistence directory
CHROMA_DB_PATH=./chroma_db
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ Created .env file template")
    else:
        print("✅ .env file already exists")

def generate_sample_data():
    """Generate sample contract data"""
    
    try:
        subprocess.run([sys.executable, 'sample_contract.py'], check=True)
        print("✅ Sample contracts generated")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate sample contracts: {e}")
        return False

def display_next_steps():
    """Display next steps for the user"""
    
    print("\n" + "="*60)
    print("🎉 Setup Complete!")
    print("="*60)
    print()
    print("Next Steps:")
    print("1. 🔑 Get your Google Gemini API key:")
    print("   https://makersuite.google.com/app/apikey")
    print()
    print("2. 🛠️  Set your API key (choose one):")
    print("   • Edit .env file and add your key")
    print("   • Set environment variable: export GOOGLE_API_KEY='your_key'")
    print("   • Enter it in the Streamlit sidebar when running the app")
    print()
    print("3. 🚀 Run the application:")
    print("   • Web interface: python run_app.py")
    print("   • Command line demo: python demo.py")
    print("   • Direct streamlit: streamlit run agentic_payroll_app.py")
    print()
    print("4. 📁 Sample contracts are available in 'sample_contracts/' directory")
    print()
    print("5. 📚 Read README.md for detailed documentation")
    print()

def main():
    """Main setup function"""
    
    print("=" * 60)
    print("🤖 AgenticAI Payroll System - Setup")
    print("=" * 60)
    print()
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check operating system
    os_name = platform.system()
    print(f"✅ Operating System: {os_name}")
    print()
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Setup failed due to dependency installation issues")
        print("Try running manually:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    
    print()
    
    # Create environment file
    create_env_file()
    print()
    
    # Generate sample data
    print("📄 Generating sample contracts...")
    if generate_sample_data():
        print()
    
    # Display next steps
    display_next_steps()

if __name__ == "__main__":
    main()