#!/bin/bash

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: BSD-3-Clause

# Runs qualcomm-cdi-generator.py on the booted target and validates its
# output. This script lives alongside the LAVA test definition that
# references it (cdi-generate.yaml); LAVA fetches both by cloning this
# repository at the commit under test, so the generator script itself is
# already present on-target under the checkout's repo root.

set -u -o pipefail
set -x

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
GENERATOR="${CDI_GENERATOR:-$REPO_ROOT/qualcomm-cdi-generator.py}"
OUTPUT_DIR="$(mktemp -d /tmp/cdi-lava-test.XXXXXX)"
failures=0
final_result=fail

finish()
{
    status=$?
    trap - EXIT
    if [ "$final_result" = pass ] && [ "$status" -eq 0 ]; then
        lava-test-case cdi-test-complete --result pass
    else
        lava-test-case cdi-test-complete --result fail
        status=1
    fi
    rm -rf -- "$OUTPUT_DIR"
    exit "$status"
}
trap finish EXIT

if [ ! -f "$GENERATOR" ]; then
    lava-test-case cdi-generator-present --result fail
    failures=$((failures + 1))
else
    lava-test-case cdi-generator-present --result pass
fi

if [ "$failures" -eq 0 ] && python3 "$GENERATOR" -d "$OUTPUT_DIR" -v; then
    lava-test-case cdi-generate-run --result pass
else
    lava-test-case cdi-generate-run --result fail
    failures=$((failures + 1))
fi

shopt -s nullglob
json_files=("$OUTPUT_DIR"/run/cdi/*.json)
if [ "${#json_files[@]}" -eq 0 ]; then
    lava-test-case cdi-output-present --result fail
    failures=$((failures + 1))
else
    lava-test-case cdi-output-present --result pass
fi

json_failures=0
for json_file in "${json_files[@]}"; do
    if ! python3 - "$json_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    spec = json.load(source)

if not isinstance(spec, dict):
    raise ValueError("CDI spec must be a JSON object")
if not isinstance(spec.get("cdiVersion"), str):
    raise ValueError("CDI spec has no cdiVersion")
if not str(spec.get("kind", "")).startswith("qualcomm.com/"):
    raise ValueError("CDI spec kind is not in the qualcomm.com namespace")
if not isinstance(spec.get("devices"), list) or not spec["devices"]:
    raise ValueError("CDI spec has no devices")
PY
    then
        json_failures=$((json_failures + 1))
    fi
done
if [ "$json_failures" -eq 0 ] && [ "${#json_files[@]}" -gt 0 ]; then
    lava-test-case cdi-json-valid --result pass
else
    lava-test-case cdi-json-valid --result fail
    failures=$((failures + 1))
fi

if command -v cdi >/dev/null 2>&1; then
    if mkdir -p /etc/cdi /var/run/cdi \
            && cdi validate --spec-dirs "$OUTPUT_DIR/run/cdi"; then
        lava-test-case cdi-schema-valid --result pass
    else
        lava-test-case cdi-schema-valid --result fail
        failures=$((failures + 1))
    fi
else
    lava-test-case cdi-schema-valid --result skip
fi

if [ "$failures" -eq 0 ]; then
    final_result=pass
    exit 0
fi
exit 1
