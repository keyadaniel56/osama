"""
Deriv WebSocket API client for Rise/Fall contracts.
Handles tick streaming, contract buying with minute durations, and result tracking.
"""

import json
import time
import threading
import websocket
from typing import Callable


DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3"


class DerivClient:
    def __init__(self, app_id: str, token: str, symbol: str = "R_100"):
        self.app_id = app_id
        self.token = token
        self.symbol = symbol
        self.ws = None
        self.connected = False
        self.authorized = False
        self._req_id = 1
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5

        self.on_tick: Callable | None = None
        self.on_contract_result: Callable | None = None

        self._pending_contracts: dict = {}
        self._lock = threading.Lock()

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
        self._reconnect_attempts = 0  # Reset on successful connection
        print(f"✅ Connected to Deriv WebSocket")
        self._authorize()

    def _authorize(self):
        self._send({"authorize": self.token})

    def _on_message(self, ws, message: str):
        data = json.loads(message)
        msg_type = data.get("msg_type")

        if msg_type == "authorize":
            if "error" in data:
                print(f"❌ Auth error: {data['error']['message']}")
            else:
                self.authorized = True
                account_id = data['authorize']['loginid']
                print(f"✅ Authorized: {account_id} | Symbol: {self.symbol}")
                self._subscribe_ticks()

        elif msg_type == "tick":
            tick = data["tick"]
            if self.on_tick:
                self.on_tick(float(tick["quote"]))

        elif msg_type == "buy":
            if "error" in data:
                print(f"❌ Buy error: {data['error']['message']}")
            else:
                contract_id = data["buy"]["contract_id"]
                req_id = data.get("req_id")
                print(f"✅ Contract bought: {contract_id}")
                self._pending_contracts[contract_id] = req_id
                self._send({"proposal_open_contract": 1, "contract_id": contract_id, "subscribe": 1})

        elif msg_type == "proposal_open_contract":
            poc = data.get("proposal_open_contract", {})
            contract_id = poc.get("contract_id")
            is_sold = poc.get("is_sold") or poc.get("is_expired")
            if is_sold and contract_id in self._pending_contracts:
                profit = float(poc.get("profit", 0))
                status = poc.get("status")
                if not status:
                    status = "won" if profit >= 0 else "lost"
                if self.on_contract_result:
                    self.on_contract_result(status, profit)
                self._pending_contracts.pop(contract_id, None)

    def _on_error(self, ws, error):
        print(f"[Deriv] WebSocket error: {error}")

    def _on_close(self, ws, code, msg):
        self.connected = False
        self.authorized = False
        print(f"[Deriv] Connection closed: {code} {msg}")
        
        # Auto-reconnect
        if self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_attempts += 1
            print(f"[Deriv] Reconnecting... (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")
            time.sleep(2)
            self.connect()
        else:
            print(f"[Deriv] Max reconnection attempts reached. Please restart the bot.")

    def _subscribe_ticks(self):
        self._send({"ticks": self.symbol, "subscribe": 1})
        print(f"[Deriv] Subscribed to ticks: {self.symbol}")

    def buy_contract(self, contract_type: str, stake: float, duration_minutes: int = 1):
        """
        Buy Rise/Fall contract with minute duration.
        contract_type: "CALL" (Rise) or "PUT" (Fall)
        duration_minutes: Duration in minutes (1-60)
        """
        self._send({
            "buy": "1",
            "price": stake,
            "parameters": {
                "amount": stake,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": "USD",
                "duration": duration_minutes,
                "duration_unit": "m",  # 'm' for minutes
                "symbol": self.symbol,
            }
        })
