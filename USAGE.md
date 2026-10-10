# Using Fernery

Three logs, six commands, one JSON file. Everything below runs from a directory
of your choosing; `fernery.json` is written there on your first successful
`add`. If you did not run `install.sh`, replace `fernery` with `python3 fernery.py`.

## 1. Frond unfurling tracker

Record each frond as it moves through the five stages - `tight`, `crook`,
`partly`, `unfurled`, `flat`:

```console
$ fernery frond add --date 2026-01-04 --stage tight --notes "first crozier of the season"
Saved frond observation: 2026-01-04 tight

$ fernery frond add --date 2026-02-20 --stage unfurled --notes "midrib straight, pinnae even"
Saved frond observation: 2026-02-20 unfurled

$ fernery frond add --date 2026-03-06 --stage flat
Saved frond observation: 2026-03-06 flat
```

Read the log back - always newest first, ties broken by insertion order so the
same store always prints the same text:

```console
$ fernery frond list
Frond unfurling log — 3 observations
DATE        STAGE      NOTES
────────────────────────────────────────────────────────────────────────────────
2026-03-06  flat
2026-02-20  unfurled   midrib straight, pinnae even
2026-01-04  tight      first crozier of the season
```

With nothing recorded yet, the log tells you how to start:

```console
$ fernery frond list
No fronds recorded yet.
Add the first one with:
  fernery frond add --date 2026-01-01 --stage tight --notes "first frond of the season"
```

A note longer than the column is shortened with an ellipsis so the table never
wraps; the full text is still in `fernery.json`.

## 2. Spore print index

Index a print by species, the date it was taken and its colour - one of
`white`, `cream`, `yellow`, `green`, `brown`, `purple`, `black`, `rust`:

```console
$ fernery spore add --species "Dryopteris filix-mas" --date 2026-02-11 --color brown \
    --notes "print on white cartridge paper"
Saved spore print: Dryopteris filix-mas (brown) on 2026-02-11

$ fernery spore add --species "Asplenium scolopendrium" --date 2026-02-15 --color cream
Saved spore print: Asplenium scolopendrium (cream) on 2026-02-15

$ fernery spore list
Spore print index — 2 prints
SPECIES                     COLOR     DATE        NOTES
────────────────────────────────────────────────────────────────────────────────
Asplenium scolopendrium     cream     2026-02-15
Dryopteris filix-mas        brown     2026-02-11  print on white cartridge paper
```

## 3. Rhizome division log

Log how many divisions a plant gave on a date, then read the whole log or one
plant at a time:

```console
$ fernery rhizome add --plant "Bird's Nest" --date 2026-02-08 --divisions 3 \
    --notes "three eyes, all firm"
Saved rhizome division: plant Bird's Nest, 3 divisions on 2026-02-08

$ fernery rhizome add --plant "Hart's Tongue" --date 2026-02-10 --divisions 1
Saved rhizome division: plant Hart's Tongue, 1 division on 2026-02-10

$ fernery rhizome list
Rhizome division log — all plants: 2 records, 4 divisions
PLANT                       DATE        DIVISIONS  NOTES
───────────────────────────────────────────────────────────────────────────────────────────────
Hart's Tongue               2026-02-10  1
Bird's Nest                 2026-02-08  3          three eyes, all firm

$ fernery rhizome list --plant "Bird's Nest"
Rhizome division log — plant Bird's Nest: 1 record, 3 divisions
PLANT                       DATE        DIVISIONS  NOTES
───────────────────────────────────────────────────────────────────────────────────────────────
Bird's Nest                 2026-02-08  3          three eyes, all firm
```

A filter that matches nothing says so, and repeats the command to fix it:

```console
$ fernery rhizome list --plant Maidenhair
No divisions recorded for plant Maidenhair yet.
Log one with:
  fernery rhizome add --plant Maidenhair --date 2026-01-01 --divisions 1
```

## Rejections

Nothing is ever written when a value is rejected, the message names the value
and (for stages and colours) the complete allowed set, and the exit code is `2`:

```console
$ fernery frond add --date 2026-01-01 --stage half-open
fernery: error: stage must be one of: tight, crook, partly, unfurled, flat (got 'half-open')

$ fernery spore add --species Amanita --date 2026-01-01 --color teal
fernery: error: color must be one of: white, cream, yellow, green, brown, purple, black, rust (got 'teal')

$ fernery rhizome add --plant A --date 2026-01-01 --divisions 0
fernery: error: divisions must be a positive whole number (1 or more): got '0'

$ fernery rhizome add --plant A --date 2026-02-30 --divisions 1
fernery: error: date must be a real calendar date written as YYYY-MM-DD (got '2026-02-30')

$ fernery spore add --species "   " --date 2026-01-01 --color brown
fernery: error: species is required and must not be blank
```

Stage and colour tokens are matched exactly as written above; `Crook` and
`Brown` are rejected with the allowed list.

## Scripting

Records go to stdout, messages and errors to stderr, and every list has a
`--json` mode, so Fernery composes with the rest of a shell:

```console
$ fernery frond list --json | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
3

$ fernery frond list > fronds.txt 2> errors.txt

$ fernery frond add --date 2026-01-01 --stage bogus 2>/dev/null; echo $?
2
```

| Exit code | Meaning |
| --- | --- |
| `0` | success |
| `2` | usage or validation error |
| `3` | `fernery.json` could not be read or written |

A corrupt `fernery.json` is reported rather than repaired, and never blocks
itself out of sight:

```console
$ echo "{ not json" > fernery.json
$ fernery frond add --date 2026-01-01 --stage tight
fernery: error: fernery.json could not be read (not valid JSON: line 1, column 1)
$ echo $?
3
```

Your existing entries are left exactly as they were - Fernery refuses to
overwrite a store it cannot parse, so a hand-editing mistake is never made worse.

## The file

```console
$ cat fernery.json
{
  "schema_version": 1,
  "fronds": [
    {
      "id": 1,
      "date": "2026-01-04",
      "stage": "tight",
      "notes": "first crozier of the season"
    }
  ],
  "spores": [],
  "rhizomes": []
}
```

Entries are append-only: Fernery records, it never rewrites or deletes what you
already logged. Back the file up the way you would any text file, and keep one
per season or per bench by running the command from a different directory.

## Colour

Headings and confirmations use a single accent colour, and only when stdout is a
real terminal. Set `NO_COLOR=1` or pass `--no-color` to turn it off; when output
is piped or redirected the colour is dropped automatically.

## Full help

```bash
fernery --help          # the whole surface, with examples
fernery frond --help    # a command group
fernery rhizome add --help
fernery --version
```
