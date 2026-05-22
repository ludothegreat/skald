---
title: "skald v1 — cross-platform audiobook player"
type: feat
status: active
date: 2026-05-22
origin: docs/brainstorm/decisions.md
---

# skald v1 — cross-platform audiobook player

> **Plan history:** Originally written 2026-05-22 from a 27-question brainstorm. Deepened the same day with 8 parallel review agents; their findings (real defects, refinements, perf and idiom improvements) have been folded into the phases below. The pre-deepening version is recoverable via `git show 39873fd`. Optional scope rollbacks the simplicity reviewer suggested live at the end as an appendix — they contradict explicit brainstorm decisions and are *not* applied; they're surfaced for the user's awareness if v1 schedule slips.

## Overview

Build `skald` v1: a cross-platform (Linux + Windows) audiobook player with both a PySide6 GUI and a terminal CLI, backed by libmpv for playback and SQLite for state. Ship as an AppImage + AUR package on Linux and an Inno Setup `.exe` installer on Windows. Canonical git is `gitforge.online`, mirrored (including tags) to `github.com/ludothegreat/skald` where CI, issues, and releases live.

All v1 scope and design decisions are pre-decided across **27 brainstorm questions** in [`docs/brainstorm/decisions.md`](../brainstorm/decisions.md).

## Problem Statement / Motivation

Ludo wants a "super basic" audiobook player that works on both their Linux desktop (Arch) and Windows machines, with a GUI for casual use and a CLI for terminal-only sessions. Existing alternatives are Android-only, web-only (Audiobookshelf needs a server), tied to one ecosystem (Audible app), or abandoned. The brainstorm framed v1 as "all the default settings and features that an audiobook player should have," explicitly *not* a feature-light prototype. Deferred items live in [`docs/brainstorm/future-features.md`](../brainstorm/future-features.md).

## Proposed Solution

A single Python application with three runtime modes:

1. **GUI mode** (default): full PySide6 desktop app with library, book detail, persistent player bar, themes
2. **Headless CLI playback**: `skald play <path>` — TUI player in the terminal, no GUI
3. **Library admin CLI**: `skald scan` / `skald library` — non-interactive

All three share one SQLite library DB, one libmpv-driven playback engine, one settings file, and one log file in the platform's standard user data directory (`~/.local/share/skald/` on Linux, `%APPDATA%\skald\` on Windows via `platformdirs`).

Single-instance enforcement (via `QLocalServer`) means a second GUI launch focuses the existing window, and `skald play` from the CLI refuses to run when the GUI is up (preventing two libmpv instances racing on the SQLite DB).

## Technical Approach

### Architecture

Flat package layout — no `core/` namespace (Python idiom; `core/` is a Java-ism). OS-specific code is isolated under `integration/` with lazy imports so startup doesn't load `winrt` or `dbus_fast` until the relevant adapter is constructed.

```
skald/
├── pyproject.toml                  # PEP 621; all deps + extras (linux/windows/dev)
├── README.md, LICENSE, .gitignore  # present
├── .pre-commit-config.yaml         # ruff, black, mypy, lint-imports
├── .github/workflows/
│   ├── test.yml                    # lint+typecheck+test on push/PR (matrix)
│   └── release.yml                 # on tag v*, build + GH Release + SHA256SUMS
├── src/skald/
│   ├── __init__.py                 # __version__
│   ├── __main__.py                 # entry; LC_NUMERIC fix HERE; routes to GUI or CLI
│   ├── errors.py                   # SkaldError, PlayerError, LibraryError, MigrationError
│   ├── paths.py                    # platformdirs wrappers; all return pathlib.Path
│   ├── settings.py                 # pydantic-settings BaseSettings(toml_file=...)
│   ├── logging_setup.py            # dictConfig; RotatingFileHandler 5×5MB
│   ├── single_instance.py          # QLocalServer/Socket; UserAccessOption + 0700
│   ├── updates.py                  # GH Releases ping (HTTPS GET; 5s timeout)
│   ├── validation.py               # validate_media_path() — resolve+ext-allowlist
│   ├── time_util.py                # ms_to_human(), human_to_ms()
│   ├── player.py                   # libmpv wrapper (callbacks, NOT Qt signals)
│   ├── playback_controller.py      # Protocol + PlaybackState (frozen slots)
│   ├── library.py                  # in-process library state + repository helpers
│   ├── scanner.py                  # FS walk; symlink guards; QThread worker
│   ├── metadata.py                 # mutagen + folder-name fallback
│   ├── chapters.py                 # M4B chpl + mpv chapter_list fallback
│   ├── positions.py                # per-book position read/write (timer pauses on pause)
│   ├── bookmarks.py                # user bookmarks CRUD
│   ├── covers.py                   # extract original + write 360px thumbnail
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py           # WAL pragmas; threading.local; file lock
│   │   ├── migrations.py           # registry; refuse-newer; manual BEGIN/COMMIT; online backup
│   │   └── migrations/
│   │       └── 0001_initial.sql    # schema v1
│   ├── cli/
│   │   ├── __init__.py             # Typer app
│   │   ├── play.py                 # headless rich.live TUI player (no separate tui/)
│   │   ├── scan.py
│   │   └── library.py              # renamed from `list_cmd.py`
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── app.py                  # QApplication; Fusion; translator; theme
│   │   ├── main_window.py          # QSplitter; bottom player bar; shortcuts
│   │   ├── library_view.py         # grid + list modes (toggle)
│   │   ├── book_detail.py          # cover, chapters, bookmarks, metadata
│   │   ├── player_bar.py           # persistent transport
│   │   ├── dialogs.py              # edit-metadata, cover-upload, sleep-timer (single file)
│   │   └── theme.py                # string.Template substitution; QSS load + switch
│   ├── integration/
│   │   ├── __init__.py             # init_media_keys() — lazy OS dispatch
│   │   ├── mpris.py                # Linux only; mpris_server-backed
│   │   └── smtc.py                 # Windows only; winrt + HWND interop
│   ├── resources/
│   │   ├── icons/                  # SVG, recolored at theme load
│   │   ├── themes/                 # dark.qss.template, light.qss.template
│   │   ├── config.default.toml     # commented defaults; copied on first run
│   │   └── translations/           # .ts and compiled .qm
│   └── _stubs/
│       └── mpv.pyi                 # local stubs for python-mpv
├── tests/
│   ├── conftest.py                 # session fixtures generate audio via ffmpeg
│   ├── unit/                       # scanner, metadata, positions, settings, CLI args
│   └── integration/                # ~5-10 tests using generated fixtures + libmpv
├── packaging/
│   ├── linux/
│   │   ├── skald.desktop
│   │   ├── AppImageBuilder.yml     # or linuxdeploy invocation
│   │   └── PKGBUILD                # AUR
│   └── windows/
│       └── skald.iss               # Inno Setup; HKCU file association
├── docs/
│   ├── brainstorm/                 # decisions, future-features, learned-topics, tbds
│   └── plans/                      # this file
└── MANUAL_TEST_PLAN.md
```

### Dependency graph (high-level)

```
GUI (main_window) ──┐
                    ├──> playback_controller (Protocol+listeners)
TUI (cli/play.py) ──┤        │
CLI commands ───────┘        │ owns ↓
                             player.py ──> libmpv
                             
integration/mpris.py ──┐
                       ├─── add_listener(controller, on_state_change)
integration/smtc.py  ──┘

scanner ──> metadata + covers + chapters ──> library (DB)
                                                  │
positions / bookmarks ────────────────────────────┤
                                                  ▼
                                          SQLite (WAL mode; threading.local; file lock)

settings.py (pydantic-settings) ──> config.toml
logging_setup.py (dictConfig) ──> rotating log file
paths.py (platformdirs → pathlib.Path)
```

