#!/usr/bin/env python3
"""Fernery - one offline log for three fern-keeping habits.

Fernery keeps three append-only logs in a single human-readable JSON file
(``fernery.json`` in the current working directory):

* a frond unfurling tracker (tight, crook, partly, unfurled, flat),
* a spore print index (eight print colours), and
* a rhizome division log (per-plant division counts).

Standard library only. Run ``fernery --help`` for the command surface.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, NoReturn, Sequence

__version__ = "1.0.0"

STORE_NAME = "fernery.json"
SCHEMA_VERSION = 1

STAGES: tuple[str, ...] = ("tight", "crook", "partly", "unfurled", "flat")
COLORS: tuple[str, ...] = ("white", "cream", "yellow", "green", "brown", "purple", "black", "rust")

FROND_KEY = "fronds"
SPORE_KEY = "spores"
RHIZOME_KEY = "rhizomes"
COLLECTIONS: tuple[str, ...] = (FROND_KEY, SPORE_KEY, RHIZOME_KEY)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_STORE = 3

ERROR_PREFIX = "fernery: error: "
DATE_FORMAT = "YYYY-MM-DD"
LINE_WIDTH = 100
ELLIPSIS = "\u2026"
RULE_CHAR = "\u2500"
RULE_MAX = LINE_WIDTH - 4  # keep the rule just inside the column budget

ACCENT_RGB = (181, 94, 66)  # #b55e42 - the committed Fernery accent, in truecolor
DIM_RGB = (138, 138, 138)

# Column widths per list. Each table's total (widths + 2-space gutters) stays
# under LINE_WIDTH so a long note can never break the layout.
FROND_COLUMNS: tuple[tuple[str, int], ...] = (("DATE", 10), ("STAGE", 9), ("NOTES", 72))
SPORE_COLUMNS: tuple[tuple[str, int], ...] = (
    ("SPECIES", 26),
    ("COLOR", 8),
    ("DATE", 10),
    ("NOTES", 46),
)
RHIZOME_COLUMNS: tuple[tuple[str, int], ...] = (
    ("PLANT", 26),
    ("DATE", 10),
    ("DIVISIONS", 9),
    ("NOTES", 44),
)

EXAMPLE_FROND_DATE = "2026-01-01"


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class FerneryError(Exception):
    """Base class for problems Fernery reports as one line, never a traceback."""


class ValidationError(FerneryError):
    """A value supplied on the command line was rejected."""


class StoreError(FerneryError):
    """fernery.json could not be read or written."""


# --------------------------------------------------------------------------
# Terminal styling (single accent, never the only signal)
# --------------------------------------------------------------------------


def use_color(stream: Any, no_color: bool) -> bool:
    """Colour only on a real terminal, and never when the user opts out."""
    if no_color or os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def paint(text: str, rgb: tuple[int, int, int], enabled: bool) -> str:
    if not enabled or not text:
        return text
    red, green, blue = rgb
    return f"\x1b[38;2;{red};{green};{blue}m{text}\x1b[0m"


def accent(text: str, enabled: bool) -> str:
    return paint(text, ACCENT_RGB, enabled)


def dim(text: str, enabled: bool) -> str:
    return paint(text, DIM_RGB, enabled)


# --------------------------------------------------------------------------
# Validators
# --------------------------------------------------------------------------


def validate_iso_date(value: str) -> str:
    """Accept a real calendar date written exactly YYYY-MM-DD."""
    problem = ValidationError(
        f"date must be a real calendar date written as {DATE_FORMAT} (got {value!r})"
    )
    if not isinstance(value, str):
        raise problem
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError:
        raise problem from None
    if parsed.isoformat() != value:
        # Rejects ISO variants such as 20260101 or 2026-W01-1.
        raise problem
    return value


def validate_choice(value: str, allowed: Sequence[str], label: str) -> str:
    """Accept only one of the listed lowercase tokens, naming the full set."""
    if value not in allowed:
        raise ValidationError(
            f"{label} must be one of: {', '.join(allowed)} (got {value!r})"
        )
    return value


def validate_required_text(value: str | None, label: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required and must not be blank")
    return text


def validate_divisions(value: str) -> int:
    """Accept a positive whole number; reject 0, negatives and non-numbers."""
    message = f"divisions must be a positive whole number (1 or more): got {value!r}"
    try:
        number = int(str(value).strip(), 10)
    except (TypeError, ValueError):
        raise ValidationError(message) from None
    if number < 1:
        raise ValidationError(message)
    return number


def clean_notes(value: str | None) -> str:
    """Notes are optional on every tracker and default to the empty string."""
    if value is None:
        return ""
    return value


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------


def new_store() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        FROND_KEY: [],
        SPORE_KEY: [],
        RHIZOME_KEY: [],
    }


def load_store(path: Path) -> dict[str, Any]:
    """Read fernery.json, or return an empty store when it does not exist yet."""
    if not path.exists():
        return new_store()
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise StoreError(f"{STORE_NAME} could not be read (the file is not valid UTF-8)") from exc
    except OSError as exc:
        reason = exc.strerror or exc.__class__.__name__
        raise StoreError(f"{STORE_NAME} could not be read ({reason})") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StoreError(
            f"{STORE_NAME} could not be read (not valid JSON: line {exc.lineno}, column {exc.colno})"
        ) from exc

    if not isinstance(data, dict):
        raise StoreError(f"{STORE_NAME} could not be read (expected a JSON object at the top level)")

    store = new_store()
    version = data.get("schema_version")
    if isinstance(version, int) and not isinstance(version, bool):
        store["schema_version"] = version
    for key in COLLECTIONS:
        entries = data.get(key)
        if entries is None:
            entries = []
        if not isinstance(entries, list):
            raise StoreError(f"{STORE_NAME} could not be read (the {key!r} collection is not a list)")
        if any(not isinstance(entry, dict) for entry in entries):
            raise StoreError(
                f"{STORE_NAME} could not be read (every entry in {key!r} must be a JSON object)"
            )
        store[key] = list(entries)
    return store


def save_store(path: Path, store: dict[str, Any]) -> None:
    """Write fernery.json atomically: temp file in the same directory, then replace."""
    store["schema_version"] = SCHEMA_VERSION
    try:
        payload = json.dumps(store, ensure_ascii=False, indent=2) + "\n"
    except (TypeError, ValueError) as exc:
        raise StoreError(
            f"{STORE_NAME} could not be written (the log holds a value that is not JSON serialisable)"
        ) from exc

    temp_name: str | None = None
    try:
        directory = path.parent if str(path.parent) else Path(".")
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(directory),
            prefix=".fernery-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        reason = exc.strerror or exc.__class__.__name__
        raise StoreError(f"{STORE_NAME} could not be written ({reason})") from exc


def next_id(entries: Sequence[dict[str, Any]]) -> int:
    highest = 0
    for entry in entries:
        value = entry.get("id")
        if isinstance(value, int) and not isinstance(value, bool) and value > highest:
            highest = value
    return highest + 1


# --------------------------------------------------------------------------
# Entry helpers (defensive: a hand-edited store must never crash a list)
# --------------------------------------------------------------------------


def text_field(entry: dict[str, Any], key: str, default: str = "") -> str:
    value = entry.get(key, default)
    return value if isinstance(value, str) else default


def int_field(entry: dict[str, Any], key: str, default: int = 0) -> int:
    value = entry.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def newest_first(entries: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by date descending, ties broken by insertion order (highest id first)."""
    return sorted(
        entries,
        key=lambda entry: (text_field(entry, "date"), int_field(entry, "id")),
        reverse=True,
    )


