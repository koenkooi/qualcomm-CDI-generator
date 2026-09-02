# List of workflows and actions
This folder contains workflows that are helpful for maintaining a smooth and secure development process. The workflows should be enabled for open-source projects.

Workflows:
1. `ci.yml` - Runs Python 3.8 and current-Python tests, CDI schema validation, setuptools and Meson package builds, static checks, and DCO sign-off checks. Pull requests use a pinned CDI release; the weekly scheduled run checks compatibility with the latest release.
2. `qcom-preflight-checks.yml` - Runs copyright, email, repolinter, dependency review, Semgrep, and other policy checks. See [qualcomm/qcom-reusable-workflows](https://github.com/qualcomm/qcom-reusable-workflows).
3. `stale-issues.yaml` - Runs weekly, marks unexempt issues and pull requests stale after 90 days of inactivity, and closes them after they have remained stale for at least 7 days.
4. `lava-schema-check.yml` - Reusable validation for rendered job templates under `ci/lava/`. `ci.yml` calls it for pull requests, and `lava-hardware.yml` calls it before job submission.
5. `lava-test.yml` - Reusable three-board matrix that validates its inputs, renders each LAVA job without modifying the checkout, and waits for the hardware result. Failed test cases and incomplete or canceled LAVA jobs fail the GitHub Actions job.
6. `lava-hardware.yml` - Runs the schema gate and real-hardware matrix on pushes to `main`, daily at 07:15 UTC, or manually. Scheduled and push runs use the `CDI_TEST_BUILD_DOWNLOAD_URL` repository variable; manual runs may override the URL and Debian suite.