Boundary rules enforced by `import-linter` in CI:

- `cli/`, `library.py`, `playback_controller.py`, `player.py` must not import from `gui/` or `PySide6.QtWidgets`/`QtGui`
- `integration/mpris.py` must not import `winrt`; `integration/smtc.py` must not import `dbus_fast`

### Key version pins

| Package | Pin | Why |
|---|---|---|
| Python | `>=3.12,<3.15` | Dev tested on 3.14; supported floor 3.12 (covers Ubuntu 22.04 if needed) |
| `PySide6` | `>=6.7,<7.0` | `styleHints().colorScheme()` stable; `colorSchemeChanged` signal |
| `PySide6-stubs` | latest (dev) | mypy-friendly Qt types |
| `python-mpv` | `>=1.0.8,<2.0` | Current stable; libmpv 2.x ABI |
| `mutagen` | `>=1.47` | Reads M4B `chpl`, ID3 `CHAP` |
| `platformdirs` | `>=4.3` | Stable API with `ensure_exists` kwarg |
| `pydantic-settings` | `>=2.5` | Typed settings; TOML source via `tomllib` |
| `typer` | `>=0.12,<1.0` | Click 8.1+ floor |
| `rich` | `>=13` | TUI rendering for `cli/play.py` |
| `dbus-fast` | `>=4.0` (Linux extra) | Active fork of dbus-next |
| `mpris-server` | latest (Linux extra) | MPRIS publisher abstraction |
| `winrt-Windows.Media` | `>=3.0` (Windows extra) | Own-session SMTC API |
| `winrt-Windows.Media.Control` | `>=3.0` (Windows extra) | Control API |
| `winrt-Windows.Storage.Streams` | `>=3.0` (Windows extra) | Thumbnail streams |
| `pyinstaller` | `>=6.10` | Built-in PySide6 hook through 6.8 |
| `ruff`, `black`, `mypy`, `pre-commit`, `pytest`, `pytest-qt`, `import-linter` | latest (dev) | Quality bar |

Linux extras (`pip install skald[linux]`) and Windows extras (`pip install skald[windows]`) gate OS-specific deps. The OS-detection wrapper at runtime only imports the relevant integration module.

### Non-negotiable cross-stack rules

1. **The libmpv locale fix lives at the top of `skald/__main__.py`** — before any other import. Qt clobbers `LC_NUMERIC` on import and libmpv parses numeric properties with the C locale; failure mode is silent on non-English systems. The CLI / TUI / GUI all enter through `__main__.py` so all three paths get the fix:
   ```python
   # src/skald/__main__.py — first 4 lines
   import locale
   locale.setlocale(locale.LC_NUMERIC, "C")
   import sys
   from skald.cli import app
   ```
   `player.py` asserts the fix is active in its constructor: `assert locale.getlocale(locale.LC_NUMERIC)[0] in (None, "C"), "..."`. A unit test imports each entry path and verifies the locale.

2. **python-mpv → main-thread marshalling via callbacks.** python-mpv property observers and event callbacks fire on the engine's event thread. `player.py` exposes a transport-agnostic `add_listener(callback)` API. The GUI wraps that with a `QObject.Signal` *at the boundary* (`PlayerSignals(QObject)` in `gui/app.py`); the CLI/TUI uses callbacks directly. Never put `QObject.Signal` into `player.py` or `playback_controller.py` — that would force Qt into non-GUI code paths.

3. **`player.terminate()` explicitly on `aboutToQuit`.** Relying on `__del__`/GC deadlocks at shutdown while the event thread is alive. Hook into `QApplication.aboutToQuit` (GUI) and `atexit` (CLI).

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

5. **Qt 6 HiDPI is default-on.** Do not set the deprecated `Qt.AA_EnableHighDpiScaling`. Use `QFontMetrics` for sizing and SVG icons.

6. **`app.setStyle("Fusion")` before loading QSS.** PySide6 wheels on Linux ship without native platform theme plugins; Fusion is the safe baseline that QSS layers cleanly on top of.

7. **PyInstaller `--onedir`, never `--onefile`.** Onefile extracts to `%TEMP%` on every launch (2–5s startup hit) and triggers Windows antivirus heuristics. Inno Setup wraps the onedir output into a single `.exe` installer.

8. **Single-instance via `QLocalServer` with `UserAccessOption` and a `user_runtime_dir` socket path with 0700 perms.** Always call `QLocalServer.removeServer(name)` before `listen(...)`. Crash-leftover socket files on Unix block startup otherwise. Default Linux behavior leaves the socket world-accessible — without `UserAccessOption`, another local user can intercept second-launch CLI args.

9. **All SQL uses `?` parameter binding.** No f-strings, `.format()`, or `+` concatenation in any query. `ruff` rule `S608` (`hardcoded-sql-expression`) is enabled in `pyproject.toml`. CI greps for `f"…(SELECT|INSERT|UPDATE|DELETE)…"` patterns under `src/` and fails the build on any hit.

10. **SQLite connection per thread.** `db/connection.py` keeps a per-thread connection in `threading.local()`. Background scanner thread gets its own connection; main thread gets its own. Never share.

11. **Connections take a file lock on `library.db.lock`** before any SQL (Unix `fcntl.flock`, Windows `msvcrt.locking`, abstracted). Migration acquires exclusively; normal ops shared. This covers the pre-Qt startup window where the Qt single-instance gate isn't yet up.

12. **`validate_media_path()` for every externally-supplied path** — CLI args, `QLocalSocket` second-launch handoff, file-association entry. Library-internal playback (DB-sourced paths) bypasses it.

### Implementation Phases

Honors the user's global preference: "Start every project as a single working file that proves the core concept." Phase 0 is that file; Phases 1+ scaffold into the layout above.

#### Phase 0 — Single-file spike (½ day)

**Goal:** Prove the toolchain works end-to-end on Linux before scaffolding anything.

**Deliverable:** `spike.py` (at repo root, gitignored or kept as historical reference) — a single Python file that:
- Imports `PySide6` then immediately applies `locale.setlocale(locale.LC_NUMERIC, "C")`
- Loads a real audiobook from `/hoard/books/audio` (sampling a small one) via python-mpv
- Prints chapter list, current chapter, time-pos every second
- Accepts `p`/`s`/`+`/`-`/`q` keystrokes for pause/seek-back/speed-up/speed-down/quit (via `readchar` or stdin loop)
- Calls `player.terminate()` on exit

**Success criterion:** Plays an `.m4b` from `/hoard/books/audio` to a few minutes in with chapter detection working. **Discard or recycle** into `player.py` — not committed to `main` as-is (kept in a `spike/` directory or git-ignored after Phase 1 lands).

#### Phase 1 — Project skeleton + quality bar (1 day)

