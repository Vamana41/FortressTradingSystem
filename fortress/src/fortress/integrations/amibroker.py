"""AmiBroker integration for Fortress Trading System."""

from __future__ import annotations

import asyncio
import csv
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field
from watchfiles import awatch

from ..core.events import Event, EventType, SignalEvent
from ..core.event_bus import publish_event
from ..core.logging import get_logger


logger = get_logger(__name__)


class AmiBrokerSignal(BaseModel):
    """AmiBroker signal structure."""
    
    symbol: str = Field(..., description="Trading symbol")
    signal_type: str = Field(..., description="Signal type (BUY/SELL/SHORT/COVER)")
    quantity: int = Field(..., description="Quantity to trade")
    price: Optional[float] = Field(None, description="Signal price")
    timeframe: str = Field(..., description="Strategy timeframe")
    strategy_name: str = Field(..., description="Strategy name")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Signal timestamp")
    additional_data: Dict[str, Any] = Field(default_factory=dict, description="Additional signal data")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class AmiBrokerFileFormat(BaseModel):
    """AmiBroker file format configuration."""
    
    delimiter: str = Field(default=",", description="CSV delimiter")
    quotechar: str = Field(default='"', description="CSV quote character")
    field_names: List[str] = Field(
        default=["symbol", "signal_type", "quantity", "price", "timeframe", "strategy_name"],
        description="Expected field names in CSV"
    )
    has_header: bool = Field(default=True, description="Whether CSV has header row")
    encoding: str = Field(default="utf-8", description="File encoding")


