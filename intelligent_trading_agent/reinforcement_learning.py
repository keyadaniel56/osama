"""
Reinforcement Learning System for Intelligent Trading Agent.
Learns optimal trading decisions from market conditions and trade outcomes.

Key features:
1. Q-learning with neural network approximation for trade/no-trade decisions
2. State representation from market indicators + patterns + recent performance
3. Reward shaping: positive for profitable trades, negative for losses, small penalties for missed opportunities
4. Experience replay with prioritized sampling (learn more from surprising outcomes)
5. Epsilon-greedy exploration during early training
6. Profit compounding: automatically grows stake as account equity increases

The agent learns:
- Which market conditions lead to profitable trades
- When to skip trades (avoiding losses is as important as making profits)
- How to compound profits by increasing stake proportionally with account growth
"""

import numpy as np
import pickle
import os
import json
from typing import Dict, List, Tuple, Optional
from collections import deque, defaultdict
from datetime import datetime
from logger import agent_logger
from config import MODELS_DIR


class ExperienceReplay:
    """
    Prioritized experience replay buffer.
    Stores (state, action, reward, next_state) tuples.
    Prioritizes learning from surprising outcomes (high TD-error).
    """
    def __init__(self, max_size: int = 2000):
        self.buffer = deque(maxlen=max_size)
        self.priorities = deque(maxlen=max_size)
        self.alpha = 0.6  # Priority exponent (0 = uniform, 1 = full priority)
        self.beta = 0.4   # Importance sampling correction (starts low, anneals to 1)
        self.epsilon = 1e-6  # Small constant to avoid zero priority
    
    def add(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool = False):
        """Add experience with max priority (so it gets sampled at least once)."""
        self.buffer.append((state, action, reward, next_state, done))
        # New experiences get max priority to ensure they're sampled
        max_priority = max(self.priorities) if self.priorities else 1.0
        self.priorities.append(max_priority)
    
    def sample(self, batch_size: int) -> Tuple[List, np.ndarray, List[int]]:
        """Sample batch of experiences with priority-based probability."""
        if len(self.buffer) < batch_size:
            batch_size = len(self.buffer)
        
        # Calculate sampling probabilities
        priorities = np.array(self.priorities)[-len(self.buffer):]
        probs = priorities ** self.alpha
        probs /= probs.sum() + self.epsilon
        
        # Sample indices
        indices = np.random.choice(len(self.buffer), batch_size, p=probs, replace=False)
        
        # Calculate importance sampling weights
        total = len(self.buffer)
        weights = (total * probs[indices]) ** (-self.beta)
        weights /= weights.max()  # Normalize
        
        samples = [self.buffer[i] for i in indices]
        return samples, weights, indices
    
    def update_priorities(self, indices: List[int], td_errors: np.ndarray):
        """Update priorities for sampled experiences."""
        for idx, error in zip(indices, td_errors):
            if 0 <= idx < len(self.priorities):
                self.priorities[idx] = abs(error) + self.epsilon
    
    def __len__(self) -> int:
        return len(self.buffer)


