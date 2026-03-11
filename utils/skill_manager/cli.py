"""
CLI for skill-manager

Commands:
  create   Create a new skill from a document or interactively
  update   Update an existing skill from context text
  scan     Scan a skills directory and update all relevant skills
  validate Validate a skill against the agentskills.io spec
  rollback Rollback a skill to a previous backup
  backups  List available backups for a skill
"""

import argparse
import logging
import sys
from pathlib import Path


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(levelname)s  %(message)s",
        level=level,
        stream=sys.stderr,
    )


# ── Subcommand handlers ───────────────────────────────────────────────────────

def cmd_create(args):
    from creator import SkillCreator
    creator = SkillCreator()

    if args.document:
        doc_path = Path(args.document)
        if not doc_path.exists():
            print(f"ERROR: document file not found: {doc_path}", file=sys.stderr)
            sys.exit(1)
        document = doc_path.read_text(encoding="utf-8")
        skill_path = creator.from_document(
            document=document,
            skill_name=args.name,
            output_dir=Path(args.output_dir),
            description=args.description,
            license_text=args.license,
            compatibility=args.compatibility,
            author=args.author,
            overwrite=args.overwrite,
        )
    else:
        # Interactive mode: prompt for body
        print("Enter skill body markdown (end with a line containing only '---END---'):")
        lines = []
        for line in sys.stdin:
            if line.strip() == "---END---":
                break
            lines.append(line)
        body = "".join(lines)

        skill_path = creator.from_scratch(
            skill_name=args.name,
            description=args.description or "",
            body_markdown=body,
            output_dir=Path(args.output_dir),
            license_text=args.license,
            compatibility=args.compatibility,
            author=args.author,
            overwrite=args.overwrite,
        )

    print(f"✓ Skill created: {skill_path}")

    if args.with_dirs:
        creator.create_optional_dirs(skill_path)
        print(f"  Optional directories created (scripts/, references/, assets/)")


def cmd_update(args):
    from skill_manager import SkillUpdater
    updater = SkillUpdater(provider=args.provider, model=args.model)

    if args.context_file:
        context = Path(args.context_file).read_text(encoding="utf-8")
    else:
        print("Enter context text (end with '---END---'):")
        lines = []
        for line in sys.stdin:
            if line.strip() == "---END---":
                break
            lines.append(line)
        context = "".join(lines)

    result = updater.update_from_context(
        skill_path=Path(args.skill_path),
        context=context,
        dry_run=args.dry_run,
        force=args.force,
    )
    print(result)


def cmd_scan(args):
    from skill_manager import SkillScanner
    scanner = SkillScanner(skills_dir=Path(args.skills_dir), provider=args.provider, model=args.model)

    if args.context_file:
        context = Path(args.context_file).read_text(encoding="utf-8")
    else:
        print("Enter context text (end with '---END---'):")
        lines = []
        for line in sys.stdin:
            if line.strip() == "---END---":
                break
            lines.append(line)
        context = "".join(lines)

    targets = args.skills.split(",") if args.skills else None
    results = scanner.scan_and_update(
        context=context,
        dry_run=args.dry_run,
        target_skills=targets,
    )
    print(scanner.report(results))


def cmd_validate(args):
    from skill_manager import validate_skill, SkillValidationError
    skill_path = Path(args.skill_path)
    errors = validate_skill(skill_path, raise_on_error=False)
    if errors:
        print(f"✗ Validation failed for '{skill_path}':")
        for e in errors:
            print(f"  • {e}")
        sys.exit(1)
    else:
        print(f"✓ '{skill_path.name}' is valid")


def cmd_rollback(args):
    from skill_manager import SkillUpdater
    updater = SkillUpdater(provider=args.provider, model=args.model)
    ok = updater.rollback(Path(args.skill_path), steps=args.steps)
    if ok:
        print(f"✓ Rolled back '{args.skill_path}' ({args.steps} step(s))")
    else:
        print("✗ Rollback failed — no backups available", file=sys.stderr)
        sys.exit(1)


def cmd_backups(args):
    from skill_manager import SkillUpdater
    updater = SkillUpdater(provider=args.provider, model=args.model)
    backups = updater.list_backups(Path(args.skill_path))
    if not backups:
        print("No backups found")
    else:
        print(f"Backups for '{args.skill_path}' (newest first):")
        for i, b in enumerate(backups, 1):
            print(f"  {i}. {b.name}")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill-manager",
        description="agentskills.io-compliant skill creator and updater",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--provider",
        default=None,
        help="LangChain provider (e.g. anthropic, openai, ollama, groq). "
             "Overrides SKILL_MANAGER_PROVIDER env var.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for the chosen provider (e.g. gpt-4o, llama3). "
             "Overrides SKILL_MANAGER_MODEL env var.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="Create a new skill")
    p_create.add_argument("name", help="Skill name (will be slugified)")
    p_create.add_argument("output_dir", help="Parent directory for the new skill")
    p_create.add_argument("--document", help="Path to source document (text/markdown)")
    p_create.add_argument("--description", help="Skill description (LLM-generated if omitted)")
    p_create.add_argument("--license", help="License string")
    p_create.add_argument("--compatibility", help="Compatibility string")
    p_create.add_argument("--author", help="Author name for metadata")
    p_create.add_argument("--overwrite", action="store_true", help="Overwrite existing skill")
    p_create.add_argument("--with-dirs", action="store_true", help="Create optional directories")
    p_create.set_defaults(func=cmd_create)

    # update
    p_update = sub.add_parser("update", help="Update an existing skill from context")
    p_update.add_argument("skill_path", help="Path to skill directory")
    p_update.add_argument("--context-file", help="Path to context text file (stdin if omitted)")
    p_update.add_argument("--dry-run", action="store_true", help="Preview without writing")
    p_update.add_argument("--force", action="store_true", help="Skip detection, always update")
    p_update.set_defaults(func=cmd_update)

    # scan
    p_scan = sub.add_parser("scan", help="Scan a skills directory and update relevant skills")
    p_scan.add_argument("skills_dir", help="Path to skills directory")
    p_scan.add_argument("--context-file", help="Path to context text file (stdin if omitted)")
    p_scan.add_argument("--dry-run", action="store_true", help="Preview without writing")
    p_scan.add_argument("--skills", help="Comma-separated skill names to restrict scan")
    p_scan.set_defaults(func=cmd_scan)

    # validate
    p_val = sub.add_parser("validate", help="Validate a skill against the spec")
    p_val.add_argument("skill_path", help="Path to skill directory")
    p_val.set_defaults(func=cmd_validate)

    # rollback
    p_rb = sub.add_parser("rollback", help="Rollback a skill to a previous backup")
    p_rb.add_argument("skill_path", help="Path to skill directory")
    p_rb.add_argument("--steps", type=int, default=1, help="How many versions back (default: 1)")
    p_rb.set_defaults(func=cmd_rollback)

    # backups
    p_bk = sub.add_parser("backups", help="List available backups for a skill")
    p_bk.add_argument("skill_path", help="Path to skill directory")
    p_bk.set_defaults(func=cmd_backups)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
