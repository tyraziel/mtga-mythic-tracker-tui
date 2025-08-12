#!/usr/bin/env python3
"""
Simple prompt logging tool that appends prompts to a file without reading existing content.
"""

import sys
import datetime
import os

def log_prompt(prompt_text, log_file="prompts.log"):
    """Append a prompt to the log file with timestamp."""
    timestamp = datetime.datetime.now().isoformat()
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n--- {timestamp} ---\n")
        f.write(prompt_text)
        f.write("\n" + "="*80 + "\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python prompt_logger.py '<prompt_text>' [log_file]")
        print("   or: echo 'prompt' | python prompt_logger.py")
        sys.exit(1)
    
    log_file = sys.argv[2] if len(sys.argv) > 2 else "prompts.log"
    
    if sys.argv[1] == '-':
        # Read from stdin
        prompt_text = sys.stdin.read().strip()
    else:
        prompt_text = sys.argv[1]
    
    if not prompt_text:
        print("Error: No prompt text provided")
        sys.exit(1)
    
    log_prompt(prompt_text, log_file)
    print(f"Prompt logged to {log_file}")

if __name__ == "__main__":
    main()