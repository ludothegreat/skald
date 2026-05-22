# skald — Decisions

Project: `skald` — cross-platform (Linux + Windows) audiobook player with GUI and CLI modes.

Brainstorm started: 2026-05-22

---

## Core Product

| # | Question | Answer |
|---|----------|--------|
| 1 | Library model: manager, simple player, or both? | **Both (C)**. Library-managed GUI experience with auto-scan of a watched folder, plus ability to play a one-off file/folder ad-hoc (especially via CLI). Keeps "basic" honest while still feeling like a real audiobook player. |
| 2 | Which audio formats does v1 support? | **MP3, M4B, M4A, OGG, FLAC**. Folder-as-book (e.g., `Book/01.mp3, 02.mp3, …` treated as a single book) is essential. **AAX/AAXC deferred** — legal grey area + DRM complexity. Use a single underlying audio engine (mpv or ffmpeg) so format support is "whatever the engine handles." |

## Architecture

| # | Question | Answer |
|---|----------|--------|
| 3 | Language + GUI framework? | **Python + PySide6 (Qt)**. User is most familiar with this stack. Native-looking GUI on Linux and Windows, easy to pair with a Click/Typer CLI, Python `mpv` or `python-vlc` bindings for audio. Distribution via PyInstaller (~80–150 MB bundle, acceptable). |
| 4 | Audio engine? | **`python-mpv` (libmpv bindings)**. Smooth seeking, speed control with pitch preservation, gapless playback between chapter files, reads embedded M4B chapter markers. Linux: depend on system `mpv` package. Windows: bundle `libmpv.dll` for self-contained installs. |

## Playback Features

| # | Question | Answer |
|---|----------|--------|
| 5 | Chapter handling? | **All four features**: (1) chapter list sidebar (click to jump), (2) next/previous chapter buttons, (3) current chapter name displayed under the title, (4) exact-second resume on reopen (not chapter-rounded). Sources: embedded M4B chapters; folder-of-MP3s where each file = one chapter (filename or ID3 title as name); single-file-no-chapters falls back to position only. External `.cue`/`chapters.txt` deferred. |
| 6 | Standard playback features in v1? | **Include**: variable speed (0.5×–3× with pitch preservation), skip forward 30s / back 10s (configurable), sleep timer (X min or end-of-chapter), user bookmarks with notes, per-book position memory, volume + system mixer integration, media keys (MPRIS on Linux, SMTC on Windows) for OS lockscreen/media center. **Defer**: equalizer, mono mix. |

## Library

| # | Question | Answer |
|---|----------|--------|
| 7 | Library scanning + storage model | **(a) Multiple watched folders** — start with one, allow adding more in settings. **(b) Both folder-as-book and single-file-as-book** are valid units (industry convention: `~/Audiobooks/Author/Book/…`). **(c) Scan on startup + manual rescan button**; no filesystem watcher in v1 (extra dep, edge cases). **(d) Read-only against the user's files** — all state (position, bookmarks, library index) lives in the app data directory. Never write to ID3/M4B tags. |
| 8 | Metadata sources + editing? | **Sources in order**: (1) embedded ID3/M4B tags, (2) folder/filename parsing (`Author/Book` convention), (3) `cover.jpg`/`folder.jpg` in the book folder. **No online metadata lookup in v1** (deferred — keeps the app offline-clean). **User-editable metadata in v1**: edit dialog for title/author/narrator/description, plus **manual cover art upload (drop in a JPG/PNG to override)**. Overrides persist in the library DB; the original files are never modified. |
| 9 | State storage (DB, paths, settings) | **SQLite** for library / positions / bookmarks / metadata overrides (stdlib `sqlite3`, ACID, queryable, single file). Paths via `platformdirs`: Linux `~/.local/share/skald/library.db`, Windows `%APPDATA%\skald\library.db`. **Cover art stored as files** in `…/covers/<book-id>.jpg`, not as DB blobs (easier to inspect/replace). **Settings in a separate human-readable `config.toml`** in the same data dir, with commented defaults written on first run. |

## CLI

| # | Question | Answer |
|---|----------|--------|
| 10 | CLI scope for v1? | **Headless TUI player + light library admin**. (1) `skald play <path>` opens a terminal-only player with keystroke controls (play/pause/seek/speed/chapter) — great for SSH or no-GUI sessions. (2) `skald scan` and `skald list` for basic library management from the shell. **Skip** controlling a running GUI from the CLI — user has no need for it. CLI shares the same library DB and per-book position state as the GUI. |

