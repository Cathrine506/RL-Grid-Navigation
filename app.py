"""
Streamlit Demo App – RL Grid Navigation (Render-compatible)
Supports both localhost and remote API URLs via API_URL env var

ANIMATION FIX: Uses st.session_state + st.rerun() instead of time.sleep()
loop, which causes only the final frame to render on deployed environments.
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
DELAY = 0.25

# ── Terrain ────────────────────────────────────────────────────────────────────
TERRAIN_PRESETS = {
    "Open field": {},
    "Forest":     {(1,1):"🌲",(2,2):"🌲",(3,1):"🌲",(4,3):"🌲"},
    "Rocky":      {(0,3):"🪨",(2,3):"🪨",(3,2):"🪨",(4,1):"🪨"},
    "Swamp":      {(1,0):"🌊",(2,1):"🌊",(3,3):"🌊"},
}

CELL = 72

# ── Session state init ─────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "animating":   False,
        "frame_index": 0,
        "path":        [],
        "data":        None,
        "extra_obs":   set(),
        "start":       (0, 0),
        "terrain":     {},
        "visited":     [],   # list of sets, one per frame
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Grid UI ────────────────────────────────────────────────────────────────────
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
                f'<td style="width:{CELL}px;height:{CELL}px;'
                f'text-align:center;background:{bg};'
                f'border:2px solid #B0BEC5;font-size:22px;">{icon}</td>'
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
        pos = (random.randint(0, GRID_SIZE-1), random.randint(0, GRID_SIZE-1))
        if pos != start and pos != GOAL:
            obs.add(pos)
    return list(obs)

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Settings")

env_choice    = st.sidebar.radio("Environment", ["dynamic", "static"])
col1, col2    = st.sidebar.columns(2)
start_x       = col1.number_input("Row", 0, GRID_SIZE-1, 0)
start_y       = col2.number_input("Col", 0, GRID_SIZE-1, 0)
terrain_name  = st.sidebar.selectbox("Terrain", list(TERRAIN_PRESETS.keys()))
terrain       = TERRAIN_PRESETS[terrain_name]
num_obstacles = st.sidebar.slider("Obstacles", 1, 4, 2)

with st.sidebar.expander("🔧 Debug", expanded=False):
    st.code(f"API_URL={API_URL}", language="bash")

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🤖 RL Grid Navigation")
st.caption(f"{terrain_name} | {env_choice} | {num_obstacles} obstacles")

grid_ph   = st.empty()
status_ph = st.empty()

# ── Run button ─────────────────────────────────────────────────────────────────
run_btn = st.button(
    "▶ Run Agent",
    type="primary",
    disabled=st.session_state.animating,
)

# ── Handle Run ─────────────────────────────────────────────────────────────────
if run_btn:
    if (start_x, start_y) == GOAL:
        st.error("❌ Start cannot equal goal")
        st.stop()

    obstacles = generate_obstacles(num_obstacles, (start_x, start_y))
    ox, oy    = obstacles[0]

    payload = {
        "start_x":    start_x,
        "start_y":    start_y,
        "obstacle_x": ox,
        "obstacle_y": oy,
        "env":        env_choice,
    }

    try:
        with st.spinner("🔄 Fetching path from API…"):
            res = requests.post(
                f"{API_URL}/predict",
                json=payload,
                timeout=30,
            )
            res.raise_for_status()
        data = res.json()

        # Pre-compute visited sets per frame for smooth animation
        path     = data["path"]
        visited  = []
        seen     = set()
        for step in path:
            seen.add(tuple(step["agent"]))
            visited.append(frozenset(seen))

        extra_obs = set(tuple(o) for o in obstacles[1:])

        # Store everything in session_state and start animation
        st.session_state.animating   = True
        st.session_state.frame_index = 0
        st.session_state.path        = path
        st.session_state.visited     = visited
        st.session_state.data        = data
        st.session_state.extra_obs   = extra_obs
        st.session_state.start       = (start_x, start_y)
        st.session_state.terrain     = terrain

    except requests.exceptions.ConnectionError:
        st.error(
            f"❌ **Connection Error** — cannot reach API at `{API_URL}`\n\n"
            f"Local: `uvicorn api:app --reload`\n"
            f"Render: verify the API service is running and URL is correct."
        )
    except requests.exceptions.Timeout:
        st.error(f"❌ **Timeout** — API at `{API_URL}` took too long. "
                 f"Free-tier Render services may be spun down.")
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ **API Error** ({e.response.status_code})\n\n{e.response.text}")
    except Exception as e:
        st.error(f"❌ **Unexpected Error** — {type(e).__name__}: {e}")

# ── Animation loop (one frame per rerun) ───────────────────────────────────────
if st.session_state.animating:
    idx  = st.session_state.frame_index
    path = st.session_state.path

    if idx < len(path):
        step    = path[idx]
        agent   = tuple(step["agent"])
        api_obs = {tuple(step["obstacle"])} if step.get("obstacle") else set()
        obs     = api_obs | st.session_state.extra_obs
        visited_so_far = st.session_state.visited[idx] - {agent}

        html = make_grid(agent, obs, visited_so_far, st.session_state.terrain)
        grid_ph.markdown(html, unsafe_allow_html=True)
        status_ph.info(f"Step {idx + 1} / {len(path)} — action: **{step['action']}**")

        st.session_state.frame_index += 1
        time.sleep(DELAY)
        st.rerun()                          # ← key fix: forces a real re-render

    else:
        # Animation done — show final frame + results
        data = st.session_state.data

        last    = path[-1]
        agent   = tuple(last["agent"])
        api_obs = {tuple(last["obstacle"])} if last.get("obstacle") else set()
        obs     = api_obs | st.session_state.extra_obs
        html    = make_grid(agent, obs, st.session_state.visited[-1] - {agent},
                            st.session_state.terrain)
        grid_ph.markdown(html, unsafe_allow_html=True)

        # Metrics
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
            status_ph.error("❌ Failed to reach goal")

        with st.expander("📋 Path Details"):
            for s in path:
                st.text(f"Step {s['step']} → {s['agent']} ({s['action']})")

        st.session_state.animating = False   # re-enable Run button

else:
    # Idle — show initial grid
    obs  = generate_obstacles(num_obstacles, (start_x, start_y))
    html = make_grid((start_x, start_y), obs, set(), terrain)
    grid_ph.markdown(html, unsafe_allow_html=True)