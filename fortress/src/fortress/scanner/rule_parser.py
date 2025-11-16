"""Rule parser for English-like scanner DSL similar to ChartInk."""

import re
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

from .scanner_config import ScannerRule, Operator, ScannerTimeframe


class TokenType(Enum):
    """Token types for the rule parser."""
    FIELD = "FIELD"
    OPERATOR = "OPERATOR"
    VALUE = "VALUE"
    TIMEFRAME = "TIMEFRAME"
    LOOKBACK = "LOOKBACK"
    AND = "AND"
    OR = "OR"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EOF = "EOF"


@dataclass
class Token:
    """Token representation."""
    type: TokenType
    value: str
    position: int


class RuleLexer:
    """Lexical analyzer for scanner rules."""
    
    # English-like operator mappings
    OPERATOR_MAPPINGS = {
        # Comparison operators
        "is greater than": Operator.GREATER_THAN,
        "is above": Operator.GREATER_THAN,
        ">": Operator.GREATER_THAN,
        "is less than": Operator.LESS_THAN,
        "is below": Operator.LESS_THAN,
        "<": Operator.LESS_THAN,
        "is equal to": Operator.EQUAL_TO,
        "equals": Operator.EQUAL_TO,
        "=": Operator.EQUAL_TO,
        "is greater than or equal to": Operator.GREATER_THAN_OR_EQUAL,
        ">=": Operator.GREATER_THAN_OR_EQUAL,
        "is less than or equal to": Operator.LESS_THAN_OR_EQUAL,
        "<=": Operator.LESS_THAN_OR_EQUAL,
        "is not equal to": Operator.NOT_EQUAL,
        "not equals": Operator.NOT_EQUAL,
        "!=": Operator.NOT_EQUAL,
        "is between": Operator.BETWEEN,
        "is not between": Operator.NOT_BETWEEN,
    }
    
    # Field name mappings (ChartInk style)
    FIELD_MAPPINGS = {
        # Price fields
        "close": "close",
        "closing price": "close",
        "open": "open",
        "opening price": "open",
        "high": "high",
        "low": "low",
        "volume": "volume",
        "rsi": "rsi",
        "rsi14": "rsi",
        "macd": "macd",
        "macd signal": "macd_signal",
        "ema": "ema",
        "sma": "sma",
        "bollinger upper": "bb_upper",
        "bollinger lower": "bb_lower",
        "bollinger middle": "bb_middle",
        "atr": "atr",
        "adx": "adx",
        "stochastic": "stochastic",
        "mfi": "mfi",
        "williams %r": "williams_r",
        "cci": "cci",
        "parabolic sar": "psar",
    }
    
    # Timeframe mappings
    TIMEFRAME_MAPPINGS = {
        "1 minute": ScannerTimeframe.ONE_MINUTE,
        "5 minutes": ScannerTimeframe.FIVE_MINUTES,
        "15 minutes": ScannerTimeframe.FIFTEEN_MINUTES,
        "30 minutes": ScannerTimeframe.THIRTY_MINUTES,
        "1 hour": ScannerTimeframe.ONE_HOUR,
        "4 hours": ScannerTimeframe.FOUR_HOURS,
        "daily": ScannerTimeframe.DAILY,
        "weekly": ScannerTimeframe.WEEKLY,
        "1m": ScannerTimeframe.ONE_MINUTE,
        "5m": ScannerTimeframe.FIVE_MINUTES,
        "15m": ScannerTimeframe.FIFTEEN_MINUTES,
        "30m": ScannerTimeframe.THIRTY_MINUTES,
        "1h": ScannerTimeframe.ONE_HOUR,
        "4h": ScannerTimeframe.FOUR_HOURS,
        "1d": ScannerTimeframe.DAILY,
        "1w": ScannerTimeframe.WEEKLY,
    }
    
    def __init__(self, rule_text: str):
        self.rule_text = rule_text.lower().strip()
        self.position = 0
        self.tokens: List[Token] = []
    
    def tokenize(self) -> List[Token]:
        """Convert rule text to tokens."""
        self.tokens = []
        self.position = 0
        
        while self.position < len(self.rule_text):
            self._skip_whitespace()
            
            if self.position >= len(self.rule_text):
                break
            
            # Try to match different token types
            token = self._match_operator() or \
                   self._match_timeframe() or \
                   self._match_field() or \
                   self._match_value() or \
                   self._match_logical_operator() or \
                   self._match_parenthesis()
            
            if token:
                self.tokens.append(token)
            else:
                # Skip unknown character
                self.position += 1
        
        self.tokens.append(Token(TokenType.EOF, "", self.position))
        return self.tokens
    
    def _skip_whitespace(self):
        """Skip whitespace characters."""
        while self.position < len(self.rule_text) and self.rule_text[self.position].isspace():
            self.position += 1
    
    def _match_operator(self) -> Optional[Token]:
        """Match comparison operators."""
        # Try multi-word operators first
        for op_text, op_enum in self.OPERATOR_MAPPINGS.items():
            if self.rule_text.startswith(op_text, self.position):
                self.position += len(op_text)
                return Token(TokenType.OPERATOR, op_text, self.position - len(op_text))
        
        # Try single character operators
        if self.position < len(self.rule_text):
            char = self.rule_text[self.position]
            if char in [">", "<", "=", "!"]:
                # Check for two-character operators
                if self.position + 1 < len(self.rule_text):
                    two_char = char + self.rule_text[self.position + 1]
                    if two_char in [">=", "<=", "!=", "=="]:
                        self.position += 2
                        return Token(TokenType.OPERATOR, two_char, self.position - 2)
                
                # Single character operator
                self.position += 1
                return Token(TokenType.OPERATOR, char, self.position - 1)
        
        return None
    
    def _match_timeframe(self) -> Optional[Token]:
        """Match timeframe specifications."""
        # Look for "in [timeframe]" pattern
        if self.position < len(self.rule_text) - 2:
            if self.rule_text.startswith("in ", self.position):
                # Skip "in "
                start_pos = self.position + 3
                remaining = self.rule_text[start_pos:]
                
                # Try to match timeframe
                for tf_text, tf_enum in self.TIMEFRAME_MAPPINGS.items():
                    if remaining.startswith(tf_text):
                        self.position = start_pos + len(tf_text)
                        return Token(TokenType.TIMEFRAME, tf_text, start_pos)
        
        return None
    
    def _match_field(self) -> Optional[Token]:
        """Match field names."""
        # Try multi-word fields first
        for field_text, field_name in self.FIELD_MAPPINGS.items():
            if self.rule_text.startswith(field_text, self.position):
                self.position += len(field_text)
                return Token(TokenType.FIELD, field_text, self.position - len(field_text))
        
        # Try single word fields (alphanumeric + underscore)
        start_pos = self.position
        field_name = ""
        
        while self.position < len(self.rule_text):
            char = self.rule_text[self.position]
            if char.isalnum() or char == "_":
                field_name += char
                self.position += 1
            else:
                break
        
        if field_name and field_name in self.FIELD_MAPPINGS.values():
            return Token(TokenType.FIELD, field_name, start_pos)
        
        # Backtrack if no match
        self.position = start_pos
        return None
    
    def _match_value(self) -> Optional[Token]:
        """Match numeric values."""
        start_pos = self.position
        
        # Try to match number (integer or decimal)
        if self.position < len(self.rule_text) and (self.rule_text[self.position].isdigit() or self.rule_text[self.position] == "."):
            value_str = ""
            decimal_found = False
            
            while self.position < len(self.rule_text):
                char = self.rule_text[self.position]
                if char.isdigit():
                    value_str += char
                    self.position += 1
                elif char == "." and not decimal_found:
                    value_str += char
                    decimal_found = True
                    self.position += 1
                else:
                    break
            
            if value_str:
                return Token(TokenType.VALUE, value_str, start_pos)
        
        # Backtrack if no match
        self.position = start_pos
        return None
    
    def _match_logical_operator(self) -> Optional[Token]:
        """Match logical operators (AND, OR)."""
        if self.rule_text.startswith("and ", self.position) or self.rule_text.startswith("and\n", self.position):
            self.position += 3
            return Token(TokenType.AND, "and", self.position - 3)
        elif self.rule_text.startswith("or ", self.position) or self.rule_text.startswith("or\n", self.position):
            self.position += 2
            return Token(TokenType.OR, "or", self.position - 2)
        
        return None
    
    def _match_parenthesis(self) -> Optional[Token]:
        """Match parentheses."""
        if self.position < len(self.rule_text):
            char = self.rule_text[self.position]
            if char == "(":
                self.position += 1
                return Token(TokenType.LPAREN, char, self.position - 1)
            elif char == ")":
                self.position += 1
                return Token(TokenType.RPAREN, char, self.position - 1)
        
        return None


