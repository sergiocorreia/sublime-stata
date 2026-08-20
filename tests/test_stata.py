from __future__ import annotations

from pathlib import Path
import os
import stat as stat_module
import tempfile
import unittest

import stata


class Result:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class SelectionAndWrapperTests(unittest.TestCase):
    def test_selection_ending_at_next_line_start_does_not_include_next_line(self):
        source = "one\ntwo\nthree\n"
        self.assertEqual(stata.selected_or_buffer(source, [(0, 4)]), "one\n")
        self.assertEqual(stata.selected_or_buffer(source, [(5, 6)]), "two\n")

    def test_selection_clamps_and_merges_expanded_regions(self):
        source = "one\ntwo\nthree\n"
        self.assertEqual(stata.selected_or_buffer(source, [(-20, 2), (1, 7)]), "one\ntwo\n")
        self.assertEqual(stata.selected_or_buffer(source, []), source)

    def test_active_delimiter_at_selection_start(self):
        source = "#delimit ;\ndisplay 1;\n#delimit cr\ndisplay 2\n"
        semicolon_line = source.index("display 1")
        cr_line = source.index("display 2")
        self.assertEqual(stata.active_delimiter(source, semicolon_line), ";")
        self.assertEqual(stata.active_delimiter(source, cr_line), "cr")
        crlf_source = "#delimit ;\r\ndisplay 1;\r\n"
        self.assertEqual(stata.active_delimiter(crlf_source), ";")

    def test_delimiter_scan_ignores_commented_directives(self):
        source = (
            "* #delimit ;\n"
            "// #delimit ;\n"
            "/*\n#delimit ;\n*/\n"
            "/* #delimit ;"
            "display 1\n"
        )
        self.assertEqual(stata.active_delimiter(source), "cr")

    def test_delimiter_scan_handles_nested_block_comments_and_string_markers(self):
        source = (
            "#delimit ;\n"
            "display \"/* not a comment\";\n"
            "/* outer /* inner */\n"
            "#delimit cr\n"
            "*/\n"
            "display 1;\n"
        )
        self.assertEqual(stata.active_delimiter(source), ";")

    def test_wraps_semicolon_selection_after_cr_delimited_cd(self):
        wrapped = stata.wrap_script("display 1;\n", "/tmp/my project", ";")
        self.assertEqual(
            wrapped,
            'cd `"/tmp/my project"\'\n#delimit ;\ndisplay 1;\n',
        )

    def test_raw_standalone_mata_gets_an_execution_wrapper(self):
        raw = "real scalar square(real scalar x) {\n\treturn(x^2)\n}\n"
        self.assertEqual(
            stata.wrap_standalone_mata(raw),
            "mata:\n" + raw + "end\n",
        )
        wrapped = "version 19\nmata:\nreal scalar x\nend\n"
        self.assertEqual(stata.wrap_standalone_mata(wrapped), wrapped)

    def test_compound_path_quoting(self):
        cases = {
            "/tmp/a b": '`"/tmp/a b"\'',
            "/tmp/café": '`"/tmp/café"\'',
            "/tmp/$data": '`"/tmp/\\$data"\'',
            "/tmp/`local": '`"/tmp/\\`local"\'',
            r"/tmp/a\b": '`"/tmp/a\\b"\'',
            '/tmp/a "q"': '`"/tmp/a "q""\'',
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(stata.quote_stata_string(path), expected)
        with self.assertRaises(stata.StataError):
            stata.quote_stata_string('/tmp/bad"\'path')

    def test_working_directory_for_saved_and_unsaved_buffers(self):
        self.assertEqual(stata.working_directory("/work/code/main.do", []), "/work/code")
        self.assertEqual(stata.working_directory(None, ["/project"]), "/project")
        self.assertIsNone(stata.working_directory(None, ["/one", "/two"]))


class BuildAndTemporaryFileTests(unittest.TestCase):
    def test_resolves_relative_quoted_build_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "command.ado"
            source.write_text("program command\nend\n", encoding="utf-8")
            target = root / "test command.do"
            target.write_text('display "ok"', encoding="utf-8")
            (root / "build.txt").write_text('"test command.do"\n', encoding="utf-8")
            spec = stata.read_build_spec(str(source))
            self.assertEqual(spec.contents, 'display "ok"\n')
            self.assertEqual(spec.cwd, str(root))
            self.assertEqual(spec.source_path, str(target.resolve()))

    def test_build_errors_do_not_fall_back_to_active_buffer(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "command.ado"
            source.write_text("program command\nend\n", encoding="utf-8")
            with self.assertRaises(stata.BuildFileError):
                stata.read_build_spec(str(source))
            (source.parent / "build.txt").write_text("one.do\ntwo.do\n", encoding="utf-8")
            with self.assertRaises(stata.BuildFileError):
                stata.read_build_spec(str(source))

    def test_temp_files_are_unique_private_and_cleaned_only_when_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = stata.TempDoFileManager(directory, max_age=60)
            first = Path(manager.create("display 1"))
            second = Path(manager.create("display 2\n"))
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(encoding="utf-8"), "display 1\n")
            self.assertEqual(stat_module.S_IMODE(first.stat().st_mode), 0o600)
            unrelated = Path(directory) / "other.do"
            unrelated.write_text("keep", encoding="utf-8")
            similarly_named = Path(directory) / "sublime-stata-important.do"
            similarly_named.write_text("keep", encoding="utf-8")
            os.utime(first, (1, 1))
            os.utime(similarly_named, (1, 1))
            removed = manager.cleanup_stale(now=1000)
            self.assertEqual(removed, [str(first)])
            self.assertTrue(second.exists())
            self.assertTrue(unrelated.exists())
            self.assertTrue(similarly_named.exists())


class WindowsAutomationTests(unittest.TestCase):
    def test_configured_path_is_validated_before_importing_windows_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / "StataMP-64.exe")
            backend = stata.WindowsAutomationBackend(missing)
            with self.assertRaisesRegex(
                stata.StataEnvironmentError, "configured Windows stata_path"
            ):
                backend._ensure_application()


