@echo off
echo Testing NBA API connection with proxy configuration
echo ===================================================

if "%1"=="--proxy" (
    echo Running with forced proxy
    python scripts/test_proxy.py --proxy
) else if "%1"=="--local" (
    echo Running with forced local connection
    python scripts/test_proxy.py --local
) else (
    echo Running with automatic detection
    python scripts/test_proxy.py
)

echo.
echo Test completed
pause 