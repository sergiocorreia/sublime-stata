from __future__ import annotations

import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from completions import extended_locals


ROOT = Path(__file__).resolve().parents[1]


class RichStaticCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        payload = json.loads(
            (ROOT / "Stata.sublime-completions").read_text(encoding="utf-8")
        )
        self.entries = {entry["trigger"]: entry for entry in payload["completions"]}

    def test_required_research_workflows_have_rich_entries(self) -> None:
        required = {
            "frame": "framecreate",
            "frlink": "frlink",
            "frget": "frget",
            "collect": "collectlayout",
            "dtable": "dtable",
            "etable": "etable",
            "didregress": "didregress",
            "hdidregress": "hdidregress",
            "telasso": "telasso",
            "cate": "cate",
            "mediate": "mediate",
            "lateffects": "lateffects",
            "xtswitchdid": "xtswitchdid",
            "h2oml": "h2oml-gbregress",
            "gisid": "gisid",
            "gegen": "gegen",
            "reghdfe": "reghdfe-absorb",
            "ppmlhdfe": "ppmlhdfe-absorb",
            "rangestat": "rangestat-interval",
        }
        for workflow, trigger in required.items():
            with self.subTest(workflow=workflow):
                entry = self.entries[trigger]
                for field in ("annotation", "contents", "kind", "details"):
                    self.assertIsInstance(entry.get(field), str)
                    self.assertTrue(entry[field].strip())
                self.assertEqual(entry["kind"], "snippet")
                self.assertIn("${", entry["contents"])

    def test_stata_entries_are_excluded_from_embedded_languages(self) -> None:
        payload = json.loads(
            (ROOT / "Stata.sublime-completions").read_text(encoding="utf-8")
        )
        scope = payload["scope"]
        for embedded in ("source.mata", "source.python", "text.tex.latex"):
            self.assertIn("- " + embedded, scope)

        for path in (ROOT / "snippets").glob("*.sublime-snippet"):
            scope = ET.parse(path).getroot().findtext("scope") or ""
            for embedded in ("source.mata", "source.python", "text.tex.latex"):
                self.assertIn("- " + embedded, scope, path.name)

    def test_command_snippets_are_visible_after_typing_the_trigger(self) -> None:
        for path in (ROOT / "snippets").glob("*.sublime-snippet"):
            scope = ET.parse(path).getroot().findtext("scope") or ""
            self.assertNotIn(
                "inner-commands",
                scope,
                "{} disappears after its command trigger is typed".format(path.name),
            )

    def test_static_triggers_do_not_duplicate_snippet_tab_triggers(self) -> None:
        snippet_triggers = set()
        for path in (ROOT / "snippets").glob("*.sublime-snippet"):
            trigger = ET.parse(path).getroot().findtext("tabTrigger")
            if trigger:
                snippet_triggers.add(trigger)
        self.assertTrue(set(self.entries).isdisjoint(snippet_triggers))

    def test_style_guide_command_and_function_snippets(self) -> None:
        expected = {
            "rename.sublime-snippet": ("rename", "rename ${1:old_name} ${2:new_name}"),
            "summarize.sublime-snippet": ("su", "su ${1:varlist}${2:, detail}"),
            "missing.sublime-snippet": ("mi-fn", "mi(${1:varlist})"),
        }
        for filename, (trigger, contents) in expected.items():
            with self.subTest(filename=filename):
                root = ET.parse(ROOT / "snippets" / filename).getroot()
                self.assertEqual(root.findtext("tabTrigger"), trigger)
                self.assertEqual((root.findtext("content") or "").strip(), contents)


class LocalCompletionTests(unittest.TestCase):
    def test_extended_local_triggers_are_clean_and_annotated(self) -> None:
        completions = extended_locals.get_completions()
        self.assertGreater(len(completions), 10)
        for trigger, annotation, contents in completions:
            self.assertNotIn("\t", trigger)
            self.assertTrue(annotation)
            self.assertTrue(contents)
        spaced = extended_locals.get_completions(add_space=True)
        self.assertTrue(all(contents.startswith(" ") for _, _, contents in spaced))

    def test_list_local_entries_are_rich_and_clean_is_correct(self) -> None:
        payload = json.loads(
            (ROOT / "list-local.sublime-completions").read_text(encoding="utf-8")
        )
        entries = {entry["trigger"]: entry for entry in payload["completions"]}
        self.assertEqual(entries["clean"]["contents"], "clean ${1:macname}")
        for entry in entries.values():
            self.assertTrue(
                all(entry.get(field) for field in ("annotation", "contents", "kind", "details"))
            )


class CompletionListenerStructureTests(unittest.TestCase):
    def test_filesystem_work_is_deferred_and_requests_are_guarded(self) -> None:
        source = (ROOT / "stata_completions.py").read_text(encoding="utf-8")
        self.assertIn("completion_list = sublime.CompletionList()", source)
        self.assertIn("sublime.set_timeout_async(resolve)", source)
        self.assertIn("completion_list.set_completions(", source)
        self.assertIn("sublime.INHIBIT_REORDER", source)
        self.assertLess(
            source.index("catalog.matching_snippet_candidates("),
            source.index("catalog.command_candidates("),
        )
        self.assertIn("view.change_count()", source)
        self.assertIn("request_locations", source)
        self.assertIn("window.views()", source)
        self.assertIn("source.mata, source.python, text.tex.latex", source)
        self.assertIn('view.match_selector(point, "string")', source)
        self.assertIn('context.kind not in (', source)
        self.assertLess(
            source.index("sublime.set_timeout_async(resolve)"),
            source.index("return completion_list"),
        )

    def test_mata_owns_its_dot_trigger_and_editor_settings(self) -> None:
        mata = json.loads((ROOT / "Mata.sublime-settings").read_text(encoding="utf-8"))
        stata_text = (ROOT / "Stata.sublime-settings").read_text(encoding="utf-8")
        self.assertEqual(mata["translate_tabs_to_spaces"], False)
        self.assertEqual(mata["rulers"], [100])
        self.assertTrue(mata["ensure_newline_at_eof_on_save"])
        self.assertEqual(mata["auto_complete_triggers"][0]["characters"], ".")
        self.assertRegex(mata["auto_complete_triggers"][0]["selector"], r"source\.mata")
        self.assertNotIn('"selector": "source.mata', stata_text)


if __name__ == "__main__":
    unittest.main()
