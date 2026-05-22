# skald — named for the Old Norse poet-storytellers who recited sagas aloud

Cross-platform audiobook player for Linux and Windows. GUI + CLI.

## Status

**Pre-alpha — not yet usable.** The project is currently in the brainstorm/planning phase. See `docs/brainstorm/` for the decisions, deferred features, and learned topics that will shape v1.

## Planned for v1

- Library scan of one or more watched folders (folder-as-book or single-file-as-book)
- Formats: MP3, M4B, M4A, OGG, FLAC
- Chapter navigation, variable speed (0.5×–3×) with pitch preservation, sleep timer, bookmarks
- Per-book position memory; media key support (MPRIS on Linux, SMTC on Windows)
- GUI built with PySide6 (Qt); custom dark/light/follow-system theme
- CLI: `skald play <path>` (headless terminal player) + `skald scan` + `skald list`

See `docs/brainstorm/decisions.md` for the full v1 scope.

## License

MIT — see `LICENSE`.
