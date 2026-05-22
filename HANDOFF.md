# skald — Project Handoff

Everything needed to pick this project up and keep building.

---

## Current State (2026-05-22)

`skald` is a brand-new cross-platform (Linux + Windows) audiobook player. Day-1 work: brainstormed (27 questions), planned (11 phases, ~18 days), deepened (8-reviewer pass folded into the plan body), repo bootstrapped with gitforge→GitHub tag mirroring verified, and **Phase 0 spike PASSED** against a real 155 MB M4B. Next session picks up at **Phase 1 — project skeleton + quality bar** in `src/skald/`.

### What's Running
Nothing live yet. The project is at proof-of-concept. The Phase 0 spike at `spike/smoke.py` validates that python-mpv + PySide6 + mutagen work together on Python 3.14 on Arch.

### Branch Status
- Branch: `main` (committing directly per ADR — personal project, single contributor)
- 6 commits on `main`, all mirrored to GitHub
- Last commit: `c45d262` — Phase 0 spike
- No outstanding uncommitted changes in `/hoard/workspace/skald/`
- **CRITICAL outside-repo cleanup**: `/hoard/workspace/gitforge-manager/app.py` has an uncommitted patch (the tag-mirror fix) that needs to be committed to that repo separately

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12–3.14 (dev on 3.14) |
| GUI | PySide6 ≥6.7,<7.0 (currently 6.11.1) |
| Audio engine | python-mpv 1.0.8 + libmpv 2.x (system on Linux, bundled on Windows) |
| Metadata | mutagen 1.47 |
| Settings | pydantic-settings ≥2.5 (config.toml source) |
| CLI | Typer ≥0.12 + Rich for TUI |
| State | SQLite (WAL mode, threading.local per-thread, file-locked) |
| Paths | platformdirs ≥4.3 |
| Linux media keys | mpris-server + dbus-fast |
| Windows media keys | winrt-Windows.Media (3.x; `winsdk` is deprecated) |
| Packaging | PyInstaller --onedir → AppImage (linuxdeploy) + Inno Setup |
| CI | GitHub Actions on `ubuntu-22.04` + `windows-latest` |
| Dev tooling | ruff, mypy, pre-commit, import-linter, pytest, PySide6-stubs |

---

## Key Files

| File | Purpose |
|---|---|
| `docs/plans/2026-05-22-001-feat-skald-v1-audiobook-player-plan.md` | **Source of truth** — 873-line v1 plan with 11 phases, all corrections from the 8-reviewer deepening folded in |
| `docs/brainstorm/decisions.md` | 27-question brainstorm (origin doc); plan references decision numbers Q1–Q27 |
| `docs/brainstorm/future-features.md` | 22+ deferred items |
| `docs/brainstorm/learned-topics.md` | Patterns to apply to future brainstorms |
| `docs/brainstorm/tbds.md` | Loose ends (icon, gitforge-manager patch commit, contrast check, PyPI namespace) |
| `spike/spike.py` | Interactive single-file spike (kept as a reference for the Phase 4 TUI; not on path) |
| `spike/smoke.py` | Non-interactive Phase 0 verification — run this to confirm the toolchain still works |
| `README.md`, `LICENSE` (MIT), `.gitignore` | Standard repo scaffolding (present) |

**Not yet created** — comes in Phase 1: `pyproject.toml`, `src/skald/`, `tests/conftest.py`, `.pre-commit-config.yaml`, `.github/workflows/`.

---

## Database

No DB yet. Phase 1 creates `~/.local/share/skald/library.db` (SQLite, WAL mode). The schema (in `db/migrations/0001_initial.sql` per the plan) has tables: `_migrations`, `books`, `tracks`, `positions`, `bookmarks`, `metadata_overrides`, `watched_folders`.

**CRITICAL design choices folded in from the deepening pass:**
- Book identity is `book_uuid` (sidecar `.skald.json` → fingerprint → path fallback), **not** the file path — folder renames must not orphan position/bookmarks/metadata
- All time fields are `INTEGER milliseconds`, never `REAL seconds`
- Status has a `CHECK` constraint: `'present' | 'missing' | 'archived'`
- Migration runner uses manual `BEGIN`/.../`PRAGMA user_version = N`/`COMMIT` — **never `executescript()`** (which is NOT a transaction)
- DB refuses to open if `user_version > EXPECTED_VERSION` (prevents downgrade corruption)
- Online backup via `Connection.backup()` before any migration; rotates 3 backups

