from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from completions import catalog


class SymbolExtractionTests(unittest.TestCase):
    def test_extracts_buffer_and_project_declarations(self) -> None:
        source = """
        generate wage = income / hours
        egen double score = std(wage)
        clonevar copied = wage
        rename old_name new_name
        input byte id str12 person double amount
        local outcome wage
        global DATA data/raw
        tempvar marked sampled // internal variables
        tempfile results
        tempname post_handle
        frame create analysis id str20 label outcome
        frame copy default backup
        frame rename backup final_results
        frame put id outcome, into(subset)
        program define research_estimator
        prog def quick_estimator
        """

        index = catalog.extract_symbols(source)

        self.assertTrue(
            {"wage", "score", "copied", "new_name", "id", "person", "amount", "label", "outcome"}
            <= set(index.variables)
        )
        self.assertEqual(index.tempvars, ("marked", "sampled"))
        self.assertEqual(index.tempfiles, ("results",))
        self.assertEqual(index.tempnames, ("post_handle",))
        self.assertTrue(
            {"outcome", "marked", "sampled", "results", "post_handle"}
            <= set(index.locals)
        )
        self.assertEqual(
            set(index.frames), {"analysis", "backup", "final_results", "subset"}
        )
        self.assertEqual(index.programs, ("quick_estimator", "research_estimator"))
        self.assertEqual(index.globals, ("DATA",))

    def test_merges_every_symbol_category(self) -> None:
        first = catalog.SymbolIndex(tempvars=("one",), frames=("main",))
        second = catalog.SymbolIndex(tempvars=("two",), frames=("results",))
        merged = first.merged(second)
        self.assertEqual(merged.tempvars, ("one", "two"))
        self.assertEqual(merged.frames, ("main", "results"))


class ContextTests(unittest.TestCase):
    def test_detects_command_positions(self) -> None:
        for line, fragment in (
            ("", ""),
            ("reg", "reg"),
            ("quietly hdid", "hdid"),
            ("by group: med", "med"),
            ("collect create report; dta", "dta"),
        ):
            with self.subTest(line=line):
                self.assertEqual(
                    catalog.detect_context(line),
                    catalog.CompletionContext("command", fragment),
                )

    def test_detects_macro_path_and_symbol_positions(self) -> None:
        self.assertEqual(
            catalog.detect_context("display `out"),
            catalog.CompletionContext("local", "out"),
        )
        self.assertEqual(
            catalog.detect_context("display ${DAT"),
            catalog.CompletionContext("global", "DAT"),
        )
        self.assertEqual(
            catalog.detect_context('use "data/pan'),
            catalog.CompletionContext("path", "data/pan"),
        )
        self.assertEqual(
            catalog.detect_context('use "$da'),
            catalog.CompletionContext("global", "da"),
        )
        self.assertEqual(
            catalog.detect_context('use "${DA'),
            catalog.CompletionContext("global", "DA"),
        )
        self.assertEqual(
            catalog.detect_context('use "`dat'),
            catalog.CompletionContext("local", "dat"),
        )
        self.assertEqual(
            catalog.detect_context("replace long_variable"),
            catalog.CompletionContext("symbol", "long_variable"),
        )


class FilesystemCompletionTests(unittest.TestCase):
    def test_recursive_scans_collapse_nested_project_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "analysis"
            nested.mkdir()
            self.assertEqual(catalog.normalize_roots([str(nested), str(root)]), (str(nested), str(root)))
            self.assertEqual(catalog.minimal_roots([str(nested), str(root)]), (str(root),))

    def test_discovers_ado_commands_and_filters_private_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "publiccmd.ado").write_text("program publiccmd\n", encoding="utf-8")
            (root / "_helper.ado").write_text("program _helper\n", encoding="utf-8")
            self.assertEqual(catalog.discover_ado_commands([directory]), ("publiccmd",))

    def test_nested_ado_changes_refresh_after_bounded_cache_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "p"
            nested.mkdir()
            first = nested / "firstcmd.ado"
            second = nested / "secondcmd.ado"
            first.write_text("program firstcmd\n", encoding="utf-8")

            with mock.patch.object(catalog.time, "monotonic", return_value=100.0):
                self.assertEqual(catalog.discover_ado_commands([directory]), ("firstcmd",))
                second.write_text("program secondcmd\n", encoding="utf-8")
                # Repeated keystrokes in the same epoch reuse the bounded cache.
                self.assertEqual(catalog.discover_ado_commands([directory]), ("firstcmd",))

            with mock.patch.object(catalog.time, "monotonic", return_value=103.0):
                self.assertEqual(
                    catalog.discover_ado_commands([directory]),
                    ("firstcmd", "secondcmd"),
                )
                first.unlink()

            with mock.patch.object(catalog.time, "monotonic", return_value=106.0):
                self.assertEqual(catalog.discover_ado_commands([directory]), ("secondcmd",))

    def test_path_candidates_respect_context_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "panel.dta").touch()
            (root / "panel.csv").touch()
            (root / "plots").mkdir()
            candidates = catalog.path_candidates("p", [directory], extensions=(".dta",))
            self.assertEqual(
                [candidate.trigger for candidate in candidates],
                ["plots/", "panel.dta"],
            )


