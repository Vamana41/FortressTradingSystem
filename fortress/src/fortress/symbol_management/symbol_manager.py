"""Symbol Management and Futures Contract Handling for Fortress Trading System."""

import asyncio
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field
from structlog import get_logger

from fortress.core.logging import TradingContext

logger = get_logger(__name__)


class ContractStatus(str, Enum):
    """Futures contract status."""
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    ROLLED_OVER = "rolled_over"


class SymbolType(str, Enum):
    """Symbol type classification."""
    EQUITY = "equity"
    FUTURES = "futures"
    OPTIONS = "options"
    INDEX = "index"
    CURRENCY = "currency"
    COMMODITY = "commodity"


@dataclass
class SymbolInfo:
    """Information about a trading symbol."""
    symbol: str
    name: str
    symbol_type: SymbolType
    exchange: str
    lot_size: int
    tick_size: float
    margin_required: float
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class FuturesContract:
    """Futures contract information."""
    symbol: str
    underlying: str
    expiry_date: date
    contract_month: str
    lot_size: int
    tick_size: float
    margin_required: float
    strike_price: Optional[float] = None
    option_type: Optional[str] = None
    status: ContractStatus = ContractStatus.ACTIVE
    rollover_to: Optional[str] = None
    rollover_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def days_to_expiry(self) -> int:
        """Days until contract expiry."""
        return (self.expiry_date - date.today()).days
    
    @property
    def is_expiring_soon(self) -> bool:
        """Check if contract is expiring soon (within 7 days)."""
        return 0 < self.days_to_expiry <= 7
    
    @property
    def is_expired(self) -> bool:
        """Check if contract has expired."""
        return self.days_to_expiry <= 0


@dataclass
class RolloverConfig:
    """Configuration for contract rollover."""
    symbol: str
    rollover_days_before_expiry: int = 7
    auto_rollover: bool = True
    rollover_strategy: str = "next_month"  # next_month, next_quarter, specific_month
    specific_month: Optional[int] = None
    notification_days: List[int] = field(default_factory=lambda: [30, 14, 7, 3, 1])
    max_slippage_percentage: float = 0.5
    rollover_time: str = "09:30"  # Time to execute rollover (HH:MM)


