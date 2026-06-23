#!/bin/bash
# ============================================================================
# Open XML Tool — double-click this file to open the Salesforce Metadata
# XML Compare / Merge / Deduplicate UI.
#
# It starts a tiny local server in the BACKGROUND (so it keeps running even
# after you close this window) and opens the tool in your browser. Run it
# again any time to reopen the tool. To stop it, use "Stop XML Tool.command".
# ============================================================================

cd "$(dirname "$0")" || exit 1

PORT="${XML_UI_PORT:-8799}"
URL="http://127.0.0.1:${PORT}/"
PING="http://127.0.0.1:${PORT}/api/ping"

pause_and_exit() {
  echo ""
  echo "Press any key to close this window…"
  read -n 1 -s 2>/dev/null
  exit "${1:-1}"
}

# 1) Find a Python 3 interpreter.
PY=""
for c in python3 /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "ERROR: Python 3 was not found on this Mac."
  echo "Install it from https://www.python.org/downloads/  (or run: xcode-select --install)"
  pause_and_exit 1
fi

# 2) If the tool is already running, check whether it's the current version.
RUNNING_PING="$(curl -s "$PING" 2>/dev/null)"
if echo "$RUNNING_PING" | grep -q "xml-tool"; then
  CUR_BUILD="$("$PY" xml_tool.py --print-build 2>/dev/null)"
  RUN_BUILD="$(echo "$RUNNING_PING" | sed -n 's/.*"build"[^"]*"\([^"]*\)".*/\1/p')"
  if [ -n "$CUR_BUILD" ] && [ "$CUR_BUILD" = "$RUN_BUILD" ]; then
    echo "XML Tool is already running (latest version). Opening ${URL}"
    open "$URL"
    exit 0
  fi
  echo "A different version of XML Tool is running — restarting with the latest code…"
  OLD_PIDS="$(lsof -nP -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null)"
  [ -n "$OLD_PIDS" ] && kill $OLD_PIDS 2>/dev/null
  sleep 1
fi

# 3) Start the server in the background so it survives this window closing.
mkdir -p logs
echo "Starting XML Tool…"
nohup "$PY" xml_tool.py --no-browser > logs/xml-ui.log 2>&1 &
disown 2>/dev/null

# 4) Wait until it is ready, then open the browser.
for i in $(seq 1 40); do
  if curl -s "$PING" 2>/dev/null | grep -q "xml-tool"; then
    open "$URL"
    echo ""
    echo "XML Tool is running at ${URL}"
    echo "You can close this window — the tool keeps running in the background."
    echo "To stop it later, double-click \"Stop XML Tool.command\"."
    exit 0
  fi
  sleep 0.5
done

# 5) It did not start — show why.
echo ""
echo "ERROR: The XML Tool did not start within 20 seconds."
echo "----- last lines of logs/xml-ui.log -----"
tail -n 25 logs/xml-ui.log 2>/dev/null
pause_and_exit 1
