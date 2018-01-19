# TODO: write a Stata class

# S = Stata
# S.is_active()
# S.open()
# S.run(cmd)
# S.run_many(cmds)
# S.find_path()
# ...

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

try:
    import Pywin32.setup, win32com.client, win32con, win32api
except:
    sublime.message_dialog("StataEditor not loaded - Need Pywin32 package")
    raise Exception


# ---------------------------
# Constants
# ---------------------------

settings_file = "Stata.sublime-settings"
stata_debug = False


# ---------------------------
# Classes
# ---------------------------

class StataExecCommand(sublime_plugin.WindowCommand):

    def run(self, action='', mode='', **kwargs):
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

        if contents[-1] != "\n":
            contents = contents + "\n"

        prepare = []

        # Change current folder
        cwd = get_cwd(view)
        if cwd: prepare.append("cd " + cwd)
        
        # Run requested command
        stata_automate(contents, prepare)

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
        msg ="Stata: Enter the path of the Stata executable"
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


def stata_is_active():
    try:
        sublime.stata.UtilIsStataFree()
        return True
    except:
        return False


def stata_automate(stata_commands, prepare_commands=None):
    """ Launch Stata (if needed) and send commands """
    if prepare_commands is None:
        prepare_commands = []

    if not stata_is_active():
        launch_stata()
        for cmd in prepare_commands:
            rc = sublime.stata.DoCommand(cmd)
            if rc:
                #sublime.message_dialog(str(rc))
                return
            #sublime.message_dialog("OK")

    # Create temporary do-file and run it
    fn = os.path.join(tempfile.gettempdir(), 'sublime-stata.tmp')
    with open(fn,'w') as fh:
        fh.write(stata_commands)
        fh.close()
        cmd = "do " + fn
        rc = sublime.stata.DoCommandAsync(cmd)
        #if rc: return
        #if stata_debug: print('[CMD]', stata_command)


def launch_stata():
    stata_fn = settings.get("stata_path")

    if not check_correct_executable(stata_fn):
        print('Stata path not found in settings')
        sublime.run_command('stata_update_executable_path')
        return

    #   stata_fn = settings.get("stata_path")
    #   if not check_correct_executable(stata_fn):
    #       sublime.error_message("Cannot run Stata; the path does not exist: {}".format(stata_fn))

    try:
        win32api.WinExec(stata_fn, win32con.SW_SHOWMINNOACTIVE)
        sublime.stata = win32com.client.Dispatch("stata.StataOLEApp")
    except:
        sublime.run_command('stata_register_automation')
        sublime.error_message("Stata: Stata Automation type library appears to be unregistered, see http://www.stata.com/automation/#install")

    # Stata takes a while to start and will silently discard commands sent until it finishes starting
    # Workaround: call a trivial command and see if it was executed (-local- in this case)
    seed = int(random.random()*1e6) # Any number
    for i in range(50):
        sublime.stata.DoCommand('local {} ok'.format(seed))
        sublime.stata.DoCommand('macro list')
        rc = sublime.stata.MacroValue('_{}'.format(seed))
        if rc=='ok':
            sublime.stata.DoCommand('local {}'.format(seed)) # Empty it
            sublime.stata.DoCommand('cap cls')
            print("Stata process started (waited {}ms)".format((1+i)/10))
            sublime.status_message("Stata opened!")
            break
        else:
            time.sleep(0.1)
    else:
        raise IOError('Stata process did not start before timeout')


def get_exe_path():
    
    reg = winreg.ConnectRegistry(None,winreg.HKEY_CLASSES_ROOT)
    subkeys = [r"Applications\StataMP64.exe\shell\open\command",
    r"Applications\StataMP-64.exe\shell\open\command"]

    key_found = False
    for subkey in subkeys:
        try:
            key = winreg.OpenKey(reg, subkey)
            fn = winreg.QueryValue(key, None).strip('"').split('"')[0]
            key_found = True
        except:
            print("Stata: key not found, searching more;", subkey)
            pass
        if key_found:
            break
    else:
        print("Stata: Couldn't find Stata path")
        settings_fn = 'Stata.sublime-settings'
        settings = sublime.load_settings(settings_fn)
        fn = settings.get('stata_path', settings.get('stata_path_old', ''))
    return fn


def check_correct_executable(fn):
    return os.path.isfile(fn) and 'stata' in fn.lower()
