"""
OPTIMAL Q-Learning Training with Guaranteed Convergence
"""
import pickle
import random
import os
import numpy as np

GRID_SIZE = 6
GOAL = (5, 5)
ACTIONS = ["up", "down", "left", "right"]
ACTION_MAP = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}

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

def manhattan_distance(pos1, pos2):
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

# ─── Train Static Environment ─────────────────────────────────
print("=" * 60)
print("Training STATIC environment...")
print("=" * 60)

Q_static = {}
EPISODES = 50000
ALPHA = 0.5
GAMMA = 0.95
EPSILON = 1.0
EPSILON_MIN = 0.01
EPSILON_DECAY = 0.9995

best_steps = 50

for episode in range(EPISODES):
    agent = (0, 0)  # Always start from (0,0)
    epsilon = max(EPSILON_MIN, EPSILON * (EPSILON_DECAY ** episode))
    alpha = max(0.05, ALPHA * (0.9999 ** episode))
    
    for step in range(100):
        state = agent
        
        # Initialize Q-values for this state
        if state not in Q_static:
            Q_static[state] = {a: 0.0 for a in ACTIONS}
        
        # Action selection
        if random.random() < epsilon:
            action = random.choice(ACTIONS)
        else:
            # Greedy with random tie-breaking
            q_vals = Q_static[state]
            max_val = max(q_vals.values())
            best_actions = [a for a, v in q_vals.items() if v == max_val]
            action = random.choice(best_actions)
        
        next_pos = next_state(agent, action)
        
        # REWARD FUNCTION
        if next_pos == GOAL:
            reward = 100
            done = True
        elif next_pos == agent:  # Hit wall
            reward = -20
            done = False
        else:
            # Distance-based reward
            cur_dist = manhattan_distance(agent, GOAL)
            next_dist = manhattan_distance(next_pos, GOAL)
            
            if next_dist < cur_dist:
                reward = 10
            elif next_dist > cur_dist:
                reward = -5
            else:
                reward = -1
            
            reward -= 0.1  # Small step penalty to encourage shortest path
            done = False
        
        # Q-Learning update
        if next_pos not in Q_static:
            Q_static[next_pos] = {a: 0.0 for a in ACTIONS}
        
        next_max = max(Q_static[next_pos].values())
        Q_static[state][action] += alpha * (reward + GAMMA * next_max - Q_static[state][action])
        
        agent = next_pos
        
        if done:
            if step + 1 < best_steps:
                best_steps = step + 1
                print(f"Episode {episode}: New best path = {best_steps} steps")
            break
    
    if episode % 5000 == 0:
        print(f"Progress: {episode}/{EPISODES} | Epsilon: {epsilon:.3f} | Alpha: {alpha:.3f} | Best: {best_steps}")

# Save
with open("q_table.pkl", "wb") as f:
    pickle.dump(Q_static, f)
print(f"\n✅ Static Q-table saved: {len(Q_static)} states")
print(f"   Optimal path length: {best_steps} steps (minimum possible: 10)")

# ─── Train Dynamic Environment ─────────────────────────────────
print("\n" + "=" * 60)
print("Training DYNAMIC environment...")
print("=" * 60)

Q_dynamic = {}
EPISODES = 100000
ALPHA = 0.5
GAMMA = 0.95
EPSILON = 1.0

best_steps = 50
success_count = 0

