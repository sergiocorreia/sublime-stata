from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SyntaxResourceTests(unittest.TestCase):
    def test_v2_headers_and_standalone_mata_extension(self) -> None:
        stata = (ROOT / "Stata.sublime-syntax").read_text(encoding="utf-8")
        mata = (ROOT / "Mata.sublime-syntax").read_text(encoding="utf-8")
        self.assertRegex(stata, r"(?m)^version: 2$")
        self.assertRegex(mata, r"(?m)^version: 2$")
        self.assertIn("first_line_match: '(?i)", stata)
        stata_extensions = re.search(
            r"(?ms)^file_extensions:\n(?P<body>(?:  - .+\n)+)", stata
        ).group("body")
        self.assertNotIn("- mata", stata_extensions)
        self.assertRegex(mata, r"(?m)^  - mata$")

    def test_capture_maps_do_not_repeat_keys(self) -> None:
        """Catch duplicate YAML capture keys, which permissive parsers hide."""

        for filename in ("Stata.sublime-syntax", "Mata.sublime-syntax"):
            lines = (ROOT / filename).read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines):
                if line.strip() != "captures:":
                    continue
                block_indent = len(line) - len(line.lstrip())
                keys: set[int] = set()
                for nested_number in range(line_number + 1, len(lines)):
                    nested = lines[nested_number]
                    if not nested.strip():
                        continue
                    indent = len(nested) - len(nested.lstrip())
                    if indent <= block_indent:
                        break
                    match = re.match(r"\s+(\d+):", nested)
                    if not match:
                        continue
                    key = int(match.group(1))
                    self.assertNotIn(
                        key,
                        keys,
                        f"{filename}:{nested_number + 1}: duplicate capture {key}",
                    )
                    keys.add(key)

    def test_syntax_fixtures_cover_structural_regressions(self) -> None:
        stata_fixture = (ROOT / "tests" / "syntax_test_stata.do").read_text(
            encoding="utf-8"
        )
        mata_fixture = (ROOT / "tests" / "syntax_test_mata.mata").read_text(
            encoding="utf-8"
        )
        for required in (
            "entity.name.section",
            "prog def research_command",
            "support.function.result.stata",
            "#delimit ;",
            "futuristic outcome",
            "storage.modifier.factor-variable.stata",
            "storage.modifier.time-series.stata",
            "keyword.operator.interaction.stata",
            "by id: quietly capture regress",
            "ib(first).region",
            "ib(last).industry",
            "ib(freq).sector",
            "dtable income age ///",
            "order price weight ///",
            "order price weight ////",
            "length // an ordinary comment ends this continued command",
            "#delimit ;\n// <- keyword.control.directive.stata\ndtable income age",
            "continuous(income, statistics(mean sd));",
            "mata: sqrt(4); collect clear;",
            'python: print("semicolon Python"); collect clear;',
            "punctuation.terminator.statement.stata",
            "mata;\n// <- support.function.command.stata",
            "python;\n# <- support.function.command.stata",
            "semicolon_result = sum([1, 2, 3])",
            "#delimit cr\n// <- keyword.control.directive.stata\nsummarize outcome",
            "string.quoted.double.compound.stata",
            "frame create analysis",
            "mata: sqrt(4)",
            'python: print("inline Python")',
            "source.python",
            "text.tex.latex",
        ):
            self.assertIn(required, stata_fixture)
        self.assertIn('SYNTAX TEST "Packages/Stata/Mata.sublime-syntax"', mata_fixture)

    def test_semicolon_and_newline_command_bodies_have_distinct_terminators(self) -> None:
        syntax = (ROOT / "Stata.sublime-syntax").read_text(encoding="utf-8")

        def context_body(name: str) -> str:
            match = re.search(
                rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [A-Za-z][A-Za-z0-9-]*:|\Z)",
                syntax,
            )
            self.assertIsNotNone(match, name)
            return match.group("body")

        newline_body = context_body("command-body")
        semicolon_body = context_body("semicolon-command-body")
        self.assertIn("- match: '$'", newline_body)
        self.assertNotIn("- match: '$'", semicolon_body)
        self.assertIn("- match: ';'", semicolon_body)
        self.assertIn(
            "push: semicolon-main",
            context_body("delimiter-switch-to-semicolon"),
        )
        self.assertIn("pop: true", context_body("delimiter-switch-to-newline"))

    def test_slash_continuations_preserve_the_newline_command_context(self) -> None:
        syntax = (ROOT / "Stata.sublime-syntax").read_text(encoding="utf-8")

        def context_body(name: str) -> str:
            match = re.search(
                rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [A-Za-z][A-Za-z0-9-]*:|\Z)",
                syntax,
            )
            self.assertIsNotNone(match, name)
            return match.group("body")

        comments = context_body("comments")
        self.assertIn("- match: '///.*$'", comments)
        self.assertIn("push: line-continuation", comments)
        self.assertNotIn("(?:\\n|$)", comments)
        continuation = context_body("line-continuation")
        self.assertIn("meta_include_prototype: false", continuation)
        self.assertIn("- match: '^'", continuation)
        self.assertIn("pop: true", continuation)

    def test_embedded_languages_follow_the_active_delimiter(self) -> None:
        syntax = (ROOT / "Stata.sublime-syntax").read_text(encoding="utf-8")

        def context_body(name: str) -> str:
            match = re.search(
                rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [A-Za-z][A-Za-z0-9-]*:|\Z)",
                syntax,
            )
            self.assertIsNotNone(match, name)
            return match.group("body")

        newline_main = context_body("main").splitlines()
        semicolon_main = context_body("semicolon-main").splitlines()
        newline_embeds = context_body("embedded-languages")
        semicolon_embeds = context_body("semicolon-embedded-languages")

        self.assertIn("    - include: embedded-languages", newline_main)
        self.assertIn("    - include: semicolon-embedded-languages", semicolon_main)
        self.assertNotIn("with_prototype:", syntax)
        self.assertIn(
            "    - match: '{{semicolon_start}}(mata)\\s*(;)'",
            semicolon_embeds,
        )
        self.assertIn(
            "    - match: '{{semicolon_start}}(python)\\s*(;)'",
            semicolon_embeds,
        )
        for language in ("mata", "python"):
            self.assertIn(
                f"push: {language}-inline-newline-body",
                newline_embeds,
            )
            self.assertIn(
                f"push: {language}-block-newline-body",
                newline_embeds,
            )
            self.assertIn(
                f"push: {language}-inline-semicolon-body",
                semicolon_embeds,
            )
            self.assertIn(
                f"push: {language}-block-semicolon-body",
                semicolon_embeds,
            )
            self.assertIn(
                "- match: '$'",
                context_body(f"{language}-inline-newline-body"),
            )
            self.assertIn(
                "- match: ';'",
                context_body(f"{language}-inline-semicolon-body"),
            )
            self.assertIn(
                "(?=^\\s*end\\s*$)",
                context_body(f"{language}-block-newline-body"),
            )
            self.assertIn(
                "(?={{semicolon_start}}(?i:end)\\s*;)",
                context_body(f"{language}-block-semicolon-body"),
            )
        self.assertIn(
            "include: Packages/Stata/Mata.sublime-syntax",
            context_body("mata-code"),
        )
        self.assertIn(
            "include: Packages/Python/Python.sublime-syntax#statements",
            context_body("python-code"),
        )
        self.assertIn(
            "include: Packages/LaTeX/TeX.sublime-syntax",
            context_body("texdoc-body"),
        )


if __name__ == "__main__":
    unittest.main()
