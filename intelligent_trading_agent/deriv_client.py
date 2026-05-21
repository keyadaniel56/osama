"""
Deriv API Client wrapper for the intelligent trading agent.
Reusable and robust API client for trading operations.
"""

import json
import time
import threading
import websocket
from typing import Callable, Optional, Dict, List
from logger import agent_logger


DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3"


class DerivClient:
    """
    WebSocket client for Deriv trading platform.
    Handles: connection, authorization, tick streaming, contract execution.
    """
    
    def __init__(self, app_id: str, token: str, symbol: str = "R_100", symbols: List[str] = None):
        self.app_id = app_id
        self.token = token
        self.symbol = symbol  # Primary symbol for trading
        self.symbols = symbols or [symbol]  # All symbols to monitor
        self.ws = None
        self.connected = False
        self.authorized = False
        self._req_id = 1
        
        # Reconnection settings
        self.should_reconnect = True
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        
        # Callbacks
        self.on_tick: Optional[Callable] = None
        self.on_contract_result: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Pending contracts tracking
        self._pending_contracts: Dict = {}
        self._lock = threading.Lock()
        
        # Tick history for analysis (per symbol)
        self.tick_history: Dict[str, List[Dict]] = {sym: [] for sym in self.symbols}
        self.max_history_size = 500
        
        # Tick counters (total ticks received, not limited by history size)
        self.tick_counters: Dict[str, int] = {sym: 0 for sym in self.symbols}
        
        # Tick health monitoring
        self.last_tick_time: Dict[str, float] = {sym: time.time() for sym in self.symbols}
        self.tick_timeout = 30  # seconds - if no tick for 30s, resubscribe
        self.subscription_ids: Dict[str, str] = {}  # symbol -> subscription_id for resubscription
    
    def connect(self):
        """Connect to Deriv WebSocket."""
        try:
            url = f"{DERIV_WS_URL}?app_id={self.app_id}"
            self.ws = websocket.WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error_handler,
                on_close=self._on_close,
            )
            
            # Run in daemon thread
            thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            thread.start()
            
            # Wait for connection
            timeout = 10
            while not self.connected and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
            
            if not self.connected:
                raise ConnectionError("Failed to connect to Deriv WebSocket")
            
            agent_logger.log_info(f"Connected to Deriv: {self.symbol}")
            
        except Exception as e:
            agent_logger.log_error(f"Connection failed: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from Deriv."""
        self.should_reconnect = False  # Disable auto-reconnect on manual disconnect
        if self.ws:
            self.ws.close()
            self.connected = False
            agent_logger.log_info("Disconnected from Deriv")
    
    def _send(self, payload: Dict):
        """Send JSON message to server."""
        try:
            with self._lock:
                payload["req_id"] = self._req_id
                self._req_id += 1
            self.ws.send(json.dumps(payload))
            return payload  # Return the payload with req_id for subscription tracking
        except Exception as e:
            agent_logger.log_error(f"Send error: {e}")
            return None
    
    def _on_open(self, ws):
        """WebSocket opened."""
        self.connected = True
        self._authorize()
    
    def _authorize(self):
        """Authorize with API token."""
        self._send({"authorize": self.token})
    
    def _on_message(self, ws, message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            msg_type = data.get("msg_type")
            
            # Log ALL messages for debugging (including ticks)
            # TODO: Remove this after debugging - it's very verbose
            if msg_type == "tick":
                # Log tick messages occasionally
                symbol = data.get("tick", {}).get("symbol", "unknown")
                if len(self.tick_history.get(symbol, [])) % 50 == 0:
                    agent_logger.log_info(f"Received: tick ({symbol})")
            else:
                agent_logger.log_info(f"Received: {msg_type}")
            
            if msg_type == "authorize":
                self._handle_authorize(data)
            elif msg_type == "tick":
                self._handle_tick(data)
            elif msg_type == "buy":
                self._handle_buy(data)
            elif msg_type == "proposal_open_contract":
                self._handle_contract_update(data)
            elif msg_type == "sell":
                self._handle_sell(data)
            elif msg_type == "forget":
                # Confirmation that we've unsubscribed - no action needed
                pass
            elif msg_type == "error":
                self._handle_error(data)
            else:
                # Log unknown message types
                agent_logger.log_info(f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            agent_logger.log_error(f"JSON decode error: {message}")
        except Exception as e:
            agent_logger.log_error(f"Message handling error: {e}")
    
    def _handle_authorize(self, data: Dict):
        """Handle authorization response."""
        if "error" in data:
            agent_logger.log_error(f"Auth error: {data['error']['message']}")
            self.authorized = False
        else:
            self.authorized = True
            account_id = data['authorize']['loginid']
            agent_logger.log_info(f"Authorized: Account {account_id}")
            self._subscribe_ticks()
    
    def _subscribe_ticks(self):
        """Subscribe to tick updates for all monitored symbols."""
        for symbol in self.symbols:
            response = self._send({
                "ticks": symbol,
                "subscribe": 1
            })
            agent_logger.log_info(f"Subscribed to ticks: {symbol}")
            # Reset last tick time when subscribing
            self.last_tick_time[symbol] = time.time()
    
    def _handle_tick(self, data: Dict):
        """Handle tick data."""
        try:
            tick = data.get("tick", {})
            symbol = tick.get('symbol', self.symbol)
            
            # Store subscription ID for potential resubscription
            subscription_id = data.get("subscription", {}).get("id")
            if subscription_id and symbol:
                self.subscription_ids[symbol] = subscription_id
            
            tick_data = {
                'epoch': tick.get('epoch'),
                'quote': tick.get('quote'),
                'symbol': symbol,
                'timestamp': time.time()
            }
            
            # Update last tick time for health monitoring
            self.last_tick_time[symbol] = time.time()
            
            # Increment tick counter (unlimited, for tracking total ticks)
            if symbol not in self.tick_counters:
                self.tick_counters[symbol] = 0
            self.tick_counters[symbol] += 1
            
            # Store in history per symbol (limited size for analysis)
            if symbol not in self.tick_history:
                self.tick_history[symbol] = []
            
            self.tick_history[symbol].append(tick_data)
            if len(self.tick_history[symbol]) > self.max_history_size:
                self.tick_history[symbol].pop(0)
            
            # Log occasionally to verify ticks are flowing (use counter, not history length)
            if self.tick_counters[symbol] % 100 == 0:
                agent_logger.log_info(f"📊 Tick milestone: {symbol} has received {self.tick_counters[symbol]} total ticks (history: {len(self.tick_history[symbol])})")
            
            # Trigger callback
            if self.on_tick:
                self.on_tick(tick_data)
                
        except Exception as e:
            agent_logger.log_error(f"Tick handling error: {e}")
    
    def _handle_buy(self, data: Dict):
        """Handle buy contract response."""
        if "error" in data:
            agent_logger.log_error(f"Buy error: {data['error']['message']}")
            return
            
        contract = data.get("buy", {})
        contract_id = contract.get("contract_id")
        buy_price = contract.get("buy_price", 0)
        
        if contract_id:
            contract_id = str(contract_id)  # Normalize to string
            self._pending_contracts[contract_id] = {
                'type': 'buy',
                'time': time.time(),
                'buy_price': buy_price,
                'data': contract
            }
            agent_logger.log_info(f"Contract bought: {contract_id} - ${buy_price:.2f}")
            
            # Subscribe to contract updates to get the result when it closes
            self._subscribe_to_contract(contract_id)
    
    def _subscribe_to_contract(self, contract_id: int):
        """Subscribe to contract updates to track when it closes."""
        self._send({
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "subscribe": 1
        })
    
    def _unsubscribe_from_contract(self, subscription_id: str):
        """Unsubscribe from contract updates using the subscription ID."""
        if subscription_id:
            self._send({
                "forget": subscription_id
            })
            agent_logger.log_info(f"🔕 Unsubscribed from contract updates (subscription_id={subscription_id})")
    
    def _handle_contract_update(self, data: Dict):
        """Handle contract status updates."""
        contract = data.get("proposal_open_contract", {})
        contract_id = str(contract.get("contract_id", ""))  # Normalize to string
        status = contract.get("status", "")
        is_expired = contract.get("is_expired", 0)
        is_sold = contract.get("is_sold", 0)
        profit = contract.get("profit", 0)
        sell_price = contract.get("sell_price", 0)
        
        # Store subscription ID from response for unsubscribe
        subscription_id = data.get("subscription", {}).get("id")
        if subscription_id and contract_id in self._pending_contracts:
            self._pending_contracts[contract_id]['subscription_id'] = subscription_id
        
        # Log every update so we can see when contract expires
        if contract_id:
            pending = self._pending_contracts.get(contract_id, {})
            update_count = pending.get('update_count', 0) + 1
            if contract_id in self._pending_contracts:
                self._pending_contracts[contract_id]['update_count'] = update_count
            
            if update_count % 30 == 0 or status not in ('open', ''):
                elapsed = time.time() - pending.get('time', time.time()) if pending else 0
                agent_logger.log_info(
                    f"Contract {contract_id}: status={status}, "
                    f"is_expired={is_expired}, is_sold={is_sold}, "
                    f"profit={profit}, elapsed={elapsed:.0f}s"
                )
        
        # Fire result when contract is closed — check ALL possible close indicators
        contract_closed = (
            status in ("sold", "won", "lost")
            or is_expired == 1
            or is_sold == 1
        )
        
        if contract_closed and contract_id:
            agent_logger.log_info(
                f"Contract {contract_id} CLOSED — status={status}, "
                f"sell_price=${sell_price:.2f}, profit=${profit:.2f}"
            )
            
            # CRITICAL: Unsubscribe from contract updates to stop receiving messages
            pending = self._pending_contracts.get(contract_id, {})
            subscription_id = pending.get('subscription_id') or data.get("subscription", {}).get("id")
            if subscription_id:
                self._unsubscribe_from_contract(subscription_id)
            
            # Fire result callback — agent uses this to update active_contracts
            if self.on_contract_result:
                self.on_contract_result({
                    'contract_id': contract_id,
                    'result': sell_price,
                    'profit': profit,
                    'status': status,
                    'timestamp': time.time()
                })
            
            # Clean up pending contracts
            if contract_id in self._pending_contracts:
                del self._pending_contracts[contract_id]
    
    def _handle_sell(self, data: Dict):
        """Handle sell contract response."""
        sell = data.get("sell", {})
        contract_id = sell.get("contract_id")
        
        if contract_id and contract_id in self._pending_contracts:
            result = sell.get("sell_price", 0)
            self._pending_contracts[contract_id]['result'] = result
            
            # Trigger callback
            if self.on_contract_result:
                self.on_contract_result({
                    'contract_id': contract_id,
                    'result': result,
                    'timestamp': time.time()
                })
    
    def _handle_error(self, data: Dict):
        """Handle error message."""
        error = data.get("error", {})
        message = error.get("message", "Unknown error")
        agent_logger.log_error(f"API error: {message}")
        if self.on_error:
            self.on_error(message)
    
    def _on_error_handler(self, ws, error):
        """WebSocket error handler."""
        agent_logger.log_error(f"WebSocket error: {error}")
        if self.on_error:
            self.on_error(str(error))
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket closed."""
        self.connected = False
        self.authorized = False
        
        if close_status_code:
            agent_logger.log_warning(f"WebSocket closed: code={close_status_code}, msg={close_msg}")
        else:
            agent_logger.log_warning("WebSocket closed")
        
        # Attempt automatic reconnection if enabled
        if self.should_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            agent_logger.log_info(
                f"🔄 Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts} "
                f"in {self.reconnect_delay} seconds..."
            )
            time.sleep(self.reconnect_delay)
            
            try:
                self.connect()
                self.reconnect_attempts = 0  # Reset on successful reconnection
                agent_logger.log_info("✅ Reconnected successfully!")
            except Exception as e:
                agent_logger.log_error(f"❌ Reconnection attempt {self.reconnect_attempts} failed: {e}")
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    agent_logger.log_error("❌ Max reconnection attempts reached. Giving up.")
                    if self.on_error:
                        self.on_error("Max reconnection attempts reached")
    
    def buy_contract(self, symbol: str, contract_type: str, duration: int, duration_unit: str = "m", amount: float = 1.0, currency: str = "USD") -> Optional[str]:
        """
        Buy a contract.
        
        Args:
            symbol: Trading symbol (e.g., "R_100")
            contract_type: Contract type (e.g., "CALL", "PUT")
            duration: Duration value
            duration_unit: Duration unit - "s" (seconds), "m" (minutes), "h" (hours), "t" (ticks)
            amount: Stake amount
            currency: Currency code (default: "USD")
            
        Returns: contract_id (asynchronously via callback)
        """
        payload = {
            "buy": "1",
            "price": amount,
            "parameters": {
                "contract_type": contract_type,
                "symbol": symbol,
                "duration": duration,
                "duration_unit": duration_unit,
                "basis": "stake",
                "amount": amount,
                "currency": currency
            }
        }
        self._send(payload)
        agent_logger.log_info(f"Buy request sent: {contract_type} on {symbol} for ${amount} {currency} - {duration}{duration_unit}")
        # Returns contract_id asynchronously via callback
        return None
    
    def get_tick_history(self, symbol: str = None) -> List[Dict]:
        """Get recent tick history for a symbol."""
        if symbol is None:
            symbol = self.symbol
        return self.tick_history.get(symbol, []).copy()
    
    def get_tick_counter(self, symbol: str = None) -> int:
        """Get total tick count for a symbol (not limited by history size)."""
        if symbol is None:
            symbol = self.symbol
        return self.tick_counters.get(symbol, 0)
    
    def get_pending_contracts(self) -> Dict:
        """Get pending contracts."""
        with self._lock:
            return self._pending_contracts.copy()
    
    def check_tick_health(self) -> Dict[str, bool]:
        """
        Check if ticks are flowing for all symbols.
        Returns dict of symbol -> is_healthy (True if ticks received recently).
        """
        current_time = time.time()
        health_status = {}
        
        for symbol in self.symbols:
            last_tick = self.last_tick_time.get(symbol, 0)
            time_since_tick = current_time - last_tick
            is_healthy = time_since_tick < self.tick_timeout
            health_status[symbol] = is_healthy
            
            if not is_healthy and self.connected and self.authorized:
                agent_logger.log_warning(
                    f"⚠️ Tick timeout for {symbol}: {time_since_tick:.1f}s since last tick "
                    f"(threshold: {self.tick_timeout}s)"
                )
        
        return health_status
    
    def resubscribe_to_ticks(self, symbol: str = None):
        """
        Resubscribe to tick stream for a symbol (or all symbols if None).
        Use this when ticks stop flowing.
        """
        symbols_to_resubscribe = [symbol] if symbol else self.symbols
        
        for sym in symbols_to_resubscribe:
            agent_logger.log_info(f"🔄 Resubscribing to ticks for {sym}...")
            
            # Unsubscribe first if we have a subscription ID
            if sym in self.subscription_ids:
                self._send({
                    "forget": self.subscription_ids[sym]
                })
                agent_logger.log_info(f"🔕 Unsubscribed from old tick stream: {sym}")
                del self.subscription_ids[sym]
            
            # Subscribe again
            self._send({
                "ticks": sym,
                "subscribe": 1
            })
            self.last_tick_time[sym] = time.time()
            agent_logger.log_info(f"✅ Resubscribed to ticks: {sym}")
