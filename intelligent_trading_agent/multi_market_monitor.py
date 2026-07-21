"""
Multi-Market Monitor - Simultaneously monitor multiple markets/symbols.
Tracks opportunities across different trading instruments in real-time.
"""

from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from market_analyzer import MarketAnalyzer
from strategy_selector import StrategySelector
from features.pattern_recognition import ChartPatternRecognizer
from logger import agent_logger


class MarketOpportunity:
    """Represents a trading opportunity in a market."""
    
    def __init__(self, symbol: str, market_state: str, patterns: Dict, 
                 strategy: str, confidence: float, health: float):
        self.symbol = symbol
        self.market_state = market_state
        self.patterns = patterns
        self.strategy = strategy
        self.confidence = confidence
        self.health = health
        self.score = self._calculate_score()
    
    def _calculate_score(self) -> float:
        """Calculate opportunity score (0-100).
        
        Key change: Strongly prioritize markets in a CLEAR TREND (trending_up or trending_down).
        Ranging and volatile markets get significantly lower scores so the bot
        only trades one market with the strongest trend.
        """
        score = 50.0  # Base score
        
        # Confidence component
        score += self.confidence * 20
        
        # Health component
        score += (self.health / 100) * 20
        
        # Trend dominance bonus (key improvement: trending markets get big boost)
        if 'trending' in self.market_state:
            score += 20  # Major bonus for trending markets
        elif self.market_state == 'ranging':
            score -= 15  # Penalty for ranging (direction unclear)
        elif self.market_state == 'volatile':
            score -= 20  # Heavy penalty for volatile (unreliable signals)
        
        # Pattern confirmation bonus (only if patterns align with trend)
        if self.patterns:
            pattern_count = len(self.patterns)
            # If trending with patterns → big bonus; if ranging → small bonus
            if 'trending' in self.market_state:
                score += min(pattern_count * 8, 16)  # Max 16 points for patterns in trend
            else:
                score += min(pattern_count * 2, 4)   # Minimal bonus in non-trending
        
        # Cap at 100, floor at 0
        return max(0.0, min(score, 100.0))
    
    def __repr__(self) -> str:
        return f"Opportunity({self.symbol}: {self.strategy} @ {self.confidence:.0%}, score={self.score:.1f})"


