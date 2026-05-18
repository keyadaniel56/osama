#!/bin/bash

echo "🎯 Starting SMC Bot with Live Chart Dashboard"
echo "=============================================="
echo ""
echo "📦 Installing dependencies..."
pip install -q websockets

echo ""
echo "🚀 Starting bot..."
echo "📊 Dashboard will be available at: http://localhost:8765"
echo "🌐 Open chart_dashboard.html in your browser"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python smc_bot.py
