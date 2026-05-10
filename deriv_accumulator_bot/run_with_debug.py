"""
Run bot with detailed debug logging to see rejection reasons
"""

import sys
import os

# Add verbose logging
os.environ['BOT_DEBUG'] = '1'

# Import and run
from multi_market_bot_with_dashboard import main

if __name__ == '__main__':
    print("\n" + "="*70)
    print("   DEBUG MODE - Detailed rejection reasons will be shown")
    print("="*70 + "\n")
    main()
