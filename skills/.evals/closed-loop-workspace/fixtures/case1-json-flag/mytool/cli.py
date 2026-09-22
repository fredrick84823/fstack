"""mytool command line interface."""

from __future__ import annotations

import argparse

from .core import gather_status


def format_status(status: dict) -> str:
    state = "clean" if status["clean"] else "dirty"
    return (
        f"root:     {status['root']}\n"
        f"branch:   {status['branch']}\n"
        f"tracked:  {status['tracked']}\n"
        f"modified: {status['modified']}\n"
        f"state:    {state}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mytool")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="show workspace status")
    status.add_argument("--root", default=".", help="workspace root")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        print(format_status(gather_status(args.root)))
        return 0
    return 1
