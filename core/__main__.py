"""
Titan-Quant Core Engine Entry Point

This module provides the command-line interface for starting the Titan-Quant
backend server. It can be run directly with:

    python -m core [options]

Or through the startup scripts:
    - Windows: bin/start_server.bat
    - Linux/Mac: bin/start_server.sh
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.server import (
    WebSocketServer,
    ServerConfig,
    MessageType,
    Message,
    MessageRouter,
)
from core.handlers import create_message_handlers


def setup_logging(debug: bool = False) -> None:
    """
    Configure logging for the server.
    
    Args:
        debug: Enable debug level logging.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/server.log", encoding="utf-8"),
        ],
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Titan-Quant Backend Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m core
  python -m core --port 9000
  python -m core --host 0.0.0.0 --port 8765 --debug
        """,
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("TITAN_QUANT_HOST", "127.0.0.1"),
        help="Server host address (default: 127.0.0.1)",
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("TITAN_QUANT_PORT", "8765")),
        help="Server port number (default: 8765)",
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=30.0,
        help="Heartbeat interval in seconds (default: 30)",
    )
    
    parser.add_argument(
        "--heartbeat-timeout",
        type=float,
        default=60.0,
        help="Heartbeat timeout in seconds (default: 60)",
    )
    
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> int:
    """
    Main async entry point.
    
    Args:
        args: Parsed command line arguments.
    
    Returns:
        Exit code (0 for success, non-zero for error).
    """
    logger = logging.getLogger(__name__)
    
    # Create server configuration
    config = ServerConfig(
        host=args.host,
        port=args.port,
        heartbeat_interval=args.heartbeat_interval,
        heartbeat_timeout=args.heartbeat_timeout,
    )
    
    # Create server instance
    server = WebSocketServer(config)
    
    # Register message handlers
    try:
        handlers = create_message_handlers()
        for msg_type, handler in handlers.items():
            server.register_handler(msg_type, handler)
        logger.info(f"Registered {len(handlers)} message handlers")
    except Exception as e:
        logger.warning(f"Failed to register some handlers: {e}")
    
    # Setup shutdown event
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, initiating shutdown...")
        shutdown_event.set()
    
    # Register signal handlers
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    else:
        # Windows doesn't support SIGTERM well in async context
        signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start server
        await server.start()
        
        logger.info("=" * 50)
        logger.info("Titan-Quant Server is running")
        logger.info(f"WebSocket URL: ws://{args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 50)
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        return 1
    finally:
        # Graceful shutdown
        logger.info("Shutting down server...")
        await server.stop()
        logger.info("Server stopped")
    
    return 0


def main() -> int:
    """
    Main entry point.
    
    Returns:
        Exit code (0 for success, non-zero for error).
    """
    args = parse_args()
    
    # Setup logging
    setup_logging(debug=args.debug)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Titan-Quant Server...")
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Debug: {args.debug}")
    
    # Run async main
    try:
        if sys.platform == "win32":
            # Windows requires specific event loop policy
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
