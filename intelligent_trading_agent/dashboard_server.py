"""
Dashboard server - provides real-time data API for web UI.
Run alongside agent.py for beautiful monitoring.
"""

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Shared state file (updated by agent.py)
STATE_FILE = 'dashboard_state.json'

def get_agent_state():
    """Read current agent state from file."""
    if not os.path.exists(STATE_FILE):
        return get_default_state()
    
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return get_default_state()

def get_default_state():
    """Return default/empty state."""
    return {
        'daily_profit': 0.0,
        'daily_loss': 0.0,
        'win_count': 0,
        'loss_count': 0,
        'total_trades': 0,
        'consecutive_losses': 0,
        'market_state': 'analyzing',
        'market_health': 0,
        'current_strategy': None,
        'confidence': 0.0,
        'drawdown': 0.0,
        'max_drawdown': 0.0,
        'tick_count': 0,
        'trading_paused': False,
        'pause_reason': None,
        'trade_direction': None,
        'ensemble_confidence': 0.0,
        'signals': {
            'ml': None,
            'pattern': None,
            'indicator': None
        },
        'recent_trades': [],
        'market_opportunities': [],
        'pnl_history': []
    }

@app.route('/')
def dashboard():
    """Serve the dashboard HTML."""
    with open('dashboard.html', 'r') as f:
        return f.read()

@app.route('/api/dashboard')
def api_dashboard():
    """Get current dashboard data."""
    return jsonify(get_agent_state())

@app.route('/api/pause', methods=['POST'])
def api_pause():
    """Pause trading."""
    state = get_agent_state()
    state['trading_paused'] = True
    state['pause_reason'] = 'User paused at ' + datetime.now().strftime('%H:%M:%S')
    save_state(state)
    return jsonify({'status': 'paused'})

@app.route('/api/resume', methods=['POST'])
def api_resume():
    """Resume trading."""
    state = get_agent_state()
    state['trading_paused'] = False
    state['pause_reason'] = None
    save_state(state)
    return jsonify({'status': 'resumed'})

@app.route('/api/reset-daily', methods=['POST'])
def api_reset_daily():
    """Reset daily stats."""
    state = get_agent_state()
    state['daily_profit'] = 0.0
    state['daily_loss'] = 0.0
    state['win_count'] = 0
    state['loss_count'] = 0
    state['consecutive_losses'] = 0
    state['recent_trades'] = []
    state['pnl_history'] = []
    save_state(state)
    return jsonify({'status': 'reset'})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Signal to stop the agent."""
    # Create a stop signal file
    with open('STOP_SIGNAL', 'w') as f:
        f.write('STOP')
    return jsonify({'status': 'stop signal sent'})

def save_state(state):
    """Save state to file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving state: {e}")

if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║    🚀 Trading Agent Dashboard Server Starting...         ║
    ║                                                           ║
    ║  📊 Dashboard: http://localhost:5000                     ║
    ║  📡 API: http://localhost:5000/api/dashboard             ║
    ║                                                           ║
    ║  Make sure agent.py is running in another terminal!     ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    app.run(debug=False, host='0.0.0.0', port=5000)
