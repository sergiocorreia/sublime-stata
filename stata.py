"""Platform-neutral execution support for the Sublime Stata package.

This module deliberately has no dependency on Sublime Text. On Linux it
starts or drives a Stata GUI through xdotool; Windows imports remain lazy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid


DEFAULT_LINUX_EXECUTABLES = ("xstata-mp", "xstata-se", "xstata")
DEFAULT_LINUX_INSTALL_DIRS = ("/usr/local/stata19",)
DEFAULT_COMMAND_FOCUS_KEYS = ("ctrl+1",)
LINUX_STARTUP_TIMEOUT_SECONDS = 20.0
LINUX_STARTUP_POLL_SECONDS = 0.2
LINUX_STARTUP_SETTLE_SECONDS = 0.5
TEMP_PREFIX = "sublime-stata-"
TEMP_SUFFIX = ".do"
TEMP_MAX_AGE_SECONDS = 24 * 60 * 60
_TEMP_FILENAME = re.compile(
    r"^{}[0-9a-f]{{32}}{}$".format(re.escape(TEMP_PREFIX), re.escape(TEMP_SUFFIX))
)


class StataError(RuntimeError):
    """Base class for errors that should be shown to the user."""


class StataEnvironmentError(StataError):
    """The desktop environment cannot support the requested delivery."""


class StataWindowError(StataError):
    """No suitable Stata GUI window could be found."""


class BuildFileError(StataError):
    """A build.txt pointer or its target is invalid."""


@dataclass(frozen=True)
class StataWindow:
    window_id: int
    title: str
    pid: int | None = None
    executable: str | None = None
    stack_index: int = 0
    window_class: str = ""
    area: int = 0

    @property
    def label(self) -> str:
        pid = "?" if self.pid is None else str(self.pid)
        return "{}  —  PID {}  —  0x{:x}".format(
            self.title or "Stata", pid, self.window_id
        )


@dataclass(frozen=True)
class BuildSpec:
    contents: str
    cwd: str
    source_path: str


def ensure_trailing_newline(contents: str) -> str:
    if not contents or contents.endswith("\n"):
        return contents
    return contents + "\n"


def selected_or_buffer(contents: str, selections) -> str:
    """Return complete selected lines, or the complete buffer.

    ``selections`` is an iterable of ``(begin, end)`` integer pairs. Empty
    carets are ignored. Overlapping expanded lines are merged.
    """

    size = len(contents)
    regions = []
    for begin, end in selections:
        begin = min(size, max(0, int(begin)))
        end = min(size, max(0, int(end)))
        begin, end = sorted((begin, end))
        if begin == end:
            continue
        line_begin = contents.rfind("\n", 0, begin) + 1
        if end and contents[end - 1] == "\n":
            line_end = end
        else:
            newline = contents.find("\n", end)
            line_end = size if newline < 0 else newline + 1
        regions.append((line_begin, line_end))

    if not regions:
        return ensure_trailing_newline(contents)

    merged = []
    for begin, end in sorted(regions):
        if merged and begin <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((begin, end))
    return ensure_trailing_newline("".join(contents[a:b] for a, b in merged))


def quote_stata_string(value: str) -> str:
    """Represent a path with Stata compound double quotes.

    Compound quotes allow spaces, Unicode, ordinary backslashes, and embedded
    double quotes. The closing delimiter itself cannot occur in a pathname.
    """

    if any(character in value for character in ("\x00", "\r", "\n")):
        raise StataError("Stata paths cannot contain NUL or newline characters")
    if '"\'' in value:
        raise StataError("This path contains Stata's compound-quote closing sequence")
    escaped = value.replace("$", "\\$").replace("`", "\\`")
    return '`"{}"\''.format(escaped)


_DELIMIT_DIRECTIVE = re.compile(
    r"(?im)^[ \t]*#delimit[ \t]+(?P<delimiter>;|cr)(?:[ \t\r]|$)"
)


def active_delimiter(contents: str, offset: int | None = None) -> str:
    """Return the delimiter active immediately before ``offset``."""

    delimiter = "cr"
    prefix = contents if offset is None else contents[:max(0, min(len(contents), offset))]
    visible = _mask_stata_comments(prefix)
    for match in _DELIMIT_DIRECTIVE.finditer(visible):
        delimiter = match.group("delimiter").lower()
    return delimiter


def _mask_stata_comments(contents: str) -> str:
    """Replace Stata comments with spaces while retaining line structure."""

    output = []
    index = 0
    block_depth = 0
    line_comment = False
    quote_state = None
    compound_depth = 0
    only_space_on_line = True

    while index < len(contents):
        character = contents[index]
        pair = contents[index:index + 2]

        if character == "\n":
            output.append("\n")
            index += 1
            line_comment = False
            only_space_on_line = True
            continue

        if line_comment:
            output.append(" ")
            index += 1
            continue

        if block_depth:
            if pair == "/*":
                output.extend((" ", " "))
                block_depth += 1
                index += 2
            elif pair == "*/":
                output.extend((" ", " "))
                block_depth -= 1
                index += 2
            else:
                output.append(" ")
                index += 1
            continue

        if quote_state == "compound":
            output.append(character)
            if pair == '`"':
                output.append('"')
                compound_depth += 1
                index += 2
            elif pair == '"\'':
                output.append("'")
                compound_depth -= 1
                index += 2
                if compound_depth == 0:
                    quote_state = None
            else:
                index += 1
            only_space_on_line = False
            continue

        if quote_state == "simple":
            output.append(character)
            index += 1
            if character == '"':
                quote_state = None
            only_space_on_line = False
            continue

        if pair == '`"':
            output.extend(("`", '"'))
            quote_state = "compound"
            compound_depth = 1
            only_space_on_line = False
            index += 2
        elif character == '"':
            output.append(character)
            quote_state = "simple"
            only_space_on_line = False
            index += 1
        elif pair == "/*":
            output.extend((" ", " "))
            block_depth = 1
            index += 2
        elif pair == "//" or (only_space_on_line and character == "*"):
            output.append(" ")
            line_comment = True
            index += 1
        else:
            output.append(character)
            if character not in " \t\r":
                only_space_on_line = False
            index += 1

    return "".join(output)


def wrap_script(contents: str, cwd: str | None = None, delimiter: str = "cr") -> str:
    contents = ensure_trailing_newline(contents)
    prefix = ""
    if cwd:
        prefix += "cd {}\n".format(quote_stata_string(cwd))
    if delimiter == ";":
        prefix += "#delimit ;\n"
    elif delimiter != "cr":
        raise StataError("Unknown Stata delimiter: {}".format(delimiter))
    contents = prefix + contents
    return ensure_trailing_newline(contents)


_MATA_BLOCK_START = re.compile(r"(?im)^[ \t]*mata:?\s*(?://.*)?$")


def wrap_standalone_mata(contents: str) -> str:
    """Make raw standalone Mata source executable as a Stata do-file.

    Official ``.mata`` sources commonly contain their own ``mata:``/``end``
    wrapper. Those files are left unchanged; editor-native Mata files that
    contain only Mata declarations and expressions receive the wrapper.
    """

    contents = ensure_trailing_newline(contents)
    if _MATA_BLOCK_START.search(contents):
        return contents
    return "mata:\n{}end\n".format(contents)


def working_directory(filename: str | None, project_folders=()) -> str | None:
    if filename:
        return os.path.dirname(filename)
    folders = [folder for folder in project_folders if folder]
    return folders[0] if len(folders) == 1 else None


def read_build_spec(active_file: str) -> BuildSpec:
    """Resolve a sibling build.txt for an .ado or .mata source file."""

    if not active_file:
        raise BuildFileError("Build requires a saved .ado or .mata file")
    source = Path(active_file)
    if source.suffix.lower() not in (".ado", ".mata"):
        raise BuildFileError("Build mode is only available from .ado or .mata files")

    pointer = source.parent / "build.txt"
    if not pointer.is_file():
        raise BuildFileError("No build.txt exists next to {}".format(source.name))
    try:
        lines = [line.strip() for line in pointer.read_text(encoding="utf-8-sig").splitlines()]
    except (OSError, UnicodeError) as error:
        raise BuildFileError("Could not read {}: {}".format(pointer, error))
    lines = [line for line in lines if line and not line.startswith("#")]
    if len(lines) != 1:
        raise BuildFileError("build.txt must contain exactly one do-file path")
    target_text = lines[0]
    if len(target_text) >= 2 and target_text[0] == target_text[-1] and target_text[0] in "\"'":
        target_text = target_text[1:-1]
    target = Path(target_text).expanduser()
    if not target.is_absolute():
        target = pointer.parent / target
    target = target.resolve()
    if not target.is_file():
        raise BuildFileError("The build do-file does not exist: {}".format(target))
    try:
        contents = target.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise BuildFileError("Could not read {}: {}".format(target, error))
    return BuildSpec(ensure_trailing_newline(contents), str(pointer.parent), str(target))


class TempDoFileManager:
    """Create private do-files and remove only stale plugin-owned files."""

    def __init__(self, directory: str | None = None, max_age: int = TEMP_MAX_AGE_SECONDS):
        self.directory = Path(directory or tempfile.gettempdir())
        self.max_age = max_age

    def create(self, contents: str) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "{}{}{}".format(TEMP_PREFIX, uuid.uuid4().hex, TEMP_SUFFIX)
        descriptor = os.open(
            str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            stat.S_IRUSR | stat.S_IWUSR,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(ensure_trailing_newline(contents))
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
            raise
        return str(path)

    def cleanup_stale(self, now: float | None = None) -> list[str]:
        now = time.time() if now is None else now
        removed = []
        try:
            entries = list(self.directory.iterdir())
        except OSError:
            return removed
        for path in entries:
            if not _TEMP_FILENAME.fullmatch(path.name):
                continue
            try:
                metadata = path.lstat()
                if not stat.S_ISREG(metadata.st_mode) or now - metadata.st_mtime < self.max_age:
                    continue
                getuid = getattr(os, "getuid", None)
                if callable(getuid) and metadata.st_uid != getuid():
                    continue
                path.unlink()
                removed.append(str(path))
            except OSError:
                continue
        return removed


_MAIN_TITLE = re.compile(
    r"^\s*Stata(?:Now)?(?:/(?:BE|IC|SE|MP))?(?:\s+[0-9]+(?:\.[0-9]+)*)?\b",
    re.IGNORECASE,
)
_SPECIAL_WINDOW = re.compile(
    r"^\s*(?:Graph|Viewer|Data Editor|Do-file Editor|Variables Manager)\b",
    re.IGNORECASE,
)


def _main_window_score(title: str) -> int:
    if _MAIN_TITLE.search(title):
        return 100
    if "stata" in title.lower():
        return 20 - (10 if _SPECIAL_WINDOW.search(title) else 0)
    # Executable/PID validation is authoritative. A profile.do may replace
    # Stata's main title entirely (for example, with "Running: ...").
    return 1


def choose_recent_window(windows: list[StataWindow]) -> StataWindow:
    if not windows:
        raise StataWindowError(
            "No running Stata GUI window was found. Start Stata, then try again."
        )
    return windows[-1]


def choose_target_window(
    windows: list[StataWindow], pinned: StataWindow | int | None = None
) -> StataWindow:
    if pinned is None:
        return choose_recent_window(windows)
    pinned_window_id = pinned.window_id if isinstance(pinned, StataWindow) else pinned
    for window in windows:
        if window.window_id == pinned_window_id:
            if isinstance(pinned, StataWindow):
                same_pid = pinned.pid is not None and window.pid == pinned.pid
                same_executable = (
                    pinned.executable is not None
                    and window.executable is not None
                    and os.path.realpath(pinned.executable)
                    == os.path.realpath(window.executable)
                )
                if not (same_pid and same_executable):
                    break
            return window
    raise StataWindowError(
        "The pinned Stata window is no longer available. Use “Choose Target "
        "Window” to select another session, or “Use Most Recent Window” to "
        "explicitly return to automatic targeting."
    )


class XdotoolBackend:
    """Discover, start, and control a Stata GUI in an X11 session."""

    def __init__(self, binary="xdotool", xprop_binary="xprop", env=None,
                 runner=None, which=None, process_executable=None, sleeper=None,
                 modifiers_pressed=None, launcher=None,
                 install_dirs=DEFAULT_LINUX_INSTALL_DIRS):
        self.binary = binary
        self.xprop_binary = xprop_binary
        self.env = os.environ if env is None else env
        self.runner = runner or self._subprocess_runner
        self.which = which or shutil.which
        self.process_executable = process_executable or self._read_process_executable
        self.sleep = sleeper or time.sleep
        self.modifiers_pressed = modifiers_pressed or self._x11_modifiers_pressed
        self.launcher = launcher or self._subprocess_launcher
        if isinstance(install_dirs, (str, os.PathLike)):
            install_dirs = (install_dirs,)
        self.install_dirs = tuple(
            str(directory) for directory in (install_dirs or ()) if directory
        )
        self._launch_lock = threading.Lock()
        self._launched_processes = []

    @staticmethod
    def _subprocess_runner(argv):
        return subprocess.run(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=10, check=False,
        )

    def _subprocess_launcher(self, argv):
        return subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=dict(self.env),
            start_new_session=True,
            close_fds=True,
        )

    @staticmethod
    def _read_process_executable(pid: int) -> str | None:
        try:
            return os.readlink("/proc/{}/exe".format(pid))
        except OSError:
            try:
                with open("/proc/{}/comm".format(pid), encoding="utf-8") as handle:
                    return handle.read().strip()
            except OSError:
                return None

    def validate_environment(self) -> None:
        if str(self.env.get("XDG_SESSION_TYPE", "")).lower() == "wayland":
            raise StataEnvironmentError(
                "Sending code to the active Stata GUI is not supported on Wayland. "
                "Log into an X11 session to use Ctrl+B."
            )
        if not self.env.get("DISPLAY"):
            raise StataEnvironmentError(
                "No X11 display is available. Start Sublime Text in an X11 desktop session."
            )
        if not self.which(self.binary):
            raise StataEnvironmentError(
                "xdotool is required to send code to Stata on Linux. Install xdotool and retry."
            )

    def _x11_modifiers_pressed(self) -> bool:
        """Query non-locking X11 modifier state without another dependency."""

        try:
            import ctypes
            import ctypes.util

            library_name = ctypes.util.find_library("X11") or "libX11.so.6"
            x11 = ctypes.CDLL(library_name)
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            x11.XDefaultRootWindow.restype = ctypes.c_ulong
            x11.XQueryPointer.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_uint),
            ]
            x11.XQueryPointer.restype = ctypes.c_int
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

            display_name = str(self.env.get("DISPLAY", "")).encode("utf-8") or None
            display = x11.XOpenDisplay(display_name)
            if not display:
                raise RuntimeError("XOpenDisplay failed")
            try:
                root = x11.XDefaultRootWindow(display)
                root_return = ctypes.c_ulong()
                child_return = ctypes.c_ulong()
                root_x = ctypes.c_int()
                root_y = ctypes.c_int()
                window_x = ctypes.c_int()
                window_y = ctypes.c_int()
                mask = ctypes.c_uint()
                status = x11.XQueryPointer(
                    display,
                    root,
                    ctypes.byref(root_return),
                    ctypes.byref(child_return),
                    ctypes.byref(root_x),
                    ctypes.byref(root_y),
                    ctypes.byref(window_x),
                    ctypes.byref(window_y),
                    ctypes.byref(mask),
                )
                if not status:
                    raise RuntimeError("XQueryPointer failed")
            finally:
                x11.XCloseDisplay(display)
        except Exception as error:
            raise StataEnvironmentError(
                "Could not query X11 modifier keys before delivery: {}".format(error)
            ) from error

        # Ignore Caps Lock (LockMask) and Num Lock (normally Mod2Mask), which
        # may remain latched. Wait for Shift, Control, Alt/Meta, Super, AltGr,
        # and other non-locking modifier masks.
        non_locking_modifiers = 0x01 | 0x04 | 0x08 | 0x20 | 0x40 | 0x80
        return bool(mask.value & non_locking_modifiers)

    def _wait_for_modifier_release(self) -> None:
        for attempt in range(101):
            if not self.modifiers_pressed():
                return
            if attempt == 100:
                raise StataEnvironmentError(
                    "Release Ctrl, Shift, Alt, or Super before sending code to Stata"
                )
            self.sleep(0.01)

    def _run(self, arguments, allow_no_match=False) -> str:
        result = self.runner([self.binary] + list(arguments))
        if result.returncode and not (allow_no_match and result.returncode == 1):
            detail = (result.stderr or result.stdout or "unknown xdotool error").strip()
            raise StataEnvironmentError("xdotool failed: {}".format(detail))
        return result.stdout or ""

    @staticmethod
    def _parse_wm_class(output: str) -> str:
        """Return the two WM_CLASS values emitted by standard xprop."""

        if "=" not in output or "not found" in output.lower():
            return ""
        values = re.findall(r'"((?:\\.|[^"\\])*)"', output)
        return " ".join(values)

    def _window_class(self, window_id: int) -> str:
        """Read WM_CLASS with xprop when available.

        xdotool does not provide a getwindowclassname command in its standard
        Linux releases.  WM_CLASS improves main-window scoring, but remains
        optional because PID/executable discovery is sufficient for safety.
        """

        xprop = self.which(self.xprop_binary)
        if not xprop:
            return ""
        result = self.runner([xprop, "-id", str(window_id), "WM_CLASS"])
        if result.returncode:
            return ""
        return self._parse_wm_class(result.stdout or "")

    def active_window_id(self) -> int:
        """Return the active X11 window without changing focus."""

        self.validate_environment()
        active = self._run(["getactivewindow"]).strip()
        try:
            window_id = int(active, 0)
        except ValueError:
            raise StataEnvironmentError(
                "xdotool could not identify the active X11 window"
            )
        if window_id <= 0:
            raise StataEnvironmentError(
                "xdotool returned an invalid active X11 window"
            )
        return window_id

    def capture_sublime_window(self) -> int:
        """Capture and validate the originating Sublime X11 window."""

        window_id = self.active_window_id()
        try:
            pid_text = self._run(["getwindowpid", str(window_id)]).strip()
            pid = int(pid_text) if pid_text else None
        except (StataEnvironmentError, ValueError):
            pid = None
        executable = self.process_executable(pid) if pid is not None else None
        executable_name = os.path.basename(
            (executable or "").removesuffix(" (deleted)")
        ).lower()
        window_class = self._window_class(window_id).lower()
        if "sublime" not in executable_name and "sublime" not in window_class:
            raise StataEnvironmentError(
                "Ctrl+B did not originate from a Sublime Text X11 window "
                "(active executable: {!r}; class: {!r})".format(
                    executable_name or "unknown", window_class or "unknown"
                )
            )
        return window_id

    @staticmethod
    def _parse_window_ids(output: str) -> list[int]:
        ids = []
        for token in output.split():
            try:
                ids.append(int(token, 0))
            except ValueError:
                continue
        return ids

    @staticmethod
    def _allowed_executable(executable: str | None, configured) -> bool:
        if not executable:
            return False
        actual_path = executable.removesuffix(" (deleted)")
        actual_name = os.path.basename(actual_path)
        for item in configured:
            if not item:
                continue
            configured_path = os.path.expanduser(str(item))
            if os.path.isabs(configured_path):
                if os.path.realpath(actual_path) == os.path.realpath(configured_path):
                    return True
            elif actual_name == configured_path:
                return True
        return False

    def discover_windows(self, executables=DEFAULT_LINUX_EXECUTABLES) -> list[StataWindow]:
        self.validate_environment()
        output = self._run(
            ["search", "--onlyvisible", "--maxdepth", "2", "--class", ".*"],
            allow_no_match=True,
        )
        ids = self._parse_window_ids(output)

        candidates = []
        for index, window_id in enumerate(ids):
            try:
                pid_text = self._run(["getwindowpid", str(window_id)]).strip()
                pid = int(pid_text) if pid_text else None
            except (StataEnvironmentError, ValueError):
                continue
            executable = self.process_executable(pid) if pid is not None else None
            if not self._allowed_executable(executable, executables):
                continue
            try:
                title = self._run(["getwindowname", str(window_id)]).strip()
            except StataEnvironmentError:
                title = ""
            window_class = self._window_class(window_id)
            try:
                geometry = self._run(
                    ["getwindowgeometry", "--shell", str(window_id)]
                )
                width = re.search(r"(?m)^WIDTH=(\d+)$", geometry)
                height = re.search(r"(?m)^HEIGHT=(\d+)$", geometry)
                area = (
                    int(width.group(1)) * int(height.group(1))
                    if width and height else 0
                )
            except StataEnvironmentError:
                area = 0
            if _SPECIAL_WINDOW.search(title):
                continue
            title_score = _main_window_score(title)
            class_score = 1 if "stata" in window_class.lower() else 0
            # Class and geometry identify the main top-level window even when
            # profile.do has replaced the normal Stata/StataNow title.
            score = (class_score, area, title_score)
            candidates.append((score, StataWindow(
                window_id, title or "Stata", pid, executable, index,
                window_class, area,
            )))

        by_process = {}
        for score, window in candidates:
            key = window.pid if window.pid is not None else window.window_id
            previous = by_process.get(key)
            if previous is None or (score, window.stack_index) > (
                previous[0], previous[1].stack_index
            ):
                by_process[key] = (score, window)
        return sorted(
            (item[1] for item in by_process.values()), key=lambda window: window.stack_index
        )

    @staticmethod
    def _launch_order(executables) -> list[str]:
        """Return unique launch candidates with graphical MP builds first."""

        candidates = []
        for item in executables:
            candidate = str(item or "").strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        def is_mp(candidate: str) -> bool:
            name = os.path.basename(candidate).lower().replace("_", "-")
            return bool(re.search(r"stata(?:now)?-?mp(?:$|[-.])", name))

        return (
            [candidate for candidate in candidates if is_mp(candidate)]
            + [candidate for candidate in candidates if not is_mp(candidate)]
        )

    def _resolve_launch_executable(self, candidate: str) -> str | None:
        expanded = os.path.expandvars(os.path.expanduser(candidate))
        executable = self.which(expanded)
        if executable:
            return executable
        if os.path.basename(expanded) != expanded:
            return None
        for directory in self.install_dirs:
            root = os.path.expandvars(os.path.expanduser(str(directory)))
            path = os.path.join(root, expanded)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return None

    def launch_stata(self, executables=DEFAULT_LINUX_EXECUTABLES) -> str:
        """Start the preferred graphical Stata executable from known locations."""

        self.validate_environment()
        launch_order = self._launch_order(executables)
        executable = None
        for candidate in launch_order:
            executable = self._resolve_launch_executable(candidate)
            if executable:
                break
        if not executable:
            expected = ", ".join(launch_order) or ", ".join(DEFAULT_LINUX_EXECUTABLES)
            locations = "PATH"
            if self.install_dirs:
                locations += " or " + ", ".join(self.install_dirs)
            raise StataEnvironmentError(
                "No graphical Stata executable was found in {}. Tried: {}".format(
                    locations, expected
                )
            )
        try:
            process = self.launcher([executable])
        except OSError as error:
            raise StataEnvironmentError(
                "Could not start {}: {}".format(executable, error)
            ) from error
        # Retain the Popen object while the plugin is loaded. Stata remains an
        # independent desktop process, while retaining the handle avoids an
        # unhelpful subprocess warning during normal long-running sessions.
        if process is not None:
            self._launched_processes.append(process)
        return executable

    def discover_or_launch_windows(
        self,
        executables=DEFAULT_LINUX_EXECUTABLES,
        timeout=LINUX_STARTUP_TIMEOUT_SECONDS,
        poll_interval=LINUX_STARTUP_POLL_SECONDS,
        settle_time=LINUX_STARTUP_SETTLE_SECONDS,
    ) -> tuple[list[StataWindow], bool]:
        """Return visible Stata windows, starting one when none exists.

        The lock prevents simultaneous Sublime build jobs from launching more
        than one replacement Stata process.
        """

        with self._launch_lock:
            windows = self.discover_windows(executables)
            if windows:
                return windows, False

            executable = self.launch_stata(executables)
            interval = max(0.01, float(poll_interval))
            timeout_seconds = max(0.0, float(timeout))
            settle_seconds = max(0.0, float(settle_time))
            attempts = max(1, math.ceil(timeout_seconds / interval))
            for _attempt in range(attempts):
                self.sleep(interval)
                windows = self.discover_windows(executables)
                if windows:
                    if settle_seconds:
                        self.sleep(settle_seconds)
                        refreshed = self.discover_windows(executables)
                        if refreshed:
                            windows = refreshed
                    return windows, True

        raise StataWindowError(
            "Started {}, but no visible Stata GUI window appeared within {:g} seconds.".format(
                executable, timeout_seconds
            )
        )

    def _key(self, window_id: int, key: str, background: bool) -> None:
        arguments = ["key"]
        if background:
            arguments += ["--window", str(window_id)]
        arguments.append(key)
        self._run(arguments)

    def _type(self, window_id: int, command: str, background: bool) -> None:
        arguments = ["type", "--delay", "1"]
        if background:
            arguments += ["--window", str(window_id)]
        arguments.append(command)
        self._run(arguments)

    def deliver(self, window: StataWindow, command: str,
                mode="activate_restore", focus_keys=DEFAULT_COMMAND_FOCUS_KEYS,
                restore_window: int | None = None) -> None:
        self.validate_environment()
        if any(character in command for character in ("\x00", "\r", "\n")):
            raise StataError("Only a single-line command can be sent to Stata")
        if mode not in ("activate_restore", "background"):
            raise StataError(
                "linux_delivery_mode must be 'activate_restore' or 'background'"
            )

        # Ctrl+B may still be physically held when Sublime invokes us. Wait for
        # the actual X11 modifier state to clear before changing focus. Do not
        # also pass xdotool's --clearmodifiers: it snapshots and later restores
        # modifiers with synthetic key events, which can leave a modifier stuck
        # if its physical state changes while xdotool is running.
        self._wait_for_modifier_release()
        background = mode == "background"
        original = None
        if not background:
            original = (
                self.active_window_id()
                if restore_window is None else int(restore_window)
            )
            if original <= 0:
                raise StataEnvironmentError("The Sublime restore window is invalid")

        delivery_error = None
        try:
            if not background:
                self._run(["windowactivate", "--sync", str(window.window_id)])
                self.sleep(0.05)
            for key in focus_keys or ():
                self._key(window.window_id, str(key), background)
                self.sleep(0.03)
            self._key(window.window_id, "Escape", background)
            self._type(window.window_id, command, background)
            self._key(window.window_id, "Return", background)
        except Exception as error:
            delivery_error = error
            raise
        finally:
            if not background and original is not None and original != window.window_id:
                try:
                    self._run(["windowactivate", "--sync", str(original)])
                except Exception as restore_error:
                    if delivery_error is None:
                        raise StataEnvironmentError(
                            "The command was sent, but Sublime focus could not be restored. "
                            "Check Stata before retrying so the code is not executed twice: {}"
                            .format(restore_error)
                        ) from restore_error


def format_do_command(path: str) -> str:
    return "do {}".format(quote_stata_string(path))


def normalize_help_topic(topic: str) -> str:
    topic = " ".join(topic.strip().split())
    if not topic:
        raise StataError("Select a Stata command or place the cursor on one first")
    if any(character in topic for character in (";", "\x00", "\r", "\n")):
        raise StataError("The selected help topic is not valid")
    return topic


def toggle_dataset_io_line(line: str) -> tuple[str, bool]:
    """Toggle only ``save path, replace`` and ``use path, clear`` lines."""

    match = re.match(
        r"^(?P<indent>[ \t]*)(?P<command>save|use)\b[ \t]+(?P<body>.*?)(?P<newline>\r?\n)?$",
        line, re.IGNORECASE,
    )
    if not match:
        return line, False
    body = match.group("body").strip()

    quote_state = None
    compound_depth = 0
    commas = []
    comment = None
    index = 0
    while index < len(body):
        pair = body[index:index + 2]
        if quote_state == "compound":
            if pair == '`"':
                compound_depth += 1
                index += 2
                continue
            if pair == '"\'':
                compound_depth -= 1
                index += 2
                if compound_depth == 0:
                    quote_state = None
                continue
            index += 1
            continue
        if quote_state == "simple":
            if body[index] == '"':
                quote_state = None
            index += 1
            continue
        if pair == '`"':
            quote_state = "compound"
            compound_depth = 1
            index += 2
            continue
        if body[index] == '"':
            quote_state = "simple"
        elif body[index] == ",":
            commas.append(index)
        elif body[index:index + 3] == "///":
            return line, False
        elif pair == "//":
            comment = index
            break
        elif pair == "/*":
            return line, False
        index += 1

    if quote_state is not None:
        return line, False

    main = body if comment is None else body[:comment].rstrip()
    trailing = "" if comment is None else " " + body[comment:].lstrip()
    terminator = ";" if main.endswith(";") else ""
    if terminator:
        main = main[:-1].rstrip()
    main_commas = [position for position in commas if position < len(main)]
    if len(main_commas) != 1:
        return line, False
    comma = main_commas[0]
    path = main[:comma].strip()
    options = main[comma + 1:].strip()

    command = match.group("command").lower()
    expected_option = "replace" if command == "save" else "clear"
    if options.lower() != expected_option:
        return line, False
    compound_quoted = path.startswith('`"') and path.endswith('"\'')
    simply_quoted = path.startswith('"') and path.endswith('"')
    if compound_quoted:
        depth = 0
        index = 0
        while index < len(path):
            pair = path[index:index + 2]
            if pair == '`"':
                depth += 1
                index += 2
                continue
            if pair == '"\'':
                depth -= 1
                index += 2
                if depth == 0 and index != len(path):
                    return line, False
                if depth < 0:
                    return line, False
                continue
            index += 1
        if depth:
            return line, False
    elif simply_quoted:
        if '"' in path[1:-1]:
            return line, False
    elif not path or re.search(r'[\s,;"*]', path):
        return line, False

    new_command, new_option = (
        ("use", "clear") if command == "save" else ("save", "replace")
    )
    result = "{}{} {}, {}{}{}{}".format(
        match.group("indent"), new_command, path, new_option,
        terminator, trailing, match.group("newline") or "",
    )
    return result, True


def toggle_dataset_io_text(contents: str) -> tuple[str, int]:
    transformed = []
    count = 0
    lines = contents.splitlines(keepends=True)
    if not lines and contents:
        lines = [contents]
    for line in lines:
        replacement, changed = toggle_dataset_io_line(line)
        transformed.append(replacement)
        count += int(changed)
    return "".join(transformed), count


class WindowsAutomationBackend:
    """Lazy adapter for Stata's Windows-only Automation API."""

    def __init__(self, stata_path=""):
        self._application = None
        self.stata_path = str(stata_path or "").strip()

    def _validated_stata_path(self) -> str:
        if not self.stata_path:
            return ""
        path = os.path.abspath(
            os.path.expandvars(os.path.expanduser(self.stata_path))
        )
        if not os.path.isfile(path):
            raise StataEnvironmentError(
                "The configured Windows stata_path is not a file: {}".format(path)
            )
        return path

    def _ensure_application(self):
        if self._application is not None:
            return self._application
        configured_path = self._validated_stata_path()
        try:
            import pythoncom
            import win32com.client
        except ImportError as error:
            raise StataEnvironmentError(
                "Stata Automation on Windows requires the pywin32 package"
            ) from error
        try:
            clsid = pythoncom.CoCreateInstanceEx(
                "stata.StataOLEApp", None, pythoncom.CLSCTX_SERVER,
                None, (pythoncom.IID_IDispatch,),
            )[0]
        except Exception as error:
            hint = ""
            if configured_path:
                hint = (
                    ' Register the configured executable with "{}" /Register '
                    "from an elevated Windows prompt."
                ).format(configured_path)
            raise StataEnvironmentError(
                "Could not create the registered Stata Automation object.{}".format(hint)
            ) from error
        self._application = win32com.client.gencache.EnsureDispatch(clsid)
        return self._application

    def deliver(self, command: str) -> None:
        rc = self._ensure_application().DoCommandAsync(command)
        if rc != 0:
            raise StataError(
                "Stata Automation rejected the command (return code {})".format(rc)
            )


