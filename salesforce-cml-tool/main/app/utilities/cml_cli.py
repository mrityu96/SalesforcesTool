#!/usr/bin/env python3
"""Guarded command-line adapter for the CML Tool application core.

This module intentionally contains no Salesforce implementation. Fetch and
deploy operations delegate to app/cml_tool.py so exact-version validation,
credential refresh, backups, deployment locks, rollback, reports, and
post-write verification cannot drift from the UI.
"""

import argparse
import importlib.util
import pathlib
import shutil
import sys


APP_DIR = pathlib.Path(__file__).resolve().parents[1]
CORE_PATH = APP_DIR / "cml_tool.py"


def load_core():
    spec = importlib.util.spec_from_file_location("cml_tool_cli_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load CML Tool core from {CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_parser():
    parser = argparse.ArgumentParser(
        description="Use the CML Tool's guarded fetch/deploy core.")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser(
        "fetch", help="Fetch one exact CML version.")
    fetch.add_argument("org", help="Authorized Salesforce org alias")
    fetch.add_argument("model", help="Constraint Model developer name")
    fetch.add_argument("version_id", help="Exact definition version Id")
    fetch.add_argument(
        "output", nargs="?",
        help="Optional additional output path; the core always keeps its safe copy")

    deploy = commands.add_parser(
        "deploy", help="Deploy through backup and verification safeguards.")
    deploy.add_argument("org", help="Authorized Salesforce target org alias")
    deploy.add_argument("model", help="Constraint Model developer name")
    deploy.add_argument("version_id", help="Exact target definition version Id")
    deploy.add_argument("file", help="CML file to deploy")
    return parser


def _print_result(result):
    stream = sys.stdout if result.get("ok") else sys.stderr
    print(result.get("log") or (
        "Operation succeeded." if result.get("ok") else "Operation failed."),
          file=stream)
    if result.get("file"):
        print(f"File: {result['file']}", file=stream)
    if result.get("backup", {}).get("file"):
        print(f"Recovery backup: {result['backup']['file']}", file=stream)
    if result.get("report", {}).get("file"):
        print(f"Deployment report: {result['report']['file']}", file=stream)


def run(argv=None, input_fn=input):
    args = build_parser().parse_args(argv)
    core = load_core()

    if args.command == "fetch":
        result = core.fetch_cml(args.org, args.model, args.version_id)
        _print_result(result)
        if not result.get("ok") and not result.get("empty"):
            return 1
        if args.output:
            destination = pathlib.Path(args.output).expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result["file"], destination)
            print(f"Additional copy: {destination}")
        return 0

    source = pathlib.Path(args.file).expanduser()
    if not source.is_file():
        print(f"CML file does not exist: {source}", file=sys.stderr)
        return 1
    content = source.read_text(encoding="utf-8")
    if not content.strip():
        print("Deployment blocked: the selected CML file is empty.",
              file=sys.stderr)
        return 1

    print(
        f'Deploy "{args.model}" to org "{args.org}" exact version '
        f'"{args.version_id}"?')
    typed = input_fn(
        f'Type the target org alias exactly to continue ({args.org}): ').strip()
    if typed != args.org:
        print("Deployment cancelled: target org alias did not match.",
              file=sys.stderr)
        return 1

    result = core.deploy_cml(
        args.org, args.model, args.version_id, content,
        confirm_target=typed)
    _print_result(result)
    return 0 if result.get("ok") else 1


def main():
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
