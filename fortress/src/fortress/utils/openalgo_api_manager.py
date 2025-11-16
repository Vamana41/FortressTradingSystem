"""
OpenAlgo API Key Manager with Automatic Regeneration Detection
Handles API key retrieval from web interface and automatic updates
"""

import asyncio
import aiohttp
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import time
import re
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class OpenAlgoAPIManager:
    """Manages OpenAlgo API keys with automatic regeneration detection"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session = None
        self.current_api_key = None
        self.last_key_check = None
        self.key_check_interval = 300  # Check every 5 minutes
        self._key_cache_file = Path.home() / ".fortress" / "openalgo_api_key.json"
        self._key_cache_file.parent.mkdir(exist_ok=True)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def get_api_key_from_dashboard(self, username: str, password: str) -> Optional[str]:
        """Get API key from OpenAlgo dashboard by logging in and accessing API key page"""
        try:
            # First, login to get session cookie
            login_url = urljoin(self.base_url, "/auth/login")
            login_data = {
                "username": username,
                "password": password
            }
            
            async with self.session.post(login_url, data=login_data) as response:
                if response.status != 200:
                    logger.error(f"Login failed with status {response.status}")
                    return None
                    
                # Get session cookies
                cookies = response.cookies
                
            # Now access the API key page
            api_key_url = urljoin(self.base_url, "/apikey")
            
            async with self.session.get(api_key_url, cookies=cookies) as response:
                if response.status != 200:
                    logger.error(f"Failed to access API key page with status {response.status}")
                    return None
                    
                html_content = await response.text()
                
                # Extract API key from HTML content
                api_key = self._extract_api_key_from_html(html_content)
                if api_key:
                    logger.info(f"Successfully retrieved API key from dashboard")
                    self.current_api_key = api_key
                    self._save_key_to_cache(api_key)
                    return api_key
                    
                logger.error("Could not extract API key from HTML content")
                return None
                
        except Exception as e:
            logger.error(f"Error getting API key from dashboard: {e}")
            return None
            
    def _extract_api_key_from_html(self, html_content: str) -> Optional[str]:
        """Extract API key from HTML content using various patterns"""
        # Look for API key in various possible formats
        patterns = [
            r'api[_-]?key["\']?\s*[:=]\s*["\']([a-f0-9]{64})["\']',
            r'["\']([a-f0-9]{64})["\'].*api[_-]?key',
            r'value=["\']([a-f0-9]{64})["\']',
            r'data-apikey=["\']([a-f0-9]{64})["\']',
            r'class=["\']api-key["\'][^>]*>([a-f0-9]{64})<',
            r'>([a-f0-9]{64})<.*api[_-]?key',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                api_key = match.group(1)
                # Validate it's a proper hex string of correct length
                if len(api_key) == 64 and all(c in 'abcdef0123456789' for c in api_key.lower()):
                    logger.info(f"Found API key using pattern: {pattern}")
                    return api_key
                    
        # If no pattern matches, look for any 64-character hex string
        hex_pattern = r'[a-f0-9]{64}'
        matches = re.findall(hex_pattern, html_content, re.IGNORECASE)
        for match in matches:
            # Additional validation - check if it looks like an API key
            if self._looks_like_api_key(match, html_content):
                logger.info(f"Found potential API key: {match[:8]}...")
                return match
                
        return None
        
    def _looks_like_api_key(self, hex_string: str, html_content: str) -> bool:
        """Check if a hex string looks like an API key based on context"""
        # Look for surrounding context that suggests it's an API key
        context_patterns = [
            r'api[_-]?key',
            r'token',
            r'auth',
            r'secret',
            r'key',
            r'generate',
            r'regenerate',
            r'copy',
        ]
        
        # Check surrounding context (100 characters before and after)
        for pattern in context_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                return True
                
        return False
        
    async def check_for_new_api_key(self, username: str, password: str) -> Optional[str]:
        """Check if API key has changed and return new key if found"""
        current_time = datetime.now()
        
        # Only check if enough time has passed
        if (self.last_key_check and 
            current_time - self.last_key_check < timedelta(seconds=self.key_check_interval)):
            return None
            
        self.last_key_check = current_time
        
        # Get current key from dashboard
        new_key = await self.get_api_key_from_dashboard(username, password)
        
        if new_key and new_key != self.current_api_key:
            logger.info(f"Detected new API key: {new_key[:8]}...")
            self.current_api_key = new_key
            return new_key
            
        return None
        
    def _save_key_to_cache(self, api_key: str):
        """Save API key to local cache"""
        try:
            cache_data = {
                "api_key": api_key,
                "timestamp": datetime.now().isoformat()
            }
            with open(self._key_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.info("API key saved to cache")
        except Exception as e:
            logger.error(f"Failed to save API key to cache: {e}")
            
    def load_key_from_cache(self) -> Optional[str]:
        """Load API key from local cache"""
        try:
            if not self._key_cache_file.exists():
                return None
                
            with open(self._key_cache_file, 'r') as f:
                cache_data = json.load(f)
                
            api_key = cache_data.get("api_key")
            timestamp = cache_data.get("timestamp")
            
            if api_key and timestamp:
                # Check if cached key is not too old (24 hours)
                cache_time = datetime.fromisoformat(timestamp)
                if datetime.now() - cache_time < timedelta(hours=24):
                    logger.info("Loaded API key from cache")
                    self.current_api_key = api_key
                    return api_key
                else:
                    logger.info("Cached API key is too old")
                    
        except Exception as e:
            logger.error(f"Failed to load API key from cache: {e}")
            
        return None
        
    async def test_api_key(self, api_key: str) -> bool:
        """Test if API key is valid by making a test API call"""
        try:
            test_url = urljoin(self.base_url, "/api/v1/ping")
            headers = {"Authorization": f"Bearer {api_key}"}
            
            async with self.session.get(test_url, headers=headers) as response:
                if response.status == 200:
                    logger.info(f"API key test successful")
                    return True
                else:
                    logger.warning(f"API key test failed with status {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error testing API key: {e}")
            return False
            
    async def monitor_api_key_changes(self, username: str, password: str, callback=None):
        """Continuously monitor for API key changes"""
        logger.info("Starting API key monitoring...")
        
        while True:
            try:
                new_key = await self.check_for_new_api_key(username, password)
                if new_key and callback:
                    await callback(new_key)
                    
                await asyncio.sleep(self.key_check_interval)
                
            except Exception as e:
                logger.error(f"Error in API key monitoring: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying


class FortressOpenAlgoIntegration:
    """Integration between Fortress and OpenAlgo with automatic API key updates"""
    
    def __init__(self, brain_instance=None):
        self.brain = brain_instance
        self.api_manager = None
        self.username = None
        self.password = None
        
    async def initialize(self, username: str, password: str):
        """Initialize integration with OpenAlgo credentials"""
        self.username = username
        self.password = password
        
        async with OpenAlgoAPIManager() as manager:
            self.api_manager = manager
            
            # Try to load cached key first
            cached_key = manager.load_key_from_cache()
            if cached_key:
                if await manager.test_api_key(cached_key):
                    logger.info("Using cached API key")
                    await self._update_fortress_api_key(cached_key)
                    return cached_key
                    
            # If no valid cached key, get from dashboard
            logger.info("Getting API key from OpenAlgo dashboard...")
            api_key = await manager.get_api_key_from_dashboard(username, password)
            
            if api_key:
                await self._update_fortress_api_key(api_key)
                
                # Start monitoring for changes
                asyncio.create_task(self._monitor_api_key_changes())
                
                return api_key
            else:
                logger.error("Failed to get API key from OpenAlgo dashboard")
                return None
                
    async def _update_fortress_api_key(self, api_key: str):
        """Update Fortress system with new API key"""
        try:
            if self.brain and hasattr(self.brain, 'openalgo_gateway'):
                # Update the gateway with new API key
                self.brain.openalgo_gateway.api_key = api_key
                logger.info(f"Updated Fortress Brain with new OpenAlgo API key")
                
            # Update secure storage
            from .api_key_manager import SecureAPIKeyManager
            secure_manager = SecureAPIKeyManager()
            secure_manager.store_api_key("openalgo", api_key)
            logger.info("Updated secure API key storage")
            
        except Exception as e:
            logger.error(f"Error updating Fortress API key: {e}")
            
    async def _monitor_api_key_changes(self):
        """Monitor for API key changes and update Fortress automatically"""
        while True:
            try:
                new_key = await self.api_manager.check_for_new_api_key(
                    self.username, self.password
                )
                
                if new_key:
                    logger.info(f"Detected API key change, updating Fortress...")
                    await self._update_fortress_api_key(new_key)
                    
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error monitoring API key changes: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying


# Standalone functions for easy integration
async def get_openalgo_api_key(username: str, password: str, base_url: str = "http://localhost:5000") -> Optional[str]:
    """Get OpenAlgo API key from dashboard"""
    async with OpenAlgoAPIManager(base_url) as manager:
        return await manager.get_api_key_from_dashboard(username, password)

async def setup_automatic_key_updates(brain_instance, username: str, password: str):
    """Setup automatic API key updates for Fortress"""
    integration = FortressOpenAlgoIntegration(brain_instance)
    return await integration.initialize(username, password)


if __name__ == "__main__":
    # Test the API manager
    async def test():
        async with OpenAlgoAPIManager() as manager:
            # Test with demo credentials (replace with actual)
            api_key = await manager.get_api_key_from_dashboard("demo", "demo")
            if api_key:
                print(f"Found API key: {api_key[:8]}...")
                # Test the key
                if await manager.test_api_key(api_key):
                    print("API key is valid!")
                else:
                    print("API key test failed")
            else:
                print("Could not get API key")
                
    asyncio.run(test())