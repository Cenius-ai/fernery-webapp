# Installing Fernery

Fernery is one Python file that uses only the standard library, so "installing"
means linking an optional console command and nothing more.

## Prerequisites

Only these, and both are usually present already:

| Requirement | Notes |
| --- | --- |
| Python 3.9 or newer | `python3 --version`. Developed and tested on 3.11. |
| pip | `python3 -m pip --version`. Only used to link the `fernery` command. |

There is **no** compiler step, **no** system package to install, **no** database
engine and **no** environment file to fill in. Everything Fernery needs ships in
the standard library.

## Step 1 - get the files

Unpack the project, then enter it:

```bash
unzip fernery.zip -d fernery && cd fernery
```

Everything below is run from the project root (the directory holding
`fernery.py`, `pyproject.toml` and `tests/`).

## Step 2 - install (one package manager: pip)

```bash
bash install.sh
```

That single script, in order:

1. refreshes `pip`, `setuptools` and `wheel`,
2. installs **this project** with `pip install --no-build-isolation -e .`, which
   links the `fernery` console command into the current Python environment
   (nothing is downloaded from a registry - Fernery declares no dependencies),
3. imports `fernery` to prove the module loads on that interpreter,

and then **exits**. It never starts a server and never prompts. Re-running it is
safe and idempotent.

If the environment is not writable, the script prints how to run Fernery without
the console command; the tool itself needs no install at all:

```bash
python3 fernery.py --help
```

Do **not** run install.sh with `sudo`; it never installs system packages.

## Step 3 - seed data

There is no seed step, by design. `fernery.json` is created by your first
successful `add`, and Fernery is explicit about which command fills each log:

```bash
$ fernery frond list
No fronds recorded yet.
Add the first one with:
  fernery frond add --date 2026-01-01 --stage tight --notes "first frond of the season"
```

To see every log populated, run the bundled demonstration - it works inside a
throwaway temporary directory and never touches your own `fernery.json`:

```bash
bash demo.sh
```

## Step 4 - run it

Install.sh links the `fernery` command; if you skipped it, use
`python3 fernery.py` instead of `fernery` in every example:

```bash
fernery --help
fernery frond add --date 2026-01-04 --stage tight --notes "first crozier"
fernery frond list
fernery spore add --species "Dryopteris filix-mas" --date 2026-02-11 --color brown
fernery rhizome add --plant "Bird's Nest" --date 2026-02-08 --divisions 3
fernery rhizome list --plant "Bird's Nest"
```

All records are written to `./fernery.json` in whichever directory you run the
command from, so you can keep one file per season or per bench just by changing
directory.

## Step 5 - run the tests

```bash
python3 -m unittest discover -s tests
python3 -m pytest            # if pytest is available; the same tests run
```

Both run offline, create their own temporary working directories and need no
fixtures.

## Configuration

None. Fernery reads no environment variables and has no config file.
`.env.example` is present only to make that contract explicit. The single
optional setting is the conventional `NO_COLOR=1` if you prefer uncoloured
output (equivalent to `--no-color`).

## Uninstalling

```bash
python3 -m pip uninstall fernery
rm -rf __pycache__ fernery.egg-info
```

Your `fernery.json` files are plain data and are left alone.
