"""Regression suite for Fernery.

Two layers:

* validator / helper unit tests that import ``fernery`` directly, and
* end-to-end tests that run the real CLI in a throwaway working directory and
  assert on stdout, stderr and the exit code, which is the contract the plan
  promises to scripts.

Run with either ``python -m unittest discover -s tests`` or ``pytest``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FERNERY = REPO_ROOT / "fernery.py"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import fernery  # noqa: E402  (path is set up above)

ALL_STAGES = ["tight", "crook", "partly", "unfurled", "flat"]
ALL_COLORS = ["white", "cream", "yellow", "green", "brown", "purple", "black", "rust"]


class ValidatorTests(unittest.TestCase):
    """The shared validators keep rejection wording identical everywhere."""

    def test_valid_dates_are_accepted(self):
        for value in ("2026-01-01", "1999-12-31", "2024-02-29"):
            with self.subTest(value=value):
                self.assertEqual(fernery.validate_iso_date(value), value)

    def test_impossible_and_malformed_dates_are_rejected(self):
        for value in ("2026-02-30", "2026-13-01", "2026-00-10", "20260101", "26-01-01", "2026/01/01", ""):
            with self.subTest(value=value):
                with self.assertRaises(fernery.ValidationError) as caught:
                    fernery.validate_iso_date(value)
                self.assertIn("must be a real calendar date written as YYYY-MM-DD", str(caught.exception))

    def test_every_stage_is_accepted(self):
        for stage in ALL_STAGES:
            with self.subTest(stage=stage):
                self.assertEqual(fernery.validate_choice(stage, fernery.STAGES, "stage"), stage)

    def test_stage_rejection_names_all_five_stages(self):
        with self.assertRaises(fernery.ValidationError) as caught:
            fernery.validate_choice("bogus", fernery.STAGES, "stage")
        message = str(caught.exception)
        self.assertIn("'bogus'", message)
        for stage in ALL_STAGES:
            self.assertIn(stage, message)

    def test_every_colour_is_accepted(self):
        for colour in ALL_COLORS:
            with self.subTest(colour=colour):
                self.assertEqual(fernery.validate_choice(colour, fernery.COLORS, "color"), colour)

    def test_colour_rejection_names_all_eight_colours(self):
        with self.assertRaises(fernery.ValidationError) as caught:
            fernery.validate_choice("teal", fernery.COLORS, "color")
        message = str(caught.exception)
        self.assertIn("'teal'", message)
        for colour in ALL_COLORS:
            self.assertIn(colour, message)

    def test_case_sensitive_stage_and_colour_tokens(self):
        for value in ("Crook", "CROOK", "Unfurled"):
            with self.subTest(value=value):
                with self.assertRaises(fernery.ValidationError):
                    fernery.validate_choice(value, fernery.STAGES, "stage")
        with self.assertRaises(fernery.ValidationError):
            fernery.validate_choice("Brown", fernery.COLORS, "color")

    def test_divisions_accepts_positive_whole_numbers(self):
        for value in ("1", "2", "17", "1000"):
            with self.subTest(value=value):
                self.assertEqual(fernery.validate_divisions(value), int(value))

    def test_divisions_rejects_zero_negative_and_text(self):
        for value in ("0", "-1", "-42", "abc", "", "2.5", "1 2"):
            with self.subTest(value=value):
                with self.assertRaises(fernery.ValidationError) as caught:
                    fernery.validate_divisions(value)
                self.assertIn(
                    "divisions must be a positive whole number (1 or more)",
                    str(caught.exception),
                )

    def test_required_text_rejects_blank_and_trims(self):
        for value in ("", "   ", "\t", None):
            with self.subTest(value=value):
                with self.assertRaises(fernery.ValidationError) as caught:
                    fernery.validate_required_text(value, "species")
                self.assertIn("species is required", str(caught.exception))
        self.assertEqual(fernery.validate_required_text("  Bird's Nest  ", "plant"), "Bird's Nest")

    def test_notes_default_to_empty_string(self):
        self.assertEqual(fernery.clean_notes(None), "")
        self.assertEqual(fernery.clean_notes("kept  exactly "), "kept  exactly ")

    def test_newest_first_sorts_by_date_then_insertion_order(self):
        entries = [
            {"id": 1, "date": "2026-01-01"},
            {"id": 2, "date": "2026-02-01"},
            {"id": 3, "date": "2026-01-01"},
        ]
        self.assertEqual([entry["id"] for entry in fernery.newest_first(entries)], [2, 3, 1])

    def test_truncate_shortens_with_an_ellipsis(self):
        self.assertEqual(fernery.truncate("abc", 5), "abc")
        self.assertEqual(fernery.truncate("abcdefgh", 5), "abcd\u2026")
        self.assertEqual(len(fernery.truncate("x" * 300, 20)), 20)

    def test_next_id_ignores_missing_and_non_integer_ids(self):
        self.assertEqual(fernery.next_id([]), 1)
        self.assertEqual(fernery.next_id([{"id": 4}, {"id": "7"}, {}, {"id": None}]), 5)


class CliTestCase(unittest.TestCase):
    """End-to-end contract: stdout, stderr and exit codes of the real command."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workdir = Path(self._tmp.name)

    # -- helpers ----------------------------------------------------------

    def run_cli(self, *args, expect=None):
        env = dict(os.environ)
        env["NO_COLOR"] = "1"
        result = subprocess.run(
            [sys.executable, str(FERNERY), *args],
            cwd=str(self.workdir),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        if expect is not None:
            self.assertEqual(
                result.returncode,
                expect,
                msg=f"args={args} stdout={result.stdout!r} stderr={result.stderr!r}",
            )
        return result

    def store(self):
        return json.loads((self.workdir / "fernery.json").read_text(encoding="utf-8"))

    def add_frond(self, date, stage, notes=None):
        args = ["frond", "add", "--date", date, "--stage", stage]
        if notes is not None:
            args += ["--notes", notes]
        return self.run_cli(*args, expect=0)

    # -- help and version -------------------------------------------------

    def test_help_lists_every_command_group_and_action(self):
        result = self.run_cli("--help", expect=0)
        for token in ("frond", "spore", "rhizome", "add", "list"):
            self.assertIn(token, result.stdout)
        self.assertEqual(result.stderr, "")

    def test_version(self):
        result = self.run_cli("--version", expect=0)
        self.assertIn("fernery", result.stdout)

    def test_subcommand_help_is_available(self):
        self.assertIn("frond", self.run_cli("frond", "--help", expect=0).stdout)
        self.assertIn("--divisions", self.run_cli("rhizome", "add", "--help", expect=0).stdout)
        self.assertIn("--color", self.run_cli("spore", "add", "--help", expect=0).stdout)

    def test_bare_invocation_prints_usage_and_succeeds(self):
        result = self.run_cli(expect=0)
        self.assertIn("COMMAND", result.stdout)

    def test_missing_required_option_is_a_usage_error(self):
        result = self.run_cli("frond", "add", "--date", "2026-01-01", expect=2)
        self.assertTrue(result.stderr.strip().splitlines()[-1].startswith("fernery: error: "))

    def test_unknown_command_is_a_usage_error(self):
        self.run_cli("compost", "list", expect=2)

    # -- frond ------------------------------------------------------------

    def test_frond_add_confirms_and_writes_the_store(self):
        result = self.run_cli(
            "frond", "add", "--date", "2026-01-01", "--stage", "crook",
            "--notes", "first crook of spring",
            expect=0,
        )
        self.assertIn("2026-01-01", result.stdout)
        self.assertIn("crook", result.stdout)
        self.assertTrue((self.workdir / "fernery.json").exists())
        store = self.store()
        self.assertEqual(store["fronds"][0]["notes"], "first crook of spring")
        self.assertEqual(store["fronds"][0]["stage"], "crook")

    def test_frond_list_prints_date_stage_and_notes(self):
        self.add_frond("2026-01-01", "crook", "first crook of spring")
        result = self.run_cli("frond", "list", expect=0)
        line = next(
            row for row in result.stdout.splitlines() if "2026-01-01" in row
        )
        self.assertIn("crook", line)
        self.assertIn("first crook of spring", line)

    def test_all_five_stages_render_in_the_log(self):
        for index, stage in enumerate(ALL_STAGES):
            self.add_frond(f"2026-01-0{index + 1}", stage)
        result = self.run_cli("frond", "list", expect=0)
        for stage in ALL_STAGES:
            self.assertIn(stage, result.stdout)

    def test_frond_empty_state_names_the_add_command(self):
        result = self.run_cli("frond", "list", expect=0)
        self.assertIn("No fronds recorded yet.", result.stdout)
        self.assertIn("fernery frond add", result.stdout)

    def test_frond_notes_default_to_empty_string_in_the_store(self):
        self.add_frond("2026-01-01", "tight")
        self.assertEqual(self.store()["fronds"][0]["notes"], "")

    def test_rejected_stage_names_all_five_stages(self):
        result = self.run_cli("frond", "add", "--date", "2026-01-01", "--stage", "bogus", expect=2)
        self.assertIn("bogus", result.stderr)
        for stage in ALL_STAGES:
            self.assertIn(stage, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_frond_rejects_impossible_date(self):
        result = self.run_cli("frond", "add", "--date", "2026-02-30", "--stage", "crook", expect=2)
        self.assertIn("must be a real calendar date written as YYYY-MM-DD", result.stderr)

    # -- spore ------------------------------------------------------------

    def test_spore_add_confirms_and_lists(self):
        result = self.run_cli(
            "spore", "add", "--species", "Amanita muscaria", "--date", "2026-01-01",
            "--color", "brown", expect=0,
        )
        self.assertIn("Amanita muscaria", result.stdout)
        listing = self.run_cli("spore", "list", expect=0)
        self.assertIn("Amanita muscaria", listing.stdout)
        self.assertIn("2026-01-01", listing.stdout)

    def test_spore_notes_are_persisted_and_printed(self):
        self.run_cli(
            "spore", "add", "--species", "Amanita", "--date", "2026-01-01",
            "--color", "brown", "--notes", "print off white gills", expect=0,
        )
        self.assertEqual(self.store()["spores"][0]["notes"], "print off white gills")
        self.assertIn("print off white gills", self.run_cli("spore", "list", expect=0).stdout)

    def test_all_eight_colours_render_in_the_index(self):
        for index, colour in enumerate(ALL_COLORS):
            self.run_cli(
                "spore", "add", "--species", f"Species {index}", "--date", "2026-01-01",
                "--color", colour, expect=0,
            )
        listing = self.run_cli("spore", "list", expect=0).stdout
        for colour in ALL_COLORS:
            self.assertIn(colour, listing)

    def test_spore_rejected_colour_names_all_eight(self):
        result = self.run_cli(
            "spore", "add", "--species", "Amanita", "--date", "2026-01-01", "--color", "teal",
            expect=2,
        )
        for colour in ALL_COLORS:
            self.assertIn(colour, result.stderr)
        self.assertIn("teal", result.stderr)

    def test_spore_rejects_impossible_date(self):
        result = self.run_cli(
            "spore", "add", "--species", "Amanita", "--date", "2026-13-01", "--color", "brown",
            expect=2,
        )
        self.assertIn("must be a real calendar date written as YYYY-MM-DD", result.stderr)

    def test_spore_requires_a_non_blank_species(self):
        blank = self.run_cli(
            "spore", "add", "--species", "   ", "--date", "2026-01-01", "--color", "brown",
            expect=2,
        )
        self.assertIn("species is required", blank.stderr)
        omitted = self.run_cli(
            "spore", "add", "--date", "2026-01-01", "--color", "brown", expect=2
        )
        self.assertIn("--species", omitted.stderr)

    def test_spore_empty_state(self):
        result = self.run_cli("spore", "list", expect=0)
        self.assertIn("No spore prints indexed yet.", result.stdout)
        self.assertIn("fernery spore add", result.stdout)

    # -- rhizome ----------------------------------------------------------

    def test_rhizome_add_confirms_and_lists(self):
        result = self.run_cli(
            "rhizome", "add", "--plant", "A", "--date", "2026-01-01", "--divisions", "2", expect=0
        )
        self.assertIn("A", result.stdout)
        self.assertIn("2 divisions", result.stdout)
        listing = self.run_cli("rhizome", "list", expect=0)
        self.assertIn("2026-01-01", listing.stdout)
        self.assertIn("2", listing.stdout)

    def test_rhizome_notes_persisted(self):
        self.run_cli(
            "rhizome", "add", "--plant", "A", "--date", "2026-01-01", "--divisions", "2",
            "--notes", "two eyes, healthy", expect=0,
        )
        self.assertEqual(self.store()["rhizomes"][0]["notes"], "two eyes, healthy")
        self.assertIn("two eyes, healthy", self.run_cli("rhizome", "list", expect=0).stdout)

    def test_rhizome_plant_filter_excludes_other_plants(self):
        self.run_cli("rhizome", "add", "--plant", "A", "--date", "2026-01-01", "--divisions", "2", expect=0)
        self.run_cli("rhizome", "add", "--plant", "B", "--date", "2026-01-02", "--divisions", "1", expect=0)
        listing = self.run_cli("rhizome", "list", "--plant", "A", expect=0)
        self.assertIn("2026-01-01", listing.stdout)
        self.assertNotIn("2026-01-02", listing.stdout)

    def test_rhizome_filter_empty_state_names_the_plant(self):
        self.run_cli("rhizome", "add", "--plant", "A", "--date", "2026-01-01", "--divisions", "2", expect=0)
        result = self.run_cli("rhizome", "list", "--plant", "C", expect=0)
        self.assertIn("No divisions recorded for plant C yet.", result.stdout)
        self.assertIn("fernery rhizome add", result.stdout)

    def test_rhizome_rejects_zero_negative_and_text_counts(self):
        for value in ("0", "-1", "abc"):
            with self.subTest(value=value):
                result = self.run_cli(
                    "rhizome", "add", "--plant", "A", "--date", "2026-01-01",
                    "--divisions", value, expect=2,
                )
                self.assertIn(
                    "divisions must be a positive whole number (1 or more)", result.stderr
                )
        self.assertFalse((self.workdir / "fernery.json").exists())

    def test_rhizome_requires_a_non_blank_plant(self):
        result = self.run_cli(
            "rhizome", "add", "--plant", "  ", "--date", "2026-01-01", "--divisions", "1", expect=2
        )
        self.assertIn("plant is required", result.stderr)

    def test_rhizome_rejects_impossible_date(self):
        result = self.run_cli(
            "rhizome", "add", "--plant", "A", "--date", "2026-02-30", "--divisions", "1", expect=2
        )
        self.assertIn("must be a real calendar date written as YYYY-MM-DD", result.stderr)

    def test_rhizome_empty_state(self):
        result = self.run_cli("rhizome", "list", expect=0)
        self.assertIn("No rhizome divisions logged yet.", result.stdout)
        self.assertIn("fernery rhizome add", result.stdout)

    # -- ordering ---------------------------------------------------------

    def test_frond_list_is_newest_first(self):
        self.add_frond("2026-01-01", "tight")
        self.add_frond("2026-02-01", "flat")
        lines = [line for line in self.run_cli("frond", "list", expect=0).stdout.splitlines() if "2026-" in line]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("2026-02-01"))

    def test_spore_list_is_newest_first(self):
        self.run_cli("spore", "add", "--species", "Old", "--date", "2026-01-01", "--color", "brown", expect=0)
        self.run_cli("spore", "add", "--species", "New", "--date", "2026-02-01", "--color", "rust", expect=0)
        lines = [line for line in self.run_cli("spore", "list", expect=0).stdout.splitlines() if "2026-" in line]
        self.assertTrue(lines[0].startswith("New "))

    def test_rhizome_list_is_newest_first(self):
        self.run_cli("rhizome", "add", "--plant", "A", "--date", "2026-01-01", "--divisions", "1", expect=0)
        self.run_cli("rhizome", "add", "--plant", "A", "--date", "2026-02-01", "--divisions", "3", expect=0)
        lines = [line for line in self.run_cli("rhizome", "list", expect=0).stdout.splitlines() if "2026-" in line]
        self.assertTrue(lines[0].startswith("A "))
        self.assertTrue(lines[0].rstrip().endswith("3") or "  3 " in lines[0])

    def test_same_date_falls_back_to_insertion_order(self):
        self.add_frond("2026-01-01", "tight", "added first")
        self.add_frond("2026-01-01", "flat", "added second")
        listing = self.run_cli("frond", "list", expect=0).stdout
        self.assertLess(listing.index("added second"), listing.index("added first"))

    def test_repeated_list_runs_print_identical_text(self):
        self.add_frond("2026-01-01", "tight", "one")
        self.add_frond("2026-01-01", "flat", "two")
        self.add_frond("2026-02-01", "crook", "three")
        first = self.run_cli("frond", "list", expect=0).stdout
        second = self.run_cli("frond", "list", expect=0).stdout
        self.assertEqual(first, second)

    # -- output polish ----------------------------------------------------

    def test_long_note_is_shortened_to_fit_the_columns(self):
        self.add_frond("2026-01-01", "unfurled", "x" * 300)
        lines = self.run_cli("frond", "list", expect=0).stdout.splitlines()
        row = next(line for line in lines if line.startswith("2026-01-01"))
        self.assertLessEqual(len(row), 100)
        self.assertTrue(row.endswith("\u2026"))

    def test_every_rejection_uses_the_same_prefix(self):
        rejections = [
            ("frond", "add", "--date", "2026-01-01", "--stage", "bogus"),
            ("frond", "add", "--date", "2026-02-30", "--stage", "tight"),
            ("spore", "add", "--species", "A", "--date", "2026-01-01", "--color", "teal"),
            ("spore", "add", "--species", " ", "--date", "2026-01-01", "--color", "brown"),
            ("rhizome", "add", "--plant", "A", "--date", "2026-01-01", "--divisions", "0"),
            ("rhizome", "add", "--plant", " ", "--date", "2026-01-01", "--divisions", "1"),
        ]
        for args in rejections:
            with self.subTest(args=args):
                result = self.run_cli(*args, expect=2)
                self.assertTrue(result.stderr.startswith("fernery: error: "), msg=result.stderr)

    def test_store_error_uses_the_same_prefix_and_exit_code(self):
        (self.workdir / "fernery.json").write_text("{ not json", encoding="utf-8")
        for args in (["frond", "list"], ["spore", "list"], ["rhizome", "list"]):
            with self.subTest(args=args):
                result = self.run_cli(*args, expect=3)
                self.assertTrue(result.stderr.startswith("fernery: error: "), msg=result.stderr)

    def test_json_output_is_machine_readable(self):
        self.add_frond("2026-01-01", "crook", "first crook of spring")
        self.add_frond("2026-02-01", "flat")
        payload = json.loads(self.run_cli("frond", "list", "--json", expect=0).stdout)
        self.assertEqual([entry["date"] for entry in payload], ["2026-02-01", "2026-01-01"])

    # -- store handling ---------------------------------------------------

    def test_corrupt_store_is_reported_without_a_traceback(self):
        (self.workdir / "fernery.json").write_text("{ not json", encoding="utf-8")
        result = self.run_cli("frond", "list", expect=3)
        self.assertIn("fernery.json could not be read", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_corrupt_store_blocks_writes_so_entries_are_never_lost(self):
        (self.workdir / "fernery.json").write_text("{ not json", encoding="utf-8")
        result = self.run_cli("frond", "add", "--date", "2026-01-01", "--stage", "tight", expect=3)
        self.assertIn("fernery.json could not be read", result.stderr)
        self.assertEqual((self.workdir / "fernery.json").read_text(encoding="utf-8"), "{ not json")

    def test_store_shape_and_atomic_write(self):
        self.add_frond("2026-01-01", "tight")
        store = self.store()
        self.assertEqual(store["schema_version"], 1)
        self.assertEqual(set(store), {"schema_version", "fronds", "spores", "rhizomes"})
        leftovers = [path.name for path in self.workdir.iterdir() if path.name.startswith(".fernery-")]
        self.assertEqual(leftovers, [])

    def test_add_creates_the_store_on_first_use(self):
        self.assertFalse((self.workdir / "fernery.json").exists())
        self.add_frond("2026-01-01", "tight")
        self.assertTrue((self.workdir / "fernery.json").exists())

    def test_store_is_written_as_utf8_json_with_readable_notes(self):
        self.run_cli(
            "spore", "add", "--species", "Dryopteris filix-mas", "--date", "2026-01-01",
            "--color", "brown", "--notes", "spores shed on white paper \u2014 print holds", expect=0,
        )
        raw = (self.workdir / "fernery.json").read_text(encoding="utf-8")
        self.assertIn("\u2014", raw)
        self.assertIn("Dryopteris filix-mas", self.run_cli("spore", "list", expect=0).stdout)


if __name__ == "__main__":
    unittest.main()
