"""
Test buying a contract to verify API format.
Tries multiple payload formats to find the correct one.
"""

import time
import json
from deriv_client import DerivClient
from config import DERIV_API_TOKEN, DERIV_APP_ID

def test_buy():
    print("Testing contract purchase with different payload formats...")
    
    client = DerivClient(DERIV_APP_ID, DERIV_API_TOKEN, "R_100")
    
    # Track messages
    messages = []
    test_results = []
    
    def on_tick(tick_data):
        pass  # Don't print ticks
    
    def on_error(error):
        print(f"ERROR: {error}")
        messages.append(('error', error))
    
    client.on_tick = on_tick
    client.on_error = on_error
    
    try:
        client.connect()
        print("✓ Connected and authorized")
        
        # Wait for connection and ticks
        time.sleep(3)
        
        # Try different payload formats
        formats = [
            # Format 1: Duration as object (duration: {amount, unit})
            {
                "buy": "1",
                "price": 1.0,
                "parameters": {
                    "contract_type": "CALL",
                    "symbol": "R_100",
                    "duration": {"amount": 5, "unit": "m"},
                    "basis": "stake",
                    "amount": 1.0,
                    "currency": "USD"
                }
            },
            # Format 2: buy as int, duration as object
            {
                "buy": 1,
                "price": 1.0,
                "parameters": {
                    "contract_type": "CALL",
                    "symbol": "R_100",
                    "duration": {"amount": 5, "unit": "m"},
                    "basis": "stake",
                    "amount": 1.0,
                    "currency": "USD"
                }
            },
            # Format 3: Old binary.com API (ws.binaryws.com) format
            {
                "buy": "1",
                "price": 1.0,
                "parameters": {
                    "amount": 1.0,
                    "basis": "stake",
                    "contract_type": "CALL",
                    "currency": "USD",
                    "duration": 5,
                    "duration_unit": "m",
                    "symbol": "R_100"
                }
            },
            # Format 4: Using proposal first then buy - just buy with proposal=1
            {"proposal": 1, "amount": 1.0, "basis": "stake", "contract_type": "CALL",
             "currency": "USD", "duration": 5, "duration_unit": "m", "symbol": "R_100"},
            # Format 5: Flat with buy=1, no price, no parameters
            {
                "buy": 1,
                "price": 1.0,
                "contract_type": "CALL",
                "symbol": "R_100",
                "duration": 5,
                "duration_unit": "m",
                "basis": "stake",
                "amount": 1.0,
                "currency": "USD"
            },
            # Format 6: buy as string, flat
            {
                "buy": "1",
                "price": 1.0,
                "contract_type": "CALL",
                "symbol": "R_100",
                "duration": 5,
                "duration_unit": "m",
                "basis": "stake",
                "amount": 1.0,
                "currency": "USD"
            },
            # Format 7: proposal approach - get price first then buy
            # Just try buy with proposal fields
            {
                "buy": "1",
                "price": 1.5,
                "proposal_id": 1,
            },
            # Format 8: Duration units as "t" (ticks) instead of "m" (minutes)
            {
                "buy": "1",
                "price": 1.0,
                "parameters": {
                    "contract_type": "CALL",
                    "symbol": "R_100",
                    "duration": 5,
                    "duration_unit": "t",
                    "basis": "stake",
                    "amount": 1.0,
                    "currency": "USD"
                }
            },
        ]
        
        for i, fmt in enumerate(formats):
            print(f"\n{'='*60}")
            print(f"Trying format #{i+1}:")
            print(f"  Payload: {json.dumps(fmt, indent=4)}")
            
            # Send the payload directly
            client._send(fmt)
            print(f"  Sent! Waiting for response...")
            time.sleep(3)
            
            # Check if we got any error responses
            while messages:
                msg_type, msg = messages.pop(0)
                if 'Input validation' in msg:
                    print(f"  ✗ FAILED: {msg}")
                    test_results.append((i+1, False, msg))
                else:
                    test_results.append((i+1, "other", msg))
        
        print(f"\n{'='*60}")
        print("TEST RESULTS:")
        for fmt_num, success, msg in test_results:
            status = "✓ OK" if success else "✗ FAIL"
            print(f"  Format #{fmt_num}: {status} - {msg}")
        
        print(f"\nPending contracts: {client.get_pending_contracts()}")
        
        # Wait a bit more for any async responses
        time.sleep(10)
        print(f"\nPending contracts after wait: {client.get_pending_contracts()}")
        
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.disconnect()

if __name__ == "__main__":
    test_buy()