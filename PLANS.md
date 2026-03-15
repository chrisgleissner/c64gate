# GHCR Tag Publish Plan

## Objective

Make GitHub build and publish a Docker image to GHCR when tag `0.0.1` is pushed, then pull that published image locally, start it without rebuilding, and verify the C64U REST API is reachable via HTTPS.

## Current CI Status

- Branch: `main`
- Local HEAD: `518f861d0b7f49d4fac20a2bab5595be069190b5`
- Current workflow trigger coverage: branch pushes and pull requests only
- Current publish status: no GHCR publish job exists, so tag pushes cannot publish `ghcr.io/chrisgleissner/c64gate`
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
- [ ] Commit and push the workflow changes to `main`.
- [ ] Create or refresh tag `0.0.1` on the intended commit and push it.
- [ ] Wait for the tag-triggered publish workflow to finish green.
- [ ] Pull `ghcr.io/chrisgleissner/c64gate:0.0.1` locally.
- [ ] Start the published image locally without rebuilding.
- [ ] Verify HTTPS access to `/v1/version` from the published image.
- [ ] Record final GHCR evidence here.

## Work Log

- 2026-03-15T16:47:11+00:00 Re-scoped the execution plan from CI artifact validation to GHCR tag publishing. Verified that the only active workflow is `CI`, it does not trigger on tags, and it contains no GHCR login or push step. Confirmed the requested tag to use is `0.0.1`.
- 2026-03-15T16:49:07+00:00 Updated `.github/workflows/ci.yml` to trigger on tag `0.0.1` and added a pinned `publish-image` job that logs into GHCR, builds a multi-architecture image, pushes `ghcr.io/chrisgleissner/c64gate:0.0.1`, and uploads the published digest/reference as artifacts. Validated the workflow structure locally with `PyYAML` using `BaseLoader` to preserve the `on` key.

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