- Create the `src/skald/` flat layout above (modules with `raise NotImplementedError` placeholders and full type signatures — forces design before implementation)
- `pyproject.toml` with all version pins, `[project.optional-dependencies]` for `linux` / `windows` / `dev`
- `.pre-commit-config.yaml` with `ruff` (lint + format), `mypy` (strict-ish), `pyupgrade`, `lint-imports`
- `pre-commit install` runs hooks on commit
- `paths.py` — thin `platformdirs` wrappers (`data_dir()`, `config_path()`, `db_path()`, `log_dir()`, `covers_dir()`, `thumbnails_dir()`, `runtime_dir()`). **All return `pathlib.Path`, never `str`.**
- `errors.py` — exception hierarchy: `SkaldError` base, `PlayerError`, `LibraryError`, `MigrationError`, `MetadataError`
- `logging_setup.py` — `logging.config.dictConfig` with a dict literal; `RotatingFileHandler` 5 files × 5 MB; `--debug` flag switches level
- `settings.py` — `pydantic-settings` `BaseSettings` reading `config.toml` via the `tomllib` source. Default values defined as class attributes. Ship `src/skald/resources/config.default.toml` (commented) — copied to user dir on first run (`tomli_w` strips comments, so static template is the only way to preserve them)
- `validation.py` — `validate_media_path(p) -> Path` (resolve strict, extension allowlist `{".mp3",".m4a",".m4b",".ogg",".opus",".flac",".wav"}`, file-not-dir check)
- `time_util.py` — `ms_to_human(ms) -> "1:23:45"`, `human_to_ms(s) -> int`
- `db/connection.py` — `get_connection()` returns `threading.local()` connection; applies WAL pragmas on first acquire; acquires file lock on `library.db.lock`
- `db/migrations.py` — loads `.sql` files from `db/migrations/`, sorted by leading number; for each version > `user_version`, runs in manual `BEGIN`/.../`PRAGMA user_version = N`/`COMMIT` transaction (NOT `executescript()`). Pre-flight: refuses to open DB where `user_version > EXPECTED_VERSION`. Online-backup before any migration via `Connection.backup()`; rotates 3 backups.
- `db/migrations/0001_initial.sql` — the initial schema (below)
- `tests/conftest.py` — session-scoped fixtures generate audio via `ffmpeg` (sine MP3, M4B with chapter, three-track folder); no binaries committed
- `tests/unit/` — `test_settings.py`, `test_paths.py`, `test_validation.py`, `test_migrations.py`, `test_locale_init.py` (asserts LC_NUMERIC=C after importing each entry path)
- `import-linter` config in `pyproject.toml` enforcing boundary rules above

**Schema v1 — `db/migrations/0001_initial.sql`:**

```sql
CREATE TABLE _migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    checksum   TEXT    NOT NULL,
    applied_at INTEGER NOT NULL
);

CREATE TABLE books (
    id               INTEGER PRIMARY KEY,
    book_uuid        TEXT    NOT NULL UNIQUE,
    path             TEXT    NOT NULL UNIQUE,
    kind             TEXT    NOT NULL CHECK (kind IN ('folder', 'file')),
    title            TEXT    NOT NULL,
    author           TEXT,
    narrator         TEXT,
    series           TEXT,
    series_index     REAL,
    description      TEXT,
    duration_ms      INTEGER,
    cover_path       TEXT,
    added_at         INTEGER NOT NULL,
    last_played_at   INTEGER,
    status           TEXT    NOT NULL DEFAULT 'present'
                     CHECK (status IN ('present', 'missing', 'archived'))
);

CREATE TABLE tracks (
    id             INTEGER PRIMARY KEY,
    book_id        INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    path           TEXT    NOT NULL,
    order_index    INTEGER NOT NULL,
    duration_ms    INTEGER,
    file_mtime     INTEGER NOT NULL
);

CREATE TABLE positions (
    book_id      INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
    position_ms  INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL
);

CREATE TABLE bookmarks (
    id           INTEGER PRIMARY KEY,
    book_id      INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    position_ms  INTEGER NOT NULL,
    note         TEXT,
    created_at   INTEGER NOT NULL
);

CREATE TABLE metadata_overrides (
    book_id           INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
    title             TEXT,
    author            TEXT,
    narrator          TEXT,
    series            TEXT,
    series_index      REAL,
    description       TEXT,
    cover_overridden  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE watched_folders (
    id               INTEGER PRIMARY KEY,
    path             TEXT    NOT NULL UNIQUE,
    enabled          INTEGER NOT NULL DEFAULT 1,
    last_scanned_at  INTEGER
);

CREATE INDEX idx_books_last_played ON books(last_played_at DESC);
CREATE INDEX idx_tracks_book       ON tracks(book_id, order_index);
CREATE INDEX idx_bookmarks_book    ON bookmarks(book_id, position_ms);
```

Notes on the schema:

