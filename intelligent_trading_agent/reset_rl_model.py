"""Reset RL model to fresh state - run before restarting the bot."""
import pickle
import numpy as np
import json
import os

models_dir = os.path.join(os.path.dirname(__file__), 'models')

# 1. Delete old RL model so it starts fresh
model_path = os.path.join(models_dir, 'rl_model.pkl')
if os.path.exists(model_path):
    os.remove(model_path)
    print(f"✅ Deleted old RL model: {model_path}")
else:
    print("ℹ️ No RL model file found")

# 2. Reset compounder data
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
else:
    print("ℹ️ No compounder file found")

print("🎯 RL model reset complete. Start fresh!")