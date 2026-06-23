#!/bin/bash
# ============================================================================
# Stop XML Tool — double-click to stop the background XML Tool server.
# ============================================================================

cd "$(dirname "$0")" || exit 1

PORT="${XML_UI_PORT:-8799}"

PIDS="$(lsof -nP -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null)"
if [ -z "$PIDS" ]; then
  echo "XML Tool is not running (nothing listening on port ${PORT})."
else
  echo "Stopping XML Tool (PID: ${PIDS})…"
  kill $PIDS 2>/dev/null
  sleep 1
  echo "Stopped."
fi

echo ""
echo "Press any key to close this window…"
read -n 1 -s 2>/dev/null
