# 🚀 Deployment Guide — RL Grid Navigation

Complete step-by-step guide to deploy this RL agent locally and to the cloud.

---

## Quick Start — Local (5 minutes)

### Prerequisites
- Docker + Docker Compose installed
- `q_table.pkl` and `q_table_dynamic.pkl` in project root

### Run Locally
```bash
# Clone/navigate to project directory
cd rl-grid-navigation

# Start both services
docker compose up --build

# Open in browser:
# - Streamlit UI: http://localhost:8501
# - API Docs: http://localhost:8000/docs
# - Health: http://localhost:8000/health
```

That's it! Both services start automatically with proper dependencies and health checks.

---

## Architecture

```
┌──────────────────────────────────┐
│  Streamlit Frontend (port 8501)  │
│  • Grid visualization            │
│  • Parameter controls            │
│  • Real-time animation           │
└────────────┬─────────────────────┘
             │ HTTP POST /predict
             │ (JSON payload)
             ▼
┌──────────────────────────────────┐
│  FastAPI Backend (port 8000)     │
│  • Q-Learning inference          │
│  • Input validation              │
│  • Metrics & monitoring          │
└────────────┬─────────────────────┘
             │
             ▼
        ┌─────────────┐
        │  Q-Tables   │
        │  (pickle)   │
        └─────────────┘
```

---

## Setup Options

### Option 1: Docker Compose (Recommended)

**Best for:** Local development, testing, deployment

```bash
# One command to rule them all
docker compose up --build

# View logs
docker compose logs -f api    # API logs
docker compose logs -f app    # Streamlit logs

# Stop all services
docker compose down

# Rebuild after code changes
docker compose up --build --force-recreate
```

**Health Check:** Automatically monitors API at `GET /health` every 30s.

---

### Option 2: Manual Local Setup (No Docker)

**Best for:** Development, quick testing

```bash
# 1. Create environment
conda create -n rl_env python=3.11.9 -y
conda activate rl_env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Terminal 1 — Start API
uvicorn api:app --reload --port 8000

# 4. Terminal 2 — Start Streamlit
API_URL=http://localhost:8000 streamlit run app.py --server.port 8501
```

**URLs:**
- Streamlit: http://localhost:8501
- API: http://localhost:8000/docs

---

### Option 3: Production Docker (Single Container)

**Best for:** Cloud deployment, minimal resources

```bash
# Build image
docker build -t rl-grid-navigation:latest .

# Run API only (for headless deployment)
docker run -p 8000:8000 \
  -e MLFLOW_TRACKING_URI=mlruns \
  rl-grid-navigation:latest

# Run Streamlit (requires API_URL env var)
docker run -p 8501:8501 \
  -e API_URL=http://api-service:8000 \
  rl-grid-navigation:latest \
  streamlit run app.py --server.port 8501 --server.headless true
```

---

## Cloud Deployment — Render.com (FREE)

Render.com offers **completely free** web services. No credit card required.

### Step 1: Prepare Repository

```bash
# Ensure you have all these files
ls -la
  api.py                     ✓
  app.py                     ✓
  q_table.pkl                ✓
  q_table_dynamic.pkl        ✓
  requirements.txt           ✓
  Dockerfile                 ✓
  render.yaml                ✓
  .github/workflows/ci-cd.yml ✓
```

### Step 2: Push to GitHub

```bash
git add .
git commit -m "Initial deployment"
git push origin main
```

### Step 3: Deploy on Render

1. Go to https://render.com → Sign up (free)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` and creates 2 services:
   - `rl-grid-api` (FastAPI backend)
   - `rl-grid-app` (Streamlit frontend)

### Step 4: Connect Services

After first deploy, copy the API service URL and set it as an environment variable:

1. Go to `rl-grid-app` service → **Environment** → edit `API_URL`
2. Set to: `https://rl-grid-api.onrender.com`
3. **Deploy** to apply changes

### Step 5: Access Your App

- **API Docs**: `https://rl-grid-api.onrender.com/docs`
- **Streamlit App**: `https://rl-grid-app.onrender.com`

**Note:** Free tier services sleep after 15 min of inactivity. First request takes ~30s to wake up.

---

## CI/CD Pipeline (GitHub Actions)

File: `.github/workflows/ci-cd.yml`

Automatically:
1. Lints code (ruff)
2. Tests imports
3. Builds Docker image
4. Pushes to Docker Hub
5. Triggers Render deployment

### Setup

Go to GitHub repo → **Settings** → **Secrets and variables** → **Actions**

Add these secrets:

| Name | Value |
|------|-------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | [Get here](https://hub.docker.com/settings/security) |
| `RENDER_DEPLOY_HOOK_URL` | Render → Service → Settings → Deploy Hook |

Once configured, every push to `main` triggers the full pipeline.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Welcome message |
| `GET` | `/health` | Liveness probe (used by Docker) |
| `POST` | `/predict` | Run one episode |
| `GET` | `/metrics` | Aggregated stats & drift detection |
| `GET` | `/model-info` | Model hyperparameters |

### Example: POST /predict

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "start_x": 0,
    "start_y": 0,
    "obstacle_x": 2,
    "obstacle_y": 2,
    "env": "dynamic"
  }'
