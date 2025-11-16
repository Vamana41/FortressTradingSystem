#!/usr/bin/env python3
"""
Automatic OpenAlgo Upgrade System for Fortress Trading System

This system monitors OpenAlgo releases and automatically upgrades the installation
while maintaining compatibility with Fortress Trading System.
"""

import os
import sys
import json
import shutil
import logging
import subprocess
import requests
import hashlib
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import asyncio
import aiohttp
from packaging import version

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('openalgo_upgrade.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OpenAlgoUpgradeManager:
    """Manages automatic upgrades for OpenAlgo and Fortress compatibility"""

    def __init__(self):
        self.openalgo_repo = "marketcalls/OpenAlgo"
        self.github_api_base = "https://api.github.com"
        self.openalgo_dir = Path("openalgo")
        self.backup_dir = Path("backups")
        self.config_file = Path("upgrade_config.json")
        self.current_version_file = Path("current_openalgo_version.txt")
        self.fortress_config_file = Path("fortress/src/fortress/config/compatibility.json")

        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)

        # Load configuration
        self.config = self.load_config()

    def load_config(self) -> Dict:
        """Load upgrade configuration"""
        default_config = {
            "auto_upgrade": True,
            "check_interval_hours": 24,
            "backup_before_upgrade": True,
            "compatibility_check": True,
            "rollback_on_failure": True,
            "notify_on_upgrade": True,
            "last_check": None,
            "last_upgrade": None,
            "compatibility_matrix": {
                "fortress_version": "1.0.0",
                "supported_openalgo_versions": [">=1.0.0"],
                "critical_api_endpoints": [
                    "/api/v1/funds",
                    "/api/v1/orderbook",
                    "/api/v1/positionbook",
                    "/api/v1/placeorder",
                    "/api/v1/modifyorder",
                    "/api/v1/cancelorder"
                ]
            }
        }

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults
                    default_config.update(loaded_config)
            except Exception as e:
                logger.error(f"Error loading config: {e}")

        return default_config

    def save_config(self):
        """Save upgrade configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get_current_version(self) -> Optional[str]:
        """Get current OpenAlgo version"""
        if self.current_version_file.exists():
            try:
                with open(self.current_version_file, 'r') as f:
                    return f.read().strip()
            except Exception as e:
                logger.error(f"Error reading current version: {e}")

        # Try to get version from OpenAlgo installation
        version_file = self.openalgo_dir / "openalgo" / "utils" / "version.py"
        if version_file.exists():
            try:
                with open(version_file, 'r') as f:
                    content = f.read()
                    # Extract version from various patterns
                    import re

                    # Try VERSION = 'x.x.x.x' pattern (with single or double quotes)
                    match = re.search(r'VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                    if match:
                        return match.group(1)

                    # Try VERSION='x.x.x.x' pattern (no spaces)
                    match = re.search(r'VERSION=[\'"]([^\'"]+)[\'"]', content)
                    if match:
                        return match.group(1)

                    # Try __version__ = "x.x.x" pattern
                    match = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                    if match:
                        return match.group(1)

                    # Try version = "x.x.x" pattern
                    match = re.search(r'version\s*=\s*[\'"]([^\'"]+)[\'"]', content, re.IGNORECASE)
                    if match:
                        return match.group(1)

                    # Try to find any semantic version pattern
                    match = re.search(r'[\'"](\d+\.\d+\.\d+(?:\.\d+)?)[\'"]', content)
                    if match:
                        return match.group(1)

            except Exception as e:
                logger.error(f"Error extracting version: {e}")

        return None

    def get_latest_release(self) -> Optional[Dict]:
        """Get latest OpenAlgo release from GitHub"""
        try:
            url = f"{self.github_api_base}/repos/{self.openalgo_repo}/releases/latest"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching latest release: {e}")
            return None

    def get_release_by_tag(self, tag: str) -> Optional[Dict]:
        """Get specific release by tag"""
        try:
            url = f"{self.github_api_base}/repos/{self.openalgo_repo}/releases/tags/{tag}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching release {tag}: {e}")
            return None

    def download_release(self, release: Dict) -> Optional[Path]:
        """Download release assets"""
        try:
            # Find source code zip asset
            zip_url = None
            for asset in release.get('assets', []):
                if asset['name'].endswith('.zip') and 'source' in asset['name']:
                    zip_url = asset['browser_download_url']
                    break

            if not zip_url:
                # Fallback to source code archive
                zip_url = release.get('zipball_url')

            if not zip_url:
                logger.error("No download URL found for release")
                return None

            # Download to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_path = Path(temp_file.name)

            logger.info(f"Downloading release from {zip_url}")
            response = requests.get(zip_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rDownload progress: {progress:.1f}%", end='', flush=True)

            temp_file.close()
            print()  # New line after progress

            return temp_path

        except Exception as e:
            logger.error(f"Error downloading release: {e}")
            return None

    def backup_current_installation(self) -> Optional[Path]:
        """Create backup of current OpenAlgo installation"""
        if not self.config.get("backup_before_upgrade", True):
            return None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"openalgo_backup_{timestamp}"

            if self.openalgo_dir.exists():
                logger.info(f"Creating backup at {backup_path}")
                shutil.copytree(self.openalgo_dir, backup_path)

                # Create backup manifest
                manifest = {
                    "timestamp": timestamp,
                    "version": self.get_current_version(),
                    "backup_path": str(backup_path)
                }

                manifest_file = backup_path / "backup_manifest.json"
                with open(manifest_file, 'w') as f:
                    json.dump(manifest, f, indent=2)

                return backup_path
            else:
                logger.warning("OpenAlgo directory not found for backup")
                return None

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None

    def extract_and_install(self, zip_path: Path, target_version: str) -> bool:
        """Extract and install new OpenAlgo version"""
        try:
            # Create temp extraction directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract zip
                logger.info("Extracting release archive")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_path)

                # Find the actual source directory (GitHub adds a prefix)
                source_dirs = [d for d in temp_path.iterdir() if d.is_dir()]
                if not source_dirs:
                    logger.error("No source directory found in archive")
                    return False

                source_dir = source_dirs[0]  # Take first directory

                # Remove old installation (except config and data)
                logger.info("Preparing installation directory")

                # Keep important files
                keep_files = ['.env', 'db', 'keys', 'log', 'config']
                for keep_file in keep_files:
                    keep_path = self.openalgo_dir / keep_file
                    if keep_path.exists():
                        backup_keep = temp_path / f"keep_{keep_file}"
                        if keep_path.is_dir():
                            shutil.copytree(keep_path, backup_keep)
                        else:
                            shutil.copy2(keep_path, backup_keep)

                # Remove old installation
                if self.openalgo_dir.exists():
                    shutil.rmtree(self.openalgo_dir)

                # Copy new installation
                logger.info("Installing new version")
                shutil.copytree(source_dir, self.openalgo_dir)

                # Restore kept files
                for keep_file in keep_files:
                    keep_path = self.openalgo_dir / keep_file
                    backup_keep = temp_path / f"keep_{keep_file}"
                    if backup_keep.exists():
                        if backup_keep.is_dir():
                            shutil.copytree(backup_keep, keep_path)
                        else:
                            shutil.copy2(backup_keep, keep_path)

                # Update version file
                with open(self.current_version_file, 'w') as f:
                    f.write(target_version)

                return True

        except Exception as e:
            logger.error(f"Error installing new version: {e}")
            return False

    def check_compatibility(self, new_version: str) -> Tuple[bool, str]:
        """Check if new version is compatible with Fortress"""
        if not self.config.get("compatibility_check", True):
            return True, "Compatibility check disabled"

        try:
            current_fortress_version = self.config["compatibility_matrix"]["fortress_version"]
            supported_versions = self.config["compatibility_matrix"]["supported_openalgo_versions"]

            # Simple version comparison
            for supported in supported_versions:
                if supported.startswith(">="):
                    min_version = supported[2:]
                    if version.parse(new_version) >= version.parse(min_version):
                        return True, f"Version {new_version} is compatible"
                elif supported.startswith("=="):
                    exact_version = supported[2:]
                    if version.parse(new_version) == version.parse(exact_version):
                        return True, f"Version {new_version} is compatible"

            return False, f"Version {new_version} is not in supported versions: {supported_versions}"

        except Exception as e:
            logger.error(f"Error checking compatibility: {e}")
            return False, f"Compatibility check failed: {e}"

    def test_critical_endpoints(self) -> Tuple[bool, str]:
        """Test critical API endpoints after upgrade"""
        try:
            base_url = "http://localhost:5000"

            # Test basic connectivity
            response = requests.get(f"{base_url}/api/v1/ping", timeout=10)
            if response.status_code != 200:
                return False, "Basic connectivity test failed"

            # Test critical endpoints
            critical_endpoints = self.config["compatibility_matrix"]["critical_api_endpoints"]

            for endpoint in critical_endpoints:
                try:
                    response = requests.get(f"{base_url}{endpoint}", timeout=10)
                    # Some endpoints might require auth, so we check for proper error codes
                    if response.status_code not in [200, 401, 403]:
                        return False, f"Endpoint {endpoint} returned unexpected status: {response.status_code}"
                except Exception as e:
                    return False, f"Endpoint {endpoint} test failed: {e}"

            return True, "All critical endpoints working"

        except Exception as e:
            return False, f"Endpoint testing failed: {e}"

    def rollback(self, backup_path: Path) -> bool:
        """Rollback to backup version"""
        try:
            logger.info(f"Rolling back to backup: {backup_path}")

            # Remove current installation
            if self.openalgo_dir.exists():
                shutil.rmtree(self.openalgo_dir)

            # Restore from backup
            shutil.copytree(backup_path, self.openalgo_dir)

            # Restore version file
            manifest_file = backup_path / "backup_manifest.json"
            if manifest_file.exists():
                with open(manifest_file, 'r') as f:
                    manifest = json.load(f)
                    with open(self.current_version_file, 'w') as vf:
                        vf.write(manifest.get("version", "unknown"))

            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def upgrade_openalgo(self, target_version: Optional[str] = None) -> bool:
        """Perform OpenAlgo upgrade"""
        try:
            logger.info("Starting OpenAlgo upgrade process")

            # Get current version
            current_version = self.get_current_version()
            logger.info(f"Current version: {current_version}")

            # Get target release
            if target_version:
                release = self.get_release_by_tag(target_version)
            else:
                release = self.get_latest_release()

            if not release:
                logger.error("Could not fetch release information")
                return False

            # Get version from release name or tag_name
            target_version = release.get('name', release['tag_name'])
            logger.info(f"Target version: {target_version}")

            # Clean version strings (remove 'v' prefix if present)
            clean_target_version = target_version.lstrip('v')
            clean_current_version = current_version.lstrip('v') if current_version else None

            # Check if upgrade is needed
            if clean_current_version and version.parse(clean_target_version) <= version.parse(clean_current_version):
                logger.info("Already up to date")
                return True

            # Check compatibility
            compatible, compat_msg = self.check_compatibility(clean_target_version)
            if not compatible:
                logger.error(f"Compatibility check failed: {compat_msg}")
                return False

            # Create backup
            backup_path = self.backup_current_installation()
            if not backup_path and self.config.get("backup_before_upgrade", True):
                logger.error("Backup creation failed, aborting upgrade")
                return False

            # Download release
            zip_path = self.download_release(release)
            if not zip_path:
                logger.error("Download failed")
                return False

            # Install new version
            if not self.extract_and_install(zip_path, clean_target_version):
                logger.error("Installation failed")

                # Rollback if enabled
                if backup_path and self.config.get("rollback_on_failure", True):
                    logger.info("Attempting rollback")
                    self.rollback(backup_path)

                return False

            # Test installation
            logger.info("Testing new installation")
            endpoints_ok, test_msg = self.test_critical_endpoints()
            if not endpoints_ok:
                logger.error(f"Post-upgrade testing failed: {test_msg}")

                # Rollback if enabled
                if backup_path and self.config.get("rollback_on_failure", True):
                    logger.info("Attempting rollback")
                    self.rollback(backup_path)

                return False

            # Update configuration
            self.config["last_upgrade"] = datetime.now().isoformat()
            self.save_config()

            logger.info(f"Successfully upgraded to version {target_version}")

            # Clean up old backups (keep last 5)
            self.cleanup_old_backups()

            return True

        except Exception as e:
            logger.error(f"Upgrade process failed: {e}")
            return False

    def cleanup_old_backups(self, keep_count: int = 5):
        """Clean up old backup files, keep only recent ones"""
        try:
            backup_dirs = [d for d in self.backup_dir.iterdir() if d.is_dir() and d.name.startswith("openalgo_backup_")]
            backup_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            for old_backup in backup_dirs[keep_count:]:
                logger.info(f"Removing old backup: {old_backup}")
                shutil.rmtree(old_backup)

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

    def check_for_updates(self) -> Tuple[bool, str]:
        """Check if updates are available"""
        try:
            current_version = self.get_current_version()
            latest_release = self.get_latest_release()

            if not latest_release:
                return False, "Could not fetch latest release"

            latest_version = latest_release.get('name', latest_release['tag_name'])

            # Clean version strings (remove 'v' prefix if present)
            clean_latest_version = latest_version.lstrip('v')
            clean_current_version = current_version.lstrip('v') if current_version else None

            if clean_current_version and version.parse(clean_latest_version) <= version.parse(clean_current_version):
                return False, "Already up to date"

            # Check compatibility
            compatible, compat_msg = self.check_compatibility(clean_latest_version)
            if not compatible:
                return False, f"Update available but incompatible: {compat_msg}"

            return True, f"Update available: {current_version} -> {latest_version}"

        except Exception as e:
            return False, f"Update check failed: {e}"

    async def monitor_for_updates(self):
        """Async monitor for updates"""
        while True:
            try:
                logger.info("Checking for OpenAlgo updates")
                has_update, message = self.check_for_updates()

                if has_update:
                    logger.info(message)
                    if self.config.get("auto_upgrade", True):
                        logger.info("Auto-upgrade enabled, starting upgrade")
                        self.upgrade_openalgo()
                else:
                    logger.info(message)

                # Wait for next check
                check_interval = self.config.get("check_interval_hours", 24) * 3600
                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in update monitor: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error

def main():
    """Main function for command-line usage"""
    import argparse

    parser = argparse.ArgumentParser(description="OpenAlgo Upgrade Manager")
    parser.add_argument("--check", action="store_true", help="Check for updates")
    parser.add_argument("--upgrade", action="store_true", help="Perform upgrade")
    parser.add_argument("--version", help="Target specific version")
    parser.add_argument("--monitor", action="store_true", help="Start monitoring mode")
    parser.add_argument("--config", help="Configuration file path")

    args = parser.parse_args()

    # Create upgrade manager
    manager = OpenAlgoUpgradeManager()

    if args.check:
        has_update, message = manager.check_for_updates()
        print(message)
        return 0 if has_update else 1

    elif args.upgrade:
        success = manager.upgrade_openalgo(args.version)
        return 0 if success else 1

    elif args.monitor:
        logger.info("Starting update monitor")
        try:
            asyncio.run(manager.monitor_for_updates())
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
        return 0

    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
