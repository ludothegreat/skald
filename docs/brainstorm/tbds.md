# Small TBDs

Things small enough that they don't deserve their own brainstorm question, but worth tracking so they don't get forgotten when implementation starts.

- **App icon / branding assets** — Need a `.png` / `.ico` / `.svg` for the OS launcher, AppImage, Windows installer, and macOS (later). Suggested vibe: a stylized harp / lyre or a runestone, matching the "skald" name and the terracotta accent. Generate or commission before the first public release.
- **README structure** — Standard sections: badges, screenshots (once GUI exists), what-it-is, install (per-OS), usage (GUI + CLI), keyboard shortcuts table, supported formats, config-file reference, building from source, license. Generate from this brainstorm doc when starting on the project.
- **AppImage build runner image** — Decide whether to use `appimage-builder` or `python-appimage` in CI. Pick when wiring CI.
- **Verify gitforge → GitHub mirror pushes tags**, not just branches — required for the release-build workflow to fire on `git tag v0.1.0 && git push gitforge v0.1.0`.
- **Verify the terracotta accent (`#C45A3A`-ish) meets WCAG AA** against both the dark and light theme backgrounds. May need to nudge the shade once we have real text rendered on it.
