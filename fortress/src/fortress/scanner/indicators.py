"""Technical indicator calculator for scanner rules."""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

from .scanner_config import ScannerTimeframe


class IndicatorCalculator:
    """Calculate technical indicators for scanner rules."""

    def __init__(self):
        self.cache: Dict[str, pd.DataFrame] = {}
        self.cache_timeout = 300  # 5 minutes

    def calculate_indicators(self, data: pd.DataFrame, indicators: List[str]) -> Dict[str, float]:
        """Calculate multiple indicators for the given data."""
        results = {}

        for indicator in indicators:
            try:
                value = self.calculate_indicator(data, indicator)
                if value is not None:
                    results[indicator] = value
            except Exception as e:
                print(f"Error calculating {indicator}: {e}")
                results[indicator] = None

        return results

    def calculate_indicator(self, data: pd.DataFrame, indicator: str, **kwargs) -> Optional[float]:
        """Calculate a specific technical indicator."""
        if data.empty or len(data) < 2:
            return None

        # Ensure required columns exist
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            print(f"Missing columns: {missing_columns}")
            return None

        # Get the latest values
        latest_close = data['close'].iloc[-1]
        latest_volume = data['volume'].iloc[-1]

        # Simple price indicators
        if indicator == "close":
            return latest_close
        elif indicator == "open":
            return data['open'].iloc[-1]
        elif indicator == "high":
            return data['high'].iloc[-1]
        elif indicator == "low":
            return data['low'].iloc[-1]
        elif indicator == "volume":
            return latest_volume

        # Moving averages
        elif indicator.startswith("sma_"):
            period = int(indicator.split("_")[1])
            return self.sma(data['close'], period)
        elif indicator.startswith("ema_"):
            period = int(indicator.split("_")[1])
            return self.ema(data['close'], period)

        # RSI
        elif indicator == "rsi":
            period = kwargs.get('period', 14)
            return self.rsi(data['close'], period)

        # MACD
        elif indicator == "macd":
            fast = kwargs.get('fast', 12)
            slow = kwargs.get('slow', 26)
            signal = kwargs.get('signal', 9)
            return self.macd(data['close'], fast, slow, signal)[0]
        elif indicator == "macd_signal":
            fast = kwargs.get('fast', 12)
            slow = kwargs.get('slow', 26)
            signal = kwargs.get('signal', 9)
            return self.macd(data['close'], fast, slow, signal)[1]
        elif indicator == "macd_histogram":
            fast = kwargs.get('fast', 12)
            slow = kwargs.get('slow', 26)
            signal = kwargs.get('signal', 9)
            macd_line, signal_line = self.macd(data['close'], fast, slow, signal)
            return macd_line - signal_line

        # Bollinger Bands
        elif indicator == "bb_upper":
            period = kwargs.get('period', 20)
            std_dev = kwargs.get('std_dev', 2)
            upper, _, _ = self.bollinger_bands(data['close'], period, std_dev)
            return upper
        elif indicator == "bb_lower":
            period = kwargs.get('period', 20)
            std_dev = kwargs.get('std_dev', 2)
            _, lower, _ = self.bollinger_bands(data['close'], period, std_dev)
            return lower
        elif indicator == "bb_middle":
            period = kwargs.get('period', 20)
            _, _, middle = self.bollinger_bands(data['close'], period, std_dev)
            return middle
        elif indicator == "bb_width":
            period = kwargs.get('period', 20)
            std_dev = kwargs.get('std_dev', 2)
            upper, lower, _ = self.bollinger_bands(data['close'], period, std_dev)
            return (upper - lower) / latest_close if latest_close != 0 else 0

        # ATR
        elif indicator == "atr":
            period = kwargs.get('period', 14)
            return self.atr(data, period)

        # ADX
        elif indicator == "adx":
            period = kwargs.get('period', 14)
            return self.adx(data, period)

        # Stochastic
        elif indicator == "stochastic":
            period = kwargs.get('period', 14)
            smooth_k = kwargs.get('smooth_k', 3)
            smooth_d = kwargs.get('smooth_d', 3)
            k, d = self.stochastic(data, period, smooth_k, smooth_d)
            return d  # Return %D line

        # MFI
        elif indicator == "mfi":
            period = kwargs.get('period', 14)
            return self.mfi(data, period)

        # Williams %R
        elif indicator == "williams_r":
            period = kwargs.get('period', 14)
            return self.williams_r(data, period)

        # CCI
        elif indicator == "cci":
            period = kwargs.get('period', 20)
            return self.cci(data, period)

        # Parabolic SAR
        elif indicator == "psar":
            acceleration = kwargs.get('acceleration', 0.02)
            maximum = kwargs.get('maximum', 0.2)
            return self.parabolic_sar(data, acceleration, maximum)

        # Volume indicators
        elif indicator == "avg_volume_5":
            return data['volume'].tail(5).mean()
        elif indicator == "avg_volume_10":
            return data['volume'].tail(10).mean()
        elif indicator == "avg_volume_20":
            return data['volume'].tail(20).mean()
        elif indicator.startswith("volume_sma_"):
            period = int(indicator.split("_")[2])
            return data['volume'].tail(period).mean()

        # Price change
        elif indicator == "price_change":
            if len(data) >= 2:
                prev_close = data['close'].iloc[-2]
                return ((latest_close - prev_close) / prev_close * 100) if prev_close != 0 else 0
            return 0
        elif indicator == "price_change_pct":
            return self.calculate_indicator(data, "price_change")

        # Volume surge
        elif indicator == "volume_surge":
            if len(data) >= 2:
                current_volume = data['volume'].iloc[-1]
                avg_volume = data['volume'].tail(10).mean()
                return ((current_volume - avg_volume) / avg_volume * 100) if avg_volume != 0 else 0
            return 0

        # Support/Resistance levels (simplified)
        elif indicator == "resistance_level":
            return self.calculate_resistance(data)
        elif indicator == "support_level":
            return self.calculate_support(data)

        return None

    def sma(self, prices: pd.Series, period: int) -> Optional[float]:
        """Simple Moving Average."""
        if len(prices) < period:
            return None
        return prices.tail(period).mean()

    def ema(self, prices: pd.Series, period: int) -> Optional[float]:
        """Exponential Moving Average."""
        if len(prices) < period:
            return None

        # Calculate EMA using pandas
        ema_series = prices.ewm(span=period, adjust=False).mean()
        return ema_series.iloc[-1] if not ema_series.empty else None

    def rsi(self, prices: pd.Series, period: int = 14) -> Optional[float]:
        """Relative Strength Index."""
        if len(prices) < period + 1:
            return None

        # Calculate price changes
        delta = prices.diff()

        # Separate gains and losses
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # Calculate average gain and loss
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1] if not rsi.empty else None

    def macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """MACD (Moving Average Convergence Divergence)."""
        if len(prices) < slow:
            return None, None

        # Calculate EMAs
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()

        # Calculate MACD line
        macd_line = ema_fast - ema_slow

        # Calculate signal line
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()

        return macd_line.iloc[-1], signal_line.iloc[-1]

    def bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple:
        """Bollinger Bands."""
        if len(prices) < period:
            return None, None, None

        # Calculate SMA
        sma = prices.rolling(window=period).mean()

        # Calculate standard deviation
        std = prices.rolling(window=period).std()

        # Calculate bands
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)

        return upper_band.iloc[-1], lower_band.iloc[-1], sma.iloc[-1]

    def atr(self, data: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Average True Range."""
        if len(data) < period:
            return None

        # Calculate true range
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift())
        low_close = abs(data['low'] - data['close'].shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # Calculate ATR
        atr = true_range.rolling(window=period).mean()

        return atr.iloc[-1] if not atr.empty else None

    def adx(self, data: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Average Directional Index."""
        if len(data) < period * 2:
            return None

        # Calculate directional movement
        high_diff = data['high'].diff()
        low_diff = data['low'].diff()

        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

        # Calculate true range
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift())
        low_close = abs(data['low'] - data['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # Calculate directional indicators
        plus_di = 100 * (plus_dm.rolling(window=period).sum() / true_range.rolling(window=period).sum())
        minus_di = 100 * (minus_dm.rolling(window=period).sum() / true_range.rolling(window=period).sum())

        # Calculate DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx.iloc[-1] if not adx.empty else None

    def stochastic(self, data: pd.DataFrame, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> tuple:
        """Stochastic Oscillator."""
        if len(data) < period:
            return None, None

        # Calculate %K
        lowest_low = data['low'].rolling(window=period).min()
        highest_high = data['high'].rolling(window=period).max()

        k_percent = 100 * ((data['close'] - lowest_low) / (highest_high - lowest_low))

        # Calculate %D (smoothed %K)
        d_percent = k_percent.rolling(window=smooth_d).mean()

        return k_percent.iloc[-1], d_percent.iloc[-1]

    def mfi(self, data: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Money Flow Index."""
        if len(data) < period:
            return None

        # Calculate typical price
        typical_price = (data['high'] + data['low'] + data['close']) / 3

        # Calculate raw money flow
        raw_money_flow = typical_price * data['volume']

        # Calculate money flow ratio
        money_flow_ratio = raw_money_flow.where(typical_price > typical_price.shift(), 0).rolling(window=period).sum() / \
                          raw_money_flow.where(typical_price < typical_price.shift(), 0).rolling(window=period).sum()

        # Calculate MFI
        mfi = 100 - (100 / (1 + money_flow_ratio))

        return mfi.iloc[-1] if not mfi.empty else None

    def williams_r(self, data: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Williams %R."""
        if len(data) < period:
            return None

        # Calculate highest high and lowest low
        highest_high = data['high'].rolling(window=period).max()
        lowest_low = data['low'].rolling(window=period).min()

        # Calculate Williams %R
        williams_r = -100 * ((highest_high - data['close']) / (highest_high - lowest_low))

        return williams_r.iloc[-1] if not williams_r.empty else None

    def cci(self, data: pd.DataFrame, period: int = 20) -> Optional[float]:
        """Commodity Channel Index."""
        if len(data) < period:
            return None

        # Calculate typical price
        typical_price = (data['high'] + data['low'] + data['close']) / 3

        # Calculate SMA of typical price
        sma_typical = typical_price.rolling(window=period).mean()

        # Calculate mean deviation
        mean_deviation = (typical_price - sma_typical).abs().rolling(window=period).mean()

        # Calculate CCI
        cci = (typical_price - sma_typical) / (0.015 * mean_deviation)

        return cci.iloc[-1] if not cci.empty else None

    def parabolic_sar(self, data: pd.DataFrame, acceleration: float = 0.02, maximum: float = 0.2) -> Optional[float]:
        """Parabolic Stop and Reverse."""
        if len(data) < 2:
            return None

        # Simplified Parabolic SAR calculation
        # This is a basic implementation - can be enhanced
        high = data['high']
        low = data['low']
        close = data['close']

        # Initialize values
        sar = [close.iloc[0]]
        ep = [high.iloc[0]]
        af = [acceleration]

        for i in range(1, len(data)):
            # Simplified SAR calculation
            if close.iloc[i] > close.iloc[i-1]:
                # Uptrend
                sar.append(min(sar[-1] + af[-1] * (ep[-1] - sar[-1]), low.iloc[i-1]))
                ep.append(max(ep[-1], high.iloc[i]))
                af.append(min(af[-1] + acceleration, maximum))
            else:
                # Downtrend
                sar.append(max(sar[-1] + af[-1] * (ep[-1] - sar[-1]), high.iloc[i-1]))
                ep.append(min(ep[-1], low.iloc[i]))
                af.append(min(af[-1] + acceleration, maximum))

        return sar[-1] if sar else None

    def calculate_resistance(self, data: pd.DataFrame, lookback_period: int = 20) -> Optional[float]:
        """Calculate resistance level (simplified)."""
        if len(data) < lookback_period:
            return None

        # Find recent highs
        recent_data = data.tail(lookback_period)
        highs = recent_data['high']

        # Return the highest high as resistance
        return highs.max()

    def calculate_support(self, data: pd.DataFrame, lookback_period: int = 20) -> Optional[float]:
        """Calculate support level (simplified)."""
        if len(data) < lookback_period:
            return None

        # Find recent lows
        recent_data = data.tail(lookback_period)
        lows = recent_data['low']

        # Return the lowest low as support
        return lows.min()

    def get_cache_key(self, symbol: str, timeframe: str, indicators: List[str]) -> str:
        """Generate cache key for indicator calculations."""
        return f"{symbol}_{timeframe}_{'_'.join(sorted(indicators))}"

    def get_cached_indicators(self, cache_key: str) -> Optional[Dict[str, float]]:
        """Get cached indicator values."""
        if cache_key in self.cache:
            return self.cache[cache_key]
        return None

    def cache_indicators(self, cache_key: str, indicators: Dict[str, float]) -> None:
        """Cache indicator values."""
        self.cache[cache_key] = indicators


# Pre-built indicator sets for common scanners
INDICATOR_SETS = {
    "basic": ["close", "open", "high", "low", "volume", "price_change", "volume_surge"],
    "momentum": ["rsi", "macd", "macd_signal", "stochastic", "williams_r"],
    "trend": ["sma_20", "sma_50", "sma_200", "ema_20", "ema_50", "adx"],
    "volatility": ["atr", "bb_upper", "bb_lower", "bb_width"],
    "volume": ["volume", "avg_volume_5", "avg_volume_10", "avg_volume_20", "volume_surge"],
    "support_resistance": ["resistance_level", "support_level"],
    "comprehensive": [
        "close", "volume", "price_change", "volume_surge",
        "rsi", "macd", "macd_signal", "sma_20", "sma_50", "ema_20", "ema_50",
        "bb_upper", "bb_lower", "atr", "adx", "stochastic", "mfi"
    ],
}


if __name__ == "__main__":
    # Test the indicator calculator
    import numpy as np

    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    # Generate OHLCV data
    base_price = 100
    prices = [base_price]

    for i in range(1, 100):
        change = np.random.normal(0, 2)
        new_price = max(1, prices[-1] + change)
        prices.append(new_price)

    data = pd.DataFrame({
        'open': [p + np.random.uniform(-1, 1) for p in prices],
        'high': [p + np.random.uniform(0, 3) for p in prices],
        'low': [p - np.random.uniform(0, 3) for p in prices],
        'close': prices,
        'volume': [np.random.randint(100000, 1000000) for _ in range(100)],
    }, index=dates)

    # Ensure proper OHLC relationships
    data['high'] = data[['open', 'high', 'low', 'close']].max(axis=1)
    data['low'] = data[['open', 'high', 'low', 'close']].min(axis=1)

    calculator = IndicatorCalculator()

    # Test basic indicators
    print("Testing Indicator Calculator")
    print("=" * 40)

    indicators = ["close", "volume", "price_change", "volume_surge", "rsi", "sma_20", "ema_20"]
    results = calculator.calculate_indicators(data, indicators)

    for indicator, value in results.items():
        print(f"{indicator}: {value:.2f}" if isinstance(value, (int, float)) else f"{indicator}: {value}")

    print("\nTesting MACD")
    macd_line, signal_line = calculator.macd(data['close'])
    print(f"MACD Line: {macd_line:.4f}")
    print(f"Signal Line: {signal_line:.4f}")

    print("\nTesting Bollinger Bands")
    upper, lower, middle = calculator.bollinger_bands(data['close'])
    print(f"Upper Band: {upper:.2f}")
    print(f"Lower Band: {lower:.2f}")
    print(f"Middle Band: {middle:.2f}")

    print("\nTesting Stochastic")
    k, d = calculator.stochastic(data)
    print(f"%K: {k:.2f}")
    print(f"%D: {d:.2f}")
