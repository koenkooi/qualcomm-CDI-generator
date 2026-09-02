# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Tests for LAVA job rendering and on-target result propagation."""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_SCRIPT = REPO_ROOT / "ci/lava-tests/cdi-generate/run.sh"


def _load_lava_job_module():
    script = REPO_ROOT / "ci/lava_job.py"
    spec = importlib.util.spec_from_file_location("lava_job", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lava_job = _load_lava_job_module()


class LavaJobRenderingTests(unittest.TestCase):
    def test_normalize_build_url(self):
        self.assertEqual(
            lava_job.normalize_build_url("https://example.com/build/1/"),
            "https://example.com/build/1",
        )

    def test_rejects_unsafe_build_url(self):
        for url in (
            "",
            "http://example.com/build",
            "https://user@example.com/build",
            "https://example.com/build?token=value",
            "https://example.com/build\nother",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                lava_job.normalize_build_url(url)

    def test_render_rejects_unresolved_placeholders(self):
        with self.assertRaisesRegex(ValueError, "unresolved-placeholder"):
            lava_job.render_template(
                "{{GITHUB_SHA}} {{unresolved-placeholder}}",
                {"GITHUB_SHA": "a" * 40},
            )


class LavaRunScriptTests(unittest.TestCase):
    def run_script(self, generator_body, cdi_status=0):
        with tempfile.TemporaryDirectory() as directory:
            tempdir = Path(directory)
            bin_dir = tempdir / "bin"
            bin_dir.mkdir()
            results = tempdir / "lava-results.txt"

            lava_test_case = bin_dir / "lava-test-case"
            lava_test_case.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$LAVA_RESULTS"\n',
                encoding="utf-8",
            )
            lava_test_case.chmod(0o755)

            cdi = bin_dir / "cdi"
            cdi.write_text(
                f"#!/bin/sh\nexit {cdi_status}\n",
                encoding="utf-8",
            )
            cdi.chmod(0o755)

            mkdir = bin_dir / "mkdir"
            mkdir.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            mkdir.chmod(0o755)

            generator = tempdir / "generator.py"
            generator.write_text(generator_body, encoding="utf-8")

            env = os.environ.copy()
            env["CDI_GENERATOR"] = str(generator)
            env["LAVA_RESULTS"] = str(results)
            env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
            completed = subprocess.run(
                ["bash", str(RUN_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            return completed, results.read_text(encoding="utf-8")

    @staticmethod
    def successful_generator():
        spec = {
            "cdiVersion": "0.8.0",
            "kind": "qualcomm.com/gpu",
            "devices": [{"name": "renderD128", "containerEdits": {}}],
        }
        return (
            "import json, pathlib, sys\n"
            "root = pathlib.Path(sys.argv[sys.argv.index('-d') + 1])\n"
            "output = root / 'run/cdi/qualcomm-gpu.json'\n"
            "output.parent.mkdir(parents=True)\n"
            f"output.write_text({json.dumps(json.dumps(spec))}, encoding='utf-8')\n"
        )

    def test_success_requires_output_and_finishes_with_pass(self):
        completed, results = self.run_script(self.successful_generator())
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("cdi-output-present --result pass", results)
        self.assertIn("cdi-json-valid --result pass", results)
        self.assertTrue(results.rstrip().endswith("cdi-test-complete --result pass"))

    def test_zero_outputs_fail(self):
        completed, results = self.run_script("raise SystemExit(0)\n")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("cdi-output-present --result fail", results)
        self.assertTrue(results.rstrip().endswith("cdi-test-complete --result fail"))

    def test_generator_failure_propagates(self):
        completed, results = self.run_script("raise SystemExit(2)\n")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("cdi-generate-run --result fail", results)
        self.assertTrue(results.rstrip().endswith("cdi-test-complete --result fail"))

    def test_invalid_json_propagates(self):
        generator = (
            "import pathlib, sys\n"
            "root = pathlib.Path(sys.argv[sys.argv.index('-d') + 1])\n"
            "output = root / 'run/cdi/invalid.json'\n"
            "output.parent.mkdir(parents=True)\n"
            "output.write_text('{', encoding='utf-8')\n"
        )
        completed, results = self.run_script(generator)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("cdi-json-valid --result fail", results)
        self.assertTrue(results.rstrip().endswith("cdi-test-complete --result fail"))

    def test_schema_failure_propagates(self):
        completed, results = self.run_script(
            self.successful_generator(),
            cdi_status=1,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("cdi-schema-valid --result fail", results)
        self.assertTrue(results.rstrip().endswith("cdi-test-complete --result fail"))


if __name__ == "__main__":
    unittest.main()
