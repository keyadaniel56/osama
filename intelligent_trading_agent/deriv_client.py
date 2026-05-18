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
            
            # Log important messages only (not every tick)
            if msg_type != "tick":
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
        if "error" in data:
            agent_logger.log_error(f"Buy error: {data['error']['message']}")
            return
            
        contract = data.get("buy", {})
        contract_id = contract.get("contract_id")
        buy_price = contract.get("buy_price", 0)
        
        if contract_id:
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
    
    def _handle_contract_update(self, data: Dict):
        """Handle contract status updates."""
        contract = data.get("proposal_open_contract", {})
        contract_id = contract.get("contract_id")
        status = contract.get("status")
        
        if status == "sold" or status == "won" or status == "lost":
            sell_price = contract.get("sell_price", 0)
            profit = contract.get("profit", 0)
            
            agent_logger.log_info(f"Contract {contract_id} {status} - Sell: ${sell_price:.2f}, Profit: ${profit:.2f}")
            
            # Trigger callback with result
            if self.on_contract_result:
                self.on_contract_result({
                    'contract_id': contract_id,
                    'result': sell_price,
                    'profit': profit,
                    'status': status,
                    'timestamp': time.time()
                })
            
            # Clean up
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
        agent_logger.log_warning("WebSocket closed")
    
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
    
    def get_tick_history(self) -> List[Dict]:
        """Get recent tick history."""
        return self.tick_history.copy()
    
    def get_pending_contracts(self) -> Dict:
        """Get pending contracts."""
        with self._lock:
            return self._pending_contracts.copy()
