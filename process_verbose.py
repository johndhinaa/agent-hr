#!/usr/bin/env python3

import os
import sys
import tempfile
from real_workflow import create_real_payroll_workflow

USAGE = """
Usage:
  GOOGLE_API_KEY=... python3 process_verbose.py /absolute/path/to/contract.txt
"""

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)
    contract_path = sys.argv[1]
    if not os.path.isabs(contract_path):
        contract_path = os.path.abspath(contract_path)
    if not os.path.exists(contract_path):
        print(f"Contract file not found: {contract_path}")
        sys.exit(1)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY env var not set. Export it and retry.")
        sys.exit(1)

    # Create workflow with verbose=True to stream agent prompts/responses
    workflow = create_real_payroll_workflow(api_key, verbose=True)

    print("\n=== Running Agentic AI Payroll Workflow (verbose mode) ===")
    result = workflow.process_contract_sync(contract_path)

    print("\n=== Final Result ===")
    print({
        "success": result.success,
        "employee_id": result.employee_id,
        "processing_time": result.processing_time,
        "errors": result.errors,
    })

    print("\n=== Agent Logs (with raw prompts/responses) ===")
    for log in result.agent_logs:
        print(f"\n--- {log['agent']} ---")
        print({k: v for k, v in log.items() if k in ["success", "execution_time", "confidence_score", "error"]})
        if log.get("raw_prompt"):
            print("Prompt:")
            print(log["raw_prompt"])
        if log.get("raw_response"):
            print("Response:")
            print(log["raw_response"])

if __name__ == "__main__":
    main()