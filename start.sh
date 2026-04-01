#!/bin/bash

echo "Starting OpenClaw services..."

# Start services in background
uvicorn services.task_service:task_app --port 8001 --reload &
uvicorn services.scheduler_service:schedule_app --port 8002 --reload &
uvicorn services.trend_service:trend_app --port 8003 --reload &
uvicorn services.github_service:github_app --port 8004 --reload &

# Wait a bit before starting gateway
sleep 2

uvicorn api_gateway.main:app --port 8000 --reload &

echo "All services started!"