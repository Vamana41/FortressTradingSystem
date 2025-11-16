#!/usr/bin/env python3
"""
Token Sharing Manager for Fortress Trading System
Integrates OpenAlgo token storage with Rtd_Ws_AB_plugin for seamless Fyers data access
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# Configure logging
import logging
logger = logging.getLogger(__name__)

class TokenSharingManager:
    """Manages token sharing between OpenAlgo and Rtd_Ws_AB_plugin integration"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.openalgo_db_path = self.base_dir / "openalgo" / "db" / "openalgo.db"
        self.config_path = self.base_dir / "rtd_ws_config.json"

        # Get pepper from environment or use default
        self.pepper = os.getenv('API_KEY_PEPPER', 'a25d94718479b170c16278e321ea6c989358bf499a658fd20c90033cef8ce772')
        self.fernet = self._get_encryption_cipher()

        logger.info("TokenSharingManager initialized")

    def _get_encryption_cipher(self) -> Fernet:
        """Initialize Fernet encryption cipher using the pepper"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'openalgo_static_salt',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.pepper.encode()))
        return Fernet(key)

    def decrypt_token(self, encrypted_token: str) -> Optional[str]:
        """Decrypt an encrypted token"""
        if not encrypted_token:
            return None
        try:
            return self.fernet.decrypt(encrypted_token.encode()).decode()
        except Exception as e:
            logger.error(f"Error decrypting token: {e}")
            return None

    def get_openalgo_fyers_token(self) -> Optional[str]:
        """
        Extract Fyers access token from OpenAlgo database
        Returns the decrypted access token if found, None otherwise
        """
        try:
            if not self.openalgo_db_path.exists():
                logger.error(f"OpenAlgo database not found at {self.openalgo_db_path}")
                return None

            conn = sqlite3.connect(str(self.openalgo_db_path))
            cursor = conn.cursor()

            # Query for Fyers broker entries
            cursor.execute("""
                SELECT name, auth, feed_token, broker
                FROM auth
                WHERE broker = 'fyers' AND is_revoked = 0
                ORDER BY id DESC
                LIMIT 1
            """)

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.warning("No Fyers auth token found in OpenAlgo database")
                return None

            name, encrypted_auth, encrypted_feed_token, broker = result

            # Decrypt the access token
            access_token = self.decrypt_token(encrypted_auth)
            if not access_token:
                logger.error("Failed to decrypt Fyers access token")
                return None

            logger.info(f"Successfully extracted Fyers token for user: {name}")
            return access_token

        except Exception as e:
            logger.error(f"Error extracting Fyers token from OpenAlgo: {e}")
            return None

    def get_fyers_credentials_from_env(self) -> Dict[str, str]:
        """Extract Fyers credentials from OpenAlgo .env file"""
        env_path = self.base_dir / "openalgo" / "openalgo" / ".env"
        credentials = {}

        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('BROKER_API_KEY') and '=' in line:
                        credentials['app_id'] = line.split('=', 1)[1].strip().strip("'\"")
                    elif line.startswith('BROKER_API_SECRET') and '=' in line:
                        credentials['secret_key'] = line.split('=', 1)[1].strip().strip("'\"")
                    elif line.startswith('REDIRECT_URL') and '=' in line:
                        credentials['redirect_uri'] = line.split('=', 1)[1].strip().strip("'\"")

            logger.info("Successfully extracted Fyers credentials from .env")
            return credentials

        except Exception as e:
            logger.error(f"Error reading Fyers credentials from .env: {e}")
            return {}

    def update_rtd_config_with_token(self, access_token: str) -> bool:
        """Update RTD_WS configuration with the extracted token"""
        try:
            # Load current config
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            # Get credentials from .env
            credentials = self.get_fyers_credentials_from_env()

            # Update Fyers configuration
            config['fyers']['app_id'] = credentials.get('app_id', 'YOUR_FYERS_APP_ID')
            config['fyers']['secret_key'] = credentials.get('secret_key', 'YOUR_FYERS_SECRET_KEY')
            config['fyers']['redirect_uri'] = credentials.get('redirect_uri', 'https://127.0.0.1:5000/')
            config['fyers']['access_token'] = access_token  # Add the extracted token

            # Update AmiBroker path to 64-bit location
            config['paths']['amibroker_plugin_path'] = "C:\\Program Files\\AmiBroker\\Plugins"

            # Save updated config
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)

            logger.info("Successfully updated RTD_WS configuration with Fyers token")
            return True

        except Exception as e:
            logger.error(f"Error updating RTD_WS configuration: {e}")
            return False

    def sync_tokens(self) -> Dict[str, Any]:
        """
        Main method to sync tokens between OpenAlgo and RTD_WS
        Returns status dictionary with operation results
        """
        logger.info("Starting token sync between OpenAlgo and RTD_WS")

        result = {
            'status': 'error',
            'message': '',
            'openalgo_token_found': False,
            'token_synced': False,
            'config_updated': False,
            'credentials_extracted': False
        }

        # Step 1: Extract Fyers token from OpenAlgo
        access_token = self.get_openalgo_fyers_token()
        if not access_token:
            result['message'] = "No Fyers token found in OpenAlgo database"
            return result

        result['openalgo_token_found'] = True
        logger.info(f"Found Fyers token in OpenAlgo: {access_token[:10]}...")

        # Step 2: Update RTD_WS configuration
        if self.update_rtd_config_with_token(access_token):
            result['token_synced'] = True
            result['config_updated'] = True
            result['credentials_extracted'] = True
            result['status'] = 'success'
            result['message'] = 'Token successfully synced from OpenAlgo to RTD_WS'
            logger.info("Token sync completed successfully")
        else:
            result['message'] = "Failed to update RTD_WS configuration"
            logger.error("Token sync failed")

        return result

    def get_current_token_info(self) -> Dict[str, Any]:
        """Get current token information for debugging"""
        info = {
            'openalgo_db_exists': self.openalgo_db_path.exists(),
            'config_exists': self.config_path.exists(),
            'current_token': None,
            'token_source': 'unknown'
        }

        try:
            # Check if token exists in OpenAlgo
            openalgo_token = self.get_openalgo_fyers_token()
            if openalgo_token:
                info['current_token'] = openalgo_token[:10] + "..."
                info['token_source'] = 'openalgo'

            # Check if token exists in RTD config
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                if 'access_token' in config.get('fyers', {}):
                    info['rtd_token'] = config['fyers']['access_token'][:10] + "..."
                    if not info['current_token']:
                        info['current_token'] = config['fyers']['access_token'][:10] + "..."
                        info['token_source'] = 'rtd_config'

        except Exception as e:
            logger.error(f"Error getting token info: {e}")

        return info

def main():
    """Main function for standalone testing"""
    logging.basicConfig(level=logging.INFO)

    manager = TokenSharingManager()

    # Display current token status
    print("Current Token Status:")
    info = manager.get_current_token_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    print("\nAttempting token sync...")
    result = manager.sync_tokens()

    print(f"\nSync Result:")
    for key, value in result.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    main()
