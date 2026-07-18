"""
Terminal UI for the Intelligent Trading Agent.
Provides a real-time dashboard with live updates using ANSI escape codes.
No external dependencies required - uses only standard library.
"""

import time
import os
import sys
import threading
from datetime import datetime
from collections import deque
from typing import Dict, Optional, List, Tuple


class TerminalUI:
    """
    Real-time terminal dashboard for the trading agent.
    Displays live market data, trade status, signals, and performance metrics.
    Uses ANSI escape codes for terminal manipulation (no external deps).
    """
    
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.update_thread = None
        
        # Data store (updated by agent)
        self.data = {
            'agent_id': '',
            'symbol': 'R_100',
            'status': 'Starting...',
            'connected': False,
            'authorized': False,
            'tick_count': 0,
            'total_trades': 0,
            'win_count': 0,
            'loss_count': 0,
            'daily_profit': 0.0,
            'daily_loss': 0.0,
            'session_profit': 0.0,
            'peak_profit': 0.0,
            'consecutive_losses': 0,
            'global_consecutive_losses': 0,
            'market_state': 'unknown',
            'market_health': 0.0,
            'current_strategy': 'N/A',
            'confidence': 0.0,
            'ensemble_confidence': 0.0,
            'trade_direction': None,
            'position_size': 0.0,
            'current_stake': 0.0,
            'martingale_step': 0,
            'use_martingale': False,
            'trading_paused': False,
            'pause_reason': '',
            'drawdown': 0.0,
            'bankroll': 0.0,
            'kelly_fraction': 0.0,
            'recent_win_rate': 0.0,
            'adaptive_threshold': 0.0,
            'trailing_stop_active': False,
            'active_contracts': {},
            'signals': {},
            'patterns': [],
            'multi_tf_trend': None,
            'recent_trades': [],
            'pnl_history': [],
            'ml_accuracy': 0.0,
            'ml_samples': 0,
            'ml_live_accuracy': 0.0,
            'last_update': '',
        }
        
        # Terminal dimensions
        self.term_width = 120
        self.term_height = 40
        
        # Animation frame
        self.spinner_idx = 0
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        
        # Price history for mini chart
        self.price_history = deque(maxlen=60)
        
    def start(self):
        """Start the terminal UI update thread."""
        self.running = True
        self.update_thread = threading.Thread(target=self._render_loop, daemon=True)
        self.update_thread.start()
        
    def stop(self):
        """Stop the terminal UI."""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=1)
        self._clear_screen()
        print("\n🤖 Trading Agent Terminal UI stopped.\n")
    
    def update(self, new_data: Dict):
        """Update the UI data from the agent."""
        with self.lock:
            for key, value in new_data.items():
                if key in self.data:
                    self.data[key] = value
            # Track price for mini chart
            if 'latest_price' in new_data and new_data['latest_price']:
                self.price_history.append(new_data['latest_price'])
    
    def _render_loop(self):
        """Main render loop - refreshes the display."""
        try:
            while self.running:
                self._render()
                time.sleep(0.5)  # Update every 500ms
        except Exception as e:
            pass  # Silently handle terminal errors
    
    def _render(self):
        """Render the full terminal UI."""
        with self.lock:
            self._clear_screen()
            lines = self._build_display()
            # Print all lines
            sys.stdout.write('\n'.join(lines))
            sys.stdout.flush()
    
    def _clear_screen(self):
        """Clear terminal and move cursor to top."""
        sys.stdout.write('\033[2J\033[H')
    
    def _color(self, text: str, color_code: str) -> str:
        """Wrap text in ANSI color codes."""
        colors = {
            'green': '\033[92m',
            'red': '\033[91m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'cyan': '\033[96m',
            'magenta': '\033[95m',
            'white': '\033[97m',
            'bold': '\033[1m',
            'dim': '\033[2m',
            'reset': '\033[0m',
            'bg_green': '\033[42m',
            'bg_red': '\033[41m',
            'bg_yellow': '\033[43m',
            'bg_blue': '\033[44m',
        }
        start = colors.get(color_code, '\033[0m')
        reset = colors['reset']
        return f"{start}{text}{reset}"
    
    def _bar(self, value: float, max_val: float, width: int = 20, good_high: bool = True) -> str:
        """Render a horizontal bar chart."""
        ratio = min(value / max_val, 1.0) if max_val > 0 else 0
        filled = int(ratio * width)
        empty = width - filled
        
        if good_high:
            if ratio > 0.7:
                color = 'green'
            elif ratio > 0.4:
                color = 'yellow'
            else:
                color = 'red'
        else:
            if ratio < 0.3:
                color = 'green'
            elif ratio < 0.6:
                color = 'yellow'
            else:
                color = 'red'
        
        bar = '█' * filled + '░' * empty
        return self._color(bar, color)
    
    def _mini_chart(self, width: int = 40, height: int = 6) -> List[str]:
        """Render a mini price chart from history."""
        if len(self.price_history) < 2:
            return [self._color("  [waiting for price data...]", 'dim')]
        
        prices = list(self.price_history)
        min_p = min(prices)
        max_p = max(prices)
        range_p = max_p - min_p if max_p > min_p else 1
        
        # Sample points to fit width
        step = max(1, len(prices) // width)
        sampled = prices[::step][:width]
        
        if len(sampled) < 2:
            return [self._color("  [not enough data]", 'dim')]
        
        lines = []
        for row in range(height - 1, -1, -1):
            threshold = min_p + (range_p * row / (height - 1)) if height > 1 else min_p
            next_threshold = min_p + (range_p * (row + 1) / (height - 1)) if height > 1 else max_p
            
            line = '  '
            for i, p in enumerate(sampled):
                if threshold <= p <= next_threshold:
                    # Determine color based on direction
                    if i > 0 and p >= sampled[i-1]:
                        line += self._color('█', 'green')
                    elif i > 0:
                        line += self._color('█', 'red')
                    else:
                        line += self._color('·', 'dim')
                elif p > next_threshold:
                    line += ' '
                else:
                    line += ' '
            lines.append(line)
        
        # Add price labels
        lines.append(f"  {self._color(f'${min_p:.2f}', 'dim')}{' ' * (width - 10)}{self._color(f'${max_p:.2f}', 'dim')}")
        return lines
    
    def _build_display(self) -> List[str]:
        """Build all display lines."""
        d = self.data
        lines = []
        spinner = self.spinner_chars[self.spinner_idx % len(self.spinner_chars)]
        self.spinner_idx += 1
        
        # === HEADER ===
        title = f"  {spinner} INTELLIGENT TRADING AGENT  {spinner}"
        lines.append('')
        lines.append(f"  {'=' * 80}")
        lines.append(f"  {self._color(title, 'cyan')}")
        lines.append(f"  {'=' * 80}")
        lines.append(f"  {self._color(d['agent_id'], 'dim')}  |  {d['last_update']}")
        lines.append('')
        
        # === STATUS BAR ===
        status_color = 'green' if d['connected'] and d['authorized'] else 'red'
        status_text = '● LIVE' if d['connected'] and d['authorized'] else '○ DISCONNECTED'
        if d['trading_paused']:
            status_color = 'yellow'
            status_text = '◐ PAUSED'
        
        lines.append(f"  {self._color('▸ STATUS', 'bold')}  {self._color(status_text, status_color)}  |  "
                     f"Symbol: {self._color(d['symbol'], 'cyan')}  |  "
                     f"Ticks: {d['tick_count']}  |  "
                     f"Trades: {d['total_trades']}")
        lines.append('')
        
        # === MAIN GRID: 2-COLUMN LAYOUT ===
        # Left column: Market + Signals
        # Right column: Performance + Risk
        
        # --- LEFT COLUMN: MARKET ---
        lines.append(f"  {self._color('┌─ MARKET ANALYSIS ─────────────────────────────', 'bold')}")
        
        # Market state with color
        state_colors = {
            'trending_up': 'green',
            'trending_down': 'red',
            'ranging': 'yellow',
            'volatile': 'magenta',
            'calm': 'blue',
            'unknown': 'dim'
        }
        state_color = state_colors.get(d['market_state'], 'white')
        
        lines.append(f"  │ State: {self._color(d['market_state'].upper(), state_color)}  "
                     f"Health: {self._bar(d['market_health'], 100, 15)} {d['market_health']:.0f}/100")
        
        # Multi-timeframe trend
        tf = d.get('multi_tf_trend')
        if tf and tf.get('is_trending'):
            tf_dir = tf.get('primary_direction', '?')
            tf_color = 'green' if tf_dir == 'up' else 'red'
            tf_str = f"  │ {self._color('📊 MULTI-TF TREND:', 'bold')} {self._color(tf_dir.upper(), tf_color)} "
            if tf.get('all_timeframes_align'):
                tf_str += self._color('★ ALL ALIGNED', 'green')
            elif tf.get('higher_medium_agree'):
                tf_str += self._color('✓ Higher+Medium Agree', 'yellow')
            lines.append(tf_str)
        
        # Strategy
        lines.append(f"  │ Strategy: {self._color(d['current_strategy'].upper(), 'cyan')}  |  "
                     f"Direction: {self._color((d['trade_direction'] or 'N/A').upper(), 'green' if d.get('trade_direction') == 'up' else 'red' if d.get('trade_direction') == 'down' else 'dim')}")
        
        # Signals
        signals = d.get('signals', {})
        signal_parts = []
        for sig_type in ['trend', 'ml', 'pattern', 'indicator']:
            sig = signals.get(sig_type)
            if sig:
                sig_dir = sig.get('direction', '?')
                sig_conf = sig.get('confidence', 0)
                sig_color = 'green' if sig_dir == 'up' else 'red' if sig_dir == 'down' else 'dim'
                signal_parts.append(f"{sig_type}={self._color(sig_dir.upper(), sig_color)}@{sig_conf:.2f}")
        
        if signal_parts:
            lines.append(f"  │ Signals: [{', '.join(signal_parts)}]")
        
        # Confidence
        conf = d.get('ensemble_confidence', 0) or d.get('confidence', 0)
        conf_color = 'green' if conf > 0.8 else 'yellow' if conf > 0.65 else 'red'
        lines.append(f"  │ {self._color('Confidence:', 'bold')} {self._bar(conf, 1.0, 20)} {self._color(f'{conf:.1%}', conf_color)}")
        
        # Patterns
        patterns = d.get('patterns', [])
        if patterns:
            pattern_str = ', '.join(list(patterns)[:4])
            if len(patterns) > 4:
                pattern_str += f' +{len(patterns)-4} more'
            lines.append(f"  │ Patterns: {self._color(pattern_str, 'magenta')}")
        
        lines.append(f"  └──────────────────────────────────────────────────")
        lines.append('')
        
        # --- RIGHT COLUMN: PERFORMANCE ---
        lines.append(f"  {self._color('┌─ PERFORMANCE ─────────────────────────────────', 'bold')}")
        
        # Win/Loss
        total = d['win_count'] + d['loss_count']
        win_rate = (d['win_count'] / total * 100) if total > 0 else 0
        wr_color = 'green' if win_rate > 60 else 'yellow' if win_rate > 45 else 'red'
        wc = d['win_count']
        lc = d['loss_count']
        rwr = d['recent_win_rate']
        lines.append(f"  │ {self._color('W/L:', 'bold')} {self._color(f'{wc}W', 'green')} / "
                     f"{self._color(f'{lc}L', 'red')}  "
                     f"({self._color(f'{win_rate:.1f}%', wr_color)})  "
                     f"Recent: {self._color(f'{rwr:.1%}', wr_color)}")
        
        # P&L
        pnl = d['daily_profit'] - d['daily_loss']
        pnl_color = 'green' if pnl > 0 else 'red' if pnl < 0 else 'dim'
        lines.append(f"  │ {self._color('P&L:', 'bold')} {self._color(f'${pnl:.2f}', pnl_color)}  "
                     f"(Profit: ${d['daily_profit']:.2f} / Loss: ${d['daily_loss']:.2f})")
        
        # Session P&L with peak
        session_pnl = d.get('session_profit', 0)
        peak = d.get('peak_profit', 0)
        spnl_color = 'green' if session_pnl > 0 else 'red'
        lines.append(f"  │ Session: {self._color(f'${session_pnl:.2f}', spnl_color)}  "
                     f"Peak: ${peak:.2f}  "
                     f"{'🔒 Trailing Stop ACTIVE' if d.get('trailing_stop_active') else ''}")
        
        # Consecutive losses
        cons = d['consecutive_losses']
        cons_color = 'red' if cons > 2 else 'yellow' if cons > 0 else 'green'
        lines.append(f"  │ Loss Streak: {self._color(str(cons), cons_color)}  "
                     f"Global: {d['global_consecutive_losses']}")
        
        lines.append(f"  └──────────────────────────────────────────────────")
        lines.append('')
        
        # --- RISK METRICS ROW ---
        lines.append(f"  {self._color('┌─ RISK MANAGEMENT ──────────────────────────────', 'bold')}")
        
        # Stake info
        stake = d.get('current_stake', 0)
        base = d.get('base_stake', 0.35) if 'base_stake' in d else 0.35
        mart_step = d.get('martingale_step', 0)
        mart_str = f"  Martingale: Step {mart_step}" if mart_step > 0 else "  Martingale: Inactive"
        
        lines.append(f"  │ Stake: ${stake:.2f} (Base: ${base:.2f}){mart_str}")
        
        # Kelly
        kelly = d.get('kelly_fraction', 0)
        dd = d.get('drawdown', 0)
        dd_color = 'red' if dd > 10 else 'yellow' if dd > 5 else 'green'
        lines.append(f"  │ Kelly: {kelly:.1%}  |  "
                     f"Bankroll: ${d.get('bankroll', 0):.2f}  |  "
                     f"Drawdown: {self._color(f'{dd:.1f}%', dd_color)}")
        
        # Adaptive threshold
        adaptive = d.get('adaptive_threshold', 0)
        lines.append(f"  │ Confidence Threshold: {adaptive:.2f}  |  "
                     f"ML Accuracy: {d.get('ml_accuracy', 0):.1%}  |  "
                     f"ML Live: {d.get('ml_live_accuracy', 0):.1%}")
        
        # Pause reason
        if d['trading_paused']:
            pause_reason = d['pause_reason']
            lines.append(f"  │ {self._color(f'⏸ PAUSED: {pause_reason}', 'yellow')}")
        
        lines.append(f"  └──────────────────────────────────────────────────")
        lines.append('')
        
        # === ACTIVE CONTRACTS ===
        contracts = d.get('active_contracts', {})
        if contracts:
            lines.append(f"  {self._color('┌─ ACTIVE CONTRACTS ────────────────────────────', 'bold')}")
            for cid, cinfo in list(contracts.items())[:3]:
                ctype = cinfo.get('contract_type', '?')
                cpredict = cinfo.get('prediction', '?')
                cprice = cinfo.get('buy_price', 0)
                ctick = cinfo.get('tick_opened', 0)
                lines.append(f"  │ {self._color('●', 'green')} {cid[:12]}  {ctype} {cpredict}  @ ${cprice:.2f}  "
                             f"(tick {ctick})")
            if len(contracts) > 3:
                lines.append(f"  │ ... and {len(contracts)-3} more")
            lines.append(f"  └──────────────────────────────────────────────────")
            lines.append('')
        
        # === MINI PRICE CHART ===
        lines.append(f"  {self._color('┌─ PRICE CHART ──────────────────────────────────', 'bold')}")
        chart_lines = self._mini_chart(50, 6)
        lines.extend(chart_lines)
        lines.append(f"  └──────────────────────────────────────────────────")
        lines.append('')
        
        # === RECENT TRADES ===
        recent = d.get('recent_trades', [])
        if recent:
            lines.append(f"  {self._color('┌─ RECENT TRADES ───────────────────────────────', 'bold')}")
            for trade in recent[-5:]:
                tres = trade.get('result', '?')
                ttype = trade.get('contract_type', '?')
                tpred = trade.get('prediction', '?')
                tpnl = trade.get('pnl', 0)
                tcolor = 'green' if tres == 'win' else 'red'
                lines.append(f"  │ {self._color('●', tcolor)} {ttype} {tpred}  "
                             f"{self._color(f'${tpnl:+.2f}', tcolor)}")
            lines.append(f"  └──────────────────────────────────────────────────")
            lines.append('')
        
        # === FOOTER ===
        lines.append(f"  {self._color('─' * 80, 'dim')}")
        lines.append(f"  {self._color('Ctrl+C to stop  |  Updates every 500ms', 'dim')}")
        lines.append('')
        
        return lines


# Standalone test
if __name__ == "__main__":
    ui = TerminalUI()
    ui.start()
    
    # Simulate data updates
    try:
        import random
        for i in range(100):
            time.sleep(1)
            ui.update({
                'tick_count': i * 10,
                'total_trades': i // 5,
                'win_count': i // 8,
                'loss_count': i // 12,
                'daily_profit': random.uniform(0, 5),
                'daily_loss': random.uniform(0, 2),
                'session_profit': random.uniform(-1, 3),
                'peak_profit': 3.5,
                'market_state': random.choice(['trending_up', 'ranging', 'trending_down']),
                'market_health': random.uniform(50, 90),
                'current_strategy': 'rise_fall',
                'confidence': random.uniform(0.6, 0.95),
                'ensemble_confidence': random.uniform(0.6, 0.95),
                'trade_direction': random.choice(['up', 'down', None]),
                'current_stake': 0.35,
                'martingale_step': 0,
                'consecutive_losses': i % 5,
                'global_consecutive_losses': i % 8,
                'drawdown': random.uniform(0, 8),
                'bankroll': 35.0,
                'kelly_fraction': random.uniform(0.05, 0.15),
                'recent_win_rate': random.uniform(0.4, 0.7),
                'adaptive_threshold': 0.65,
                'trailing_stop_active': i > 20,
                'ml_accuracy': 0.82,
                'ml_live_accuracy': 0.75,
                'ml_samples': 500,
                'latest_price': 500 + random.uniform(-5, 5),
                'patterns': ['bullish_engulfing', 'breakout'],
                'multi_tf_trend': {
                    'is_trending': True,
                    'primary_direction': 'up',
                    'all_timeframes_align': i % 3 == 0,
                    'higher_medium_agree': True,
                },
                'signals': {
                    'ml': {'direction': 'up', 'confidence': 0.72},
                    'pattern': {'direction': 'up', 'confidence': 0.85},
                },
                'active_contracts': {
                    '5833661419': {
                        'contract_type': 'CALL',
                        'prediction': 'RISE',
                        'buy_price': 0.35,
                        'tick_opened': 650,
                    }
                } if i % 2 == 0 else {},
                'recent_trades': [
                    {'result': 'win', 'contract_type': 'CALL', 'prediction': 'RISE', 'pnl': 0.30},
                    {'result': 'loss', 'contract_type': 'PUT', 'prediction': 'FALL', 'pnl': -0.35},
                ],
                'last_update': datetime.now().strftime('%H:%M:%S'),
                'connected': True,
                'authorized': True,
                'trading_paused': False,
            })
    except KeyboardInterrupt:
        pass
    finally:
        ui.stop()