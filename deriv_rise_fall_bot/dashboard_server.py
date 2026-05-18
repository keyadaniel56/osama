"""
Simple HTTP server with embedded dashboard and WebSocket for bot data.
"""

import http.server
import socketserver
import json
import threading
from urllib.parse import urlparse


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMC Bot - Live Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .stat-card h3 { font-size: 0.9em; opacity: 0.8; margin-bottom: 10px; }
        .stat-card .value { font-size: 2em; font-weight: bold; }
        .stat-card.positive .value { color: #4ade80; }
        .stat-card.negative .value { color: #f87171; }
        .analysis-panel {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .analysis-section { margin-bottom: 20px; }
        .analysis-section h3 {
            font-size: 1.2em;
            margin-bottom: 10px;
            border-bottom: 2px solid rgba(255,255,255,0.3);
            padding-bottom: 5px;
        }
        .indicator-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .indicator-label { opacity: 0.8; }
        .indicator-value { font-weight: bold; }
        .signal-box {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 15px;
            margin-top: 15px;
            text-align: center;
        }
        .signal-box.bullish { background: rgba(74, 222, 128, 0.3); border: 2px solid #4ade80; }
        .signal-box.bearish { background: rgba(248, 113, 113, 0.3); border: 2px solid #f87171; }
        .signal-box.neutral { background: rgba(156, 163, 175, 0.3); border: 2px solid #9ca3af; }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        .status-indicator.connected { background: #4ade80; }
        .status-indicator.disconnected { background: #f87171; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 SMC Bot - Live Dashboard</h1>
            <p><span class="status-indicator connected" id="statusIndicator"></span><span id="statusText">Running</span></p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card"><h3>Total Trades</h3><div class="value" id="totalTrades">0</div></div>
            <div class="stat-card"><h3>Win Rate</h3><div class="value" id="winRate">0%</div></div>
            <div class="stat-card" id="plCard"><h3>Profit/Loss</h3><div class="value" id="profitLoss">$0.00</div></div>
            <div class="stat-card"><h3>Current Price</h3><div class="value" id="currentPrice">-</div></div>
            <div class="stat-card"><h3>Market Structure</h3><div class="value" id="marketStructure">-</div></div>
            <div class="stat-card"><h3>MTF Trend</h3><div class="value" id="mtfTrend">-</div></div>
        </div>
        
        <div class="analysis-panel">
            <h2 style="margin-bottom: 20px;">📈 Live SMC Analysis</h2>
            
            <div class="analysis-section">
                <h3>Market Structure</h3>
                <div class="indicator-item"><span class="indicator-label">Structure Type:</span><span class="indicator-value" id="structureType">-</span></div>
                <div class="indicator-item"><span class="indicator-label">Trend:</span><span class="indicator-value" id="trendType">-</span></div>
                <div class="indicator-item"><span class="indicator-label">Strength:</span><span class="indicator-value" id="structureStrength">-</span></div>
            </div>
            
            <div class="analysis-section">
                <h3>Multi-Timeframe Analysis</h3>
                <div class="indicator-item"><span class="indicator-label">1-Minute:</span><span class="indicator-value" id="tf1m">-</span></div>
                <div class="indicator-item"><span class="indicator-label">5-Minute:</span><span class="indicator-value" id="tf5m">-</span></div>
                <div class="indicator-item"><span class="indicator-label">15-Minute:</span><span class="indicator-value" id="tf15m">-</span></div>
                <div class="indicator-item"><span class="indicator-label">Alignment:</span><span class="indicator-value" id="tfAlignment">-</span></div>
            </div>
            
            <div class="analysis-section">
                <h3>Order Blocks & Zones</h3>
                <div class="indicator-item"><span class="indicator-label">Bullish Order Blocks:</span><span class="indicator-value" id="bullishOB">0</span></div>
                <div class="indicator-item"><span class="indicator-label">Bearish Order Blocks:</span><span class="indicator-value" id="bearishOB">0</span></div>
                <div class="indicator-item"><span class="indicator-label">Support Zones:</span><span class="indicator-value" id="supportZones">0</span></div>
                <div class="indicator-item"><span class="indicator-label">Resistance Zones:</span><span class="indicator-value" id="resistanceZones">0</span></div>
            </div>
            
            <div class="signal-box neutral" id="signalBox">
                <h3>Current Signal</h3>
                <div style="font-size: 1.5em; margin: 10px 0;" id="signalDirection">NO SIGNAL</div>
                <div id="signalReason">Waiting for setup...</div>
                <div style="margin-top: 10px; font-size: 1.2em;" id="signalConfidence"></div>
            </div>
        </div>
    </div>
    
    <script>
        let updateInterval;
        
        function fetchData() {
            fetch('/data')
                .then(response => response.json())
                .then(data => updateDashboard(data))
                .catch(error => console.error('Error:', error));
        }
        
        function updateDashboard(data) {
            if (data.stats) {
                document.getElementById('totalTrades').textContent = data.stats.total_trades || 0;
                document.getElementById('winRate').textContent = (data.stats.win_rate || 0).toFixed(1) + '%';
                
                const pl = data.stats.profit_loss || 0;
                const plCard = document.getElementById('plCard');
                document.getElementById('profitLoss').textContent = '$' + pl.toFixed(2);
                plCard.className = 'stat-card ' + (pl >= 0 ? 'positive' : 'negative');
            }
            
            if (data.price) {
                document.getElementById('currentPrice').textContent = data.price.toFixed(2);
            }
            
            if (data.analysis) {
                const analysis = data.analysis;
                document.getElementById('marketStructure').textContent = analysis.market_structure?.structure || '-';
                document.getElementById('structureType').textContent = analysis.market_structure?.structure || '-';
                document.getElementById('trendType').textContent = analysis.market_structure?.trend || '-';
                document.getElementById('structureStrength').textContent = 
                    analysis.market_structure?.strength ? (analysis.market_structure.strength * 100).toFixed(0) + '%' : '-';
                
                const mtf = analysis.mtf_trend || {};
                document.getElementById('mtfTrend').textContent = mtf.aligned || '-';
                document.getElementById('tf1m').textContent = mtf['1m'] || '-';
                document.getElementById('tf5m').textContent = mtf['5m'] || '-';
                document.getElementById('tf15m').textContent = mtf['15m'] || '-';
                document.getElementById('tfAlignment').textContent = mtf.aligned || '-';
                
                document.getElementById('bullishOB').textContent = analysis.order_blocks?.bullish || 0;
                document.getElementById('bearishOB').textContent = analysis.order_blocks?.bearish || 0;
                document.getElementById('supportZones').textContent = analysis.support_zones || 0;
                document.getElementById('resistanceZones').textContent = analysis.resistance_zones || 0;
            }
            
            if (data.signal) {
                const signalBox = document.getElementById('signalBox');
                const signal = data.signal;
                
                if (signal.direction === 'RISE') {
                    signalBox.className = 'signal-box bullish';
                    document.getElementById('signalDirection').textContent = '🚀 RISE';
                } else if (signal.direction === 'FALL') {
                    signalBox.className = 'signal-box bearish';
                    document.getElementById('signalDirection').textContent = '📉 FALL';
                } else {
                    signalBox.className = 'signal-box neutral';
                    document.getElementById('signalDirection').textContent = 'NO SIGNAL';
                }
                
                document.getElementById('signalReason').textContent = signal.reason || '';
                document.getElementById('signalConfidence').textContent = 
                    signal.confidence ? 'Confidence: ' + (signal.confidence * 100).toFixed(0) + '%' : '';
            }
        }
        
        fetchData();
        updateInterval = setInterval(fetchData, 1000);
    </script>
</body>
</html>"""


class DashboardServer:
    """Simple HTTP server with embedded dashboard."""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.latest_data = {}
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the HTTP server in a background thread."""
        handler = self._create_handler()
        self.server = socketserver.TCPServer(("", self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"📊 Dashboard running at http://localhost:{self.port}")
    
    def _create_handler(self):
        """Create request handler with access to latest_data."""
        latest_data = self.latest_data
        
        class DashboardHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/' or self.path == '/index.html':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(HTML_DASHBOARD.encode())
                elif self.path == '/data':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(latest_data).encode())
                else:
                    self.send_error(404)
            
            def log_message(self, format, *args):
                pass  # Suppress logs
        
        return DashboardHandler
    
    def update(self, data: dict):
        """Update dashboard with new data."""
        self.latest_data.update(data)
    
    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
