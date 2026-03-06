---
description: Windsurf release workflow
---

# Windsurf Release Workflow

1. **Collect release context**
   - Run `git status -sb` and confirm the working tree only has intentional changes.
   - Review `git log -5 --oneline` plus open PRDs/issues to understand which items are shipping.

2. **Align metadata + docs**
   - Update `CHANGELOG.md` (see `.windsurf/workflows/changelog.md`) and `SPEC_FREEZE.md` so the release scope is documented.
   - Sync any affected docs (`docs/specs/core.md`, `docs/operations/release_process.md`, tutorials) using `.windsurf/workflows/update-docs.md`.
   - If the release ties to PRD tasks, update the matching checklist entry in `tracecore-prd/checklists/` per the PRD Guide memory.

3. **Versioning + tagging prep**
   - Bump `pyproject.toml` (and any mirrored version strings such as `agent_bench/webui/app.py`).
   - Draft the git tag name (`vX.Y.Z`) and record it in `docs/operations/release_process.md` per the release instructions.
   - Ensure the tag annotation will call out key changes and any migration notes.

4. **Test matrix**
   - Run the required suite:
     - `python -m pytest`
     - `python -m ruff check agent_bench`
     - Targeted/feature-specific tests as needed (unit, integration, performance) per `AGENTS.md`.
   - Capture results/screenshots if they must be attached to the release issue.

5. **Bundle + artifact checks**
   - Run `tracecore maintain` or the equivalent maintainer helper to regenerate baselines/artifacts.
   - Run `tracecore tasks validate --registry` and confirm it exits successfully.
   - Verify `tracecore bundle seal` + `tracecore bundle status` succeed for the intended run per the smoother CLI loop expectations.
   - Confirm new artifacts include the correct `spec_version`, `runtime_identity`, and task hashes.

6. **Security & dependency scan**
   - Re-run Dependabot/Snyk summaries or manual `pip list --outdated` if the release introduces new deps.
   - Document any security/privacy review outcomes if telemetry/signing/bundle logic changed.

7. **CI + tag**
   - Push the release branch and ensure GitHub Actions are green for the full matrix (`ci.yml`, release checks, docs, dashboard build, etc.).
   - Once CI is green, create the annotated tag (`git tag -a vX.Y.Z -m "TraceCore vX.Y.Z"`) and push it (`git push origin vX.Y.Z`).
   - Verify the tag appears on GitHub and note it in the release checklist.

8. **Publish + verify**
   - Rely on the GitHub Release workflow (`.github/workflows/release.yml`) to build wheels/sdists and run `uv publish` with the repo’s `PYPI_API_TOKEN`.
   - Once the workflow finishes, confirm PyPI, docs hosting, and dashboard assets reflect the new version; open the packaged CLI to ensure `tracecore --version` reports the tag.
   - Re-run `python -m pytest` (smoke) or `tracecore run --replay-bundle` if the release process requires post-publish validation.

9. **Post-release bookkeeping**
   - Update roadmap/status docs (`docs/reference/project_positioning.md`, relevant issues) to mark the release as shipped.
   - Capture learnings or TODOs for the next milestone in the appropriate board or PRD.
   - Verify CI status once more after tags/publish, then share release notes internally.
