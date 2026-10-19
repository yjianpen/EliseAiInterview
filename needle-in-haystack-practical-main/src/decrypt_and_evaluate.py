#!/usr/bin/env python3
"""
Engineer-only script to decrypt and run full evaluation.
This script should only be used by the interviewer after the candidate has completed their implementation.
"""
import sys
import os
import json
import getpass
from datetime import datetime

from evaluator import Evaluator
from crypto_utils import load_and_decrypt_qa
from candidate_solution import answer

def main():
    print("\n" + "="*60)
    print("INTERVIEWER EVALUATION TOOL")
    print("="*60)
    print("\nThis tool will decrypt the full Q&A set and evaluate the candidate's solution.")
    
    # Get password securely
    password = getpass.getpass("\nEnter the secret password: ")
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    data_file = os.path.join(data_dir, 'enwiki', 'enwiki-1gb.xml')
    encrypted_qa_path = os.path.join(data_dir, 'encrypted_qa.json')
    
    # Check files exist
    if not os.path.exists(data_file):
        print(f"Error: Wikipedia articles file not found at {data_file}")
        sys.exit(1)
    
    if not os.path.exists(encrypted_qa_path):
        print(f"Error: Encrypted Q&A file not found at {encrypted_qa_path}")
        sys.exit(1)
    
    try:
        print("\nDecrypting Q&A set...")
        qa_set = load_and_decrypt_qa(encrypted_qa_path, password)
        print(f"Successfully decrypted {len(qa_set)} questions")
        
        print("\nStarting evaluation...")
        print("-" * 60)
        
        # Run evaluation
        evaluator = Evaluator(qa_set, verbose=True)
        results = evaluator.run_evaluation(answer, data_file)
        
        # Save full results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = os.path.join(os.path.dirname(__file__), '..', f'evaluation_results_{timestamp}.json')
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Full results saved to: {results_file}\n\n\n")
        
    except ValueError as e:
        print(f"\nError: {e}")
        print("Please check the password and try again.")
        print("\nNote: The interviewer will provide the password when ready for evaluation")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()