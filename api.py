"""
FastAPI Inference API for Q-Learning Grid Navigation
Supports both Static and Dynamic environments
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import pickle
import random
import os
import time
import logging
import json
from typing import List, Optional
from datetime import datetime, timezone

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("rl_api")

# ── MLflow (optional – graceful fallback) ─────────────────────────────────────
MLFLOW_ENABLED = False
try:
    import mlflow
    MLFLOW_ENABLED = True
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "mlruns"))
    mlflow.set_experiment("rl_grid_navigation")
    logger.info("MLflow tracking enabled")
except Exception as e:
    logger.warning(f"MLflow not available – skipping experiment tracking: {e}")

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RL Grid Navigation API",
    description="Q-Learning agent navigation in 6x6 grid (static & dynamic environments)",
    version="1.0.0",
    openapi_url="/openapi.json",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Constants ──────────────────────────────────────────────────────────────────
GRID_SIZE = 6
GOAL = (5, 5)
ACTIONS = ["up", "down", "left", "right"]
ACTION_MAP = {
    "up":    (-1,  0),
    "down":  ( 1,  0),
    "left":  ( 0, -1),
    "right": ( 0,  1),
}

# ── Load Q-tables ──────────────────────────────────────────────────────────────
def load_q_table(filename: str) -> dict:
    try:
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                table = pickle.load(f)
            logger.info(f"Loaded Q-table: {filename} ({len(table)} states)")
            return table
        else:
            logger.warning(f"Q-table not found: {filename} – using empty table")
            return {}
    except Exception as e:
        logger.error(f"Error loading Q-table {filename}: {e}")
        return {}

Q_STATIC  = load_q_table("q_table.pkl")
Q_DYNAMIC = load_q_table("q_table_dynamic.pkl")

# ── Telemetry ─────────────────────────────────────────────────────────────────
_call_count   = 0
_total_latency = 0.0
_drift_log: List[dict] = []

# ── Helpers ───────────────────────────────────────────────────────────────────
def next_state(state: tuple, action: str) -> tuple:
    dx, dy = ACTION_MAP[action]
    ns = (state[0] + dx, state[1] + dy)
    if 0 <= ns[0] < GRID_SIZE and 0 <= ns[1] < GRID_SIZE:
        return ns
    return state


def move_obstacle(obstacle: tuple) -> tuple:
    moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    dx, dy = random.choice(moves)
    np_ = (obstacle[0] + dx, obstacle[1] + dy)
    if 0 <= np_[0] < GRID_SIZE and 0 <= np_[1] < GRID_SIZE:
        return np_
    return obstacle


def safe_action(Q: dict, state: tuple, agent: tuple, obstacle: Optional[tuple]) -> str:
    """Get best action that doesn't hit obstacle AND actually moves the agent"""
    actions = Q.get(state, {a: 0.0 for a in ACTIONS})
    
    if not actions or all(v == 0.0 for v in actions.values()):
        # If all Q-values are zero, pick random safe action that moves
        valid_moves = [a for a in ACTIONS if next_state(agent, a) != agent]
        safe_moves = [a for a in valid_moves if not obstacle or next_state(agent, a) != obstacle]
        if safe_moves:
            return random.choice(safe_moves)
        elif valid_moves:
            return random.choice(valid_moves)
        return random.choice(ACTIONS)
    
    # Sort actions by Q-value (highest first)
    sorted_actions = sorted(actions.items(), key=lambda x: x[1], reverse=True)
    
    # First, try to find a safe action that actually moves
    for act, _ in sorted_actions:
        next_pos = next_state(agent, act)
        if next_pos != agent:  # Action actually moves the agent
            if not obstacle or next_pos != obstacle:
                return act
    
    # If no safe action moves, try any action that moves (even if unsafe)
    for act, _ in sorted_actions:
        if next_state(agent, act) != agent:
            return act
    
    # If really stuck, try any safe action
    for act, _ in sorted_actions:
        if not obstacle or next_state(agent, act) != obstacle:
            return act
    
    # Last resort
    return sorted_actions[0][0]


def best_action(Q: dict, state: tuple) -> str:
    """Get best action, breaking ties randomly to avoid getting stuck"""
    actions = Q.get(state, {a: 0.0 for a in ACTIONS})
    if not actions or all(v == 0.0 for v in actions.values()):
        # If all Q-values are zero (untrained), return a random action
        return random.choice(ACTIONS)
    max_val = max(actions.values())
    best_actions = [a for a, v in actions.items() if v == max_val]
    return random.choice(best_actions)

# ── Models ────────────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    start_x: int = 0
    start_y: int = 0
    obstacle_x: Optional[int] = 2
    obstacle_y: Optional[int] = 2
    env: str = "dynamic"

    @field_validator("start_x", "start_y")
    @classmethod
    def check_grid_bounds(cls, v):
        if not (0 <= v < GRID_SIZE):
            raise ValueError(f"Coordinates must be 0-{GRID_SIZE-1}, got {v}")
        return v

    @field_validator("env")
    @classmethod
    def check_env(cls, v):
        if v not in ("static", "dynamic"):
            raise ValueError("env must be 'static' or 'dynamic'")
        return v


