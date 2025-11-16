#!/usr/bin/env python3
"""
Dashboard main entry point for Fortress Trading System.

This module provides a standalone entry point for running the dashboard
independently or as part of the main trading system.
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

# Add the src directory to Python path for proper imports
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from fortress.dashboard.app import app
from fortress.core.logging import configure_structlog, get_logger

logger = get_logger(__name__)


def create_dashboard_main():
    """Create the main dashboard application."""
    return app


async def run_dashboard(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the dashboard application."""
    try:
        logger.info(f"Starting Fortress Dashboard on {host}:{port}")

        import uvicorn

        config = uvicorn.Config(
            app="fortress.dashboard.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )

        server = uvicorn.Server(config)
        await server.serve()

    except Exception as e:
        logger.error(f"Failed to start dashboard", error=str(e))
        raise


def main():
    """Main entry point for the dashboard."""
    parser = argparse.ArgumentParser(description="Fortress Trading System Dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()

    # Configure logging
    configure_structlog(log_level=args.log_level, json_format=False)

    logger.info("Fortress Trading System Dashboard starting")
    logger.info(f"Configuration: host={args.host}, port={args.port}, reload={args.reload}")

    try:
        # Run the dashboard
        asyncio.run(run_dashboard(args.host, args.port, args.reload))

    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Dashboard error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
