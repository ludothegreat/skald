# Learned Topics

Topics that emerged organically during brainstorming sessions and should be considered in future projects of the same shape.

## Distribution & Packaging

- **gitforge → GitHub mirror split**: When the user's canonical git lives on `gitforge.online` (pure `git-shell`, no CI / no web UI), GitHub becomes the community surface — issues, PRs, releases, downloads, and CI all live on the mirror. Verify the mirror pushes tags as well as branches so GitHub Actions can trigger release builds. Relevant when: any project ludo plans to publish publicly.
  - Discovered: 2026-05-22, skald (audiobook player)

## Architecture / Runtime

- **Single-instance behavior for desktop apps with shared SQLite state**: Always ask whether the app should be single-instance vs. multi-instance, since multi-instance + a single SQLite DB is a corruption risk. Relevant when: any desktop app that writes to a single local DB.
  - Discovered: 2026-05-22, skald

- **CLI/GUI overlap with shared state**: If a project has both a GUI and a CLI that share state (positions, DB), explicitly decide what happens when both want to run at once. Refusing one is safer than letting both write to the DB. Relevant when: any hybrid GUI+CLI app with shared persistent state.
  - Discovered: 2026-05-22, skald

- **State save cadence**: For any app where the user can lose progress on a crash (media players, editors, games), pin down explicitly how often state writes happen — every N seconds, on pause/seek/exit/etc. Don't leave it to "I'll figure it out." Relevant when: any app with stateful per-session user progress.
  - Discovered: 2026-05-22, skald

- **Missing-file behavior in library-style apps**: Any app that tracks user files (audiobooks, music, photos, ebooks) needs an explicit answer for "what happens when the file is gone." Defaults vary wildly between apps; not asking means you ship surprise behavior. Relevant when: any library / catalog / collection app.
  - Discovered: 2026-05-22, skald

## Distribution

- **Code signing as a deferred-by-default decision**: For desktop apps, decide explicitly that you're *not* signing in v1 — Windows SmartScreen / macOS Gatekeeper warnings need to be documented in the README so users aren't blindsided. Relevant when: any cross-platform desktop app shipped outside official stores.
  - Discovered: 2026-05-22, skald

## UX

- **First-run experience without a modal wizard**: Default to a banner / empty-state prompt instead of a setup wizard for v1. Wizards are more work and easier to get wrong. Relevant when: any desktop app with a "library" concept that requires user-supplied folders.
  - Discovered: 2026-05-22, skald

- **Auto-resume on launch (yes / no / button)**: For media players, explicitly decide whether the app auto-resumes the last item on launch. "Land in library + prominent Resume button" is often the right answer when users juggle multiple in-progress items. Relevant when: any media player with multi-item progress tracking.
  - Discovered: 2026-05-22, skald

## Quality

- **Pre-commit hook with lint+format+typecheck from day one**: For projects with non-programmer maintainers, this is non-negotiable safety net. Relevant when: any Python project ludo touches (already in CLAUDE.md, reinforced here as a brainstorm checkpoint).
  - Discovered: 2026-05-22, skald
