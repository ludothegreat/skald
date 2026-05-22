---
title: "skald v1 — cross-platform audiobook player"
type: feat
status: active
date: 2026-05-22
origin: docs/brainstorm/decisions.md
---

# skald v1 — cross-platform audiobook player

## Overview

Build `skald` v1: a cross-platform (Linux + Windows) audiobook player with both a PySide6 GUI and a terminal CLI, backed by libmpv for playback and SQLite for state. Ship as an AppImage + AUR package on Linux and an Inno Setup `.exe` installer on Windows. Canonical git is `gitforge.online`, mirrored (including tags) to `github.com/ludothegreat/skald` where CI, issues, and releases live.

All v1 scope and design decisions are pre-decided across **27 brainstorm questions** in [`docs/brainstorm/decisions.md`](../brainstorm/decisions.md). This plan does not re-litigate them — it sequences the implementation, pins versions, and captures the 2026-current technical details from external research that grounds the build.

## Problem Statement / Motivation

Ludo wants a "super basic" audiobook player that works on both their Linux desktop (Arch) and Windows machines, with a GUI for casual use and a CLI for terminal-only sessions. The market gap they're filling for themselves: most existing players are either Android-only, web-only (Audiobookshelf needs a server), or skewed toward one OS (Audible app is closed-source and tied to Audible's ecosystem). Existing cross-platform Python audiobook players are mostly abandoned or single-developer hobby projects in poor health.

The brainstorm framed v1 as "all the default settings and features that an audiobook player should have," explicitly *not* a feature-light prototype. Deferred items live in [`docs/brainstorm/future-features.md`](../brainstorm/future-features.md).

## Proposed Solution

A single Python application with three runtime modes:

1. **GUI mode** (default): full PySide6 desktop app with library, book detail, persistent player bar, themes
2. **Headless CLI playback**: `skald play <path>` — TUI player in the terminal, no GUI
3. **Library admin CLI**: `skald scan` / `skald list` — non-interactive

All three share one SQLite library DB, one libmpv-driven playback engine, one settings file, and one log file in the platform's standard user data directory (`~/.local/share/skald/` on Linux, `%APPDATA%\Skald\skald\` on Windows via `platformdirs`).

Single-instance enforcement (via `QLocalServer`) means a second GUI launch focuses the existing window, and `skald play` from the CLI refuses to run when the GUI is up (preventing two libmpv instances racing on the SQLite DB).

## Technical Approach

### Architecture

```
skald/
├── pyproject.toml                  # PEP 621, all deps + extras (linux/windows)
├── README.md, LICENSE, .gitignore  # present
├── .pre-commit-config.yaml         # ruff, black, mypy
├── .github/workflows/
│   ├── test.yml                    # lint+typecheck+test on push/PR (matrix)
│   └── release.yml                 # on tag v*, build artifacts + GH Release
├── src/skald/
│   ├── __init__.py                 # __version__
│   ├── __main__.py                 # entry; routes to GUI or CLI
│   ├── core/
│   │   ├── player.py               # libmpv wrapper (locale fix, terminate, Qt signals)
│   │   ├── library.py              # in-process library state
│   │   ├── scanner.py              # filesystem walk + book detection
│   │   ├── metadata.py             # mutagen + folder-name fallback + overrides
│   │   ├── chapters.py             # M4B chpl + mpv fallback + folder-of-MP3s inference
│   │   ├── positions.py            # per-book position read/write
│   │   ├── bookmarks.py            # user bookmarks CRUD
│   │   ├── covers.py               # extract + store cover art files
│   │   ├── settings.py             # config.toml loader/writer
│   │   ├── paths.py                # platformdirs wrappers
│   │   ├── logging_setup.py        # rotating file handler + --debug toggle
│   │   ├── single_instance.py      # QLocalServer / QLocalSocket
│   │   ├── playback_controller.py  # Protocol shared with OS-integration adapters
│   │   └── updates.py              # GH releases ping for update banner
│   ├── db/
│   │   ├── schema.py               # migrations list, PRAGMA user_version pattern
│   │   └── connection.py           # WAL pragmas, connection factory
│   ├── cli/
│   │   ├── __init__.py             # Typer app
│   │   ├── play.py                 # headless TUI player
│   │   ├── scan.py
│   │   └── list_cmd.py             # `list` reserved name → list_cmd
│   ├── gui/
│   │   ├── app.py                  # QApplication setup
│   │   ├── main_window.py          # QSplitter, bottom player bar, shortcuts
│   │   ├── library_view.py         # grid + list modes (toggle)
│   │   ├── book_detail.py          # cover, chapters, bookmarks, metadata
│   │   ├── player_bar.py           # persistent transport
│   │   ├── dialogs/                # edit metadata, cover upload, sleep timer
│   │   ├── theme.py                # QSS load + variable substitution + switch
│   │   └── themes/
│   │       ├── dark.qss.tmpl
│   │       └── light.qss.tmpl
│   ├── integration/
│   │   ├── mpris_linux.py          # Linux-only import; mpris_server-backed
│   │   └── smtc_windows.py         # Windows-only import; winrt + HWND interop
│   ├── resources/
│   │   ├── icons/                  # SVG, recolored at theme load
│   │   └── translations/           # .ts and compiled .qm
│   └── tui/
│       └── player_tui.py           # rich.live-based for the CLI play command
├── tests/
│   ├── fixtures/
│   │   ├── short.mp3               # ≤5s, public-domain LibriVox snippet
│   │   ├── short.m4b               # with embedded chapter
│   │   └── folder_book/            # 3× tiny MP3s with track tags
│   ├── unit/                       # scanner, metadata, positions, settings, CLI args
│   └── integration/                # ~5-10 tests using fixtures + libmpv
├── packaging/
│   ├── linux/
│   │   ├── skald.desktop
│   │   ├── AppImageBuilder.yml     # or linuxdeploy invocation
│   │   └── PKGBUILD                # AUR
│   └── windows/
│       └── skald.iss               # Inno Setup script
├── docs/
│   ├── brainstorm/                 # decisions, future-features, learned-topics, tbds
│   └── plans/                      # this file
└── MANUAL_TEST_PLAN.md
```

### Dependency graph (high-level)

