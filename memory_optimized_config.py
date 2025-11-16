import os
import gc
import logging
from datetime import timedelta

class MemoryOptimizedConfig:
    """Memory-optimized configuration for Flask/OpenAlgo"""

    # Flask Memory Optimization
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    JSON_SORT_KEYS = False  # Disable JSON key sorting for memory efficiency
    JSONIFY_PRETTYPRINT_REGULAR = False  # Disable pretty printing
    SEND_FILE_MAX_AGE_DEFAULT = 300  # 5 minutes cache for static files

    # Session Configuration
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_PERMANENT = False  # Don't store permanent sessions

    # Database Memory Optimization
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable event tracking
    SQLALCHEMY_RECORD_QUERIES = False  # Disable query recording
    SQLALCHEMY_POOL_SIZE = 5  # Reduced connection pool
    SQLALCHEMY_POOL_RECYCLE = 1800  # 30 minutes
    SQLALCHEMY_POOL_PRE_PING = True
    SQLALCHEMY_MAX_OVERFLOW = 2
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 1800,
        'pool_pre_ping': True,
        'max_overflow': 2,
        'statement_cache_size': 50,
        'connect_args': {
            'check_same_thread': False,
            'timeout': 30,
            'isolation_level': None
        }
    }

    # Cache Configuration
    CACHE_TYPE = "simple"  # Use simple in-memory cache
    CACHE_DEFAULT_TIMEOUT = 1800  # 30 minutes
    CACHE_THRESHOLD = 500  # Max items in cache

    # Logging Optimization
    LOG_LEVEL = "WARNING"  # Reduce log verbosity
    LOG_MAX_BYTES = 100 * 1024 * 1024  # 100MB max log size
    LOG_BACKUP_COUNT = 3

    # WebSocket Optimization
    SOCKETIO_MAX_HTTP_BUFFER_SIZE = 1 * 1024 * 1024  # 1MB
    SOCKETIO_PING_TIMEOUT = 30
    SOCKETIO_PING_INTERVAL = 15
    SOCKETIO_MAX_DECODE_PACKETS = 16
    SOCKETIO_COMPRESSION_THRESHOLD = 1024

    @staticmethod
    def init_memory_optimization(app):
        """Initialize memory optimization for Flask app"""
        # Configure garbage collection
        gc.set_threshold(500, 5, 5)
        gc.enable()

        # Set up periodic garbage collection
        def periodic_gc():
            gc.collect()
            logging.getLogger(__name__).debug("Periodic garbage collection completed")

        # Add before request handler
        @app.before_request
        def before_request():
            # Clean up any large temporary objects
            if hasattr(gc, 'collect'):
                gc.collect(0)  # Collect only young generation

        # Add after request handler
        @app.after_request
        def after_request(response):
            # Force garbage collection for large responses
            if response.content_length and response.content_length > 1024 * 1024:  # > 1MB
                gc.collect(0)
            return response

        # Configure logging
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('socketio').setLevel(logging.WARNING)
        logging.getLogger('engineio').setLevel(logging.WARNING)

        return app
