# Installation

## Supported setup

The active-window build bridge currently supports Linux desktop sessions running X11. It controls an
already-open Stata GUI with `xdotool`, preserving the session's data and state. Sublime Text build 4205
or newer is required because this package selects the embedded Python 3.14 API environment.

Sublime's own Python is used; do not install Python 3.14 or Python packages into the system interpreter
for this package. See Sublime Text's official documentation for
[API environments](https://www.sublimetext.com/docs/api_environments.html).

## 1. Install the X11 helper

Install `xdotool` with the system package manager:

```sh
# Ubuntu or Debian
sudo apt install xdotool

# Fedora
sudo dnf install xdotool

# Arch Linux
sudo pacman -S xdotool
```

Confirm that the desktop session is X11:

```sh
echo "$XDG_SESSION_TYPE"
```

The result should be `x11`. The upstream `xdotool` project explains why window search and synthetic
input do not work reliably on Wayland in its
[Wayland notes](https://github.com/jordansissel/xdotool#wayland).

## 2. Install the package as a loose package

In Sublime Text, select **Preferences > Browse Packages…**. This opens the data directory where loose
packages belong, as described in Sublime Text's
[package documentation](https://www.sublimetext.com/docs/packages.html#locations).

Clone the repository into that directory with the exact package folder name `Stata`:

```sh
cd "/path/opened/by/browse-packages"
git clone https://github.com/sergiocorreia/sublime-stata.git Stata
```

For development, keep the repository elsewhere and symlink it instead:

```sh
ln -s "/absolute/path/to/sublime-stata" "/path/opened/by/browse-packages/Stata"
```

The exact `Stata` name matters because package resources and menu links use that name. Restart Sublime
Text after the first installation. Later edits to a loose package normally reload automatically.

This repository is not the unrelated legacy package currently listed as
[`Stata` on Package Control](https://packagecontrol.io/packages/Stata). Remove or disable that package
before installing this repository under the same name, otherwise the two packages can conflict. Package
Control's **Add Repository** workflow is documented separately in its
[usage guide](https://packagecontrol.io/docs/usage), but a loose clone or symlink is the predictable
installation method while developing this package.

## 3. Select the syntax and build system

1. Open a `.do`, `.ado`, or `.mata` file.
2. If necessary, choose **View > Syntax > Stata** (or **Mata** for a standalone Mata file).
3. Choose **Tools > Build System > Stata**.
4. Start the Stata GUI.
5. Press <kbd>Ctrl+B</kbd>.

When more than one Stata window is open, run `Stata: Choose Target Window` from the Command Palette
to pin one. Run `Stata: Use Most Recent Window` to return to automatic selection.

## 4. Configure a nonstandard Stata installation

Open **Preferences > Package Settings > Stata > Settings** and override the executable list with
basenames or absolute paths. For example:

```json
{
    "linux_stata_executables": [
        "/usr/local/stata19/xstata-mp",
        "/usr/local/stata19/xstata-se",
        "/usr/local/stata19/xstata"
    ]
}
```

See [Usage and settings](usage.md#settings) for every supported option.

## Updating

If installed with Git, update from the package directory:

```sh
git pull --ff-only
```

Sublime Text normally reloads the modified package. Restart it if a Python plugin remains on the old
version, then check **View > Show Console** for load errors.

## Windows and macOS

The `stata_path` setting is retained for legacy Windows Automation installations. It validates an
optional executable path and can provide a specific `/Register` hint, but Stata's Automation server
must still be registered with Windows. Creating that COM object starts its own Stata Automation
instance; it does not attach to an arbitrary already-open GUI window. Windows is not the primary test
platform for this modernization. Editing features work on macOS, but this package does not yet provide
a macOS active-window execution transport.
