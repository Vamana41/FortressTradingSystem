#!/usr/bin/env python3
"""Test version detection for OpenAlgo upgrade system"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openalgo_upgrade_system import OpenAlgoUpgradeManager

def test_version_detection():
    """Test the version detection functionality"""
    print("Testing OpenAlgo version detection...")
    
    manager = OpenAlgoUpgradeManager()
    
    # Test current version detection
    current_version = manager.get_current_version()
    print(f"Detected current version: {current_version}")
    
    # Test latest release check
    print("\nChecking for latest release...")
    latest_release = manager.get_latest_release()
    
    if latest_release:
        latest_version = latest_release.get('name', latest_release['tag_name'])
        print(f"Latest release: {latest_version}")
        print(f"Published: {latest_release.get('published_at', 'Unknown')}")
        print(f"Pre-release: {latest_release.get('prerelease', False)}")
    else:
        print("Failed to fetch latest release")
    
    # Test update check
    print("\nChecking for updates...")
    has_update, message = manager.check_for_updates()
    print(f"Update available: {has_update}")
    print(f"Message: {message}")
    
    return current_version is not None

if __name__ == "__main__":
    success = test_version_detection()
    sys.exit(0 if success else 1)