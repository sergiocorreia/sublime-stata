# Linux/X11 execution bridge

## What Ctrl+B sends

The Linux backend never launches Stata and never starts a batch or PyStata session. It writes the
in-memory selection or buffer to a private temporary do-file and types one command into an already
running graphical Stata session:

```stata
do `"/tmp/sublime-stata-<unique-id>.do"'
```

This is why the submitted code can use the target window's current data, frames, macros, estimates,
and installed commands. It is also why Linux execution requires X11 and `xdotool`: Stata Automation
is Windows-only, while batch mode creates a different Stata process.

## Source preparation

- Nonempty selections expand to complete physical lines, merge when they overlap, and run in document
  order. With only carets, the complete unsaved buffer runs without changing the visible selection.
- A saved source uses its containing directory for a prepended `cd`. An unsaved source uses the sole
  open project folder when there is exactly one.
- If `#delimit ;` is active at the first selected line, the temporary wrapper preserves semicolon
  parsing. Commented delimiter directives are ignored.
- Raw standalone Mata source receives a temporary `mata:`/`end` wrapper. A `.mata` file that already
  contains a Mata block is left alone.
- Each UTF-8 temporary file has mode `0600`. Only exact package UUID files owned by the current user
  are eligible for cleanup after 24 hours.

## Window discovery and pinning

Window discovery starts from X11's visible stacking order, then verifies the candidate PID,
`/proc/<pid>/exe`, configured executable name/path, and window class. Known Stata Graph, Viewer, Data
Editor, and Do-file Editor children are excluded. This works when `window manage maintitle` has changed
the main Stata title, including the `Running: ...` titles used by `extra/dodo.ado`.

Without a pin, the topmost compatible Stata window is used. `Stata: Choose Target Window` shows title,
PID, and X11 ID and pins the complete window identity to the current Sublime window. A stale or reused
identity stops with an error; it never redirects code to another Stata session. Use `Stata: Use Most
Recent Window` to opt back into automatic targeting.

## Delivery modes

`activate_restore` is the default and supported mode. It waits until the Ctrl+B modifiers are
released, remembers the active Sublime X11 window, activates Stata, sends the configured Command-pane
focus sequence (default `Ctrl+1`), presses Escape, types the single `do` command, presses Return, and
restores Sublime in a `finally` path. The short focus flash is expected.

`background` sends the same focus and typing sequence to the target window without activating it. It
is experimental because window managers and applications may ignore synthetic input sent to an
inactive window. The backend never retries with another mode, which prevents accidental duplicate
execution.

## What “sent” means

X11 input injection has no reliable acknowledgement from Stata. A status message therefore says
**sent**, not accepted, completed, or successful. A busy Stata instance may ignore or defer the
Command-window input. If delivery or focus restoration is uncertain, inspect Stata before pressing
Ctrl+B again.

See [Troubleshooting](troubleshooting.md) for missing dependencies, Wayland, target selection, and
Command-pane focus problems.
