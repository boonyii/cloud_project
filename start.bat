@echo off
echo Starting OpenClaw services...

start "Task Service" cmd /k "py -m uvicorn services.task_service:task_app --port 8001 --reload"
start "Scheduler Service" cmd /k "py -m uvicorn services.scheduler_service:schedule_app --port 8002 --reload"
start "Trend Service" cmd /k "py -m uvicorn services.trend_service:trend_app --port 8003 --reload"
start "GitHub Service" cmd /k "py -m uvicorn services.github_service:github_app --port 8004 --reload"

timeout /t 2 /nobreak > nul

start "API Gateway" cmd /k "py -m uvicorn api_gateway.main:app --port 8000 --reload"

echo All services started!