- **Time fields are INTEGER milliseconds**, not REAL seconds. Avoids float-equality bugs in queries; matches what libmpv's `time-pos * 1000` rounds to.
- **`book_uuid` is the stable identity** — assigned on first scan, persisted to a `.skald.json` sidecar file in the book folder (or alongside a single-file book). Survives folder renames. Scanner matches: (1) sidecar UUID, (2) fingerprint `sha256(first 64 KiB of first track + duration_ms)`, (3) fall back to `path`.
- **`status` has a CHECK constraint** including `'archived'` (soft-delete future use).
- **`tracks.file_mtime`** lets the scanner detect external re-tagging and re-extract metadata.
- **`metadata_overrides` stays as a separate table** — makes "reset to embedded metadata" a clean `DELETE FROM metadata_overrides WHERE book_id=?`. Reads always use `COALESCE(o.field, b.field)` via a single repository helper (`library.get_book(book_id)`) so no caller forgets the COALESCE.
- **`books.cover_path`** is the canonical pointer (may be inside the user's media folder, our covers dir, or our thumbnails dir, depending). The 360px thumbnail lives at `<thumbnails_dir>/<book_uuid>.jpg`.
- **`_migrations` audit table** alongside `PRAGMA user_version` gives ordering, names, timestamps, and checksums for debuggability.
- **No `idx_books_status`** — two-value low-cardinality column doesn't benefit from a btree.

**Acceptance:** `pre-commit run --all-files` passes; `pytest` passes; `skald --version` prints version; `mypy src/skald` clean; `lint-imports` clean.

#### Phase 2 — Audio engine + chapters + position memory (1.5 days)

- `player.py` — wraps `mpv.MPV(vo='null', ytdl=False, audio_pitch_correction=True)`; exposes `play(path)`, `pause()`, `resume()`, `seek(s, relative)`, `set_speed(s)`, `position`, `chapter_index`, `chapter_list`, `terminate()`, `add_listener(cb) / remove_listener(cb)`. Observers (`time-pos`, `chapter`, `end-file`) call all registered listeners with a `PlayerEvent` value object. **No Qt imports in this file.**
- `playback_controller.py` — `Protocol` with `play / pause / next_chapter / prev_chapter / seek_relative / set_speed / get_state / add_listener / remove_listener`. Value object:
  ```python
  @dataclass(frozen=True, slots=True)
  class PlaybackState:
      position_ms: int
      duration_ms: int
      title: str
      chapter_title: str | None
      cover_path: Path | None
      is_playing: bool
      speed: float
  ```
- `chapters.py` — `extract_chapters(path) -> list[Chapter]`. Order: (1) mutagen MP4 `chpl`, (2) mutagen ID3 `CHAP`, (3) `mpv.chapter_list` fallback (handles MP4 chapter-text-tracks that mutagen issue #530 misses), (4) folder-of-files → one chapter per track using filename or `TIT2`.
- `positions.py` — `read(book_id) -> int | None` (ms), `write(book_id, ms)`. Periodic writer is a `QTimer` (or `threading.Timer` in CLI) that runs every 5s **only while playback is active** — stops on pause; resumes on play. Event-driven writes always fire (pause, seek, chapter change, app exit, focus loss).
- `tests/integration/test_playback.py` — uses the conftest-generated fixtures. Asserts: load, play, position advances, seek works, speed sets, chapter list returns, terminate is clean.

**Acceptance:** Can play a fixture file headlessly via `python -c "from skald.player import Player; ..."`. Position persists across restarts within tests. `player.terminate()` returns cleanly under pytest.

#### Phase 3 — Library scanner + metadata + covers (1.5 days)

- `scanner.py` — `scan(folder: Path)` runs on a `QThread` (or background thread in CLI). Emits incremental signals: `progress(done, total, current_folder)`, `book_discovered(book_id)`, `finished(added, missing)`. Heuristics:
  - `os.walk(folder, followlinks=False)`; deduplicate by `(st_dev, st_ino)`; max depth 8; max files per book 500
  - Every path goes through `Path.resolve(strict=True)` and `is_relative_to(watched_root.resolve())` — refuses paths that escape the watched root via symlinks
  - First directory containing audio files = the book; do not recurse below
  - Detect `CD01/`, `disc 1/`, `cd1/` (case-insensitive) subfolders and group as one book
  - Track ordering: perfect 1..N `track` tags wins; else natural-sort by filename
  - A single `.m4b` / `.m4a` / `.mp3` in a watched folder is a book
  - Identity via sidecar `.skald.json` UUID → fingerprint → path
- `metadata.py` — extract from (1) embedded tags via mutagen, (2) folder/filename pattern `Author/Book` or `Author - Book`, (3) `metadata_overrides` (wins). Title falls back to folder name. Re-extracts on `file_mtime` change.
- `covers.py` — extract embedded cover (`APIC` for ID3, `covr` for MP4) or `cover.jpg` / `folder.jpg` in the book folder; write original to `<covers_dir>/<book_uuid>.jpg`; write 360px thumbnail (2× for HiDPI) to `<thumbnails_dir>/<book_uuid>.jpg`. User uploads (Phase 7) re-encode through `QImageReader` with allocation limit before writing.
- Missing-file handling: books whose `path` no longer resolves get `status = 'missing'` (never deleted). Re-detected paths reset to `'present'`.
- Tests: scanner on a fixture tree (folder_book + standalone .m4b + CD-style fixture + symlink-loop fixture), metadata extraction round-trip, override application order, symlink-loop guard.

**Acceptance:** `scan()` returns the right number of books for each fixture topology; metadata overrides take precedence over embedded; missing books survive rescans with state intact; symlink loop does not hang.

#### Phase 4 — CLI (1 day)

- `cli/__init__.py` — Typer app; global `--debug` flag wires `logging_setup.configure_logging(debug=True)`
- `cli/play.py` — Headless TUI player using `rich.live` for the progress bar + chapter + speed + time display. Keystroke handling via `readchar` (simpler than prompt_toolkit; no async). Calls `validate_media_path()` on the argument. Bindings match the GUI table where applicable. The TUI IS the play command — no separate `tui/` directory.
- `cli/scan.py` — Adds folder to `watched_folders`, runs scanner, prints summary
- `cli/library.py` — Prints library as a `rich.table.Table`; `--status`, `--author`, `--sort` filters
- Single-instance gate: `single_instance.py` exposes `gui_is_running() -> bool` via a `QLocalSocket` connect probe (atomic, self-healing). `cli/play.py` refuses if a GUI is up, printing the future `--isolated` hint
- Tests for argument parsing and command dispatch

**Acceptance:** `skald --help`, `skald scan ~/Audiobooks`, `skald library`, and `skald play <path>` all work; refusal message fires when a (mocked) GUI is up.

#### Phase 5 — GUI shell + theme + single-instance (2.5 days)

- `gui/app.py` — `QApplication` setup (locale fix is already done in `__main__.py`): `app.setStyle("Fusion")`, single-instance gate (`QLocalServer` with `UserAccessOption`, socket in `runtime_dir()` with 0700; second-launch forwarding via `QLocalSocket`), translator install (BEFORE any widget construction), theme load, `QPixmapCache.setCacheLimit(64 * 1024)`
- `gui/main_window.py` — Top-level window: `QSplitter(Qt.Horizontal)` containing the library panel (left) and a `QStackedWidget` (right) for library / book-detail switching. Persistent bottom player bar in a vertical `QVBoxLayout` outside the splitter. Library-pane collapse via stored `sizes` + `setSizes([0, total])` (never `hide()` — that loses splitter geometry). UI state (splitter sizes, last-used view mode, window geometry) lives in `QSettings`, not `config.toml` or SQLite.
- Toolbar with hamburger button (toggle library pane), theme selector, settings button
- `gui/player_bar.py` — Cover thumbnail, title/chapter label, transport buttons (prev-chapter, back-10, play/pause, forward-30, next-chapter), seek slider, time labels, speed control, volume control, sleep timer button
- `gui/theme.py` — Loads `resources/themes/dark.qss.template` / `light.qss.template`. Substitution via `string.Template` (`$accent`, `$bg`, etc.) — NOT `str.format` (collides with QSS's `{` selectors). `apply_theme(name)` reloads + walks widgets calling `style().unpolish/polish()` for any with dynamic state properties. Listens to `app.styleHints().colorSchemeChanged` when `theme=auto`.
- `gui/app.py` bridges `player`'s listener callbacks to Qt signals via a single boundary `QObject` (`PlayerSignals`) so widgets connect normally
- Defer OS-specific imports: `from skald.integration import init_media_keys; init_media_keys(controller)` inside that function does the `if sys.platform == "linux": from skald.integration.mpris import ...` lazy import
- Keyboard shortcuts wired per Q15 brainstorm table
- Tests: `pytest-qt` spot checks for "splitter collapses on toggle" and "theme switch doesn't crash"

**Acceptance:** GUI launches, library pane collapses and restores, theme switch (dark/light/follow-system) works without restart, second launch focuses the existing window.

#### Phase 6 — GUI library view (2 days)

- `gui/library_view.py` — Two visual modes backed by a single `QAbstractListModel`:
  - **Grid:** `QListView.setViewMode(IconMode)` + custom `QStyledItemDelegate` painting cover thumbnail (from `<thumbnails_dir>/<book_uuid>.jpg`, never the original — that's only loaded in detail view), title, author, progress bar
  - **List:** `QTableView` with sortable columns (Title, Author, Length, Progress, Last Played)
  - `QListView.setUniformItemSizes(True)` + `setLayoutMode(Batched)` for grid scroll perf
- The delegate must not do I/O. `QPixmapCache` (64 MB) caches loaded thumbnails by `book_uuid`. A `QThreadPool` background-loads any cache misses triggered by scroll visibility.
- Toggle button in toolbar swaps mode; choice persists in `QSettings`
- Sort menu (5 sort orders), filter dropdown (`All / In Progress / Finished / Not Started`)
- Empty state: prominent "Add folder" button + helper text describing supported folder layouts (Q16)
- "Continue listening" tile at the top of the library when there's a last-played book — selecting opens the book detail view (does **not** auto-play)
- Tests: model produces the right row counts under each filter

**Acceptance:** Library renders grid and list, sort/filter work, "Add folder" picker pre-fills `~/Audiobooks` / `%USERPROFILE%\Audiobooks` and offers to mkdir if missing. Grid scrolls smoothly at 500 books.

#### Phase 7 — GUI book detail + dialogs (2.5 days)

- `gui/book_detail.py` — Large cover (loaded from `<covers_dir>`, not the thumbnail), metadata block, big Play/Resume button, chapter list (`QListWidget`, click to jump), bookmarks list with add/edit/delete, Edit-metadata button
- `gui/dialogs.py` — Three dialog classes in a single file (split when it exceeds ~300 lines):
  - `EditMetadataDialog` — fields for title/author/narrator/series/description; saves to `metadata_overrides`
  - `CoverUploadDialog` — file picker + drag-and-drop. **Re-encodes via `QImageReader` with `setAllocationLimit(64)` MB**, clamps dimensions to 4096×4096, file size cap 10 MB pre-decode, accepts JPEG/PNG only, writes JPEG quality 85 to `<covers_dir>/<book_uuid>.jpg` (strips EXIF/ICC). Never stores user bytes verbatim. Sets `metadata_overrides.cover_overridden = 1`. Also re-generates the thumbnail.
  - `SleepTimerDialog` — radio buttons (15/30/45/60 min, end-of-chapter, custom); on fire, `QTimer` calls `player.pause()`
- Bookmarks: add at current position (key `B`), edit note inline, delete with confirmation
- Tests: metadata override round-trip; cover replace overwrites prior file; sleep timer pauses player at expiry (`qtbot.wait`)

**Acceptance:** Editing metadata, uploading a cover (including a malformed image rejection path), adding bookmarks, and triggering a sleep timer all work end-to-end.

#### Phase 8 — OS integration: media keys + file associations (2.5 days)

- `playback_controller.py` is already defined (Phase 2). `MainPlaybackController` is the production implementation wrapping `Player` + library lookups; subscribes to player events and recomputes `PlaybackState`.
- `integration/__init__.py` exposes `init_media_keys(controller) -> Adapter`:
  ```python
  def init_media_keys(controller: PlaybackController) -> MediaKeyAdapter:
      if sys.platform == "linux":
          from skald.integration.mpris import MprisAdapter
          return MprisAdapter(controller)
      elif sys.platform == "win32":
          from skald.integration.smtc import SmtcAdapter
          return SmtcAdapter(controller)
      return NullAdapter()
  ```
- `integration/mpris.py` — `mpris_server`-backed. Bus name `org.mpris.MediaPlayer2.skald`. Runs on a `QThread` driving `dbus-fast`'s asyncio loop (pick one: not `qasync` for v1 — fewer moving parts). Subscribes to controller `add_listener`. Imports `dbus_fast` / `mpris_server` lazily at adapter construction.
- `integration/smtc.py` — Uses `winrt-Windows.Media.SystemMediaTransportControls`. HWND interop via `ISystemMediaTransportControlsInterop::GetForWindow(HWND)` through ctypes against `Windows.Media.dll`; HWND from `QMainWindow.winId()`. Updates display via `display_updater.music_properties` and cover via `winrt-Windows.Storage.Streams.RandomAccessStreamReference`. Subscribes to `ButtonPressed`, dispatches by `args.button`.
- **Throttling**: position updates emit to MPRIS at most every 5s; SMTC `SetTimelineProperties` at most every 5s. Metadata-changed only on actual track/chapter/title/cover change (per MPRIS spec — clients query position, not poll-push).
- Teardown order: integration adapters unregister bus name / SMTC association *before* `player.terminate()` on `aboutToQuit`. Stale `org.mpris.MediaPlayer2.skald` would otherwise linger on the bus.
- Linux file association via `packaging/linux/skald.desktop` with `MimeType=audio/mp4;audio/x-m4b;audio/mpeg;application/ogg;` etc. Windows file association handled by Inno Setup (Phase 10).
- File-association handoff: when the OS hands `skald.exe "C:\path\foo.m4b"` to the running instance via `QLocalSocket`, the receiver decodes the bytes as a single argv (not split on spaces) and routes through `validate_media_path()`.
- Tests: mock the OS integration adapter; verify the controller forwards play/pause requests correctly

**Acceptance:** GNOME/KDE media keys (and `playerctl`) drive playback on Linux; Windows lock-screen media controls show the book + cover and respond to play/pause.

#### Phase 9 — First-run, accessibility, i18n, update check (1.5 days)

- First-run flow: empty library shows a banner with a prominent "Add folder" button (no modal wizard); folder picker pre-filled with `~/Audiobooks` (Linux) or `%USERPROFILE%\Audiobooks` (Windows), offer mkdir-if-missing
- i18n scaffolding: all user-facing strings via `self.tr(...)` or `QCoreApplication.translate(...)`; `pyside6-lupdate` extracts to `resources/translations/skald_en.ts`; `pyside6-lrelease` compiles `.qm`. CI step verifies extraction is up-to-date. Translator installed in `gui/app.py` *before* any widget construction.
- Accessibility audit pass: tab order verification, `setAccessibleName` on custom widgets (transport buttons, sleep timer, chapter list), keyboard-only smoke test, contrast checker against `#C45A3A` on both themes (adjust shade if needed for WCAG-AA)
- `updates.py` — On startup (gated by `config.toml: check_for_updates = true`), HTTPS GET `https://api.github.com/repos/ludothegreat/skald/releases/latest` with:
  - 5-second timeout
  - explicit `User-Agent: skald/X.Y.Z`
  - max 3 redirects
  - stdlib `urllib.request` (no `requests` dep) with `certifi`-backed TLS
  - errors silent (logged only)
- Compare `tag_name` against `__version__` using `packaging.version.Version`. If newer, show a non-modal banner with a "Open download page" button.
- Privacy paragraph added to README documenting the only network call

**Acceptance:** Fresh install → empty library prompt works; tab cycles through all controls; screen reader (Orca on Linux) announces transport buttons; update banner appears when a fake newer tag is mocked in tests.

#### Phase 10 — Distribution, CI, release v0.1.0 (1.5 days)

- `packaging/linux/AppImageBuilder.yml` (or a `linuxdeploy` invocation script). Build on Ubuntu 22.04 runner specifically (glibc 2.35 — never `ubuntu-latest` which is too new for downstream compatibility). libmpv is **distro-installed**, not bundled — recipe declares `libmpv2` as a runtime dep
- `packaging/linux/PKGBUILD` for AUR; depends on `mpv`, `python>=3.12`, `python-pyside6`, etc.
- `packaging/windows/skald.iss` — Inno Setup: registers `.m4b` association under `HKCU`, Start Menu shortcut, uninstall entry, embeds the PyInstaller `--onedir` output
- `pyinstaller.spec` (or CLI args in CI): `--onedir`, `--windowed`, `--add-binary "libmpv-2.dll;."` on Windows
- **`libmpv-2.dll` is fetched at CI build time**, not vendored in-repo, so each `skald` release auto-picks up upstream libmpv security fixes:
  ```yaml
  - name: Fetch libmpv
    run: |
      Invoke-WebRequest -Uri "https://sourceforge.net/projects/mpv-player-windows/files/libmpv/mpv-dev-x86_64-LATEST.7z" -OutFile mpv.7z
      7z x mpv.7z -ompv
      Copy-Item mpv\libmpv-2.dll .\dist\skald\
  ```
  SHA256 of the bundled DLL is recorded in `CHANGELOG.md` per release.
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
        - run: pip install -e .[dev,linux]   # or [dev,windows] on Windows
        - run: pre-commit run --all-files
        - run: lint-imports
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
        - # checkout, setup-python, apt install libmpv2 libmpv-dev, pip install -e .[linux]
        - # pyinstaller --onedir
        - # linuxdeploy + appimagetool → skald-X.Y.Z-x86_64.AppImage
        - uses: actions/upload-artifact@v4
    build-windows:
      runs-on: windows-latest
      steps:
        - # checkout, setup-python, fetch libmpv-2.dll, pip install -e .[windows]
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
        - name: Generate SHA256SUMS
          run: |
            cd artifacts
            sha256sum *.AppImage *.exe > SHA256SUMS.txt
        - uses: softprops/action-gh-release@v2
          with:
            files: |
              artifacts/**/*.AppImage
              artifacts/**/*.exe
              artifacts/SHA256SUMS.txt
            generate_release_notes: true
            prerelease: ${{ contains(github.ref_name, '-') }}
  ```
- `MANUAL_TEST_PLAN.md` — checklist of things automation can't cover: GUI look-and-feel on both themes, media keys on real KDE / Windows installs, sleep timer ticking down, missing-file badge, single-instance focus, file-association handoff
- README update:
  - Install instructions per OS (download AppImage / Windows installer; **never `pip install skald`** — the PyPI namespace is occupied by an unrelated package; document as a `tbds.md` follow-up)
  - SHA256 verification commands per OS (`sha256sum -c SHA256SUMS.txt` / `Get-FileHash`)
  - SmartScreen first-run note for Windows
  - Screenshots once GUI exists
  - Keyboard shortcuts table
  - Privacy paragraph about the update check
- App icon: ship a placeholder SVG (stylized harp/lyre in terracotta) — `tbds.md` notes future improvement
- Tag `v0.1.0` on gitforge — mirror push (already verified end-to-end) propagates to GitHub and triggers the release workflow

**Acceptance:** `v0.1.0` GitHub Release page has working `skald-0.1.0-x86_64.AppImage`, `skald-setup-0.1.0.exe`, and `SHA256SUMS.txt`. Both binaries launch and play an audiobook on a clean VM.

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

The brainstorm already rejected:

- **Rust + Tauri or egui** (Q3) — user is most familiar with Python and PySide6. Tradeoff accepted: ~80–150 MB bundle vs. ~5–20 MB for Rust.
- **`python-vlc`** (Q4) — clunkier API and worse chapter handling than mpv.
- **JSON files instead of SQLite** (Q9) — gets ugly at scale and loses queryability.
- **Online metadata lookup in v1** (Q8) — keeps app offline-clean; deferred.
- **macOS support** (Q17) — out of scope for v1.
- **Flatpak distribution** (Q17) — sandbox-permission work deferred.
- **AAX/AAXC (Audible DRM)** (Q2) — legal grey area + DRM complexity.

## System-Wide Impact

### Interaction graph

Within this single-process app, the chain when a user double-clicks a book in the GUI library:

```
LibraryView.item_double_clicked (Qt signal)
  → MainWindow.open_book(book_id)
    → MainPlaybackController.load(book)         ← reads positions + chapters via library.get_book
      → Player.load(path)                       ← libmpv loadfile (path from DB, no validate_media_path needed)
        → property observers wire up
        → 'time-pos' fires every ~1s on mpv event thread
          → Player.add_listener callbacks fire
            → PlayerSignals (the GUI boundary QObject) emits state_changed
              ↓                ↓                       ↓
            PlayerBar       BookDetail              integration adapters
            (UI update)     (UI update)             (MPRIS / SMTC, throttled to 5s)
      → every 5s while playing + on pause/seek/chapter:
        → positions.write(book_id, position_ms)
          → SQLite UPDATE (WAL, parameterized)
```

### Error propagation

| Failure point | Behavior | User-visible |
|---|---|---|
| libmpv can't open file | `Player.load` raises `PlayerError` | Toast: "Couldn't open: <filename>"; book marked `status='missing'` on rescan |
| SQLite locked (rare; single-instance gate + file lock prevent most) | `busy_timeout=5000` retries; if still locked, logged + skipped | Silent in normal use; log shows |
| mutagen can't parse | extraction falls back through chain (mpv chapter_list → folder inference → empty) | Book may have weak metadata until user edits |
| MPRIS/SMTC registration fails on startup | logged WARNING; rest of app continues | No media keys; everything else works |
| Update-check HTTP failure | logged DEBUG; no banner shown | Silent |
| Cover decode fails | fall back to a generic terracotta book-icon | Generic cover shown |
| Future-version DB | `MigrationError` raised before UI starts | Clear error message: "Library DB written by newer skald (v2). Upgrade or restore from backup." |
| Symlink loop in watched folder | scanner detects via `(st_dev, st_ino)` set; skips and logs | Logged; scan completes |
| Crafted image in cover upload | `QImageReader` allocation limit triggers; decode returns null | Dialog shows "Cannot decode image" |

Errors **never silently swallow** in the playback path. The mpv `end-file` event with `reason='error'` raises into the controller and surfaces as a toast.

### State lifecycle risks

- **Partial position write on crash**: single `UPDATE positions` is atomic in SQLite. WAL commit on `synchronous=NORMAL` is durable (no corruption; may lose the last commit on power loss — acceptable).
- **Stale `covers/<book_uuid>.jpg`** after a book is archived/removed: cascade FK deletes the row, but the file lingers. Cleanup: `library.gc_orphans()` called from scan completion.
- **Watched folder pointing at unmounted drive**: scanner detects `not folder.exists()`, logs WARNING, leaves that folder's books at `status='missing'`. Next scan when the drive is back restores them.
- **libmpv crash during playback**: process exits; user re-launches. Position is durable because positions write every 5s while playing + on chapter change.
- **Folder rename**: scanner's identity chain (sidecar UUID → fingerprint → path) re-attaches the moved folder to the existing book row; position/bookmarks/metadata follow.
- **External re-tag**: scanner's `file_mtime` check detects the change and re-extracts metadata; user overrides (`metadata_overrides` table) are preserved via the `COALESCE` read path.

### Integration test scenarios

1. **Folder-of-MP3s book with messy track tags** (some `track=`, some missing) — scanner natural-sorts, library shows correct order, chapter sidebar names match filenames
2. **M4B with embedded `chpl` chapters** — chapter detection via mutagen; click chapter in sidebar jumps to time; position resume lands within the right chapter
3. **Watched folder containing both a single-file book and a multi-file book** — both detected
4. **Watched folder with a symlink loop** — scanner doesn't hang; logs the dedup
5. **Network drive unplugged mid-listen** — `end-file` with `reason='error'` raises a toast; book marked missing on next rescan; the rest of the library is unaffected
6. **GUI running, user opens a `.m4b` via Windows Explorer double-click** — file association sends the path to the running GUI via `QLocalSocket`; receiver routes through `validate_media_path`; GUI focuses and opens the book detail view
7. **Theme change while playing** — full QSS reload mid-playback; player keeps playing; no visual flicker
8. **Second `skald play` launched while GUI running** — `QLocalSocket` probe detects GUI; CLI refuses with clear error message, exit code 1
9. **Folder renamed between scans** — book row preserved; position/bookmarks intact
10. **Mutagen returns empty chapter list for an M4B with chapter-text-track format** — falls back to mpv `chapter_list` and works correctly

## Acceptance Criteria

### Functional requirements (v1 ships when all are true)

- [ ] Playback works for MP3, M4B, M4A, OGG, FLAC on both Linux and Windows
- [ ] Folder-as-book and single-file-as-book both detected
- [ ] Variable speed 0.5×–3× with pitch preservation
- [ ] Skip forward 30s / back 10s (brainstorm Q6 default; configurable in `config.toml`)
- [ ] Sleep timer (15/30/45/60 min, end-of-chapter, custom)
- [ ] User bookmarks with notes (add/edit/delete)
- [ ] Per-book position memory; auto-resume on opening a book (not on launch)
- [ ] Library scan of one or more watched folders
- [ ] Manual cover-art upload (drag-drop + file picker) with image-bomb hardening
- [ ] Metadata editing dialog with override persistence
- [ ] Dark + Light + Follow-system themes; runtime switch; terracotta accent
- [ ] GUI library: grid + list views, sort, filter (in-progress / finished / not-started)
- [ ] GUI: collapsible left pane, persistent bottom player bar
- [ ] CLI: `skald play`, `skald scan`, `skald library` work
- [ ] Media keys: MPRIS on Linux, SMTC on Windows
- [ ] File association for `.m4b` registered (Linux `.desktop`, Windows Inno Setup)
- [ ] Single-instance GUI; CLI refuses to play when GUI is up
- [ ] Update-check banner (HTTPS GET to GH Releases) with opt-out
- [ ] Missing-file books surface with a badge and survive rescans
- [ ] Folder rename does not orphan position/bookmarks/metadata (identity via `book_uuid`)
- [ ] Re-tagging an audio file in an external editor triggers metadata re-extraction on next scan
- [ ] Scanner does not hang on symlink loops or recurse beyond depth 8
- [ ] CLI rejects audio paths outside the allowed extension set
- [ ] Cover upload re-encodes through `QImageReader` and never stores raw user bytes
- [ ] DB written by a newer skald is rejected with a clear error message

### Non-functional requirements

- [ ] WCAG-AA color contrast in both themes (verified with a contrast checker)
- [ ] Full keyboard navigation; tab order is logical; no mouse-only actions
- [ ] HiDPI scaling works correctly (test 1.25× and 1.5×)
- [ ] Screen-reader compatibility via Qt's default accessibility + `setAccessibleName` on custom widgets
- [ ] Qt i18n scaffolding present; English-only ship; `.ts` extraction reproducible in CI
- [ ] Startup time on a 100-book library < 2 seconds on a SATA SSD
- [ ] No remote crash reporting; no analytics; only network call is the optional update check
- [ ] Scanner runs on a background thread; UI stays responsive during a 500-book scan
- [ ] Grid view scrolls smoothly at 500 books on a 1080p display (no per-frame JPEG decode)
- [ ] Position-write timer is inactive while playback is paused
- [ ] MPRIS/SMTC position updates emitted no more than once per 5 seconds
- [ ] No `pip install skald` instructions in any documentation
- [ ] Release artifacts have `SHA256SUMS.txt` attached to the GitHub Release

### Quality gates

- [ ] `ruff check .` passes (including `S608` for SQL strings)
- [ ] `mypy src/skald` passes with no errors
- [ ] `lint-imports` passes (import-linter boundary contracts)
- [ ] `pytest -v` passes on both Linux and Windows CI runners
- [ ] `pre-commit run --all-files` passes
- [ ] CI test workflow green on `main` after every push
- [ ] CI release workflow on a test tag produces both AppImage and `.exe` artifacts + `SHA256SUMS.txt`
- [ ] `tests/conftest.py` generates audio fixtures via `ffmpeg`; no binary fixtures committed
- [ ] Migration test covers: fresh-install, v1→vN with seeded data, simulated mid-migration crash, future-DB refusal, checksum mismatch detection
- [ ] `MANUAL_TEST_PLAN.md` checklist run by Ludo before tagging `v0.1.0`

## Success Metrics

This is a personal project, so the metrics are qualitative:

- **Primary:** Ludo uses `skald` as their daily-driver audiobook player for one full audiobook on Linux and one on Windows, without falling back to another player.
- **Secondary:** Total v1 install size — AppImage under 50 MB (excluding distro-installed libmpv), Windows installer under 100 MB.
- **Secondary:** No data-loss bugs in the first month of personal use (position memory, bookmarks, library state).
- **Tertiary:** A second user successfully installs and uses it on their machine without one-on-one support.

## Dependencies & Prerequisites

### Runtime
- **libmpv 2.x** — Linux: distro package; Windows: `libmpv-2.dll` fetched at CI build time and bundled
- **Python 3.12+** — bundled by PyInstaller on Windows; AUR depends on system Python
- **Qt 6.7+** — bundled with PySide6 wheels on both OSes
- **D-Bus session bus** (Linux only, for MPRIS) — present by default on GNOME / KDE / XFCE

### Build/CI
- GitHub Actions `ubuntu-22.04` and `windows-latest` runners
- Inno Setup 6 (pre-installed on `windows-latest`)
- `linuxdeploy` + `linuxdeploy-plugin-python` on Ubuntu 22.04
- `softprops/action-gh-release@v2`, `Minionguyjpro/Inno-Setup-Action@v1`

### Already-completed prerequisite
- gitforge → GitHub mirror pushes tags. Verified end-to-end during repo setup. Captured in [`tbds.md`](../brainstorm/tbds.md).

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Windows SMTC HWND interop is the worst code in the project | High | Medium | Reference [DubyaDude/WindowsMediaController](https://github.com/DubyaDude/WindowsMediaController). Worst case: ship without SMTC in v1; document as a known limitation. MPRIS on Linux is dramatically simpler with `mpris_server`. |
| libmpv ABI break in a future distro | Medium | Low | Pin `python-mpv<2.0`; libmpv 2.x ABI has been stable for years. |
| AppImage glibc compatibility | Medium | Medium | Build on `ubuntu-22.04` specifically. Do not use `ubuntu-24.04` or `ubuntu-latest`. |
| Qt clobbers `LC_NUMERIC`; libmpv silently mis-parses on non-English locales | High (if forgotten) | High | First init in `__main__.py`. Pin as comment + `test_locale_init.py` asserts for all entry paths. |
| Update-check hits GitHub rate limits | Low | Low | Unauthenticated `/releases/latest` is 60/hr per IP; one call per startup is fine. Errors silent. |
| First-time Windows user spooked by SmartScreen | High | Low | Documented prominently in README. Future: code-signing in `future-features.md`. SHA256SUMS published on each release. |
| Bundle inflation past comfort threshold | Low | Low | `--onedir` keeps things inspectable. Periodic audit; trim unused PySide6 modules with `--exclude-module` if needed. |
| **Folder rename orphans user's position/bookmarks** | High | High | Stable `book_uuid` via `.skald.json` sidecar or content fingerprint. |
| **Power loss mid-migration corrupts DB** | Low | High | Explicit `BEGIN`/`COMMIT` around each migration; online backup before; `_migrations` audit table. |
| **User downgrades skald binary, opens newer-schema DB, code-path silently corrupts data** | Medium | High | Refuse to open DB with `user_version > EXPECTED_VERSION`. |
| **`QLocalServer` socket spoofed by another local user on shared Linux** | Low | Medium | `UserAccessOption` + `user_runtime_dir` with 0700 perms. |
| **Scanner hangs on symlink loop in watched folder** | Medium | Medium | `followlinks=False` + `(st_dev, st_ino)` dedup + depth cap. |
| **Malicious image triggers Qt CVE via cover upload** | Low | Medium | Re-encode through `QImageReader` with allocation limit; clamp dimensions; strip metadata. |
| **User runs `pip install skald` and gets unrelated PyPI package** | Medium | High | README never instructs `pip install`. |
| **Bundled `mpv-2.dll` carries stale ffmpeg CVEs into v0.N** | Medium | Medium | Fetch DLL at CI build time; record SHA256 per release. |
| **External re-tag (mp3tag) not detected on next scan** | High | Low | `tracks.file_mtime` triggers re-extraction. |
| **Synchronous scan freezes UI on a 500-book library** | High | Medium | `QThread`-based scanner with incremental progress signals. |

## Resource Requirements

- **One developer** (Ludo) — part-time over 2–3 months
- **Test hardware**: one Linux desktop (Arch), one Windows machine. Both already available.
- **GitHub Actions usage**: well within free-tier minutes (matrix tests < 10 min, releases < 30 min)
- **No paid services**: no Sentry, no analytics, no code-signing cert in v1
- **No additional infra**: gitforge.online already operating; GitHub repo already mirrored

## Future Considerations

All deferred features in [`docs/brainstorm/future-features.md`](../brainstorm/future-features.md). Highlights:

- Online metadata lookup (Open Library / Audible) behind a toggle
- CLI controls running GUI via local socket
- Flatpak distribution with sandbox permission handling
- Code signing (Windows Authenticode, Apple Developer for future macOS)
- macOS support as a deliberate effort
- GUI for keyboard rebinding (v1 is config.toml only)
- `skald play --isolated` flag for CLI alongside GUI with a separate DB
- Equalizer / mono mix
- Author / series filters in the library view
- External `.cue` / `chapters.txt` parsing
- AAX / AAXC support (legal grey area)
- Remote crash reporting (Sentry) if bug volume justifies it
- Claim the PyPI namespace for `skald` (currently held by an unrelated package)

## Documentation Plan

| Doc | When | Audience |
|---|---|---|
| `README.md` | Updated each phase; finalized for v0.1.0 | End users, contributors |
| `docs/brainstorm/*` | Already exists | Future-Ludo, future-contributors |
| `docs/plans/<this file>` | This document | Future-Ludo |
| `MANUAL_TEST_PLAN.md` | Phase 10 | Ludo before each release |
| Inline docstrings | Throughout (no AI-sounding comments per CLAUDE.md) | Code readers |
| `CHANGELOG.md` | Phase 10; manual edits per release; includes libmpv DLL SHA256 | End users; release notes |
| Screenshots | Phase 10 after GUI is final | README |
| App icon | Phase 10 placeholder; improve later | Branding |

## Sources & References

### Origin

- **Origin document:** [`docs/brainstorm/decisions.md`](../brainstorm/decisions.md) — 27 questions answered covering scope, architecture, UX, distribution, licensing, accessibility, i18n, telemetry, versioning, and runtime behavior. Key decisions carried forward:
  - **Q3 / Q4:** Python + PySide6 + python-mpv (audio engine)
  - **Q7 / Q9:** Multiple watched folders, read-only against user files, SQLite in platform-standard data dir, settings in separate `config.toml`
  - **Q11–Q14:** Two-pane layout with collapsible library pane, grid + list modes, custom QSS theme with `#C45A3A` terracotta accent on dark + light + follow-system
  - **Q17 / Q18:** AppImage + AUR + Inno Setup; update-check via GitHub Releases; no code signing in v1
  - **Q25:** Canonical source on gitforge.online; GitHub mirror is community surface; tag-mirror patch already applied and verified
  - **Q27:** No auto-resume on launch; position writes every 5s + events; missing-file books keep state; single-instance GUI; CLI refuses to run when GUI is up

- **Companion docs:**
  - [`docs/brainstorm/future-features.md`](../brainstorm/future-features.md) — 22+ deferred items
  - [`docs/brainstorm/learned-topics.md`](../brainstorm/learned-topics.md) — patterns to apply to future brainstorms
  - [`docs/brainstorm/tbds.md`](../brainstorm/tbds.md) — small loose ends (icon, gitforge-manager patch commit, contrast verification, PyPI namespace claim)

### User context

- **User's global instructions:** `/home/ludo/.claude/CLAUDE.md` — Python-first defaults, single-file-spike-then-scaffold, pre-commit / ruff / mypy as safety net for a non-programmer maintainer, no AI-sounding comments, verbose logging from day one
- **gitforge-manager API** at `http://localhost:7777` for canonical repo management

### External references (consulted 2026-05-22)

- [python-mpv on PyPI](https://pypi.org/project/python-mpv/) — version 1.0.8; API + locale fix + threading notes
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
- [alexdelorenzo/mpris_server](https://github.com/alexdelorenzo/mpris_server)
- [MPRIS MediaPlayer2.Player spec](https://specifications.freedesktop.org/mpris/latest/Player_Interface.html)
- [pywinrt/python-winsdk (deprecation notice)](https://github.com/pywinrt/python-winsdk) — `winsdk` deprecated
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
- [pydantic-settings on PyPI](https://pypi.org/project/pydantic-settings/) — typed settings via BaseSettings
- [import-linter docs](https://import-linter.readthedocs.io/) — boundary enforcement in CI
- [Qt Dynamic Properties and Stylesheets wiki](https://wiki.qt.io/Dynamic_Properties_and_Stylesheets) — `unpolish`/`polish` after dynamic property change
- [Fix PyQt/PySide styling on Linux pip install](https://www.pythonguis.com/faq/installation-via-pip-styling/) — `setStyle("Fusion")` baseline

### Related ecosystem

- Audiobookshelf (web-based, server-required) — closest open-source comparable
- Smart AudioBook Player (Android) — UX reference for chapter sidebar and bookmarks
- Voice (Android, F-Droid) — clean minimalist UI reference

---

# Appendix — Optional scope rollbacks

These are **not applied**. They contradict explicit brainstorm decisions. Listed so the option is visible if v1 schedule slips and you want to ship a leaner first release. Each can be re-added in v0.2.0 once v0.1.0 is shipping daily-driver use.

| Rollback | Saves | Contradicts brainstorm | When to consider |
|---|---|---|---|
| Drop MPRIS + SMTC (no media keys in v1) | ~2.5 days | Q6 (explicit) | If Phase 8 consumes more than 4 days |
| Drop i18n scaffolding (no `tr()` wrappers) | ~0.5 day | Q22 (explicit) | If `lupdate` / `lrelease` tooling fights you |
| Drop update-check banner | ~0.5 day | Q18 (explicit) | If GH API rate-limit / proxy environments cause bug reports |
| Single `db.py` instead of `db/{connection,migrations}.py` | ~minor | Style only | Anytime |
| Drop grid OR list view (pick list) | ~0.5 day | Q12 (explicit) | If grid view perf becomes a multi-day rabbit hole |
| Drop manual cover-art upload | ~0.5 day | Q8 (explicit) | If image re-encoding fights Qt for half a day |
| Drop multi-watched-folder support (single `~/Audiobooks`) | ~minor | Q7 | Anytime; most users have one folder |

The user explicitly answered each of these in the brainstorm. The simplicity reviewer's argument was that personal-project velocity matters more than scope fidelity. Both arguments are valid — decide at implementation time when you hit a wall, not pre-emptively.