class SymbolManager:
    """Manages trading symbols and futures contracts."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config/symbols.json")
        self.symbols: Dict[str, SymbolInfo] = {}
        self.futures_contracts: Dict[str, FuturesContract] = {}
        self.rollover_configs: Dict[str, RolloverConfig] = {}
        self.active_contracts: Dict[str, str] = {}  # symbol -> active_contract
        self.symbol_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Load configuration if exists
        if self.config_path.exists():
            self.load_configuration()
    
    def load_configuration(self) -> None:
        """Load symbol configuration from file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Load symbols
            for symbol_data in config.get('symbols', []):
                symbol_info = SymbolInfo(**symbol_data)
                self.symbols[symbol_info.symbol] = symbol_info
            
            # Load futures contracts
            for contract_data in config.get('futures_contracts', []):
                contract = FuturesContract(**contract_data)
                self.futures_contracts[contract.symbol] = contract
            
            # Load rollover configs
            for config_data in config.get('rollover_configs', []):
                rollover_config = RolloverConfig(**config_data)
                self.rollover_configs[rollover_config.symbol] = rollover_config
            
            # Load active contracts
            self.active_contracts = config.get('active_contracts', {})
            
            logger.info("Symbol configuration loaded", 
                       symbols_count=len(self.symbols),
                       contracts_count=len(self.futures_contracts))
            
        except Exception as e:
            logger.error("Failed to load symbol configuration", error=str(e))
            raise
    
    def save_configuration(self) -> None:
        """Save symbol configuration to file."""
        try:
            config = {
                'symbols': [vars(symbol) for symbol in self.symbols.values()],
                'futures_contracts': [vars(contract) for contract in self.futures_contracts.values()],
                'rollover_configs': [vars(config) for config in self.rollover_configs.values()],
                'active_contracts': self.active_contracts,
                'last_updated': datetime.now().isoformat()
            }
            
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2, default=str)
            
            logger.info("Symbol configuration saved")
            
        except Exception as e:
            logger.error("Failed to save symbol configuration", error=str(e))
            raise
    
    def register_symbol(self, symbol_info: SymbolInfo) -> None:
        """Register a new symbol."""
        with TradingContext(symbol=symbol_info.symbol, operation="register_symbol"):
            self.symbols[symbol_info.symbol] = symbol_info
            logger.info("Symbol registered", symbol=symbol_info.symbol)
    
    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """Get symbol information."""
        return self.symbols.get(symbol)
    
    def add_futures_contract(self, contract: FuturesContract) -> None:
        """Add a futures contract."""
        with TradingContext(symbol=contract.symbol, operation="add_contract"):
            self.futures_contracts[contract.symbol] = contract
            
            # Update active contract if this is the current month
            if contract.is_active and not contract.is_expired:
                underlying = contract.underlying
                if underlying not in self.active_contracts or contract.days_to_expiry > 0:
                    self.active_contracts[underlying] = contract.symbol
            
            logger.info("Futures contract added", 
                       symbol=contract.symbol,
                       expiry=contract.expiry_date,
                       days_to_expiry=contract.days_to_expiry)
    
    def get_active_contract(self, underlying: str) -> Optional[FuturesContract]:
        """Get the active futures contract for an underlying."""
        active_symbol = self.active_contracts.get(underlying)
        if active_symbol:
            return self.futures_contracts.get(active_symbol)
        return None
    
    def get_contract_info(self, symbol: str) -> Optional[FuturesContract]:
        """Get futures contract information."""
        return self.futures_contracts.get(symbol)
    
    def get_expiring_contracts(self, days_ahead: int = 7) -> List[FuturesContract]:
        """Get contracts expiring within specified days."""
        expiring = []
        for contract in self.futures_contracts.values():
            if contract.is_expiring_soon and contract.days_to_expiry <= days_ahead:
                expiring.append(contract)
        return expiring
    
    def get_expired_contracts(self) -> List[FuturesContract]:
        """Get expired contracts."""
        expired = []
        for contract in self.futures_contracts.values():
            if contract.is_expired:
                expired.append(contract)
        return expired
    
    def set_rollover_config(self, config: RolloverConfig) -> None:
        """Set rollover configuration for a symbol."""
        self.rollover_configs[config.symbol] = config
        logger.info("Rollover configuration set", symbol=config.symbol)
    
    def get_rollover_config(self, symbol: str) -> Optional[RolloverConfig]:
        """Get rollover configuration for a symbol."""
        return self.rollover_configs.get(symbol)
    
    def update_contract_status(self, symbol: str, status: ContractStatus) -> None:
        """Update contract status."""
        if symbol in self.futures_contracts:
            self.futures_contracts[symbol].status = status
            logger.info("Contract status updated", symbol=symbol, status=status)
    
    def get_all_symbols(self, symbol_type: Optional[SymbolType] = None) -> List[str]:
        """Get all registered symbols."""
        if symbol_type:
            return [s.symbol for s in self.symbols.values() if s.symbol_type == symbol_type and s.is_active]
        return [s.symbol for s in self.symbols.values() if s.is_active]
    
    def get_all_futures_symbols(self) -> List[str]:
        """Get all futures symbols."""
        return list(self.futures_contracts.keys())
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol exists and is active."""
        if symbol in self.symbols:
            return self.symbols[symbol].is_active
        
        # Check if it's a futures contract
        if symbol in self.futures_contracts:
            contract = self.futures_contracts[symbol]
            return contract.status == ContractStatus.ACTIVE and not contract.is_expired
        
        return False
    
    def get_symbol_metadata(self, symbol: str) -> Dict[str, Any]:
        """Get symbol metadata."""
        return self.symbol_metadata.get(symbol, {})
    
    def set_symbol_metadata(self, symbol: str, metadata: Dict[str, Any]) -> None:
        """Set symbol metadata."""
        self.symbol_metadata[symbol] = metadata
        logger.info("Symbol metadata updated", symbol=symbol)
    
    async def cleanup_expired_contracts(self) -> List[str]:
        """Clean up expired contracts and return list of removed symbols."""
        with TradingContext(operation="cleanup_expired_contracts"):
            expired_contracts = self.get_expired_contracts()
            removed_symbols = []
            
            for contract in expired_contracts:
                # Remove from active contracts if it's the current one
                underlying = contract.underlying
                if self.active_contracts.get(underlying) == contract.symbol:
                    del self.active_contracts[underlying]
                
                # Mark as expired
                contract.status = ContractStatus.EXPIRED
                removed_symbols.append(contract.symbol)
                
                logger.info("Expired contract cleaned up", 
                           symbol=contract.symbol,
                           expiry_date=contract.expiry_date)
            
            return removed_symbols
    
    def get_contract_chain(self, underlying: str) -> List[FuturesContract]:
        """Get the contract chain for an underlying symbol."""
        chain = []
        for contract in self.futures_contracts.values():
            if contract.underlying == underlying:
                chain.append(contract)
        
        # Sort by expiry date
        chain.sort(key=lambda x: x.expiry_date)
        return chain
    
    def get_next_contract(self, current_symbol: str) -> Optional[FuturesContract]:
        """Get the next contract in the chain."""
        current = self.futures_contracts.get(current_symbol)
        if not current:
            return None
        
        chain = self.get_contract_chain(current.underlying)
        
        # Find current contract and return next one
        for i, contract in enumerate(chain):
            if contract.symbol == current_symbol and i < len(chain) - 1:
                return chain[i + 1]
        
        return None