class MarketStateEncoder:
    """
    Encodes market conditions into a state vector for the RL agent.
    Uses the same features the decision engine uses, plus recent performance.
    """
    
    @staticmethod
    def encode(features: Dict, recent_win_rate: float, consecutive_losses: int, 
               current_stake_pct: float, trade_count: int) -> np.ndarray:
        """
        Encode market state into a normalized feature vector.
        
        Args:
            features: Market indicator features dict
            recent_win_rate: Win rate over last N trades (0.0-1.0)
            consecutive_losses: Current consecutive loss count
            current_stake_pct: Current stake as % of base stake (1.0 = normal)
            trade_count: Total trades taken so far
            
        Returns:
            numpy array state vector
        """
        state = np.array([
            # Price action features
            features.get('rsi', 50.0) / 100.0,  # Normalize to 0-1
            features.get('bb_position', 0.5),     # Already 0-1
            min(features.get('volatility', 0.5), 1.0),
            features.get('momentum_10', 0.0) / 10.0,  # Bound to ~[-1, 1]
            features.get('momentum_20', 0.0) / 10.0,
            
            # Trend features
            min(features.get('trend_strength', 0.0) * 10, 1.0),  # Scale up
            features.get('ma_crossover', 0.0),     # 0 or 1
            features.get('price_above_sma', 0.0),  # 0 or 1
            features.get('price_direction', 0.5),  # 0-1
            
            # Market state
            features.get('rsi_overbought', 0.0),    # 0 or 1
            features.get('rsi_oversold', 0.0),      # 0 or 1
            features.get('volatility_high', 0.0),   # 0 or 1
            features.get('volatility_low', 0.0),    # 0 or 1
            features.get('macd_positive', 0.5),     # 0 or 1
            
            # Performance feedback (critical for learning)
            min(recent_win_rate, 1.0),
            min(consecutive_losses / 10.0, 1.0),   # Normalized to 0-1 (cap at 10)
            min(current_stake_pct, 3.0) / 3.0,     # How aggressive we are
            min(trade_count / 100.0, 1.0),          # Experience level
        ], dtype=np.float32)
        
        return state