def count_phrase(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


# --------------------------------------------------------------------------
# Column rendering
# --------------------------------------------------------------------------


def flatten(text: str) -> str:
    """One entry per line: collapse newlines and tabs so columns stay aligned."""
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()


def truncate(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return ELLIPSIS
    return text[: width - 1] + ELLIPSIS


def format_row(cells: Sequence[str], columns: Sequence[tuple[str, int]]) -> str:
    last = len(columns) - 1
    parts: list[str] = []
    for index, (cell, (_, width)) in enumerate(zip(cells, columns)):
        text = truncate(flatten(cell), width)
        parts.append(text if index == last else text.ljust(width))
    return "  ".join(parts).rstrip()


def table_rule(columns: Sequence[tuple[str, int]]) -> str:
    total = sum(width for _, width in columns) + 2 * (len(columns) - 1)
    return RULE_CHAR * min(total, RULE_MAX)


def render_table(
    columns: Sequence[tuple[str, int]],
    rows: Sequence[Sequence[str]],
    color: bool,
) -> list[str]:
    lines = [
        dim(format_row([name for name, _ in columns], columns), color),
        dim(table_rule(columns), color),
    ]
    lines.extend(format_row(row, columns) for row in rows)
    return lines


# --------------------------------------------------------------------------
# Command-line parsing
# --------------------------------------------------------------------------


class FerneryArgumentParser(argparse.ArgumentParser):
    """argparse, but every error line carries Fernery's one error prefix."""

    def error(self, message: str) -> NoReturn:  # noqa: D102 - argparse hook
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{ERROR_PREFIX}{message}\n")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS,
        help="never colour the output (also honours the NO_COLOR environment variable)",
    )

    parser = FerneryArgumentParser(
        prog="fernery",
        parents=[common],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Fernery keeps three plant logs in one plain JSON file, fernery.json, in the\n"
            "current directory: a frond unfurling tracker, a spore print index and a\n"
            "rhizome division log. It works fully offline and never touches the network."
        ),
        epilog=(
            "examples:\n"
            "  fernery frond add --date 2026-01-01 --stage crook --notes \"first crook of spring\"\n"
            "  fernery frond list\n"
            "  fernery spore add --species \"Amanita muscaria\" --date 2026-01-01 --color brown\n"
            "  fernery spore list\n"
            "  fernery rhizome add --plant \"Bird's Nest\" --date 2026-01-01 --divisions 2\n"
            "  fernery rhizome list --plant \"Bird's Nest\"\n"
            "\n"
            "exit codes: 0 success, 2 usage or validation error, 3 fernery.json unreadable."
        ),
    )
    parser.add_argument("--version", action="version", version=f"fernery {__version__}")

    commands = parser.add_subparsers(dest="command", metavar="COMMAND", title="commands")

    frond = commands.add_parser(
        "frond",
        parents=[common],
        help="frond unfurling tracker",
        description="Track each frond through the five unfurling stages.",
    )
    frond_actions = frond.add_subparsers(dest="action", metavar="ACTION")
    frond_add = frond_actions.add_parser(
        "add",
        parents=[common],
        help="record one unfurling observation",
        description="Record one frond observation.",
    )
    frond_add.add_argument("--date", required=True, metavar="YYYY-MM-DD", help="date observed")
    frond_add.add_argument(
        "--stage",
        required=True,
        metavar="STAGE",
        help=f"one of: {', '.join(STAGES)}",
    )
    frond_add.add_argument("--notes", default=None, help="free-text note (optional)")
    frond_add.set_defaults(handler=handle_frond_add)

    frond_list = frond_actions.add_parser(
        "list",
        parents=[common],
        help="print the frond log, newest first",
        description="Print every frond observation, newest first.",
    )
    frond_list.add_argument("--json", action="store_true", help="emit the log as JSON")
    frond_list.set_defaults(handler=handle_frond_list)

    spore = commands.add_parser(
        "spore",
        parents=[common],
        help="spore print index",
        description="Index spore prints by species, date and print colour.",
    )
    spore_actions = spore.add_subparsers(dest="action", metavar="ACTION")
    spore_add = spore_actions.add_parser(
        "add",
        parents=[common],
        help="index one spore print",
        description="Index one spore print.",
    )
    spore_add.add_argument("--species", required=True, metavar="NAME", help="species the print came from")
    spore_add.add_argument("--date", required=True, metavar="YYYY-MM-DD", help="date the print was taken")
    spore_add.add_argument(
        "--color",
        required=True,
        metavar="COLOR",
        help=f"one of: {', '.join(COLORS)}",
    )
    spore_add.add_argument("--notes", default=None, help="free-text note (optional)")
    spore_add.set_defaults(handler=handle_spore_add)

    spore_list = spore_actions.add_parser(
        "list",
        parents=[common],
        help="print the spore print index, newest first",
        description="Print the spore print index, newest first.",
    )
    spore_list.add_argument("--json", action="store_true", help="emit the index as JSON")
    spore_list.set_defaults(handler=handle_spore_list)

    rhizome = commands.add_parser(
        "rhizome",
        parents=[common],
        help="rhizome division log",
        description="Log how many rhizome divisions were taken from a plant, per plant.",
    )
    rhizome_actions = rhizome.add_subparsers(dest="action", metavar="ACTION")
    rhizome_add = rhizome_actions.add_parser(
        "add",
        parents=[common],
        help="log one division event",
        description="Log one rhizome division event.",
    )
    rhizome_add.add_argument("--plant", required=True, metavar="NAME", help="plant the divisions came from")
    rhizome_add.add_argument("--date", required=True, metavar="YYYY-MM-DD", help="date the divisions were taken")
    rhizome_add.add_argument("--divisions", required=True, metavar="N", help="how many divisions (1 or more)")
    rhizome_add.add_argument("--notes", default=None, help="free-text note (optional)")
    rhizome_add.set_defaults(handler=handle_rhizome_add)

    rhizome_list = rhizome_actions.add_parser(
        "list",
        parents=[common],
        help="print the division log, newest first",
        description="Print rhizome divisions, newest first, optionally for one plant.",
    )
    rhizome_list.add_argument("--plant", default=None, metavar="NAME", help="only show this plant")
    rhizome_list.add_argument("--json", action="store_true", help="emit the log as JSON")
    rhizome_list.set_defaults(handler=handle_rhizome_list)

    return parser


