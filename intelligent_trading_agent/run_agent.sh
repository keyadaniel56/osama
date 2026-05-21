#!/bin/bash
# Quick start script for Intelligent Trading Agent

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  🚀 Intelligent Trading Agent - Quick Start              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

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

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        echo "Please install python3-venv: sudo apt install python3-venv"
        exit 1
    fi
    
    echo "✓ Virtual environment created"
    echo ""
    echo "Installing dependencies..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
    
    echo "✓ Dependencies installed"
else
    # Activate existing virtual environment
    source venv/bin/activate
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to activate virtual environment"
        exit 1
    fi
    
    echo "✓ Virtual environment activated ($(python --version))"
fi

# Verify required packages are installed
echo "🔍 Checking dependencies..."
python -c "import websocket, sklearn, numpy" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "⚠️  Some dependencies missing, installing..."
    pip install -r requirements.txt
fi

echo "✓ All dependencies ready"
echo ""

# Display configuration
echo "📋 Configuration:"
SYMBOL=$(grep "^SYMBOL=" .env | cut -d '=' -f2)
STAKE=$(grep "^STAKE=" .env | cut -d '=' -f2)
echo "   Symbol: ${SYMBOL:-R_100}"
echo "   Stake: \$${STAKE:-1.0}"
echo ""

# Start agent
echo "🤖 Starting Trading Agent..."
echo "   Press Ctrl+C to stop"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""

python agent.py

# Deactivate virtual environment on exit
deactivate 2>/dev/null