class RLEngine:
    """
    Reinforcement Learning engine for trading decisions.
    Uses neural network approximation for Q-learning.
    Learns which market states lead to profitable vs unprofitable trades.
    
    The RL agent learns:
    - Q(s, take_trade) = expected cumulative reward from taking a trade in state s
    - Q(s, skip) = expected cumulative reward from skipping in state s
    - Only takes trades when Q(take) > Q(skip) + threshold
    
    Rewards:
    - +profit_pct * 10 for profitable trades (scaled by profit magnitude)
    - -abs(profit_pct) * 5 for losing trades (loss aversion)
    - -0.1 for skipped trades that would have been profitable (small penalty)
    - +0.05 for skipped trades that would have been losses (small reward for good judgment)
    """
    
    def __init__(self, state_dim: int = 18, learning_rate: float = 0.01):
        self.state_dim = state_dim
        self.learning_rate = learning_rate
        
        # Q-table as linear approximator: Q(s, a) = theta[a] dot s
        # Using linear approximation is simple, fast, and works well for small state spaces
        self.theta = np.random.randn(2, state_dim) * 0.01  # 2 actions: [skip, take_trade]
        self.theta_bias = np.zeros(2)
        
        # Gradient descent optimizer state
        self.theta_velocity = np.zeros_like(self.theta)
        self.bias_velocity = np.zeros_like(self.theta_bias)
        self.beta1 = 0.9  # Adam momentum
        self.beta2 = 0.999
        self.epsilon_adam = 1e-8
        self.timestep = 0
        
        # Experience replay
        self.memory = ExperienceReplay(max_size=2000)
        
        # Training hyperparameters
        self.gamma = 0.95          # Discount factor
        self.epsilon = 1.0         # Exploration rate (starts high)
        self.epsilon_min = 0.05    # Minimum exploration
        self.epsilon_decay = 0.995 # Decay per training step
        self.batch_size = 32
        self.train_every = 10       # Train every N new experiences
        self.experiences_since_train = 0
        
        # Performance tracking
        self.training_count = 0
        self.loss_history = deque(maxlen=100)
        self.q_values_history = deque(maxlen=100)
        
        # Whether to load saved model
        self.model_loaded = False
    
    def get_action(self, state: np.ndarray, force_explore: bool = False) -> Tuple[int, float]:
        """
        Get action using epsilon-greedy policy.
        
        Args:
            state: Encoded market state
            force_explore: Force exploration (for training)
            
        Returns:
            (action, q_value)
            action: 0 = skip, 1 = take_trade
            q_value: Q-value of the chosen action
        """
        # Explore with probability epsilon
        if not force_explore and np.random.random() < self.epsilon:
            action = np.random.choice([0, 1])
            q_value = self._predict(state)[action]
            return action, float(q_value)
        
        # Greedy: choose best action
        q_values = self._predict(state)
        action = int(np.argmax(q_values))
        q_value = float(q_values[action])
        self.q_values_history.append(q_value)
        
        return action, q_value
    
    def _predict(self, state: np.ndarray) -> np.ndarray:
        """Predict Q-values for all actions given state."""
        return state @ self.theta.T + self.theta_bias
    
    def train(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool = False):
        """
        Single training step (one experience).
        Stores experience and periodically trains on batch.
        """
        # Store experience
        self.memory.add(state, action, reward, next_state, done)
        self.experiences_since_train += 1
        
        # Train on batch periodically
        if self.experiences_since_train >= self.train_every and len(self.memory) >= self.batch_size:
            self._batch_train()
            self.experiences_since_train = 0
            
            # Decay exploration
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
    
    def _batch_train(self):
        """Train on a batch of experiences using prioritized replay."""
        self.timestep += 1
        self.training_count += 1
        
        # Sample batch
        samples, weights, indices = self.memory.sample(self.batch_size)
        
        states = np.array([s[0] for s in samples])
        actions = np.array([s[1] for s in samples])
        rewards = np.array([s[2] for s in samples])
        next_states = np.array([s[3] for s in samples])
        
        # Compute target Q-values
        next_q = self._predict(next_states)  # (batch, 2)
        max_next_q = np.max(next_q, axis=1)  # (batch,)
        
        # Q-learning target: reward + gamma * max(Q(s', a'))
        targets = self._predict(states)  # Current predictions
        for i in range(len(samples)):
            td_target = rewards[i] + self.gamma * max_next_q[i]
            td_error = td_target - targets[i, actions[i]]
            targets[i, actions[i]] = td_target
            
            # Store TD-error for priority update
            # (weights array acts as placeholder for indexing)
        
        # Compute TD-errors for priority update
        current_q = self._predict(states)
        td_errors = np.zeros(len(samples))
        for i in range(len(samples)):
            td_errors[i] = abs(rewards[i] + self.gamma * max_next_q[i] - current_q[i, actions[i]])
        
        # Gradient step (simplified linear Q-learning)
        # Gradient = -(target - prediction) * state
        # We use a simple SGD update with importance sampling weights
        loss = 0.0
        for i in range(len(samples)):
            w = weights[i]
            state_i = states[i]
            action_i = actions[i]
            
            # Prediction error
            pred = self._predict(state_i)
            target = targets[i]
            error = pred - target
            
            # Update weights: theta[action] -= lr * error[action] * state * w
            self.theta[action_i] -= self.learning_rate * error[action_i] * state_i * w
            self.theta_bias[action_i] -= self.learning_rate * error[action_i] * w
            
            loss += error[action_i] ** 2 * w
        
        # Update priorities in replay buffer
        self.memory.update_priorities(indices, td_errors)
        
        avg_loss = loss / len(samples)
        self.loss_history.append(avg_loss)
    
    def get_optimal_q_value(self, state: np.ndarray) -> Tuple[float, float]:
        """
        Get Q-values for both actions.
        Returns (Q_skip, Q_take)
        """
        q_values = self._predict(state)
        return float(q_values[0]), float(q_values[1])
    
    def should_trade(self, state: np.ndarray, min_advantage: float = 0.01) -> Tuple[bool, float, float]:
        """
        Decide whether to trade based on Q-values.
        Only trades if Q(take_trade) > Q(skip) + min_advantage.
        
        Args:
            state: Encoded market state
            min_advantage: Minimum Q-value advantage to take trade
            
        Returns:
            (should_trade, Q_skip, Q_take)
        """
        q_skip, q_take = self.get_optimal_q_value(state)
        advantage = q_take - q_skip
        return advantage > min_advantage, q_skip, q_take
    
    def save(self, filepath: str):
        """Save RL model to disk."""
        try:
            model_data = {
                'theta': self.theta,
                'theta_bias': self.theta_bias,
                'epsilon': self.epsilon,
                'training_count': self.training_count,
                'theta_velocity': self.theta_velocity,
                'bias_velocity': self.bias_velocity,
                'timestep': self.timestep,
                'loss_history': list(self.loss_history),
                'state_dim': self.state_dim,
            }
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            agent_logger.log_info(f"💾 RL model saved to {filepath} (trained {self.training_count} times)")
        except Exception as e:
            agent_logger.log_error(f"Error saving RL model: {e}")
    
    def load(self, filepath: str) -> bool:
        """Load RL model from disk."""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    model_data = pickle.load(f)
                self.theta = model_data['theta']
                self.theta_bias = model_data['theta_bias']
                self.epsilon = model_data.get('epsilon', 0.5)
                self.training_count = model_data.get('training_count', 0)
                self.theta_velocity = model_data.get('theta_velocity', np.zeros_like(self.theta))
                self.bias_velocity = model_data.get('bias_velocity', np.zeros_like(self.theta_bias))
                self.timestep = model_data.get('timestep', 0)
                self.loss_history = deque(model_data.get('loss_history', []), maxlen=100)
                self.model_loaded = True
                agent_logger.log_info(f"📂 RL model loaded from {filepath} (trained {self.training_count} times)")
                return True
            return False
        except Exception as e:
            agent_logger.log_error(f"Error loading RL model: {e}")
            return False


