#!/usr/bin/env python3
"""Deploy the OpenAlgo upgrade system"""

import os
import sys
import subprocess
import logging
from pathlib import Path

def deploy_upgrade_system():
    """Deploy the upgrade system with all necessary components"""
    print("🚀 Deploying OpenAlgo Upgrade System...")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Test the upgrade system
        print("\n📋 Step 1: Testing upgrade system functionality...")
        result = subprocess.run([
            sys.executable, "openalgo_upgrade_system.py", "--check"
        ], capture_output=True, text=True)
        
        # Return code 1 means "no update available" which is normal
        if result.returncode in [0, 1]:
            print("✅ Upgrade system check passed")
            print(f"   Output: {result.stdout.strip()}")
        else:
            print(f"❌ Upgrade system check failed: {result.stderr}")
            return False
        
        # Step 2: Create upgrade configuration
        print("\n⚙️ Step 2: Creating upgrade configuration...")
        upgrade_config = {
            "auto_upgrade": True,
            "check_interval_hours": 6,  # Check every 6 hours
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
                    "/api/v1/cancelorder",
                    "/api/v1/holdings",
                    "/api/v1/tradebook",
                    "/api/v1/history",
                    "/api/v1/quotes",
                    "/api/v1/depth",
                    "/api/v1/search",
                    "/api/v1/symbol",
                    "/api/v1/expiry",
                    "/api/v1/latency",
                    "/api/v1/ping"
                ]
            }
        }
        
        with open("upgrade_config.json", "w") as f:
            import json
            json.dump(upgrade_config, f, indent=2)
        
        print("✅ Upgrade configuration created")
        
        # Step 3: Create systemd service (Linux) or Windows service
        print("\n🔧 Step 3: Creating service configuration...")
        
        if os.name == 'nt':  # Windows
            # Create Windows service script
            service_script = '''@echo off
echo Starting OpenAlgo Upgrade Monitor Service...
:loop
python openalgo_upgrade_system.py --monitor
timeout /t 21600 /nobreak >nul
goto loop
'''
            with open("start_upgrade_monitor.bat", "w") as f:
                f.write(service_script)
            print("✅ Windows service script created: start_upgrade_monitor.bat")
            
        else:  # Linux/Mac
            # Create systemd service file
            systemd_service = '''[Unit]
Description=OpenAlgo Upgrade Monitor
After=network.target

[Service]
Type=simple
User=fortress
WorkingDirectory=/opt/fortress
ExecStart=/usr/bin/python3 openalgo_upgrade_system.py --monitor
Restart=always
RestartSec=21600

[Install]
WantedBy=multi-user.target
'''
            with open("openalgo-upgrade.service", "w") as f:
                f.write(systemd_service)
            print("✅ Systemd service file created: openalgo-upgrade.service")
        
        # Step 4: Create upgrade monitoring script
        print("\n📊 Step 4: Creating upgrade monitoring script...")
        
        monitor_script = '''#!/usr/bin/env python3
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
'''
        
        with open("monitor_upgrade_system.py", "w") as f:
            f.write(monitor_script)
        
        print("✅ Upgrade monitoring script created: monitor_upgrade_system.py")
        
        # Step 5: Create backup directory structure
        print("\n💾 Step 5: Creating backup directory structure...")
        backup_dirs = ["backups", "backups/configs", "backups/logs", "backups/versions"]
        
        for backup_dir in backup_dirs:
            Path(backup_dir).mkdir(exist_ok=True)
        
        print("✅ Backup directory structure created")
        
        # Step 6: Test upgrade system one more time
        print("\n🧪 Step 6: Final upgrade system test...")
        result = subprocess.run([
            sys.executable, "openalgo_upgrade_system.py", "--check"
        ], capture_output=True, text=True)
        
        # Return code 1 means "no update available" which is normal
        if result.returncode in [0, 1]:
            print("✅ Final upgrade system test passed")
            print("\n🎉 OpenAlgo Upgrade System deployed successfully!")
            
            print("\n📋 Deployment Summary:")
            print("- ✅ Upgrade system configured and tested")
            print("- ✅ Auto-upgrade enabled (checks every 6 hours)")
            print("- ✅ Backup and rollback mechanisms in place")
            print("- ✅ Compatibility checking enabled")
            print("- ✅ Service scripts created for monitoring")
            print("- ✅ Monitoring and logging configured")
            
            print("\n🔧 Next Steps:")
            if os.name == 'nt':
                print("1. Run 'start_upgrade_monitor.bat' to start monitoring")
            else:
                print("1. Install systemd service: sudo cp openalgo-upgrade.service /etc/systemd/system/")
                print("2. Start service: sudo systemctl start openalgo-upgrade")
            
            print("2. Monitor logs: tail -f upgrade_monitor.log")
            print("3. Check status: python openalgo_upgrade_system.py --check")
            
            return True
        else:
            print(f"❌ Final upgrade system test failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return False

if __name__ == "__main__":
    success = deploy_upgrade_system()
    sys.exit(0 if success else 1)