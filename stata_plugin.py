# This file is named <stata_exec.py>, so the command is <stata_exec>
# and the key class is <StataExecCommand>, with a <run> method

# See also:
# - http://docs.sublimetext.info/en/latest/reference/build_systems/configuration.html
# - https://www.sublimetext.com/docs/3/api_reference.html
# - https://github.com/STealthy-and-haSTy/SublimeScraps/tree/master/build_enhancements

# Some excerpts based on:
# - https://github.com/TiesdeKok/ipystata/


# ---------------------------
# Imports
# ---------------------------

import os
import random
import winreg
import tempfile

import sublime
import sublime_plugin

from . import stata

#try:
#    import Pywin32.setup, win32com.client, win32con, win32api
#except:
#    sublime.message_dialog("StataEditor not loaded - Need Pywin32 package")
#    raise Exception


# ---------------------------
# Constants
# ---------------------------

settings_file = "Stata.sublime-settings"
stata_debug = False
sublime.stata = None  # Changed later


# ---------------------------
# Classes
# ---------------------------

class StataExecCommand(sublime_plugin.WindowCommand):

    def run(self, action='', mode='', **kwargs):
        
        if sublime.stata is None:
            sublime.stata = stata.Stata()

        view = self.window.active_view()
        current_file = view.file_name() # str or None
        selection_length = sum(len(s) for s in view.sel())

        # Extract contents
        if not selection_length:
            contents = view.substr(sublime.Region(0, view.size()))
        else:
            # Expand lines
            last_char = view.substr(view.sel()[-1])[-1]
            if last_char != '\n':
                view.run_command("expand_selection", {"to": "line"})
                
            contents = ''.join(view.substr(sel) for sel in view.sel())

        if contents and contents[-1] != "\n":
            contents = contents + "\n"

        # Change current folder
        cwd = get_cwd(view)
        if cwd is not None:
            # Better to modify contents instead of polluting the Stata command history
            #sublime.stata.run("cd " + cwd)
            contents = "cd " + cwd + "\n" + contents
        
        # Run requested command
        sublime.stata.run_script(contents)

        # Done!
        pass


class StataRegisterAutomationCommand(sublime_plugin.ApplicationCommand):
    def run(self, **kwargs):
        stata_fn = settings.get("stata_path")
        os.popen('powershell -command start-process "{}" "/Register" -verb RunAs'.format(stata_fn))


class StataUpdateExecutablePathCommand(sublime_plugin.ApplicationCommand):
    def run(self, **kwargs):

        def update_settings(fn):
            settings_fn = 'Stata.sublime-settings'
            settings = sublime.load_settings(settings_fn)

            old_fn = settings.get('stata_path', '')

            if check_correct_executable(fn):
                if old_fn!=fn:
                    settings.set('stata_path_old', old_fn)
                settings.set('stata_path', fn)
                sublime.save_settings(settings_fn)
                sublime.status_message("Stata path updated")
                launch_stata()
            else:
                sublime.error_message("Cannot run Stata; the path does not exist: {}".format(fn))

        def cancel_update():
            sublime.status_message("Stata path not updated")

        def check_correct(fn):
            is_correct = check_correct_executable(fn)
            if is_correct:
                sublime.status_message("Path is valid")
            else:
                sublime.status_message("Path is currently NOT valid")

        fn = get_exe_path()
        msg ="Enter the path of the Stata executable"
        sublime.active_window().show_input_panel(msg, fn, update_settings, check_correct, cancel_update)


# ---------------------------
# Functions
# ---------------------------

def plugin_loaded():
    global settings
    settings = sublime.load_settings(settings_file)


def get_cwd(view):
    fn = view.file_name()
    if not fn: return
    cwd = os.path.split(fn)[0]
    return cwd
