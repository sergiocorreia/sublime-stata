# -------------------------------------------------------------
# Imports and Constants
# -------------------------------------------------------------
import sublime, sublime_plugin
try:
	import Pywin32.setup, win32com.client, win32con, win32api
except:
	sublime.message_dialog("StataEditor not loaded - Need Pywin32 package")
	raise Exception
import os, tempfile, subprocess, re, urllib, json, random, time, calendar, winreg, webbrowser
from collections import defaultdict
# http://msdn.microsoft.com/en-us/library/windows/desktop/ms633548(v=vs.85).aspx

settings_file = "StataEditor.sublime-settings"
stata_debug = False

# -------------------------------------------------------------
# Classes
# -------------------------------------------------------------

class StataBuildCommand(sublime_plugin.WindowCommand):
	def run(self, **kwargs):
		getView().window().run_command("stata_execute", {"build":True, "Mode": kwargs["Mode"]})

class StataUpdateJsonCommand(sublime_plugin.TextCommand):
	"""Update the .json used in Stata dataset/varname autocompletions"""
	def run(self, edit):
		get_autocomplete_data(self.view, force_update=True, add_from_buffer=False, obtain_varnames=True)

class StataAutocompleteDtaCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		datasets = get_autocomplete_data(self.view, add_from_buffer=True, obtain_varnames=False)
		if datasets is None:
			return
		self.suggestions = sorted( list(zip(*datasets))[1] ) # Tuple (fn, dta name)
		self.view.window().show_quick_panel(self.suggestions, self.insert_link) #, sublime.MONOSPACE_FONT)

	def insert_link(self, choice):
		if choice==-1:
			return
		link = '"' + self.suggestions[choice] + '"'
		self.view.run_command("stata_insert", {'link':link})

class StataAutocompleteVarCommand(sublime_plugin.TextCommand):
	def run(self, edit, menu='all', prev_choice=-1, filter_dta=None):

		# Three menus: normal ("all"), select one DTA only ("filter"), pick which dta to select ("dta")
		assert menu in ('all', 'filter', 'dta')

		# Called from keybinding in a line with a -using-
		if menu=='filter' and filter_dta is None:
			line = self.view.substr(self.view.line(self.view.sel()[0]))
			regex = re.search('using "?([^",*]+)', line)
			if regex is not None:
				filter_dta = regex.group(1).strip()
				prev_choice = 0
			else:
				menu = 'all'

		# dtamap: dict of dta->varlist
		# datasets: list of dtas
		# varlist: dict of varlist -> datasets

		dtamap, sortlist = get_autocomplete_data(self.view, add_from_buffer=True, obtain_varnames=True)
		if dtamap is None:
			return
		if menu=='filter' and filter_dta not in dtamap:
			if filter_dta:
				print('[Stata] Note: <{}> not found in'.format(filter_dta), list(dtamap.keys()))
			menu = 'all'

		self.menu = menu
		self.filter_dta = filter_dta
		#f = lambda var: "    [#{}]".format(1+sorts.index(var)) if var in sorts else ''
		f = lambda var: "* " if var in sorts else ''

		if menu=='all':
			varlist = defaultdict(list)
			for dta,variables in dtamap.items():
				for varname in variables:
					varlist[varname].append(dta)
			if not varlist: return
			self.suggestions = [['    ----> Select this to filter by dataset <----    ','']] + list( [v, ' '.join(d) if len(d) < 5 else d[0] + ' and {} other files'.format(len(d)-1)] for v,d in varlist.items() )
		elif menu=='filter':
			sorts = sortlist[filter_dta]
			# First shows the variables that sort the dataset
			#varlist = sorted(dtamap[filter_dta])
			varlist = sorted(dtamap[filter_dta], key=lambda x: (sorts.index(x) if x in sorts else len(sorts), x))
			if not varlist: return
			self.suggestions = ['    ----> Variables in {} <----    '.format(filter_dta)]
			self.suggestions.extend(f(var) + var for var in varlist)
		else:
			self.datasets = dtamap.keys()
			if not self.datasets: return
			self.suggestions = [['    ----> Remove filter <----    ', '']] + sorted([d, ' '.join(v if len(v)<9 else v[:9]) + '...' if len(v)>=9 else '' ] for d,v in dtamap.items())

		if prev_choice+1>=len(self.suggestions):
			prev_choice = -1
		sublime.set_timeout(lambda: self.view.window().show_quick_panel(self.suggestions, self.insert_link, selected_index=prev_choice+1), 1) #, flags=sublime.MONOSPACE_FONT)

	def insert_link(self, choice):
		# Lots of recursive calls; alternatively I could just have a while loop
		if choice==-1:
			return

		if choice==0:
			if self.menu=='all':
				self.run(None, menu='dta', prev_choice=0)
			else:
				self.run(None, menu='all')
			return

		if self.menu=='all':
			link = self.suggestions[choice][0]
		elif self.menu=='filter':
			link = self.suggestions[choice].strip(' *')
		else:
			link = self.suggestions[choice][0]
			self.run(None, menu='filter', filter_dta=link, prev_choice=0)
			return

		self.view.run_command("stata_insert", {'link':link, 'leading_space':True})
		
		# Call again until the user presses Escape
		self.run(None, menu=self.menu, filter_dta=self.filter_dta, prev_choice=choice)

