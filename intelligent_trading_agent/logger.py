"""
Structured logging for the intelligent trading agent.
Tracks trades, market analysis, decisions, and errors.
"""

import logging
import os
from datetime import datetime
from config import LOG_DIR, LOG_LEVEL


class AgentLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, LOG_LEVEL))
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        simple_formatter = logging.Formatter('%(levelname)s: %(message)s')
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        self.logger.addHandler(console_handler)
        
        # File handlers for different log types
        self._setup_file_handlers(detailed_formatter)
    
    def _setup_file_handlers(self, formatter):
        """Setup file handlers for different log types."""
        # Main agent log
        agent_file = os.path.join(LOG_DIR, 'agent.log')
        agent_handler = logging.FileHandler(agent_file)
        agent_handler.setFormatter(formatter)
        self.logger.addHandler(agent_handler)
        
        # Trades log
        self.trades_logger = logging.getLogger('trades')
        trades_file = os.path.join(LOG_DIR, 'trades.log')
        trades_handler = logging.FileHandler(trades_file)
        trades_handler.setFormatter(formatter)
        self.trades_logger.addHandler(trades_handler)
        
        # Market analysis log
        self.market_logger = logging.getLogger('market')
        market_file = os.path.join(LOG_DIR, 'market_analysis.log')
        market_handler = logging.FileHandler(market_file)
        market_handler.setFormatter(formatter)
        self.market_logger.addHandler(market_handler)
        
        # Decisions log
        self.decisions_logger = logging.getLogger('decisions')
        decisions_file = os.path.join(LOG_DIR, 'decisions.log')
        decisions_handler = logging.FileHandler(decisions_file)
        decisions_handler.setFormatter(formatter)
        self.decisions_logger.addHandler(decisions_handler)
    
    def log_trade(self, trade_info: dict):
        """Log a trade execution."""
        msg = f"TRADE: {trade_info}"
        self.trades_logger.info(msg)
    
    def log_market_analysis(self, analysis: dict):
        """Log market analysis results."""
        msg = f"ANALYSIS: {analysis}"
        self.market_logger.info(msg)
    
    def log_decision(self, decision: dict):
        """Log a trading decision."""
        msg = f"DECISION: {decision}"
        self.decisions_logger.info(msg)
    
    def log_error(self, error: str):
        """Log an error."""
        self.logger.error(error)
    
    def log_info(self, message: str):
        """Log info."""
        self.logger.info(message)
    
    def log_warning(self, message: str):
        """Log warning."""
        self.logger.warning(message)


# Global logger instance
agent_logger = AgentLogger('IntelligentTradingAgent')
