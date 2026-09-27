"""Point d'entrée en ligne de commande.

    ad-agent validate            # valide tous les briefs et formats du repo
    ad-agent formats             # liste la base de formats
    ad-agent run briefs/x.yaml   # génère les variantes d'un brief
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from agent.render import BROWSERS
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
        niches = ",".join(n.value for n in f.niches_fit) or "universel"
        hooks = ",".join(h.value for h in f.hook_types)
        print(f"{f.id:28} [{f.status}] ratios={','.join(f.ratios)} hooks={hooks} niches={niches}")
    return 0


def load_dotenv(path: Path) -> None:
    """Charge un fichier .env (CLE=valeur) dans l'environnement, sans écraser les variables déjà définies."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def cmd_run(args: argparse.Namespace) -> int:
    from agent.loader import ROOT
    from agent.pipeline import OUTPUTS_DIR, run
    from agent.writers import OfflineWriter, WriterError

    load_dotenv(ROOT / ".env")
    try:
        if args.writer == "claude":
            from agent.claude_writer import ClaudeWriter

            writer = ClaudeWriter(model=args.model)
        else:
            writer = OfflineWriter()
        run_dir = run(Path(args.brief), writer=writer, out_root=Path(args.out) if args.out else OUTPUTS_DIR,
                      render_png=not args.no_png, browser=args.browser, fond=args.fond,
                      safe_overlay=args.zones_securite)
    except WriterError as e:
        print(f"ERREUR du rédacteur : {e}", file=sys.stderr)
        return 1
    except (ValidationError, ValueError, FileNotFoundError) as e:
        print(f"ERREUR\n{e}", file=sys.stderr)
        return 1
    print(f"Run créé : {run_dir}")
    print(f"Revue     : {run_dir / 'review.md'}")
    usage = getattr(writer, "usage", None)
    if usage and usage["calls"]:
        print(f"Modèle {writer.model} : {usage['calls']} appel(s), "
              f"{usage['input_tokens']} tokens en entrée, {usage['output_tokens']} en sortie")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ad-agent")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="valide les briefs et les formats").set_defaults(func=cmd_validate)
    sub.add_parser("formats", help="liste les formats").set_defaults(func=cmd_formats)
    run_p = sub.add_parser("run", help="génère les variantes d'un brief")
    run_p.add_argument("brief", help="chemin du brief YAML")
    run_p.add_argument("--out", help="dossier de sortie (défaut : outputs/)")
    run_p.add_argument("--no-png", action="store_true", help="HTML uniquement, sans capture PNG")
    run_p.add_argument("--writer", choices=("offline", "claude"), default="offline",
                       help="rédacteur des angles et des textes (défaut : offline, sans clé API)")
    run_p.add_argument("--model", help="modèle Claude (défaut : variable AD_AGENT_MODEL ou claude-opus-5)")
    run_p.add_argument("--browser", choices=BROWSERS, default="chromium",
                       help="moteur de rendu des PNG (défaut : chromium)")
    run_p.add_argument("--fond", choices=("auto", "lineaire", "mesh", "uni"), default="auto",
                       help="traitement de fond (défaut : auto = DA du brief, sinon celui de chaque format)")
    run_p.add_argument("--zones-securite", action="store_true",
                       help="superpose les zones de sécurité Meta (rendu de contrôle, à ne pas publier)")
    run_p.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