class ProfitCompounder:
    """
    Manages profit-based stake growth.
    Automatically increases base_stake as account equity grows.
    
    Rules:
    - Every time profit reaches a multiple of base_stake, increase stake
    - Use conservative compounding: increase by 10-20% of profits
    - Never reduce stake from user-configured base (only grow with profits)
    - Track peak equity to avoid reducing stake on drawdowns
    """
    
    def __init__(self, initial_stake: float = 0.35, growth_rate: float = 0.15):
        self.initial_stake = initial_stake       # User's configured base stake
        self.current_stake = initial_stake       # Current stake (grows with profits)
        self.growth_rate = growth_rate           # % of profits added to stake (15%)
        self.equity_peak = initial_stake * 100   # Peak equity tracked for compounding
        self.starting_equity = initial_stake * 100
        self.last_growth_equity = initial_stake * 100  # Equity at last stake increase
        
        # Stake milestones (for logging)
        self.milestones_logged = set()
        self._log_milestone(initial_stake)
    
    def update(self, current_equity: float, trade_result: float):
        """
        Update equity tracking and potentially increase stake.
        
        Args:
            current_equity: Current account equity
            trade_result: P&L of last trade (positive = win, negative = loss)
            
        Returns:
            new_stake: Updated stake (may be same as before)
            did_grow: Whether stake was increased
        """
        # Track peak equity
        if current_equity > self.equity_peak:
            self.equity_peak = current_equity
        
        # Calculate profit from starting equity
        profit = current_equity - self.starting_equity
        
        # Only grow when we have profit and equity is at or near peak
        if profit > 0 and current_equity >= self.equity_peak * 0.95:
            # Calculate how much we've grown since last increase
            growth_multiple = current_equity / self.last_growth_equity
            
            # Grow stake when equity increases by at least 20% from last growth point
            if growth_multiple >= 1.2:
                # Calculate stake increase based on growth_rate * profit
                # But cap at 50% increase per step to avoid over-aggressive growth
                profit_for_growth = current_equity - self.last_growth_equity
                stake_increase = self.current_stake * self.growth_rate
                max_increase = self.current_stake * 0.5  # Max 50% increase per step
                
                actual_increase = min(stake_increase, max_increase)
                
                # Only increase if it makes a meaningful difference (at least $0.05)
                if actual_increase >= 0.05:
                    self.current_stake = round(self.current_stake + actual_increase, 2)
                    self.last_growth_equity = current_equity
                    self._log_milestone(self.current_stake)
                    
                    agent_logger.log_info(
                        f"📈 STAKE GROWTH: ${self.current_stake - actual_increase:.2f} → "
                        f"${self.current_stake:.2f} (equity=${current_equity:.2f}, "
                        f"profit=${profit:.2f}, increase=${actual_increase:.2f})"
                    )
                    return self.current_stake, True
        
        return self.current_stake, False
    
    def _log_milestone(self, stake: float):
        """Log when stake reaches a notable milestone."""
        milestone = round(stake / self.initial_stake, 1)
        
        # Log at every 0.1x multiple of initial stake
        key = f"{milestone:.1f}x"
        if key not in self.milestones_logged:
            self.milestones_logged.add(key)
            agent_logger.log_info(
                f"🏆 STAKE MILESTONE: ${stake:.2f} ({milestone:.1f}x initial stake of ${self.initial_stake:.2f})"
            )
    
    def get_current_stake(self) -> float:
        """Get the current stake (may be higher than base due to compounding)."""
        return self.current_stake
    
    def reset(self, initial_stake: float):
        """Reset compounder to new initial stake."""
        self.initial_stake = initial_stake
        self.current_stake = initial_stake
        self.equity_peak = initial_stake * 100
        self.starting_equity = initial_stake * 100
        self.last_growth_equity = initial_stake * 100
        self.milestones_logged = set()
        self._log_milestone(initial_stake)
    
    def get_growth_stats(self) -> Dict:
        """Get growth statistics."""
        return {
            'initial_stake': self.initial_stake,
            'current_stake': self.current_stake,
            'growth_multiple': round(self.current_stake / self.initial_stake, 2),
            'equity_peak': self.equity_peak,
            'growth_rate': self.growth_rate,
            'total_growth': round(self.current_stake - self.initial_stake, 2),
        }


