@echo off
echo ========================================
echo Quick Testing Script
echo ========================================
echo.

echo [Step 1/7] Rebuilding API with new code...
docker-compose build api --no-cache
if errorlevel 1 (
    echo ERROR: Failed to build API
    pause
    exit /b 1
)

echo.
echo [Step 2/7] Restarting API service...
docker-compose up -d api
timeout /t 10 /nobreak

echo.
echo [Step 3/7] Testing health endpoint...
curl -s http://localhost:8000/health
echo.

echo.
echo [Step 4/7] Testing readiness endpoint...
curl -s http://localhost:8000/health/ready
echo.

echo.
echo [Step 5/7] Testing API authentication...
echo Without API key (should fail):
curl -s http://localhost:8000/api/v1/anomalies
echo.

echo With API key:
curl -s -H "X-API-Key: your-secret-api-key" http://localhost:8000/api/v1/anomalies
echo.

echo.
echo [Step 6/7] Checking API logs...
docker-compose logs --tail=20 api

echo.
echo [Step 7/7] Service URLs:
echo - API Health: http://localhost:8000/health
echo - API Docs: http://localhost:8000/api/docs
echo - Grafana: http://localhost:3001 (admin/admin)
echo - MLflow: http://localhost:5001
echo - Prometheus: http://localhost:9090
echo.

echo ========================================
echo Testing Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Open Grafana: http://localhost:3001
echo 2. Open API Docs: http://localhost:8000/api/docs
echo 3. Run Streamlit: streamlit run app.py
echo.
pause
