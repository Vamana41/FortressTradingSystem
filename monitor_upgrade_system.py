#!/usr/bin/env python3
"""Monitor OpenAlgo upgrade system status"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime

def monitor_upgrade_system():
    """Monitor the upgrade system status"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('upgrade_monitor.log'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    config_file = Path("upgrade_config.json")
    version_file = Path("current_openalgo_version.txt")
    log_file = Path("openalgo_upgrade.log")
    
    logger.info("Starting upgrade system monitoring...")
    
    while True:
        try:
            # Check configuration
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    last_check = config.get('last_check', 'Never')
                    last_upgrade = config.get('last_upgrade', 'Never')
                    auto_upgrade = config.get('auto_upgrade', False)
                    
                    logger.info(f"Auto-upgrade: {'Enabled' if auto_upgrade else 'Disabled'}")
                    logger.info(f"Last check: {last_check}")
                    logger.info(f"Last upgrade: {last_upgrade}")
            
            # Check current version
            if version_file.exists():
                with open(version_file, 'r') as f:
                    current_version = f.read().strip()
                    logger.info(f"Current OpenAlgo version: {current_version}")
            
            # Check log file size
            if log_file.exists():
                log_size = log_file.stat().st_size / 1024 / 1024  # MB
                logger.info(f"Upgrade log size: {log_size:.2f} MB")
                
                # Rotate log if too large (> 100MB)
                if log_size > 100:
                    log_file.rename(f"upgrade_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
                    logger.info("Log file rotated")
            
            # Wait for next check (1 hour)
            time.sleep(3600)
            
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Error during monitoring: {e}")
            time.sleep(3600)  # Wait 1 hour on error

if __name__ == "__main__":
    monitor_upgrade_system()
