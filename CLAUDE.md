# CLAUDE.md

How to install, test and check `fred-oss`. Every command below comes from the scripts at the
repository root and from `.github/workflows/check-tests.yaml`. Run them all from the
**repository root**.

## Layout

- `fred/` holds the Python package (`setup.py`, `requirements.txt`).
- `fred/src/main/fred` holds the source code (the `fred` package).
- `fred/src/test` holds the unit tests (pytest, under `fred/src/test/test_fred`).
- The repository-root scripts `tests-unit.sh`, `tests-coverage.sh`, `check-style.sh` and
  `check-types.sh` wrap the test and check commands.

## Installation

You need Python 3.12 or newer. `fred/setup.py` sets `python_requires=">=3.12"`, CI uses `3.12`,
and `.python-version` pins `3.12.3`.

This is the same sequence as the "Install Requirements" and "Install Package" steps in CI:

```sh
python -m pip install --upgrade pip
python -m pip install -r requirements-develop.txt   # dev tools: pytest, coverage, pycodestyle, mypy, ...
python -m pip install -e ./fred                     # the fred package, editable, with fred/requirements.txt
```

## Unit tests and coverage

CI runs these two steps:

```sh
bash tests-unit.sh       # (cd fred; coverage run -m pytest src/test)
bash tests-coverage.sh   # (cd fred; coverage report --omit="test_*")
```

- `tests-unit.sh` runs the pytest suite under coverage from inside `fred/`.
- `tests-coverage.sh` prints the coverage report from that run. Run it after `tests-unit.sh`.
- CI calls them as `bash tests-unit.sh fred` and `bash tests-coverage.sh fred`. The scripts ignore
  that argument and always `cd fred`.

To run a single test file, run the same command from inside `fred/`, for example
`(cd fred; coverage run -m pytest src/test/test_fred/test_settings.py)`.

## Style and type checks

```sh
bash check-style.sh   # pycodestyle fred --max-line-length 120
bash check-types.sh   # mypy fred --ignore-missing-imports --install-types --non-interactive
```

- Lines can be up to 120 characters long.
- `--install-types --non-interactive` lets mypy download any missing stub packages without
  prompting, so the type check needs network access.
- No CI workflow runs these two checks. Run them yourself before you open a pull request.

## CI

- `.github/workflows/check-tests.yaml` runs on every pull request. It installs the requirements
  and the package as shown above, then runs `tests-unit.sh` and `tests-coverage.sh`.
- `.github/workflows/check-wheel.yaml` runs on every pull request. It builds the wheel with
  `(cd fred; python setup.py bdist_wheel)`, installs it, and runs `fred version`.
