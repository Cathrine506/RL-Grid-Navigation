"""
Train Q-Learning Agent for Grid Navigation
Run this to create properly trained Q-tables
"""

import pickle
import random
import numpy as np

# ── Constants ──────────────────────────────────────────────────
GRID_SIZE = 6
GOAL = (5, 5)
ACTIONS = ["up", "down", "left", "right"]
ACTION_MAP = {
    "up":    (-1,  0),
    "down":  ( 1,  0),
    "left":  ( 0, -1),
    "right": ( 0,  1),
}

# ── Helper Functions ───────────────────────────────────────────
def next_state(state, action):
    dx, dy = ACTION_MAP[action]
    ns = (state[0] + dx, state[1] + dy)
    if 0 <= ns[0] < GRID_SIZE and 0 <= ns[1] < GRID_SIZE:
        return ns
    return state

def move_obstacle(obstacle):
    moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    dx, dy = random.choice(moves)
    np_ = (obstacle[0] + dx, obstacle[1] + dy)
    if 0 <= np_[0] < GRID_SIZE and 0 <= np_[1] < GRID_SIZE:
        return np_
    return obstacle

def get_state_key(agent, obstacle=None):
    """Create state key for Q-table"""
    if obstacle:
        return (agent, obstacle)
    return agent

# ── Training Parameters ────────────────────────────────────────
EPISODES = 50000  # Number of training episodes
ALPHA = 0.1      # Learning rate
GAMMA = 0.95     # Discount factor
EPSILON_START = 1.0
EPSILON_END = 0.01
EPSILON_DECAY = 0.9995

# ── Train Static Environment ───────────────────────────────────
print("Training static environment...")
Q_static = {}

for episode in range(EPISODES):
    agent = (0, 0)  # Start position
    epsilon = max(EPSILON_END, EPSILON_START * (EPSILON_DECAY ** episode))
    
    for step in range(200):
        state = agent
        
        # Initialize state if not in Q-table
        if state not in Q_static:
            Q_static[state] = {a: 0.0 for a in ACTIONS}
        
        # Epsilon-greedy action selection
        if random.random() < epsilon:
            action = random.choice(ACTIONS)
        else:
            action = max(Q_static[state], key=Q_static[state].get)
        
        # Take action
        next_pos = next_state(agent, action)
        
        # Calculate reward
        if next_pos == GOAL:
            reward = 100
        elif next_pos == agent:  # Hit wall
            reward = -10
        else:
            # Reward for moving closer to goal
            current_dist = abs(agent[0] - GOAL[0]) + abs(agent[1] - GOAL[1])
            next_dist = abs(next_pos[0] - GOAL[0]) + abs(next_pos[1] - GOAL[1])
            reward = (current_dist - next_dist) * 2 - 0.1  # Small penalty for each step
        
        # Update Q-value
        next_state_key = next_pos
        if next_state_key not in Q_static:
            Q_static[next_state_key] = {a: 0.0 for a in ACTIONS}
        
        best_next = max(Q_static[next_state_key].values())
        Q_static[state][action] += ALPHA * (reward + GAMMA * best_next - Q_static[state][action])
        
        agent = next_pos
        
        if agent == GOAL:
            break
    
    if (episode + 1) % 5000 == 0:
        print(f"Episode {episode + 1}/{EPISODES}, Epsilon: {epsilon:.3f}")

# Save static Q-table
with open("q_table.pkl", "wb") as f:
    pickle.dump(Q_static, f)
print(f"✅ Static Q-table saved with {len(Q_static)} states")

# ── Train Dynamic Environment ──────────────────────────────────
print("\nTraining dynamic environment...")
Q_dynamic = {}

