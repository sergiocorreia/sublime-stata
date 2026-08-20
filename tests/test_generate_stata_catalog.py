from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from misc import generate_stata_catalog as generator


class CatalogGeneratorTests(unittest.TestCase):
    def make_install(self, root: Path) -> None:
        base = root / "ado" / "base"
        updates = root / "ado" / "updates"
        base.mkdir(parents=True)
        updates.mkdir(parents=True)
        (root / "isstata.195").touch()
        (base / "update").write_text("12 Aug 2026\n", encoding="ascii")

        (base / "documented.ado").write_text(
            "*! public command\nprogram define documented\nend\n", encoding="utf-8"
        )
        (base / "documented.sthlp").write_text("{title:documented}\n", encoding="utf-8")
        (base / "sharedcmd.ado").write_text(
            "program define sharedcmd\nend\n", encoding="utf-8"
        )
        (base / "parent.sthlp").write_text(
            "{title:parent}\n{cmd:sharedcmd} [{cmd:,} {it:options}]\n",
            encoding="utf-8",
        )
        (base / "shelp_alias.maint").write_text(
            "sharedcmd parent\n", encoding="utf-8"
        )
        (base / "model_p.ado").write_text("program model_p\n", encoding="utf-8")
        (base / "model_p.sthlp").write_text("{title:helper}\n", encoding="utf-8")
        for helper in ("model_predict", "model_likelihood", "model_dialog", "model_estat_gof"):
            (base / (helper + ".ado")).write_text(
                "program " + helper + "\n", encoding="utf-8"
            )
            (base / (helper + ".sthlp")).write_text("{title:helper}\n", encoding="utf-8")
        (base / "undocumented.ado").write_text("program undocumented\n", encoding="utf-8")
        for private in ("cscript_log", "disp_res", "twoway__function_gen"):
            (base / (private + ".ado")).write_text(
                "program " + private + "\n", encoding="utf-8"
            )
            (base / (private + ".sthlp")).write_text("{title:technical}\n", encoding="utf-8")

        (updates / "updatedcmd.ado").write_text(
            "program updatedcmd\nend\n", encoding="utf-8"
        )
        (updates / "updatedcmd.sthlp").write_text("{title:updated}\n", encoding="utf-8")

    def test_builds_reproducible_public_catalog_from_base_and_updates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_install(root)
            payload = generator.build_catalog(root)
            commands = set(payload["commands"])

            self.assertEqual(payload["stata"]["version"], "19.5")
            self.assertEqual(payload["stata"]["update_date"], "2026-08-12")
            self.assertTrue(payload["sources"]["scanned_updates"])
            self.assertIn("documented", commands)
            self.assertIn("sharedcmd", commands)
            self.assertIn("updatedcmd", commands)
            self.assertIn("lateffects", commands)
            self.assertTrue(
                {
                    "about",
                    "adopath",
                    "cd",
                    "estat",
                    "net",
                    "predict",
                    "pwd",
                    "save",
                    "shell",
                    "su",
                    "tab",
                    "tabulate",
                    "twoway",
                    "update",
                    "xtdidregress",
                }
                <= commands
            )
            self.assertNotIn("model_p", commands)
            self.assertTrue(
                {"model_predict", "model_likelihood", "model_dialog", "model_estat_gof"}
                .isdisjoint(commands)
            )
            self.assertNotIn("undocumented", commands)
            self.assertTrue(
                {"cscript_log", "disp_res", "twoway__function_gen"}.isdisjoint(commands)
            )
            self.assertEqual(
                generator.rendered_catalog(payload),
                generator.rendered_catalog(generator.build_catalog(root)),
            )

    def test_first_program_ignores_leading_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.ado"
            path.write_text(
                "*! version 1.0\n\nprog defin Example, rclass\nend\n",
                encoding="utf-8",
            )
            self.assertEqual(generator.first_program(path), "example")


if __name__ == "__main__":
    unittest.main()