```
GUI (main_window) ──┐
                    ├──> playback_controller (Protocol) ──> player.py ──> libmpv
TUI (player_tui) ───┤                                    │
CLI commands ───────┘                                    │
                                                         │
mpris_linux / smtc_windows ──> playback_controller ──────┘ (subscribes via signals)

scanner ──> metadata + covers + chapters ──> library (DB)
                                                  │
positions / bookmarks ────────────────────────────┤
                                                  ▼
                                          SQLite (WAL mode)

settings.py ──> config.toml
logging_setup ──> rotating log file
paths.py ──> platformdirs
```

### Key version pins

| Package | Pin | Why |
|---|---|---|
| Python | `>=3.12,<3.14` | CI matrix target; matches Ubuntu 22.04 + Windows runners |
| `PySide6` | `>=6.7,<7.0` | `styleHints().colorScheme()` stable; `colorSchemeChanged` signal |
| `python-mpv` | `>=1.0.8,<2.0` | Current stable; libmpv 2.x ABI |
| `mutagen` | `>=1.47` | Current; reads M4B `chpl`, ID3 `CHAP` |
| `platformdirs` | `>=4.3` | Stable API with `ensure_exists` kwarg |
| `typer` | `>=0.12,<1.0` | Click 8.1+ floor |
| `rich` | `>=13` | TUI rendering for `skald play` |
| `dbus-fast` | `>=4.0` (Linux extra) | Active fork of dbus-next |
| `mpris-server` | latest (Linux extra) | Pragmatic MPRIS exposure |
| `winrt-Windows.Media` | `>=3.0` (Windows extra) | Own-session SMTC API |
| `winrt-Windows.Media.Control` | `>=3.0` (Windows extra) | Control API |
| `winrt-Windows.Storage.Streams` | `>=3.0` (Windows extra) | Thumbnail streams |
| `pyinstaller` | `>=6.10` | Built-in PySide6 hook through 6.8 |
| `ruff`, `black`, `mypy`, `pre-commit`, `pytest` | latest | Dev only |

Linux extras (`pip install skald[linux]`) and Windows extras (`pip install skald[windows]`) gate the OS-specific deps; the OS-detection wrapper at runtime only imports the relevant integration module.

### Non-negotiable cross-stack rules

1. **The libmpv locale fix.** In `app.py`, *immediately* after `from PySide6 import ...` and *before* the first `mpv.MPV(...)`:
   ```python
   import locale
   locale.setlocale(locale.LC_NUMERIC, "C")
   ```
   Qt clobbers `LC_NUMERIC` on import; libmpv parses numeric properties with the C locale and fails silently on non-English systems otherwise.

2. **python-mpv → Qt thread marshalling.** Property observers and event callbacks fire on python-mpv's event thread. Never touch widgets from them. Pattern: each observer emits a `Signal` on a `QObject` that lives on the main thread; the slot does the UI work.

3. **`player.terminate()` explicitly at shutdown.** Relying on `__del__`/GC deadlocks on exit while the event thread is alive. Hook into `QApplication.aboutToQuit`.

4. **SQLite WAL pragmas on every connection** (set in `db/connection.py`):
   ```sql
   PRAGMA journal_mode = WAL;
   PRAGMA synchronous = NORMAL;
   PRAGMA foreign_keys = ON;
   PRAGMA busy_timeout = 5000;
   PRAGMA temp_store = MEMORY;
   PRAGMA cache_size = -64000;
   ```
   The library DB must live on a local filesystem (WAL silently corrupts on NFS/SMB). Media files can be on a NAS — only the DB path is constrained.

5. **Qt 6 HiDPI is default-on.** Do not set `Qt.AA_EnableHighDpiScaling` — it's deprecated and a no-op in Qt 6. Use `QFontMetrics` for sizing and SVG icons.

6. **`app.setStyle("Fusion")` before loading QSS.** PySide6 wheels on Linux ship without native platform theme plugins; default is Windows-95-ish. Fusion is the safe baseline that QSS layers cleanly on top of.

7. **PyInstaller `--onedir`, never `--onefile`.** Onefile extracts to `%TEMP%` every launch (2–5s startup hit) and triggers Windows antivirus heuristics. Inno Setup wraps the onedir output into the single `.exe` installer.

8. **Single-instance dance.** Always call `QLocalServer.removeServer("skald-singleton")` before `QLocalServer.listen(...)`. Crash-leftover socket files on Unix block startup otherwise.

### Implementation Phases

The phasing honors the user's global preference (CLAUDE.md): "Start every project as a single working file that proves the core concept." Phase 0 is that file; Phases 1+ scaffold into the layout above.

#### Phase 0 — Single-file spike (½ day)

**Goal:** Prove the toolchain works end-to-end on Linux before scaffolding anything.

**Deliverable:** `spike.py` — a single Python file that, with `python -m skald` not yet wired up:
- Imports PySide6, applies the `LC_NUMERIC=C` fix
- Loads a real audiobook from a hardcoded path via python-mpv (audio-only)
- Prints chapter list, current chapter, time-pos every second
- Accepts `p`/`s`/`+`/`-`/`q` keystrokes for pause/seek/speed/quit
- Calls `player.terminate()` on exit

**Success criterion:** Plays an `.m4b` from `~/Audiobooks/` to completion on Arch Linux with chapter detection working. **Discard or recycle** into `core/player.py` afterward — not committed to `main` as-is.

#### Phase 1 — Project skeleton + quality bar (1 day)

- Create the `src/skald/` layout above (empty modules with TODO comments are fine)
- `pyproject.toml` with all version pins from the table above, including `[project.optional-dependencies]` for `linux` and `windows`
- `.pre-commit-config.yaml` with `ruff` (lint + format), `mypy` (strict-ish), `pyupgrade`
- `pre-commit install` runs hook on commit
- `core/paths.py` — thin `platformdirs` wrappers (`data_dir()`, `config_path()`, `log_dir()`, `covers_dir()`)
- `core/logging_setup.py` — `RotatingFileHandler`, 5 files × 5 MB, `--debug` flag switches level
- `core/settings.py` — `tomllib` (read) + `tomli_w` (write) wrapper around `config.toml`; writes commented defaults on first run
- `db/schema.py` — initial schema as `MIGRATIONS = ["CREATE TABLE ...", ...]`; `apply_migrations(conn)` uses `PRAGMA user_version`
- `db/connection.py` — `get_connection()` applies the WAL pragmas every open
- `pytest` config with `tests/fixtures/` placeholder
- `tests/unit/test_settings.py`, `test_paths.py`, `test_migrations.py` — first passing tests

