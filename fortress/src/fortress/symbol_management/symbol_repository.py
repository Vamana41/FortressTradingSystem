"""Symbol Repository for data persistence and retrieval."""

import json
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any

from structlog import get_logger

logger = get_logger(__name__)


class SymbolRepository:
    """Repository for symbol data persistence."""

    def __init__(self, db_path: str = "data/symbols.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Create symbols table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    symbol_type TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    lot_size INTEGER NOT NULL,
                    tick_size REAL NOT NULL,
                    margin_required REAL NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create futures contracts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS futures_contracts (
                    symbol TEXT PRIMARY KEY,
                    underlying TEXT NOT NULL,
                    expiry_date DATE NOT NULL,
                    contract_month TEXT NOT NULL,
                    lot_size INTEGER NOT NULL,
                    tick_size REAL NOT NULL,
                    margin_required REAL NOT NULL,
                    status TEXT DEFAULT 'active',
                    rollover_to TEXT,
                    rollover_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            logger.info("Database initialized", db_path=str(self.db_path))

    def save_symbol(self, symbol_data: Dict[str, Any]) -> None:
        """Save symbol information to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO symbols
                (symbol, name, symbol_type, exchange, lot_size, tick_size,
                 margin_required, is_active, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                symbol_data['symbol'],
                symbol_data['name'],
                symbol_data['symbol_type'],
                symbol_data['exchange'],
                symbol_data['lot_size'],
                symbol_data['tick_size'],
                symbol_data['margin_required'],
                symbol_data.get('is_active', True),
                json.dumps(symbol_data.get('metadata', {}))
            ))
            conn.commit()
            logger.info("Symbol saved", symbol=symbol_data['symbol'])

    def load_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Load symbol information from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT symbol, name, symbol_type, exchange, lot_size, tick_size,
                       margin_required, is_active, metadata
                FROM symbols WHERE symbol = ?
            """, (symbol,))

            row = cursor.fetchone()
            if row:
                return {
                    'symbol': row[0],
                    'name': row[1],
                    'symbol_type': row[2],
                    'exchange': row[3],
                    'lot_size': row[4],
                    'tick_size': row[5],
                    'margin_required': row[6],
                    'is_active': bool(row[7]),
                    'metadata': json.loads(row[8])
                }
            return None

    def save_futures_contract(self, contract_data: Dict[str, Any]) -> None:
        """Save futures contract to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO futures_contracts
                (symbol, underlying, expiry_date, contract_month, lot_size, tick_size,
                 margin_required, status, rollover_to, rollover_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                contract_data['symbol'],
                contract_data['underlying'],
                contract_data['expiry_date'],
                contract_data['contract_month'],
                contract_data['lot_size'],
                contract_data['tick_size'],
                contract_data['margin_required'],
                contract_data.get('status', 'active'),
                contract_data.get('rollover_to'),
                contract_data.get('rollover_date')
            ))
            conn.commit()
            logger.info("Futures contract saved", symbol=contract_data['symbol'])

    def load_expiring_contracts(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Load contracts expiring within specified days."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT symbol, underlying, expiry_date, contract_month, lot_size, tick_size,
                       margin_required, status
                FROM futures_contracts
                WHERE expiry_date <= date('now', '+' || ? || ' days')
                AND status = 'active'
                ORDER BY expiry_date
            """, (days_ahead,))

            contracts = []
            for row in cursor.fetchall():
                contracts.append({
                    'symbol': row[0],
                    'underlying': row[1],
                    'expiry_date': row[2],
                    'contract_month': row[3],
                    'lot_size': row[4],
                    'tick_size': row[5],
                    'margin_required': row[6],
                    'status': row[7]
                })

            logger.info("Loaded expiring contracts", count=len(contracts), days_ahead=days_ahead)
            return contracts
