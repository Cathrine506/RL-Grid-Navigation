# 🚀 Quick Start Guide

## 1-Minute Local Test

```bash
# Make sure you're in the project directory with:
# - api.py, app.py
# - q_table.pkl, q_table_dynamic.pkl
# - requirements.txt, Dockerfile, docker-compose.yml

# Start everything
docker compose up --build

# Wait for both services to be healthy (~30 seconds)
# Then open:
# 📊 Streamlit UI:  http://localhost:8501
# 📚 API Docs:      http://localhost:8000/docs
# 💚 Health Check:  http://localhost:8000/health
```

**That's it!** Both services run with automatic health checks.

---

## Files You Need ✓

```
your-project/
├── api.py                          (FastAPI backend)
├── app.py                          (Streamlit frontend)
├── q_table.pkl                     (Trained static model)
├── q_table_dynamic.pkl             (Trained dynamic model)
├── requirements.txt                (Dependencies)
├── Dockerfile                      (Container image)
├── docker-compose.yml              (Multi-service setup)
├── render.yaml                     (Cloud deployment)
├── DEPLOYMENT.md                   (Full guide)
└── .github/workflows/ci-cd.yml     (Auto-deploy on push)
```

---

## Troubleshooting

### "Connection refused"
```bash
# Wait 30 seconds for services to start
docker compose logs api
docker compose logs app
```

### "Q-table not found"
```bash
# Copy trained models to project directory
# Or create empty ones for testing:
python -c "import pickle; pickle.dump({}, open('q_table.pkl','wb')); pickle.dump({}, open('q_table_dynamic.pkl','wb'))"
```

### "Port 8501 already in use"
```bash
# Change the port in docker-compose.yml:
# ports:
#   - "8502:8501"  (instead of 8501:8501)
```

---

## Deployment Flow

| Step | Time | Details |
|------|------|---------|
| **Local Test** | 5 min | `docker compose up` |
| **GitHub Setup** | 10 min | Push code, add secrets |
| **Render Deploy** | 3 min | Connect repo, auto-build |
| **Live** | ✓ | App running at `https://rl-grid-app.onrender.com` |

---

## Key Files Overview

### api.py
- FastAPI inference server
- Q-table loading (graceful fallback if missing)
- Endpoints: `/predict`, `/health`, `/metrics`, `/model-info`
- MLflow integration (optional)

### app.py
- Streamlit visualization UI
- Connects to API via `API_URL` env var
- Animated grid, metrics display
- Error handling for connection issues

### docker-compose.yml
- **api** service: Port 8000, FastAPI
- **app** service: Port 8501, Streamlit
- Health check on API every 30s
- Automatic restart on failure

### render.yaml
- Free Render.com deployment
- Two services: `rl-grid-api` + `rl-grid-app`
- Auto-detected by Render
- No credit card needed

---

## Next: Cloud Deployment

See **DEPLOYMENT.md** for full Render.com setup.

**Happy deploying!** 🎉
