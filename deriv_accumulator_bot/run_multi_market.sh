#!/bin/bash
# Launcher for Multi-Market Accumulator Bot

echo "=========================================="
echo "  Multi-Market Accumulator Bot Launcher"
echo "=========================================="
echo ""
echo "This bot will monitor 5 markets simultaneously:"
echo "  - R_10 (Volatility 10)"
echo "  - R_25 (Volatility 25)"
echo "  - R_50 (Volatility 50)"
echo "  - R_75 (Volatility 75)"
echo "  - R_100 (Volatility 100)"
echo ""
echo "Starting bot..."
echo ""

python multi_market_bot.py
