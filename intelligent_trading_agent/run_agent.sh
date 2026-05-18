#!/bin/bash
# Quick start script for Intelligent Trading Agent with Dashboard

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  🚀 Intelligent Trading Agent - Quick Start              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

cd intelligent_trading_agent

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Missing .env file!"
    echo ""
    echo "Setup instructions:"
    echo "1. Copy .env.example to .env:"
    echo "   cp .env.example .env"
    echo ""
    echo "2. Add your Deriv API token to .env:"
    echo "   DERIV_API_TOKEN=your_token_here"
    echo ""
    echo "3. Get a token from: https://app.deriv.com/account/api-token"
    exit 1
fi

# Activate virtual environment
. venv/bin/activate

echo "✓ Environment ready"
echo ""
echo "Starting services..."
echo ""

# Start dashboard server in background
echo "📊 Starting Dashboard Server (http://localhost:5000)..."
python3 dashboard_server.py &
DASHBOARD_PID=$!
sleep 2

# Start agent
echo "🤖 Starting Trading Agent..."
echo ""
python3 agent.py

# Clean up on exit
kill $DASHBOARD_PID 2>/dev/null
