# Changelog

## Unreleased

### Added

- Linux/X11 delivery to an already-running Stata GUI through `xdotool`.
- Automatic Linux GUI startup when no compatible Stata window is open, preferring Stata/MP from
  `PATH`.
- Explicit Stata-window selection and most-recent-window targeting.
- Contextual <kbd>F1</kbd> help and the <kbd>Ctrl+Alt+U</kbd> dataset save/use toggle.
- Runtime completions for current Stata commands and configured personal ADO paths.
- Style-guide-aligned snippets for project do-files, frames, `gtools`, merges, regressions, and output.
- Installation, usage, troubleshooting, and development documentation.
- Dependency-free package validation and GitHub Actions coverage.

### Changed

- Preserved Stata command highlighting across `///` and longer slash continuations.
- Avoid xdotool's modifier snapshot/restore path during Linux delivery, preventing synthetic keys
  from remaining logically held and continuously resetting the desktop idle timer.
- Selected Sublime Text's embedded Python 3.14 runtime explicitly.
- Updated syntax coverage for modern Stata and standalone Mata files.
- Made literal tabs and a 100-column ruler the Stata source defaults.
- Replaced the old build variants with `Run Package Test (build.txt)`.
- Modernized menus and command-palette entries around the supported public commands.

### Removed

- Dead menu/key bindings for unimplemented variable, DTA, and split help commands.
- Generic Windows Automation registration/path commands from the cross-platform menu.
- Nonfunctional `Trace` and `Clear all` build variants.
- Deprecated `insheet` snippet in favor of `import delimited`.

## 1.0.0 - 2018-01-20

- Initial Sublime Text 3 package for Stata 13–15, with Windows Automation execution, syntax
  highlighting, snippets, and symbol navigation.
