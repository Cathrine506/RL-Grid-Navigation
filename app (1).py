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

# Support Render deployment: API_URL from environment, fallback to localhost
API_URL = os.getenv("API_URL", "http://localhost:8000")

GRID_SIZE = 6
GOAL = (5, 5)
DELAY = 0.25

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
    """Generate HTML grid visualization."""
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

env_choice = st.sidebar.radio("Environment", ["dynamic", "static"])

col1, col2 = st.sidebar.columns(2)
start_x = col1.number_input("Row", 0, GRID_SIZE-1, 0)
start_y = col2.number_input("Col", 0, GRID_SIZE-1, 0)

terrain_name = st.sidebar.selectbox("Terrain", list(TERRAIN_PRESETS.keys()))
terrain = TERRAIN_PRESETS[terrain_name]

num_obstacles = st.sidebar.slider("Obstacles", 1, 4, 2)

# ── Auto obstacle generator ─────────────────────────────────────────────────────
def generate_obstacles(n, start):
    """Generate random obstacles avoiding start and goal."""
    obs = set()
    while len(obs) < n:
        pos = (random.randint(0, GRID_SIZE-1), random.randint(0, GRID_SIZE-1))
        if pos != start and pos != GOAL:
            obs.add(pos)
    return list(obs)

# ── UI Header ───────────────────────────────────────────────────────────────────
st.title("🤖 RL Grid Navigation")
st.caption(f"{terrain_name} | {env_choice} | {num_obstacles} obstacles")

# Debug info: show which API we're connecting to
with st.sidebar.expander("🔧 Debug", expanded=False):
    st.code(f"API_URL={API_URL}", language="bash")
    st.info(f"**API Status**: Checking {API_URL}/health")

run_btn = st.button("▶ Run Agent", type="primary")

grid_ph = st.empty()
status_ph = st.empty()

# ── Initial grid ────────────────────────────────────────────────────────────────
def show_idle():
    """Display initial state."""
    obs = generate_obstacles(num_obstacles, (start_x, start_y))
    html = make_grid((start_x, start_y), obs, set(), (start_x, start_y), terrain)
    grid_ph.markdown(html, unsafe_allow_html=True)

show_idle()

# ── Run agent ───────────────────────────────────────────────────────────────────
if run_btn:
    if (start_x, start_y) == GOAL:
        st.error("❌ Start cannot equal goal")
        st.stop()

    obstacles = generate_obstacles(num_obstacles, (start_x, start_y))
    ox, oy = obstacles[0]  # API uses only one obstacle

    payload = {
        "start_x": start_x,
        "start_y": start_y,
        "obstacle_x": ox,
        "obstacle_y": oy,
        "env": env_choice,
    }

    try:
        with st.spinner("🔄 Running agent..."):
            t0 = time.perf_counter()
            res = requests.post(
                f"{API_URL}/predict",
                json=payload,
                timeout=30,
                verify=True
            )
            res.raise_for_status()
            client_ms = (time.perf_counter() - t0) * 1000

        data = res.json()
        path = data["path"]
        steps = data["steps"]

        visited = set()

        # Extra obstacles (beyond the one tracked by the API) stay fixed for display
        extra_obs = set(tuple(o) for o in obstacles[1:])

        # Animate path
        for step in path:
            agent = tuple(step["agent"])
            obs = set([tuple(step["obstacle"])]) if step.get("obstacle") else set()
            obs = obs | extra_obs  # combine moving obstacle with extra static ones

            visited.add(agent)

            html = make_grid(agent, obs, visited - {agent}, (start_x, start_y), terrain)
            grid_ph.markdown(html, unsafe_allow_html=True)
            time.sleep(DELAY)

        # ── Metrics (AUTO SHOWN) ───────────────────────────────────────────────
        st.markdown("### 📊 Agent Metrics")
        c1, c2, c3 = st.columns(3)
        c1.metric("Steps", steps)
        c2.metric("Result", "✅ Success" if data["success"] else "❌ Failed")
        c3.metric("Latency", f"{data['latency_ms']:.1f} ms")

        # ── Status ─────────────────────────────────────────────────────────────
        if data["hit_obstacle"]:
            status_ph.warning("💣 Hit obstacle!")
        elif data["success"]:
            st.balloons()
            status_ph.success("🏆 Goal reached!")
        else:
            status_ph.error("❌ Failed to reach goal")

        # ── Path log ───────────────────────────────────────────────────────────
        with st.expander("📋 Path Details"):
            for s in path:
                st.text(f"Step {s['step']} → {s['agent']} ({s['action']})")

    except requests.exceptions.ConnectionError as e:
        st.error(
            f"❌ **Connection Error**\n\n"
            f"Cannot reach API at: `{API_URL}`\n\n"
            f"**Local setup:** Start FastAPI with:\n"
            f"```bash\nuvicorn api:app --reload\n```\n\n"
            f"**Render deployment:** Check that the API service is running and the URL is correct."
        )
    except requests.exceptions.Timeout:
        st.error(
            f"❌ **Timeout**\n\n"
            f"API at `{API_URL}` took too long to respond.\n\n"
            f"If using Render free tier, the service may have been spun down."
        )
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ **API Error** ({e.response.status_code})\n\n{e.response.text}")
    except Exception as e:
        st.error(f"❌ **Unexpected Error**\n\n{type(e).__name__}: {str(e)}")
