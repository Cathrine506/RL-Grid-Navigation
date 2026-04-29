"""
Streamlit Demo App – RL Grid Navigation (Render-compatible)
DEBUGGED VERSION - Fixed animation
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
DELAY = 0.5   # Increased delay for visibility

# ── Terrain ────────────────────────────────────────────────────────────────────
TERRAIN_PRESETS = {
    "Open field": {},
    "Forest":     {(1,1):"🌲",(2,2):"🌲",(3,1):"🌲",(4,3):"🌲"},
    "Rocky":      {(0,3):"🪨",(2,3):"🪨",(3,2):"🪨",(4,1):"🪨"},
    "Swamp":      {(1,0):"🌊",(2,1):"🌊",(3,3):"🌊"},
}

CELL = 72

# ── Initialize ALL session state variables ─────────────────────────────────
def init_session_state():
    if "animating" not in st.session_state:
        st.session_state.animating = False
    if "frame" not in st.session_state:
        st.session_state.frame = 0
    if "path" not in st.session_state:
        st.session_state.path = None
    if "api_data" not in st.session_state:
        st.session_state.api_data = None
    if "extra_obs" not in st.session_state:
        st.session_state.extra_obs = []
    if "terrain" not in st.session_state:
        st.session_state.terrain = {}
    if "visited" not in st.session_state:
        st.session_state.visited = set()
    if "agent_pos" not in st.session_state:
        st.session_state.agent_pos = None
    if "obstacles_pos" not in st.session_state:
        st.session_state.obstacles_pos = set()
    if "current_step_num" not in st.session_state:
        st.session_state.current_step_num = 0
    if "total_steps" not in st.session_state:
        st.session_state.total_steps = 0
    if "current_action" not in st.session_state:
        st.session_state.current_action = ""

init_session_state()

# ── Grid renderer ──────────────────────────────────────────────────────────────
def make_grid(agent, obstacles, visited, terrain):
    rows = []
    for r in range(GRID_SIZE):
        cells = []
        for c in range(GRID_SIZE):
            pos = (r, c)
            
            # ✅ Check for collision (agent and obstacle at same position)
            collision = (pos == agent and pos in obstacles)
            
            if collision:
                bg, icon = "#FF1744", "💥"  # Red flash for collision
            elif pos == GOAL and pos == agent:
                bg, icon = "#43A047", "🏁🚀"
            elif pos == GOAL:
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
                f'background:{bg};border:2px solid #B0BEC5;font-size:22px;'
                f'{"animation: flash 0.5s infinite;" if collision else ""}">'
                f'{icon}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    
    # Add CSS animation for collision effect
    style = """
    <style>
        @keyframes flash {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
    """ if any(pos == agent and pos in obstacles for pos in [(r,c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)]) else ""
    
    return (
        style +
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

with st.sidebar.expander("🔧 Debug Info"):
    st.write(f"API_URL: {API_URL}")
    st.write(f"Animating: {st.session_state.animating}")
    st.write(f"Frame: {st.session_state.frame}")
    st.write(f"Path length: {len(st.session_state.path) if st.session_state.path else 0}")
    st.write(f"Current step: {st.session_state.current_step_num}/{st.session_state.total_steps}")

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🤖 RL Grid Navigation")
st.caption(f"{terrain_name} | {env_choice} | {num_obstacles} obstacles")

grid_ph   = st.empty()
status_ph = st.empty()

# ── Buttons ────────────────────────────────────────────────────────────────────
btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])
run_btn  = btn_col1.button("▶ Run",  type="primary", disabled=st.session_state.animating)
stop_btn = btn_col2.button("⏹ Stop", disabled=not st.session_state.animating)
debug_btn = btn_col3.button("🔍 Debug State", disabled=st.session_state.animating)

if debug_btn:
    st.write("Current Session State:")
    st.json({
        "animating": st.session_state.animating,
        "frame": st.session_state.frame,
        "path_exists": st.session_state.path is not None,
        "path_length": len(st.session_state.path) if st.session_state.path else 0,
        "current_step": st.session_state.current_step_num,
        "total_steps": st.session_state.total_steps,
        "agent_pos": st.session_state.agent_pos,
        "obstacles": list(st.session_state.obstacles_pos) if st.session_state.obstacles_pos else [],
        "visited_count": len(st.session_state.visited),
    })

if stop_btn:
    st.session_state.animating = False
    st.session_state.frame = 0
    st.session_state.path = None
    st.session_state.agent_pos = None
    st.session_state.obstacles_pos = set()
    st.session_state.visited = set()
    st.session_state.current_step_num = 0
    st.session_state.total_steps = 0
    st.session_state.current_action = ""
    st.rerun()

# ── Run: fetch full path once, store, kick off animation ───────────────────────
if run_btn:
    start_pos = (start_x, start_y)
    if start_pos == GOAL:
        st.error("❌ Start cannot equal goal")
        st.stop()

    obstacles = generate_obstacles(num_obstacles, start_pos)
    ox, oy = obstacles[0]

    try:
        with st.spinner("🔄 Fetching path from API..."):
            res = requests.post(
                f"{API_URL}/predict",
                json={
                    "start_x": start_x,
                    "start_y": start_y,
                    "obstacle_x": ox,
                    "obstacle_y": oy,
                    "env": env_choice,
                },
                timeout=30,
            )
            res.raise_for_status()

        data = res.json()
        
        # Debug: Show raw API response
        with st.sidebar.expander("🔧 Raw API Response", expanded=False):
            st.json(data)

        path = data.get("path", [])
        
        if not path:
            st.error(f"❌ API returned empty path. Response: {data}")
            st.stop()

        # Store everything in session state
        st.session_state.path = path
        st.session_state.api_data = data
        st.session_state.extra_obs = [tuple(o) for o in obstacles[1:]]
        st.session_state.terrain = terrain
        st.session_state.visited = set()
        st.session_state.frame = 0
        st.session_state.animating = True
        st.session_state.agent_pos = start_pos
        st.session_state.obstacles_pos = set()
        st.session_state.current_step_num = 0
        st.session_state.total_steps = len(path)
        st.session_state.current_action = "starting"
        
        st.success(f"✅ Path loaded! {len(path)} steps")
        st.rerun()  # Start animation

    except requests.exceptions.ConnectionError:
        st.error(f"❌ Cannot connect to API at `{API_URL}`. Is the backend running?")
    except requests.exceptions.Timeout:
        st.error("❌ API timeout — service may be spun down (Render free tier)")
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ API error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        st.error(f"❌ {type(e).__name__}: {e}")

# ── Animation: one frame per rerun ────────────────────────────────────────────
# ── Animation: one frame per rerun ────────────────────────────────────────────
elif st.session_state.animating and st.session_state.path:
    path = st.session_state.path
    frame = st.session_state.frame
    
    if frame < len(path):
        step = path[frame]
        
        # Extract current positions
        agent = tuple(step["agent"])
        obstacle = step.get("obstacle")
        
        # Build obstacle set
        obs = set()
        if obstacle:
            obs.add(tuple(obstacle))
        obs.update(st.session_state.extra_obs)
        
        # Add previous position to visited (for trail)
        if frame > 0:
            prev_step = path[frame - 1]
            st.session_state.visited.add(tuple(prev_step["agent"]))
        
        # ✅ Check if this step hit obstacle
        is_collision = "hit obstacle" in step.get("action", "").lower() or "💥" in step.get("action", "")
        
        # Update session state
        st.session_state.agent_pos = agent
        st.session_state.obstacles_pos = obs
        st.session_state.current_step_num = frame + 1
        st.session_state.current_action = step["action"]
        
        # Render current state
        trail = st.session_state.visited - {agent}
        
        # ✅ SHOW COLLISION EFFECT
        if is_collision:
            # Flash effect - show agent and obstacle at same position
            # Merge agent and obstacle for visual overlap
            grid_ph.markdown(
                make_grid(agent, obs.union({agent}), trail, st.session_state.terrain),
                unsafe_allow_html=True,
            )
            status_ph.error(
                f"💥 **COLLISION!** Step {frame + 1} | "
                f"Agent at {agent} | "
                f"Obstacle at {obstacle if obstacle else 'unknown'}"
            )
        else:
            grid_ph.markdown(
                make_grid(agent, obs, trail, st.session_state.terrain),
                unsafe_allow_html=True,
            )
            status_ph.info(
                f"🚀 Step **{frame + 1}** / {len(path)}  |  "
                f"Position: {agent}  |  "
                f"Action: **{step['action']}**"
            )
        
        # Show progress
        progress = (frame + 1) / len(path)
        st.progress(progress)
        
        # Advance frame
        st.session_state.frame += 1
        time.sleep(DELAY)
        st.rerun()
    
    else:
        # ── Animation Complete ──────────────────────────────────────────────
        st.session_state.animating = False
        st.session_state.frame = 0
        
        data = st.session_state.api_data
        path = st.session_state.path
        
        # Show final state
        last_step = path[-1]
        final_agent = tuple(last_step["agent"])
        obs = set()
        if last_step.get("obstacle"):
            obs.add(tuple(last_step["obstacle"]))
        obs.update(st.session_state.extra_obs)
        
        st.session_state.visited.add(final_agent)
        
        # ✅ Check if ended with collision
        if data.get("hit_obstacle"):
            # Show collision in final frame
            grid_ph.markdown(
                make_grid(final_agent, obs.union({final_agent}), 
                         st.session_state.visited - {final_agent}, 
                         st.session_state.terrain),
                unsafe_allow_html=True,
            )
        else:
            grid_ph.markdown(
                make_grid(final_agent, obs, 
                         st.session_state.visited - {final_agent}, 
                         st.session_state.terrain),
                unsafe_allow_html=True,
            )
        
        # Metrics
        st.markdown("---")
        st.markdown("### 📊 Results")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Steps", data["steps"])
        c2.metric("Env", data["env"])
        c3.metric("Latency", f"{data['latency_ms']:.1f} ms")
        
        if data["hit_obstacle"]:
            c4.metric("Result", "💥 Collision!")
            status_ph.error("💥 Agent hit an obstacle! Episode ended.")
            st.warning("🚨 The agent collided with a moving obstacle. Try running again!")
        elif data["success"]:
            c4.metric("Result", "✅ Success")
            st.balloons()
            status_ph.success("🏆 Goal reached successfully!")
        else:
            c4.metric("Result", "❌ Failed")
            status_ph.error("❌ Failed to reach goal in 50 steps")
        
        # Show path with collision highlighted
        with st.expander("📋 Full Path Details"):
            st.write(f"Start: {data['start']} → Goal: {data['goal']}")
            for s in path:
                if "hit obstacle" in s.get('action', '').lower() or "💥" in s.get('action', ''):
                    st.error(
                        f"💥 Step {s['step']:2d} | "
                        f"Agent: ({s['agent'][0]},{s['agent'][1]}) | "
                        f"Obstacle: {s.get('obstacle', 'N/A')} | "
                        f"Action: {s['action']}"
                    )
                else:
                    st.text(
                        f"Step {s['step']:2d} | "
                        f"Agent: ({s['agent'][0]},{s['agent'][1]}) | "
                        f"Obstacle: {s.get('obstacle', 'N/A')} | "
                        f"Action: {s['action']}"
                    )
        
        # Reset button
        if st.button("🔄 Run Again", type="primary"):
            st.session_state.animating = False
            st.session_state.path = None
            st.rerun()
# ── Idle state: show initial grid ─────────────────────────────────────────────
else:
    # Reset animation state when idle
    if not st.session_state.animating:
        st.session_state.frame = 0
        st.session_state.path = None
        
    obs_list = generate_obstacles(num_obstacles, (start_x, start_y))
    obs_set = set(obs_list)
    html = make_grid((start_x, start_y), obs_set, set(), terrain)
    grid_ph.markdown(html, unsafe_allow_html=True)
    status_ph.info("👆 Configure settings and click **Run** to start the agent!")