# --------------------------------------------------------------------------
# Small output helpers
# --------------------------------------------------------------------------


def store_path() -> Path:
    return Path(STORE_NAME)


def emit(line: str = "") -> None:
    print(line)


def quote_arg(value: str) -> str:
    """Quote a value so a printed example command can be pasted back in."""
    if value and all(ch.isalnum() or ch in "-_./," for ch in value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def empty_hint(headline: str, command: str, color: bool) -> None:
    emit(accent(headline, color))
    emit("Add the first one with:")
    emit(f"  {command}")


# --------------------------------------------------------------------------
# frond
# --------------------------------------------------------------------------


def handle_frond_add(args: argparse.Namespace) -> int:
    date = validate_iso_date(args.date)
    stage = validate_choice(args.stage, STAGES, "stage")
    notes = clean_notes(args.notes)

    store = load_store(store_path())
    entry = {"id": next_id(store[FROND_KEY]), "date": date, "stage": stage, "notes": notes}
    store[FROND_KEY].append(entry)
    save_store(store_path(), store)

    color = use_color(sys.stdout, getattr(args, "no_color", False))
    emit(accent(f"Saved frond observation: {date} {stage}", color))
    return EXIT_OK


def handle_frond_list(args: argparse.Namespace) -> int:
    store = load_store(store_path())
    entries = newest_first(store[FROND_KEY])

    if getattr(args, "json", False):
        emit(json.dumps(entries, ensure_ascii=False, indent=2))
        return EXIT_OK

    color = use_color(sys.stdout, getattr(args, "no_color", False))
    if not entries:
        empty_hint(
            "No fronds recorded yet.",
            f"fernery frond add --date {EXAMPLE_FROND_DATE} --stage tight "
            '--notes "first frond of the season"',
            color,
        )
        return EXIT_OK

    emit(accent(f"Frond unfurling log \u2014 {count_phrase(len(entries), 'observation', 'observations')}", color))
    rows = [
        [text_field(entry, "date"), text_field(entry, "stage"), text_field(entry, "notes")]
        for entry in entries
    ]
    for line in render_table(FROND_COLUMNS, rows, color):
        emit(line)
    return EXIT_OK


# --------------------------------------------------------------------------
# spore
# --------------------------------------------------------------------------


def handle_spore_add(args: argparse.Namespace) -> int:
    species = validate_required_text(args.species, "species")
    date = validate_iso_date(args.date)
    color_value = validate_choice(args.color, COLORS, "color")
    notes = clean_notes(args.notes)

    store = load_store(store_path())
    entry = {
        "id": next_id(store[SPORE_KEY]),
        "species": species,
        "date": date,
        "color": color_value,
        "notes": notes,
    }
    store[SPORE_KEY].append(entry)
    save_store(store_path(), store)

    color = use_color(sys.stdout, getattr(args, "no_color", False))
    emit(accent(f"Saved spore print: {species} ({color_value}) on {date}", color))
    return EXIT_OK


def handle_spore_list(args: argparse.Namespace) -> int:
    store = load_store(store_path())
    entries = newest_first(store[SPORE_KEY])

    if getattr(args, "json", False):
        emit(json.dumps(entries, ensure_ascii=False, indent=2))
        return EXIT_OK

    color = use_color(sys.stdout, getattr(args, "no_color", False))
    if not entries:
        empty_hint(
            "No spore prints indexed yet.",
            f"fernery spore add --species \"Amanita muscaria\" --date {EXAMPLE_FROND_DATE} --color brown",
            color,
        )
        return EXIT_OK

    emit(accent(f"Spore print index \u2014 {count_phrase(len(entries), 'print', 'prints')}", color))
    rows = [
        [
            text_field(entry, "species"),
            text_field(entry, "color"),
            text_field(entry, "date"),
            text_field(entry, "notes"),
        ]
        for entry in entries
    ]
    for line in render_table(SPORE_COLUMNS, rows, color):
        emit(line)
    return EXIT_OK


# --------------------------------------------------------------------------
# rhizome
# --------------------------------------------------------------------------


def handle_rhizome_add(args: argparse.Namespace) -> int:
    plant = validate_required_text(args.plant, "plant")
    date = validate_iso_date(args.date)
    divisions = validate_divisions(args.divisions)
    notes = clean_notes(args.notes)

    store = load_store(store_path())
    entry = {
        "id": next_id(store[RHIZOME_KEY]),
        "plant": plant,
        "date": date,
        "divisions": divisions,
        "notes": notes,
    }
    store[RHIZOME_KEY].append(entry)
    save_store(store_path(), store)

    color = use_color(sys.stdout, getattr(args, "no_color", False))
    emit(accent(f"Saved rhizome division: plant {plant}, {count_phrase(divisions, 'division', 'divisions')} on {date}", color))
    return EXIT_OK


def handle_rhizome_list(args: argparse.Namespace) -> int:
    store = load_store(store_path())
    plant = validate_required_text(args.plant, "plant") if args.plant is not None else None
    entries = newest_first(store[RHIZOME_KEY])
    if plant is not None:
        entries = [entry for entry in entries if text_field(entry, "plant") == plant]

    if getattr(args, "json", False):
        emit(json.dumps(entries, ensure_ascii=False, indent=2))
        return EXIT_OK

    color = use_color(sys.stdout, getattr(args, "no_color", False))
    if not entries:
        if plant is not None:
            emit(accent(f"No divisions recorded for plant {plant} yet.", color))
            emit("Log one with:")
            emit(
                f"  fernery rhizome add --plant {quote_arg(plant)} "
                f"--date {EXAMPLE_FROND_DATE} --divisions 1"
            )
        else:
            empty_hint(
                "No rhizome divisions logged yet.",
                f"fernery rhizome add --plant \"Bird's Nest\" --date {EXAMPLE_FROND_DATE} --divisions 2",
                color,
            )
        return EXIT_OK

    total = sum(int_field(entry, "divisions") for entry in entries)
    scope = f"plant {plant}" if plant is not None else "all plants"
    if len(entries) == 1:
        emit(accent(f"Rhizome division log \u2014 {scope}: 1 record, {total} divisions", color))
    else:
        emit(accent(f"Rhizome division log \u2014 {scope}: {len(entries)} records, {total} divisions", color))
    rows = [
        [
            text_field(entry, "plant"),
            text_field(entry, "date"),
            str(int_field(entry, "divisions")),
            text_field(entry, "notes"),
        ]
        for entry in entries
    ]
    for line in render_table(RHIZOME_COLUMNS, rows, color):
        emit(line)
    return EXIT_OK


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def report(message: str, args: argparse.Namespace, stream: Any) -> None:
    color = use_color(stream, getattr(args, "no_color", False))
    print(accent(f"{ERROR_PREFIX}{message}", color), file=stream)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Dispatch, printing help instead of an error when no action was given."""
    if not getattr(args, "command", None):
        parser.print_help(sys.stdout)
        return EXIT_OK
    if not getattr(args, "action", None):
        # parse_args([...]) prints that group's help and exits 0.
        parser.parse_args([args.command, "--help"])
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return run(args, parser)
    except ValidationError as exc:
        report(str(exc), args, sys.stderr)
        return EXIT_USAGE
    except StoreError as exc:
        report(str(exc), args, sys.stderr)
        return EXIT_STORE


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:  # pragma: no cover - interactive interrupt
        sys.exit(130)
    except BrokenPipeError:  # pragma: no cover - `fernery ... | head`
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(EXIT_OK)
