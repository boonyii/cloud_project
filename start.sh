#!/bin/bash

echo "Starting OpenClaw services..."

# -----------------------------
# Load environment variables
# -----------------------------
export $(grep -v '^#' .env | xargs)

echo "Loaded environment variables"

# -----------------------------
# Start microservices
# -----------------------------
uvicorn services.task_service:task_app --port 8001 --reload &
uvicorn services.scheduler_service:schedule_app --port 8002 --reload &
uvicorn services.trend_service:trend_app --port 8003 --reload &
uvicorn services.github_service:github_app --port 8004 --reload &
uvicorn agent.llm_decision_engine:decision_app --port 8005 --reload &
uvicorn services.vibe_service:vibe_app --port 8006 --reload &


# -----------------------------
# Wait before starting gateway
# -----------------------------
sleep 2

# API Gateway
uvicorn api_gateway.main:app --port 8000 --reload &

echo "All services started!"
echo "API Gateway → http://localhost:8000"
echo "Recommendation → http://localhost:8000/recommendation"
echo "Vibe Coding → http://localhost:8000/vibe"