## GUI

| # | Question | Answer |
|---|----------|--------|
| 11 | Main window layout? | **Two-pane (layout A) with a collapsible left pane**. Left: library grid/list of covers + titles, behind an accordion/collapse toggle so the user can hide it for a now-playing-focused view. Right (or main area): book detail when one is selected. Player bar pinned to the bottom of the window, always visible. Implementation: Qt `QSplitter` with a collapse-to-zero handle, plus a toolbar/hamburger button to toggle the pane explicitly. State of the toggle persists across sessions. |
| 12 | Library view mode + per-book info + sort/filter? | **Both grid and list modes, togglable** (grid by default, list for big libraries; choice persists). **Per-book display in both modes**: cover, title, author, total length, progress bar. Narrator shown only on the detail view to keep tiles clean. **Sort by**: title, author, date added, last played, % complete. **Filter (v1)**: in-progress / finished / not-started. Author and series filtering deferred. |
| 13 | Now-playing / book detail view? | **Book detail replaces the library area (layout A)**. Shows large cover, title, author, narrator, total length, % complete, description, big Play/Resume button, full chapter list, user bookmarks list, Edit-metadata button. Back button returns to library. **Transport controls live in both** the persistent bottom player bar (always available across all views) and the detail view (with a bigger seek bar and chapter list for active listening). |
| 14 | Visual style / theme? | **Dark + Light + Follow system** (Follow-system is default). **Custom QSS theme** so the app looks identical on Linux and Windows (no native-style drift). **Palette**: neutral dark grays in dark mode / cream-and-off-white in light mode, with a single warm accent — **muted terracotta / burnt orange** (around `#C45A3A`). User said no blue and no yellow, so amber is out; terracotta keeps the warm "evening reading" feel without crossing into yellow. |
| 15 | Keyboard shortcuts? | **Hardcoded defaults for v1**, with a config-file-only override for power users (edit `config.toml`; no GUI rebinding). **Defaults**: Space = play/pause; ←/→ = seek back 10s / forward 30s; Shift+←/→ = 5s seek; Ctrl+←/→ = prev / next chapter; ↑/↓ = volume; M = mute; +/− = speed ±0.1×; 0 = reset speed to 1×; B = bookmark at current position; L = toggle library pane; F11 = fullscreen; Esc = back to library. GUI rebinding deferred to a later version. |
| 16 | First-run / empty-library experience? | **No modal wizard**. (a) Empty library shows a minimal banner / prominent "Add folder" button — no interrupt modal. (b) Suggest the default path (`~/Audiobooks` on Linux, `%USERPROFILE%\Audiobooks` on Windows), pre-populate the folder picker with it, and offer to create the directory if it doesn't exist. (c) Empty state shows a brief "Library empty" message + Add-folder button + a short note explaining the supported folder layouts (one folder per book, or a folder of MP3s = one book). (d) **No bundled sample book** — not worth the bundle-size cost. |

## Distribution & Packaging

| # | Question | Answer |
|---|----------|--------|
| 17 | Distribution / packaging for v1? | **Linux**: AppImage (primary, cross-distro, no install required) + **AUR package** (easy since user is on Arch). Flatpak deferred (sandboxing the watched-folder feature is meaningful extra work). **Windows**: PyInstaller `.exe` packaged with **Inno Setup installer** — registers file associations for `.m4b`, adds Start Menu shortcut, handles clean uninstall. **No code signing in v1** — Windows SmartScreen will warn on first run; documented in README. Real cert + CI signing deferred until the project matures. |
| 18 | Auto-update behavior? | **Update check only (option B)** — on startup, HTTPS GET to GitHub Releases for the latest tag. If newer than installed, show a non-intrusive banner: "Update available: vX.Y.Z" with a button to open the download page. **No automatic install** in v1. Setting in preferences: "Check for updates on startup" (default: on); README documents that the only network call is the GitHub Releases ping. **Release host**: `github.com/ludothegreat/skald`. |

## Identity

| # | Question | Answer |
|---|----------|--------|
| 19 | Project name? | **`skald`** — Old Norse poet/storyteller who recited sagas aloud. Literal "audio storyteller." Short, distinctive, easy to type as a CLI command. **Availability**: `github.com/ludothegreat/skald` free, AUR `skald` free, PyPI `skald` taken by an unrelated niche experiment-logger package — irrelevant since the app ships as AppImage / Windows installer / AUR, not via pip. If a PyPI presence is ever needed, use **`skald-player`** there. Binary, AppImage filename, Windows installer name, menu entry, AUR package, and config dir all use plain `skald`. |

