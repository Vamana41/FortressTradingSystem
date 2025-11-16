#!/usr/bin/env python3
"""
Memory-optimized database configuration for OpenAlgo
Reduces memory footprint and improves connection efficiency
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, scoped_session
import logging

logger = logging.getLogger(__name__)

class MemoryOptimizedDatabase:
    """Memory-optimized database configuration"""
    
    def __init__(self):
        self.engines = {}
        self.sessions = {}
        self.setup_memory_optimization()
    
    def setup_memory_optimization(self):
        """Setup memory optimization for database connections"""
        # Reduce connection pool size
        self.pool_size = 5
        self.max_overflow = 2
        self.pool_recycle = 1800  # 30 minutes
        self.pool_timeout = 30
        self.statement_cache_size = 50
        
        # Memory optimization settings
        self.enable_pragmas = True
        self.journal_mode = 'WAL'  # Write-Ahead Logging for better concurrency
        self.synchronous = 'NORMAL'  # Balance between safety and performance
        self.temp_store = 'MEMORY'  # Use memory for temp tables
        self.cache_size = -2000  # 2MB cache size (negative means KB)
        
    def create_memory_optimized_engine(self, database_url, engine_key='default'):
        """Create a memory-optimized database engine"""
        
        # SQLite specific optimizations
        if 'sqlite' in database_url:
            engine = create_engine(
                database_url,
                poolclass=StaticPool,
                connect_args={
                    'check_same_thread': False,
                    'timeout': self.pool_timeout,
                    'isolation_level': None,
                    'cached_statements': self.statement_cache_size,
                    'pragma': {
                        'journal_mode': self.journal_mode,
                        'synchronous': self.synchronous,
                        'temp_store': self.temp_store,
                        'cache_size': self.cache_size,
                        'page_size': 4096,  # Optimal page size
                        'max_page_count': 10000,  # Limit database size
                    }
                },
                pool_pre_ping=True,
                echo=False,  # Disable SQL logging to reduce memory
                echo_pool=False,  # Disable pool logging
            )
            
            # Apply SQLite pragmas for memory optimization
            if self.enable_pragmas:
                @event.listens_for(engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA journal_mode = WAL")
                    cursor.execute("PRAGMA synchronous = NORMAL")
                    cursor.execute("PRAGMA temp_store = MEMORY")
                    cursor.execute("PRAGMA cache_size = -2000")
                    cursor.execute("PRAGMA page_size = 4096")
                    cursor.execute("PRAGMA max_page_count = 10000")
                    cursor.close()
        
        else:
            # PostgreSQL/MySQL optimizations
            engine = create_engine(
                database_url,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_recycle=self.pool_recycle,
                pool_timeout=self.pool_timeout,
                pool_pre_ping=True,
                echo=False,
                echo_pool=False,
                execution_options={
                    'compiled_cache': None,  # Disable compiled query cache
                    'isolation_level': 'READ_COMMITTED'
                }
            )
        
        self.engines[engine_key] = engine
        logger.info(f"Created memory-optimized engine: {engine_key}")
        return engine
    
    def create_memory_optimized_session(self, engine_key='default'):
        """Create a memory-optimized session"""
        if engine_key not in self.sessions:
            if engine_key not in self.engines:
                raise ValueError(f"Engine {engine_key} not found")
            
            engine = self.engines[engine_key]
            
            # Create session with memory optimization
            session_factory = sessionmaker(
                bind=engine,
                autoflush=False,  # Disable autoflush to reduce memory
                autocommit=False,
                expire_on_commit=True,  # Expire objects after commit
                enable_baked_queries=False  # Disable baked queries
            )
            
            # Use scoped session for thread safety
            session = scoped_session(session_factory)
            self.sessions[engine_key] = session
            
            logger.info(f"Created memory-optimized session: {engine_key}")
        
        return self.sessions[engine_key]
    
    def optimize_table_memory(self, table_name, engine_key='default'):
        """Optimize memory usage for specific tables"""
        if engine_key not in self.engines:
            return
        
        engine = self.engines[engine_key]
        
        try:
            with engine.connect() as conn:
                # SQLite VACUUM to reclaim space
                if 'sqlite' in str(engine.url):
                    conn.execute(f"VACUUM")
                    conn.execute(f"ANALYZE {table_name}")
                    logger.info(f"Optimized SQLite table: {table_name}")
                
                # PostgreSQL/VACUUM optimization
                elif 'postgresql' in str(engine.url):
                    conn.execute(f"VACUUM ANALYZE {table_name}")
                    logger.info(f"Optimized PostgreSQL table: {table_name}")
                
                # MySQL optimization
                elif 'mysql' in str(engine.url):
                    conn.execute(f"OPTIMIZE TABLE {table_name}")
                    logger.info(f"Optimized MySQL table: {table_name}")
        
        except Exception as e:
            logger.error(f"Table optimization error for {table_name}: {e}")
    
    def cleanup_connections(self):
        """Cleanup database connections"""
        for key, session in self.sessions.items():
            try:
                session.remove()
                logger.info(f"Cleaned up session: {key}")
            except Exception as e:
                logger.error(f"Session cleanup error for {key}: {e}")
        
        for key, engine in self.engines.items():
            try:
                engine.dispose()
                logger.info(f"Disposed engine: {key}")
            except Exception as e:
                logger.error(f"Engine disposal error for {key}: {e}")
    
    def get_memory_stats(self):
        """Get database memory statistics"""
        stats = {}
        for key, engine in self.engines.items():
            try:
                with engine.connect() as conn:
                    if 'sqlite' in str(engine.url):
                        result = conn.execute("PRAGMA page_count").scalar()
                        page_size = conn.execute("PRAGMA page_size").scalar()
                        stats[key] = {
                            'page_count': result,
                            'page_size': page_size,
                            'total_size_mb': (result * page_size) / (1024 * 1024)
                        }
            except Exception as e:
                logger.error(f"Memory stats error for {key}: {e}")
        
        return stats

# Global database optimizer instance
db_optimizer = MemoryOptimizedDatabase()

# Export convenient functions
def create_optimized_engine(database_url, engine_key='default'):
    """Create memory-optimized database engine"""
    return db_optimizer.create_memory_optimized_engine(database_url, engine_key)

def create_optimized_session(engine_key='default'):
    """Create memory-optimized database session"""
    return db_optimizer.create_memory_optimized_session(engine_key)

def optimize_database_memory():
    """Optimize all database memory usage"""
    # Get common table names from OpenAlgo
    tables = [
        'users', 'api_keys', 'orders', 'positions', 'holdings',
        'trades', 'latency_logs', 'api_logs', 'traffic_logs'
    ]
    
    for table in tables:
        try:
            db_optimizer.optimize_table_memory(table)
        except Exception as e:
            logger.debug(f"Table optimization skipped for {table}: {e}")

def cleanup_database_connections():
    """Cleanup all database connections"""
    db_optimizer.cleanup_connections()

if __name__ == "__main__":
    # Test memory-optimized database
    import os
    
    # Create test engine
    database_url = os.getenv('DATABASE_URL', 'sqlite:///openalgo.db')
    engine = create_optimized_engine(database_url, 'test')
    
    # Get memory stats
    stats = db_optimizer.get_memory_stats()
    print(f"Database memory stats: {stats}")
    
    # Cleanup
    cleanup_database_connections()