"""
Deriv API Client wrapper for the intelligent trading agent.
Reusable and robust API client for trading operations.

Authentication strategy:
1. Public WebSocket for market data (ticks, active_symbols, ticks_history) - no auth needed
2. For trading, try the new Deriv REST API with PAT token + Deriv-App-ID header
   (requires a registered app_id on the new Deriv API platform)

Note: app_id 1089 is the old binary.com app_id and is NOT registered on the new
Deriv API (api.derivws.com). To enable trading, you must:
  1. Go to https://app.deriv.com/account/api-token
  2. Register a new application to get a new app_id
  3. Update DERIV_APP_ID in your .env file
"""

import json
import time
import threading
import requests
import websocket
from typing import Callable, Optional, Dict, List
from logger import agent_logger


# WebSocket endpoints
DERIV_WS_PUBLIC = "wss://api.derivws.com/trading/v1/options/ws/public"
DERIV_WS_OLD = "wss://ws.binaryws.com/websockets/v3"

# REST API base
DERIV_REST_BASE = "https://api.derivws.com"


class DerivClient:
    """
    WebSocket client for Deriv trading platform.
    Handles: connection, authorization, tick streaming, contract execution.
    
    Uses the public WebSocket for market data (no auth required for ticks).
    For trading, attempts authentication via:
    1. New Deriv REST API (PAT token + Deriv-App-ID)
    2. Old binary.com WebSocket (authorize message)
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
        self._auth_method = None  # 'rest_otp', 'old_ws', or None for public-only
        
        # Reconnection settings
        self.should_reconnect = True
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        
        # Callbacks
        self.on_tick: Optional[Callable] = None
        self.on_buy_confirmed: Optional[Callable] = None  # Called when buy is confirmed with contract_id
        self.on_buy_failed: Optional[Callable] = None     # Called when buy fails
        self.on_contract_result: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Pending contracts tracking
        self._pending_contracts: Dict = {}
        self._lock = threading.Lock()
        
        # Proposal tracking (new Deriv API: proposal → buy two-step flow)
        self._pending_proposals: Dict[int, Dict] = {}  # req_id -> proposal info
        self._pending_buy_requests: Dict[int, Dict] = {}  # req_id -> buy info (for matching proposal to buy)
        
        # Tick history for analysis (per symbol)
        self.tick_history: Dict[str, List[Dict]] = {sym: [] for sym in self.symbols}
        self.max_history_size = 500
        
        # Tick counters (total ticks received, not limited by history size)
        self.tick_counters: Dict[str, int] = {sym: 0 for sym in self.symbols}
        
        # Tick health monitoring
        self.last_tick_time: Dict[str, float] = {sym: time.time() for sym in self.symbols}
        self.tick_timeout = 30  # seconds - if no tick for 30s, resubscribe
        self.subscription_ids: Dict[str, str] = {}  # symbol -> subscription_id for resubscription
    
    def _rest_get(self, path: str) -> Dict:
        """Make a REST GET request to the Deriv API with Bearer token auth."""
        url = f"{DERIV_REST_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Deriv-App-ID": self.app_id
        }
        agent_logger.log_info(f"REST GET {url}")
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    
    def _rest_post(self, path: str, data: Dict = None) -> Dict:
        """Make a REST POST request to the Deriv API with Bearer token auth."""
        url = f"{DERIV_REST_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Deriv-App-ID": self.app_id,
            "Content-Type": "application/json"
        }
        agent_logger.log_info(f"REST POST {url}")
        r = requests.post(url, headers=headers, json=data or {}, timeout=15)
        r.raise_for_status()
        return r.json()
    
    def _try_rest_auth(self) -> bool:
        """
        Try to authenticate using the new Deriv REST API.
        This requires a registered app_id on the new Deriv platform.
        
        Returns: True if authentication succeeded, False otherwise.
        """
        try:
            agent_logger.log_info("Trying REST API authentication (PAT token + Deriv-App-ID)...")
            response = self._rest_get("/trading/v1/options/accounts")
            
            # Actual API response: {"data": [{"account_id": "DOT93150502", ...}]}
            accounts = response.get("data", [])
            
            if not accounts:
                agent_logger.log_warning("REST API returned no accounts")
                return False
            
            account = accounts[0]
            account_id = account.get("account_id")
            agent_logger.log_info(f"REST API auth succeeded! Account: {account_id} ({account.get('account_type')})")
            
            # Get OTP URL for authenticated WebSocket
            # Actual API response: {"data": {"url": "wss://..."}}
            otp_response = self._rest_post(f"/trading/v1/options/accounts/{account_id}/otp")
            otp_data = otp_response.get("data", {})
            ws_url = otp_data.get("url", "")
            
            if ws_url:
                self._otp_url = ws_url
                self._auth_method = 'rest_otp'
                agent_logger.log_info(f"Got OTP WebSocket URL (demo account)")
                return True
            else:
                agent_logger.log_warning(f"No WebSocket URL in OTP response: {otp_response}")
                return False
                
        except requests.exceptions.HTTPError as e:
            agent_logger.log_warning(f"REST API auth failed: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            agent_logger.log_warning(f"REST API auth failed: {e}")
            return False
    
    def connect(self, max_retries: int = 3):
        """Connect to Deriv WebSocket for market data and optionally authenticate for trading.
        
        Args:
            max_retries: Number of connection retry attempts (default: 3)
        """
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    agent_logger.log_info(f"🔄 Connection attempt {attempt}/{max_retries}...")
                
                # Step 1: Try REST API authentication first (new Deriv API)
                rest_auth_success = self._try_rest_auth()
                
                if rest_auth_success and hasattr(self, '_otp_url') and self._otp_url:
                    # Connect via OTP URL (fully authenticated)
                    agent_logger.log_info("Connecting via OTP-authenticated WebSocket...")
                    self.ws = websocket.WebSocketApp(
                        self._otp_url,
                        on_open=self._on_open_otp,
                        on_message=self._on_message,
                        on_error=self._on_error_handler,
                        on_close=self._on_close,
                    )
                else:
                    # Fall back to public WebSocket for market data
                    agent_logger.log_info("Connecting to public WebSocket for market data...")
                    self.ws = websocket.WebSocketApp(
                        DERIV_WS_PUBLIC,
                        on_open=self._on_open_public,
                        on_message=self._on_message,
                        on_error=self._on_error_handler,
                        on_close=self._on_close,
                    )
                
                # Run in daemon thread
                thread = threading.Thread(target=self.ws.run_forever, daemon=True)
                thread.start()
                
                # Wait for connection (longer timeout)
                timeout = 20
                while not self.connected and timeout > 0:
                    time.sleep(0.5)
                    timeout -= 0.5
                
                if not self.connected:
                    raise ConnectionError("Failed to connect to Deriv WebSocket (timeout)")
                
                # Wait for authorization if using OTP
                if rest_auth_success:
                    auth_timeout = 10
                    while not self.authorized and auth_timeout > 0:
                        time.sleep(0.5)
                        auth_timeout -= 0.5
                    
                    if not self.authorized:
                        agent_logger.log_warning("OTP WebSocket connected but auth not confirmed")
                        self.authorized = True  # OTP URL is pre-authenticated
                
                agent_logger.log_info(f"Connected to Deriv: {self.symbol} (auth={self._auth_method or 'public'})")
                return  # Success - exit retry loop
                    
            except Exception as e:
                last_error = e
                agent_logger.log_warning(f"Connection attempt {attempt}/{max_retries} failed: {e}")
                
                # Clean up failed connection
                if self.ws:
                    try:
                        self.ws.close()
                    except:
                        pass
                    self.ws = None
                self.connected = False
                self.authorized = False
                
                if attempt < max_retries:
                    wait_time = attempt * 2  # Progressive backoff: 2, 4, 6 seconds
                    agent_logger.log_info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        
        # All retries exhausted
        agent_logger.log_error(f"Connection failed after {max_retries} attempts: {last_error}")
        raise ConnectionError(f"Failed to connect to Deriv WebSocket after {max_retries} attempts")
    
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
    
    def _on_open_public(self, ws):
        """WebSocket opened (public endpoint - no auth needed for market data)."""
        self.connected = True
        agent_logger.log_info("Public WebSocket connected (market data only)")
        # Subscribe to ticks immediately
        self._subscribe_ticks()
    
    def _on_open_otp(self, ws):
        """WebSocket opened (OTP-authenticated endpoint)."""
        self.connected = True
        self.authorized = True
        agent_logger.log_info("OTP-authenticated WebSocket connected")
        # Subscribe to ticks immediately
        self._subscribe_ticks()
    
    def _on_message(self, ws, message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            msg_type = data.get("msg_type")
            
            # Log ALL messages for debugging (including ticks)
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
            elif msg_type == "proposal":
                self._handle_proposal(data)
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
            error_msg = data['error']['message']
            agent_logger.log_error(f"Buy error: {error_msg}")
            # Notify agent that buy failed so it can clean up pending contracts
            if self.on_buy_failed:
                self.on_buy_failed({'error': error_msg})
            return
            
        contract = data.get("buy", {})
        contract_id = contract.get("contract_id")
        buy_price = contract.get("buy_price", 0)
        
        if contract_id:
            # Keep as integer for Deriv API compatibility (proposal_open_contract expects int)
            # But also store string version for dict key lookups
            contract_id_int = int(contract_id) if not isinstance(contract_id, int) else contract_id
            contract_id_str = str(contract_id_int)
            self._pending_contracts[contract_id_str] = {
                'type': 'buy',
                'time': time.time(),
                'buy_price': buy_price,
                'data': contract
            }
            agent_logger.log_info(f"Contract bought: {contract_id_str} - ${buy_price:.2f}")
            
            # Notify agent that buy was confirmed with the real contract_id
            if self.on_buy_confirmed:
                self.on_buy_confirmed({'contract_id': contract_id_str, 'buy_price': buy_price})
            
            # Subscribe to contract updates to get the result when it closes
            # Pass contract_id as integer for Deriv API compatibility
            self._subscribe_to_contract(contract_id_int)
        else:
            agent_logger.log_error(f"Buy response missing contract_id: {data}")
            if self.on_buy_failed:
                self.on_buy_failed({'error': 'Missing contract_id in buy response'})
    
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
            
            # Normalize profit to float to avoid format-string crash
            profit_float = 0.0
            try:
                profit_float = float(profit) if profit is not None else 0.0
            except (ValueError, TypeError):
                profit_float = 0.0
            
            if update_count % 30 == 0 or status not in ('open', ''):
                elapsed = time.time() - pending.get('time', time.time()) if pending else 0
                agent_logger.log_info(
                    f"Contract {contract_id}: status={status}, "
                    f"is_expired={is_expired}, is_sold={is_sold}, "
                    f"profit={profit_float:.2f}, elapsed={elapsed:.0f}s"
                )
        
        # Fire result when contract is closed — check ALL possible close indicators
        contract_closed = (
            status in ("sold", "won", "lost")
            or is_expired == 1
            or is_sold == 1
        )
        
        if contract_closed and contract_id:
            # Normalize both sell_price and profit to float for safe formatting
            sell_price_float = 0.0
            try:
                sell_price_float = float(sell_price) if sell_price is not None else 0.0
            except (ValueError, TypeError):
                sell_price_float = 0.0
            try:
                profit_float = float(profit) if profit is not None else 0.0
            except (ValueError, TypeError):
                profit_float = 0.0
            
            agent_logger.log_info(
                f"Contract {contract_id} CLOSED — status={status}, "
                f"sell_price=${sell_price_float:.2f}, profit=${profit_float:.2f}"
            )
            
            # Use normalized profit in the callback so agent.py doesn't crash
            profit = profit_float
            
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
    
    def _handle_proposal(self, data: Dict):
        """Handle proposal response (new Deriv API two-step flow)."""
        if "error" in data:
            error_msg = data['error']['message']
            agent_logger.log_error(f"Proposal error: {error_msg}")
            # Notify agent that buy failed (since proposal is step 1 of buy)
            if self.on_buy_failed:
                self.on_buy_failed({'error': f'Proposal failed: {error_msg}'})
            return
        
        proposal = data.get("proposal", {})
        # The Deriv API returns the proposal id inside the "proposal" object as "id"
        proposal_id = proposal.get("id") or data.get("proposal_id")
        req_id = data.get("req_id")
        ask_price = proposal.get("ask_price")
        
        if proposal_id:
            agent_logger.log_info(f"✅ Proposal received: id={proposal_id}, ask_price={ask_price}")
            
            # Check if we have a pending buy request waiting for this proposal
            if req_id and req_id in self._pending_buy_requests:
                buy_info = self._pending_buy_requests.pop(req_id)
                # Now execute the buy with the proposal_id and the actual ask_price
                self._execute_buy_with_proposal(proposal_id, buy_info, ask_price)
            else:
                # Store proposal for later use
                self._pending_proposals[proposal_id] = {
                    'time': time.time(),
                    'data': proposal,
                    'ask_price': ask_price
                }
                agent_logger.log_info(f"📝 Stored proposal {proposal_id} for later use (ask_price={ask_price})")
        else:
            agent_logger.log_error(f"Proposal response missing proposal_id: {data}")
            if self.on_buy_failed:
                self.on_buy_failed({'error': 'Missing proposal_id in proposal response'})
    
    def _execute_buy_with_proposal(self, proposal_id: int, buy_info: Dict, ask_price: float = None):
        """
        Execute a buy contract.
        
        The OTP-authenticated WebSocket uses the old binary.com format:
        {
            "buy": "1",
            "price": "<actual_contract_cost>",
            "parameters": {
                "amount": <stake>,
                "basis": "stake",
                "contract_type": "CALL"/"PUT",
                "currency": "USD",
                "duration": <value>,
                "duration_unit": "m"/"s"/"h"/"t",
                "underlying_symbol": "R_100"
            }
        }
        
        IMPORTANT: price must be the ask_price from the proposal, NOT the stake amount.
        The proposal_id is NOT used in this format - instead the full parameters are passed.
        """
        agent_logger.log_info(f"🔄 Executing buy with proposal_id={proposal_id}, ask_price={ask_price}")
        
        # Use ask_price from proposal if available, otherwise fall back to amount
        if ask_price is not None:
            price = str(ask_price)
        else:
            price = str(buy_info['amount'])
            agent_logger.log_warning(f"⚠️ No ask_price from proposal, using amount as price: {price}")
        
        if self._auth_method == 'rest_otp':
            # OTP-authenticated WebSocket uses "parameters" object format
            payload = {
                "buy": "1",
                "price": price,
                "parameters": {
                    "amount": buy_info['amount'],
                    "basis": "stake",
                    "contract_type": buy_info['contract_type'],
                    "currency": buy_info['currency'],
                    "duration": buy_info['duration'],
                    "duration_unit": buy_info['duration_unit'],
                    "underlying_symbol": buy_info['symbol'],
                }
            }
        else:
            # Old binary.com WebSocket (ws.binaryws.com) uses proposal_id format
            payload = {
                "buy": "1",
                "price": price,
                "proposal_id": proposal_id
            }
        
        agent_logger.log_info(f"📤 Sending buy request: {payload}")
        self._send(payload)
    
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
        Buy a contract using the new Deriv API two-step flow:
        1. Send a proposal to get a price quote
        2. When proposal response arrives, execute the buy with proposal_id
        
        Args:
            symbol: Trading symbol (e.g., "R_100")
            contract_type: Contract type (e.g., "CALL", "PUT")
            duration: Duration value
            duration_unit: Duration unit - "s" (seconds), "m" (minutes), "h" (hours), "t" (ticks)
            amount: Stake amount
            currency: Currency code (default: "USD")
            
        Returns: None (contract_id comes back asynchronously via callback)
        """
        if not self.authorized:
            agent_logger.log_error("Cannot buy contract: not authorized (public WebSocket mode)")
            agent_logger.log_error("To enable trading, register a new app at https://app.deriv.com/account/api-token")
            agent_logger.log_error("and update DERIV_APP_ID in your .env file with the new app_id")
            if self.on_error:
                self.on_error("Cannot trade: not authorized. Register a new app on Deriv and update DERIV_APP_ID")
            return None
        
        # Step 1: Send a proposal to get a price quote
        # The Deriv API requires a two-step flow:
        # proposal → get proposal_id → buy with proposal_id
        #
        # IMPORTANT: The OTP-authenticated WebSocket uses "underlying_symbol"
        # (NOT "symbol" or "underlying") to specify the trading symbol.
        # The old binary.com API used "symbol" but the new API rejects it.
        #
        # Duration must be flat fields (duration + duration_unit), NOT an object.
        if self._auth_method == 'rest_otp':
            # OTP-authenticated WebSocket uses "underlying_symbol"
            proposal_payload = {
                "proposal": 1,
                "amount": amount,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": currency,
                "duration": duration,
                "duration_unit": duration_unit,
                "underlying_symbol": symbol,
            }
        else:
            # Old binary.com WebSocket (ws.binaryws.com) uses flat format
            proposal_payload = {
                "proposal": 1,
                "amount": amount,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": currency,
                "duration": duration,
                "duration_unit": duration_unit,
                "symbol": symbol,
            }
        
        # Store buy info so _handle_proposal can execute the buy when proposal arrives
        sent_payload = self._send(proposal_payload)
        if sent_payload:
            req_id = sent_payload.get("req_id")
            if req_id:
                self._pending_buy_requests[req_id] = {
                    'amount': amount,
                    'symbol': symbol,
                    'contract_type': contract_type,
                    'duration': duration,
                    'duration_unit': duration_unit,
                    'currency': currency
                }
        
        agent_logger.log_info(f"Proposal sent: {contract_type} on {symbol} for ${amount} {currency} - {duration}{duration_unit}")
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
    
    def unsubscribe_from_symbol(self, symbol: str):
        """
        Unsubscribe from tick stream for a specific symbol.
        Used after initial market selection to stop receiving ticks
        for non-selected markets.
        """
        if symbol in self.subscription_ids:
            self._send({
                "forget": self.subscription_ids[symbol]
            })
            agent_logger.log_info(f"🔕 Unsubscribed from ticks: {symbol}")
            del self.subscription_ids[symbol]
        else:
            # Try to unsubscribe without subscription ID
            self._send({
                "forget_all": "ticks"
            })
            agent_logger.log_info(f"🔕 Unsubscribed from all ticks (no subscription ID for {symbol})")
            # Re-subscribe only to the current symbol
            self._send({
                "ticks": self.symbol,
                "subscribe": 1
            })
            agent_logger.log_info(f"✅ Re-subscribed to ticks for current symbol: {self.symbol}")
