"""
Streamlit Demo App – RL Grid Navigation (Render-compatible)

ANIMATION: Uses session_state + st.rerun() — one frame per script run.
The run button fetches the full path from the API once, stores it in
session_state, then each st.rerun() renders exactly one more frame.
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
DELAY = 0.3   # seconds between frames

# ── Terrain ────────────────────────────────────────────────────────────────────
TERRAIN_PRESETS = {
    "Open field": {},
    "Forest":     {(1,1):"🌲",(2,2):"🌲",(3,1):"🌲",(4,3):"🌲"},
    "Rocky":      {(0,3):"🪨",(2,3):"🪨",(3,2):"🪨",(4,1):"🪨"},
    "Swamp":      {(1,0):"🌊",(2,1):"🌊",(3,3):"🌊"},
}

CELL = 72

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in {
    "animating":  False,
    "frame":      0,
    "path":       None,
    "api_data":   None,
    "extra_obs":  [],
    "terrain":    {},
    "visited":    set(),
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Grid renderer ──────────────────────────────────────────────────────────────
def make_grid(agent, obstacles, visited, terrain):
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
                f'<td style="width:{CELL}px;height:{CELL}px;text-align:center;'
                f'background:{bg};border:2px solid #B0BEC5;font-size:22px;">'
                f'{icon}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<table style="border-collapse:collapse;margin:auto;">'
        + "".join(rows)
        + "</table>"
    )

# ── Helpers ────────────────────────────────────────────────────────────────────
def generate_obstacles(n, start):
    obs = set()
    while len(obs) < n:
        pos = (random.randint(0, GRID_SIZE - 1), random.randint(0, GRID_SIZE - 1))
        if pos != start and pos != GOAL:
            obs.add(pos)
    return list(obs)

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Settings")
env_choice    = st.sidebar.radio("Environment", ["dynamic", "static"], key="env")
col1, col2    = st.sidebar.columns(2)
start_x       = col1.number_input("Row", 0, GRID_SIZE - 1, 0, key="sx")
start_y       = col2.number_input("Col", 0, GRID_SIZE - 1, 0, key="sy")
terrain_name  = st.sidebar.selectbox("Terrain", list(TERRAIN_PRESETS.keys()), key="terrain_name")
terrain       = TERRAIN_PRESETS[terrain_name]
num_obstacles = st.sidebar.slider("Obstacles", 1, 4, 2, key="n_obs")

with st.sidebar.expander("🔧 Debug"):
    st.code(f"API_URL={API_URL}")
    st.write(f"frame={st.session_state.frame}, animating={st.session_state.animating}")

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🤖 RL Grid Navigation")
st.caption(f"{terrain_name} | {env_choice} | {num_obstacles} obstacles")

grid_ph   = st.empty()
status_ph = st.empty()

# ── Buttons ────────────────────────────────────────────────────────────────────
btn_col1, btn_col2 = st.columns([1, 5])
run_btn  = btn_col1.button("▶ Run",  type="primary", disabled=st.session_state.animating)
stop_btn = btn_col2.button("⏹ Stop", disabled=not st.session_state.animating)

if stop_btn:
    st.session_state.animating = False
    st.session_state.frame     = 0
    st.session_state.path      = None
    st.rerun()

# ── Run: fetch full path once, store, kick off animation ───────────────────────
if run_btn:
    if (start_x, start_y) == GOAL:
        st.error("❌ Start cannot equal goal")
        st.stop()

    obstacles = generate_obstacles(num_obstacles, (start_x, start_y))
    ox, oy    = obstacles[0]

    try:
        with st.spinner("🔄 Fetching path…"):
            res = requests.post(
                f"{API_URL}/predict",
                json={
                    "start_x":    start_x,
                    "start_y":    start_y,
                    "obstacle_x": ox,
                    "obstacle_y": oy,
                    "env":        env_choice,
                },
                timeout=30,
            )
            res.raise_for_status()

        data = res.json()

        if not data.get("path"):
            st.error("❌ API returned empty path.")
            st.stop()

        st.session_state.path      = data["path"]
        st.session_state.api_data  = data
        st.session_state.extra_obs = [tuple(o) for o in obstacles[1:]]
        st.session_state.terrain   = terrain
        st.session_state.visited   = set()
        st.session_state.frame     = 0
        st.session_state.animating = True
        st.rerun()  # start animation immediately

    except requests.exceptions.ConnectionError:
        st.error(f"❌ Cannot connect to API at `{API_URL}`")
    except requests.exceptions.Timeout:
        st.error("❌ API timeout — service may be spun down (Render free tier)")
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ API error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        st.error(f"❌ {type(e).__name__}: {e}")

# ── Animation: one frame per rerun ────────────────────────────────────────────
# ── Animation: one frame per rerun ────────────────────────────────────────────
elif st.session_state.animating and st.session_state.path:
    path  = st.session_state.path
    frame = st.session_state.frame

    if frame < len(path):
        step  = path[frame]
        agent = tuple(step["agent"])
        obs   = set()
        if step.get("obstacle"):
            obs.add(tuple(step["obstacle"]))
        obs.update(st.session_state.extra_obs)

        # Update visited set and add current agent position
        if frame > 0:
            prev_step = path[frame-1]
            st.session_state.visited.add(tuple(prev_step["agent"]))
        
        st.session_state.visited.add(agent)
        trail = st.session_state.visited - {agent}

        # Display current frame
        grid_ph.markdown(
            make_grid(agent, obs, trail, st.session_state.terrain),
            unsafe_allow_html=True,
        )
        status_ph.info(
            f"Step **{frame + 1}** / {len(path)} — action: **{step['action']}**"
        )

        # Advance frame counter
        st.session_state.frame += 1
        time.sleep(DELAY)
        st.rerun()  # render next frame

    else:
        # ── Done ──────────────────────────────────────────────────────────────
        st.session_state.animating = False

        data  = st.session_state.api_data
        path  = st.session_state.path
        last  = path[-1]
        agent = tuple(last["agent"])
        obs   = set()
        if last.get("obstacle"):
            obs.add(tuple(last["obstacle"]))
        obs.update(st.session_state.extra_obs)

        grid_ph.markdown(
            make_grid(agent, obs, st.session_state.visited - {agent}, st.session_state.terrain),
            unsafe_allow_html=True,
        )

        st.markdown("### 📊 Agent Metrics")
        c1, c2, c3 = st.columns(3)
        c1.metric("Steps",   data["steps"])
        c2.metric("Result",  "✅ Success" if data["success"] else "❌ Failed")
        c3.metric("Latency", f"{data['latency_ms']:.1f} ms")

        if data["hit_obstacle"]:
            status_ph.warning("💣 Hit obstacle!")
        elif data["success"]:
            st.balloons()
            status_ph.success("🏆 Goal reached!")
        else:
            status_ph.error("❌ Failed to reach goal in 50 steps")

        with st.expander("📋 Path Details"):
            for s in path:
                st.text(f"Step {s['step']} → {s['agent']} ({s['action']})")

# ── Idle ──────────────────────────────────────────────────────────────────────
else:
    obs  = generate_obstacles(num_obstacles, (start_x, start_y))
    html = make_grid((start_x, start_y), obs, set(), terrain)
    grid_ph.markdown(html, unsafe_allow_html=True)