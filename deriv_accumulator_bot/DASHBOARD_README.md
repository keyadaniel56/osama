# Trading Bot Dashboard

Interactive web-based dashboard for monitoring your trading bot in real-time.

## Features

✅ **Real-time Performance Tracking**
- Live P&L chart
- Win rate and trade statistics
- Session balance monitoring

✅ **Active Trade Monitoring**
- Current trade details
- Entry score and metrics
- Live profit/loss updates

✅ **Market Conditions**
- All 5 markets monitored simultaneously
- Entry scores for each market
- Visual indicators (excellent/good/fair/poor)

✅ **Trade History**
- Recent trades table
- Timestamps and results
- Profit/loss per trade

✅ **Activity Logs**
- Real-time bot actions
- Entry/exit notifications
- Error and warning messages

## Quick Start

### Option 1: Run Bot with Dashboard (Recommended)

```bash
python multi_market_bot_with_dashboard.py
```

Then open your browser to: **http://localhost:8080**

### Option 2: Run Dashboard Separately

**Terminal 1 - Start Dashboard:**
```bash
python dashboard_server.py
```

**Terminal 2 - Run Bot:**
```bash
python multi_market_bot.py
```

Then open your browser to: **http://localhost:8080**

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│  🤖 Trading Bot Dashboard              [STATUS: RUNNING] │
├─────────────────────────────────────────────────────────┤
│  Balance    Session P&L   Total Trades   Win Rate       │
│  $10,000    +$45.60       156            92.3%          │
│  Wins       Losses                                       │
│  144        12                                           │
├──────────────────────────────┬──────────────────────────┤
│  Performance Chart           │  Active Trade            │
│  [Line chart showing P&L]    │  R_75 - OPEN             │
│                              │  Score: 68.5             │
│                              │  Stake: $20.00           │
│                              ├──────────────────────────┤
│  Recent Trades               │  Market Conditions       │
│  Time    Symbol  P&L  Result │  R_10  [Score: 45.2]    │
│  14:23   R_100  +$0.20  WIN  │  R_25  [Score: 62.8]    │
│  14:18   R_75   +$0.40  WIN  │  R_50  [Score: 38.1]    │
│  14:12   R_50   -$20.0  LOSS │  R_75  [Score: 71.3]    │
│                              │  R_100 [Score: 55.9]    │
│                              ├──────────────────────────┤
│                              │  Activity Logs           │
│                              │  [14:23] ✅ WIN on R_100 │
│                              │  [14:18] Entered R_75    │
└──────────────────────────────┴──────────────────────────┘
```

## Dashboard Updates

- **Auto-refresh:** Every 2 seconds
- **No manual refresh needed**
- **Real-time data** from bot

## Access from Other Devices

### On Same Network

1. Find your computer's IP address:
   ```bash
   # Linux/Mac
   ifconfig | grep "inet "
   
   # Or
   hostname -I
   ```

2. Open browser on other device:
   ```
   http://<your-ip>:8080
   ```
   
   Example: `http://192.168.1.100:8080`

### From Internet (Advanced)

Use a reverse proxy like ngrok:

```bash
# Install ngrok
# Then run:
ngrok http 8080
```

Access via the provided ngrok URL.

## Data Persistence

Dashboard data is saved to `dashboard_data.json`:
- Survives bot restarts
- Tracks historical performance
- Can be backed up

To reset data:
```bash
rm dashboard_data.json
```

## Troubleshooting

### Dashboard won't load

**Check if server is running:**
```bash
# Should see "Dashboard URL: http://localhost:8080"
```

**Try different port:**
Edit `multi_market_bot_with_dashboard.py`:
```python
run_dashboard(port=8081)  # Change from 8080
```

### Data not updating

**Check bot is running:**
- Status badge should show "RUNNING"
- Look for green pulsing indicator

**Refresh browser:**
- Press F5 or Ctrl+R

### Can't access from other devices

**Check firewall:**
```bash
# Linux - allow port 8080
sudo ufw allow 8080
```

**Verify IP address:**
```bash
# Make sure you're using correct IP
ip addr show
```

## Customization

### Change Update Frequency

Edit `dashboard.html` line ~450:
```javascript
setInterval(updateDashboard, 2000); // Change 2000 to 5000 for 5 seconds
```

### Change Port

Edit `multi_market_bot_with_dashboard.py`:
```python
run_dashboard(port=8080)  # Change to your preferred port
```

### Modify Colors/Theme

Edit `dashboard.html` CSS section (lines 10-200)

## Performance

- **Lightweight:** Uses minimal resources
- **No database required:** Data stored in JSON
- **Fast updates:** 2-second refresh cycle
- **Mobile friendly:** Responsive design

## Security Notes

⚠️ **Dashboard is NOT password protected**

- Only run on trusted networks
- Don't expose to public internet without authentication
- Your API token is NOT visible in dashboard
- Trade data is stored locally only

## Tips

1. **Keep dashboard open** while bot runs for best monitoring
2. **Check logs** for detailed bot activity
3. **Monitor win rate** - should stay above 80%
4. **Watch market scores** - higher is better (55+ for entry)
5. **Track session P&L** - set alerts if needed

## Requirements

- Python 3.8+
- No additional packages needed (uses built-in HTTP server)
- Modern web browser (Chrome, Firefox, Safari, Edge)

## Support

If dashboard isn't working:
1. Check Python version: `python --version`
2. Verify bot is running
3. Check console for errors
4. Try different browser
5. Restart both bot and dashboard

## Next Steps

- Run bot for 1 week with dashboard monitoring
- Track daily performance in dashboard
- Export `dashboard_data.json` for analysis
- Adjust strategy based on dashboard insights
