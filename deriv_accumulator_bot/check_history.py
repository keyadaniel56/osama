#!/usr/bin/env python3
"""
Quick script to check trade history file
"""
import json
import os
from datetime import datetime

HISTORY_FILE = "trade_history.json"

print("=" * 60)
print("TRADE HISTORY CHECK")
print("=" * 60)

# Check if file exists
if os.path.exists(HISTORY_FILE):
    print(f"✅ History file found: {HISTORY_FILE}")
    
    # Load and display
    try:
        with open(HISTORY_FILE, 'r') as f:
            trades = json.load(f)
        
        print(f"✅ Total trades in history: {len(trades)}")
        
        if trades:
            print("\nFirst trade:")
            print(f"  Time: {trades[0]['timestamp']}")
            print(f"  Symbol: {trades[0]['symbol']}")
            print(f"  Profit: ${trades[0]['profit']:.2f}")
            print(f"  Result: {trades[0]['result']}")
            
            print("\nLast trade:")
            print(f"  Time: {trades[-1]['timestamp']}")
            print(f"  Symbol: {trades[-1]['symbol']}")
            print(f"  Profit: ${trades[-1]['profit']:.2f}")
            print(f"  Result: {trades[-1]['result']}")
            
            # Calculate stats
            wins = sum(1 for t in trades if t['result'] == 'win')
            losses = sum(1 for t in trades if t['result'] == 'loss')
            total_pnl = sum(t['profit'] for t in trades)
            
            print("\nOverall Stats:")
            print(f"  Wins: {wins}")
            print(f"  Losses: {losses}")
            print(f"  Win Rate: {(wins/len(trades)*100):.1f}%")
            print(f"  Total P&L: ${total_pnl:.2f}")
            
            # Date range
            dates = [datetime.fromisoformat(t['timestamp']).date() for t in trades]
            print(f"\nDate Range:")
            print(f"  First: {min(dates)}")
            print(f"  Last: {max(dates)}")
            
        else:
            print("⚠️  History file is empty")
            
    except Exception as e:
        print(f"❌ Error reading history: {e}")
else:
    print(f"❌ History file not found: {HISTORY_FILE}")
    print("\nSearching in other locations...")
    
    alt_path = "deriv_accumulator_bot/trade_history.json"
    if os.path.exists(alt_path):
        print(f"✅ Found at: {alt_path}")
    else:
        print(f"❌ Not found at: {alt_path}")

print("=" * 60)
