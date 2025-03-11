@echo off
echo Finding NBA API calls that need to be updated
echo ===================================================

python scripts/update_remaining_api_calls.py

echo.
echo Scan completed
pause 