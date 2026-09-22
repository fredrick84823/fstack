# mytool

Small workspace status CLI.

## Conventions

- Product code lives in `mytool/`. Tests live in `tests/`.
- `mytool/core.py` gathers data and never formats output. `mytool/cli.py` owns
  argument parsing and all printing.
- Every subcommand is registered in `build_parser()` and dispatched in `main()`.
- Human-readable output is the default for every command.

## Commands

- `make test` runs the test suite (pytest).
- `make lint` byte-compiles the package.
- Run the tool with `python3 -m mytool status`.
