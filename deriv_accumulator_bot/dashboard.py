"""
Real-time Trading Bot Dashboard
Web-based interface to monitor bot performance with live updates
"""

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import json
import os
from datetime import datetime
from threading import Lock

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Thread-safe data storage
data_lock = Lock()
bot_data = {
    'status': 'stopped',
    'session_start': None,
    'total_trades': 0,
    'wins': 0,
    'losses': 0,
    'win_rate': 0.0,
    'session_pnl': 0.0,
    'balance': 0.0,
    'active_trade': None,
    'recent_trades': [],
    'market_conditions': {},
    'performance_history': [],
    'daily_stats': {},
}


class DashboardLogger:
    """Logger that sends updates to the dashboard"""
    
    @staticmethod
    def update_status(status: str):
        with data_lock:
            bot_data['status'] = status
            if status == 'running' and not bot_data['session_start']:
                bot_data['session_start'] = datetime.now().isoformat()
        socketio.emit('status_update', {'status': status})
    
    @staticmethod
    def update_balance(balance: float):
        with data_lock:
            bot_data['balance'] = balance
        socketio.emit('balance_update', {'balance': balance})
    
    @staticmethod
    def log_trade_entry(symbol: str, score: float, metrics: dict, stake: float):
        trade = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'score': score,
            'stake': stake,
            'metrics': metrics,
            'status': 'open'
        }
        with data_lock:
            bot_data['active_trade'] = trade
        socketio.emit('trade_entry', trade)
    
    @staticmethod
    def log_trade_exit(symbol: str, profit: float, ticks: int, result: str):
        trade = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'profit': profit,
            'ticks': ticks,
            'result': result
        }
        
        with data_lock:
            bot_data['total_trades'] += 1
            if result == 'win':
                bot_data['wins'] += 1
            else:
                bot_data['losses'] += 1
            
            bot_data['session_pnl'] += profit
            bot_data['win_rate'] = (bot_data['wins'] / bot_data['total_trades'] * 100) if bot_data['total_trades'] > 0 else 0
            
            # Add to recent trades (keep last 50)
            bot_data['recent_trades'].insert(0, trade)
            bot_data['recent_trades'] = bot_data['recent_trades'][:50]
            
            # Add to performance history
            bot_data['performance_history'].append({
                'timestamp': trade['timestamp'],
                'pnl': bot_data['session_pnl']
            })
            
            bot_data['active_trade'] = None
        
        socketio.emit('trade_exit', trade)
        socketio.emit('stats_update', {
            'total_trades': bot_data['total_trades'],
            'wins': bot_data['wins'],
            'losses': bot_data['losses'],
            'win_rate': bot_data['win_rate'],
            'session_pnl': bot_data['session_pnl']
        })
    
    @staticmethod
    def update_market_conditions(markets: dict):
        with data_lock:
            bot_data['market_conditions'] = markets
        socketio.emit('market_update', markets)
    
    @staticmethod
    def log_message(level: str, message: str):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        socketio.emit('log_message', log_entry)


@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/data')
def get_data():
    """Get current bot data"""
    with data_lock:
        return jsonify(bot_data)


@app.route('/api/stats')
def get_stats():
    """Get statistics summary"""
    with data_lock:
        return jsonify({
            'total_trades': bot_data['total_trades'],
            'wins': bot_data['wins'],
            'losses': bot_data['losses'],
            'win_rate': bot_data['win_rate'],
            'session_pnl': bot_data['session_pnl'],
            'balance': bot_data['balance'],
            'status': bot_data['status']
        })


@socketio.on('connect')
def handle_connect():
    """Send current data when client connects"""
    with data_lock:
        socketio.emit('initial_data', bot_data)


def run_dashboard(host='0.0.0.0', port=5000):
    """Start the dashboard server"""
    print(f"\n{'='*60}")
    print(f"   TRADING BOT DASHBOARD")
    print(f"{'='*60}")
    print(f"   Dashboard URL: http://localhost:{port}")
    print(f"   Access from network: http://<your-ip>:{port}")
    print(f"{'='*60}\n")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    run_dashboard()
