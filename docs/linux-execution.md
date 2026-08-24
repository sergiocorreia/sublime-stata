# Linux/X11 execution bridge

## What Ctrl+B sends

The Linux backend writes the in-memory selection or buffer to a private temporary do-file and types
one command into a graphical Stata session:

```stata
do `"/tmp/sublime-stata-<unique-id>.do"'
```

This is why the submitted code can use the target window's current data, frames, macros, estimates,
and installed commands. It is also why Linux execution requires X11 and `xdotool`: Stata Automation
is Windows-only, while batch mode creates a different Stata process.

If no compatible window is visible, the backend starts a configured graphical executable. For each
candidate it checks `PATH`, then the conventional `/usr/local/stata19` installation directory. MP
candidates are tried first, followed by the remaining `linux_stata_executables` entries in their
configured order. The default preference is `xstata-mp`, `xstata-se`, then `xstata`. The backend waits
up to 20 seconds for a visible GUI, allows a short initialization interval, and then performs the same
one-time delivery sequence. Concurrent build jobs share a launch lock so they do not each start a new
Stata process. This is a GUI launch, not a batch or PyStata fallback.

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

When no compatible session remains and the package starts a replacement, any pin owned by that
Sublime window is cleared because its process no longer exists. Pins are never cleared merely because
a different compatible session is already open.

## Delivery modes

`activate_restore` is the default and supported mode. It waits until the Ctrl+B modifiers are
released, remembers the active Sublime X11 window, activates Stata, sends the configured Command-pane
focus sequence (default `Ctrl+1`), presses Escape, types the single `do` command, presses Return, and
restores Sublime in a `finally` path. The short focus flash is expected.

The bridge checks that physical modifiers are released before delivery and deliberately does not use
xdotool's `--clearmodifiers` option. That option clears and then synthetically restores a snapshot of
the modifier state; a physical release during that interval can otherwise leave the XTEST keyboard
with a logically held modifier.

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
