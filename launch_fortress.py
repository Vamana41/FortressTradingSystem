#!/usr/bin/env python3
"""
Fortress Trading System Launcher
Properly launches the Fortress Trading System with correct Python path setup
"""

import sys
import os
import argparse
import asyncio
import signal
from pathlib import Path

# Add the fortress/src directory to Python path
fortress_src_path = Path(__file__).parent / "fortress" / "src"
sys.path.insert(0, str(fortress_src_path))

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n🛑 Received shutdown signal. Stopping Fortress Trading System...")
    sys.exit(0)

async def main():
    """Main launcher function"""
    parser = argparse.ArgumentParser(description="Fortress Trading System Launcher")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Logging level")
    parser.add_argument("--no-dashboard", action="store_true",
                       help="Disable dashboard")
    parser.add_argument("--test-mode", action="store_true",
                       help="Run in test mode (no actual trading)")

    args = parser.parse_args()

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("🚀 Starting Fortress Trading System...")
    print("=" * 60)

    # Import and start the main system
    try:
        from fortress.main import FortressTradingSystem

        # Create system instance
        system = FortressTradingSystem(config_path=args.config)

        # Configure logging
        import logging
        logging.basicConfig(
            level=getattr(logging, args.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        print(f"📊 Log level: {args.log_level}")
        print(f"🎯 Test mode: {'Enabled' if args.test_mode else 'Disabled'}")
        print(f"📱 Dashboard: {'Disabled' if args.no_dashboard else 'Enabled'}")

        if args.test_mode:
            os.environ["TRADING_MODE"] = "paper"
            print("⚠️  Running in test mode - no actual trades will be executed")

        # Start the system
        print("\n🔄 Initializing system components...")
        await system.start()

    except KeyboardInterrupt:
        print("\n👋 User interrupted. Shutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Error starting Fortress Trading System: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
