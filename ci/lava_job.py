#!/usr/bin/env python3

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


PLACEHOLDER_RE = re.compile(r"{{[^{}]+}}")
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
REVISION_RE = re.compile(r"[0-9a-f]{40}")
SUITE_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")


def normalize_build_url(value: str) -> str:
    if not value:
        raise ValueError(
            "No build URL supplied; set CDI_TEST_BUILD_DOWNLOAD_URL or use "
            "the workflow_dispatch build_download_url input"
        )
    if value != value.strip() or any(char in value for char in '"\\\r\n'):
        raise ValueError("The build URL contains unsupported characters")

    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "The build URL must be an HTTPS base URL without credentials, "
            "a query, or a fragment"
        )
    return value.rstrip("/")


def validate_suite(value: str) -> str:
    if not SUITE_RE.fullmatch(value):
        raise ValueError(
            "The suite must start with a lowercase letter or digit and contain "
            "only lowercase letters, digits, dots, underscores, or hyphens"
        )
    return value


def render_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for placeholder, value in replacements.items():
        if "\n" in value or "\r" in value:
            raise ValueError(f"{placeholder} contains a newline")
        rendered = rendered.replace("{{" + placeholder + "}}", value)

    unresolved = sorted(set(PLACEHOLDER_RE.findall(rendered)))
    if unresolved:
        raise ValueError(
            "Unresolved LAVA template placeholders: " + ", ".join(unresolved)
        )
    return rendered


def validate_render_arguments(args: argparse.Namespace) -> dict[str, str]:
    build_url = normalize_build_url(args.build_download_url)
    suite = validate_suite(args.suite)
    if not REPOSITORY_RE.fullmatch(args.repository):
        raise ValueError("The repository must have owner/name form")
    if not REVISION_RE.fullmatch(args.revision):
        raise ValueError("The revision must be a lowercase 40-character commit SHA")
    if not args.run_id.isdigit() or not args.run_attempt.isdigit():
        raise ValueError("The run ID and run attempt must be decimal integers")

    return {
        "BUILD_DOWNLOAD_URL": build_url,
        "SUITE": suite,
        "GITHUB_REPOSITORY": args.repository,
        "GITHUB_SHA": args.revision,
        "GITHUB_RUN_ID": args.run_id,
        "GITHUB_RUN_ATTEMPT": args.run_attempt,
    }


def validate_configuration(args: argparse.Namespace) -> None:
    build_url = normalize_build_url(args.build_download_url)
    suite = validate_suite(args.suite)
    if args.require_lava_token and not os.environ.get("LAVA_TOKEN"):
        raise ValueError("The LAVATOKEN Actions secret is not configured")

    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"build_download_url={build_url}\n")
            output.write(f"suite={suite}\n")


def render_job(args: argparse.Namespace) -> None:
    replacements = validate_render_arguments(args)
    template = args.template.read_text(encoding="utf-8")
    rendered = render_template(template, replacements)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and render LAVA jobs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--build-download-url", required=True)
    validate_parser.add_argument("--suite", required=True)
    validate_parser.add_argument("--require-lava-token", action="store_true")
    validate_parser.add_argument("--github-output", type=Path)
    validate_parser.set_defaults(handler=validate_configuration)

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--template", required=True, type=Path)
    render_parser.add_argument("--output", required=True, type=Path)
    render_parser.add_argument("--build-download-url", required=True)
    render_parser.add_argument("--suite", required=True)
    render_parser.add_argument("--repository", required=True)
    render_parser.add_argument("--revision", required=True)
    render_parser.add_argument("--run-id", required=True)
    render_parser.add_argument("--run-attempt", required=True)
    render_parser.set_defaults(handler=render_job)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
