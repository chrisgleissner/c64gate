# CI Release Plan

## Objective

Make the repository releasable by driving GitHub Actions on `main` to green, then validating the exact Docker image produced by GitHub locally without rebuilding it. Final proof requires a successful Chrome Playwright HTTPS call to `/v1/version` on the CI-built image with HTTP 200, JSON returned, and no TLS warnings.

## Current CI Status

- Branch: `main`
- Local HEAD: `83d74d5b841c29465f50b53267a235f892770c24`
- Current GitHub Actions run: `failed on amd64 smoke, arm64 still in progress at inspection time`
- Current run URL: `https://github.com/chrisgleissner/c64gate/actions/runs/23113861979`
- Most recent completed failed run URL: `https://github.com/chrisgleissner/c64gate/actions/runs/23113274140`
- Last confirmed failure signature: `ModuleNotFoundError: No module named 'yaml'` in the traceability step

## Root Cause Investigations

1. Confirmed prior CI failures were caused by running `tools/check_traceability.py` outside the project virtualenv on the GitHub runner, which omitted `PyYAML` from the active interpreter.
2. Confirmed the runtime currently serves `/api/version` but does not serve `/v1/version`, which means the repository does not yet satisfy the required browser validation path.
3. Confirmed the workflow already exports an amd64 Docker image tarball artifact, but it does not currently persist digest metadata needed for exact artifact-to-local verification.
4. Confirmed the first pushed verification run for commit `d6f128793146ae036e5cc1680ea603c4a82014b3` passed `source-validation` but failed `image-validation (linux/amd64)` during smoke with `AssertionError: control plane did not become healthy` after a fixed 30-second readiness window.
5. The most likely root cause is runner-specific startup latency during first-boot TLS/runtime initialization rather than a deterministic functional failure, because local smoke and full local `./build ci` both passed against the same code path.

## Ordered Task List

- [x] Inspect current GitHub CI state and capture failing run evidence.
- [x] Rewrite `PLANS.md` into an execution document for the CI/image validation mission.
- [x] Add `/v1/version` support at the runtime source and update automated coverage.
- [x] Persist CI image digest metadata alongside the uploaded Docker artifact.
- [x] Run narrow local validation for the changed runtime and smoke paths.
- [ ] Commit and push the fixes to `main`.
- [ ] Wait for GitHub Actions to complete and inspect the exact run results.
- [ ] Push the smoke-timeout remediation and rerun GitHub Actions.
- [ ] Download the CI-produced amd64 image artifact locally.
- [ ] Load the downloaded artifact into Docker without rebuilding.
- [ ] Verify the local image digest matches the CI-recorded digest.
- [ ] Start the CI-produced image locally and run Chrome Playwright against `https://127.0.0.1:<port>/v1/version`.
- [ ] Record final evidence here: CI run URL, image digest, and Playwright logs.

## Work Log

- 2026-03-15T15:51:34+00:00 Inspected repository guidance, architecture, workflow definition, and repo CI notes. Verified that the latest completed CI failures were caused by traceability running outside `.venv`, verified that the current `main` workflow run is still active, and identified two remaining release blockers in the codebase: missing `/v1/version` support and missing persisted CI digest metadata.
- 2026-03-15T15:53:54+00:00 Added `/v1/version` support in the simulated REST backend and HTTPS facade, updated runtime/Caddy/smoke coverage, and added CI artifact metadata files for image identity and tarball checksum. Focused validation passed with `./build lint`, targeted integration tests, a fresh `docker build -t c64gate:0.0.1 .`, and the smoke test against `https://127.0.0.1:<port>/v1/version`.
- 2026-03-15T15:54:41+00:00 Completed the broader local CI-equivalent validation with `./build ci`. Results: formatting clean, lint clean, 41 tests passed with 1 expected skip, total Python coverage 90.13%, smoke image validation passed, and traceability validated 20 requirement rows.
- 2026-03-15T15:59:46+00:00 Pushed commit `d6f128793146ae036e5cc1680ea603c4a82014b3` and inspected GitHub Actions run `23113861979`. `source-validation` passed, but `image-validation (linux/amd64)` failed in smoke because the control plane did not become healthy within the prior 30-second readiness loop. Hardened the smoke test to allow up to 90 seconds on slower runners, capture the last HTTP/TLS detail, and include a container log tail in failures. Also changed image artifact upload to `if: always()` so the next CI loop preserves debugging artifacts on failure. Local validation after the fix passed with `./build lint` and the smoke test against `c64gate:0.0.1`.

## Risks And Assumptions

- Assumption: GitHub CLI authentication remains valid for reading workflow status, downloading artifacts, and pushing commits.
- Assumption: The `image-validation (linux/amd64)` job continues to be the authoritative source for the locally downloaded artifact.
- Risk: The current in-progress run may complete before the code changes needed for `/v1/version` and digest persistence are merged, which would require another push-and-verify loop.
- Risk: Local Chrome Playwright validation depends on Chrome being available in the environment and on the generated local CA/SPKI pin strategy remaining compatible with the CI-produced image.
- Risk: Multi-architecture build behavior under QEMU can still fail independently from amd64 smoke success, so both matrix legs must be observed before declaring CI green.

## Verification Steps

1. Run focused local tests that cover the added `/v1/version` behavior and smoke expectations.
2. Commit and push the workflow/runtime changes to `main`.
3. Wait for the GitHub Actions run on the pushed commit to finish green.
4. Download the GitHub-produced amd64 image artifact from that run.
5. Load the artifact with Docker and compare the local image digest to the digest recorded by CI.
6. Start the loaded image locally without rebuilding.
7. Launch Chrome via Playwright and call `https://127.0.0.1:<port>/v1/version`.
8. Record HTTP status, JSON payload, browser console output, and TLS result here.
