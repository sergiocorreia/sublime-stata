# Usage and settings

## Running code in the active Stata session

With the Stata build system selected, <kbd>Ctrl+B</kbd> runs:

- every nonempty selection, expanded to complete lines; or
- the complete in-memory buffer when there is no selection.

The buffer does not need to be saved. The package writes the submitted text to a unique temporary
do-file, prepends a `cd` to the source file's directory when available, and tells the selected Stata GUI
session to run it. This preserves data, frames, globals, estimates, and other state already in that Stata
window. Temporary do-files are private to the current user; stale package-owned files are cleaned after
24 hours so asynchronous Stata execution is not interrupted.

For a standalone `.mata` file containing raw Mata source, the package adds a temporary `mata:`/`end`
execution wrapper. A conventional `.mata` source that already contains its own `mata:` block is sent
unchanged.

The default Linux delivery mode briefly activates Stata, focuses its Command window, submits the
temporary do-file, and restores Sublime Text. The command itself continues asynchronously in Stata.

## Choosing among Stata windows

Automatic targeting uses the most recently active compatible Stata window.

- `Stata: Choose Target Window` displays the visible candidates and pins the selected window.
- `Stata: Use Most Recent Window` clears that choice and resumes automatic targeting.

A pinned choice lasts for the current Sublime window until it is unpinned or that Sublime window
closes. If the target Stata window closes first, execution stops with an error instead of risking
delivery to a different research session. Choose another target or run `Stata: Use Most Recent Window`
explicitly.

## Dataset save/use toggle

Place a caret on a dataset I/O line and press <kbd>Ctrl+Alt+U</kbd>, or run
`Stata: Toggle save/use` from the Command Palette:

```stata
	save "$data/analysis.dta", replace
```

becomes

```stata
	use "$data/analysis.dta", clear
```

Running the command again performs the reverse transformation. Indentation and the dataset path are
preserved, including path spelling, quotes/macros, an explicit `.dta` suffix, and a trailing `//`
comment. The exact accepted forms are `save <path>, replace` and `use <path>, clear`, optionally ending
in `;` before the comment. The command applies to the current line or every selected line as one undo
step. It leaves nonmatches untouched and deliberately refuses varlists, extra options, prefixes,
continuations, block comments, and malformed or otherwise ambiguous paths.

## Contextual help

Select a Stata command, or place the caret on one, and press <kbd>F1</kbd>. The same action is available
as `Stata: Help for Command`.

## Package-test build variant

The `Run Package Test (build.txt)` build variant supports ado/Mata package development:

1. Put a file named `build.txt` beside the active `.ado` or `.mata` source file.
2. Store the relative path of the package's test do-file as the only nonblank content, for example
   `tests/test_reghdfe.do`.
3. Press <kbd>Ctrl+Shift+B</kbd> and select `Stata - Run Package Test (build.txt)`.

The referenced do-file runs in the chosen Stata window. A missing pointer or target is reported in the
Sublime console/status area instead of silently running a different file. See the focused
[package-test workflow](build-workflow.md) for the accepted pointer format and failure behavior.

## Settings

Open **Preferences > Package Settings > Stata > Settings**. User settings override these defaults:

```json
{
    "linux_delivery_mode": "activate_restore",
    "linux_command_focus_keys": ["ctrl+1"],
    "linux_stata_executables": ["xstata-mp", "xstata-se", "xstata"],
    "ado_paths": [],
    "command_priorities": [],
    "stata_path": ""
}
```

### `linux_delivery_mode`

- `"activate_restore"` (default): activate Stata for delivery and restore focus to Sublime Text.
- `"background"`: request delivery without raising Stata. Window-manager restrictions may make this
  less reliable, so use it only after verifying it on the local desktop. The package never retries with
  the other mode automatically, because doing so could execute research code twice.

### `linux_command_focus_keys`

An ordered list of `xdotool` key names sent to the target before submission. `ctrl+1` focuses Stata's
Command window in the supported Linux GUI. After these configured keys, the bridge always sends
<kbd>Escape</kbd> to clear partial Command-window input before typing the `do` command.

### `linux_stata_executables`

Executable basenames or absolute paths used to identify compatible Stata GUI processes. Put the
entries in any order; this is an identity allowlist, while the topmost compatible X11 window determines
automatic targeting.

### `ado_paths`

Absolute paths to additional personal or project ADO directories. Runtime command completion scans
these along with Stata's standard locations.

### `command_priorities`

An optional ordered list of personal overrides. Matching snippets always appear first. Plain commands
then use the bundled **very common**, **common**, and **infrequent/default** tiers derived from aggregate
do-file usage, with alphabetical ordering inside each tier. Personal overrides are placed before the
bundled tiers. This makes `clear` appear before `class` for the prefix `cl` by default.

### `stata_path`

Optional legacy Windows Automation executable path. The Windows backend validates this path and uses
it to give executable-specific registration guidance if COM activation fails. Automation still uses
Windows' registered `stata.StataOLEApp` server; this setting is never read by the Linux/X11 backend.

## Snippet triggers

Type a trigger and press <kbd>Tab</kbd>. Useful project-aligned triggers include:

| Trigger | Expansion |
| --- | --- |
| `dofile-template` | Project title, `include common.do`, and first section |
| `header` / `topheader` | Standard section or file-title rule |
| `forv` | `forvalues` numeric loop |
| `fornum` | `foreach ... of numlist` for an irregular sequence |
| `rename` | Full-name variable rename |
| `su` | Preferred summary command, with an optional `detail` placeholder |
| `mi-fn` | Compact `mi(varlist)` missing-value test |
| `frame-results` | Create, post to, and enter a results frame |
| `gegen-xtile` | Fast quantile categories, optionally by group |
| `merge` | One-line merge that leaves `_merge` available for checking |
| `merge-check` | Merge followed by `tab`, `assert`, and `drop _merge` |
| `join` | Dataset join using `ftools` |
| `reshape` | Reshape data between long and wide forms |
| `reghdfe` / `ppmlhdfe` | High-dimensional fixed-effect models |
| `rangestat` | Windowed statistics |
| `post-scalar` | Write a scalar for a LaTeX include |
| `import-delimited` | Import a TSV/CSV-style source file |

The package settings use literal tabs and show a 100-column ruler in Stata source files. The detailed
project conventions are in [`extra/STATA_STYLE_GUIDE.md`](../extra/STATA_STYLE_GUIDE.md).

## Delivery status and busy Stata sessions

The status message says that code was **sent**, not that it completed. The X11 bridge cannot reliably
tell whether a busy Stata Command window accepted the request or whether the resulting do-file later
finished. Check Stata before retrying a build after an uncertain delivery. In `activate_restore` mode,
briefly seeing Stata take focus is expected; `background` mode avoids that flash but has a greater risk
of silent non-delivery on some window managers.
