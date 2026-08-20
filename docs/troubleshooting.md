# Troubleshooting

## Start with the Sublime console

Choose **View > Show Console** and look for messages prefixed with `Stata`. Plugin import errors,
missing helpers, invalid settings, missing `build.txt` targets, and window-delivery failures are reported
there.

## `xdotool` is missing

Install it with the operating system package manager, then verify:

```sh
command -v xdotool
xdotool --version
```

Sublime Text must inherit a normal graphical-session environment, including `DISPLAY` and access to
the X server. A Sublime process started from a restricted service or unrelated SSH session may not have
that access.

## Wayland is not supported for execution

Check the session type:

```sh
echo "$XDG_SESSION_TYPE"
```

If it prints `wayland`, log into an X11/Xorg desktop session to use active-window execution. `xdotool`
uses X11's XTEST and window-management APIs; its upstream documentation notes that typing, searching,
and activation do not work correctly on Wayland or consistently through XWayland:
[xdotool Wayland notes](https://github.com/jordansissel/xdotool#wayland).

Do not grant broad input-device privileges to a replacement tool merely to bypass this limitation. A
native Wayland transport should be designed and tested separately.

## No Stata window was found

1. Start the graphical Stata executable, not console Stata.
2. Confirm its process name:

   ```sh
   ps -eo pid,comm,args | grep -E '[x]stata(-mp|-se)?'
   ```

3. Add its basename or absolute path to `linux_stata_executables`.
4. Run `Stata: Use Most Recent Window` and try <kbd>Ctrl+B</kbd> again.

To inspect visible titles manually:

```sh
xdotool search --onlyvisible --maxdepth 2 --class '.*' \
    getwindowclassname %@ getwindowname %@
```

This intentionally does not filter on the title, because `window manage maintitle` may replace the
usual Stata/StataNow title.

## Code goes to the wrong Stata window

Run `Stata: Choose Target Window` and select the intended session. The chosen X11 window is pinned to
the current Sublime window until `Stata: Use Most Recent Window` is run or that Sublime window closes.
If the target closes first, the next execution stops with a stale-pin error; the package never silently
redirects research code to another Stata session.

## Stata activates but the command does not run

The default `linux_command_focus_keys` value is `["ctrl+1"]`, which focuses the Stata Command
window before delivery. If the local Stata keymap differs, set the sequence that focuses the Command
window on that installation. Values use `xdotool key` names and are sent in order; the bridge then
sends <kbd>Escape</kbd> automatically.

Also try the default `activate_restore` mode before `background`; some window managers reject input to
a window that has not been activated. Delivery modes are never retried automatically. If Sublime
reports a delivery error, inspect the Stata Command and Results windows before pressing
<kbd>Ctrl+B</kbd> again.

## Sublime stays on the wrong build system

Open a Stata file, then choose **Tools > Build System > Stata**. The build selector covers both
`source.stata` and standalone `source.mata`.

## F1 or Ctrl+Alt+U does nothing

The default bindings are limited to the `source.stata` scope. Confirm that the status bar reports the
Stata syntax. User key bindings loaded later can override package bindings; invoke `Stata: Help for
Command` or `Stata: Toggle save/use` from the Command Palette to distinguish a binding conflict from a
plugin error.

## The package does not load

- Confirm the installed directory is named exactly `Stata` under the directory opened by
  **Preferences > Browse Packages…**.
- Remove or disable the unrelated legacy Package Control package also named `Stata`; an installed
  archive and a loose package with the same name can conflict.
- Confirm the root contains `.python-version` with `3.14`.
- Use Sublime Text build 4205 or newer.
- Restart Sublime Text and inspect the console for the first traceback.

Sublime documents package locations in [Packages](https://www.sublimetext.com/docs/packages.html) and
the embedded runtime in [API environments](https://www.sublimetext.com/docs/api_environments.html).
