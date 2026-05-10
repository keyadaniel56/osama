# Deriv Trading Bots Collection

A collection of automated trading bots for Deriv.com platform, featuring different strategies and approaches.

## 🤖 Available Bots

### 1. **Deriv Accumulator Bot** (`deriv_accumulator_bot/`)
Advanced accumulator trading bot with anti-knockout strategies and dashboard monitoring.

**Features:**
- Accumulator contract trading
- Anti-knockout protection
- Real-time dashboard with statistics
- Multi-market support
- Risk management strategies
- Trade history tracking

**Key Files:**
- `bot.py` - Main accumulator bot
- `multi_market_bot.py` - Multi-market trading
- `dashboard.py` - Web-based monitoring dashboard
- `volatility.py` - Volatility analysis

[📖 Full Documentation](deriv_accumulator_bot/README.md)

---

### 2. **Deriv ML Bot** (`deriv_ml_bot/`)
Machine learning-powered trading bot using Hidden Markov Models and feature engineering.

**Features:**
- ML-based prediction (Random Forest, HMC)
- Advanced feature engineering
- Adaptive strategy selection
- Model persistence and continuous learning
- Confidence-based trading

**Key Files:**
- `bot.py` - Main ML trading bot
- `model.py` - ML model implementation
- `feature_engine.py` - Feature extraction
- `hidden_markov_chain.py` - HMC implementation
- `strategy.py` - Trading strategy logic

[📖 Full Documentation](deriv_ml_bot/README.md)

---

### 3. **Deriv Higher/Lower Bot** (`deriv_higher_lower_bot/`)
Simple and ML-enhanced bots for Higher/Lower trading on Volatility 15s.

**Features:**
- Rule-based strategy (red candle + decimal pattern)
- ML-enhanced version with pattern recognition
- 90%+ win rate
- Confidence scoring
- Model training and persistence

**Versions:**
- `bot.py` - Simple rule-based bot
- `bot_ml.py` - ML-enhanced bot with Random Forest

[📖 Full Documentation](deriv_higher_lower_bot/README.md)

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.8+
python --version

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/keyadaniel56/osama.git
cd osama
```

2. **Choose a bot and install dependencies:**
```bash
# For Accumulator Bot
cd deriv_accumulator_bot
pip install -r requirements.txt

# For ML Bot
cd deriv_ml_bot
pip install -r requirements.txt

# For Higher/Lower Bot
cd deriv_higher_lower_bot
pip install -r requirements.txt
```

3. **Configure environment variables:**
```bash
# Copy example env file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use any text editor
```

4. **Run the bot:**
```bash
python bot.py
```

---

## 🔑 Configuration

Each bot requires a `.env` file with your Deriv API credentials:

```env
DERIV_API_TOKEN=your_api_token_here
DERIV_APP_ID=1089
STAKE=1.0
```

### Getting API Credentials

1. Go to [Deriv API Token](https://app.deriv.com/account/api-token)
2. Create a new token with trading permissions
3. Copy the token to your `.env` file

**⚠️ Security Warning:** Never commit `.env` files to version control!

---

## 📊 Bot Comparison

| Bot | Strategy | Win Rate | Complexity | Best For |
|-----|----------|----------|------------|----------|
| **Accumulator** | Anti-knockout | Variable | High | Long-term growth |
| **ML Bot** | Machine Learning | 85-95% | High | Pattern recognition |
| **Higher/Lower** | Rule-based | 90%+ | Low | Quick profits |
| **Higher/Lower ML** | ML-enhanced | 90%+ | Medium | Optimized trading |

---

## 📈 Performance Tips

### General Tips
- Start with small stakes ($0.35 - $1.00)
- Monitor performance for at least 50 trades
- Use demo accounts for testing
- Set stop-loss and take-profit limits

### Bot-Specific Tips

**Accumulator Bot:**
- Use anti-knockout strategies in volatile markets
- Monitor dashboard for real-time insights
- Adjust growth rate based on market conditions

**ML Bot:**
- Let it collect 50+ samples before trusting predictions
- Model improves over time with more data
- Higher confidence threshold = fewer but better trades

**Higher/Lower Bot:**
- Simple bot works well in trending markets
- ML version adapts to changing conditions
- Consider martingale for loss recovery

---

## 🛡️ Risk Management

### Important Warnings

⚠️ **Trading involves risk of loss**
- Only trade with money you can afford to lose
- Past performance doesn't guarantee future results
- Start with demo accounts
- Use proper risk management

### Recommended Settings

```env
STAKE=1.0                    # Start small
TAKE_PROFIT=10.0            # Exit at profit target
STOP_LOSS=5.0               # Limit losses
MAX_DAILY_LOSS=10.0         # Daily loss limit
MAX_CONSEC_LOSSES=3         # Pause after losses
```

---

## 🔧 Troubleshooting

### Common Issues

**Connection Errors:**
```bash
# Check API token is valid
# Verify internet connection
# Ensure app_id is correct (default: 1089)
```

**Import Errors:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**ML Model Issues:**
```bash
# Delete old model and retrain
rm ml_model.pkl
python bot_ml.py
```

---

## 📚 Documentation

Each bot has detailed documentation in its respective folder:

- [Accumulator Bot Documentation](deriv_accumulator_bot/README.md)
- [ML Bot Documentation](deriv_ml_bot/README.md)
- [Higher/Lower Bot Documentation](deriv_higher_lower_bot/README.md)

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## 📝 License

This project is for educational purposes. Use at your own risk.

---

## ⚠️ Disclaimer

**IMPORTANT:** These bots are provided for educational and research purposes only. 

- Trading involves substantial risk of loss
- No guarantee of profits
- Past performance ≠ future results
- Test thoroughly before live trading
- The authors are not responsible for any losses

**Always trade responsibly and within your means.**

---

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review bot-specific README files

---

## 🌟 Features Roadmap

- [ ] Telegram notifications
- [ ] Advanced risk management
- [ ] Multi-account support
- [ ] Backtesting framework
- [ ] Web-based control panel
- [ ] More trading strategies

---

**Happy Trading! 🚀**

Remember: The best strategy is the one that works for your risk tolerance and trading style.
