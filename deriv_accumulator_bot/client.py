"""
Deriv WebSocket client for Accumulator contracts.
Handles tick streaming, accumulator buying, and live P&L tracking.
"""

import json
import time
import threading
import websocket
from typing import Callable, Optional


DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3"


class DerivClient:
    def __init__(self, app_id: str, token: str, symbol: str = "R_10"):
        self.app_id = app_id
        self.token = token
        self.symbol = symbol
        self.ws = None
        self.connected = False
        self.authorized = False
        self._req_id = 1
        self._lock = threading.Lock()

        self.on_tick: Optional[Callable] = None
        self.on_contract_update: Optional[Callable] = None  # (status, profit, current_value)
        self.on_contract_sold: Optional[Callable] = None    # (profit,)
        self.on_buy_error: Optional[Callable] = None        # ()
        self.on_authorized: Optional[Callable] = None       # () - called when authorization succeeds

        self._active_contract_id: Optional[int] = None
        self._sell_requested = False

    def connect(self):
        url = f"{DERIV_WS_URL}?app_id={self.app_id}"
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        thread.start()
        timeout = 10
        while not self.connected and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5
        if not self.connected:
            raise ConnectionError("Failed to connect to Deriv WebSocket.")

    def _send(self, payload: dict):
        with self._lock:
            payload["req_id"] = self._req_id
            self._req_id += 1
        self.ws.send(json.dumps(payload))

    def _on_open(self, ws):
        self.connected = True
        print("[Client] Connected to Deriv WebSocket.")
        self._send({"authorize": self.token})

    def _on_message(self, ws, message: str):
        data = json.loads(message)
        msg_type = data.get("msg_type")

        if msg_type == "authorize":
            if "error" in data:
                print(f"[Client] Auth error: {data['error']['message']}")
            else:
                self.authorized = True
                account = data["authorize"]["loginid"]
                balance = data["authorize"]["balance"]
                print(f"[Client] Authorized as {account} | Balance: {balance} USD")
                self._subscribe_ticks()
                if self.on_authorized:
                    self.on_authorized()

        elif msg_type == "tick":
            tick = data["tick"]
            if self.on_tick:
                self.on_tick(float(tick["quote"]))

        elif msg_type == "buy":
            if "error" in data:
                print(f"[Client] Buy error: {data['error']['message']}")
                self._active_contract_id = None
                if self.on_buy_error:
                    self.on_buy_error()
            else:
                contract_id = data["buy"]["contract_id"]
                buy_price = data["buy"]["buy_price"]
                self._active_contract_id = contract_id
                self._sell_requested = False
                print(f"[Client] Accumulator started — ID: {contract_id} | Paid: ${buy_price:.2f}")
                # Subscribe to live updates
                self._send({
                    "proposal_open_contract": 1,
                    "contract_id": contract_id,
                    "subscribe": 1
                })

        elif msg_type == "proposal_open_contract":
            poc = data.get("proposal_open_contract", {})
            contract_id = poc.get("contract_id")
            is_sold = poc.get("is_sold") or poc.get("is_expired")
            profit = float(poc.get("profit", 0))
            current_value = float(poc.get("bid_price", 0))
            status = poc.get("status", "open")

            if self.on_contract_update and not is_sold:
                self.on_contract_update(status, profit, current_value)

            if is_sold and contract_id == self._active_contract_id:
                self._active_contract_id = None
                self._sell_requested = False
                print(f"[Client] Contract closed — Profit: ${profit:.4f} | Status: {status}")
                if self.on_contract_sold:
                    self.on_contract_sold(profit)

        elif msg_type == "sell":
            if "error" in data:
                print(f"[Client] Sell error: {data['error']['message']}")
            else:
                sold_for = data["sell"].get("sold_for", 0)
                print(f"[Client] Sell confirmed — Sold for: ${sold_for:.4f}")

    def _on_error(self, ws, error):
        print(f"[Client] WebSocket error: {error}")

    def _on_close(self, ws, code, msg):
        self.connected = False
        self.authorized = False
        print(f"[Client] Connection closed: {code} {msg}")

    def _subscribe_ticks(self):
        self._send({"ticks": self.symbol, "subscribe": 1})
        print(f"[Client] Subscribed to ticks: {self.symbol}")

    def buy_accumulator(self, stake: float, growth_rate: float):
        """
        Buy an accumulator contract.
        growth_rate: 0.01 = 1%, 0.02 = 2%, 0.03 = 3%, 0.04 = 4%, 0.05 = 5%
        """
        self._send({
            "buy": "1",
            "price": stake,
            "parameters": {
                "amount": stake,
                "basis": "stake",
                "contract_type": "ACCU",
                "currency": "USD",
                "symbol": self.symbol,
                "growth_rate": growth_rate,
            }
        })

    def sell_contract(self, force_retry: bool = False):
        """
        Sell the active accumulator contract to lock in profit.
        
        Args:
            force_retry: If True, allows retry even if sell was already requested.
                        Useful when previous sell attempt may have failed.
        """
        if self._active_contract_id:
            # Allow retry if forced, or if this is the first sell attempt
            if force_retry or not self._sell_requested:
                self._sell_requested = True
                print(f"[Client] Selling contract {self._active_contract_id}...")
                self._send({
                    "sell": self._active_contract_id,
                    "price": 0  # sell at market
                })

    @property
    def has_active_contract(self) -> bool:
        return self._active_contract_id is not None