class ToggleTests(unittest.TestCase):
    def assertToggle(self, original, expected):
        self.assertEqual(stata.toggle_dataset_io_line(original), (expected, True))

    def test_toggles_only_exact_safe_pairs(self):
        self.assertToggle("save data.dta, replace\n", "use data.dta, clear\n")
        self.assertToggle("save data/panel.dta, replace\n", "use data/panel.dta, clear\n")
        self.assertToggle(
            '  use "data files/a,b.dta", clear; // reload\n',
            '  save "data files/a,b.dta", replace; // reload\n',
        )
        self.assertToggle(
            '\tsave "$data/analysis.dta", replace // canonical output\n',
            '\tuse "$data/analysis.dta", clear // canonical output\n',
        )
        self.assertToggle(
            'use `"`folder\'/source data.dta"\', clear\n',
            'save `"`folder\'/source data.dta"\', replace\n',
        )
        rejected = (
            "save data.dta\n",
            "save data.dta, clear\n",
            "use data.dta\n",
            "use price using data.dta, clear\n",
            "use data.dta if group == 1, clear\n",
            "save data.dta, replace emptyok\n",
            "use data.dta, clear replace\n",
            "save data.dta, replace /// continuation\n",
            'use "one.dta" "two.dta", clear\n',
            'save"data.dta", replace\n',
            "save data.dta, replace /* block comment */\n",
        )
        for line in rejected:
            with self.subTest(line=line):
                self.assertEqual(stata.toggle_dataset_io_line(line), (line, False))