class RuleParser:
    """Parser for English-like scanner rules similar to ChartInk."""
    
    def __init__(self):
        self.lexer = None
        self.tokens: List[Token] = []
        self.current_token_index = 0
    
    def parse_rule(self, rule_text: str, default_timeframe: ScannerTimeframe = ScannerTimeframe.DAILY) -> List[ScannerRule]:
        """Parse a rule text into scanner rules."""
        self.lexer = RuleLexer(rule_text)
        self.tokens = self.lexer.tokenize()
        self.current_token_index = 0
        
        rules = []
        
        # Parse rules until EOF
        while self.current_token.type != TokenType.EOF:
            rule = self._parse_single_rule(default_timeframe)
            if rule:
                rules.append(rule)
            
            # Skip logical operators for now (we'll handle complex logic later)
            if self.current_token.type in [TokenType.AND, TokenType.OR]:
                self._advance()
        
        return rules
    
    def _parse_single_rule(self, default_timeframe: ScannerTimeframe) -> Optional[ScannerRule]:
        """Parse a single rule."""
        # Parse field
        field_token = self._consume(TokenType.FIELD)
        if not field_token:
            return None
        
        field_name = self._get_field_name(field_token.value)
        
        # Parse operator
        operator_token = self._consume(TokenType.OPERATOR)
        if not operator_token:
            return None
        
        operator = self._get_operator_enum(operator_token.value)
        
        # Parse value
        value_token = self._consume(TokenType.VALUE)
        if not value_token:
            return None
        
        value = float(value_token.value)
        
        # Parse optional timeframe (default to provided timeframe)
        timeframe = default_timeframe
        if self.current_token.type == TokenType.TIMEFRAME:
            timeframe_token = self._consume(TokenType.TIMEFRAME)
            timeframe = self._get_timeframe_enum(timeframe_token.value)
        
        # Create scanner rule
        return ScannerRule(
            field=field_name,
            operator=operator,
            value=value,
            timeframe=timeframe,
            description=f"{field_token.value} {operator_token.value} {value_token.value}"
        )
    
    def _get_field_name(self, field_text: str) -> str:
        """Get normalized field name from text."""
        # Use the field mappings from lexer
        if field_text in RuleLexer.FIELD_MAPPINGS:
            return RuleLexer.FIELD_MAPPINGS[field_text]
        
        # Return as-is if already a valid field name
        return field_text
    
    def _get_operator_enum(self, operator_text: str) -> Operator:
        """Get operator enum from text."""
        if operator_text in RuleLexer.OPERATOR_MAPPINGS:
            return RuleLexer.OPERATOR_MAPPINGS[operator_text]
        
        # Default to greater than if unknown
        return Operator.GREATER_THAN
    
    def _get_timeframe_enum(self, timeframe_text: str) -> ScannerTimeframe:
        """Get timeframe enum from text."""
        if timeframe_text in RuleLexer.TIMEFRAME_MAPPINGS:
            return RuleLexer.TIMEFRAME_MAPPINGS[timeframe_text]
        
        # Default to daily if unknown
        return ScannerTimeframe.DAILY
    
    def _current_token(self) -> Token:
        """Get current token."""
        if self.current_token_index < len(self.tokens):
            return self.tokens[self.current_token_index]
        return Token(TokenType.EOF, "", len(self.tokens))
    
    @property
    def current_token(self) -> Token:
        """Get current token."""
        return self._current_token()
    
    def _advance(self) -> None:
        """Advance to next token."""
        if self.current_token_index < len(self.tokens) - 1:
            self.current_token_index += 1
    
    def _consume(self, expected_type: TokenType) -> Optional[Token]:
        """Consume token of expected type."""
        if self.current_token.type == expected_type:
            token = self.current_token
            self._advance()
            return token
        return None
    
    def _peek(self, offset: int = 1) -> Token:
        """Peek at token ahead."""
        peek_index = self.current_token_index + offset
        if peek_index < len(self.tokens):
            return self.tokens[peek_index]
        return Token(TokenType.EOF, "", len(self.tokens))


