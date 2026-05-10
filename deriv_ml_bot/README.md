# Deriv ML Trading Bot

A machine learning bot for Deriv digit over/under trading with hidden pattern detection and automatic loss recovery.

## Strategy

- Normal mode: OVER 1 / UNDER 8
- Recovery mode: OVER 3 / UNDER 6 (auto-switches after a loss, reverts after 2 consecutive wins)

## ML Features (hidden patterns)

The bot does NOT rely on simple tick percentages. Instead it extracts:

- Short/medium/long momentum
- Volatility clustering (GARCH-like proxy)
- Autocorrelation at multiple lags (serial dependency)
- Shannon entropy (randomness measure)
- Streak/run-length detection
- Price position within recent range
- Mean reversion z-score
- Tick direction imbalance
- Skewness and kurtosis of returns
- Hurst exponent (long-memory / trend persistence)

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

   - `DERIV_API_TOKEN`: Get from https://app.deriv.com/account/api-token
   - `DERIV_APP_ID`: Use `1089` for demo or register your own at https://developers.deriv.com
   - `SYMBOL`: e.g. `R_100`, `R_50`, `R_75`, `R_25`, `R_10`
   - `STAKE`: Amount per trade in USD

3. Run the bot:
   ```bash
   cd deriv_ml_bot
   python bot.py
   ```

## Notes

- The model starts with a heuristic fallback and trains itself as it collects data (needs ~200 samples before ML kicks in).
- Model is saved to `model.pkl` and reloaded on restart.
- The bot retrains every 50 new labeled samples.
- Set `MIN_CONFIDENCE` in `bot.py` to control trade selectivity (0.55 = only trade when 55%+ confident).

## Risk Warning

Trading involves risk. Use a demo account first. Never trade with money you cannot afford to lose.
