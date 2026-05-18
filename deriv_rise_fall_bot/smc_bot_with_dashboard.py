"""
Smart Money Concepts (SMC) Trading Bot with Built-in Dashboard
All-in-one: Bot + Web Dashboard on http://localhost:5000
"""

import time
import os
import json
import threading
from dotenv import load_dotenv
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

from deriv_client import DerivClient
from smc_analysis import SMCAnalyzer
from strategy import Strategy

load_dotenv()

# Configuration
API_TOKEN = os.getenv("DERIV_API_TOKEN", "")
APP_ID = os.getenv("DERIV_APP_ID", "1089")
SYMBOL = os.getenv("SYMBOL", "R_100")
STAKE = float(os.getenv("STAKE", "0.50"))
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "5"))
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", "20.0"))
STOP_LOSS = float(os.getenv("STOP_LOSS", "10.0"))

# Martingale
ENABLE_MARTINGALE = 