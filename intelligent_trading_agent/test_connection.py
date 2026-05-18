"""
Quick test to verify Deriv API connection.
"""

import time
from deriv_client import DerivClient
from config import DERIV_API_TOKEN, DERIV_APP_ID

def test_connection():
    print("Testing Deriv API connection...")
    
    client = DerivClient(DERIV_APP_ID, DERIV_API_TOKEN, "R_100")
    
    # Set up tick callback
    tick_count = 0
    def on_tick(tick_data):
        nonlocal tick_count
        tick_count += 1
        print(f"Tick #{tick_count}: {tick_data['symbol']} = {tick_data['quote']:.4f}")
    
    client.on_tick = on_tick
    
    # Connect
    try:
        client.connect()
        print("✓ Connected successfully!")
        print("✓ Authorized!")
        print("Receiving ticks... (Press Ctrl+C to stop)")
        
        # Wait for some ticks
        time.sleep(30)
        
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        client.disconnect()
        print(f"Received {tick_count} ticks total")

if __name__ == "__main__":
    test_connection()