class ChartInkStyleParser:
    """ChartInk-style rule parser with advanced features."""
    
    @staticmethod
    def parse_simple_rule(rule_text: str) -> List[ScannerRule]:
        """Parse simple English-like rules."""
        parser = RuleParser()
        return parser.parse_rule(rule_text)
    
    @staticmethod
    def parse_complex_rule(rule_text: str) -> List[ScannerRule]:
        """Parse complex rules with multiple conditions."""
        # For now, split by logical operators and parse each part
        # This is a simplified implementation - can be enhanced later
        
        rules = []
        
        # Split by "AND" and "OR" for now
        conditions = re.split(r'\s+(and|or)\s+', rule_text, flags=re.IGNORECASE)
        
        for condition in conditions:
            condition = condition.strip()
            if condition and condition.lower() not in ['and', 'or']:
                parser = RuleParser()
                condition_rules = parser.parse_rule(condition)
                rules.extend(condition_rules)
        
        return rules
    
    @staticmethod
    def parse_pkscreener_style_rule(rule_text: str) -> List[ScannerRule]:
        """Parse PKScreener-style rules with Indian market specifics."""
        # Add Indian market specific mappings
        parser = RuleParser()
        
        # Add NSE-specific field mappings
        parser.lexer.FIELD_MAPPINGS.update({
            "nifty 50": "nifty50",
            "bank nifty": "banknifty",
            "finnifty": "finnifty",
            "sensex": "sensex",
            "nse": "nse_price",
            "bse": "bse_price",
            "delivery": "delivery_volume",
            "delivery percentage": "delivery_pct",
        })
        
        return parser.parse_rule(rule_text)


# Example usage and testing
if __name__ == "__main__":
    # Test simple rules
    test_rules = [
        "close is greater than 100",
        "rsi is less than 30 in daily",
        "volume is greater than 1000000",
        "close is above ema_20 in 15 minutes",
        "macd is greater than macd_signal",
    ]
    
    parser = RuleParser()
    
    for rule_text in test_rules:
        print(f"Parsing: {rule_text}")
        try:
            rules = parser.parse_rule(rule_text)
            for rule in rules:
                print(f"  Field: {rule.field}, Operator: {rule.operator}, Value: {rule.value}, Timeframe: {rule.timeframe}")
        except Exception as e:
            print(f"  Error: {e}")
        print()