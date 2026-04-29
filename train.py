"""
Optimized Q-Learning Training for Grid Navigation
Run this to create OPTIMAL Q-tables
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

# ── OPTIMIZED Training Parameters ──────────────────────────────
EPISODES = 100000  # More episodes for better learning
ALPHA = 0.3       # Higher learning rate initially
GAMMA = 0.99      # Higher discount for long-term planning
EPSILON_START = 1.0
EPSILON_END = 0.001  # More exploitation at the end
EPSILON_DECAY = 0.9999  # Slower decay for better exploration

# ── Train Static Environment (OPTIMIZED) ──────────────────────
print("Training OPTIMIZED static environment...")
Q_static = {}
best_path_length = 50

for episode in range(EPISODES):
    agent = (0, 0)
    epsilon = max(EPSILON_END, EPSILON_START * (EPSILON_DECAY ** episode))
    
    # Dynamic alpha decay
    alpha = max(0.01, ALPHA * (0.9999 ** episode))
    
    for step in range(100):
        state = agent
        
        if state not in Q_static:
            Q_static[state] = {a: 0.0 for a in ACTIONS}
        
        # Epsilon-greedy with preference for unexplored actions
        if random.random() < epsilon:
            # Prefer actions that lead to unexplored states
            unexplored = []
            for a in ACTIONS:
                ns = next_state(agent, a)
                if ns not in Q_static and ns != agent:
                    unexplored.append(a)
            if unexplored:
                action = random.choice(unexplored)
            else:
                action = random.choice(ACTIONS)
        else:
            action = max(Q_static[state], key=Q_static[state].get)
        
        next_pos = next_state(agent, action)
        
        # IMPROVED REWARD FUNCTION
        if next_pos == GOAL:
            reward = 200  # Bigger reward for reaching goal
        elif next_pos == agent:  # Hit wall
            reward = -20  # Bigger penalty for hitting walls
        else:
            # Distance-based reward
            current_dist = abs(agent[0] - GOAL[0]) + abs(agent[1] - GOAL[1])
            next_dist = abs(next_pos[0] - GOAL[0]) + abs(next_pos[1] - GOAL[1])
            
            if next_dist < current_dist:
                reward = 5  # Reward for moving closer
            else:
                reward = -2  # Penalty for moving away
            
            # Additional step penalty to encourage shorter paths
            reward -= 0.5
        
        # Update Q-value
        next_state_key = next_pos
        if next_state_key not in Q_static:
            Q_static[next_state_key] = {a: 0.0 for a in ACTIONS}
        
        best_next = max(Q_static[next_state_key].values())
        Q_static[state][action] += alpha * (reward + GAMMA * best_next - Q_static[state][action])
        
        agent = next_pos
        
        if agent == GOAL:
            if step + 1 < best_path_length:
                best_path_length = step + 1
                print(f"🎯 New best path: {best_path_length} steps (episode {episode + 1})")
            break
    
    if (episode + 1) % 10000 == 0:
        print(f"Episode {episode + 1}/{EPISODES}, Epsilon: {epsilon:.4f}, Alpha: {alpha:.4f}")

# Save optimized static Q-table
with open("q_table.pkl", "wb") as f:
    pickle.dump(Q_static, f)
print(f"✅ Optimized static Q-table saved ({len(Q_static)} states, best path: {best_path_length} steps)")

# ── Train Dynamic Environment (OPTIMIZED) ─────────────────────
print("\nTraining OPTIMIZED dynamic environment...")
Q_dynamic = {}
best_path_length = 50

for episode in range(EPISODES):
    agent = (0, 0)
    obstacle = (2, 2)
    epsilon = max(EPSILON_END, EPSILON_START * (EPSILON_DECAY ** episode))
    alpha = max(0.01, ALPHA * (0.9999 ** episode))
    
    for step in range(100):
        obstacle = move_obstacle(obstacle)
        state = (agent, obstacle)
        
        if state not in Q_dynamic:
            Q_dynamic[state] = {a: 0.0 for a in ACTIONS}
        
        # Epsilon-greedy with safety AND exploration preference
        safe_actions = [a for a in ACTIONS if next_state(agent, a) != obstacle]
        
        if random.random() < epsilon:
            # Prefer safe unexplored actions
            unexplored_safe = [a for a in safe_actions 
                             if (next_state(agent, a), obstacle) not in Q_dynamic 
                             and next_state(agent, a) != agent]
            if unexplored_safe:
                action = random.choice(unexplored_safe)
            elif safe_actions:
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
        
        next_pos = next_state(agent, action)
        
        # IMPROVED REWARD FUNCTION
        if next_pos == GOAL:
            reward = 200
        elif next_pos == obstacle:
            reward = -100  # Huge penalty for hitting obstacle
        elif next_pos == agent:
            reward = -20
        else:
            current_dist = abs(agent[0] - GOAL[0]) + abs(agent[1] - GOAL[1])
            next_dist = abs(next_pos[0] - GOAL[0]) + abs(next_pos[1] - GOAL[1])
            
            if next_dist < current_dist:
                reward = 10  # Higher reward for progress
            else:
                reward = -3
            
            # Bonus for being far from obstacle
            if obstacle:
                obs_dist = abs(next_pos[0] - obstacle[0]) + abs(next_pos[1] - obstacle[1])
                if obs_dist > 2:
                    reward += 2  # Bonus for keeping distance
            
            reward -= 0.5  # Step penalty
        
        # Update Q-value
        next_state_key = (next_pos, obstacle)
        if next_state_key not in Q_dynamic:
            Q_dynamic[next_state_key] = {a: 0.0 for a in ACTIONS}
        
        best_next = max(Q_dynamic[next_state_key].values())
        Q_dynamic[state][action] += alpha * (reward + GAMMA * best_next - Q_dynamic[state][action])
        
        agent = next_pos
        
        if agent == GOAL:
            if step + 1 < best_path_length:
                best_path_length = step + 1
                print(f"🎯 New best dynamic path: {best_path_length} steps (episode {episode + 1})")
            break
        if agent == obstacle:
            break
    
    if (episode + 1) % 10000 == 0:
        print(f"Episode {episode + 1}/{EPISODES}, Epsilon: {epsilon:.4f}, Alpha: {alpha:.4f}")

# Save optimized dynamic Q-table
with open("q_table_dynamic.pkl", "wb") as f:
    pickle.dump(Q_dynamic, f)
print(f"✅ Optimized dynamic Q-table saved ({len(Q_dynamic)} states, best path: {best_path_length} steps)")

# ── Test and visualize ─────────────────────────────────────────
print("\n🧪 Testing OPTIMIZED models...")

def get_optimal_path_static():
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
            return path
    return path

def get_optimal_path_dynamic():
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
            return path
        if agent == obstacle:
            return path
    return path

# Test static
path_static = get_optimal_path_static()
print(f"\n📊 Static Environment:")
print(f"   Path length: {len(path_static)-1} steps")
print(f"   Reached goal: {'✅' if path_static[-1] == GOAL else '❌'}")
print(f"   Path: {path_static}")

# Test dynamic (average over multiple runs)
success_count = 0
total_steps = 0
for i in range(100):
    path_dyn = get_optimal_path_dynamic()
    if path_dyn[-1] == GOAL:
        success_count += 1
        total_steps += len(path_dyn) - 1

print(f"\n📊 Dynamic Environment:")
print(f"   Success rate: {success_count}%")
if success_count > 0:
    print(f"   Average steps: {total_steps / success_count:.1f}")
    # Show one example path
    path_dyn = get_optimal_path_dynamic()
    print(f"   Example path: {path_dyn[:10]}..." if len(path_dyn) > 10 else f"   Example path: {path_dyn}")
else:
    print("   No successful paths found")

print("\n✨ Training complete! Optimal Q-tables are ready.")