class StataInsert(sublime_plugin.TextCommand):
	def run(self, edit, link, leading_space=False):
		startloc = self.view.sel()[-1].end()
		if leading_space and startloc>0 and \
		self.view.substr(startloc-1) not in (' ', '\t', '\r', '\n'):
			link = ' ' + link
		self.view.insert(edit, startloc, link)

class StataExecuteCommand(sublime_plugin.TextCommand):
	def run(self, edit, **args):
		all_text = ""
		len_sels = 0
		sels = self.view.sel()
		len_sels = 0
		for sel in sels:
			len_sels = len_sels + len(sel)

		if len_sels==0 or args.get("Build", False)==True:
			all_text = self.view.substr(self.view.find('(?s).*',0))
		else:
			self.view.run_command("expand_selection", {"to": "line"})
			for sel in sels:
				all_text = all_text + self.view.substr(sel)

		if all_text[-1] != "\n":
			all_text = all_text + "\n"

		dofile_path = os.path.join(tempfile.gettempdir(), 'st_stata_temp.tmp')

		this_file = open(dofile_path,'w')
		this_file.write(all_text)
		this_file.close()
		
		view = self.view.window().active_view()
		cwd = get_cwd(view)
		if cwd: StataAutomate("cd " + cwd)
		
		StataAutomate(str(args["Mode"]) + " " + dofile_path)

class StataHelpExternal(sublime_plugin.TextCommand):
	def run(self,edit):
		self.view.run_command("expand_selection", {"to": "word"})
		sel = self.view.sel()[0]
		help_word = self.view.substr(sel)
		help_command = "help " + help_word

		StataAutomate(help_command)

class StataHelpInternal(sublime_plugin.TextCommand):
	def run(self,edit):
		self.view.run_command("expand_selection", {"to": "word"})
		sel = self.view.sel()[0]
		help_word = self.view.substr(sel)
		help_word = re.sub(" ","_",help_word)

		help_address = "http://www.stata.com/help.cgi?" + help_word
		helpfile_path = os.path.join(tempfile.gettempdir(), 'st_stata_help.txt')

		print(help_address)

		try:
			a = urllib.request.urlopen(help_address)
			source_code = a.read().decode("utf-8")
			a.close()

			regex_pattern = re.findall("<!-- END HEAD -->\n(.*?)<!-- BEGIN FOOT -->", source_code, re.DOTALL)
			help_content = re.sub("<h2>|</h2>|<pre>|</pre>|<p>|</p>|<b>|</b>|<a .*?>|</a>|<u>|</u>|<i>|</i>","",regex_pattern[0])
			help_content = re.sub("&gt;",">",help_content)
			help_content = re.sub("&lt;",">",help_content)

			with open(helpfile_path, 'w') as f:
				f.write(help_content)

			self.window = sublime.active_window()
			self.window.open_file(helpfile_path)
		
		except:
			print("Could not retrieve help file")

class StataLoad(sublime_plugin.TextCommand):
	def run(self,edit):
		sel = self.view.substr(self.view.sel()[0])
		StataAutomate("use " + sel + ", clear")

class StataLocal(sublime_plugin.TextCommand):
	def run(self,edit):
		sels = self.view.sel()
		for sel in sels:
			word_sel = self.view.word(sel.a)
			word_str = self.view.substr(word_sel)
			word_str = "`"+word_str+"'"
			self.view.replace(edit,word_sel,word_str)

class StataRegisterAutomationCommand(sublime_plugin.ApplicationCommand):
	def run(self, **kwargs):
		stata_fn = settings.get("stata_path")
		os.popen('powershell -command start-process "{}" "/Register" -verb RunAs'.format(stata_fn))

class StataUpdateExecutablePathCommand(sublime_plugin.ApplicationCommand):
	def run(self, **kwargs):

		def update_settings(fn):
			settings_fn = 'StataEditor.sublime-settings'
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
		msg ="StataEditor: Enter the path of the Stata executable"
		sublime.active_window().show_input_panel(msg, fn, update_settings, check_correct, cancel_update)

