#!/usr/bin/env python3
"""Compatibility launcher for the guarded CML CLI.

Usage:
    python3 app/utilities/deploy-cml.py ORG MODEL EXACT_VERSION_ID CML_FILE

Unlike the retired standalone implementation, this launcher never chooses the
latest version and never writes directly to Salesforce. It delegates to
cml_cli.py, which uses the same backup and verification core as the web UI.
"""

import sys

from cml_cli import run


if __name__ == "__main__":
    raise SystemExit(run(["deploy", *sys.argv[1:]]))
