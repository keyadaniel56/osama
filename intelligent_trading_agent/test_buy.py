"""
Test buying a contract to verify API format.
"""

import time
import json
from deriv_client import DerivClient
from config import DERIV_API_TOKEN, DERIV_APP_ID

def test_buy():
    print("Testing contract purchase...")
    
    client = DerivClient(DERIV_APP_ID, DERIV_API_TOKEN, "R_100")
    
    # Track messages
    messages = []
    
    def on_tick(tick_data):
        print(f"Tick: {tick_data['quote']:.4f}")
    
    def on_error(error):
        print(f"ERROR: {error}")
        messages.append(('error', error))
    
    client.on_tick = on_tick
    client.on_error = on_error
    
    try:
        client.connect()
        print("✓ Connected and authorized")
        
        # Wait for a few ticks
        time.sleep(3)
        
        # Try to buy a contract
        print("\nAttempting to buy CALL contract...")
        client.buy_contract(
            symbol="R_100",
            contract_type="CALL",
            duration=5,
            amount=1.0
        )
        
        # Wait for response
        print("Waiting for buy response...")
        time.sleep(10)
        
        print("\nPending contracts:", client.get_pending_contracts())
        
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
