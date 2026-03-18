@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
echo [prepare] launching {{SCRIPT_NAME}}
{{PYTHON_COMMAND}} "%SCRIPT_DIR%{{SCRIPT_NAME}}" %*
exit /b %ERRORLEVEL%
