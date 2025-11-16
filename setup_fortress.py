#!/usr/bin/env python3
"""
Fortress Trading System Setup Script

This script helps set up and validate the complete Fortress Trading System
with proper OpenAlgo integration, environment configuration, and testing.
"""

import os
import sys
import subprocess
import asyncio
import json
import argparse
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to path
src_path = Path(__file__).parent / "fortress" / "src"
sys.path.insert(0, str(src_path))

from fortress.core.logging import configure_structlog, get_logger

logger = get_logger(__name__)


class FortressSetup:
    """Setup and validation utility for Fortress Trading System."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.checks_passed = 0
        self.checks_failed = 0
        
    def check_python_version(self) -> bool:
        """Check Python version compatibility."""
        try:
            version = sys.version_info
            if version.major == 3 and version.minor >= 8:
                logger.info(f"✓ Python version {version.major}.{version.minor}.{version.micro} is compatible")
                self.checks_passed += 1
                return True
            else:
                logger.error(f"✗ Python {version.major}.{version.minor}.{version.micro} is not supported. Need 3.8+")
                self.checks_failed += 1
                return False
        except Exception as e:
            logger.error(f"✗ Failed to check Python version: {e}")
            self.checks_failed += 1
            return False
    
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are installed."""
        try:
            requirements_file = self.project_root / "requirements.txt"
            if not requirements_file.exists():
                logger.error("✗ requirements.txt not found")
                self.checks_failed += 1
                return False
            
            with open(requirements_file) as f:
                requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            
            missing_packages = []
            for req in requirements:
                package = req.split("==")[0].split(">=")[0].split("<")[0]
                try:
                    __import__(package.replace("-", "_"))
                except ImportError:
                    missing_packages.append(req)
            
            if missing_packages:
                logger.error(f"✗ Missing packages: {missing_packages}")
                logger.info("Run: pip install -r requirements.txt")
                self.checks_failed += 1
                return False
            else:
                logger.info("✓ All dependencies are installed")
                self.checks_passed += 1
                return True
                
        except Exception as e:
            logger.error(f"✗ Failed to check dependencies: {e}")
            self.checks_failed += 1
            return False
    
    def check_redis_connection(self) -> bool:
        """Check Redis connection."""
        try:
            import redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            r = redis.from_url(redis_url)
            r.ping()
            logger.info("✓ Redis connection successful")
            self.checks_passed += 1
            return True
        except Exception as e:
            logger.error(f"✗ Redis connection failed: {e}")
            logger.info("Make sure Redis is running: redis-server")
            self.checks_failed += 1
            return False
    
    def check_openalgo_server(self) -> bool:
        """Check if OpenAlgo server is running."""
        try:
            base_url = os.getenv("OPENALGO_BASE_URL", "http://localhost:8080/api/v1")
            api_key = os.getenv("OPENALGO_API_KEY", "")
            
            if not api_key:
                logger.warning("⚠ OPENALGO_API_KEY not set, using placeholder")
                return True
            
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(f"{base_url}/ping", headers=headers, timeout=5)
            
            if response.status_code == 200:
                logger.info("✓ OpenAlgo server is accessible")
                self.checks_passed += 1
                return True
            else:
                logger.error(f"✗ OpenAlgo server returned {response.status_code}")
                self.checks_failed += 1
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error("✗ OpenAlgo server is not accessible")
            logger.info("Start OpenAlgo server first: python openalgo/app.py")
            self.checks_failed += 1
            return False
        except Exception as e:
            logger.error(f"✗ OpenAlgo check failed: {e}")
            self.checks_failed += 1
            return False
    
    def check_environment_config(self) -> bool:
        """Check environment configuration."""
        try:
            env_file = self.project_root / ".env"
            env_example = self.project_root / ".env.example"
            
            if not env_file.exists():
                if env_example.exists():
                    logger.warning("⚠ .env file not found, copying from .env.example")
                    env_file.write_text(env_example.read_text())
                    logger.info("✓ Created .env file from .env.example")
                else:
                    logger.error("✗ Neither .env nor .env.example found")
                    self.checks_failed += 1
                    return False
            
            # Check critical environment variables
            required_vars = ["OPENALGO_BASE_URL", "REDIS_URL"]
            missing_vars = []
            
            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            if missing_vars:
                logger.error(f"✗ Missing environment variables: {missing_vars}")
                logger.info("Update your .env file with required variables")
                self.checks_failed += 1
                return False
            else:
                logger.info("✓ Environment configuration is valid")
                self.checks_passed += 1
                return True
                
        except Exception as e:
            logger.error(f"✗ Environment check failed: {e}")
            self.checks_failed += 1
            return False
    
    def check_project_structure(self) -> bool:
        """Check if project structure is correct."""
        try:
            required_paths = [
                "fortress/src/fortress",
                "fortress/src/fortress/core",
                "fortress/src/fortress/brain",
                "fortress/src/fortress/worker",
                "fortress/src/fortress/integrations",
                "fortress/src/fortress/dashboard",
            ]
            
            missing_paths = []
            for path in required_paths:
                full_path = self.project_root / path
                if not full_path.exists():
                    missing_paths.append(path)
            
            if missing_paths:
                logger.error(f"✗ Missing project paths: {missing_paths}")
                self.checks_failed += 1
                return False
            else:
                logger.info("✓ Project structure is complete")
                self.checks_passed += 1
                return True
                
        except Exception as e:
            logger.error(f"✗ Project structure check failed: {e}")
            self.checks_failed += 1
            return False
    
    async def test_event_bus(self) -> bool:
        """Test event bus functionality."""
        try:
            from fortress.core.event_bus import event_bus_manager
            from fortress.core.events import Event, EventType
            
            event_bus = event_bus_manager.get_event_bus(
                name="test",
                redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
                key_prefix="test"
            )
            
            await event_bus.connect()
            
            # Test event publishing
            test_event = Event(
                event_type=EventType.SIGNAL_RECEIVED,
                data={"test": "event_bus_working"},
                source="setup_test"
            )
            
            await event_bus.publish_event(test_event)
            await event_bus.disconnect()
            
            logger.info("✓ Event bus is working")
            self.checks_passed += 1
            return True
            
        except Exception as e:
            logger.error(f"✗ Event bus test failed: {e}")
            self.checks_failed += 1
            return False
    
    def generate_setup_report(self) -> Dict[str, Any]:
        """Generate setup validation report."""
        return {
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "total_checks": self.checks_passed + self.checks_failed,
            "success_rate": (self.checks_passed / (self.checks_passed + self.checks_failed)) * 100 if (self.checks_passed + self.checks_failed) > 0 else 0,
            "status": "READY" if self.checks_failed == 0 else "NEEDS_ATTENTION",
            "recommendations": self._get_recommendations()
        }
    
    def _get_recommendations(self) -> list:
        """Get setup recommendations based on failed checks."""
        recommendations = []
        
        if self.checks_failed > 0:
            recommendations.append("Fix the failed checks above before proceeding")
        
        if not os.getenv("OPENALGO_API_KEY"):
            recommendations.append("Set OPENALGO_API_KEY in your .env file")
        
        recommendations.extend([
            "Start Redis server: redis-server",
            "Start OpenAlgo server: python openalgo/app.py",
            "Test with: python setup_fortress.py --test-full-system",
            "Monitor logs for any errors during startup"
        ])
        
        return recommendations
    
    def run_all_checks(self) -> bool:
        """Run all setup checks."""
        logger.info("=" * 60)
        logger.info("Fortress Trading System Setup Validation")
        logger.info("=" * 60)
        
        # Basic checks
        self.check_python_version()
        self.check_project_structure()
        self.check_dependencies()
        self.check_environment_config()
        
        # Service checks
        self.check_redis_connection()
        self.check_openalgo_server()
        
        # Async test
        try:
            asyncio.run(self.test_event_bus())
        except Exception as e:
            logger.error(f"Failed to run async tests: {e}")
        
        # Generate report
        report = self.generate_setup_report()
        
        logger.info("=" * 60)
        logger.info("SETUP VALIDATION REPORT")
        logger.info("=" * 60)
        logger.info(f"Checks Passed: {report['checks_passed']}")
        logger.info(f"Checks Failed: {report['checks_failed']}")
        logger.info(f"Success Rate: {report['success_rate']:.1f}%")
        logger.info(f"Status: {report['status']}")
        
        if report['recommendations']:
            logger.info("\nRecommendations:")
            for rec in report['recommendations']:
                logger.info(f"  • {rec}")
        
        logger.info("=" * 60)
        
        return report['status'] == "READY"


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Fortress Trading System Setup")
    parser.add_argument("--test-full-system", action="store_true", help="Test complete system integration")
    parser.add_argument("--setup-openalgo", action="store_true", help="Setup OpenAlgo server")
    parser.add_argument("--create-env", action="store_true", help="Create .env file from example")
    
    args = parser.parse_args()
    
    setup = FortressSetup()
    
    if args.create_env:
        env_file = setup.project_root / ".env"
        env_example = setup.project_root / ".env.example"
        
        if env_example.exists() and not env_file.exists():
            env_file.write_text(env_example.read_text())
            logger.info("✓ Created .env file from .env.example")
        else:
            logger.info(".env file already exists or .env.example not found")
    
    elif args.setup_openalgo:
        logger.info("Setting up OpenAlgo server...")
        # This would involve starting the OpenAlgo server
        logger.info("Run: python openalgo/app.py")
    
    elif args.test_full_system:
        logger.info("Testing complete system integration...")
        # This would involve running the main system and testing all components
        logger.info("Run: python fortress/src/fortress/main.py")
    
    else:
        # Run setup validation
        setup.run_all_checks()


if __name__ == "__main__":
    main()