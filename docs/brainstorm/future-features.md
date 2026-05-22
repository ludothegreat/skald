# Future Features

Things deferred from v1 — captured here so they're not lost.

---

- **AAX / AAXC (Audible DRM) support** — Requires Audible activation bytes per account, decryption logic, and lives in a legal grey area. Defer until everything else is solid.
- **External chapter files** — Support reading `.cue` and `chapters.txt` files that ship alongside the audio. Uncommon in the wild, easy to bolt on later.
- **Equalizer** — 10-band EQ or voice-boost preset. Add if a user requests it; user said they won't use it personally.
- **Mono mix** — Collapse stereo to mono for single-sided-hearing accessibility. Add if requested.
- **Online metadata lookup** — Fetch cover art and descriptions from Audible / Open Library / Google Books / MusicBrainz when local data is missing or thin. Skipped in v1 to keep things offline and avoid third-party fragility; add behind a toggle later.
- **CLI control of running GUI** — `audiobook-player pause / next / speed / status` talking to a running GUI via socket/IPC. Skipped in v1 because the user doesn't need it; would be a nice add for scripting and shell hotkeys later.
- **Author / series library filters** — Filter the library view by author or by series name. Needs more UI work than v1's basic status filter (in-progress/finished/not-started); add once series tracking is fleshed out.
- **GUI for rebinding keyboard shortcuts** — v1 only lets you change shortcuts via `config.toml`. A proper Settings → Shortcuts page with key-capture is a later improvement.
- **Flatpak distribution** — Sandboxed Linux distribution via Flathub. Skipped for v1 because the watched-folder feature needs careful sandbox permission handling. Add once the manifest is built and tested.
- **Code signing (Windows + macOS)** — Real Authenticode cert for Windows, Apple Developer cert if/when we add macOS. Eliminates SmartScreen/Gatekeeper warnings. Defer until project is mature enough to justify the cost.
- **MSIX / Microsoft Store** — Modern Windows packaging. Needs developer account + signing. Not v1.
- **macOS support** — Needs a macOS GitHub Actions runner, macOS-specific QSS tweaks (system menu bar, native title bar), and Gatekeeper signing. Out of scope for v1.
- **Nightly builds** — Auto-publish a pre-release on every `main` push. Adds clutter without an active user base; revisit when there are testers.
- **Auto-generated changelog** — Use `git-cliff` or similar to build release notes from commits. Requires commit-message discipline; write changelogs by hand for v1.
- **Remote crash reporting (Sentry)** — Send stack traces somewhere queryable. Skipped in v1 to avoid network calls; add if bug volume warrants.
- **App-internal large-text mode** — Beyond OS font scaling. Defer until requested.
- **Reduced-motion mode** — Respect `prefers-reduced-motion` and offer an opt-in toggle. Defer until there are animations meaningful enough to need it.
- **Full WCAG 2.1 AA audit** — Real testing pass with screen readers, contrast checkers, keyboard-only nav. Deferred from v1 baseline accessibility.
- **pytest-qt GUI tests + E2E AppImage-launch tests** — Higher-fidelity automated coverage. Skipped in v1 due to flakiness and maintenance cost.
- **`skald play --isolated` flag** — CLI player that uses a separate DB so it can run alongside the GUI without write contention. Useful for SSH listening while a desktop session has the GUI open. v1 just refuses to launch the CLI player when the GUI is up.
