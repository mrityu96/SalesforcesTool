@echo off
REM Windows launcher. Double-click this file (or run it) to start the XML Tool.
REM It opens your browser automatically. Close this window to stop the tool.
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
  python xml_tool.py
  goto :eof
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 xml_tool.py
  goto :eof
)

echo ERROR: Python 3 was not found. Install it from https://www.python.org/downloads/
echo Make sure to tick "Add Python to PATH" during installation.
pause
