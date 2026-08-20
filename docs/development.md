# Development and validation

## Local development setup

Symlink the repository to the Sublime Text Packages directory as `Stata`; see
[Installation](installation.md#2-install-the-package-as-a-loose-package). Sublime normally reloads
changed loose-package resources automatically. Python plugin changes may require a restart after a load
failure.

The `.python-version` file is a Sublime package runtime selector, not a pyenv configuration file. It
must remain tracked and contain `3.14`. Sublime's
[API environment documentation](https://www.sublimetext.com/docs/api_environments.html#python-version)
describes this mechanism.

## Repository validation

Run the dependency-free package checks from the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 tests/validate_package.py
```

The unit suite exercises the editor-independent execution and completion helpers. The package validator
checks:

- Python source syntax;
- Sublime JSON-with-comments resources;
- Stata and Mata syntax identities and file-extension declarations;
- snippet XML structure and unique tab triggers;
- the Python 3.14 runtime selector;
- public command names across Python, menus, keymaps, and the build target;
- the approved Linux settings contract and package-test variant.

The internal boundaries are described in [Architecture](architecture.md), and catalog maintenance is
covered in [Catalog regeneration](catalog-regeneration.md).

GitHub Actions runs both commands under Python 3.14. Behavioral Linux delivery still requires a real
X11 desktop and running Stata GUI, so use the manual checks below before a release.

## Syntax tests in Sublime Text

Open `tests/syntax_test_stata.do` or `tests/syntax_test_mata.mata`, switch **Tools > Build System** to
**Automatic**, and press <kbd>Ctrl+B</kbd>. Sublime recognizes the `SYNTAX TEST` header and runs all
package syntax assertions in its output panel. This uses Sublime's real syntax engine and complements
the dependency-free structural validator. See Sublime's
[syntax-testing documentation](https://www.sublimetext.com/docs/syntax.html#testing) for the assertion
format.

## Manual acceptance checks

1. Open one Stata GUI and run a full unsaved do-file buffer with <kbd>Ctrl+B</kbd>; with one project
   folder, confirm that folder becomes Stata's working directory.
2. Run one selection and multiple overlapping selections; confirm complete lines execute once in
   source order. Verify a Windows/CRLF source with active `#delimit ;` too.
3. Use source paths containing spaces and Unicode and confirm Stata changes to the correct directory.
4. Verify the default `Ctrl+1` sequence focuses the Command pane, then test a configured alternative.
5. Open two Stata windows, choose each target in turn, then restore most-recent targeting.
6. Close a pinned window and confirm the next run stops with a stale-pin error and does not execute in
   another Stata session.
7. Test both `activate_restore` and `background` delivery. While Stata is busy, verify the package says
   only that code was sent and never retries automatically.
8. Verify actionable errors for missing `xdotool`, Wayland, no Stata window, and a stale pin.
9. Verify <kbd>F1</kbd> for selected text and the command under the caret.
10. Toggle quoted, macro-based, and unquoted `save`/`use` lines using multiple cursors. Confirm one undo
    reverts the entire operation and ambiguous/continued lines remain unchanged.
11. Run an ado/Mata test through `Run Package Test (build.txt)`.
12. Inspect representative Stata, Mata, embedded Python, LaTeX, and frame code with syntax tests.

## Style and package conventions

Use [`extra/STATA_STYLE_GUIDE.md`](../extra/STATA_STYLE_GUIDE.md) as the source of truth for Stata
snippets and examples. In particular: literal tabs, a roughly 100-character line width, `forvalues` for
regular numeric loops, explicit merge contracts, typed generated variables, and frames for accumulated
results.

Keep the execution bridge's public command names stable:

- `stata_exec`
- `stata_choose_target_window`
- `stata_use_recent_window`
- `stata_toggle_dataset_io`
- `stata_help`

Changing one requires coordinated updates to keymaps, menus, documentation, and validation.

## Release checklist

1. Run the package validator and Sublime syntax tests.
2. Complete the Linux/Stata manual acceptance checks.
3. Update `CHANGELOG.md` and use a semantic-version Git tag.
4. Confirm no `.pyc`, `package-metadata.json`, temporary do-files, or private research data are tracked.
5. Verify installation from a fresh loose clone named `Stata`.

Package Control's current submission guidance requires semantic version tags for GitHub-hosted releases:
[Submitting a Package](https://packagecontrol.io/docs/submitting_a_package).
