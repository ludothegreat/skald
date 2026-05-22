# Small TBDs

Things small enough that they don't deserve their own brainstorm question, but worth tracking so they don't get forgotten when implementation starts.

- **App icon / branding assets** — Need a `.png` / `.ico` / `.svg` for the OS launcher, AppImage, Windows installer, and macOS (later). Suggested vibe: a stylized harp / lyre or a runestone, matching the "skald" name and the terracotta accent. Generate or commission before the first public release.
- **README structure** — Standard sections: badges, screenshots (once GUI exists), what-it-is, install (per-OS), usage (GUI + CLI), keyboard shortcuts table, supported formats, config-file reference, building from source, license. Generate from this brainstorm doc when starting on the project.
- **AppImage build runner image** — Decide whether to use `appimage-builder` or `python-appimage` in CI. Pick when wiring CI.
- ~~**Verify gitforge → GitHub mirror pushes tags**, not just branches~~ — **done 2026-05-22**. Patched `/hoard/workspace/gitforge-manager/app.py` so the post-receive hook detects tag refs and runs `git push --tags` to GitHub. Verified end-to-end with `v0.0.0-mirror-test`. Note: the hook propagates tag *creates* but not tag *deletes* — fine for release tags, but be aware if a tag ever needs to be retracted (delete it on GitHub separately via `gh api -X DELETE`).
- **Commit the gitforge-manager patch to its own repo** — the change in `/hoard/workspace/gitforge-manager/app.py` (adding `changed_tags` tracking and a `git push --tags` block) is currently uncommitted. Ludo: commit and push to the gitforge-manager canonical repo so the change survives.
- **Verify the terracotta accent (`#C45A3A`-ish) meets WCAG AA** against both the dark and light theme backgrounds. May need to nudge the shade once we have real text rendered on it.
