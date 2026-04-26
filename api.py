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

# CORS Configuration - allow requests from any origin for demo purposes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Environment constants ──────────────────────────────────────────────────────
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
    """Load Q-table from pickle file. Returns empty dict if file not found."""
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

# ── Inference telemetry (in-memory) ───────────────────────────────────────────
_call_count   = 0
_total_latency = 0.0
_drift_log: List[dict] = []          # last 100 inference results for drift detection

# ── Helper functions ───────────────────────────────────────────────────────────
def next_state(state: tuple, action: str) -> tuple:
    """Get next state given action, staying in bounds."""
    dx, dy = ACTION_MAP[action]
    ns = (state[0] + dx, state[1] + dy)
    if 0 <= ns[0] < GRID_SIZE and 0 <= ns[1] < GRID_SIZE:
        return ns
    return state


def move_obstacle(obstacle: tuple) -> tuple:
    """Move obstacle randomly, staying in bounds."""
    moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    dx, dy = random.choice(moves)
    np_ = (obstacle[0] + dx, obstacle[1] + dy)
    if 0 <= np_[0] < GRID_SIZE and 0 <= np_[1] < GRID_SIZE:
        return np_
    return obstacle


def best_action(Q: dict, state: tuple) -> str:
    """Select best action from Q-table using greedy policy."""
    actions = Q.get(state, {a: 0.0 for a in ACTIONS})
    return max(actions, key=actions.get)

# ── Pydantic models ────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    start_x: int = 0
    start_y: int = 0
    obstacle_x: Optional[int] = 2
    obstacle_y: Optional[int] = 2
    env: str = "dynamic"          # "static" or "dynamic"

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
    """Root endpoint – API info."""
    return {
        "message": "RL Grid Navigation API is running",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    """Liveness probe – used by Docker / monitoring systems."""
    return {
        "status": "ok",
        "q_table_static_states":  len(Q_STATIC),
        "q_table_dynamic_states": len(Q_DYNAMIC),
        "total_inferences": _call_count,
        "avg_latency_ms": round(_total_latency / _call_count, 2) if _call_count else 0,
    }


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """
    Run a single episode from start position using the trained Q-table.

    - **start_x / start_y**: agent starting cell (0-5)
    - **obstacle_x / obstacle_y**: initial obstacle position (dynamic env only)
    - **env**: "static" (no obstacle) or "dynamic" (moving obstacle)
    """
    global _call_count, _total_latency

    t0 = time.perf_counter()

    # --- validate start != goal ---
    if (req.start_x, req.start_y) == GOAL:
        raise HTTPException(status_code=400, detail="Start position equals goal position.")

    Q = Q_STATIC if req.env == "static" else Q_DYNAMIC

    agent    = (req.start_x, req.start_y)
    obstacle = (req.obstacle_x, req.obstacle_y) if req.env == "dynamic" else None

    path: List[StepRecord] = []
    reached_goal  = False
    hit_obstacle  = False

    for step in range(50):
        state  = (agent, obstacle) if req.env == "dynamic" else agent
        action = best_action(Q, state)

        agent = next_state(agent, action)
        if obstacle:
            obstacle = move_obstacle(obstacle)

        path.append(StepRecord(
            step=step + 1,
            agent=list(agent),
            obstacle=list(obstacle) if obstacle else None,
            action=action,
        ))

        if agent == GOAL:
            reached_goal = True
            break
        if obstacle and agent == obstacle:
            hit_obstacle = True
            break

    latency_ms = (time.perf_counter() - t0) * 1000

    # --- telemetry ---
    _call_count    += 1
    _total_latency += latency_ms

    result_record = {
        "ts":          datetime.utcnow().isoformat(),
        "env":         req.env,
        "start":       [req.start_x, req.start_y],
        "steps":       len(path),
        "success":     reached_goal,
        "latency_ms":  latency_ms,
    }
    _drift_log.append(result_record)
    if len(_drift_log) > 200:
        _drift_log.pop(0)

    logger.info(
        f"inference | env={req.env} start=({req.start_x},{req.start_y}) steps={len(path)} success={reached_goal} latency={latency_ms:.1f}ms"
    )

    # --- optional MLflow logging ---
    if MLFLOW_ENABLED:
        try:
            with mlflow.start_run(run_name=f"inference_{_call_count}", nested=True):
                mlflow.log_params({"env": req.env, "start": f"({req.start_x},{req.start_y})"})
                mlflow.log_metrics({"steps": len(path), "success": int(reached_goal), "latency_ms": latency_ms})
        except Exception as e:
            logger.debug(f"MLflow logging skipped: {e}")

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
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/metrics")
def metrics():
    """Aggregated runtime metrics & drift signal."""
    if not _drift_log:
        return {"message": "No inferences recorded yet."}

    recent = _drift_log[-50:]          # last 50 calls
    success_rate = sum(r["success"] for r in recent) / len(recent)
    avg_steps    = sum(r["steps"]   for r in recent) / len(recent)
    avg_latency  = sum(r["latency_ms"] for r in recent) / len(recent)

    # Simple drift flag: success rate drop below 50%
    drift_detected = success_rate < 0.50

    return {
        "total_inferences":       _call_count,
        "recent_window":          len(recent),
        "success_rate":           round(success_rate, 3),
        "avg_steps":              round(avg_steps, 2),
        "avg_latency_ms":         round(avg_latency, 2),
        "drift_detected":         drift_detected,
        "drift_threshold":        0.50,
        "q_table_static_states":  len(Q_STATIC),
        "q_table_dynamic_states": len(Q_DYNAMIC),
    }


@app.get("/model-info")
def model_info():
    """Describe the trained models."""
    return {
        "model_type":       "Tabular Q-Learning",
        "grid_size":        f"{GRID_SIZE}x{GRID_SIZE}",
        "start":            "(0,0)",
        "goal":             str(GOAL),
        "actions":          ACTIONS,
        "static_episodes":  500,
        "dynamic_episodes": 3000,
        "hyperparameters": {
            "alpha":   0.1,
            "gamma":   0.9,
            "epsilon": "0.2 (static) / decaying 1→0.1 (dynamic)",
        },
        "q_table_static_states":  len(Q_STATIC),
        "q_table_dynamic_states": len(Q_DYNAMIC),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
