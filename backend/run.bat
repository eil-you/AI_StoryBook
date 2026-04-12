@echo off
:: Sets PYTHONPATH to the backend folder so "import app" always resolves,
:: regardless of which directory the terminal was launched from.
set PYTHONPATH=%~dp0
call "%~dp0.venv\Scripts\activate.bat"
uvicorn app.main:app --reload --port 8000
