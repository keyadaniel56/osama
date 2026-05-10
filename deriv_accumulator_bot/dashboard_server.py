"""
Real-time Trading Bot Dashboard Server
Lightweight HTTP server with WebSocket support (no Flask required)
"""

import json
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
import os
from collections import deque

# Thread-safe data storage
class BotDataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {
            'status': 'stopped',
            'session_start': None,
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'session_pnl': 0.0,
            'balance': 0.0,
            'active_trade': None,
            'recent_trades': deque(maxlen=50),
            'market_conditions': {},
            'performance_history': deque(maxlen=1000),
            'logs': deque(maxlen=100),
        }
        self.data_file = 'dashboard_data.json'
        self.load_data()
    
    def load_data(self):
        """Load persisted data from file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    saved = json.load(f)
                    with self.lock:
                        self.data.update(saved)
                        # Convert lists back to deques
                        self.data['recent_trades'] = deque(self.data.get('recent_trades', []), maxlen=50)
                        self.data['performance_history'] = deque(self.data.get('performance_history', []), maxlen=1000)
                        self.data['logs'] = deque(self.data.get('logs', []), maxlen=100)
            except Exception as e:
                print(f"[Dashboard] Error loading data: {e}")
    
    def save_data(self):
        """Persist data to file"""
        try:
            with self.lock:
                data_copy = self.data.copy()
                # Convert deques to lists for JSON serialization
                data_copy['recent_trades'] = list(data_copy['recent_trades'])
                data_copy['performance_history'] = list(data_copy['performance_history'])
                data_copy['logs'] = list(data_copy['logs'])
                
            with open(self.data_file, 'w') as f:
                json.dump(data_copy, f, indent=2)
        except Exception as e:
            print(f"[Dashboard] Error saving data: {e}")
    
    def get_data(self):
        """Get current data snapshot"""
        with self.lock:
            data_copy = self.data.copy()
            data_copy['recent_trades'] = list(data_copy['recent_trades'])
            data_copy['performance_history'] = list(data_copy['performance_history'])
            data_copy['logs'] = list(data_copy['logs'])
            return data_copy
    
    def get_filtered_data(self, start_date: str, end_date: str):
        """Get data filtered by date range"""
        from datetime import datetime
        
        try:
            start = datetime.fromisoformat(start_date + 'T00:00:00')
            end = datetime.fromisoformat(end_date + 'T23:59:59')
        except Exception as e:
            print(f"[Dashboard] Error parsing dates: {e}")
            return self.get_data()
        
        # Load trade history from file - try multiple paths
        history_file = 'trade_history.json'
        if not os.path.exists(history_file):
            history_file = 'deriv_accumulator_bot/trade_history.json'
        
        all_trades = []
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    all_trades = json.load(f)
                print(f"[Dashboard] Loaded {len(all_trades)} trades from history")
            except Exception as e:
                print(f"[Dashboard] Error loading history: {e}")
        else:
            print(f"[Dashboard] History file not found: {history_file}")
        
        # Filter trades by date
        filtered_trades = []
        total_pnl = 0.0
        wins = 0
        losses = 0
        
        for trade in all_trades:
            try:
                trade_time = datetime.fromisoformat(trade['timestamp'])
                if start <= trade_time <= end:
                    filtered_trades.append(trade)
                    total_pnl += trade['profit']
                    if trade['result'] == 'win':
                        wins += 1
                    else:
                        losses += 1
            except Exception as e:
                print(f"[Dashboard] Error processing trade: {e}")
                continue
        
        # Build performance history
        performance_history = []
        running_pnl = 0.0
        for trade in filtered_trades:
            running_pnl += trade['profit']
            performance_history.append({
                'timestamp': trade['timestamp'],
                'pnl': running_pnl
            })
        
        total_trades = len(filtered_trades)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        with self.lock:
            return {
                'status': self.data['status'],
                'session_start': start_date,
                'total_trades': total_trades,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'session_pnl': total_pnl,
                'balance': self.data['balance'],
                'active_trade': None,  # Don't show active trade for historical data
                'recent_trades': filtered_trades[-50:],  # Last 50 trades
                'market_conditions': {},  # No market conditions for historical data
                'performance_history': performance_history,
                'logs': []  # No logs for historical data
            }
    
    def update_status(self, status: str):
        with self.lock:
            self.data['status'] = status
            if status == 'running' and not self.data['session_start']:
                self.data['session_start'] = datetime.now().isoformat()
        self.save_data()
    
    def update_balance(self, balance: float):
        with self.lock:
            self.data['balance'] = balance
        self.save_data()
    
    def log_trade_entry(self, symbol: str, score: float, metrics: dict, stake: float):
        trade = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'score': score,
            'stake': stake,
            'metrics': metrics,
            'status': 'open'
        }
        with self.lock:
            self.data['active_trade'] = trade
        self.add_log('info', f"Entered {symbol} | Score: {score:.1f} | Stake: ${stake:.2f}")
        self.save_data()
    
    def log_trade_exit(self, symbol: str, profit: float, ticks: int, result: str):
        trade = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'profit': profit,
            'ticks': ticks,
            'result': result
        }
        
        with self.lock:
            self.data['total_trades'] += 1
            if result == 'win':
                self.data['wins'] += 1
            else:
                self.data['losses'] += 1
            
            self.data['session_pnl'] += profit
            self.data['win_rate'] = (self.data['wins'] / self.data['total_trades'] * 100) if self.data['total_trades'] > 0 else 0
            
            self.data['recent_trades'].appendleft(trade)
            self.data['performance_history'].append({
                'timestamp': trade['timestamp'],
                'pnl': self.data['session_pnl']
            })
            
            self.data['active_trade'] = None
        
        result_emoji = "✅" if result == 'win' else "❌"
        self.add_log('success' if result == 'win' else 'error', 
                     f"{result_emoji} {result.upper()} on {symbol} | P&L: ${profit:.2f} | Ticks: {ticks}")
        self.save_data()
    
    def update_market_conditions(self, markets: dict):
        with self.lock:
            self.data['market_conditions'] = markets
        self.save_data()
    
    def add_log(self, level: str, message: str):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        with self.lock:
            self.data['logs'].appendleft(log_entry)


# Global data store
data_store = BotDataStore()


class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for dashboard"""
    
    def do_GET(self):
        if self.path == '/':
            self.path = '/dashboard.html'
        elif self.path.startswith('/api/data'):
            # Parse query parameters for date filtering
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            
            start_date = params.get('start', [None])[0]
            end_date = params.get('end', [None])[0]
            
            print(f"[Dashboard] API request - start: {start_date}, end: {end_date}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            data = data_store.get_data()
            
            # Filter data by date if provided
            if start_date and end_date:
                print(f"[Dashboard] Filtering data from {start_date} to {end_date}")
                data = data_store.get_filtered_data(start_date, end_date)
            
            self.wfile.write(json.dumps(data).encode())
            return
        elif self.path == '/api/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = data_store.get_data()
            stats = {
                'total_trades': data['total_trades'],
                'wins': data['wins'],
                'losses': data['losses'],
                'win_rate': data['win_rate'],
                'session_pnl': data['session_pnl'],
                'balance': data['balance'],
                'status': data['status']
            }
            self.wfile.write(json.dumps(stats).encode())
            return
        
        return SimpleHTTPRequestHandler.do_GET(self)
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


class DashboardLogger:
    """Logger interface for the bot to use"""
    
    @staticmethod
    def update_status(status: str):
        data_store.update_status(status)
    
    @staticmethod
    def update_balance(balance: float):
        data_store.update_balance(balance)
    
    @staticmethod
    def log_trade_entry(symbol: str, score: float, metrics: dict, stake: float):
        data_store.log_trade_entry(symbol, score, metrics, stake)
    
    @staticmethod
    def log_trade_exit(symbol: str, profit: float, ticks: int, result: str):
        data_store.log_trade_exit(symbol, profit, ticks, result)
    
    @staticmethod
    def update_market_conditions(markets: dict):
        data_store.update_market_conditions(markets)
    
    @staticmethod
    def log_message(level: str, message: str):
        data_store.add_log(level, message)


def run_dashboard(host='0.0.0.0', port=8080):
    """Start the dashboard server"""
    server = HTTPServer((host, port), DashboardHandler)
    
    print(f"\n{'='*60}")
    print(f"   TRADING BOT DASHBOARD")
    print(f"{'='*60}")
    print(f"   Dashboard URL: http://localhost:{port}")
    print(f"   Access from network: http://<your-ip>:{port}")
    print(f"{'='*60}\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Dashboard] Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    run_dashboard()