class BundledCatalogTests(unittest.TestCase):
    def test_catalog_metadata_and_modern_commands(self) -> None:
        payload = json.loads(catalog.CATALOG_PATH.read_text(encoding="utf-8"))
        commands = set(catalog.load_command_catalog())
        self.assertEqual(payload["stata"]["version"], "19.5")
        self.assertEqual(payload["stata"]["update_date"], "2026-08-12")
        self.assertIn("validated_builtin_or_dispatcher_commands", payload["sources"])
        self.assertNotIn("native_commands", payload["sources"])
        self.assertTrue(
            {
                "bma",
                "collect",
                "dtable",
                "etable",
                "frame",
                "hdidregress",
                "lateffects",
                "mediate",
                "xtswitchdid",
            }
            <= commands
        )
        self.assertTrue(
            {
                "about",
                "adopath",
                "cd",
                "decode",
                "di",
                "ereturn",
                "estat",
                "gettoken",
                "include",
                "inspect",
                "list",
                "move",
                "net",
                "outfile",
                "outsheet",
                "post",
                "postclose",
                "postfile",
                "predict",
                "putdocx",
                "pwd",
                "shell",
                "sreturn",
                "su",
                "sysdir",
                "tab",
                "tabulate",
                "testparm",
                "tostring",
                "twoway",
                "update",
                "view",
                "winexec",
                "xtdidregress",
            }
            <= commands
        )
        self.assertTrue(
            {
                "ac",
                "acprplot",
                "avplot",
                "avplots",
                "brr",
                "checksum",
                "cii",
                "cls",
                "cmdlog",
                "class",
                "constraint",
                "correlate",
                "cprplot",
                "creturn",
                "doedit",
                "error",
                "filefilter",
                "fvexpand",
                "fvrevar",
                "gladder",
                "h2o",
                "hettest",
                "hexdump",
                "hotelling",
                "java",
                "javacall",
                "ktau",
                "log",
                "lvr2plot",
                "memory",
                "markin",
                "markout",
                "mat_capp",
                "mat_order",
                "mat_rapp",
                "median",
                "mleval",
                "mlmatsum",
                "mlsum",
                "mlvecsum",
                "nobreak",
                "novarabbrev",
                "numlist",
                "odbc",
                "oneway",
                "pac",
                "pnorm",
                "printer",
                "pwcorr",
                "putpdf",
                "qnorm",
                "qqplot",
                "query",
                "rm",
                "rvfplot",
                "rvpplot",
                "snapshot",
                "serset",
                "symplot",
                "tab1",
                "tab2",
                "tabdisp",
                "timer",
                "translate",
                "tsrevar",
                "unabcmd",
                "varabbrev",
                "xshell",
            }
            <= commands
        )
        self.assertTrue(
            {
                "ac_7",
                "acprplot_7",
                "absorb_variable_table",
                "checkdlgfiles",
                "checkhlpfiles",
                "cscript_log",
                "disp_res",
                "dtaversion",
                "gphpen",
                "import_delimited",
                "import_excel",
                "import_parquet",
                "mgarch_ccc",
                "ml_score",
                "regress_p",
                "twoway__function_gen",
            }
            .isdisjoint(commands)
        )


if __name__ == "__main__":
    unittest.main()
