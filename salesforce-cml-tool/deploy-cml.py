#!/usr/bin/env python3
"""
deploy-cml.py — Deploy CML source code to a Salesforce org

Usage:
    python3 scripts/deploy-cml.py <orgAlias> <versionId> <cmlFilePath>
    python3 scripts/deploy-cml.py <orgAlias> --model <modelName> <cmlFilePath>

Examples:
    python3 scripts/deploy-cml.py tigerDev 9QBbZ0000000eezWAA ./TestConstraint_V1.cml
    python3 scripts/deploy-cml.py catalogGold --model TestConstraint ./TestConstraint_V1.cml

The second form auto-discovers the Version ID by querying the org for the model name.
"""

import sys
import json
import base64
import ssl
import subprocess
import urllib.request
import urllib.error


def run_sf_command(args):
    """Run an sf CLI command and return parsed JSON output."""
    result = subprocess.run(
        args, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: sf command failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def get_org_credentials(org_alias):
    """Retrieve access token and instance URL for the given org."""
    print(f"==> Authenticating to '{org_alias}'...")
    data = run_sf_command([
        "sf", "org", "display", "--target-org", org_alias, "--json"
    ])
    return data["result"]["accessToken"], data["result"]["instanceUrl"]


def find_version_id(org_alias, model_name):
    """Query the org to find the latest ExpressionSetDefinitionVersion ID."""
    print(f"==> Looking up '{model_name}' in '{org_alias}'...")
    query = (
        f"SELECT Id, DeveloperName, VersionNumber, Status "
        f"FROM ExpressionSetDefinitionVersion "
        f"WHERE ExpressionSetDefinition.DeveloperName = '{model_name}' "
        f"ORDER BY VersionNumber DESC LIMIT 1"
    )
    data = run_sf_command([
        "sf", "data", "query", "--query", query,
        "--target-org", org_alias, "--json"
    ])
    records = data["result"]["records"]
    if not records:
        print(f"ERROR: No version found for '{model_name}' in '{org_alias}'.", file=sys.stderr)
        sys.exit(1)

    rec = records[0]
    print(f"    Found: {rec['DeveloperName']} ({rec['Id']}) — Status: {rec['Status']}")
    return rec["Id"]


def deploy_cml(token, instance_url, version_id, cml_file_path):
    """Upload a CML file to the ConstraintModel blob field."""
    print(f"==> Reading CML from '{cml_file_path}'...")
    with open(cml_file_path, "r", encoding="utf-8") as f:
        cml_content = f.read()

    line_count = cml_content.count("\n") + 1
    print(f"    File has {line_count} lines.")

    cml_b64 = base64.b64encode(cml_content.encode("utf-8")).decode("utf-8")
    payload = json.dumps({"ConstraintModel": cml_b64}).encode("utf-8")

    url = f"{instance_url}/services/data/v66.0/sobjects/ExpressionSetDefinitionVersion/{version_id}"
    req = urllib.request.Request(url, data=payload, method="PATCH")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    print(f"==> Deploying to {version_id}...")
    ctx = ssl.create_default_context()
    try:
        resp = urllib.request.urlopen(req, context=ctx)
        if resp.status == 204:
            print("")
            print("SUCCESS — CML deployed to org.")
            print(f"    Version ID : {version_id}")
            print(f"    Source File: {cml_file_path}")
            print("")
        else:
            print(f"Unexpected HTTP {resp.status}: {resp.read().decode('utf-8')}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"\nFAILED — HTTP {e.code}", file=sys.stderr)
        print(body, file=sys.stderr)
        sys.exit(1)


def print_usage():
    print(__doc__)
    sys.exit(1)


def main():
    if len(sys.argv) < 4:
        print_usage()

    org_alias = sys.argv[1]

    if sys.argv[2] == "--model":
        if len(sys.argv) < 5:
            print_usage()
        model_name = sys.argv[3]
        cml_file = sys.argv[4]
        token, instance_url = get_org_credentials(org_alias)
        version_id = find_version_id(org_alias, model_name)
    else:
        version_id = sys.argv[2]
        cml_file = sys.argv[3]
        token, instance_url = get_org_credentials(org_alias)

    deploy_cml(token, instance_url, version_id, cml_file)


if __name__ == "__main__":
    main()
