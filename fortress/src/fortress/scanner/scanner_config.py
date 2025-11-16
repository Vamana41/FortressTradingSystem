"""Scanner configuration and result models."""

from typing import Dict, List, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from pydantic import BaseModel, Field


class ScannerTimeframe(str, Enum):
    """Supported scanner timeframes."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    DAILY = "1d"
    WEEKLY = "1w"


class ScannerCategory(str, Enum):
    """Scanner categories similar to ChartInk and PKScreener."""
    BREAKOUT = "breakout"
    CONSOLIDATION = "consolidation"
    MOMENTUM = "momentum"
    REVERSAL = "reversal"
    VOLUME = "volume"
    PATTERN = "pattern"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    OPTIONS = "options"
    INTRADAY = "intraday"
    SWING = "swing"


class AlertType(str, Enum):
    """Types of alerts for scanner results."""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    BROWSER = "browser"


class Operator(str, Enum):
    """Comparison operators for scanner rules."""
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    EQUAL_TO = "equal_to"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    NOT_EQUAL = "not_equal"
    BETWEEN = "between"
    NOT_BETWEEN = "not_between"


@dataclass
class ScannerRule:
    """Individual scanner rule configuration."""
    field: str
    operator: Operator
    value: Union[float, int, str, List[Union[float, int]]]
    timeframe: ScannerTimeframe = ScannerTimeframe.DAILY
    lookback_period: int = 14
    description: str = ""

    def __post_init__(self):
        if self.operator in [Operator.BETWEEN, Operator.NOT_BETWEEN]:
            if not isinstance(self.value, list) or len(self.value) != 2:
                raise ValueError("BETWEEN/NOT_BETWEEN operators require a list of 2 values")


@dataclass
class ScannerGroup:
    """Group of scanner rules with logical operators."""
    name: str
    rules: List[ScannerRule] = field(default_factory=list)
    operator: str = "AND"  # AND, OR
    description: str = ""

    def add_rule(self, rule: ScannerRule) -> None:
        """Add a rule to the group."""
        self.rules.append(rule)


class ScannerConfig(BaseModel):
    """Scanner configuration model."""

    name: str = Field(..., description="Scanner name")
    description: str = Field("", description="Scanner description")
    category: ScannerCategory = Field(ScannerCategory.TECHNICAL, description="Scanner category")

    # Rule configuration
    rule_groups: List[Dict[str, Any]] = Field(default_factory=list, description="Rule groups")
    custom_rules: List[str] = Field(default_factory=list, description="Custom rule expressions")

    # Scanning parameters
    symbols: List[str] = Field(default_factory=list, description="Symbols to scan")
    index_filter: Optional[str] = Field(None, description="Index filter (NIFTY, BANKNIFTY, etc.)")
    market_cap_filter: Optional[str] = Field(None, description="Market cap filter")
    sector_filter: Optional[List[str]] = Field(None, description="Sector filter")

    # Timeframe configuration
    primary_timeframe: ScannerTimeframe = Field(ScannerTimeframe.DAILY, description="Primary timeframe")
    additional_timeframes: List[ScannerTimeframe] = Field(default_factory=list, description="Additional timeframes")

    # Alert configuration
    alerts_enabled: bool = Field(True, description="Enable alerts")
    alert_types: List[AlertType] = Field(default_factory=list, description="Alert types")
    alert_threshold: int = Field(1, description="Minimum results to trigger alert")

    # Scheduling
    schedule_enabled: bool = Field(False, description="Enable scheduled scanning")
    scan_interval_minutes: int = Field(15, description="Scan interval in minutes")
    run_at_market_open: bool = Field(True, description="Run at market open")
    run_at_market_close: bool = Field(True, description="Run at market close")

    # Performance
    max_symbols: int = Field(500, description="Maximum symbols to scan")
    parallel_processing: bool = Field(True, description="Enable parallel processing")
    batch_size: int = Field(50, description="Batch size for processing")

    # Cache settings
    cache_enabled: bool = Field(True, description="Enable result caching")
    cache_duration_minutes: int = Field(5, description="Cache duration in minutes")

    class Config:
        use_enum_values = True


class ScannerResult(BaseModel):
    """Individual scanner result."""

    symbol: str = Field(..., description="Symbol name")
    scanner_name: str = Field(..., description="Scanner name")
    category: ScannerCategory = Field(..., description="Scanner category")

    # Match details
    match_score: float = Field(0.0, description="Match score (0-1)")
    matching_rules: List[str] = Field(default_factory=list, description="Matching rules")
    rule_values: Dict[str, Any] = Field(default_factory=dict, description="Actual values for rules")

    # Price and volume information
    current_price: float = Field(..., description="Current price")
    price_change: float = Field(0.0, description="Price change percentage")
    volume: int = Field(0, description="Current volume")
    volume_surge: float = Field(0.0, description="Volume surge percentage")

    # Technical indicators
    indicators: Dict[str, float] = Field(default_factory=dict, description="Technical indicator values")

    # Timeframe information
    timeframe: ScannerTimeframe = Field(..., description="Timeframe")
    timestamp: datetime = Field(default_factory=datetime.now, description="Scan timestamp")

    # Alert information
    alert_sent: bool = Field(False, description="Whether alert was sent")
    alert_types: List[AlertType] = Field(default_factory=list, description="Alert types sent")


class ScannerResults(BaseModel):
    """Collection of scanner results."""

    scanner_name: str = Field(..., description="Scanner name")
    scan_id: str = Field(..., description="Unique scan ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="Scan timestamp")

    total_symbols_scanned: int = Field(0, description="Total symbols scanned")
    matching_symbols: int = Field(0, description="Number of matching symbols")
    scan_duration_seconds: float = Field(0.0, description="Scan duration in seconds")

    results: List[ScannerResult] = Field(default_factory=list, description="Scan results")

    # Summary statistics
    top_performers: List[ScannerResult] = Field(default_factory=list, description="Top performing symbols")
    category_breakdown: Dict[str, int] = Field(default_factory=dict, description="Results by category")

    # Performance metrics
    cache_hit: bool = Field(False, description="Whether result was from cache")
    error_count: int = Field(0, description="Number of errors during scan")


# Pre-built scanner configurations similar to ChartInk and PKScreener
PREBUILT_SCANNERS = {
    "breakout_stocks": ScannerConfig(
        name="Breakout Stocks",
        description="Stocks breaking above resistance with volume confirmation",
        category=ScannerCategory.BREAKOUT,
        rule_groups=[
            {
                "name": "price_breakout",
                "rules": [
                    {"field": "close", "operator": "greater_than", "value": "resistance_level", "timeframe": "DAILY"},
                    {"field": "volume", "operator": "greater_than", "value": "avg_volume_20", "timeframe": "DAILY"},
                ],
                "operator": "AND"
            }
        ],
        primary_timeframe=ScannerTimeframe.DAILY,
        additional_timeframes=[ScannerTimeframe.FIFTEEN_MINUTES],
        alerts_enabled=True,
        alert_types=[AlertType.BROWSER, AlertType.EMAIL],
        scan_interval_minutes=15,
    ),

    "oversold_rsi": ScannerConfig(
        name="Oversold RSI",
        description="Stocks with RSI below 30 indicating potential reversal",
        category=ScannerCategory.REVERSAL,
        rule_groups=[
            {
                "name": "rsi_oversold",
                "rules": [
                    {"field": "rsi", "operator": "less_than", "value": 30, "timeframe": "DAILY", "lookback_period": 14},
                    {"field": "close", "operator": "greater_than", "value": "sma_20", "timeframe": "DAILY"},
                ],
                "operator": "AND"
            }
        ],
        primary_timeframe=ScannerTimeframe.DAILY,
        alerts_enabled=True,
        alert_types=[AlertType.BROWSER, AlertType.TELEGRAM],
        scan_interval_minutes=30,
    ),

    "volume_spike": ScannerConfig(
        name="Volume Spike",
        description="Stocks with unusual volume activity",
        category=ScannerCategory.VOLUME,
        rule_groups=[
            {
                "name": "volume_surge",
                "rules": [
                    {"field": "volume", "operator": "greater_than", "value": "avg_volume_20 * 2", "timeframe": "DAILY"},
                    {"field": "volume", "operator": "greater_than", "value": "avg_volume_5", "timeframe": "DAILY"},
                ],
                "operator": "AND"
            }
        ],
        primary_timeframe=ScannerTimeframe.DAILY,
        additional_timeframes=[ScannerTimeframe.FIFTEEN_MINUTES],
        alerts_enabled=True,
        alert_types=[AlertType.BROWSER],
        scan_interval_minutes=5,
    ),

    "golden_crossover": ScannerConfig(
        name="Golden Crossover",
        description="50 EMA crossing above 200 EMA with volume confirmation",
        category=ScannerCategory.TECHNICAL,
        rule_groups=[
            {
                "name": "golden_cross",
                "rules": [
                    {"field": "ema_50", "operator": "greater_than", "value": "ema_200", "timeframe": "DAILY"},
                    {"field": "ema_50_prev", "operator": "less_than", "value": "ema_200_prev", "timeframe": "DAILY"},
                    {"field": "volume", "operator": "greater_than", "value": "avg_volume_20", "timeframe": "DAILY"},
                ],
                "operator": "AND"
            }
        ],
        primary_timeframe=ScannerTimeframe.DAILY,
        alerts_enabled=True,
        alert_types=[AlertType.BROWSER, AlertType.EMAIL, AlertType.TELEGRAM],
        scan_interval_minutes=30,
    ),

    "consolidation_breakout": ScannerConfig(
        name="Consolidation Breakout",
        description="Stocks breaking out of consolidation range",
        category=ScannerCategory.CONSOLIDATION,
        rule_groups=[
            {
                "name": "consolidation",
                "rules": [
                    {"field": "bb_width", "operator": "less_than", "value": 0.05, "timeframe": "DAILY"},
                    {"field": "close", "operator": "greater_than", "value": "bb_upper", "timeframe": "DAILY"},
                    {"field": "volume", "operator": "greater_than", "value": "avg_volume_20", "timeframe": "DAILY"},
                ],
                "operator": "AND"
            }
        ],
        primary_timeframe=ScannerTimeframe.DAILY,
        additional_timeframes=[ScannerTimeframe.FIFTEEN_MINUTES],
        alerts_enabled=True,
        alert_types=[AlertType.BROWSER, AlertType.EMAIL],
        scan_interval_minutes=15,
    ),
}