class StepRecord(BaseModel):
    step: int
    agent: List[int]
    obstacle: Optional[List[int]]
    action: str


class PredictResponse(BaseModel):
    env: str
    start: List[int]
    goal: List[int]
    path: List[StepRecord]
    steps: int
    success: bool
    reached_goal: bool
    hit_obstacle: bool
    latency_ms: float
    timestamp: str


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "message": "RL Grid Navigation API is running",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "q_table_static_states":  len(Q_STATIC),
        "q_table_dynamic_states": len(Q_DYNAMIC),
        "total_inferences": _call_count,
        "avg_latency_ms": round(_total_latency / _call_count, 2) if _call_count else 0,
    }


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):

    global _call_count, _total_latency
    t0 = time.perf_counter()

    if (req.start_x, req.start_y) == GOAL:
        raise HTTPException(status_code=400, detail="Start position equals goal position.")

    Q = Q_STATIC if req.env == "static" else Q_DYNAMIC

    agent    = (req.start_x, req.start_y)
    obstacle = (req.obstacle_x, req.obstacle_y) if req.env == "dynamic" else None

    path: List[StepRecord] = []
    reached_goal  = False
    hit_obstacle  = False

    for step in range(50):
        # ✅ FIX 1: move obstacle FIRST
        if obstacle:
            obstacle = move_obstacle(obstacle)

        # state AFTER obstacle moves
        state = (agent, obstacle) if req.env == "dynamic" else agent

        # ✅ FIX 2: Smarter action selection with exploration
        import random
        if random.random() < 0.05:  # Reduced to 5% exploration since we have trained tables
            # Try random action that actually moves the agent
            valid_moves = [a for a in ACTIONS if next_state(agent, a) != agent]
            if valid_moves:
                action = random.choice(valid_moves)
            else:
                action = random.choice(ACTIONS)
        else:
            if req.env == "dynamic":
                action = safe_action(Q, state, agent, obstacle)
            else:
                action = best_action(Q, state)

        next_pos = next_state(agent, action)
        
        # ✅ FIX 3: CHECK FOR OBSTACLE COLLISION BEFORE MOVING
        if obstacle and next_pos == obstacle:
            # Agent hit obstacle - don't move, record collision
            hit_obstacle = True
            action = f"{action} (💥 hit obstacle)"
            
            # Add final step record showing collision
            path.append(StepRecord(
                step=step + 1,
                agent=list(agent),  # Stay at current position
                obstacle=list(obstacle),
                action=action,
            ))
            break  # End episode
        
        # ✅ Move agent if safe
        agent = next_pos

        path.append(StepRecord(
            step=step + 1,
            agent=list(agent),
            obstacle=list(obstacle) if obstacle else None,
            action=action,
        ))

        # Debug log
        logger.info(f"Step {step+1}: agent={agent}, action={action}, obstacle={obstacle}")

        if agent == GOAL:
            reached_goal = True
            break

    latency_ms = (time.perf_counter() - t0) * 1000

    _call_count    += 1
    _total_latency += latency_ms

    _drift_log.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "env": req.env,
        "steps": len(path),
        "success": reached_goal,
        "latency_ms": latency_ms,
    })

    if len(_drift_log) > 200:
        _drift_log.pop(0)

    return PredictResponse(
        env=req.env,
        start=[req.start_x, req.start_y],
        goal=list(GOAL),
        path=path,
        steps=len(path),
        success=reached_goal,
        reached_goal=reached_goal,
        hit_obstacle=hit_obstacle,
        latency_ms=round(latency_ms, 2),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

@app.get("/metrics")
def metrics():
    if not _drift_log:
        return {"message": "No inferences recorded yet."}

    recent = _drift_log[-50:]
    success_rate = sum(r["success"] for r in recent) / len(recent)
    avg_steps    = sum(r["steps"] for r in recent) / len(recent)
    avg_latency  = sum(r["latency_ms"] for r in recent) / len(recent)

    return {
        "success_rate": round(success_rate, 3),
        "avg_steps": round(avg_steps, 2),
        "avg_latency_ms": round(avg_latency, 2),
    }


@app.get("/model-info")
def model_info():
    return {
        "model_type": "Tabular Q-Learning",
        "grid_size": f"{GRID_SIZE}x{GRID_SIZE}",
        "goal": str(GOAL),
        "actions": ACTIONS,
    }
@app.get("/debug-state")
def debug_state(x: int = 0, y: int = 0, ox: int = 2, oy: int = 2, env: str = "dynamic"):
    """Debug: Show Q-values for a specific state"""
    Q = Q_STATIC if env == "static" else Q_DYNAMIC
    agent = (x, y)
    obstacle = (ox, oy) if env == "dynamic" else None
    state = (agent, obstacle) if env == "dynamic" else agent
    
    q_values = Q.get(state, {a: 0.0 for a in ACTIONS})
    
    return {
        "agent": agent,
        "obstacle": obstacle,
        "state": state,
        "q_values": q_values,
        "best_action": max(q_values, key=q_values.get),
        "total_states_in_table": len(Q),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)