for episode in range(EPISODES):
    agent = (0, 0)
    obstacle = (2, 2)  # Starting obstacle position
    epsilon = max(EPSILON_END, EPSILON_START * (EPSILON_DECAY ** episode))
    
    for step in range(200):
        # Move obstacle
        obstacle = move_obstacle(obstacle)
        
        state = get_state_key(agent, obstacle)
        
        # Initialize state if not in Q-table
        if state not in Q_dynamic:
            Q_dynamic[state] = {a: 0.0 for a in ACTIONS}
        
        # Epsilon-greedy with safety check
        if random.random() < epsilon:
            # Random action that doesn't hit obstacle
            safe_actions = [a for a in ACTIONS if next_state(agent, a) != obstacle]
            if safe_actions:
                action = random.choice(safe_actions)
            else:
                action = random.choice(ACTIONS)
        else:
            # Best safe action
            sorted_actions = sorted(Q_dynamic[state].items(), key=lambda x: x[1], reverse=True)
            for act, _ in sorted_actions:
                if next_state(agent, act) != obstacle:
                    action = act
                    break
            else:
                action = sorted_actions[0][0]
        
        # Take action
        next_pos = next_state(agent, action)
        
        # Calculate reward
        if next_pos == GOAL:
            reward = 100
        elif next_pos == obstacle:
            reward = -50  # Heavy penalty for hitting obstacle
        elif next_pos == agent:
            reward = -10  # Wall collision
        else:
            current_dist = abs(agent[0] - GOAL[0]) + abs(agent[1] - GOAL[1])
            next_dist = abs(next_pos[0] - GOAL[0]) + abs(next_pos[1] - GOAL[1])
            reward = (current_dist - next_dist) * 2 - 0.1
        
        # Update Q-value
        next_state_key = get_state_key(next_pos, obstacle)
        if next_state_key not in Q_dynamic:
            Q_dynamic[next_state_key] = {a: 0.0 for a in ACTIONS}
        
        best_next = max(Q_dynamic[next_state_key].values())
        Q_dynamic[state][action] += ALPHA * (reward + GAMMA * best_next - Q_dynamic[state][action])
        
        agent = next_pos
        
        if agent == GOAL:
            break
        if agent == obstacle:
            break
    
    if (episode + 1) % 5000 == 0:
        print(f"Episode {episode + 1}/{EPISODES}, Epsilon: {epsilon:.3f}")

# Save dynamic Q-table
with open("q_table_dynamic.pkl", "wb") as f:
    pickle.dump(Q_dynamic, f)
print(f"✅ Dynamic Q-table saved with {len(Q_dynamic)} states")

# ── Test the trained models ────────────────────────────────────
print("\n🧪 Testing trained models...")

def test_static():
    agent = (0, 0)
    path = [(0, 0)]
    for _ in range(50):
        state = agent
        if state in Q_static:
            action = max(Q_static[state], key=Q_static[state].get)
        else:
            break
        agent = next_state(agent, action)
        path.append(agent)
        if agent == GOAL:
            return True, len(path), path
    return False, len(path), path

success, steps, path = test_static()
print(f"Static: {'✅ Success' if success else '❌ Failed'} in {steps} steps")
print(f"Path: {path}")

def test_dynamic():
    agent = (0, 0)
    obstacle = (2, 2)
    path = [(0, 0)]
    for _ in range(50):
        obstacle = move_obstacle(obstacle)
        state = (agent, obstacle)
        if state in Q_dynamic:
            sorted_actions = sorted(Q_dynamic[state].items(), key=lambda x: x[1], reverse=True)
            for act, _ in sorted_actions:
                if next_state(agent, act) != obstacle:
                    action = act
                    break
            else:
                action = sorted_actions[0][0]
        else:
            break
        agent = next_state(agent, action)
        path.append(agent)
        if agent == GOAL:
            return True, len(path), path
        if agent == obstacle:
            return False, len(path), path
    return False, len(path), path

success, steps, path = test_dynamic()
print(f"Dynamic: {'✅ Success' if success else '❌ Failed'} in {steps} steps")
print(f"Path: {path}")