## Legal

| # | Question | Answer |
|---|----------|--------|
| 20 | License? | **MIT**. Permissive, low friction, standard for personal-but-public open-source desktop apps. Compatible with all dependencies (libmpv LGPL via dynamic linking, PySide6 LGPL via dynamic linking). |

## Observability

| # | Question | Answer |
|---|----------|--------|
| 21 | Telemetry, crash reporting, logging? | **Local logging only**. (a) **No** usage analytics — the project doesn't need a phone-home channel. (b) **No** remote crash reporting in v1; can add Sentry later if pain warrants it. (c) **Verbose local log file** in the app data dir (`~/.local/share/skald/logs/skald.log` on Linux, `%APPDATA%\skald\logs\skald.log` on Windows). Rotating handler, 5 files × 5 MB. DEBUG level when launched with `--debug`, INFO otherwise. Users can attach the log to bug reports manually. |

## Internationalization & Accessibility

| # | Question | Answer |
|---|----------|--------|
| 22 | i18n strategy? | **English-only with Qt i18n scaffolding (option B)**. All user-facing strings wrapped in Qt's `tr()` from day one; `.ts` translation files structured so a contributor can submit a translation PR without code changes. Ship v1 with only the English translation present. Modest upfront cost; avoids a global rewrite later. |
| 23 | Accessibility for v1? | **Cheap baseline only**: full keyboard navigation (logical tab order, all controls focusable, no mouse-only actions); screen-reader compatibility via Qt's default accessibility (accessible names on custom widgets); respect system font size + HiDPI scaling (avoid hardcoded pixel sizes); WCAG-AA color contrast in both themes (verify terracotta accent meets AA). **Defer**: app-internal large-text mode, explicit reduced-motion mode, full WCAG audit. Don't write code that would block adding those later. |

## Quality

| # | Question | Answer |
|---|----------|--------|
| 24 | Testing strategy for v1? | **Layer 1 (mandatory from day one)**: Ruff (lint) + black (format) + mypy (type check), all gated through a pre-commit hook. **Layer 2**: unit tests with `pytest` on pure-logic code (library scanner, metadata parser, position-saver, settings loader, CLI args). **Layer 3**: small integration test set (~5–10 tests) using a tiny audio fixture in the repo — covers library detection, playback, position save/restore. **Defer**: pytest-qt GUI tests (flaky, high maintenance) and full E2E AppImage-launch tests. Maintain a `MANUAL_TEST_PLAN.md` checklist for un-automatable items (look-and-feel, media-key integration, sleep timer behavior). |
| 25 | CI + repo / mirror layout? | **Canonical source: `gitforge.online`** (`ssh://git@gitforge.online:27665/srv/git/repos/skald.git`) — pure `git-shell`, no CI, no web UI. **GitHub mirror at `github.com/ludothegreat/skald`** is the community surface: issues, PRs, releases, downloads, and CI all live here. **GitHub Actions** does the work: (A) on every push/PR — lint, typecheck, tests, on Linux + Windows runners; (B) on tag push (mirrored from gitforge) — build AppImage on Linux runner + build Inno installer on Windows runner, attach both artifacts to the GitHub Release. **Skip** nightlies, auto-changelog, macOS builds for v1. Requires the gitforge → GitHub mirror to push tags as well as branches (verify in mirror config, not a decision to make here). |
| 26 | Versioning scheme? | **SemVer, starting at `0.1.0`**. `0.x.y` during the still-building phase (signals "no stability promises yet"). Bump to `1.0.0` once the app is stable enough to recommend to a stranger. MAJOR = breaking change (e.g., DB schema migration with no auto-upgrade path); MINOR = new feature; PATCH = bug fix. |

## Runtime Behavior

| # | Question | Answer |
|---|----------|--------|
| 27 | Launch + state robustness | (a) **No auto-resume on launch** — open app lands in library; a prominent "Resume last book" button in the library header gets the user one click from where they left off. (b) **Position save cadence**: every 5 seconds + on pause + on seek + on chapter change + on app exit. (c) **Missing files** stay in the library with a "missing" badge, state (position, bookmarks) preserved; user removes manually; re-detected if the file returns. (d) **Single-instance app** — second launch focuses the existing window (avoids SQLite-write contention). (e) **CLI while GUI is running**: refuse with a clear error pointing the user to close the GUI first. Mentions a future `--isolated` flag in the error so the door stays open for an alternate-DB CLI mode, but that flag is not built in v1. |
