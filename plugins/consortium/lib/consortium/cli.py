"""The consortium command and its incremental command-module registry."""

import argparse
import importlib
import importlib.util

from consortium import __version__

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_WRONG_APP = 3
EXIT_LOCK_TIMEOUT = 4
EXIT_DISK = 5

COMMAND_MODULES = (
    "explain",
    "locks",
    "brief",
    "crew",
    "launcher",
    "gate",
    "runlog",
    "hooks",
    "evals",
)


def _version(args: argparse.Namespace) -> int:
    print(f"consortium {__version__}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="consortium")
    sub = parser.add_subparsers(dest="command", required=True)
    version = sub.add_parser("version", help="print the Consortium version")
    version.set_defaults(func=_version)

    for name in COMMAND_MODULES:
        module_name = f"consortium.{name}"
        if importlib.util.find_spec(module_name) is not None:
            importlib.import_module(module_name).register(sub)

    args = parser.parse_args(argv)
    return args.func(args)
