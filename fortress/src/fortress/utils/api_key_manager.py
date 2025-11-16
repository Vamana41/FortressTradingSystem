#!/usr/bin/env python3
"""
Secure API Key Manager for Fortress Trading System
Handles secure storage and retrieval of OpenAlgo API keys
"""

import os
import json
import hashlib
import getpass
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key

class SecureAPIKeyManager:
    """Secure API Key Manager with encryption and validation"""
    
    def __init__(self, config_dir: str = None):
        """Initialize the API key manager"""
        if config_dir is None:
            config_dir = os.path.join(os.path.expanduser("~"), ".fortress")
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.keys_file = self.config_dir / "api_keys.enc"
        self.master_key_file = self.config_dir / ".master_key"
        self.config_file = self.config_dir / "config.json"
        
        self.cipher = self._get_or_create_cipher()
    
    def _get_or_create_cipher(self) -> Fernet:
        """Get or create encryption cipher"""
        if self.master_key_file.exists():
            with open(self.master_key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(self.master_key_file, 'wb') as f:
                f.write(key)
            # Make it hidden on Unix systems
            if os.name != 'nt':
                os.chmod(self.master_key_file, 0o600)
        
        return Fernet(key)
    
    def store_api_key(self, service: str, api_key: str, additional_data: Dict[str, Any] = None) -> bool:
        """Store API key securely"""
        try:
            # Load existing keys
            keys = self._load_encrypted_data()
            
            # Prepare data to store
            key_data = {
                "api_key": api_key,
                "timestamp": self._get_timestamp(),
                "service": service
            }
            
            if additional_data:
                key_data.update(additional_data)
            
            # Encrypt the data
            encrypted_data = self.cipher.encrypt(json.dumps(key_data).encode())
            
            # Store encrypted data
            keys[service] = encrypted_data.hex()
            
            # Save back to file
            self._save_encrypted_data(keys)
            
            print(f"✅ API key for {service} stored securely")
            return True
            
        except Exception as e:
            print(f"❌ Failed to store API key: {e}")
            return False
    
    def get_api_key(self, service: str) -> Optional[str]:
        """Retrieve API key"""
        try:
            keys = self._load_encrypted_data()
            
            if service not in keys:
                return None
            
            # Decrypt the data
            encrypted_data = bytes.fromhex(keys[service])
            decrypted_data = self.cipher.decrypt(encrypted_data)
            key_data = json.loads(decrypted_data.decode())
            
            return key_data["api_key"]
            
        except Exception as e:
            print(f"❌ Failed to retrieve API key: {e}")
            return None
    
    def list_services(self) -> list:
        """List all stored services"""
        try:
            keys = self._load_encrypted_data()
            return list(keys.keys())
        except Exception:
            return []
    
    def delete_api_key(self, service: str) -> bool:
        """Delete API key"""
        try:
            keys = self._load_encrypted_data()
            
            if service in keys:
                del keys[service]
                self._save_encrypted_data(keys)
                print(f"✅ API key for {service} deleted")
                return True
            else:
                print(f"⚠️  No API key found for {service}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to delete API key: {e}")
            return False
    
    def validate_api_key(self, service: str) -> bool:
        """Validate API key by testing connection"""
        api_key = self.get_api_key(service)
        if not api_key:
            return False
        
        # Basic validation - check format and length
        if len(api_key) < 10:
            return False
        
        # For OpenAlgo, we can test the connection
        if service == "openalgo":
            return self._test_openalgo_connection(api_key)
        
        return True
    
    def _test_openalgo_connection(self, api_key: str) -> bool:
        """Test OpenAlgo API connection"""
        try:
            import requests
            
            # Test ping endpoint
            url = "http://localhost:5000/api/v1/ping"
            data = {"apikey": api_key}
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("status") == "success"
            
            return False
            
        except Exception:
            return False
    
    def _load_encrypted_data(self) -> Dict[str, str]:
        """Load encrypted data from file"""
        if not self.keys_file.exists():
            return {}
        
        try:
            with open(self.keys_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_encrypted_data(self, data: Dict[str, str]) -> None:
        """Save encrypted data to file"""
        with open(self.keys_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Make it readable only by owner
        if os.name != 'nt':
            os.chmod(self.keys_file, 0o600)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration"""
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Failed to save config: {e}")
            return False

def main():
    """Main function for CLI usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Secure API Key Manager")
    parser.add_argument("--store", nargs=2, metavar=("SERVICE", "API_KEY"), 
                       help="Store API key for service")
    parser.add_argument("--get", metavar="SERVICE", help="Get API key for service")
    parser.add_argument("--list", action="store_true", help="List all services")
    parser.add_argument("--delete", metavar="SERVICE", help="Delete API key for service")
    parser.add_argument("--validate", metavar="SERVICE", help="Validate API key for service")
    
    args = parser.parse_args()
    
    manager = SecureAPIKeyManager()
    
    if args.store:
        service, api_key = args.store
        success = manager.store_api_key(service, api_key)
        exit(0 if success else 1)
    
    elif args.get:
        api_key = manager.get_api_key(args.get)
        if api_key:
            print(f"API Key: {api_key[:10]}...")
            exit(0)
        else:
            print("API key not found")
            exit(1)
    
    elif args.list:
        services = manager.list_services()
        if services:
            print("Stored services:")
            for service in services:
                print(f"  - {service}")
        else:
            print("No services found")
    
    elif args.delete:
        success = manager.delete_api_key(args.delete)
        exit(0 if success else 1)
    
    elif args.validate:
        is_valid = manager.validate_api_key(args.validate)
        if is_valid:
            print("✅ API key is valid")
            exit(0)
        else:
            print("❌ API key is invalid or connection failed")
            exit(1)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()