class MultiMarketMonitor:
    """
    Monitors multiple markets simultaneously.
    Tracks opportunities, patterns, and health across all symbols.
    """
    
    def __init__(self, symbols: List[str], base_stake: float = 1.0):
        self.symbols = symbols
        self.base_stake = base_stake
        
        # Initialize subsystems for each symbol
        self.analyzers: Dict[str, MarketAnalyzer] = {}
        self.selectors: Dict[str, StrategySelector] = {}
        self.pattern_recognizers: Dict[str, ChartPatternRecognizer] = {}
        
        for symbol in symbols:
            self.analyzers[symbol] = MarketAnalyzer(window=100)
            self.selectors[symbol] = StrategySelector(base_stake)
            self.pattern_recognizers[symbol] = ChartPatternRecognizer(window=100)
        
        # Opportunity tracking
        self.current_opportunities: Dict[str, MarketOpportunity] = {}
        self.opportunity_history: List[MarketOpportunity] = []
        
        # Performance by symbol
        self.performance_by_symbol: Dict[str, Dict] = defaultdict(
            lambda: {'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0}
        )
        
        agent_logger.log_info(f"MultiMarketMonitor initialized for {len(symbols)} symbols")
    
    def update_market(self, symbol: str, price: float, volume: float = 1.0):
        """Update market data for a symbol."""
        if symbol not in self.symbols:
            agent_logger.log_warning(f"Unknown symbol: {symbol}")
            return
        
        # Update all subsystems
        self.analyzers[symbol].update(price, volume)
        self.selectors[symbol].update_market_data(price, volume)
        self.pattern_recognizers[symbol].add_price(price)
    
    def scan_all_markets(self, market_data: Dict[str, Dict]) -> List[MarketOpportunity]:
        """
        Scan all markets for trading opportunities.
        Returns opportunities sorted by score (best first).
        """
        opportunities = []
        
        for symbol, data in market_data.items():
            if symbol not in self.symbols:
                continue
            
            opp = self._analyze_symbol(symbol, data)
            if opp:
                opportunities.append(opp)
                self.current_opportunities[symbol] = opp
        
        # Sort by score (descending)
        opportunities.sort(key=lambda x: x.score, reverse=True)
        
        return opportunities
    
    def _analyze_symbol(self, symbol: str, market_data: Dict) -> Optional[MarketOpportunity]:
        """Analyze a single symbol for trading opportunity."""
        try:
            analyzer = self.analyzers[symbol]
            selector = self.selectors[symbol]
            recognizer = self.pattern_recognizers[symbol]
            
            # Get market state
            state = analyzer.detect_market_state()
            regime = analyzer.get_market_regime()
            health = regime['health']
            
            # Get strategy recommendation
            strategy, confidence = selector.select_strategy(market_data)
            
            # Detect patterns
            patterns = recognizer.detect_all_patterns()
            
            # Skip if low health or no strategy
            if health < 50 or strategy == 'hold':
                return None
            
            # Create opportunity
            opp = MarketOpportunity(symbol, state, patterns, strategy, confidence, health)
            
            return opp
        
        except Exception as e:
            agent_logger.log_error(f"Error analyzing {symbol}: {e}")
            return None
    
    def get_best_opportunity(self) -> Optional[MarketOpportunity]:
        """Get the single best trading opportunity across all markets."""
        if not self.current_opportunities:
            return None
        
        return max(self.current_opportunities.values(), key=lambda x: x.score)
    
    def get_opportunities_by_score(self, min_score: float = 70.0) -> List[MarketOpportunity]:
        """Get opportunities above minimum score."""
        return [opp for opp in self.current_opportunities.values() if opp.score >= min_score]
    
    def get_opportunities_by_pattern(self, pattern_name: str) -> List[MarketOpportunity]:
        """Get all opportunities showing a specific pattern."""
        opportunities = []
        for opp in self.current_opportunities.values():
            if pattern_name in opp.patterns:
                opportunities.append(opp)
        
        return sorted(opportunities, key=lambda x: x.score, reverse=True)
    
    def get_market_status(self) -> Dict[str, Dict]:
        """Get status of all monitored markets."""
        status = {}
        
        for symbol in self.symbols:
            analyzer = self.analyzers[symbol]
            regime = analyzer.get_market_regime()
            
            opp = self.current_opportunities.get(symbol)
            
            status[symbol] = {
                'market_state': regime['state'],
                'health': regime['health'],
                'volatility': regime['volatility'],
                'momentum': regime['momentum'],
                'rsi': regime['rsi'],
                'has_opportunity': opp is not None,
                'opportunity_score': opp.score if opp else 0.0,
                'opportunity_strategy': opp.strategy if opp else 'none',
                'patterns': list(opp.patterns.keys()) if opp else []
            }
        
        return status
    
    def get_pattern_heatmap(self) -> Dict[str, List[str]]:
        """Get all patterns detected across markets."""
        heatmap = {}
        
        for symbol in self.symbols:
            patterns = self.pattern_recognizers[symbol].detect_all_patterns()
            if patterns:
                heatmap[symbol] = list(patterns.keys())
        
        return heatmap
    
    def record_trade_result(self, symbol: str, result: bool, profit: float):
        """Record trade outcome for performance tracking."""
        if symbol not in self.performance_by_symbol:
            self.performance_by_symbol[symbol] = {
                'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0
            }
        
        perf = self.performance_by_symbol[symbol]
        perf['trades'] += 1
        
        if result:
            perf['wins'] += 1
            perf['profit'] += profit
        else:
            perf['losses'] += 1
            perf['profit'] -= profit
    
    def get_symbol_performance(self, symbol: str) -> Dict:
        """Get performance stats for a symbol."""
        if symbol not in self.performance_by_symbol:
            return {'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0, 'win_rate': 0.0}
        
        perf = self.performance_by_symbol[symbol]
        total = perf['trades']
        
        return {
            'symbol': symbol,
            'trades': total,
            'wins': perf['wins'],
            'losses': perf['losses'],
            'profit': perf['profit'],
            'win_rate': perf['wins'] / total if total > 0 else 0.0,
            'avg_profit': perf['profit'] / total if total > 0 else 0.0
        }
    
    def get_all_performance(self) -> Dict[str, Dict]:
        """Get performance stats for all symbols."""
        return {symbol: self.get_symbol_performance(symbol) for symbol in self.symbols}
    
    def get_best_performing_symbol(self) -> Optional[str]:
        """Get symbol with best performance."""
        if not self.performance_by_symbol:
            return None
        
        # Filter symbols with actual performance data
        valid_symbols = {
            symbol: perf for symbol, perf in self.performance_by_symbol.items() 
            if perf.get('trades', 0) > 0
        }
        
        if not valid_symbols:
            return None
        
        best = max(
            valid_symbols.items(),
            key=lambda x: (x[1].get('win_rate', 0) * 100) + x[1].get('profit', 0)
        )
        
        return best[0]
    
    def get_hottest_market(self) -> Optional[str]:
        """Get market with highest current volatility."""
        if not self.symbols:
            return None
        
        volatilities = {}
        for symbol in self.symbols:
            regime = self.analyzers[symbol].get_market_regime()
            volatilities[symbol] = regime['volatility']
        
        return max(volatilities, key=volatilities.get)
    
    def get_calmest_market(self) -> Optional[str]:
        """Get market with lowest current volatility."""
        if not self.symbols:
            return None
        
        volatilities = {}
        for symbol in self.symbols:
            regime = self.analyzers[symbol].get_market_regime()
            volatilities[symbol] = regime['volatility']
        
        return min(volatilities, key=volatilities.get)
    
    def get_trending_markets(self) -> List[str]:
        """Get markets in trending state."""
        trending = []
        
        for symbol in self.symbols:
            state = self.analyzers[symbol].detect_market_state()
            if 'trending' in state:
                trending.append(symbol)
        
        return trending
    
    def get_ranging_markets(self) -> List[str]:
        """Get markets in ranging state."""
        ranging = []
        
        for symbol in self.symbols:
            state = self.analyzers[symbol].detect_market_state()
            if state == 'ranging':
                ranging.append(symbol)
        
        return ranging
    
    def export_market_report(self) -> Dict:
        """Export comprehensive market report."""
        return {
            'markets_monitored': len(self.symbols),
            'opportunities': len(self.current_opportunities),
            'best_opportunity': str(self.get_best_opportunity()),
            'pattern_heatmap': self.get_pattern_heatmap(),
            'market_status': self.get_market_status(),
            'performance': self.get_all_performance(),
            'hottest_market': self.get_hottest_market(),
            'calmest_market': self.get_calmest_market(),
            'trending_markets': self.get_trending_markets(),
            'ranging_markets': self.get_ranging_markets()
        }
