"""Sublime Text commands for executing Stata code."""

import sublime
import sublime_plugin

from . import stata


SETTINGS_FILE = "Stata.sublime-settings"
_settings = None
_linux_backend = None
_windows_backend = None
_temp_files = None
_pinned_targets = {}


def plugin_loaded():
    global _settings, _temp_files
    _settings = sublime.load_settings(SETTINGS_FILE)
    _temp_files = stata.TempDoFileManager()
    sublime.set_timeout_async(_temp_files.cleanup_stale)


def plugin_unloaded():
    _pinned_targets.clear()


def _get_settings():
    global _settings
    if _settings is None:
        _settings = sublime.load_settings(SETTINGS_FILE)
    return _settings


def _get_temp_files():
    global _temp_files
    if _temp_files is None:
        _temp_files = stata.TempDoFileManager()
    return _temp_files


def _get_linux_backend():
    global _linux_backend
    if _linux_backend is None:
        _linux_backend = stata.XdotoolBackend()
    return _linux_backend


def _get_windows_backend():
    global _windows_backend
    if _windows_backend is None:
        stata_path = _get_settings().get("stata_path", "")
        _windows_backend = stata.WindowsAutomationBackend(stata_path)
    return _windows_backend


def _status(message):
    sublime.set_timeout(lambda: sublime.status_message(message))


def _error(error):
    message = str(error)
    print("[Stata] {}".format(message))
    sublime.set_timeout(lambda: sublime.error_message("Stata: " + message))


def _linux_options():
    settings = _get_settings()
    mode = settings.get("linux_delivery_mode", "activate_restore")
    focus_keys = settings.get(
        "linux_command_focus_keys", list(stata.DEFAULT_COMMAND_FOCUS_KEYS)
    )
    executables = settings.get(
        "linux_stata_executables", list(stata.DEFAULT_LINUX_EXECUTABLES)
    )
    if not isinstance(focus_keys, (list, tuple)):
        focus_keys = list(stata.DEFAULT_COMMAND_FOCUS_KEYS)
    if not isinstance(executables, (list, tuple)) or not executables:
        executables = list(stata.DEFAULT_LINUX_EXECUTABLES)
    return mode, tuple(focus_keys), tuple(executables)


def _discover_or_launch_linux_windows():
    _mode, _focus_keys, executables = _linux_options()
    return _get_linux_backend().discover_or_launch_windows(executables)


def _target_for_window(sublime_window, candidates):
    pinned = _pinned_targets.get(sublime_window.id())
    return stata.choose_target_window(candidates, pinned)


def _deliver(sublime_window, command):
    if sublime.platform() == "linux":
        mode, focus_keys, executables = _linux_options()
        backend = _get_linux_backend()
        restore_window = (
            backend.capture_sublime_window()
            if mode == "activate_restore" else None
        )
        candidates, launched = backend.discover_or_launch_windows(executables)
        if launched:
            # With no compatible session left, a pin can only refer to the
            # closed process that triggered this replacement launch.
            _pinned_targets.pop(sublime_window.id(), None)
        target = _target_for_window(sublime_window, candidates)
        backend.deliver(
            target, command, mode, focus_keys, restore_window=restore_window
        )
        return target, launched
    if sublime.platform() == "windows":
        _get_windows_backend().deliver(command)
        return None, False
    raise stata.StataEnvironmentError(
        "Sending code to Stata is currently supported on Linux/X11 and Windows"
    )


def _run_script(sublime_window, contents):
    try:
        manager = _get_temp_files()
        manager.cleanup_stale()
        path = manager.create(contents)
        target, launched = _deliver(sublime_window, stata.format_do_command(path))
        if target is None:
            _status("Sent do-file to Stata")
        elif launched:
            _status(
                "Started Stata and sent do-file to {}".format(
                    target.title or "Stata"
                )
            )
        else:
            _status("Sent do-file to {}".format(target.title or "Stata"))
    except Exception as error:
        _error(error)


def _run_command(sublime_window, command, success_message):
    try:
        _deliver(sublime_window, command)
        _status(success_message)
    except Exception as error:
        _error(error)


