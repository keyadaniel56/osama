"""Reset ALL AI models to fresh state - run before restarting the bot.
This ensures the ML, RL, and all learned models start fresh with the new
intelligent configuration rather than carrying over stale biases."""
import json
import os

models_dir = os.path.join(os.path.dirname(__file__), 'models')

# Files to delete (stale models that should retrain)
files_to_delete = [
    'rl_model.pkl',           # RL model - had "never trade" bias
    'rf_model.pkl',           # Random Forest - retrain with new config
    'gb_model.pkl',           # Gradient Boosting - retrain with new config
    'scaler.pkl',             # Feature scaler - retrain with new config
    'ml_metadata.pkl',        # ML metadata - will be recreated
]

deleted_count = 0
for filename in files_to_delete:
    filepath = os.path.join(models_dir, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"✅ Deleted: {filename}")
        deleted_count += 1
    else:
        print(f"ℹ️  Not found: {filename}")

# Reset compounder data
compounder_path = os.path.join(models_dir, 'compounder_data.json')
if os.path.exists(compounder_path):
    with open(compounder_path, 'r') as f:
        compounder_data = json.load(f)
    
    initial_stake = compounder_data.get('initial_stake', 0.35)
    initial_equity = initial_stake * 100
    
    compounder_data['current_stake'] = initial_stake
    compounder_data['equity_peak'] = initial_equity
    compounder_data['last_growth_equity'] = initial_equity
    compounder_data['starting_equity'] = initial_equity
    compounder_data['current_equity'] = initial_equity
    compounder_data['wins'] = 0
    compounder_data['losses'] = 0
    compounder_data['trade_count'] = 0
    compounder_data['recent_win_rate'] = 0.5
    
    with open(compounder_path, 'w') as f:
        json.dump(compounder_data, f, indent=2)
    
    print(f"✅ Reset compounder to initial stake=${initial_stake}, equity=${initial_equity}")

print(f"\n🎯 Reset complete! Deleted {deleted_count} stale model files.")
print("   The bot will now learn fresh from current market conditions.")
print("   ML will train on actual price movements over the full contract duration.")
print("   RL will start with unbiased weights and epsilon=1.0 exploration.")