**Schema v1 (single migration to start):**

```sql
CREATE TABLE books (
    id              INTEGER PRIMARY KEY,
    path            TEXT NOT NULL UNIQUE,    -- folder or single-file path
    kind            TEXT NOT NULL CHECK (kind IN ('folder', 'file')),
    title           TEXT NOT NULL,
    author          TEXT,
    narrator        TEXT,
    series          TEXT,
    series_index    REAL,
    description     TEXT,
    duration_s      REAL,
    added_at        INTEGER NOT NULL,        -- unix seconds
    last_played_at  INTEGER,
    status          TEXT NOT NULL DEFAULT 'present'  -- 'present' | 'missing'
);
CREATE TABLE tracks (
    id              INTEGER PRIMARY KEY,
    book_id         INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    path            TEXT NOT NULL,
    order_index     INTEGER NOT NULL,
    duration_s      REAL
);
CREATE TABLE positions (
    book_id         INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
    seconds         REAL NOT NULL,
    updated_at      INTEGER NOT NULL
);
CREATE TABLE bookmarks (
    id              INTEGER PRIMARY KEY,
    book_id         INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    seconds         REAL NOT NULL,
    note            TEXT,
    created_at      INTEGER NOT NULL
);
CREATE TABLE metadata_overrides (
    book_id         INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
    title           TEXT,
    author          TEXT,
    narrator        TEXT,
    series          TEXT,
    series_index    REAL,
    description     TEXT,
    cover_overridden INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE watched_folders (
    id              INTEGER PRIMARY KEY,
    path            TEXT NOT NULL UNIQUE
);
CREATE INDEX idx_books_last_played ON books(last_played_at DESC);
CREATE INDEX idx_books_status      ON books(status);
CREATE INDEX idx_tracks_book       ON tracks(book_id, order_index);
```

**Acceptance:** `pre-commit run --all-files` passes; `pytest` passes; `skald --version` prints version.

#### Phase 2 — Audio engine + chapters + position memory (1–2 days)

