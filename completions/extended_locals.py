"""Extended-macro completion data, independent of the Sublime API."""


# Trigger, annotation, snippet contents.  Keeping display metadata separate
# prevents legacy tab-delimited labels from leaking into CompletionItem.trigger.
BASE_COMPLETIONS = [
    ("type", "storage type", "type ${1:varname}"),
    ("format", "variable format", "format ${1:varname}"),
    ("value label", "value label of variable", "value label ${1:varname}"),
    ("var label", "variable label", "var label ${1:varname}"),
    ("data label", "dataset label", "data label"),
    ("sortedby", "sorted-by variables", "sortedby"),
    ("label", "value of nth label", "label ${1:vlname} ${2:#} ${3://} , strict"),
    (
        "label indirect",
        "value of nth label (indirect)",
        "label (${1:varname}) ${2:#} ${3://} , strict",
    ),
    ("char", "variable characteristics", "char ${1:var}[${2:}]"),
    ("word count", "number of words", "word count `${1:loc}'"),
    ("word", "nth word", "word ${2:#} of `${1:loc}'"),
    (
        "subinstr",
        "replace text",
        "subinstr local ${1:macname} \"${2:from}\" \"${3:to}\"${4:, all}",
    ),
    ("list", "macro list operation", "list "),
    (
        "directory",
        "directory contents",
        "dir \"${1:dirname}\" ${2:files} \"${3:*}\", respectcase",
    ),
    ("environment", "OS environment value", "environment ${1:name}"),
    ("rownames", "matrix row names", "rownames ${1:matrixname}"),
    ("colnames", "matrix column names", "colnames ${1:matrixname}"),
    ("rowfullnames", "matrix full row names", "rowfullnames ${1:matrixname}"),
    ("colfullnames", "matrix full column names", "colfullnames ${1:matrixname}"),
    ("roweq", "matrix row equations", "roweq ${1:matrixname}"),
    ("coleq", "matrix column equations", "coleq ${1:matrixname}"),
]


def get_completions(add_space=False):
    prefix = " " if add_space else ""
    return [
        (trigger, annotation, prefix + completion)
        for trigger, annotation, completion in BASE_COMPLETIONS
    ]
