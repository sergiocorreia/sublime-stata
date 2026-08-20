# Stata for Sublime Text

A Sublime Text 4 package for writing and running Stata do-files, ado-files, and Mata code.

The Linux build bridge is designed for research sessions where Stata is already open: press
<kbd>Ctrl+B</kbd> in Sublime Text and the selected code—or the full unsaved buffer when there is no
selection—runs in the chosen Stata GUI window. The existing Stata session, data, frames, globals, and
installed commands stay available.

## Highlights

- Syntax highlighting for modern Stata, Mata, embedded Python, and `texdoc` LaTeX blocks.
- Active-session execution on Linux/X11 through `xdotool`.
- Explicit targeting when multiple Stata windows are open, with automatic topmost-window targeting
  only when unpinned.
- Contextual Stata help with <kbd>F1</kbd>.
- <kbd>Ctrl+Alt+U</kbd> toggles a dataset line between `save ..., replace` and `use ..., clear`.
- Command completions and snippets for common research workflows, including frames, `gtools`,
  `reghdfe`, `ppmlhdfe`, `rangestat`, merges, and project do-file headers.
- Literal-tab indentation and a 100-column ruler, matching
  [`extra/STATA_STYLE_GUIDE.md`](extra/STATA_STYLE_GUIDE.md).

## Requirements

- Sublime Text build 4205 or newer. The package explicitly uses Sublime's embedded Python 3.14
  environment; your system Python is unrelated.
- Stata with an already-running graphical Linux session for <kbd>Ctrl+B</kbd> execution.
- Linux/X11 and [`xdotool`](https://github.com/jordansissel/xdotool) for the active-window bridge.

Wayland does not provide the X11 window search and input facilities used by this bridge. Syntax,
snippets, and editing features still work there, but active-window execution currently requires an X11
session. See [Troubleshooting](docs/troubleshooting.md#wayland-is-not-supported-for-execution).

## Quick start on Linux

1. Install `xdotool` (on Ubuntu/Debian: `sudo apt install xdotool`).
2. In Sublime Text, choose **Preferences > Browse Packages…**.
3. Clone or symlink this repository into that directory with the exact folder name `Stata`.
4. Restart Sublime Text, open a `.do` file, and choose **Tools > Build System > Stata**.
5. Start Stata, then press <kbd>Ctrl+B</kbd> in Sublime Text.

For commands and platform-neutral installation details, see [Installation](docs/installation.md).

## Everyday commands

| Action | Shortcut | Command Palette |
| --- | --- | --- |
| Run selections, or the full buffer if none | <kbd>Ctrl+B</kbd> | `Stata: Run Selection or Buffer` |
| Help for selection or command at the caret | <kbd>F1</kbd> | `Stata: Help for Command` |
| Toggle `save` and `use` | <kbd>Ctrl+Alt+U</kbd> | `Stata: Toggle save/use` |
| Pin a particular Stata window | — | `Stata: Choose Target Window` |
| Return to automatic targeting | — | `Stata: Use Most Recent Window` |

The build bridge sends the in-memory text, so saving the do-file first is not required. Selected regions
are expanded to full lines and executed together. See [Usage](docs/usage.md) for targeting, settings,
the `build.txt` package-test workflow, and snippet triggers.

## Support status

- Linux/X11 is the primary supported active-window execution path.
- The isolated legacy Windows backend can validate `stata_path` and use the registered Automation
  server, but the current modernization work is centered on Linux.
- macOS and Wayland execution transports are not implemented.

## Documentation

- [Installation](docs/installation.md)
- [Usage and settings](docs/usage.md)
- [Linux/X11 execution](docs/linux-execution.md)
- [Completions and snippets](docs/completions-and-snippets.md)
- [Package-test build workflow](docs/build-workflow.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Architecture](docs/architecture.md)
- [Catalog regeneration](docs/catalog-regeneration.md)
- [Development and validation](docs/development.md)
- [Changelog](CHANGELOG.md)

The [`extra/`](extra/README.md) directory contains optional, project-specific research examples. The
package does not install, source, or execute those files automatically.

## Future work

Live-session introspection—an asynchronous bridge for variables and objects in the active Stata GUI
session—is intentionally deferred. It is useful, but it is separate from the reliable v1 execution path.

## License

[MIT](LICENSE)
