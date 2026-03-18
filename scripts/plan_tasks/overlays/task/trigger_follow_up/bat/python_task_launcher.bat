@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
echo [trigger-follow-up] launching {{SCRIPT_NAME}}
{{PYTHON_COMMAND}} "%SCRIPT_DIR%{{SCRIPT_NAME}}" %*
exit /b %ERRORLEVEL%
