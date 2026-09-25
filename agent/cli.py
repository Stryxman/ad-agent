"""Point d'entrée en ligne de commande.

    ad-agent validate            # valide tous les briefs et formats du repo
    ad-agent formats             # liste la base de formats
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from agent.loader import BRIEFS_DIR, FORMATS_DIR, load_all_formats, load_brief


def cmd_validate(_: argparse.Namespace) -> int:
    errors = 0

    for path in sorted(BRIEFS_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            load_brief(path)
            print(f"ok    brief   {path.name}")
        except (ValidationError, ValueError) as e:
            errors += 1
            print(f"ERREUR brief   {path.name}\n{e}\n", file=sys.stderr)

    try:
        formats = load_all_formats(FORMATS_DIR)
        for f in formats:
            print(f"ok    format  {f.id}")
    except (ValidationError, ValueError) as e:
        errors += 1
        print(f"ERREUR formats\n{e}\n", file=sys.stderr)

    return 1 if errors else 0


def cmd_formats(_: argparse.Namespace) -> int:
    for f in load_all_formats(FORMATS_DIR):
        print(f"{f.id:28} [{f.status}] ratios={','.join(f.ratios)} hooks={','.join(h.value for h in f.hook_types)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ad-agent")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="valide les briefs et les formats").set_defaults(func=cmd_validate)
    sub.add_parser("formats", help="liste les formats").set_defaults(func=cmd_formats)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