class Stata:
    """Compatibility facade for callers that previously used stata.Stata."""

    def __init__(self, platform_name: str | None = None):
        if platform_name is None:
            if os.name == "nt":
                platform_name = "windows"
            elif sys.platform == "darwin":
                platform_name = "osx"
            else:
                platform_name = "linux"
        self.platform_name = platform_name
        self.temp_files = TempDoFileManager()
        if self.platform_name == "windows":
            self.backend = WindowsAutomationBackend()
        elif self.platform_name == "linux":
            self.backend = XdotoolBackend()
        else:
            self.backend = None

    def _require_backend(self):
        if self.backend is None:
            raise StataEnvironmentError(
                "Sending code to an existing Stata GUI is not supported on macOS"
            )

    def run_script(self, commands, **kwargs):
        self._require_backend()
        if not isinstance(commands, str):
            commands = "\n".join(commands)
        path = self.temp_files.create(commands)
        command = format_do_command(path)
        if self.platform_name == "windows":
            self.backend.deliver(command)
            return path
        windows, _launched = self.backend.discover_or_launch_windows(
            kwargs.get("executables", DEFAULT_LINUX_EXECUTABLES)
        )
        window = kwargs.get("window") or choose_recent_window(windows)
        self.backend.deliver(
            window, command, kwargs.get("mode", "activate_restore"),
            kwargs.get("focus_keys", DEFAULT_COMMAND_FOCUS_KEYS),
        )
        return path

    def run(self, command: str, **kwargs):
        self._require_backend()
        if self.platform_name == "windows":
            return self.backend.deliver(command)
        windows, _launched = self.backend.discover_or_launch_windows(
            kwargs.get("executables", DEFAULT_LINUX_EXECUTABLES)
        )
        window = kwargs.get("window") or choose_recent_window(windows)
        return self.backend.deliver(
            window, command, kwargs.get("mode", "activate_restore"),
            kwargs.get("focus_keys", DEFAULT_COMMAND_FOCUS_KEYS),
        )