---

## Secrets

No secrets in skald itself. The only network call is the optional GitHub Releases ping for the update banner (Phase 9) — public unauthenticated endpoint. No analytics, no telemetry, no auth, no server component.

The gitforge mirror uses an SSH deploy key managed by gitforge-manager at `/srv/git/github-keys/skald.git.key` — managed by `gitforge-manager`, not by skald.

---

## Repo / mirror layout

- **Canonical:** `ssh://git@gitforge.online:27665/srv/git/repos/skald.git` (pure git-shell, no UI, no CI)
- **Mirror:** `github.com/ludothegreat/skald` (public; community surface — issues, PRs, releases, CI)
- **Tag mirror:** Verified working as of 2026-05-22. Required a patch to `/hoard/workspace/gitforge-manager/app.py` (lines ~342 and ~371) so the post-receive hook propagates tag refs. **That patch is still uncommitted in the gitforge-manager repo** — commit and push separately.

---

## Deploy / Distribution

Not yet deployable. Phase 10 ships:
- Linux: AppImage (built on ubuntu-22.04 specifically for glibc 2.35 floor) + AUR PKGBUILD
- Windows: Inno Setup `.exe` installer; `libmpv-2.dll` fetched at CI build time from `sourceforge.net/projects/mpv-player-windows/files/libmpv/` (not vendored — auto-tracks upstream security fixes)
- Release workflow on tag push (`v*`) emits both artifacts + `SHA256SUMS.txt` to GitHub Release via `softprops/action-gh-release@v2`
- **No code signing in v1** — SmartScreen warning documented in README

**CRITICAL:** README must **never** instruct `pip install skald` — `pypi.org/project/skald/` is occupied by an unrelated experiment-logger package. PyPI namespace claim is on `tbds.md`.

---

## Testing

Nothing automated yet. Phase 1 sets up `pytest`, `ruff`, `mypy`, `import-linter` via `pre-commit`. Phase 2 lands the first real tests (audio engine integration) against ffmpeg-generated fixtures in `tests/conftest.py` (no binary audio committed).

**To re-run the Phase 0 smoke test:**
```bash
cd /hoard/workspace/skald
.venv/bin/python spike/smoke.py "/hoard/books/audio/Rebecca C Mandeville - Rejected, Shamed, and Blamed.m4b"
```
Should print 10× `[ok]` lines and end with `Phase 0 smoke test PASSED`.

---

## What's NOT Done

The work plan: 11 phases, ~18 days focused (2–3 months part-time).

| Phase | Estimate | Status |
|---|---|---|
| 0 — Single-file spike | 0.5 d | ✅ **DONE** (commit `c45d262`) |
| 1 — Project skeleton + quality bar | 1 d | next up |
| 2 — Audio engine + chapters + position memory | 1.5 d | — |
| 3 — Library scanner + metadata + covers | 1.5 d | — |
| 4 — CLI (`skald play / scan / library`) | 1 d | — |
| 5 — GUI shell + themes + single-instance | 2.5 d | — |
| 6 — GUI library view (grid + list) | 2 d | — |
| 7 — Book detail + dialogs | 2.5 d | — |
| 8 — OS integration (MPRIS + SMTC) | 2.5 d | — |
| 9 — First-run + a11y + i18n + update check | 1.5 d | — |
| 10 — Distribution + CI + release v0.1.0 | 1.5 d | — |

**Outstanding non-implementation tasks:**
- Commit and push the `gitforge-manager/app.py` tag-mirror patch to that repo
- Decide on app icon (currently TBD per `tbds.md`)
- Eventually file a PyPI namespace dispute for `skald` if we want a pip install path

**Known constraints / gotchas to remember when resuming:**
- The `LC_NUMERIC=C` fix must be the first thing in `skald/__main__.py` — before any import. Qt clobbers it and libmpv silently mis-parses numeric properties on non-English locales. Smoke test in Phase 1 must assert this for every entry path (GUI/CLI/TUI).
- python-mpv property observers fire on the engine's event thread — never touch widgets from them. Marshal to Qt main thread via a `QObject.Signal` boundary; keep `player.py` Qt-free.
- The plan's pre-fold version is recoverable via `git show 39873fd`. The fold lives in commit `04d5149`.
