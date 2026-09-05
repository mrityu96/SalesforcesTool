#!/bin/bash
# Compatibility launcher for the guarded, cross-platform CML CLI.
#
# Usage:
#   ./app/utilities/fetch-cml.sh ORG MODEL EXACT_VERSION_ID [OUTPUT_FILE]
#
# The exact version is mandatory. Salesforce authentication, ownership
# validation, token refresh, and the primary safe download path are provided by
# app/cml_tool.py rather than duplicated here.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/cml_cli.py" fetch "$@"