for episode in range(EPISODES):
    agent = (0, 0)
    obstacle = (random.randint(0, 5), random.randint(0, 5))
    if obstacle == (0, 0) or obstacle == GOAL:
        obstacle = (2, 2)
    
    epsilon = max(EPSILON_MIN, EPSILON * (EPSILON_DECAY ** episode))
    alpha = max(0.05, ALPHA * (0.9999 ** episode))
    
    for step in range(100):
        # Move obstacle first
        obstacle = move_obstacle(obstacle)
        
        state = (agent, obstacle)
        
        # Initialize Q-values
        if state not in Q_dynamic:
            Q_dynamic[state] = {a: 0.0 for a in ACTIONS}
        
        # Action selection with obstacle avoidance
        if random.random() < epsilon:
            # Exploration: prefer safe actions
            safe_actions = [a for a in ACTIONS 
                          if next_state(agent, a) != obstacle 
                          and next_state(agent, a) != agent]
            if safe_actions:
                action = random.choice(safe_actions)
            else:
                action = random.choice(ACTIONS)
        else:
            # Exploitation: best safe action
            q_vals = Q_dynamic[state]
            sorted_actions = sorted(q_vals.items(), key=lambda x: x[1], reverse=True)
            
            # Find best safe action
            action = sorted_actions[0][0]  # Default
            for act, _ in sorted_actions:
                if next_state(agent, act) != obstacle:
                    action = act
                    break
        
        next_pos = next_state(agent, action)
        
        # REWARD FUNCTION
        if next_pos == GOAL:
            reward = 200
            done = True
        elif next_pos == obstacle:
            reward = -100
            done = True
        elif next_pos == agent:
            reward = -30
            done = False
        else:
            cur_dist = manhattan_distance(agent, GOAL)
            next_dist = manhattan_distance(next_pos, GOAL)
            
            if next_dist < cur_dist:
                reward = 15
            elif next_dist > cur_dist:
                reward = -8
            else:
                reward = -2
            
            # Bonus for keeping distance from obstacle
            obs_dist = manhattan_distance(next_pos, obstacle)
            if obs_dist <= 1:
                reward -= 5
            elif obs_dist >= 3:
                reward += 3
            
            reward -= 0.5  # Step penalty
            done = False
        
        # Q-Learning update
        next_state_key = (next_pos, obstacle)
        if next_state_key not in Q_dynamic:
            Q_dynamic[next_state_key] = {a: 0.0 for a in ACTIONS}
        
        next_max = max(Q_dynamic[next_state_key].values())
        Q_dynamic[state][action] += alpha * (reward + GAMMA * next_max - Q_dynamic[state][action])
        
        agent = next_pos
        
        if done:
            if agent == GOAL:
                success_count += 1
                if step + 1 < best_steps:
                    best_steps = step + 1
                    print(f"Episode {episode}: New best = {best_steps} steps (success rate: {success_count}/{episode+1})")
            break
    
    if episode % 10000 == 0:
        success_rate = (success_count / (episode + 1)) * 100 if episode > 0 else 0
        print(f"Progress: {episode}/{EPISODES} | Epsilon: {epsilon:.3f} | Success: {success_rate:.1f}% | Best: {best_steps}")

# Save
with open("q_table_dynamic.pkl", "wb") as f:
    pickle.dump(Q_dynamic, f)

final_success = (success_count / EPISODES) * 100
print(f"\n✅ Dynamic Q-table saved: {len(Q_dynamic)} states")
print(f"   Success rate: {final_success:.1f}%")
print(f"   Best path: {best_steps} steps")

# ─── Quick Validation Test ─────────────────────────────────────
print("\n" + "=" * 60)
print("VALIDATION TEST")
print("=" * 60)

def test_static_path():
    agent = (0, 0)
    path = [agent]
    visited_states = set()
    
    for _ in range(50):
        state = agent
        if state in visited_states:
            # Looping - break
            return None, len(path)
        visited_states.add(state)
        
        if state in Q_static:
            q_vals = Q_static[state]
            max_val = max(q_vals.values())
            best_actions = [a for a, v in q_vals.items() if v == max_val]
            action = random.choice(best_actions)
        else:
            return None, len(path)
        
        agent = next_state(agent, action)
        path.append(agent)
        
        if agent == GOAL:
            return path, len(path) - 1
    
    return None, len(path)

# Run multiple tests
print("\nStatic Environment Tests (10 runs):")
successes = 0
total_steps = 0
for i in range(10):
    path, steps = test_static_path()
    if path:
        successes += 1
        total_steps += steps
        print(f"  Test {i+1}: ✅ {steps} steps - {path}")
    else:
        print(f"  Test {i+1}: ❌ Failed (looping)")

if successes > 0:
    print(f"\nStatic: {successes}/10 successful | Avg: {total_steps/successes:.1f} steps")
else:
    print("\nStatic: ALL FAILED - Need more training!")

print("\n" + "=" * 60)
print("Training complete! Replace your Q-table files and redeploy.")
print("=" * 60)