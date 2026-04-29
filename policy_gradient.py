"""
Policy Gradient (REINFORCE) for Grid World Navigation
Uses PyTorch for neural network policy
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random

GRID_SIZE = 6
GOAL = (5, 5)
ACTIONS = ["up", "down", "left", "right"]
ACTION_MAP = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}

class PolicyNetwork(nn.Module):
    """Neural Network for Policy Gradient"""
    def __init__(self, input_size=2, hidden_size=64, output_size=4):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, output_size),
            nn.Softmax(dim=-1)
        )
    
    def forward(self, x):
        return self.network(x)

def next_state(state, action):
    dx, dy = ACTION_MAP[action]
    ns = (state[0] + dx, state[1] + dy)
    if 0 <= ns[0] < GRID_SIZE and 0 <= ns[1] < GRID_SIZE:
        return ns
    return state

def manhattan_distance(pos1, pos2):
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

def state_to_tensor(state):
    """Convert state to tensor"""
    return torch.FloatTensor([state[0] / GRID_SIZE, state[1] / GRID_SIZE])

def policy_gradient_training(episodes=3000):
    """Train using REINFORCE with PyTorch"""
    print("Training Policy Gradient (REINFORCE)...")
    
    policy_net = PolicyNetwork()
    optimizer = optim.Adam(policy_net.parameters(), lr=0.01)
    
    success_rates = []
    
    for episode in range(episodes):
        state = (0, 0)
        log_probs = []
        rewards = []
        
        for step in range(100):
            state_tensor = state_to_tensor(state)
            action_probs = policy_net(state_tensor)
            
            dist = torch.distributions.Categorical(action_probs)
            action_idx = dist.sample()
            action = ACTIONS[action_idx.item()]
            
            log_probs.append(dist.log_prob(action_idx))
            
            next_pos = next_state(state, action)
            
            # Reward
            if next_pos == GOAL:
                rewards.append(100)
                break
            elif next_pos == state:
                rewards.append(-10)
            else:
                cur_dist = manhattan_distance(state, GOAL)
                next_dist = manhattan_distance(next_pos, GOAL)
                rewards.append((cur_dist - next_dist) * 2)
            
            state = next_pos
        
        # Calculate returns
        returns = []
        G = 0
        for r in reversed(rewards):
            G = r + 0.99 * G
            returns.insert(0, G)
        
        returns = torch.FloatTensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        
        # Policy loss
        loss = torch.stack([-lp * r for lp, r in zip(log_probs, returns)]).sum()
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        success_rates.append(1 if state == GOAL else 0)
    
    final_rate = sum(success_rates[-500:]) / 500
    print(f"✅ Policy Gradient trained! Final success rate: {final_rate:.2%}")
    return policy_net, success_rates

def get_policy_path(policy_net, start=(0, 0)):
    """Get path using trained policy"""
    path = [start]
    state = start
    
    for _ in range(50):
        if state == GOAL:
            break
        
        state_tensor = state_to_tensor(state)
        with torch.no_grad():
            action_probs = policy_net(state_tensor)
        action_idx = torch.argmax(action_probs).item()
        action = ACTIONS[action_idx]
        
        state = next_state(state, action)
        path.append(state)
    
    return path

if __name__ == "__main__":
    # Train policy gradient
    policy_net, history = policy_gradient_training(episodes=3000)
    
    # Test
    path = get_policy_path(policy_net)
    
    print(f"\n📊 Policy Gradient Results:")
    print(f"Path length: {len(path)-1} steps")
    print(f"Reached goal: {'✅' if path[-1] == GOAL else '❌'}")
    print(f"Path: {path}")
    
    # Save model
    torch.save(policy_net.state_dict(), "policy_gradient_model.pth")
    print("✅ Model saved as policy_gradient_model.pth")