```

**Response:**
```json
{
  "env": "dynamic",
  "start": [0, 0],
  "goal": [5, 5],
  "path": [
    { "step": 1, "agent": [1, 0], "obstacle": [2, 3], "action": "down" },
    ...
  ],
  "steps": 8,
  "success": true,
  "reached_goal": true,
  "hit_obstacle": false,
  "latency_ms": 2.34,
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

---

## Monitoring & Metrics

### Health Check
```bash
curl http://localhost:8000/health
```
Returns: API state, Q-table sizes, inference count, avg latency.

### Metrics
```bash
curl http://localhost:8000/metrics
```
Returns: success rate, avg steps, latency, **drift detection** flag.

### Drift Detection
Flags when success rate on last 50 calls drops below 50%.

```json
{
  "total_inferences": 342,
  "success_rate": 0.92,
  "drift_detected": false,
  "drift_threshold": 0.50
}
```

### MLflow (Optional)
```bash
# View training/inference logs locally
mlflow ui --port 5000
# Open http://localhost:5000
```

---

## Troubleshooting

### "Cannot reach API at http://localhost:8000"

**Local setup:**
```bash
# Terminal 1 — start API
uvicorn api:app --reload --port 8000

# Terminal 2 — verify it's running
curl http://localhost:8000/health
```

**Docker:**
```bash
# Check if container is running
docker ps

# View logs
docker compose logs api
```

### "Streamlit not connecting to API"

**Local:**
```bash
API_URL=http://localhost:8000 streamlit run app.py
```

**Docker Compose:**
API_URL is set automatically. Check logs:
```bash
docker compose logs app | grep "API_URL"
```

### "Q-table not found"

API gracefully falls back to empty table. To use trained models:
```bash
cp /path/to/q_table.pkl .
cp /path/to/q_table_dynamic.pkl .

# Then rebuild:
docker compose up --build
```

### Docker build fails

**Clean rebuild:**
```bash
docker compose down -v
docker system prune -a
docker compose up --build
```

### Render deployment stuck

Check build logs: Render → Service → "Deploys" tab → View build output.

Common issues:
- Q-table files missing (create empty ones: `pickle.dump({}, open('q_table.pkl','wb'))`)
- Python version mismatch (Dockerfile uses 3.11.9)
- Missing secrets (check GitHub Actions secrets)

---

## Performance Tuning

| Goal | Solution |
|------|----------|
| Lower latency | Run locally (no network) — typically < 5ms |
| More throughput | Docker: `uvicorn api:app --workers 4` |
| Batch requests | POST `/predict_batch` (custom endpoint) |
| Scale horizontally | Docker Compose: `docker compose up --scale api=3` |

---

## File Reference

| File | Purpose | Location |
|------|---------|----------|
| `api.py` | FastAPI inference server | Root |
| `app.py` | Streamlit UI | Root |
| `q_table.pkl` | Static environment Q-table | Root |
| `q_table_dynamic.pkl` | Dynamic environment Q-table | Root |
| `requirements.txt` | Python dependencies (pinned) | Root |
| `Dockerfile` | Container image definition | Root |
| `docker-compose.yml` | Multi-service orchestration | Root |
| `render.yaml` | Render deployment config | Root |
| `ci-cd.yml` | GitHub Actions pipeline | `.github/workflows/` |
| `RL_Colab_2.ipynb` | Training notebook | Root |

---

## Rollback Strategy

### Docker
```bash
# All tags are saved in Docker Hub — roll back instantly
docker run -p 8000:8000 <username>/rl-grid-navigation:v1.0.0
```

### Render
Render → Service → "Deploys" tab → Click any past deploy → **"Rollback"**

### Q-Tables
Keep versioned copies:
```bash
cp q_table.pkl q_table_v1_backup.pkl
# Later: restore if needed
cp q_table_v1_backup.pkl q_table.pkl
```

---

## Security Checklist

- ✓ CORS enabled for demo (restrict in production: `allow_origins=["https://yourdomain.com"]`)
- ✓ Input validation on all endpoints (Pydantic models)
- ✓ Health checks prevent cascade failures
- ✓ No secrets in code (use env vars: `MLFLOW_TRACKING_URI`, `API_URL`)
- ✓ HTTPS in production (Render auto-provisions SSL)
- ✓ Request timeouts (30s max)

---

## Next Steps

1. **Local testing**: `docker compose up` ✓
2. **GitHub setup**: Push code, add secrets
3. **Render deployment**: Connect repo, wait for build
4. **Monitor**: Check `/metrics` and `/health` endpoints
5. **Iterate**: Update Q-tables, push, auto-deploy

---

## Support

- **API docs**: http://localhost:8000/docs (Swagger UI)
- **Logs**: `docker compose logs -f`
- **Health**: `curl http://localhost:8000/health`
- **Metrics**: `curl http://localhost:8000/metrics`

---

**Happy deploying! 🚀**