class StataExecCommand(sublime_plugin.WindowCommand):
    """Run selected complete lines, the buffer, or a build.txt target."""

    def run(self, action="do", mode="", **kwargs):
        del action, kwargs
        view = self.window.active_view()
        if view is None:
            _error(stata.StataError("There is no active file to run"))
            return
        try:
            if mode == "build":
                spec = stata.read_build_spec(view.file_name())
                contents = spec.contents
                cwd = spec.cwd
                delimiter = "cr"
            elif mode in ("", None):
                buffer_text = view.substr(sublime.Region(0, view.size()))
                selections = [(region.begin(), region.end()) for region in view.sel()]
                contents = stata.selected_or_buffer(buffer_text, selections)
                syntax = view.syntax()
                if syntax is not None and syntax.scope == "source.mata":
                    contents = stata.wrap_standalone_mata(contents)
                filename = view.file_name()
                cwd = stata.working_directory(filename, self.window.folders())
                nonempty = [
                    min(begin, end) for begin, end in selections if begin != end
                ]
                delimiter = (
                    stata.active_delimiter(buffer_text, min(nonempty))
                    if nonempty else "cr"
                )
            else:
                raise stata.StataError("Unknown Stata build mode: {}".format(mode))
            if not contents.strip():
                raise stata.StataError("There is no Stata code to run")
            contents = stata.wrap_script(contents, cwd, delimiter)
        except Exception as error:
            _error(error)
            return
        sublime.set_timeout_async(lambda: _run_script(self.window, contents))


class StataChooseTargetWindowCommand(sublime_plugin.WindowCommand):
    """Pin one running Stata instance as this Sublime window's target."""

    def run(self):
        if sublime.platform() != "linux":
            _error(stata.StataEnvironmentError(
                "Choosing among Stata windows is available on Linux/X11"
            ))
            return

        def discover():
            try:
                candidates, launched = _discover_or_launch_linux_windows()
                candidates = list(reversed(candidates))
                if launched:
                    _pinned_targets.pop(self.window.id(), None)
                stata.choose_recent_window(candidates)
            except Exception as error:
                _error(error)
                return

            labels = []
            for index, candidate in enumerate(candidates):
                prefix = "Most recent — " if index == 0 else ""
                labels.append(prefix + candidate.label)

            def show_picker():
                def selected(index):
                    if index < 0:
                        return
                    target = candidates[index]
                    _pinned_targets[self.window.id()] = target
                    sublime.status_message("Stata target pinned: {}".format(target.title))

                self.window.show_quick_panel(labels, selected)

            sublime.set_timeout(show_picker)

        sublime.set_timeout_async(discover)


class StataUseRecentWindowCommand(sublime_plugin.WindowCommand):
    """Clear a pin and resume targeting the topmost/recent Stata window."""

    def run(self):
        _pinned_targets.pop(self.window.id(), None)
        sublime.status_message("Stata target: most recent window")


class StataTargetLifecycleListener(sublime_plugin.EventListener):
    """Discard a target pin when its owning Sublime window closes."""

    def on_pre_close_window(self, window):
        _pinned_targets.pop(window.id(), None)


class StataHelpCommand(sublime_plugin.TextCommand):
    """Open Stata's internal help for the selection or word at the caret."""

    def run(self, edit):
        del edit
        selections = list(self.view.sel())
        region = selections[0] if selections else sublime.Region(0, 0)
        if region.empty():
            region = self.view.word(region)
        try:
            topic = stata.normalize_help_topic(self.view.substr(region))
        except Exception as error:
            _error(error)
            return
        window = self.view.window()
        if window is None:
            _error(stata.StataError("The current view does not belong to a window"))
            return
        sublime.set_timeout_async(
            lambda: _run_command(
                window, "help " + topic, "Sent Stata help request for " + topic
            )
        )


class StataToggleDatasetIoCommand(sublime_plugin.TextCommand):
    """Toggle simple save/use statements on the selected or current lines."""

    def run(self, edit):
        regions = []
        for selection in self.view.sel():
            region = self.view.full_line(selection)
            begin, end = region.begin(), region.end()
            if regions and begin <= regions[-1].end():
                regions[-1] = sublime.Region(regions[-1].begin(), max(end, regions[-1].end()))
            else:
                regions.append(sublime.Region(begin, end))

        changed = 0
        for region in reversed(regions):
            original = self.view.substr(region)
            replacement, count = stata.toggle_dataset_io_text(original)
            if count:
                self.view.replace(edit, region, replacement)
                changed += count
        if changed:
            sublime.status_message("Toggled {} Stata dataset command{}".format(
                changed, "" if changed == 1 else "s"
            ))
        else:
            sublime.status_message("No simple save/use command found on the selected lines")
