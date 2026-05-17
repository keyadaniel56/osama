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
    
    def __init__(self, app_id: str, token: str, symbol: str = "R_100"):
        self.app_id = app_id
        self.token = token
        self.symbol = symbol
        self.ws = None
        self.connected = False
        self.authorized = False
        self._req_id = 1
        
        # Callbacks
        self.on_tick: Optional[Callable] = None
        self.on_contract_result: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Pending contracts tracking
        self._pending_contracts: Dict = {}
        self._lock = threading.Lock()
        
        # Tick history for analysis
        self.tick_history: List[Dict] = []
        self.max_history_size = 500
    
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
        except Exception as e:
            agent_logger.log_error(f"Send error: {e}")
    
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
            
            if msg_type == "authorize":
                self._handle_authorize(data)
            elif msg_type == "tick":
                self._handle_tick(data)
            elif msg_type == "buy":
                self._handle_buy(data)
            elif msg_type == "sell":
                self._handle_sell(data)
            elif msg_type == "error":
                self._handle_error(data)
                
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
        """Subscribe to tick updates."""
        self._send({
            "ticks": self.symbol,
            "subscribe": 1
        })
    
    def _handle_tick(self, data: Dict):
        """Handle tick data."""
        try:
            tick = data.get("tick", {})
            tick_data = {
                'epoch': tick.get('epoch'),
                'quote': tick.get('quote'),
                'symbol': tick.get('symbol'),
                'timestamp': time.time()
            }
            
            # Store in history
            self.tick_history.append(tick_data)
            if len(self.tick_history) > self.max_history_size:
                self.tick_history.pop(0)
            
            # Trigger callback
            if self.on_tick:
                self.on_tick(tick_data)
                
        except Exception as e:
            agent_logger.log_error(f"Tick handling error: {e}")
    
    def _handle_buy(self, data: Dict):
        """Handle buy contract response."""
        contract = data.get("buy", {})
        contract_id = contract.get("contract_id")
        
        if contract_id:
            self._pending_contracts[contract_id] = {
                'type': 'buy',
                'time': time.time(),
                'data': contract
            }
            agent_logger.log_info(f"Contract bought: {contract_id}")
    
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
        agent_logger.log_warning("WebSocket closed")
    
    def buy_contract(self, symbol: str, contract_type: str, duration: int, amount: float) -> Optional[str]:
        """
        Buy a contract.
        Returns: contract_id
        """
        payload = {
            "buy": 1,
            "subscribe": 1,
            "symbol": symbol,
            "type": contract_type,
            "duration": duration,
            "amount": amount
        }
        self._send(payload)
        # Returns contract_id asynchronously via callback
        return None
    
    def get_tick_history(self) -> List[Dict]:
        """Get recent tick history."""
        return self.tick_history.copy()
    
    def get_pending_contracts(self) -> Dict:
        """Get pending contracts."""
        with self._lock:
            return self._pending_contracts.copy()
