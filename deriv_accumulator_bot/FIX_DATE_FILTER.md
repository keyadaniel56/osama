# Date Filter Fix Guide

## Changes Made

### 1. Fixed File Path Issues
- Changed history file path from `deriv_accumulator_bot/trade_history.json` to `trade_history.json`
- Dashboard server now checks both paths
- Added better error handling

### 2. Added Debugging
- Console logging in browser (press F12 to see)
- Server-side logging for API requests
- Better error messages

### 3. Added Reset Button
- New "Reset" button to clear filter
- Returns to live data view

## How to Test

### Step 1: Check Trade History File
```bash
cd deriv_accumulator_bot
python check_history.py
```

This will show:
- If history file exists
- How many trades are stored
- Date range of trades
- Overall statistics

### Step 2: Restart the Bot
```bash
# Stop current bot (Ctrl+C)
python multi_market_bot_with_dashboard.py
```

### Step 3: Test Date Filter

1. **Open Dashboard**: http://localhost:8080

2. **Open Browser Console**: Press F12 (or Cmd+Option+I on Mac)

3. **Select Dates**:
   - Start date: Pick a date with trades
   - End date: Today or later

4. **Click Filter Button**

5. **Check Console**: You should see:
   ```
   Filtering from 2024-XX-XX to 2024-XX-XX
   Filter response: 200
   Filtered data: {object with filtered trades}
   ```

6. **Check Server Terminal**: You should see:
   ```
   [Dashboard] API request - start: 2024-XX-XX, end: 2024-XX-XX
   [Dashboard] Filtering data from 2024-XX-XX to 2024-XX-XX
   [Dashboard] Loaded X trades from history
   ```

### Step 4: Test Reset
Click the "Reset" button to return to live data

## Troubleshooting

### If Filter Still Doesn't Work

#### Check 1: History File Location
```bash
# From deriv_accumulator_bot directory
ls -la trade_history.json

# If not found, check parent directory
cd ..
ls -la trade_history.json
```

#### Check 2: Browser Console Errors
1. Press F12
2. Go to Console tab
3. Click Filter button
4. Look for red error messages

#### Check 3: Server Logs
Look at the terminal where bot is running for error messages

#### Check 4: File Permissions
```bash
# Make sure file is readable
chmod 644 trade_history.json
```

### Common Issues

**Issue**: "History file not found"
**Fix**: 
```bash
# Create empty history file
echo "[]" > trade_history.json
```

**Issue**: "Error parsing dates"
**Fix**: Make sure dates are in YYYY-MM-DD format

**Issue**: "No trades shown after filter"
**Fix**: 
- Check date range includes actual trades
- Use check_history.py to see date range
- Try wider date range

## Manual Test

If automated filter doesn't work, you can manually check the API:

```bash
# Get current data
curl http://localhost:8080/api/data

# Get filtered data
curl "http://localhost:8080/api/data?start=2024-01-01&end=2024-12-31"
```

## Expected Behavior

### Before Filter
- Shows live session data
- Updates every 2 seconds
- Shows active trade if any
- Shows current market conditions

### After Filter
- Shows historical data for date range
- No live updates
- No active trade shown
- No market conditions shown
- Performance chart shows filtered period

### After Reset
- Returns to live data
- Resumes 2-second updates
- Shows current active trade
- Shows current market conditions

## Debug Mode

To see detailed logging, modify dashboard_server.py:

```python
# Add at top of get_filtered_data method
print(f"[DEBUG] Filtering from {start_date} to {end_date}")
print(f"[DEBUG] History file: {history_file}")
print(f"[DEBUG] File exists: {os.path.exists(history_file)}")
```

## Contact Points

If filter still doesn't work after these fixes:

1. Run `check_history.py` and share output
2. Check browser console (F12) for errors
3. Check server terminal for error messages
4. Verify trade_history.json exists and has data

The filter should now work correctly with better error handling and debugging!
