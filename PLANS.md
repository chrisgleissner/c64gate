# GHCR Tag Publish Plan

## Objective

Make GitHub build and publish a Docker image to GHCR when tag `0.0.1` is pushed, then pull that published image locally, start it without rebuilding, and verify the C64U REST API is reachable via HTTPS.

## Current CI Status

- Branch: `main`
- Local HEAD: `d420b7f3a49d99fe0ace35e0307872c3480774e4`
- Current workflow trigger coverage: branch pushes, pull requests, and tag `0.0.1`
- Current publish status: tag workflow published `ghcr.io/chrisgleissner/c64gate:0.0.1`
- Requested tag to use: `0.0.1`

## Root Cause Investigations

1. Confirmed `.github/workflows/ci.yml` does not include any `push.tags` trigger, so a Git tag cannot start a workflow run.
2. Confirmed the repository has no GHCR publish step or registry login step, so even if a tag-triggered workflow ran, no image would be uploaded.
3. Confirmed the existing workflow already builds and validates an amd64 image path suitable for publishing, so the change should extend the current workflow rather than replace it.

## Ordered Task List

- [x] Inspect the existing workflow and confirm why tag pushes do not publish images.
- [x] Update `PLANS.md` for the GHCR tag-publish mission.
- [x] Add tag trigger and GHCR publish job to GitHub Actions.
- [x] Validate the updated workflow syntax locally.
- [x] Commit and push the workflow changes to `main`.
- [x] Create or refresh tag `0.0.1` on the intended commit and push it.
- [x] Wait for the tag-triggered publish workflow to finish green.
- [x] Pull `ghcr.io/chrisgleissner/c64gate:0.0.1` locally.
- [x] Start the published image locally without rebuilding.
- [x] Verify HTTPS access to `/v1/version` from the published image.
- [x] Record final GHCR evidence here.

## Work Log

- 2026-03-15T16:47:11+00:00 Re-scoped the execution plan from CI artifact validation to GHCR tag publishing. Verified that the only active workflow is `CI`, it does not trigger on tags, and it contains no GHCR login or push step. Confirmed the requested tag to use is `0.0.1`.
- 2026-03-15T16:49:07+00:00 Updated `.github/workflows/ci.yml` to trigger on tag `0.0.1` and added a pinned `publish-image` job that logs into GHCR, builds a multi-architecture image, pushes `ghcr.io/chrisgleissner/c64gate:0.0.1`, and uploads the published digest/reference as artifacts. Validated the workflow structure locally with `PyYAML` using `BaseLoader` to preserve the `on` key.
- 2026-03-15T17:06:11+00:00 Committed the workflow change on `main`, pushed tag `0.0.1`, and verified the tag-triggered workflow run `23114819724` completed successfully. Downloaded the publish artifact, confirmed the published digest `sha256:11a68b693572a23bea760e2f543a6e9bffbe25a77276c9f46e0a857e2284c39b`, pulled `ghcr.io/chrisgleissner/c64gate:0.0.1`, and verified the pulled repo digest matched exactly. Started the published image locally on `https://127.0.0.1:57425` and validated `/v1/version` with Chrome via Playwright using the generated certificate SPKI pin. The browser result returned HTTP 200 with `{"device":"c64u-sim","transport":"https-relay","version":"0.0.1"}` and recorded no console errors, page errors, failed requests, or TLS warnings.

## Risks And Assumptions

- Assumption: The repository token available to GitHub Actions will permit publishing to `ghcr.io/chrisgleissner/c64gate` when `packages: write` permission is granted.
- Assumption: Tag `0.0.1` is the desired release tag and may need to be created or force-updated after the workflow change is merged.
- Risk: GHCR package visibility or namespace settings may require one additional repository-side adjustment even after the workflow is correct.
- Risk: Pulling from GHCR locally may require `docker login ghcr.io` with the GitHub CLI token if the package defaults to private visibility.

## Verification Steps

1. Push workflow changes that add `push.tags` support and GHCR publish logic.
2. Push tag `0.0.1` and verify a workflow run starts from the tag.
3. Confirm the run publishes `ghcr.io/chrisgleissner/c64gate:0.0.1`.
4. Pull that published image locally.
5. Start the pulled image without rebuilding.
6. Reach `https://127.0.0.1:<port>/v1/version` and confirm the HTTPS REST path answers successfully.

## Final Verification Evidence

- Tag workflow run URL: `https://github.com/chrisgleissner/c64gate/actions/runs/23114819724`
- Published image reference: `ghcr.io/chrisgleissner/c64gate:0.0.1`
- Published image digest: `sha256:11a68b693572a23bea760e2f543a6e9bffbe25a77276c9f46e0a857e2284c39b`
- Pulled local repodigest: `ghcr.io/chrisgleissner/c64gate@sha256:11a68b693572a23bea760e2f543a6e9bffbe25a77276c9f46e0a857e2284c39b`
- Local GHCR runtime endpoint: `https://127.0.0.1:57425/v1/version`
- Playwright result artifact: `artifacts/ghcr-run-23114819724/playwright-ghcr-v1-version.json`
- Browser validation result: `ok=true`, `status=200`, `consoleErrors=[]`, `pageErrors=[]`, `failedRequests=[]`