class StataOpenTutorialCommand(sublime_plugin.ApplicationCommand):
	def run(self, **kwargs):
		url = "https://sergiocorreia.github.io/StataEditor"
		webbrowser.open_new_tab(url)



# -------------------------------------------------------------
# Functions for Automation
# -------------------------------------------------------------

def getView():
	win = sublime.active_window()
	return win.active_view()
	
def get_cwd(view):
	fn = view.file_name()
	if not fn: return
	cwd = os.path.split(fn)[0]
	return cwd

def get_metadata(view):
	buf = sublime.Region(0, view.size())
	lines = (view.substr(line).replace('"', '').strip() for line in view.split_by_newlines(buf))
	lines = [line[2:].strip() for line in lines if line.startswith('*!')]
	ans = {}
	for line in lines:
		key,val = line.split(':', 1)
		key = key.strip()
		# Allow dtapath instead of dtapaths
		if key=='dtapath': key = 'dtapaths'
		if key not in ans:
			ans[key] = [cell.strip() for cell in val.split(',')]
		elif key=='dtapaths':
			# Allow repeated 'dtapaths' tags
			ans[key].extend(cell.strip() for cell in val.split(','))
		else:
			print("Warning - Repeated autocomplete key:", key)
	if 'json' in ans: ans['json'] = ans['json'][0]
	ans['autoupdate'] = ans['autoupdate'][0].lower() in ('true','1','yes') if 'autoupdate' in ans else False
	if stata_debug: print('[METADATA]', ans)
	return ans

def get_autocomplete_data(view, force_update=False, add_from_buffer=True, obtain_varnames=True):

	# Will always check if there are new datasets in the given paths (except if autoupdate=False)
	# But will not update the varlists if all the datasets were modified before the last update

	# datasets is a tuple of (filename, pretty_dta_name)
	# variables is a tuple of (varname, pretty_var_name)

	is_stata = view.match_selector(0, "source.stata")
	if not is_stata:
		return
			
	cwd = get_cwd(view)
	if cwd is None:
		sublime.error_message("Save the file to use autocompletion")
		return (None, None) if obtain_varnames else None
		
	metadata = get_metadata(view)
	paths = metadata.get('dtapaths', [])
	json_fn = metadata.get('json', '')
	json_fn = os.path.join(cwd, json_fn) if cwd and json_fn else ''
	json_exists = os.path.isfile(json_fn)
	autoupdate = True if force_update or not json_exists else metadata['autoupdate']

	if force_update and not json_fn:
		sublime.status_message('StataEdit Error: JSON filename was not set or file not saved')
		raise Exception(".json filename not specified in metadata")

	if json_exists and not force_update:
		# Read JSON
		with open(json_fn) as fh:
			data = json.load(fh)
		# If possible, use results stored in JSON
		if not autoupdate:
			variables = data['variables']
			sortlist = data['sortlist']
			datasets = data['datasets']

	# Else, first get list of datasets
	if autoupdate:
		datasets = get_datasets(view, paths)
	if stata_debug: print('[DATASETS]', datasets)

	# Get list of varnames
	if obtain_varnames and autoupdate:
		
		#assert datasets # Bugbug
		if not datasets:
			sublime.error_message("No datasets found in the paths " + str(paths) )
			return (None, None)

		if json_exists and not force_update:
			last_updated = data['updated']
			last_modified = max(os.path.getmtime(fn) for fn,_ in data['datasets'])
			needs_update = (last_updated<last_modified) or (datasets!=data['datasets'])
		else:
			needs_update = True

		if needs_update:
			variables, sortlist = get_variables(datasets)
		else:
			variables = data['variables']
			sortlist = data['sortlist']

	# Save JSON
	if autoupdate and json_fn and obtain_varnames and needs_update:
		last_updated = calendar.timegm(time.gmtime())
		data = {'updated': last_updated, 'datasets': datasets, 'variables': variables, 'sortlist': sortlist}
		with open(json_fn,'w') as fh:
			json.dump(data, fh, indent="\t")
		print('JSON file updated')

	# Add datasets from -save- commands and variables from -gen- commands
	if add_from_buffer:
		if obtain_varnames:
			if stata_debug: print('Varnames from current file:', get_generates(view))
			variables[' (current)'] = get_generates(view)
			sortlist[' (current)'] = []
		else:
			datasets.extend(get_saves(view))

	if obtain_varnames:
		assert variables
	return (variables, sortlist) if obtain_varnames else datasets

def get_datasets(view, paths):
	return list([fn,dta] for (fn,dta) in set( dta for path in paths for dta in get_dta_in_path(view, path) ))

