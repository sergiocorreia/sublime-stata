#!/usr/bin/env python3
"""Dependency-free structural validation for the Sublime Stata package."""

from __future__ import annotations

import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_COMMANDS = {
    "stata_exec",
    "stata_choose_target_window",
    "stata_use_recent_window",
    "stata_toggle_dataset_io",
    "stata_help",
}

BUILTIN_COMMANDS = {
    "edit_settings",
    "insert_snippet",
    "left_delete",
    "open_file",
    "run_macro_file",
}

JSONC_GLOBS = (
    "*.sublime-build",
    "*.sublime-commands",
    "*.sublime-completions",
    "*.sublime-keymap",
    "*.sublime-menu",
    "*.sublime-settings",
)


class ValidationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def strip_json_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving quoted strings."""
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue

        if char == "/" and next_char == "/":
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue

        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(text) and text[index : index + 2] != "*/":
                if text[index] in "\r\n":
                    output.append(text[index])
                index += 1
            if index + 1 >= len(text):
                fail("unterminated block comment in JSON-with-comments resource")
            index += 2
            continue

        output.append(char)
        index += 1

    if in_string:
        fail("unterminated string in JSON-with-comments resource")
    return "".join(output)


def strip_trailing_commas(text: str) -> str:
    """Remove commas immediately before ] or } while preserving strings."""
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False

    while index < len(text):
        char = text[index]

        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue

        if char == ",":
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead < len(text) and text[lookahead] in "]}":
                index += 1
                continue

        output.append(char)
        index += 1

    return "".join(output)


def load_jsonc(path: Path) -> Any:
    try:
        cleaned = strip_trailing_commas(strip_json_comments(path.read_text(encoding="utf-8")))
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValidationError) as error:
        fail(f"{path.relative_to(ROOT)}: invalid Sublime JSON: {error}")


def camel_to_snake(name: str) -> str:
    first_pass = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first_pass).lower()


def python_commands() -> set[str]:
    commands: set[str] = set()
    for path in sorted(ROOT.glob("*.py")) + sorted((ROOT / "completions").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as error:
            fail(f"{path.relative_to(ROOT)}: Python syntax error: {error}")

        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith("Command"):
                commands.add(camel_to_snake(node.name.removesuffix("Command")))
    return commands


def collect_commands(value: Any) -> set[str]:
    commands: set[str] = set()
    if isinstance(value, dict):
        command = value.get("command")
        if isinstance(command, str):
            commands.add(command)
        for child in value.values():
            commands.update(collect_commands(child))
    elif isinstance(value, list):
        for child in value:
            commands.update(collect_commands(child))
    return commands


def command_captions(value: Any) -> set[tuple[str, str]]:
    entries: set[tuple[str, str]] = set()
    if isinstance(value, dict):
        command = value.get("command")
        caption = value.get("caption")
        if isinstance(command, str) and isinstance(caption, str):
            entries.add((command, caption))
        for child in value.values():
            entries.update(command_captions(child))
    elif isinstance(value, list):
        for child in value:
            entries.update(command_captions(child))
    return entries


def validate_json_resources() -> dict[Path, Any]:
    resources: dict[Path, Any] = {}
    paths: set[Path] = set()
    for pattern in JSONC_GLOBS:
        paths.update(ROOT.glob(pattern))

    for path in sorted(paths):
        resources[path] = load_jsonc(path)
    return resources


def validate_runtime() -> None:
    version = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    if version != "3.14":
        fail(f".python-version must contain 3.14, found {version!r}")

    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    if ".python-version" in {line.strip() for line in ignored}:
        fail(".gitignore must not ignore Sublime's .python-version selector")


def validate_syntax_headers() -> None:
    expected = {
        "Stata.sublime-syntax": ("name: Stata", "scope: source.stata", ("do", "ado", "doh")),
        "Mata.sublime-syntax": ("name: Mata", "scope: source.mata", ("mata",)),
    }
    for filename, (name, scope, extensions) in expected.items():
        path = ROOT / filename
        text = path.read_text(encoding="utf-8")
        if not text.startswith("%YAML 1.2\n---\n"):
            fail(f"{filename}: missing Sublime YAML 1.2 header")
        if name not in text or scope not in text or "\ncontexts:\n" not in text:
            fail(f"{filename}: missing required name, scope, or contexts declaration")
        for extension in extensions:
            if not re.search(rf"(?m)^  - {re.escape(extension)}$", text):
                fail(f"{filename}: missing .{extension} file extension")

    syntax_tests = {
        "tests/syntax_test_stata.do": '// SYNTAX TEST "Packages/Stata/Stata.sublime-syntax"',
        "tests/syntax_test_mata.mata": '// SYNTAX TEST "Packages/Stata/Mata.sublime-syntax"',
    }
    for filename, expected_header in syntax_tests.items():
        path = ROOT / filename
        if not path.is_file():
            fail(f"missing Sublime syntax test: {filename}")
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        if first_line != expected_header:
            fail(f"{filename}: invalid SYNTAX TEST header")


def validate_commands(resources: dict[Path, Any]) -> None:
    implemented = python_commands()
    missing = PUBLIC_COMMANDS - implemented
    if missing:
        fail(f"public commands have no *Command class: {sorted(missing)}")

    surface_paths = [
        ROOT / "Default.sublime-keymap",
        ROOT / "Main.sublime-menu",
        ROOT / "Stata.sublime-commands",
        ROOT / "Stata.sublime-build",
    ]
    referenced: set[str] = set()
    for path in surface_paths:
        referenced.update(collect_commands(resources[path]))

    unknown = referenced - implemented - BUILTIN_COMMANDS - {"build"}
    if unknown:
        fail(f"package surfaces reference unknown commands: {sorted(unknown)}")

    palette_commands = collect_commands(resources[ROOT / "Stata.sublime-commands"])
    missing_from_palette = PUBLIC_COMMANDS - palette_commands
    if missing_from_palette:
        fail(f"public commands missing from Stata.sublime-commands: {sorted(missing_from_palette)}")

    menu_commands = collect_commands(resources[ROOT / "Main.sublime-menu"])
    missing_from_menu = PUBLIC_COMMANDS - menu_commands
    if missing_from_menu:
        fail(f"public commands missing from Main.sublime-menu: {sorted(missing_from_menu)}")

    menu_captions = command_captions(resources[ROOT / "Main.sublime-menu"])
    palette_captions = command_captions(resources[ROOT / "Stata.sublime-commands"])
    if ("stata_exec", "Run Selection or Buffer") not in menu_captions:
        fail("Main.sublime-menu must caption stata_exec as Run Selection or Buffer")
    if ("stata_exec", "Stata: Run Selection or Buffer") not in palette_captions:
        fail("Stata.sublime-commands must caption stata_exec as Stata: Run Selection or Buffer")

    obsolete = {
        "stata_autocomplete_dta",
        "stata_autocomplete_var",
        "stata_help_external",
        "stata_help_internal",
        "stata_register_automation",
        "stata_update_executable_path",
    }
    stale = referenced & obsolete
    if stale:
        fail(f"obsolete commands remain on public surfaces: {sorted(stale)}")


def validate_keymap(resources: dict[Path, Any]) -> None:
    if (ROOT / "Default (Windows).sublime-keymap").exists():
        fail("shared Stata bindings must live in Default.sublime-keymap")

    keymap = resources[ROOT / "Default.sublime-keymap"]
    bindings = [item for item in keymap if isinstance(item, dict)]

    def find_binding(keys: tuple[str, ...], command: str) -> dict[str, Any] | None:
        return next(
            (
                binding
                for binding in bindings
                if tuple(binding.get("keys", [])) == keys and binding.get("command") == command
            ),
            None,
        )

    help_binding = find_binding(("f1",), "stata_help")
    toggle_binding = find_binding(("ctrl+alt+u",), "stata_toggle_dataset_io")
    if help_binding is None:
        fail("F1 must invoke stata_help")
    if toggle_binding is None:
        fail("Ctrl+Alt+U must invoke stata_toggle_dataset_io")

    for label, binding in (("F1", help_binding), ("Ctrl+Alt+U", toggle_binding)):
        contexts = binding.get("context", [])
        is_stata_scoped = any(
            context.get("key") == "selector"
            and context.get("operand")
            == "source.stata - source.mata - source.python - text.tex.latex"
            for context in contexts
            if isinstance(context, dict)
        )
        if not is_stata_scoped:
            fail(f"{label} binding must exclude embedded Mata, Python, and LaTeX")

    bound_keys = {tuple(binding.get("keys", [])) for binding in bindings}
    missing_shared_keys = {("'",), ('"',), ("`",), ("backspace",)} - bound_keys
    if missing_shared_keys:
        fail(f"missing shared Stata quote/macro bindings: {sorted(missing_shared_keys)}")
    if find_binding((":",), "autocomplete_colon") is None:
        fail("extended-local colon completion binding must be preserved")


def validate_settings(resources: dict[Path, Any]) -> None:
    settings = resources[ROOT / "Stata.sublime-settings"]
    expected = {
        "linux_delivery_mode": "activate_restore",
        "linux_command_focus_keys": ["ctrl+1"],
        "linux_stata_executables": ["xstata-mp", "xstata-se", "xstata"],
        "ado_paths": [],
        "command_priorities": [],
        "stata_path": "",
        "translate_tabs_to_spaces": False,
        "rulers": [100],
    }
    for key, expected_value in expected.items():
        if settings.get(key) != expected_value:
            fail(f"Stata.sublime-settings: {key} must default to {expected_value!r}")

    mata_settings = resources[ROOT / "Mata.sublime-settings"]
    for key, expected_value in {
        "translate_tabs_to_spaces": False,
        "rulers": [100],
        "ensure_newline_at_eof_on_save": True,
    }.items():
        if mata_settings.get(key) != expected_value:
            fail(f"Mata.sublime-settings: {key} must default to {expected_value!r}")


def validate_build(resources: dict[Path, Any]) -> None:
    build = resources[ROOT / "Stata.sublime-build"]
    if build.get("target") != "stata_exec":
        fail("Stata.sublime-build must target stata_exec")
    if build.get("action") != "do":
        fail("Stata.sublime-build must run selection/buffer content by default")
    if build.get("selector") != "source.stata, source.mata":
        fail("Stata.sublime-build must cover source.stata and source.mata")

    expected_variant = {"name": "Run Package Test (build.txt)", "mode": "build"}
    if build.get("variants") != [expected_variant]:
        fail("Stata.sublime-build must expose only the approved build.txt variant")


def validate_snippets() -> None:
    triggers: dict[str, Path] = {}
    snippets: dict[str, str] = {}

    for path in sorted((ROOT / "snippets").glob("*.sublime-snippet")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as error:
            fail(f"{path.relative_to(ROOT)}: invalid snippet XML: {error}")

        if root.tag != "snippet":
            fail(f"{path.relative_to(ROOT)}: root element must be <snippet>")

        for element in root.iter():
            if element.tail and element.tail.strip():
                fail(f"{path.relative_to(ROOT)}: unexpected text after <{element.tag}>")

        required = {name: root.find(name) for name in ("content", "tabTrigger", "scope", "description")}
        missing = [name for name, element in required.items() if element is None or not element.text]
        if missing:
            fail(f"{path.relative_to(ROOT)}: missing snippet fields {missing}")

        trigger = required["tabTrigger"].text.strip()
        if trigger in triggers:
            fail(
                f"duplicate snippet trigger {trigger!r}: "
                f"{triggers[trigger].relative_to(ROOT)} and {path.relative_to(ROOT)}"
            )
        triggers[trigger] = path
        content = required["content"].text
        if content.startswith(("\r", "\n")) or content.endswith(("\r", "\n")):
            fail(f"{path.relative_to(ROOT)}: snippet content has an unintended edge newline")
        if "inner-commands" in required["scope"].text:
            fail(
                f"{path.relative_to(ROOT)}: snippet scope must not exclude inner-commands; "
                "the caret enters that scope as soon as a command trigger is typed"
            )
        snippets[trigger] = content

    required_triggers = {
        "dofile-template",
        "forv",
        "fornum",
        "frame-results",
        "gegen-xtile",
        "merge",
        "merge-check",
        "post-scalar",
        "ppmlhdfe",
        "rangestat",
    }
    missing_triggers = required_triggers - triggers.keys()
    if missing_triggers:
        fail(f"missing style-guide snippet triggers: {sorted(missing_triggers)}")

    if "forvalues" not in snippets["forv"]:
        fail("forv snippet must expand to the unabbreviated forvalues command")
    if "keepusing(" not in snippets["merge"] or "nogen" in snippets["merge"]:
        fail("merge snippet must use keepusing() and preserve _merge for checking")
    if "tab _merge" in snippets["merge"] or "drop _merge" in snippets["merge"]:
        fail("the basic merge snippet must remain a single-line command")
    for required_check in ("tab _merge", "assert ", "drop _merge"):
        if required_check not in snippets["merge-check"]:
            fail(f"merge-check snippet is missing {required_check!r}")
    if "include common.do" not in snippets["dofile-template"]:
        fail("dofile-template must include common.do")


def validate_xml_resources() -> None:
    for path in sorted(ROOT.glob("*.tmPreferences")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as error:
            fail(f"{path.relative_to(ROOT)}: invalid XML property list: {error}")
        if root.tag != "plist" or root.find("dict") is None:
            fail(f"{path.relative_to(ROOT)}: expected a plist containing a dict")


def validate_docs() -> None:
    required = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "docs" / "installation.md",
        ROOT / "docs" / "usage.md",
        ROOT / "docs" / "linux-execution.md",
        ROOT / "docs" / "completions-and-snippets.md",
        ROOT / "docs" / "build-workflow.md",
        ROOT / "docs" / "troubleshooting.md",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "catalog-regeneration.md",
        ROOT / "docs" / "development.md",
        ROOT / "extra" / "README.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail(f"missing documentation files: {missing}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "asynchronous bridge for variables and objects" not in readme:
        fail("README must preserve live-session introspection as deferred future work")


def main() -> int:
    try:
        resources = validate_json_resources()
        validate_runtime()
        validate_syntax_headers()
        validate_commands(resources)
        validate_keymap(resources)
        validate_settings(resources)
        validate_build(resources)
        validate_snippets()
        validate_xml_resources()
        validate_docs()
    except (OSError, ValidationError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        return 1

    print("package validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
