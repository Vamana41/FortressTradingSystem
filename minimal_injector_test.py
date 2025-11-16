#!/usr/bin/env python3
"""
Minimal test matching the injector's exact approach
"""

import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

# Load environment
load_dotenv('openalgo_symbol_injector.env')

class MinimalInjector:
    def __init__(self):
        self.ws_url = os.getenv('OPENALGO_WS_URL', 'ws://127.0.0.1:8765')
        self.api_key = os.getenv('OPENALGO_API_KEY', '703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b')
        self.websocket = None
        
    async def connect(self):
        """Connect to OpenAlgo WebSocket"""
        try:
            print(f"Connecting to OpenAlgo WebSocket at {self.ws_url}...")
            self.websocket = await websockets.connect(self.ws_url)
            print("✅ Connected to OpenAlgo WebSocket!")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to WebSocket: {e}")
            return False
    
    async def authenticate(self):
        """Authenticate with OpenAlgo using API key"""
        try:
            auth_message = {
                "action": "auth",
                "api_key": self.api_key
            }
            
            print("Authenticating with OpenAlgo...")
            print(f"Using API key: {self.api_key[:10]}...")
            await self.websocket.send(json.dumps(auth_message))
            
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
            auth_data = json.loads(response)
            
            print(f"Auth response: {auth_data}")
            
            if auth_data.get("status") == "success":
                print(f"✅ Authentication successful! User: {auth_data.get('user_id')}")
                return True
            else:
                print(f"❌ Authentication failed: {auth_data}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False

async def main():
    injector = MinimalInjector()
    
    # Connect to WebSocket
    if not await injector.connect():
        return
    
    # Authenticate
    if not await injector.authenticate():
        return
    
    print("✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(main())