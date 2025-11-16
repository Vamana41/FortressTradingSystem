#!/usr/bin/env python3
"""Check OpenAlgo version format"""

import requests
import re

# Try to get the actual OpenAlgo version file
try:
    url = 'https://raw.githubusercontent.com/marketcalls/OpenAlgo/master/openalgo/utils/version.py'
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        content = response.text
        print('OpenAlgo version file content:')
        print(content)
        print()
        
        # Test different regex patterns
        patterns = [
            r'VERSION\s*=\s*[\'\"]([^\'\"]+)[\'\"]',
            r'__version__\s*=\s*[\'\"]([^\'\"]+)[\'\"]',
            r'version\s*=\s*[\'\"]([^\'\"]+)[\'\"]',
            r'[\'\"](\d+\.\d+\.\d+\.?\d*)[\'\"]'
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                print(f'Pattern {i+1} found version: {match.group(1)}')
            else:
                print(f'Pattern {i+1}: No match')
    else:
        print(f'Failed to fetch version file: {response.status_code}')
except Exception as e:
    print(f'Error: {e}')