def get_dta_in_path(view, path):
	"""Return list of tuples (full_filename, pretty_filename)"""

	# Paths may be relative to current Stata file
	cwd = get_cwd(view)
	os.chdir(cwd)

	if '=' in path:
		nick, path = path.split('=', 1)
	else:
		nick = path
	
	if not os.path.isdir(path): return []
	# full file path, file name used in stata ($; no .dta)
	ans = [fn for fn in os.listdir(path) if fn.endswith('.dta')]
	ans = [ ( os.path.join(path,fn), nick + '/' + fn[:-4]) for fn in ans]
	return ans

def get_variables(datasets):
	"""Return dict of lists dta:varnames for all datasets"""
	varlist = dict()
	sortlist = dict()
	for (fn,dta) in datasets:
		varlist[dta], sortlist[dta] = get_vars(fn)
	return varlist, sortlist

def get_vars(fn):
	cmd = "describe using {}, varlist"
	StataAutomate(cmd.format(fn), sync=True)
	varlist = sublime.stata.StReturnString("r(varlist)")
	sortlist = sublime.stata.StReturnString("r(sortlist)")
	if stata_debug: print('[DTA={}]'.format(fn), varlist)
	StataAutomate("cap cls") # Try to clean up
	return varlist.split(' '), sortlist.split(' ')

def get_saves(view):
	buf = sublime.Region(0, view.size())
	pat = '''^[ \t]*save[ \t]+"?([a-zA-Z0-9_`'.~ /:\\-]+)"?'''
	source = view.substr(buf)
	regex = re.findall(pat, source, re.MULTILINE)
	ans = [('',fn) for fn in regex]
	return ans

def get_generates(view):

	# 1) First infer variables from current code

	buf = sublime.Region(0, view.size())
	# Only accepts gen|generate|egen (the most common ones) and only the common numeric types
	pat = '''^[ \t]*(?:gen|generate|egen)[ \t]+(?:(?:byte|int|long|float|double)[ \t]+)?([a-zA-Z0-9_`']+)[ \t]*='''
	source = view.substr(buf)
	regex = re.findall(pat, source, re.MULTILINE)
	ans = set(regex)

	# 2) Then, add variables from current Stata session

	if settings.get("variable_completions") == True:
		try:
			varlist = sublime.stata.VariableNameArray()
			ans.update(varlist)
		except:
			print("[Stata] Note: couldn't obtain varlist from current Stata window")

	return list(ans)

# -------------------------------------------------------------
# Functions for Talking to Stata
# -------------------------------------------------------------

def plugin_loaded():
	global settings
	settings = sublime.load_settings(settings_file)

def StataAutomate(stata_command, sync=False):
	""" Launch Stata (if needed) and send commands """
	try:
		sublime.stata.DoCommand(stata_command) if sync else sublime.stata.DoCommandAsync(stata_command)
	except:
		launch_stata()
		sublime.stata.DoCommand(stata_command) if sync else sublime.stata.DoCommandAsync(stata_command)
	if stata_debug: print('[CMD]', stata_command)

def launch_stata():
	stata_fn = settings.get("stata_path")
	if not check_correct_executable(stata_fn):
		print('Stata path not found in settings')
		sublime.run_command('stata_update_executable_path')
		return

	#	stata_fn = settings.get("stata_path")
	#	if not check_correct_executable(stata_fn):
	#		sublime.error_message("Cannot run Stata; the path does not exist: {}".format(stata_fn))

	try:
		win32api.WinExec(stata_fn, win32con.SW_SHOWMINNOACTIVE)
		sublime.stata = win32com.client.Dispatch("stata.StataOLEApp")
	except:
		sublime.run_command('stata_register_automation')
		sublime.error_message("StataEditor: Stata Automation type library appears to be unregistered, see http://www.stata.com/automation/#install")

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
	r"Applications\StataMP-64.exe\shell\open\command",
	r"Stata12Data\shell\open\command"]

	key_found = False
	for subkey in subkeys:
		try:
			key = winreg.OpenKey(reg, subkey)
			fn = winreg.QueryValue(key, None).strip('"').split('"')[0]
			key_found = True
		except:
			#print("StataEditor: key not found, searching more;", subkey)
			pass
		if key_found:
			break
	else:
		print("StataEditor: Couldn't find Stata path")
		settings_fn = 'StataEditor.sublime-settings'
		settings = sublime.load_settings(settings_fn)
		fn = settings.get('stata_path', settings.get('stata_path_old', ''))
	return fn

def check_correct_executable(fn):
	return os.path.isfile(fn) and 'stata' in fn.lower()
