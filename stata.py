"""
This is the API for Stata Automation through Python.

Install
=======

On top of Python and Stata, it needs two extra components:

1) pywin32 (a python package)
   Source:  https://github.com/mhammond/pywin32/releases (or pip?)
   Note:    The first time you run this you might need to run as admin

2) Stata Automation
   Source: https://www.stata.com/automation/#install


Usage
======

S = Stata()         # Create object; optional argument is fn of stata binary
S.launch_binary()   # Optional
S.run("dir")        # Execute a command (optionally set sync=True)
cmds = ['di "hello"', "sysuse auto"]
S.run_script(cmds)  # -do- list of commands (optionally set sync=True)


Missing features
================

UtilShowStata(#)    - Hide (1), Minimize (2), or Show (0) Stata
rc = DoCommand()    - Run command and wait for it to complete
UtilSetStataBreak() - Break execution
MacroValue("..")    - Return macro value

(... etc)

"""


# ---------------------------
# Imports
# ---------------------------

import os
import time
import winreg
import tempfile

# If this fails we need the Pywin32 package
# Also see: https://github.com/mhammond/pywin32/releases
# - From python you might need to run as admin the first time

#import Pywin32.setup, win32com.client, win32con, win32api
import win32com.client, win32con, win32api


# ---------------------------
# Main Class
# ---------------------------

class Stata(object):

    def __init__(self, stata_fn=None):
        self.stata_fn = self.find_binary(stata_fn)
        self.exe = None
        self.temp_fn = os.path.join(tempfile.gettempdir(), 'sublime-stata.tmp')

    def __del__(self):
        try:
            os.remove(self.temp_fn)
            print('[Stata] temp file removed')
        except:
            pass


    def find_binary(self, stata_fn):
        # 1) If provided a filename, try it first
        if binary_exists(stata_fn):
            return stata_fn
        
        # 2) Search Stata in registry
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CLASSES_ROOT)
        keys = (r"Stata15Do\shell\open\command",
                r"Stata14Do\shell\open\command",
                r"Stata13Do\shell\open\command",
                r"Applications\StataMP-64.exe\shell\open\command",
                r"Applications\StataMP64.exe\shell\open\command")
        for key in keys:
            try:
                print('[Stata] looking for registry key:', key)
                key = winreg.OpenKey(reg, key)
                fn = winreg.QueryValue(key, None).strip('"').split('"')[0]
                if binary_exists(fn):
                    print(" - key found, filename:", fn)
                    return fn
            except:
                print(" - key not found, searching more...", key)
                pass

        # 3) Try filenames listed by hand
        extra = ('C:/Bin/Stata14/StataMP-64.exe',)
        for fn in extra:
            if binary_exists(fn):
                return fn

        raise Exception('Stata binary not found')


    def launch_binary(self):
        win32api.WinExec(self.stata_fn, win32con.SW_SHOWMINNOACTIVE)
        self.exe = win32com.client.Dispatch("stata.StataOLEApp")
        #sublime.run_command('stata_register_automation')
        #sublime.error_message("Stata: Stata Automation type library appears to be unregistered, see http://www.stata.com/automation/#install")


    def is_active(self):
        """True if binary is active"""
        try:
            self.is_free()
            return True
        except:
            return False


    def ensure_is_active(self):
        if not self.is_active():
            self.launch_binary()


    def is_free(self):
        return self.exe.UtilIsStataFree()


    def run(self, cmd, sync=False):
        self.ensure_is_active()
        
        if not sync:
            self.exe.DoCommandAsync(cmd)
        else:
            i = 0
            while not self.is_free():
                time.sleep(1)
                i += 1
                if i > 10:
                    raise Exception('Stata is busy')
            return self.exe.DoCommand(cmd)


    def run_script(self, commands, sync=False):
        """Create temporary do-file and run it"""
        self.ensure_is_active()
        
        # Allow strings and lists/tuples
        if not isinstance(commands, str):
            commands = '\n'.join(c for c in commands)

        # Add tailing comma (else the last command doesn't run)
        if not commands.endswith('\n'):
            commands = commands + '\n'

        with open(self.temp_fn,'w') as fh:
            fh.write(commands)

        cmd = "do " + self.temp_fn
        rc = self.exe.DoCommandAsync(cmd)
        assert(rc==0)


# ---------------------------
# Aux Functions
# ---------------------------

def binary_exists(fn):
    return fn and os.path.isfile(fn) and 'stata' in fn.lower()


# ---------------------------
# Demo
# ---------------------------

if __name__ == '__main__':
    
    S = Stata()
    S.launch_binary()
    S.run("dir")
    time.sleep(2)
    commands = ['di "hello"', "di 1+1", "sysuse auto", "forv i = 1/10 {", "logit foreign weight", "}", "su"]
    S.run_script(commands)
    S.run("reghdfe price weight gear, a(i.turn i.trunk##c.length) tol(1e-20)", sync=True)
    print(S.is_active())
    S.run("tab turn")
    time.sleep(2)
    wait = input("PRESS ENTER TO CLOSE STATA.")
