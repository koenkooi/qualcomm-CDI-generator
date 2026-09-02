#!/usr/bin/env python3

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: BSD-3-Clause

import argparse
from pathlib import Path
import sys

import yaml
import voluptuous  # pylint: disable=import-error
from lava_common.schemas import validate  # pylint: disable=import-error


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate rendered LAVA jobs")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()

    filenames = sorted(args.directory.rglob("*.yaml"))
    if not filenames:
        parser.error(f"no YAML files found under {args.directory}")

    failures = 0
    for filename in filenames:
        try:
            with filename.open("rb") as source:
                job = yaml.safe_load(source)
            validate(job)
            print(f"{filename} is valid")
        except voluptuous.Invalid as error:
            print(f"{filename} is invalid: {error.msg} at {error.path}")
            failures += 1
        except yaml.error.MarkedYAMLError as error:
            print(
                f"{filename} is invalid: {error.problem} at {error.problem_mark}"
            )
            failures += 1
        except OSError as error:
            print(f"{filename} could not be read: {error}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