- `core/player.py` — wraps `mpv.MPV(vo='null', ytdl=False, audio_pitch_correction=True)`; exposes `play(path)`, `pause()`, `resume()`, `seek(s, relative)`, `set_speed(s)`, `position`, `chapter_index`, `chapter_list`. Observers (`time-pos`, `chapter`, `end-file`) emit `QObject.Signal` instances; constructors take an `event_dispatch: Callable` so the CLI mode can use a different dispatch (asyncio or simple callback).
- `core/chapters.py` — `extract_chapters(path) -> list[Chapter]`. Order: (1) mutagen MP4 `chpl`, (2) mutagen ID3 `CHAP`, (3) on `MP4` returning empty, fall back to `mpv.chapter_list` (handles MP4 chapter-text-tracks that mutagen issue #530 doesn't), (4) folder-of-files → one chapter per track using filename or `TIT2`.
- `core/positions.py` — `read(book_id) -> float | None`; `write(book_id, seconds)`. Hooked into player events: write every 5s while playing **plus** on pause / seek / chapter change / app exit / focus loss.
- `tests/integration/test_playback.py` — uses `tests/fixtures/short.mp3` (≤5s, LibriVox public-domain snippet, ~50 KB) and `short.m4b` (with one chapter). Asserts: load, play, position advances, seek works, speed sets, chapter list returns, terminate is clean.

**Acceptance:** Can play a fixture file headlessly via `python -c "from skald.core.player import Player; ..."`. Position persists across player restarts within tests. `player.terminate()` returns cleanly under pytest.

#### Phase 3 — Library scanner + metadata + covers (1–2 days)

- `core/scanner.py` — `scan(folder: Path) -> list[BookCandidate]`. Heuristics (from research):
  - Walk `folder` recursively, but **treat the first directory containing audio files as the book**; do not recurse below it.
  - Detect `CD01/`, `disc 1/`, `cd1/` (case-insensitive regex) subfolders and group them as one book.
  - Track ordering: if all tracks have `track` tags forming a perfect 1..N, use that; else natural-sort by filename.
  - A single `.m4b` / `.m4a` / `.mp3` file in a watched folder is a book.
- `core/metadata.py` — extract from (1) embedded tags (mutagen), (2) folder/filename pattern `Author/Book` or `Author - Book`, (3) overrides table (final word). Title falls back to folder name.
- `core/covers.py` — extract embedded cover (`APIC` for ID3, `covr` for MP4) or `cover.jpg` / `folder.jpg` in the book folder; write to `<data_dir>/covers/<book_id>.jpg`. User uploads overwrite the same file and set `metadata_overrides.cover_overridden = 1`.
- Missing-file handling: on rescan, books whose `path` no longer exists get `status = 'missing'` (never deleted). Re-detected paths reset to `'present'`.
- Tests: scanner on a fixture tree (`folder_book/` with 3 MP3s + a CD-style fixture + a standalone .m4b), metadata extraction round-trip, override application order.

**Acceptance:** `scan()` returns the right number of books for each fixture topology; metadata overrides take precedence over embedded; missing books survive rescans with state intact.

#### Phase 4 — CLI (1 day)

- `cli/__init__.py` — Typer app, global `--debug` flag wires `logging_setup`
- `cli/play.py` — Headless TUI player using `rich.live` for the progress bar + chapter + speed + time. Keystroke handling via `readchar` or `prompt_toolkit` (decide at impl time; `readchar` is simpler if no fancy input is needed). Keybindings match the GUI table from Q15 where applicable.
- `cli/scan.py` — Adds folder to `watched_folders`, scans, prints summary
- `cli/list_cmd.py` — Prints library as a table (rich.table), filterable with `--status`, `--author`, `--sort`
- Single-instance check: `core/single_instance.py` exposes `gui_is_running() -> bool` via a lockfile or socket-probe; `skald play` refuses if the GUI is up, printing the future `--isolated` hint per Q27
- Tests for argument parsing and command dispatch

**Acceptance:** `skald --help`, `skald scan ~/Audiobooks`, `skald list`, and `skald play <path>` all work; refusal message fires when a (mocked) GUI lock exists.

#### Phase 5 — GUI shell + theme + single-instance (2–3 days)

- `gui/app.py` — `QApplication` setup: locale fix, `app.setStyle("Fusion")`, single-instance gate (`QLocalServer` / `QLocalSocket`, args forwarding on second-launch), translator install, theme load
- `gui/main_window.py` — Top-level window: a `QSplitter(Qt.Horizontal)` containing the library panel (left) and a `QStackedWidget` (right) for library / book-detail switching. The bottom player bar is a separate widget added to a vertical `QVBoxLayout` outside the splitter, so it's always visible. Library-pane collapse via stored `sizes` + `setSizes([0, total])`.
- Toolbar with hamburger button (toggle library pane), theme selector, settings button
- `gui/player_bar.py` — Cover thumbnail, title/chapter label, transport buttons (prev-chapter, back-30, play/pause, forward-30, next-chapter), seek slider, time labels, speed control, volume control, sleep timer button
- `gui/theme.py` — Loads `themes/dark.qss.tmpl` / `light.qss.tmpl` and string-formats with the accent color `#C45A3A` and computed contrasts. `apply_theme(name)` reloads + walks widgets calling `style().unpolish/polish()` for any with dynamic state properties. Listens to `app.styleHints().colorSchemeChanged` when `theme=auto` is in config.
- Keyboard shortcuts wired per Q15 table
- Tests: `pytest-qt`-light spot checks (skipped if `pytest-qt` unavailable) for "splitter collapses on toggle" and "theme switch doesn't crash"

**Acceptance:** GUI launches, library pane collapses and restores, theme switch (dark/light/follow-system) works without restart, second launch focuses the existing window.

#### Phase 6 — GUI library view (2 days)

- `gui/library_view.py` — Two visual modes backed by a single `QAbstractListModel`:
  - **Grid:** `QListView.setViewMode(IconMode)` + custom `QStyledItemDelegate` painting cover (square aspect, max ~180px), title, author, progress bar
  - **List:** `QTableView` with sortable columns (Title, Author, Length, Progress, Last Played)
- Toggle button in toolbar swaps mode; choice persists in `config.toml`
- Sort menu (5 sort orders), filter dropdown (`All / In Progress / Finished / Not Started`)
- Empty state: prominent "Add folder" button + helper text describing the layouts (per Q16)
- Prominent "Continue listening" tile at the top of the library when there's a last-played book — selecting it opens the book detail view (does **not** auto-play)
- Tests: model produces the right row counts under each filter

**Acceptance:** Library renders grid and list, sort/filter work, "Add folder" picker pre-fills `~/Audiobooks` (Linux) / `%USERPROFILE%\Audiobooks` (Windows) and offers to mkdir if missing.

#### Phase 7 — GUI book detail + dialogs (2–3 days)

- `gui/book_detail.py` — Large cover (left), metadata block (title, author, narrator, duration, % complete, description), big Play/Resume button, chapter list (`QListWidget`, click to jump), bookmarks list with add/edit/delete, Edit-metadata button
- `gui/dialogs/edit_metadata.py` — Editable fields for title, author, narrator, series, description; saves to `metadata_overrides`
- `gui/dialogs/cover_upload.py` — File picker for JPG/PNG; drag-and-drop also accepted on the cover widget; writes to `<data_dir>/covers/<book_id>.jpg` and sets `cover_overridden = 1`
- `gui/dialogs/sleep_timer.py` — Radio buttons: 15/30/45/60 min, "End of chapter", custom minutes. Sleep tick implemented as a `QTimer`; on fire, calls `player.pause()`
- Bookmarks: add at current position (key `B`), edit note inline, delete with confirmation
- Tests: metadata override round-trip; cover replace overwrites prior file; sleep timer pauses player at expiry (use `qtbot.wait`)

**Acceptance:** Editing metadata, uploading a cover, adding bookmarks, and triggering a sleep timer all work end-to-end.

#### Phase 8 — OS integration: media keys + file associations (2–3 days)

- `core/playback_controller.py` — `Protocol` class with `play() / pause() / next_chapter() / prev_chapter() / seek_relative(s)` and a `state_changed` Qt signal carrying `PlaybackState` (a `dataclass`: position, duration, title, chapter, cover_path, is_playing, speed). Implemented by a `MainPlaybackController` that wraps `core/player.py` + library lookups.
- `integration/mpris_linux.py` — `mpris_server`-backed adapter. Bus name `org.mpris.MediaPlayer2.skald`. Runs on a `QThread` driving `dbus-fast`'s asyncio loop, or via `qasync` if simpler. Imported only when `sys.platform == "linux"`.
- `integration/smtc_windows.py` — Uses `winrt-Windows.Media.SystemMediaTransportControls`. The HWND interop is the gnarly part: `ISystemMediaTransportControlsInterop::GetForWindow(HWND)` via ctypes against `Windows.Media.dll`. Pull the HWND from the QMainWindow `winId()`. Updates display via `display_updater.music_properties` and a cover stream via `winrt-Windows.Storage.Streams.RandomAccessStreamReference`. Subscribes to `ButtonPressed`, dispatches by `args.button`.
- Linux file association via `.desktop` file with `MimeType=audio/mp4;audio/x-m4b;audio/mpeg;application/ogg;` etc.
- Windows file association handled by Inno Setup `Registry` section (Phase 10)
- Tests: mock the OS integration adapter; verify the controller forwards play/pause requests correctly

**Acceptance:** GNOME/KDE media keys (and `playerctl`) drive playback on Linux; Windows lock-screen media controls show the book + cover and respond to play/pause.

#### Phase 9 — First-run, accessibility, i18n, update check (1–2 days)

- First-run flow: empty library banner (Q16), pre-filled folder picker, mkdir-if-missing offer
- i18n scaffolding: all user-facing strings via `self.tr(...)` or `QCoreApplication.translate(...)`; `pyside6-lupdate` extracts to `translations/skald_en.ts`; `pyside6-lrelease` compiles `.qm`. CI step verifies extraction is up to date.
- Accessibility audit pass: tab order verification, `setAccessibleName` on custom widgets (transport buttons, sleep timer, chapter list), keyboard-only smoke test, run a contrast checker against `#C45A3A` on both themes (adjust shade if needed for WCAG-AA — captured in `tbds.md`)
- `core/updates.py` — On startup (gated by `config.toml: check_for_updates = true`), HTTPS GET `https://api.github.com/repos/ludothegreat/skald/releases/latest`, compare `tag_name` against `__version__` using `packaging.version.Version`. If newer, show a non-modal banner with a "Open download page" button. Errors are silent (logged).
- Privacy note added to README explaining the only network call

**Acceptance:** Fresh install → empty library prompt works; tab cycles through all controls; screen reader (Orca on Linux) announces transport buttons; update banner appears when a fake newer tag is mocked in tests.

#### Phase 10 — Distribution, CI, release v0.1.0 (1–2 days)

- `packaging/linux/AppImageBuilder.yml` (or a `linuxdeploy` invocation script). Build target: Ubuntu 22.04 runner (glibc 2.35 floor). libmpv is **distro-installed**, not bundled — recipe declares `libmpv2` as a runtime dep and the AppImage `.desktop` includes it in `MimeType` comments.
- `packaging/linux/PKGBUILD` for AUR; depends on `mpv`, `python>=3.12`, `python-pyside6`, etc.
- `packaging/windows/skald.iss` — Inno Setup script: registers `.m4b` association under `HKCU`, Start Menu shortcut, uninstall entry, embeds the PyInstaller `--onedir` output. Includes `mpv-2.dll` next to `skald.exe`.
- `pyinstaller.spec` (or CLI args in CI): `--onedir`, `--windowed`, `--add-binary "mpv-2.dll;."` on Windows
- `.github/workflows/test.yml`:
  ```yaml
  on: [push, pull_request]
  jobs:
    test:
      strategy:
        matrix:
          os: [ubuntu-22.04, windows-latest]
          python: ["3.12"]
      runs-on: ${{ matrix.os }}
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: ${{ matrix.python }}, cache: pip }
        - run: pip install -e .[dev,linux] # or [dev,windows]
        - run: |
            sudo apt-get install -y libmpv2 libmpv-dev   # linux
            # windows: vendored libmpv-2.dll on PATH
        - run: pre-commit run --all-files
        - run: mypy src/
        - run: pytest -v
  ```
- `.github/workflows/release.yml`:
  ```yaml
  on:
    push:
      tags: ['v*']
  jobs:
    build-linux:
      runs-on: ubuntu-22.04
      steps:
        - # checkout, setup-python, install libmpv, pip install -e .[linux]
        - # pyinstaller --onedir
        - # linuxdeploy + appimagetool → skald-X.Y.Z-x86_64.AppImage
        - uses: actions/upload-artifact@v4
    build-windows:
      runs-on: windows-latest
      steps:
        - # checkout, setup-python, vendor mpv-2.dll
        - # pyinstaller --onedir
        - uses: Minionguyjpro/Inno-Setup-Action@v1
          with: { path: packaging/windows/skald.iss }
        - uses: actions/upload-artifact@v4
    release:
      needs: [build-linux, build-windows]
      runs-on: ubuntu-latest
      permissions: { contents: write }
      steps:
        - uses: actions/download-artifact@v4
          with: { path: artifacts }
        - uses: softprops/action-gh-release@v2
          with:
            files: artifacts/**/*
            generate_release_notes: true
            prerelease: ${{ contains(github.ref_name, '-') }}
  ```
- `MANUAL_TEST_PLAN.md` — checklist of things automation can't reliably cover: GUI look-and-feel on both themes, media keys on a real KDE / Windows install, sleep timer ticking down, missing-file badge, single-instance focus
- README update: install instructions per OS (with SmartScreen warning note), screenshots once GUI exists, keyboard shortcuts table
- App icon: ship a placeholder SVG (simple harp/lyre silhouette in terracotta) — flagged in `tbds.md` for a better design later
- Tag `v0.1.0` on gitforge — verify the patched mirror pushes the tag to GitHub (already confirmed end-to-end during repo setup) and the release workflow produces both artifacts on the GitHub Release

**Acceptance:** `v0.1.0` GitHub Release page has both a working `skald-0.1.0-x86_64.AppImage` and `skald-setup-0.1.0.exe`. Both launch and play an audiobook on a clean VM.

### Estimated effort

| Phase | Estimate (focused days) |
|---|---|
| 0 — Spike | 0.5 |
| 1 — Skeleton | 1 |
| 2 — Audio engine | 1.5 |
| 3 — Library + metadata | 1.5 |
| 4 — CLI | 1 |
| 5 — GUI shell | 2.5 |
| 6 — Library view | 2 |
| 7 — Book detail + dialogs | 2.5 |
| 8 — OS integration | 2.5 |
| 9 — First-run + a11y + i18n + updates | 1.5 |
| 10 — Distribution + CI + ship | 1.5 |
| **Total** | **~18 days focused work** |

For a part-time project this realistically maps to 2–3 calendar months.

## Alternative Approaches Considered

The brainstorm already rejected a number of alternatives. Recording them here so the plan stays anchored:

- **Rust + Tauri or egui** instead of Python + PySide6 — rejected because user is most familiar with Python and PySide6 (Q3). Tradeoff accepted: ~80–150 MB bundle vs. ~5–20 MB for Rust.
- **`python-vlc` instead of `python-mpv`** — rejected for clunkier API and worse chapter handling (Q4).
- **JSON files instead of SQLite** — rejected; gets ugly at scale and loses queryability (Q9).
- **Online metadata lookup in v1** — rejected; keeps app offline-clean (Q8), deferred to future-features.
- **macOS support** — out of scope for v1 (Q17); separate effort with macOS-specific QSS + Gatekeeper signing.
- **Flatpak distribution** — deferred (Q17); the watched-folder feature needs careful sandbox permission handling.
- **AAX/AAXC (Audible DRM)** — deferred (Q2); legal grey area + DRM complexity.

## System-Wide Impact

### Interaction graph

Within this single-process app, the chain when a user double-clicks a book in the GUI library:

```
LibraryView.item_double_clicked (Qt signal)
  → MainWindow.open_book(book_id)
    → MainPlaybackController.load(book)        ← reads positions + chapters
      → Player.load(path)                       ← libmpv loadfile
        → property observers wire up
        → 'time-pos' fires every ~1s on mpv thread
          → forwarded via QObject.Signal to main thread
            → MainPlaybackController.state_changed signal
              ↓                ↓                       ↓
            PlayerBar      BookDetail              integration adapters
            (UI update)    (UI update)             (MPRIS / SMTC)
      → every 5s + on pause/seek/chapter:
        → Positions.write(book_id, time-pos)
          → SQLite UPDATE (WAL)
```

### Error propagation

| Failure point | Behavior | User-visible |
|---|---|---|
| libmpv can't open file | `Player.load` raises `PlayerError` | Toast: "Couldn't open: <filename>"; book marked status='missing' on rescan |
| SQLite locked (rare; single-instance gate prevents most) | `busy_timeout=5000` retries; if still locked, logged + skipped (position write is idempotent) | Silent in normal use; log shows |
| mutagen can't parse | extraction falls back through chain (mpv chapter_list → folder inference → empty) | Book may have weak metadata until user edits |
| MPRIS/SMTC registration fails on startup | logged WARNING; rest of app continues | No media keys; everything else works |
| Update-check HTTP failure | logged DEBUG; no banner shown | Silent |
| Cover decode fails | fall back to a generic terracotta book-icon | Generic cover shown |

Errors **never silently swallow** in the playback path. The mpv `end-file` event with `reason='error'` raises into the controller and surfaces as a toast.

### State lifecycle risks

- **Partial position write on crash**: a single `UPDATE positions SET seconds=?` is atomic in SQLite. WAL commit is durable on `PRAGMA synchronous=NORMAL` (the documented "no corruption, but may lose the last N seconds on power loss" tradeoff — acceptable).
- **Stale `covers/<book_id>.jpg`** after a book is deleted: cascade FK deletes the row, but the file lingers. Cleanup: `core/covers.py` has a `gc_orphans()` called from `scan` at the end.
- **Watched folder pointing at unmounted drive**: scanner detects `not folder.exists()`, logs WARNING, leaves all of that folder's books at `status='missing'`. Next scan when the drive is back restores them.
- **libmpv crash during playback**: process exits; user re-launches. Position is durable because we write every 5s + on chapter change.

### API surface parity

- **GUI vs CLI vs TUI**: the three modes share `MainPlaybackController` and `Library`. Anything you can do via the GUI's player bar (pause, seek, speed, chapter nav) can be done via TUI keystrokes — feature parity is enforced by the fact that they both call into the same controller.
- **What's GUI-only**: bookmark add/edit/delete UI, metadata editing dialog, cover upload, library grid/list/filter/sort UI. These exist in v1 only in the GUI. (Future features file already notes the CLI-controls-GUI gap.)

### Integration test scenarios (manual + automated mix)

1. **Folder-of-MP3s book with messy track tags** (some `track=`, some missing) — scanner natural-sorts, library shows correct order, chapter sidebar names match filenames.
2. **M4B with embedded `chpl` chapters** — chapter detection via mutagen; click chapter in sidebar jumps to time; position resume lands within the right chapter.
3. **Watched folder containing both a single-file book and a multi-file book** — both detected, displayed in the same library.
4. **Network drive unplugged mid-listen** — `end-file` with `reason='error'` raises a toast; book marked missing on next rescan; the rest of the library is unaffected.
5. **GUI running, user opens a `.m4b` via Windows Explorer double-click** — file association sends the path to the running GUI via `QLocalSocket`; GUI focuses and opens the book detail view.
6. **Theme change while playing** — full QSS reload mid-playback; player keeps playing; no visual flicker.
7. **Second `skald play` launched while GUI running** — refused with clear error message, exit code 1.

## Acceptance Criteria

### Functional requirements (v1 ships when all of these are true)

- [ ] Playback works for MP3, M4B, M4A, OGG, FLAC on both Linux and Windows
- [ ] Folder-as-book and single-file-as-book both detected
- [ ] Variable speed 0.5×–3× with pitch preservation
- [ ] Skip forward 30s / back 10s (the brainstorm Q6 default; configurable in `config.toml`). Research notes the broader industry trend of symmetric 30s/30s as an alternative; left as a future config preset list (5/10/15/30/45/60/90) but not the default.
- [ ] Sleep timer (15/30/45/60 min, end-of-chapter, custom)
- [ ] User bookmarks with notes (add/edit/delete)
- [ ] Per-book position memory; auto-resume on opening a book (not on launch)
- [ ] Library scan of one or more watched folders
- [ ] Manual cover-art upload (drag-drop + file picker)
- [ ] Metadata editing dialog with override persistence
- [ ] Dark + Light + Follow-system themes; runtime switch; terracotta accent
- [ ] GUI library: grid + list views, sort, filter (in-progress / finished / not-started)
- [ ] GUI: collapsible left pane, persistent bottom player bar
- [ ] CLI: `skald play`, `skald scan`, `skald list` work
- [ ] Media keys: MPRIS on Linux, SMTC on Windows
- [ ] File association for `.m4b` registered (Linux `.desktop`, Windows Inno Setup)
- [ ] Single-instance GUI; CLI refuses to play when GUI is up
- [ ] Update-check banner (HTTPS GET to GH Releases) with opt-out
- [ ] Missing-file books surface with a badge and survive rescans

### Non-functional requirements

- [ ] WCAG-AA color contrast in both themes (verified with a contrast checker)
- [ ] Full keyboard navigation; tab order is logical; no mouse-only actions
- [ ] HiDPI scaling works correctly (test 1.25× and 1.5×)
- [ ] Screen-reader compatibility via Qt's default accessibility + `setAccessibleName` on custom widgets
- [ ] Qt i18n scaffolding present; English-only ship; `.ts` extraction reproducible
- [ ] Startup time on a 100-book library < 2 seconds on a SATA SSD
- [ ] Position write < 5ms in WAL mode (informally measured; not a CI gate)
- [ ] No remote crash reporting; no analytics; only network call is the optional update check

### Quality gates

- [ ] `ruff check .` passes
- [ ] `mypy src/skald` passes with no errors
- [ ] `pytest -v` passes on both Linux and Windows CI runners
- [ ] `pre-commit run --all-files` passes (gate on commit)
- [ ] CI test workflow green on `main` after every push
- [ ] CI release workflow on a test tag produces both AppImage and `.exe` artifacts
- [ ] `MANUAL_TEST_PLAN.md` checklist run by Ludo before tagging `v0.1.0`

## Success Metrics

This is a personal project, so the metrics are mostly qualitative:

- **Primary:** Ludo uses `skald` as their daily-driver audiobook player for one full audiobook on Linux and one on Windows, without falling back to another player.
- **Secondary:** Total v1 install size — AppImage under 50 MB (excluding distro-installed libmpv), Windows installer under 100 MB.
- **Secondary:** No data-loss bugs in the first month of personal use (position memory, bookmarks, library state).
- **Tertiary:** A second user (friend, Discord, anyone) successfully installs and uses it on their machine without one-on-one support — proves the install instructions are real.

## Dependencies & Prerequisites

### External dependencies (runtime)

- **libmpv 2.x** — Linux: `mpv` / `libmpv2` distro package; Windows: bundled `mpv-2.dll`
- **Python 3.12+** — bundled by PyInstaller on Windows; AUR depends on system Python
- **Qt 6.7+** — bundled with PySide6 wheels on both OSes
- **D-Bus session bus** (Linux only, for MPRIS) — present by default on GNOME / KDE / XFCE

### External dependencies (build/CI)

- GitHub Actions `ubuntu-22.04` and `windows-latest` runners
- Inno Setup 6 (pre-installed on `windows-latest` per actions/runner-images #12947)
- `linuxdeploy` + `linuxdeploy-plugin-python` on Ubuntu 22.04
- `softprops/action-gh-release@v2`, `Minionguyjpro/Inno-Setup-Action@v1`

### Prerequisite: gitforge → GitHub mirror pushes tags

**Already verified** during repo setup. Hook patched in `/hoard/workspace/gitforge-manager/app.py`. Verified end-to-end with `v0.0.0-mirror-test`. Captured in [`tbds.md`](../brainstorm/tbds.md).

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Windows SMTC HWND interop is the worst code in the project** | High | Medium | Reference [DubyaDude/WindowsMediaController](https://github.com/DubyaDude/WindowsMediaController) for working Python interop. Worst case: ship without SMTC in v1, mark as a known limitation in README. MPRIS on Linux is dramatically simpler with `mpris_server`. |
| **libmpv ABI break in a future distro** | Medium | Low | Pin `python-mpv` to `<2.0`; libmpv 2.x ABI has been stable for years. Document the apt/pacman package names; the AUR PKGBUILD pins explicitly. |
| **PySide6 6.7+ not on Windows users' systems** | Low | Low | Bundled via PyInstaller. End users never install Python or PySide6. |
| **AppImage glibc compatibility** | Medium | Medium | Build on `ubuntu-22.04` specifically (glibc 2.35). Do not use `ubuntu-24.04` or `ubuntu-latest` for the AppImage runner. |
| **PyInstaller mis-detection of PySide6 modules** | Low | Low | Built-in PySide6 hook covers everything we use. Use `--collect-data PySide6` if Qt translation `.qm` files don't bundle. |
| **SQLite corruption from a kill-9 during write** | Very Low | High | WAL + `synchronous=NORMAL` is documented as no-corruption (only lose the last commit). User accepts this tradeoff implicitly. |
| **Crash leaves a stale `QLocalServer` socket on Unix; user can't relaunch** | Low | High | `QLocalServer.removeServer(name)` always called before `listen()`. Documented in code. |
| **Qt clobbers `LC_NUMERIC`; libmpv silently mis-parses on non-English locales** | High (if forgotten) | High | First-thing init in `app.py`. Pin as comment + a `tests/unit/test_locale_init.py` that fails if the locale isn't `C` after `app.py` import. |
| **Update-check hits GitHub rate limits** | Low | Low | Unauthenticated `/releases/latest` is 60/hr per IP; one call per startup is fine. Errors silent. |
| **First-time Windows user spooked by SmartScreen** | High | Low | Documented prominently in README install instructions. Future: code-signing in `future-features.md`. |
| **macOS users ask for a build** | Medium | Low | Documented as out-of-scope in `future-features.md`. Polite "PRs welcome" framing in README. |
| **Bundle inflation past comfort threshold** | Low | Low | `--onedir` keeps things inspectable. Periodic audit; trim unused PySide6 modules with `--exclude-module` if needed. |

## Resource Requirements

- **One developer** (Ludo) — part-time over 2–3 months
- **Test hardware**: one Linux desktop (Arch), one Windows machine (Windows 10 or 11). Both already available.
- **GitHub Actions usage**: well within free-tier minutes for a personal repo (matrix tests run < 10 min each; releases < 30 min each)
- **No paid services**: no Sentry, no analytics, no code-signing cert in v1 (all deferred)
- **No additional infra**: gitforge.online already operating; GitHub repo already mirrored

## Future Considerations

All deferred features documented in [`docs/brainstorm/future-features.md`](../brainstorm/future-features.md). Highlights:

- **Online metadata lookup** (Open Library / Audible) behind a toggle — when v1 is solid
- **CLI controls running GUI** via local socket — once a user actually asks for it
- **Flatpak distribution** with sandbox permission handling
- **Code signing** (Windows Authenticode, Apple Developer for any future macOS)
- **macOS support** as a deliberate effort
- **GUI for keyboard rebinding** (v1 is config.toml only)
- **`skald play --isolated`** flag for running CLI alongside GUI with a separate DB
- **Equalizer / mono mix** if a real user requests them
- **Author / series filters** in the library view
- **External `.cue` / `chapters.txt`** parsing
- **AAX / AAXC** support (legal grey area)
- **Remote crash reporting (Sentry)** if bug volume justifies it

## Documentation Plan

| Doc | When | Audience |
|---|---|---|
| `README.md` | Updated each phase; finalized for v0.1.0 | End users, contributors |
| `docs/brainstorm/*` | Already exists | Future-Ludo, future-contributors |
| `docs/plans/<this file>` | This document | Future-Ludo |
| `MANUAL_TEST_PLAN.md` | Phase 10 | Ludo before each release |
| Inline docstrings | Throughout (no AI-sounding comments per CLAUDE.md) | Code readers |
| `CHANGELOG.md` | Phase 10; manual edits per release | End users; release notes |
| Screenshots | Phase 10 after GUI is final | README |
| App icon | Phase 10 placeholder; improve later | Branding |

## Sources & References

### Origin

- **Origin document:** [`docs/brainstorm/decisions.md`](../brainstorm/decisions.md) — 27 questions answered covering scope, architecture, UX, distribution, licensing, accessibility, i18n, telemetry, versioning, and runtime behavior. Key decisions carried forward verbatim:
  - **Q3 / Q4:** Python + PySide6 + python-mpv (audio engine)
  - **Q7 / Q9:** Multiple watched folders, read-only against user files, SQLite in platform-standard data dir, settings in separate `config.toml`
  - **Q11–Q14:** Two-pane layout with collapsible library pane, grid + list modes, custom QSS theme with `#C45A3A` terracotta accent on dark + light + follow-system
  - **Q17 / Q18:** AppImage + AUR + Inno Setup; update-check via GitHub Releases; no code signing in v1
  - **Q25:** Canonical source on gitforge.online; GitHub mirror is community surface; tag-mirror patch already applied and verified
  - **Q27:** No auto-resume on launch; position writes every 5s + events; missing-file books keep state; single-instance GUI; CLI refuses to run when GUI is up
- **Companion docs:**
  - [`docs/brainstorm/future-features.md`](../brainstorm/future-features.md) — 22 deferred items
  - [`docs/brainstorm/learned-topics.md`](../brainstorm/learned-topics.md) — patterns to apply to future brainstorms
  - [`docs/brainstorm/tbds.md`](../brainstorm/tbds.md) — small loose ends (icon, gitforge-manager patch commit, contrast verification)

### User context

- **User's global instructions:** [`/home/ludo/.claude/CLAUDE.md`](file:///home/ludo/.claude/CLAUDE.md) — Python-first defaults, single-file-spike-then-scaffold workflow, pre-commit / ruff / mypy as the safety net for a non-programmer maintainer, no AI-sounding comments, verbose logging from day one
- **gitforge-manager API** at `http://localhost:7777` for canonical repo management

### External references (consulted 2026-05-22)

- [python-mpv on PyPI](https://pypi.org/project/python-mpv/) — version 1.0.8
- [jaseg/python-mpv on GitHub](https://github.com/jaseg/python-mpv) — API + locale fix + threading notes
- [mpv manual — audio-pitch-correction](https://mpv.io/manual/master/) — `scaletempo2` auto-applied
- [Qt for Python deployment guide (PyInstaller)](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)
- [QStyleHints / colorScheme](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QStyleHints.html)
- [Dark Mode on Windows 11 with Qt 6.5 (Qt blog)](https://www.qt.io/blog/dark-mode-on-windows-11-with-qt-6.5)
- [PySide6 QSplitter](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSplitter.html)
- [QLocalServer / QLocalSocket](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QLocalServer.html)
- [itay-grudev/SingleApplication](https://github.com/itay-grudev/SingleApplication) — reference single-instance pattern
- [PySide Internationalization (Qt Wiki)](https://wiki.qt.io/PySide_Internationalization)
- [niess/linuxdeploy-plugin-python](https://github.com/niess/linuxdeploy-plugin-python)
- [python-appimage](https://appimage.github.io/Python/)
- [Inno Setup Registry section help](https://jrsoftware.org/ishelp/index.php?topic=registrysection)
- [Inno Setup added to windows-2025 runner](https://github.com/actions/runner-images/issues/12947)
- [Minionguyjpro/Inno-Setup-Action](https://github.com/Minionguyjpro/Inno-Setup-Action)
- [softprops/action-gh-release](https://github.com/softprops/action-gh-release)
- [dbus-fast on PyPI](https://pypi.org/project/dbus-fast/) — active fork of dbus-next
- [alexdelorenzo/mpris_server](https://github.com/alexdelorenzo/mpris_server) — MPRIS publisher abstraction
- [MPRIS MediaPlayer2.Player spec](https://specifications.freedesktop.org/mpris/latest/Player_Interface.html)
- [pywinrt/python-winsdk (deprecation notice)](https://github.com/pywinrt/python-winsdk) — `winsdk` deprecated, use per-namespace `winrt-*` packages
- [winrt-Windows.Media.Control on PyPI](https://pypi.org/project/winrt-Windows.Media.Control/)
- [SystemMediaTransportControls (Microsoft Learn)](https://learn.microsoft.com/en-us/uwp/api/windows.media.systemmediatransportcontrols)
- [DubyaDude/WindowsMediaController](https://github.com/DubyaDude/WindowsMediaController) — working SMTC interop reference in Python
- [platformdirs API](https://platformdirs.readthedocs.io/en/latest/api.html)
- [mutagen MP4 API](https://mutagen.readthedocs.io/en/latest/api/mp4.html)
- [mutagen issue #530 (M4B chapter edge cases)](https://github.com/quodlibet/mutagen/issues/530)
- [Typer "Using Click"](https://typer.tiangolo.com/tutorial/using-click/)
- [SQLite WAL docs](https://sqlite.org/wal.html)
- [Audiobookshelf book scanner docs](https://www.audiobookshelf.org/guides/book-scanner/) — folder-as-book heuristics, CD subfolder grouping, natural-sort fallback
- [Voice (de.ph1b.audiobook) on F-Droid](https://f-droid.org/packages/de.ph1b.audiobook/) — reference for skip defaults, position cadence
- [Qt-Advanced-Stylesheets](https://github.com/githubuser0xFFFF/Qt-Advanced-Stylesheets) — runtime QSS variables (option, not adopted for v1)
- [Qt Dynamic Properties and Stylesheets wiki](https://wiki.qt.io/Dynamic_Properties_and_Stylesheets) — `unpolish`/`polish` after dynamic property change
- [Fix PyQt/PySide styling on Linux pip install](https://www.pythonguis.com/faq/installation-via-pip-styling/) — `setStyle("Fusion")` baseline

### Related ecosystem

- Audiobookshelf (web-based, server-required) — closest open-source comparable; the bar for "library detection that just works"
- Smart AudioBook Player (Android) — UX reference for chapter sidebar and bookmarks
- Voice (Android, F-Droid) — clean minimalist UI reference
