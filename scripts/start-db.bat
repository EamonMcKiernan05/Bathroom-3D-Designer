@echo off
REM Start the portable PostgreSQL 16 for the Bathroom Designer.
REM On a fresh clone this also extracts the binaries and initialises the data dir.
setlocal
cd /d "%~dp0"

set PGBIN=%~dp0pgsql\pgsql\bin
set PGDATA=%~dp0pgdata
set PGPORT=5432

REM --- extract binaries if missing ---
if not exist "%PGBIN%\pg_ctl.exe" (
  if not exist "%~dp0postgresql-binaries.zip" (
    echo [start-db] Downloading PostgreSQL 16 binaries...
    curl -L -o "%~dp0postgresql-binaries.zip" "https://get.enterprisedb.com/postgresql/postgresql-16.6-1-windows-x64-binaries.zip"
  )
  echo [start-db] Extracting...
  powershell -NoProfile -Command "Expand-Archive -Path '%~dp0postgresql-binaries.zip' -DestinationPath '%~dp0pgsql' -Force"
)

REM --- initdb if missing ---
if not exist "%PGDATA%\PG_VERSION" (
  echo [start-db] Initialising data directory...
  "%PGBIN%\initdb.exe" -D "%PGDATA%" -U postgres -E UTF8 -A trust
)

REM --- start if not running ---
netstat -ano | findstr ":%PGPORT% " | findstr "LISTENING" >nul
if %errorlevel%==0 (
  echo [start-db] PostgreSQL already running on port %PGPORT%.
) else (
  echo [start-db] Starting PostgreSQL on port %PGPORT%...
  powershell -NoProfile -Command "Start-Process -FilePath '%PGBIN%\pg_ctl.exe' -ArgumentList '-D','%PGDATA%','-l','%~dp0pg.log','start' -WindowStyle Hidden"
  timeout /t 3 /nobreak >nul
)

REM --- create role + db if this is a fresh setup ---
"%PGBIN%\psql.exe" -h 127.0.0.1 -p %PGPORT% -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='bathroom'" | findstr "1" >nul
if %errorlevel%==1 (
  "%PGBIN%\psql.exe" -h 127.0.0.1 -p %PGPORT% -U postgres -c "CREATE ROLE bathroom LOGIN PASSWORD 'bathroom';"
  "%PGBIN%\psql.exe" -h 127.0.0.1 -p %PGPORT% -U postgres -c "CREATE DATABASE bathroom_designer OWNER bathroom;"
  echo [start-db] Created bathroom role + bathroom_designer database.
)

echo [start-db] Done. Then run apps\api seed if this is a fresh setup.
endlocal
