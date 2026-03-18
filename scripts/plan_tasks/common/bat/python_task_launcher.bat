@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
{{PYTHON_COMMAND}} "%SCRIPT_DIR%{{SCRIPT_NAME}}" %*
exit /b %ERRORLEVEL%