class AmiBrokerIntegration:
    """AmiBroker integration for signal processing."""
    
    def __init__(
        self,
        watch_directory: Path,
        processed_directory: Optional[Path] = None,
        error_directory: Optional[Path] = None,
        file_format: Optional[AmiBrokerFileFormat] = None,
        file_extension: str = ".csv",
        polling_interval: float = 1.0,
    ):
        """Initialize AmiBroker integration."""
        self.watch_directory = Path(watch_directory)
        self.processed_directory = processed_directory or self.watch_directory / "processed"
        self.error_directory = error_directory or self.watch_directory / "errors"
        self.file_format = file_format or AmiBrokerFileFormat()
        self.file_extension = file_extension
        self.polling_interval = polling_interval
        
        self._running = False
        self._watch_task: Optional[asyncio.Task] = None
        
        # Create directories if they don't exist
        self.watch_directory.mkdir(parents=True, exist_ok=True)
        self.processed_directory.mkdir(parents=True, exist_ok=True)
        self.error_directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            "AmiBroker integration initialized",
            watch_directory=str(self.watch_directory),
            processed_directory=str(self.processed_directory),
            error_directory=str(self.error_directory),
        )
    
    async def start(self) -> None:
        """Start watching for AmiBroker files."""
        self._running = True
        self._watch_task = asyncio.create_task(self._watch_files())
        
        logger.info("AmiBroker integration started", watch_directory=str(self.watch_directory))
        
        # Process any existing files
        await self._process_existing_files()
    
    async def stop(self) -> None:
        """Stop watching for AmiBroker files."""
        self._running = False
        
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        
        logger.info("AmiBroker integration stopped")
    
    async def _watch_files(self) -> None:
        """Watch for new files in the directory."""
        try:
            async for changes in awatch(self.watch_directory):
                if not self._running:
                    break
                
                for change_type, file_path in changes:
                    if change_type in [1, 2]:  # Modified or Created
                        file_path = Path(file_path)
                        
                        # Check if it's a signal file
                        if file_path.suffix == self.file_extension and file_path.is_file():
                            await self._process_file(file_path)
                            
        except asyncio.CancelledError:
            logger.info("File watcher cancelled")
        except Exception as e:
            logger.error("Error watching files", error=str(e))
    
    async def _process_existing_files(self) -> None:
        """Process any existing files in the watch directory."""
        try:
            files = list(self.watch_directory.glob(f"*{self.file_extension}"))
            
            for file_path in files:
                if file_path.is_file():
                    await self._process_file(file_path)
                    
        except Exception as e:
            logger.error("Error processing existing files", error=str(e))
    
    async def _process_file(self, file_path: Path) -> None:
        """Process a single AmiBroker file."""
        logger.info("Processing AmiBroker file", file_path=str(file_path))
        
        try:
            # Read file
            signals = await self._read_signal_file(file_path)
            
            if not signals:
                logger.warning("No signals found in file", file_path=str(file_path))
                return
            
            # Process each signal
            for signal in signals:
                await self._process_signal(signal)
            
            # Move file to processed directory
            await self._move_file(file_path, self.processed_directory)
            
            logger.info(
                "File processed successfully",
                file_path=str(file_path),
                signal_count=len(signals),
            )
            
        except Exception as e:
            logger.error(
                "Error processing file",
                file_path=str(file_path),
                error=str(e),
            )
            
            # Move file to error directory
            await self._move_file(file_path, self.error_directory)
    
    async def _read_signal_file(self, file_path: Path) -> List[AmiBrokerSignal]:
        """Read signals from AmiBroker file."""
        signals = []
        
        try:
            with open(file_path, 'r', encoding=self.file_format.encoding) as file:
                if self.file_format.delimiter == ",":
                    reader = csv.DictReader(file) if self.file_format.has_header else csv.reader(file)
                else:
                    # Custom delimiter
                    reader = csv.DictReader(file, delimiter=self.file_format.delimiter) if self.file_format.has_header else csv.reader(file, delimiter=self.file_format.delimiter)
                
                for row in reader:
                    if self.file_format.has_header:
                        signal_data = dict(row)
                    else:
                        # Map by position
                        signal_data = dict(zip(self.file_format.field_names, row))
                    
                    # Parse signal
                    signal = self._parse_signal(signal_data)
                    if signal:
                        signals.append(signal)
                        
        except Exception as e:
            logger.error("Error reading signal file", file_path=str(file_path), error=str(e))
            raise
        
        return signals
    
    def _parse_signal(self, signal_data: Dict[str, Any]) -> Optional[AmiBrokerSignal]:
        """Parse signal data into AmiBrokerSignal object."""
        try:
            # Extract required fields
            symbol = signal_data.get("symbol", "").strip().upper()
            signal_type = signal_data.get("signal_type", "").strip().upper()
            quantity = int(signal_data.get("quantity", 0))
            timeframe = signal_data.get("timeframe", "").strip()
            strategy_name = signal_data.get("strategy_name", "").strip()
            
            # Validate required fields
            if not all([symbol, signal_type, timeframe, strategy_name]) or quantity <= 0:
                logger.warning("Invalid signal data", signal_data=signal_data)
                return None
            
            # Parse optional fields
            price = None
            if signal_data.get("price"):
                try:
                    price = float(signal_data.get("price"))
                except (ValueError, TypeError):
                    logger.warning("Invalid price value", price=signal_data.get("price"))
            
            # Parse timestamp if available
            timestamp = datetime.utcnow()
            if signal_data.get("timestamp"):
                try:
                    timestamp = datetime.fromisoformat(signal_data.get("timestamp"))
                except (ValueError, TypeError):
                    logger.warning("Invalid timestamp", timestamp=signal_data.get("timestamp"))
            
            # Additional data (all other fields)
            additional_data = {
                k: v for k, v in signal_data.items()
                if k not in ["symbol", "signal_type", "quantity", "price", "timeframe", "strategy_name", "timestamp"]
            }
            
            return AmiBrokerSignal(
                symbol=symbol,
                signal_type=signal_type,
                quantity=quantity,
                price=price,
                timeframe=timeframe,
                strategy_name=strategy_name,
                timestamp=timestamp,
                additional_data=additional_data,
            )
            
        except Exception as e:
            logger.error("Error parsing signal", signal_data=signal_data, error=str(e))
            return None
    
    async def _process_signal(self, signal: AmiBrokerSignal) -> None:
        """Process a single AmiBroker signal."""
        logger.info(
            "Processing AmiBroker signal",
            symbol=signal.symbol,
            signal_type=signal.signal_type,
            quantity=signal.quantity,
            timeframe=signal.timeframe,
            strategy_name=signal.strategy_name,
        )
        
        try:
            # Create signal event
            signal_event = SignalEvent(
                event_id=str(uuid.uuid4()),
                event_type=EventType.AMIBROKER_SIGNAL,
                source="amibroker.integration",
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                quantity=signal.quantity,
                price=signal.price,
                timeframe=signal.timeframe,
                strategy_name=signal.strategy_name,
                data={
                    "timestamp": signal.timestamp.isoformat(),
                    "additional_data": signal.additional_data,
                    "source_file": "amibroker",
                },
            )
            
            # Publish signal event
            success = await publish_event(signal_event)
            
            if success:
                logger.info(
                    "AmiBroker signal published successfully",
                    signal_id=signal_event.event_id,
                    symbol=signal.symbol,
                )
            else:
                logger.error("Failed to publish AmiBroker signal", symbol=signal.symbol)
                
        except Exception as e:
            logger.error(
                "Error processing AmiBroker signal",
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                error=str(e),
            )
    
    async def _move_file(self, file_path: Path, target_directory: Path) -> None:
        """Move file to target directory."""
        try:
            # Generate unique filename to avoid conflicts
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            new_filename = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            target_path = target_directory / new_filename
            
            # Move file
            file_path.rename(target_path)
            
            logger.info(
                "File moved",
                source=str(file_path),
                target=str(target_path),
            )
            
        except Exception as e:
            logger.error(
                "Error moving file",
                source=str(file_path),
                target=str(target_directory),
                error=str(e),
            )
            raise
    
    def create_sample_signal_file(self, output_path: Path, signals: List[AmiBrokerSignal]) -> None:
        """Create a sample AmiBroker signal file for testing."""
        try:
            with open(output_path, 'w', newline='', encoding=self.file_format.encoding) as file:
                writer = csv.writer(file, delimiter=self.file_format.delimiter, quotechar=self.file_format.quotechar)
                
                # Write header
                if self.file_format.has_header:
                    writer.writerow(self.file_format.field_names)
                
                # Write signals
                for signal in signals:
                    row = [
                        signal.symbol,
                        signal.signal_type,
                        signal.quantity,
                        signal.price or "",
                        signal.timeframe,
                        signal.strategy_name,
                    ]
                    writer.writerow(row)
            
            logger.info("Sample signal file created", output_path=str(output_path), signal_count=len(signals))
            
        except Exception as e:
            logger.error("Error creating sample signal file", output_path=str(output_path), error=str(e))
            raise


# Convenience functions
async def create_amibroker_integration(
    watch_directory: str,
    **kwargs: Any,
) -> AmiBrokerIntegration:
    """Create AmiBroker integration instance."""
    return AmiBrokerIntegration(
        watch_directory=Path(watch_directory),
        **kwargs,
    )


# Example usage
if __name__ == "__main__":
    # Create sample signals
    sample_signals = [
        AmiBrokerSignal(
            symbol="NIFTY24NOVFUT",
            signal_type="BUY",
            quantity=50,
            price=25000.0,
            timeframe="15min",
            strategy_name="MA_Crossover",
        ),
        AmiBrokerSignal(
            symbol="BANKNIFTY24NOVFUT",
            signal_type="SELL",
            quantity=25,
            price=52000.0,
            timeframe="5min",
            strategy_name="RSI_Strategy",
        ),
    ]
    
    # Create sample file
    integration = AmiBrokerIntegration(watch_directory="/tmp/amibroker_signals")
    integration.create_sample_signal_file(Path("/tmp/sample_signals.csv"), sample_signals)
    print("Sample signal file created at /tmp/sample_signals.csv")