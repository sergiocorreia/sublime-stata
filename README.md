# sublime-stata

Sublime Text 3 plugin for Stata (13, 14, 15).


## Features:

- Improved syntax highlighting (includes SSC commands, Mata, etc.)
- Snippets, autocomplete backticks, etc.
- Build with `ctrl+b` (or `ctrl+shift+b`) on Windows (selections or the entire file)
- Navigate through a do-file with `ctrl+r` (supports programs and sections; which start with `// XYZ`)


## Install

On top of Python and Stata, it needs two extra components:

1. pywin32 (a python package)
   - Source:  https://packagecontrol.io/packages/Pywin32

2. Stata Automation
   - Source: https://www.stata.com/automation/#install


## Disclaimer:

This package is essentially for my own use.
I will most likely accept any pull request, but not implement new features not directly useful for me
(i.e. I can accept code that implements OSX support, but I won't write it).


## Advanced: building blocks:

This program is modular, so you can use different parts independently.

### Stata API

To use `stata.py` outside of Sublime Text (e.g. from Python), you will need:
	- https://github.com/mhammond/pywin32/releases (select the correct version; maybe works from pip?)

Note that you might need to run as admin the first time you use it after installing.

