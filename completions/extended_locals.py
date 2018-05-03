import sublime

# This lists contain all completions.
# A tuple with only one string means the label is the same
# as the completion, i.e. ("foo",) is equivalent to
# ("foo", "foo").

base_completions = [
	("type\tStorage type", "type ${1:varname}"),
	("format\tVariable format", "format ${1:varname}"),
	("value label\tValue label of var", "value label ${1:varname}"),
	("var label\tVariable label", "var label ${1:varname}"),
	("data label\tDataset label", "data label" ),
	("sortedby\tSorted-by variables", "sortedby"),
	("label\tValue of nth label", "label ${1:vlname} ${2:#} ${3://} , strict"),
	("label\tValue of nth label (indirect)", "label (${1:varname}) ${2:#} ${3://} , strict"),
	("char\tVariable characteristics", "char ${1:var}[${2:}]"),
	("word count\t# of words in string", "word count `${1:loc}'"),
	("word #\tn-th word of string", "word ${2:#} of `${1:loc}'"),
	("subinstr\treplace string", "subinstr loc ${1:macname} \"${2:from}\" \"${3:to}\" // , all word count(local locname)"),
	("list", "list "),
	("directory\tDirectory contents", "dir \"${1:dirname}\" ${2:files} \"${3:*}\", respectcase"),
	("environment\tOS environment info", "environment ${1:name}"),
	("rownames\tMatrix row names", "rownames ${1:matrixname}"),
	("colnames\tMatrix col names", "colnames ${1:matrixname}"),
	("rowfullnames\tMatrix full row names", "rowfullnames ${1:matrixname}"),
	("colfullnames\tMatrix full col names", "colfullnames ${1:matrixname}"),
	("roweq\tMatrix row equations", "roweq ${1:matrixname}"),
	("coleq\tMatrix col equations", "coleq ${1:matrixname}"),
]

def get_completions(add_space=False):
    if add_space:
    	completions = [(label, ' ' + completion) for label, completion in base_completions]
    else:
    	completions = base_completions

    #return completions
    return completions, sublime.INHIBIT_WORD_COMPLETIONS
