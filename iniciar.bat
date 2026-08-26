@echo off
setlocal
cd /d "%~dp0"
set "APP_PYTHON=.venv\Scripts\python.exe"

if not exist "%APP_PYTHON%" (
  echo Preparando o SignTime pela primeira vez...
  py -3 -m venv .venv
)

"%APP_PYTHON%" -c "import docxtpl, openpyxl, pandas, sqlalchemy, psycopg, dotenv, argon2" >nul 2>&1
if errorlevel 1 (
  echo Instalando os componentes necessarios...
  "%APP_PYTHON%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Nao foi possivel concluir a instalacao.
    pause
    exit /b 1
  )
)

"%APP_PYTHON%" app.py
if errorlevel 1 pause
endlocal