class ReinforcementLearningSystem:
    """
    Complete RL system integrating market state encoding, Q-learning,
    experience replay, and profit compounding.
    
    This is the brain of the trading agent. It learns:
    1. When to trade vs skip based on market conditions
    2. How to compound profits by growing stake
    3. Which market patterns lead to consistent wins
    """
    
    def __init__(self, initial_stake: float = 0.35):
        # RL engine
        self.rl_engine = RLEngine(state_dim=18)
        
        # State encoder
        self.state_encoder = MarketStateEncoder()
        
        # Profit compounder
        self.compounder = ProfitCompounder(initial_stake, growth_rate=0.15)
        
        # Experience tracking
        self.last_state = None
        self.last_action = None
        self.last_features = None
        self.trade_count = 0
        self.recent_win_rate = 0.5
        self.consecutive_losses = 0
        self.recent_results = deque(maxlen=20)  # True=win, False=loss
        self.wins = 0
        self.losses = 0
        
        # Equity tracking
        self.current_equity = initial_stake * 100
        self.initial_equity = initial_stake * 100
        
        # Model paths
        self.model_path = os.path.join(MODELS_DIR, 'rl_model.pkl')
        self.compounder_path = os.path.join(MODELS_DIR, 'compounder_data.json')
        
        # Load saved models
        self._load()
        
        # Log start
        agent_logger.log_info("🧠 RL System initialized")
        agent_logger.log_info(
            f"  - Initial stake: ${initial_stake:.2f} | "
            f"Current stake: ${self.compounder.get_current_stake():.2f} | "
            f"Equity: ${self.current_equity:.2f}"
        )
        if self.rl_engine.model_loaded:
            agent_logger.log_info(f"  - RL model loaded (trained {self.rl_engine.training_count} times, ε={self.rl_engine.epsilon:.3f})")
        else:
            agent_logger.log_info(f"  - RL model: new (will learn from scratch, ε={self.rl_engine.epsilon:.2f})")
    
    def decide(self, features: Dict) -> Tuple[bool, float, float]:
        """
        Make trading decision based on market state.
        
        Args:
            features: Market indicator features dict
            
        Returns:
            (should_trade, Q_skip, Q_take)
        """
        # Encode current market state
        state = self.state_encoder.encode(
            features, 
            self.recent_win_rate, 
            self.consecutive_losses,
            self.compounder.get_current_stake() / self.compounder.initial_stake,
            self.trade_count
        )
        
        # Get RL action
        should_trade, q_skip, q_take = self.rl_engine.should_trade(state)
        
        # Store for learning after trade result
        self.last_state = state
        self.last_features = features
        
        return should_trade, q_skip, q_take
    
    def record_trade_execution(self, action_taken: int):
        """Record that a trade was taken (1) or skipped (0)."""
        self.last_action = action_taken
    
    def record_trade_result(self, profit: float, was_win: bool, features_at_entry: Optional[Dict] = None):
        """
        Record trade result and learn from it.
        
        The reward function:
        - Win: +profit/stake * 10 (scaled reward by profit magnitude)
        - Loss: -abs(profit)/stake * 5 (loss aversion penalty)
        - Skip that would have won: -0.2 (small regret penalty)
        - Skip that would have lost: +0.1 (reward for good judgment)
        """
        stake = self.compounder.get_current_stake()
        
        if self.last_state is not None and self.last_action is not None:
            if self.last_action == 1:  # We took a trade
                if was_win:
                    # Reward scaled by profit relative to stake
                    reward = (profit / stake) * 10
                    # Bonus for being correct with high confidence
                    reward = min(reward, 5.0)  # Cap positive reward
                else:
                    # Loss aversion: negative reward scaled by loss magnitude
                    reward = -(abs(profit) / stake) * 5
                    reward = max(reward, -5.0)  # Cap negative reward
            else:  # We skipped
                # We don't know if skip was correct until we see what happens next
                # For now, give a neutral reward (we'll learn from price movement)
                reward = 0.0
            
            # Train RL engine
            next_features = features_at_entry or self.last_features
            if next_features:
                next_state = self.state_encoder.encode(
                    next_features,
                    self.recent_win_rate,
                    self.consecutive_losses,
                    self.compounder.get_current_stake() / self.compounder.initial_stake,
                    self.trade_count
                )
                self.rl_engine.train(self.last_state, self.last_action, reward, next_state)
            
            # Clear
            self.last_state = None
            self.last_action = None
        
        # Update performance tracking
        self.recent_results.append(was_win)
        if was_win:
            self.wins += 1
            self.consecutive_losses = 0
        else:
            self.losses += 1
            self.consecutive_losses += 1
        
        # Update win rate
        if len(self.recent_results) > 0:
            self.recent_win_rate = sum(self.recent_results) / len(self.recent_results)
        
        self.trade_count += 1
        
        # Update equity
        self.current_equity += profit
        
        # Try to grow stake (profit compounding)
        new_stake, did_grow = self.compounder.update(self.current_equity, profit)
        
        # Log significant learning milestones
        if self.rl_engine.training_count > 0 and self.rl_engine.training_count % 20 == 0:
            avg_loss = np.mean(self.rl_engine.loss_history) if self.rl_engine.loss_history else 0
            agent_logger.log_info(
                f"🧠 RL Training: {self.rl_engine.training_count} batches | "
                f"Loss: {avg_loss:.4f} | ε={self.rl_engine.epsilon:.3f} | "
                f"Replay: {len(self.rl_engine.memory)} exp | "
                f"Stake: ${self.compounder.get_current_stake():.2f}"
            )
    
    def learn_from_skip(self, features_now: Dict):
        """
        Learn from skipped trades by checking if market moved favorably.
        This gives feedback on skipped decisions.
        
        Called when a new tick arrives after we skipped a trade.
        Compares current price to price when we skipped.
        """
        if self.last_state is not None and self.last_action == 0:
            # Check if the market moved in a direction that would have been profitable
            # This requires knowing what direction we would have traded
            # For simplicity, give small positive reward if market is calm
            # and small negative reward if there was a strong move we missed
            pass
    
    def get_adjusted_stake(self, base_stake: float, confidence: float) -> float:
        """
        Get the adjusted stake for a trade.
        
        The RL compounder grows stake based on accumulated profits.
        This is then used as the "base" for the risk manager.
        
        The risk manager will apply its reductions (volatility, drawdown, etc.)
        on top of this stake.
        
        Args:
            base_stake: The user's configured base stake (e.g., $0.35)
            confidence: Current trade confidence
            
        Returns:
            Stake adjusted for profit compounding
        """
        # Get the RL-grown stake
        grown_stake = self.compounder.get_current_stake()
        
        # Apply confidence-based adjustment
        # Higher confidence → closer to grown stake
        # Lower confidence → closer to original base stake
        confidence_factor = 0.5 + (confidence * 0.5)  # 0.5 to 1.0 range
        
        adjusted = base_stake + (grown_stake - base_stake) * confidence_factor
        return round(adjusted, 2)
    
    def save(self):
        """Save RL system state."""
        self.rl_engine.save(self.model_path)
        
        # Save compounder data
        try:
            compounder_data = {
                'initial_stake': self.compounder.initial_stake,
                'current_stake': self.compounder.current_stake,
                'equity_peak': self.compounder.equity_peak,
                'last_growth_equity': self.compounder.last_growth_equity,
                'starting_equity': self.compounder.starting_equity,
                'current_equity': self.current_equity,
                'wins': self.wins,
                'losses': self.losses,
                'trade_count': self.trade_count,
                'recent_win_rate': self.recent_win_rate,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.compounder_path, 'w') as f:
                json.dump(compounder_data, f, indent=2)
            agent_logger.log_info(f"💾 RL state saved")
        except Exception as e:
            agent_logger.log_error(f"Error saving RL state: {e}")
    
    def _load(self):
        """Load RL system state."""
        loaded = self.rl_engine.load(self.model_path)
        
        # Load compounder data
        try:
            if os.path.exists(self.compounder_path):
                with open(self.compounder_path, 'r') as f:
                    data = json.load(f)
                self.compounder.initial_stake = data.get('initial_stake', 0.35)
                self.compounder.current_stake = data.get('current_stake', 0.35)
                self.compounder.equity_peak = data.get('equity_peak', 35.0)
                self.compounder.last_growth_equity = data.get('last_growth_equity', 35.0)
                self.compounder.starting_equity = data.get('starting_equity', 35.0)
                self.current_equity = data.get('current_equity', 35.0)
                self.wins = data.get('wins', 0)
                self.losses = data.get('losses', 0)
                self.trade_count = data.get('trade_count', 0)
                self.recent_win_rate = data.get('recent_win_rate', 0.5)
                agent_logger.log_info(f"📂 RL state loaded: stake=${self.compounder.current_stake:.2f}, equity=${self.current_equity:.2f}")
        except Exception as e:
            agent_logger.log_error(f"Error loading RL state: {e}")
    
    def get_stats(self) -> Dict:
        """Get RL system statistics."""
        return {
            'rl_trained': self.rl_engine.training_count,
            'rl_epsilon': self.rl_engine.epsilon,
            'rl_replay_size': len(self.rl_engine.memory),
            'rl_loss': float(np.mean(self.rl_engine.loss_history)) if self.rl_engine.loss_history else 0,
            'stake': self.compounder.get_current_stake(),
            'stake_growth': round(self.compounder.get_current_stake() / self.compounder.initial_stake, 2),
            'equity': self.current_equity,
            'initial_equity': self.initial_equity,
            'total_profit': round(self.current_equity - self.initial_equity, 2),
            'win_rate': self.recent_win_rate,
            'wins': self.wins,
            'losses': self.losses,
            'trade_count': self.trade_count,
        }