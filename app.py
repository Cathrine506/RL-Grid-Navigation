"""
Streamlit Demo App – RL Grid Navigation (Render-compatible)
Supports both localhost and remote API URLs via API_URL env var
"""

import streamlit as st
import requests
import time
import random
import os

# ── Config ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="RL Grid Navigation", page_icon="🤖", layout="wide")

API_URL = os.getenv("API_URL", "http://localhost:8000")

GRID_SIZE = 6
GOAL = (5, 5)
DELAY = 0.3

# ── Terrain ────────────────────────────────────────────────────────────────────
TERRAIN_PRESETS = {
    "Open field": {},
    "Forest": {(1,1):"🌲",(2,2):"🌲",(3,1):"🌲",(4,3):"🌲"},
    "Rocky": {(0,3):"🪨",(2,3):"🪨",(3,2):"🪨",(4,1):"🪨"},
    "Swamp": {(1,0):"🌊",(2,1):"🌊",(3,3):"🌊"},
}

CELL = 72

# ── Grid UI ────────────────────────────────────────────────────────────────────
def make_grid(agent, obstacles, visited, start, terrain):
    rows = []
    for r in range(GRID_SIZE):
        cells = []
        for c in range(GRID_SIZE):
            pos = (r, c)
            if pos == GOAL:
                bg, icon = "#43A047", "🏁"
            elif pos == agent:
                bg, icon = "#1565C0", "🚀"
            elif pos in obstacles:
                bg, icon = "#C62828", "💣"
            elif pos in visited:
                bg, icon = "#FFF9C4", "·"
            elif pos in terrain:
                bg, icon = "#CFD8DC", terrain[pos]
            else:
                bg, icon = "#ECEFF1", ""
            cells.append(
                f'<td style="width:{CELL}px;height:{CELL}px;'
                f'text-align:center;background:{bg};'
                f'border:2px solid #B0BEC5;font-size:22px;">{icon}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return '<table style="border-collapse:collapse;margin:auto;">' + "".join(rows) + "</table>"


# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Settings")
env_choice    = st.sidebar.radio("Environment", ["dynamic", "static"])
col1, col2    = st.sidebar.columns(2)
start_x       = col1.number_input("Row", 0, GRID_SIZE-1, 0)
start_y       = col2.number_input("Col", 0, GRID_SIZE-1, 0)
terrain_name  = st.sidebar.selectbox("Terrain", list(TERRAIN_PRESETS.keys()))
terrain       = TERRAIN_PRESETS[terrain_name]
num_obstacles = st.sidebar.slider("Obstacles", 1, 4, 2)

# Known static path — obstacles must never be placed on these cells
STATIC_PATH = {(0,0),(1,0),(1,1),(1,2),(2,2),(3,2),(4,2),(4,3),(4,4),(5,4),(5,5)}

def generate_obstacles(n, start, avoid_static_path=False):
    obs = set()
    blocked = {start, GOAL}
    if avoid_static_path:
        blocked |= STATIC_PATH
    while len(obs) < n:
        pos = (random.randint(0, GRID_SIZE-1), random.randint(0, GRID_SIZE-1))
        if pos not in blocked:
            obs.add(pos)
    return list(obs)

# ── Session state init ─────────────────────────────────────────────────────────
for key, val in {
    "animating": False,
    "frame": 0,
    "path": [],
    "extra_obs": [],
    "visited": [],
    "api_data": None,
    "start": (0, 0),
    "terrain_snap": {},
    "env_snap": "dynamic",
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("🤖 RL Grid Navigation")
st.caption(f"{terrain_name} | {env_choice} | {num_obstacles} obstacles")

with st.sidebar.expander("🔧 Debug", expanded=False):
    st.code(f"API_URL={API_URL}", language="bash")

run_btn   = st.button("▶ Run Agent", type="primary", disabled=st.session_state.animating)
grid_ph   = st.empty()
status_ph = st.empty()

# ── Button pressed — fetch path from API ───────────────────────────────────────
if run_btn:
    if (start_x, start_y) == GOAL:
        st.error("❌ Start cannot equal goal")
        st.stop()

    obstacles = generate_obstacles(num_obstacles, (start_x, start_y), avoid_static_path=(env_choice == "static"))
    ox, oy = obstacles[0]

    payload = {
        "start_x": start_x, "start_y": start_y,
        "obstacle_x": ox,   "obstacle_y": oy,
        "env": env_choice,
    }

    try:
        status_ph.info("🔄 Fetching path...")
        res = requests.post(f"{API_URL}/predict", json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()

        st.session_state.animating   = True
        st.session_state.frame       = 0
        st.session_state.path        = data["path"]
        st.session_state.extra_obs   = [list(o) for o in obstacles[1:]]
        st.session_state.visited     = []
        st.session_state.api_data    = data
        st.session_state.start       = (start_x, start_y)
        st.session_state.terrain_snap = terrain
        st.session_state.env_snap    = env_choice
        status_ph.empty()
        st.rerun()

    except requests.exceptions.ConnectionError:
        st.error(f"❌ Cannot reach API at `{API_URL}`. Start with: `uvicorn api:app --reload`")
    except requests.exceptions.Timeout:
        st.error("❌ API timed out. Render free tier may be spinning up — try again.")
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ API Error ({e.response.status_code}): {e.response.text}")
    except Exception as e:
        st.error(f"❌ {type(e).__name__}: {e}")

# ── Animation loop — one frame per rerun ──────────────────────────────────────
elif st.session_state.animating:
    path      = st.session_state.path
    frame     = st.session_state.frame
    extra_obs = set(tuple(o) for o in st.session_state.extra_obs)
    _start    = st.session_state.start
    _terrain  = st.session_state.terrain_snap

    if frame < len(path):
        step    = path[frame]
        agent   = tuple(step["agent"])
        obs     = set([tuple(step["obstacle"])]) if step.get("obstacle") else set()
        obs     = obs | extra_obs

        st.session_state.visited.append(list(agent))
        visited = set(tuple(v) for v in st.session_state.visited[:-1])

        html = make_grid(agent, obs, visited, _start, _terrain)
        grid_ph.markdown(html, unsafe_allow_html=True)
        status_ph.info(f"Step {frame + 1} / {len(path)}")

        st.session_state.frame += 1
        time.sleep(DELAY)
        st.rerun()

    else:
        # Animation done — show final state
        data    = st.session_state.api_data
        path    = st.session_state.path
        visited = set(tuple(v) for v in st.session_state.visited)

        last    = path[-1]
        agent   = tuple(last["agent"])
        obs     = set([tuple(last["obstacle"])]) if last.get("obstacle") else set()
        obs     = obs | set(tuple(o) for o in st.session_state.extra_obs)

        html = make_grid(agent, obs, visited - {agent}, st.session_state.start, st.session_state.terrain_snap)
        grid_ph.markdown(html, unsafe_allow_html=True)
        status_ph.empty()

        st.session_state.animating = False

        st.markdown("### 📊 Agent Metrics")
        c1, c2, c3 = st.columns(3)
        c1.metric("Steps",   data["steps"])
        c2.metric("Result",  "✅ Success" if data["success"] else "❌ Failed")
        c3.metric("Latency", f"{data['latency_ms']:.1f} ms")

        if data["hit_obstacle"]:
            st.warning("💣 Hit obstacle!")
        elif data["success"]:
            st.balloons()
            st.success("🏆 Goal reached!")
        else:
            st.error("❌ Failed to reach goal")

        with st.expander("📋 Path Details"):
            for s in path:
                st.text(f"Step {s['step']} → {s['agent']} ({s['action']})")

# ── Idle — show initial grid ───────────────────────────────────────────────────
else:
    obs  = generate_obstacles(num_obstacles, (start_x, start_y), avoid_static_path=(env_choice == "static"))
    html = make_grid((start_x, start_y), set(obs), set(), (start_x, start_y), terrain)
    grid_ph.markdown(html, unsafe_allow_html=True)