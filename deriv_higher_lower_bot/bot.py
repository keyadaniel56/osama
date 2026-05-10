"""
Higher/Lower Trading Bot for Volatility 15s
Strategy: If price is red (down) and decimal part < 200, buy LOWER with 5 ticks duration
Example: Price 123.156 (red) → decimal part 156 < 200 → BUY LOWER
"""

import os
import time
import json
import websocket
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_TOKEN = os.getenv("DERIV_API_TOKEN", "")
APP_ID = os.getenv("DERIV_APP_ID", "1089")
SYMBOL = "1HZ15V"  # Volatility 15s
STAKE = float(os.getenv("STAKE", "1.0"))
DURATION = 5  # 5 ticks

class HigherLowerBot:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.authorized = False
        self.last_price = None
        self.current_price = None
        self.in_trade = False
        self.trade_history = []
        self.total_profit = 0.0
        self.processed_contracts = set()  # Track processed contracts to avoid duplicates
        self.ticks_since_trade = 0  # Cooldown counter
        self.cooldown_ticks = 3  # Wait 3 ticks between trades
        self.active_contract_id = None  # Track current active contract
        self.tick_count = 0  # Track tick count for debugging
        
    def connect(self):
        """Connect to Deriv WebSocket API"""
        url = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}"
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.ws.run_forever()
    
    def _on_open(self, ws):
        """Handle connection open"""
        self.connected = True
        print(f"[{self._timestamp()}] ✅ Connected to Deriv API")
        self._authorize()
    
    def _authorize(self):
        """Authorize with API token"""
        self.ws.send(json.dumps({"authorize": API_TOKEN}))
    
    def _subscribe_ticks(self):
        """Subscribe to tick stream"""
        self.ws.send(json.dumps({
            "ticks": SYMBOL,
            "subscribe": 1
        }))
        print(f"[{self._timestamp()}] 📊 Subscribed to {SYMBOL} ticks")
    
    def _on_message(self, ws, message):
        """Handle incoming messages"""
        data = json.loads(message)
        msg_type = data.get("msg_type")
        
        if msg_type == "authorize":
            if "error" in data:
                print(f"[{self._timestamp()}] ❌ Auth error: {data['error']['message']}")
                return
            self.authorized = True
            account_id = data['authorize']['loginid']
            print(f"[{self._timestamp()}] ✅ Authorized as {account_id}")
            self._subscribe_ticks()
        
        elif msg_type == "tick":
            self._handle_tick(data["tick"])
        
        elif msg_type == "buy":
            self._handle_buy_response(data)
        
        elif msg_type == "proposal_open_contract":
            self._handle_contract_update(data)
    
    def _handle_tick(self, tick):
        """Process incoming tick and check trading conditions"""
        price = float(tick["quote"])
        self.tick_count += 1
        
        # Update price tracking
        self.last_price = self.current_price
        self.current_price = price
        
        # Skip if we don't have previous price yet
        if self.last_price is None:
            return
        
        # Skip if already in trade
        if self.in_trade:
            return
        
        # Increment cooldown counter
        self.ticks_since_trade += 1
        
        # Skip if in cooldown period
        if self.ticks_since_trade < self.cooldown_ticks:
            return
        
        # Check strategy conditions
        is_red = price < self.last_price  # Price went down (red candle)
        
        # Extract digits after decimal point
        price_str = f"{price:.3f}"  # Format to 3 decimal places
        decimal_part = price_str.split('.')[1] if '.' in price_str else "000"
        decimal_value = int(decimal_part)  # e.g., "456" -> 456
        
        print(f"[{self._timestamp()}] 📈 Price: {price:.3f} | Last: {self.last_price:.3f} | "
              f"Red: {is_red} | Decimal: {decimal_value}")
        
        # Strategy: If red and decimal part < 200
        if is_red and decimal_value < 200:
            self._buy_lower()
    
    def _buy_lower(self):
        """Execute LOWER trade"""
        self.in_trade = True
        self.ticks_since_trade = 0  # Reset cooldown counter
        
        payload = {
            "buy": "1",
            "price": STAKE,
            "parameters": {
                "amount": STAKE,
                "basis": "stake",
                "contract_type": "PUT",  # PUT = Lower
                "currency": "USD",
                "duration": DURATION,
                "duration_unit": "t",
                "symbol": SYMBOL,
                "barrier": "+1"  # Relative barrier offset of +1 pip
            }
        }
        
        self.ws.send(json.dumps(payload))
        print(f"[{self._timestamp()}] 🎯 Buying LOWER (barrier: +1) | Stake: ${STAKE} | Duration: {DURATION} ticks")
    
    def _handle_buy_response(self, data):
        """Handle buy confirmation"""
        if "error" in data:
            print(f"[{self._timestamp()}] ❌ Buy error: {data['error']['message']}")
            self.in_trade = False
            return
        
        buy_info = data.get("buy", {})
        contract_id = buy_info.get("contract_id")
        buy_price = buy_info.get("buy_price", STAKE)
        start_time = buy_info.get("start_time")
        
        # Get the actual entry price from the contract
        # We'll verify it in the contract update
        print(f"[{self._timestamp()}] ✅ Contract bought: {contract_id} (Buy price: ${buy_price})")
        
        # Subscribe to contract updates
        self.ws.send(json.dumps({
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "subscribe": 1
        }))
        
        # Store active contract for tracking
        self.active_contract_id = contract_id    
    def _handle_contract_update(self, data):
        """Handle contract status updates"""
        contract = data.get("proposal_open_contract", {})
        contract_id = contract.get("contract_id")
        is_sold = contract.get("is_sold")
        is_expired = contract.get("is_expired")
        status = contract.get("status")
        
        # Get entry price to verify our condition
        entry_spot = contract.get("entry_spot")
        if entry_spot and contract_id not in self.processed_contracts:
            entry_price = float(entry_spot)
            price_str = f"{entry_price:.3f}"
            decimal_part = price_str.split('.')[1] if '.' in price_str else "000"
            decimal_value = int(decimal_part)
            
            # Log the actual entry price once
            if not hasattr(self, '_logged_entry'):
                self._logged_entry = set()
            if contract_id not in self._logged_entry:
                self._logged_entry.add(contract_id)
                print(f"[{self._timestamp()}] 📍 Entry price: {entry_price:.3f} | Decimal: {decimal_value}")
        
        # Debug: Log all contract updates
        if contract_id and self.tick_count % 5 == 0:  # Log every 5 ticks to avoid spam
            print(f"[{self._timestamp()}] 🔍 Contract {contract_id}: status={status}, sold={is_sold}, expired={is_expired}")
        
        if (is_sold or is_expired) and contract_id not in self.processed_contracts:
            # Mark contract as processed to avoid duplicates
            self.processed_contracts.add(contract_id)
            
            profit = float(contract.get("profit", 0))
            result_status = "WIN" if profit > 0 else "LOSS"
            
            self.total_profit += profit
            self.trade_history.append({
                "contract_id": contract_id,
                "profit": profit,
                "status": result_status,
                "timestamp": self._timestamp()
            })
            
            result_emoji = "🎉" if profit > 0 else "😞"
            print(f"[{self._timestamp()}] {result_emoji} Trade {result_status} | "
                  f"Profit: ${profit:.2f} | Total P&L: ${self.total_profit:.2f}")
            
            self.in_trade = False
            self.active_contract_id = None
            self._print_stats()
    
    def _print_stats(self):
        """Print trading statistics"""
        if not self.trade_history:
            return
        
        wins = sum(1 for t in self.trade_history if t["status"] == "WIN")
        losses = len(self.trade_history) - wins
        win_rate = (wins / len(self.trade_history) * 100) if self.trade_history else 0
        
        print(f"[{self._timestamp()}] 📊 Stats: {len(self.trade_history)} trades | "
              f"W/L: {wins}/{losses} | Win Rate: {win_rate:.1f}% | P&L: ${self.total_profit:.2f}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"[{self._timestamp()}] ❌ WebSocket error: {error}")
    
    def _on_close(self, ws, code, msg):
        """Handle connection close"""
        self.connected = False
        self.authorized = False
        print(f"[{self._timestamp()}] 🔌 Connection closed: {code} {msg}")
    
    def _timestamp(self):
        """Get formatted timestamp"""
        return datetime.now().strftime("%H:%M:%S")
    
    def run(self):
        """Start the bot"""
        print("=" * 60)
        print("🤖 Higher/Lower Trading Bot - Volatility 15s")
        print("=" * 60)
        print(f"Symbol: {SYMBOL}")
        print(f"Stake: ${STAKE}")
        print(f"Duration: {DURATION} ticks")
        print(f"Strategy: Buy LOWER when price is RED and decimal part < 200")
        print("=" * 60)
        
        try:
            self.connect()
        except KeyboardInterrupt:
            print(f"\n[{self._timestamp()}] 🛑 Bot stopped by user")
            self._print_final_summary()
    
    def _print_final_summary(self):
        """Print final trading summary"""
        if not self.trade_history:
            print("No trades executed.")
            return
        
        wins = sum(1 for t in self.trade_history if t["status"] == "WIN")
        losses = len(self.trade_history) - wins
        win_rate = (wins / len(self.trade_history) * 100)
        
        print("\n" + "=" * 60)
        print("📊 FINAL SUMMARY")
        print("=" * 60)
        print(f"Total Trades: {len(self.trade_history)}")
        print(f"Wins: {wins}")
        print(f"Losses: {losses}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Total P&L: ${self.total_profit:.2f}")
        print("=" * 60)


if __name__ == "__main__":
    bot = HigherLowerBot()
    bot.run()