class XdotoolTests(unittest.TestCase):
    def backend(
        self,
        runner,
        process_executable=lambda pid: "/opt/stata/xstata-mp",
        sleeper=None,
        modifiers_pressed=None,
    ):
        return stata.XdotoolBackend(
            env={"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"},
            runner=runner,
            which=lambda binary: "/usr/bin/{}".format(binary),
            process_executable=process_executable,
            sleeper=sleeper or (lambda seconds: None),
            modifiers_pressed=modifiers_pressed or (lambda: False),
        )

    def test_discovery_enumerates_windows_and_accepts_custom_maintitle(self):
        calls = []
        names = {10: "Running: analysis.do", 11: "Graph", 20: "StataNow/BE 19.5", 30: "Sublime Text"}
        pids = {10: 100, 11: 100, 20: 200, 30: 300}
        geometry = {10: (1200, 800), 11: (500, 400), 20: (1100, 700), 30: (1000, 700)}

        def runner(argv):
            calls.append(argv)
            if argv[0] == "/usr/bin/xprop":
                window_id = int(argv[2])
                window_class = "Stata" if window_id != 30 else "Sublime_text"
                return Result(
                    'WM_CLASS(STRING) = "{}", "{}"\n'.format(
                        window_class.lower(), window_class
                    )
                )
            command = argv[1]
            if command == "search":
                return Result("10\n11\n20\n30\n")
            window_id = int(argv[-1])
            if command == "getwindowpid":
                return Result(str(pids[window_id]))
            if command == "getwindowname":
                return Result(names[window_id])
            if command == "getwindowgeometry":
                width, height = geometry[window_id]
                return Result("WIDTH={}\nHEIGHT={}\n".format(width, height))
            raise AssertionError(argv)

        executables = {100: "/opt/stata/xstata-mp", 200: "/opt/stata/xstata", 300: "/usr/bin/sublime_text"}
        backend = self.backend(runner, process_executable=executables.get)
        windows = backend.discover_windows()
        self.assertEqual([window.window_id for window in windows], [10, 20])
        self.assertEqual(stata.choose_recent_window(windows).window_id, 20)
        self.assertIn(
            ["xdotool", "search", "--onlyvisible", "--maxdepth", "2", "--class", ".*"],
            calls,
        )

    def test_discovery_never_falls_back_to_hidden_windows(self):
        calls = []

        def runner(argv):
            calls.append(argv)
            return Result(returncode=1)

        windows = self.backend(runner).discover_windows()
        self.assertEqual(windows, [])
        search_calls = [call for call in calls if call[1] == "search"]
        self.assertEqual(len(search_calls), 1)
        self.assertIn("--onlyvisible", search_calls[0])

    def test_absolute_executable_settings_require_exact_realpath(self):
        allowed = stata.XdotoolBackend._allowed_executable
        self.assertTrue(allowed("/opt/stata/xstata-mp", ["xstata-mp"]))
        self.assertTrue(allowed("/opt/stata/xstata-mp", ["/opt/stata/xstata-mp"]))
        self.assertFalse(allowed("/other/stata/xstata-mp", ["/opt/stata/xstata-mp"]))

    def test_pinned_window_never_silently_falls_back(self):
        windows = [stata.StataWindow(10, "Stata/MP 19.0", 100, "/opt/stata/xstata-mp")]
        self.assertEqual(stata.choose_target_window(windows, 10).window_id, 10)
        with self.assertRaises(stata.StataWindowError):
            stata.choose_target_window(windows, 99)
        pinned = windows[0]
        reused_id = stata.StataWindow(
            10, "Stata/MP 19.0", 200, "/opt/stata/xstata-mp"
        )
        with self.assertRaises(stata.StataWindowError):
            stata.choose_target_window([reused_id], pinned)

    def test_background_sequence_targets_command_pane_without_activation(self):
        calls = []
        sleeps = []

        def runner(argv):
            calls.append(argv)
            return Result()

        backend = self.backend(runner, sleeper=sleeps.append)
        command = 'do `"/tmp/a;$(touch nope) $HOME.do"\''
        backend.deliver(
            stata.StataWindow(77, "StataNow/MP 19.5"),
            command,
            "background",
            ["ctrl+1"],
        )
        self.assertNotIn("windowactivate", [call[1] for call in calls])
        self.assertEqual(calls[0], ["xdotool", "key", "--clearmodifiers", "--window", "77", "ctrl+1"])
        self.assertEqual(calls[1][-1], "Escape")
        self.assertEqual(calls[2][1], "type")
        self.assertEqual(calls[2][-1], command)
        self.assertEqual(calls[3][-1], "Return")
        self.assertEqual(sleeps, [0.03])

    def test_activate_restore_sequence_ends_on_original_window(self):
        calls = []
        sleeps = []

        def runner(argv):
            calls.append(argv)
            if argv[1] == "getactivewindow":
                return Result("99\n")
            return Result()

        backend = self.backend(runner, sleeper=sleeps.append)
        backend.deliver(stata.StataWindow(77, "Stata/SE 19.0"), "help regress")
        activations = [call for call in calls if call[1] == "windowactivate"]
        self.assertEqual(activations[0][-1], "77")
        self.assertEqual(activations[-1][-1], "99")
        self.assertEqual(sleeps, [0.05, 0.03])

    def test_precaptured_sublime_window_survives_focus_change_before_delivery(self):
        calls = []
        active_window = [99]

        def runner(argv):
            calls.append(argv)
            if argv[1] == "getactivewindow":
                return Result("{}\n".format(active_window[0]))
            if argv[1] == "getwindowpid":
                return Result("500\n")
            if argv[0] == "/usr/bin/xprop":
                return Result('WM_CLASS(STRING) = "sublime_text", "Sublime_text"\n')
            return Result()

        backend = self.backend(
            runner, process_executable=lambda pid: "/opt/sublime_text/sublime_text"
        )
        restore_window = backend.capture_sublime_window()
        active_window[0] = 55  # Another app takes focus while discovery runs.
        backend.deliver(
            stata.StataWindow(77, "Stata/SE 19.0"),
            "help regress",
            restore_window=restore_window,
        )
        active_queries = [call for call in calls if call[1] == "getactivewindow"]
        activations = [call for call in calls if call[1] == "windowactivate"]
        self.assertEqual(len(active_queries), 1)
        self.assertEqual(activations[-1][-1], "99")

    def test_restore_capture_rejects_a_non_sublime_origin(self):
        def runner(argv):
            if argv[1] == "getactivewindow":
                return Result("99\n")
            if argv[1] == "getwindowpid":
                return Result("500\n")
            if argv[0] == "/usr/bin/xprop":
                return Result('WM_CLASS(STRING) = "xterm", "XTerm"\n')
            return Result()

        with self.assertRaisesRegex(stata.StataEnvironmentError, "did not originate"):
            self.backend(
                runner, process_executable=lambda pid: "/usr/bin/xterm"
            ).capture_sublime_window()

    def test_wm_class_uses_standard_xprop_output(self):
        calls = []

        def runner(argv):
            calls.append(argv)
            return Result('WM_CLASS(STRING) = "xstata-mp", "Stata"\n')

        backend = self.backend(runner)
        self.assertEqual(backend._window_class(77), "xstata-mp Stata")
        self.assertEqual(
            calls, [["/usr/bin/xprop", "-id", "77", "WM_CLASS"]]
        )

    def test_window_class_is_optional_when_xprop_is_unavailable(self):
        def runner(argv):
            command = argv[1]
            if command == "search":
                return Result("77\n")
            if command == "getwindowpid":
                return Result("700\n")
            if command == "getwindowname":
                return Result("Research session\n")
            if command == "getwindowgeometry":
                return Result("WIDTH=1200\nHEIGHT=800\n")
            raise AssertionError(argv)

        backend = stata.XdotoolBackend(
            env={"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"},
            runner=runner,
            which=lambda binary: "/usr/bin/xdotool" if binary == "xdotool" else None,
            process_executable=lambda pid: "/opt/stata/xstata-mp",
            sleeper=lambda seconds: None,
            modifiers_pressed=lambda: False,
        )
        windows = backend.discover_windows()
        self.assertEqual([window.window_id for window in windows], [77])
        self.assertEqual(windows[0].window_class, "")

    def test_delivery_waits_for_actual_modifier_release(self):
        states = iter((True, True, False))
        sleeps = []

        def runner(argv):
            if argv[1] == "getactivewindow":
                return Result("99\n")
            return Result()

        backend = self.backend(
            runner,
            sleeper=sleeps.append,
            modifiers_pressed=lambda: next(states),
        )
        backend.deliver(stata.StataWindow(77, "Stata/SE 19.0"), "help regress")
        self.assertEqual(sleeps[:2], [0.01, 0.01])
        self.assertEqual(sleeps[2:], [0.05, 0.03])

    def test_activate_restore_restores_sublime_after_delivery_error(self):
        calls = []

        def runner(argv):
            calls.append(argv)
            if argv[1] == "getactivewindow":
                return Result("99\n")
            if argv[1] == "type":
                return Result(stderr="synthetic failure", returncode=2)
            return Result()

        backend = self.backend(runner)
        with self.assertRaisesRegex(stata.StataEnvironmentError, "synthetic failure"):
            backend.deliver(stata.StataWindow(77, "Stata/SE 19.0"), "help regress")
        activations = [call for call in calls if call[1] == "windowactivate"]
        self.assertEqual(activations[-1][-1], "99")

    def test_activate_restore_restores_after_partial_activation_failure(self):
        calls = []

        def runner(argv):
            calls.append(argv)
            if argv[1] == "getactivewindow":
                return Result("99\n")
            if argv[1] == "windowactivate" and argv[-1] == "77":
                return Result(stderr="activation failed after focus change", returncode=2)
            return Result()

        backend = self.backend(runner)
        with self.assertRaisesRegex(stata.StataEnvironmentError, "activation failed"):
            backend.deliver(stata.StataWindow(77, "Stata/SE 19.0"), "help regress")
        activations = [call for call in calls if call[1] == "windowactivate"]
        self.assertEqual([call[-1] for call in activations], ["77", "99"])

    def test_restore_failure_warns_that_the_command_was_already_sent(self):
        def runner(argv):
            if argv[1] == "getactivewindow":
                return Result("99\n")
            if argv[1] == "windowactivate" and argv[-1] == "99":
                return Result(stderr="restore failed", returncode=2)
            return Result()

        backend = self.backend(runner)
        with self.assertRaisesRegex(stata.StataEnvironmentError, "command was sent"):
            backend.deliver(stata.StataWindow(77, "Stata/SE 19.0"), "help regress")

    def test_environment_errors_are_actionable(self):
        wayland = stata.XdotoolBackend(
            env={"DISPLAY": ":0", "XDG_SESSION_TYPE": "wayland"},
            which=lambda binary: "/usr/bin/xdotool",
        )
        with self.assertRaisesRegex(stata.StataEnvironmentError, "Wayland"):
            wayland.validate_environment()
        no_display = stata.XdotoolBackend(env={}, which=lambda binary: "/usr/bin/xdotool")
        with self.assertRaisesRegex(stata.StataEnvironmentError, "X11"):
            no_display.validate_environment()
        missing = stata.XdotoolBackend(env={"DISPLAY": ":0"}, which=lambda binary: None)
        with self.assertRaisesRegex(stata.StataEnvironmentError, "xdotool"):
            missing.validate_environment()

    def test_macos_facade_fails_instead_of_selecting_linux_backend(self):
        runtime = stata.Stata(platform_name="osx")
        with self.assertRaisesRegex(stata.StataEnvironmentError, "macOS"):
            runtime.run("display 1")

    def test_compatibility_facade_creates_one_temp_file_per_run(self):
        class TempFiles:
            def __init__(self):
                self.calls = 0

            def create(self, contents):
                self.calls += 1
                return "/tmp/only.do"

        class Backend:
            def discover_windows(self, executables):
                return [stata.StataWindow(1, "Stata/MP 19.0")]

            def deliver(self, window, command, mode, focus_keys):
                return None

        runtime = stata.Stata(platform_name="linux")
        runtime.temp_files = TempFiles()
        runtime.backend = Backend()
        runtime.run_script("display 1")
        self.assertEqual(runtime.temp_files.calls, 1)


if __name__ == "__main__":
    unittest.main()
