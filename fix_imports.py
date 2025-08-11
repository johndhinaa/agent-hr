#!/usr/bin/env python3
"""
Quick fix script for import issues in the AgenticAI Payroll System
"""

import os
import re

def fix_typing_imports(file_path):
    """Fix typing imports in Python files"""
    
    if not file_path.endswith('.py'):
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file has typing imports that need fixing
        if 'from typing import' in content:
            lines = content.split('\n')
            modified = False
            
            for i, line in enumerate(lines):
                if line.startswith('from typing import'):
                    # Common typing imports needed
                    required_imports = ['Dict', 'Any', 'List', 'Optional']
                    current_imports = line.replace('from typing import ', '').split(', ')
                    current_imports = [imp.strip() for imp in current_imports]
                    
                    # Add missing imports
                    for req_import in required_imports:
                        if req_import not in current_imports and req_import.lower() in content.lower():
                            current_imports.append(req_import)
                            modified = True
                    
                    if modified:
                        # Remove duplicates and sort
                        current_imports = list(set(current_imports))
                        current_imports.sort()
                        lines[i] = f"from typing import {', '.join(current_imports)}"
                        break
            
            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                print(f"✅ Fixed imports in {file_path}")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")
        return False

def main():
    """Main function to fix imports in all Python files"""
    
    print("🔧 Fixing import issues in AgenticAI Payroll System...")
    print()
    
    python_files = [
        'models.py',
        'agents.py', 
        'rag_system.py',
        'payroll_workflow.py',
        'agentic_payroll_app.py',
        'sample_contract.py',
        'demo.py',
        'run_app.py',
        'setup.py'
    ]
    
    fixed_count = 0
    
    for file_path in python_files:
        if os.path.exists(file_path):
            if fix_typing_imports(file_path):
                fixed_count += 1
        else:
            print(f"⚠️  File not found: {file_path}")
    
    print()
    if fixed_count > 0:
        print(f"✅ Fixed imports in {fixed_count} files")
    else:
        print("✅ All imports are already correct")
    
    print()
    print("🚀 You can now run the application:")
    print("   streamlit run agentic_payroll_app.py")

if __name__ == "__main__":
    main()