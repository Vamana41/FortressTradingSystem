#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv("openalgo_symbol_injector.env")

print("Environment variables loaded:")
print(f"OPENALGO_API_KEY from env: {os.getenv('OPENALGO_API_KEY', 'NOT_FOUND')}")
print(f"OPENALGO_BASE_URL from env: {os.getenv('OPENALGO_BASE_URL', 'NOT_FOUND')}")

# Check if there's a system environment variable
import os
print(f"System OPENALGO_API_KEY: {os.environ.get('OPENALGO_API_KEY', 'NOT_FOUND')}")
