#!/bin/bash
# ==============================================================================
# fetch-cml.sh — Fetch CML source code from a Salesforce org
#
# Usage:
#   ./scripts/fetch-cml.sh <orgAlias> <constraintModelName> [outputFile]
#
# Examples:
#   ./scripts/fetch-cml.sh tigerDev TestConstraint
#   ./scripts/fetch-cml.sh catalogGold PCM_Constraint_Model ./my-model.cml
# ==============================================================================

set -euo pipefail

if [ $# -lt 2 ]; then
    echo ""
    echo "Usage: $0 <orgAlias> <constraintModelName> [outputFile]"
    echo ""
    echo "  orgAlias             Salesforce org alias (e.g., tigerDev, catalogGold)"
    echo "  constraintModelName  DeveloperName of the Expression Set (e.g., TestConstraint)"
    echo "  outputFile           (Optional) Output file path. Defaults to <name>_V<n>.cml"
    echo ""
    exit 1
fi

ORG_ALIAS="$1"
MODEL_NAME="$2"
OUTPUT_FILE="${3:-}"

echo "==> Querying ${MODEL_NAME} in org '${ORG_ALIAS}'..."

VERSION_INFO=$(sf data query \
    --query "SELECT Id, DeveloperName, VersionNumber, Status FROM ExpressionSetDefinitionVersion WHERE ExpressionSetDefinition.DeveloperName = '${MODEL_NAME}' ORDER BY VersionNumber DESC LIMIT 1" \
    --target-org "${ORG_ALIAS}" \
    --json 2>/dev/null)

RECORD_COUNT=$(echo "$VERSION_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['totalSize'])")

if [ "$RECORD_COUNT" -eq 0 ]; then
    echo "ERROR: No Expression Set Version found for '${MODEL_NAME}' in org '${ORG_ALIAS}'."
    exit 1
fi

VERSION_ID=$(echo "$VERSION_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['records'][0]['Id'])")
DEV_NAME=$(echo "$VERSION_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['records'][0]['DeveloperName'])")
STATUS=$(echo "$VERSION_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['records'][0]['Status'])")

echo "    Found: ${DEV_NAME} (${VERSION_ID}) — Status: ${STATUS}"

if [ -z "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="${DEV_NAME}.cml"
fi

echo "==> Getting access token..."
ORG_INFO=$(sf org display --target-org "${ORG_ALIAS}" --json 2>/dev/null)
ACCESS_TOKEN=$(echo "$ORG_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['accessToken'])")
INSTANCE_URL=$(echo "$ORG_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['instanceUrl'])")

echo "==> Downloading CML from ${INSTANCE_URL}..."
HTTP_CODE=$(curl -s -o "${OUTPUT_FILE}" -w "%{http_code}" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    "${INSTANCE_URL}/services/data/v66.0/sobjects/ExpressionSetDefinitionVersion/${VERSION_ID}/ConstraintModel")

if [ "$HTTP_CODE" -eq 200 ]; then
    LINE_COUNT=$(wc -l < "${OUTPUT_FILE}" | tr -d ' ')
    echo ""
    echo "SUCCESS — CML saved to: ${OUTPUT_FILE} (${LINE_COUNT} lines)"
    echo ""
else
    echo ""
    echo "FAILED — HTTP ${HTTP_CODE}. Check your org connection and try again."
    cat "${OUTPUT_FILE}"
    echo ""
    exit 1
fi
