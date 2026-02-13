---
description: maintain changelog when behavior changes
---

# Changelog Maintenance Workflow

1. **Collect context**
   - Run `git status -sb` and `git log -5 --oneline` to capture pending changes and recent commits.
   - Identify which commits introduced user-visible behavior (features, fixes, docs).

2. **Choose the right section**
   - Use `## [Unreleased]` for work not yet tagged; otherwise add/update `## [X.Y.Z] - YYYY-MM-DD`.
   - Follow Keep a Changelog headings (Added, Changed, Fixed, Removed, Documentation).

3. **Draft concise bullets**
   - Summarize impact in one sentence focused on the user.
   - Reference key files with `@filepath#L-L` when clarity helps reviewers.

4. **Mention tags/releases**
   - When preparing a release, add the planned git tag (e.g., `git tag vX.Y.Z`) and date.
   - Ensure the section order matches release chronology (newest first).

5. **Review & validate**
   - Re-read the changelog diff for tone, tense, and formatting consistency.
   - Run `markdownlint`/CI linters if available.

6. **Coordinate with other docs**
   - If the change also affects guides or workflows, update `.windsurf/workflows/update-docs.md` or other references so contributors know the process.
