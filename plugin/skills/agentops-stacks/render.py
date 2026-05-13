"""Native renderer for the agentops-stacks DAB template.

Mirrors what `databricks bundle init` produces from template/, so the plugin can
scaffold projects without shelling out to the Databricks CLI. Required because
Genie Code cannot run the CLI; the renderer works identically in any Python
environment.

Supported Go-template subset (closed — extend deliberately):
  {{ .var }}                              variable substitution
  {{ `string literal` }}                  emit literal text (used to escape
                                          GitHub Actions `${{ ... }}` syntax)
  {{ template `name` . }}                 named template include
  {{ if EXPR }}...{{ else if EXPR }}...{{ else }}...{{ end }}

EXPR forms:
  (eq .var `literal`)
  (or  EXPR EXPR ...)
  (and EXPR EXPR ...)

Whitespace trim markers `{{- ... -}}` strip surrounding whitespace runs,
matching Go's text/template behavior.

The renderer covers both file content and file/directory names. Layout pruning
(cicd platform directory selection) is handled by the orchestrator, not the
renderer.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

# Named templates from library/template_variables.tmpl. Hard-coded rather than
# parsing the .tmpl helper file — there's only one and parsing `define` would
# expand the supported subset for no benefit.
NAMED_TEMPLATES: dict[str, str] = {
    "cli_version": "v0.299.1",
}

# CICD platform → top-level directory that must be kept; all others are pruned.
CICD_KEEP_DIR: dict[str, str] = {
    "github_actions": ".github",
    "github_actions_for_github_enterprise_servers": ".github",
    "azure_devops": ".azure",
    "gitlab": ".gitlab",
}
ALL_CICD_DIRS: set[str] = {".github", ".azure", ".gitlab"}


def render(text: str, context: dict) -> str:
    """Render template text against context."""
    tokens = _tokenize(text)
    _apply_trim(tokens)
    out, idx = _render_tokens(tokens, 0, context)
    if idx != len(tokens):
        raise SyntaxError(f"Trailing tokens after render at index {idx}")
    return out


def _tokenize(text: str) -> list[tuple]:
    """Split into [(text|action, ...)] tokens.

    Backtick-quoted literals inside an action may contain `}}` (used to wrap
    GitHub Actions `${{ ... }}` expressions verbatim), so the scanner tracks
    backtick state instead of leaning on a regex.
    """
    tokens: list[tuple] = []
    pos = 0
    n = len(text)
    i = 0
    while i < n:
        if text[i : i + 2] != "{{":
            i += 1
            continue
        if i > pos:
            tokens.append(("text", text[pos:i]))
        j = i + 2
        ltrim = False
        if j < n and text[j] == "-":
            ltrim = True
            j += 1
        body_start = j
        in_back = False
        while j < n:
            c = text[j]
            if in_back:
                if c == "`":
                    in_back = False
                j += 1
                continue
            if c == "`":
                in_back = True
                j += 1
                continue
            if text[j : j + 3] == "-}}":
                rtrim = True
                body_end = j
                close_end = j + 3
                break
            if text[j : j + 2] == "}}":
                rtrim = False
                body_end = j
                close_end = j + 2
                break
            j += 1
        else:
            raise SyntaxError(f"Unclosed {{{{ ... }}}} starting at offset {i}")
        body = text[body_start:body_end].strip()
        tokens.append(("action", {"body": body, "ltrim": ltrim, "rtrim": rtrim}))
        i = close_end
        pos = i
    if pos < n:
        tokens.append(("text", text[pos:]))
    return tokens


def _apply_trim(tokens: list) -> None:
    for i, tok in enumerate(tokens):
        if tok[0] != "action":
            continue
        if tok[1]["ltrim"] and i > 0 and tokens[i - 1][0] == "text":
            tokens[i - 1] = ("text", tokens[i - 1][1].rstrip(" \t\r\n"))
        if tok[1]["rtrim"] and i + 1 < len(tokens) and tokens[i + 1][0] == "text":
            tokens[i + 1] = ("text", tokens[i + 1][1].lstrip(" \t\r\n"))


def _render_tokens(tokens: list, i: int, context: dict, stop_at: set | None = None) -> tuple[str, int]:
    out: list[str] = []
    while i < len(tokens):
        kind, val = tokens[i]
        if kind == "text":
            out.append(val)
            i += 1
            continue
        body = val["body"].strip()
        keyword = body.split(None, 1)[0] if body else ""
        if stop_at and keyword in stop_at:
            return "".join(out), i
        if keyword == "if":
            rendered, i = _render_if(tokens, i, context)
            out.append(rendered)
        elif keyword in ("else", "end"):
            raise SyntaxError(f"Unexpected {keyword!r} at top level")
        else:
            out.append(_eval_action(body, context))
            i += 1
    return "".join(out), i


def _render_if(tokens: list, i: int, context: dict) -> tuple[str, int]:
    body = tokens[i][1]["body"].strip()
    cond_expr: str | None = body[len("if") :].strip()
    branches: list[tuple[str | None, str]] = []
    i += 1
    while True:
        branch_text, i = _render_tokens(tokens, i, context, stop_at={"else", "end"})
        branches.append((cond_expr, branch_text))
        if i >= len(tokens):
            raise SyntaxError("Unterminated {{if}} block")
        term = tokens[i][1]["body"].strip()
        if term == "end":
            i += 1
            break
        if term == "else":
            cond_expr = None
            i += 1
            continue
        if term.startswith("else if"):
            cond_expr = term[len("else if") :].strip()
            i += 1
            continue
        raise SyntaxError(f"Unexpected terminator in if block: {term!r}")
    for cond, txt in branches:
        if cond is None or _eval_predicate(cond, context):
            return txt, i
    return "", i


def _eval_action(body: str, context: dict) -> str:
    body = body.strip()
    if body.startswith("template "):
        m = re.match(r"template\s+`([^`]+)`\s+\.\s*$", body)
        if not m:
            raise SyntaxError(f"Malformed template action: {body!r}")
        name = m.group(1)
        if name not in NAMED_TEMPLATES:
            raise KeyError(f"Unknown named template: {name!r}")
        return NAMED_TEMPLATES[name]
    if body.startswith("`") and body.endswith("`"):
        return body[1:-1]
    if body.startswith("."):
        return str(context.get(body[1:], ""))
    raise SyntaxError(f"Unsupported action: {body!r}")


def _eval_predicate(expr: str | None, context: dict) -> bool:
    if expr is None:
        return True
    expr = expr.strip()
    if expr.startswith("(") and expr.endswith(")"):
        expr = expr[1:-1].strip()
    parts = _split_top_level(expr)
    if not parts:
        return False
    op, args = parts[0], parts[1:]
    if op == "eq":
        if len(args) != 2:
            raise SyntaxError(f"`eq` requires 2 args, got {len(args)}: {expr!r}")
        return _eval_value(args[0], context) == _eval_value(args[1], context)
    if op == "or":
        return any(_eval_predicate(a, context) for a in args)
    if op == "and":
        return all(_eval_predicate(a, context) for a in args)
    raise SyntaxError(f"Unsupported predicate op: {op!r} in {expr!r}")


def _eval_value(expr: str, context: dict) -> str:
    expr = expr.strip()
    if expr.startswith("`") and expr.endswith("`"):
        return expr[1:-1]
    if expr.startswith("."):
        return context.get(expr[1:], "")
    raise SyntaxError(f"Unsupported value form: {expr!r}")


def _split_top_level(expr: str) -> list[str]:
    """Tokenize a predicate at top level. Respects backticks and parens."""
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    in_back = False
    for c in expr:
        if in_back:
            cur.append(c)
            if c == "`":
                in_back = False
            continue
        if c == "`":
            in_back = True
            cur.append(c)
            continue
        if c == "(":
            if depth == 0 and "".join(cur).strip():
                out.append("".join(cur).strip())
                cur = []
            depth += 1
            cur.append(c)
            continue
        if c == ")":
            depth -= 1
            cur.append(c)
            if depth == 0:
                out.append("".join(cur).strip())
                cur = []
            continue
        if depth == 0 and c.isspace():
            if "".join(cur).strip():
                out.append("".join(cur).strip())
                cur = []
            continue
        cur.append(c)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


# ───────────────────────────────────────────────────────────────────────────
# Scaffold orchestration
# ───────────────────────────────────────────────────────────────────────────

PROJECT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,}$")
VALID_CLOUDS = ("aws", "azure", "gcp")
VALID_CICD = tuple(CICD_KEEP_DIR.keys())


def scaffold(
    *,
    project_name: str,
    cloud: str,
    cicd_platform: str,
    destination: Path | str,
    template_root: Path | str | None = None,
    overwrite_empty_ok: bool = True,
) -> Path:
    """Render the template into ``destination`` and return the resolved path.

    ``template_root`` defaults to ``<this-file's parent>/template`` — the
    bundled copy installed alongside the skill. Pass an explicit path when
    invoking from the repo (use the canonical ``template/`` at the repo root).
    """
    if not PROJECT_NAME_RE.match(project_name):
        raise ValueError(
            f"Invalid project_name {project_name!r}: must match {PROJECT_NAME_RE.pattern}"
        )
    if cloud not in VALID_CLOUDS:
        raise ValueError(f"Invalid cloud {cloud!r}: must be one of {VALID_CLOUDS}")
    if cicd_platform not in VALID_CICD:
        raise ValueError(f"Invalid cicd_platform {cicd_platform!r}: must be one of {VALID_CICD}")

    context = {
        "input_project_name": project_name,
        "input_root_dir": project_name,
        "input_cloud": cloud,
        "input_cicd_platform": cicd_platform,
    }

    if template_root is None:
        template_root = Path(__file__).parent / "template"
    template_root = Path(template_root).resolve()
    if not template_root.is_dir():
        raise FileNotFoundError(f"Template root not found: {template_root}")

    # The template tree has a single top-level dir named {{.input_root_dir}}.
    # We collapse that level into the destination.
    src_root_candidates = list(template_root.iterdir())
    src_roots = [p for p in src_root_candidates if p.is_dir()]
    if len(src_roots) != 1:
        raise RuntimeError(
            f"Expected exactly one top-level directory under {template_root}; "
            f"found {[p.name for p in src_root_candidates]}"
        )
    src_root = src_roots[0]

    dest = Path(destination).expanduser().resolve()
    _prepare_dest(dest, overwrite_empty_ok=overwrite_empty_ok)

    kept_cicd = CICD_KEEP_DIR[cicd_platform]
    skipped_cicd = ALL_CICD_DIRS - {kept_cicd}

    for src_path in sorted(src_root.rglob("*")):
        rel = src_path.relative_to(src_root)
        # Prune unused cicd platform directories.
        if rel.parts and rel.parts[0] in skipped_cicd:
            continue
        # Render the path itself (handles tokens in filenames like
        # `{{.input_project_name}}-bundle-cd-prod.yml.tmpl`).
        rel_rendered = Path(*[render(part, context) for part in rel.parts])
        # Strip a trailing `.tmpl` suffix on the leaf, mirroring `bundle init`.
        if rel_rendered.suffix == ".tmpl":
            rel_rendered = rel_rendered.with_suffix("")
        out_path = dest / rel_rendered
        if src_path.is_dir():
            out_path.mkdir(parents=True, exist_ok=True)
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Only render text files. Anything binary should be passed through
        # untouched; the current template has no binaries, so we always render.
        content = src_path.read_text(encoding="utf-8")
        out_path.write_text(render(content, context), encoding="utf-8")

    return dest


def _prepare_dest(dest: Path, *, overwrite_empty_ok: bool) -> None:
    if not dest.exists():
        dest.mkdir(parents=True, exist_ok=True)
        return
    if not dest.is_dir():
        raise FileExistsError(f"Destination exists and is not a directory: {dest}")
    if not overwrite_empty_ok:
        raise FileExistsError(f"Destination exists: {dest} (overwrite_empty_ok=False)")
    # Allow .git/ to be present (scaffolding into a freshly cloned empty repo).
    leftover = [p for p in dest.iterdir() if p.name != ".git"]
    if leftover:
        names = ", ".join(p.name for p in leftover[:10])
        raise FileExistsError(
            f"Destination {dest} is not empty (contains: {names}). "
            "Refusing to scaffold over existing files."
        )


# ───────────────────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────────────────


def _next_steps(project_name: str, dest: Path) -> str:
    return (
        f"\n*** AgentOps Stacks project created in '{dest}' ***\n\n"
        "Next steps:\n"
        f"  1. cd {dest}\n"
        "  2. Review .agentops-stacks/manifest.yml and databricks.yml\n"
        "  3. Set workspace hosts and Unity Catalog grants (see docs/setup.md)\n"
        "  4. uv sync   (generates uv.lock — commit it)\n"
        "  5. databricks bundle validate -t dev\n"
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scaffold an agentops-stacks project (DAB + CI/CD).",
    )
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--cloud", required=True, choices=VALID_CLOUDS)
    parser.add_argument("--cicd-platform", required=True, choices=VALID_CICD)
    parser.add_argument(
        "--destination",
        help="Output directory (default: ./<project_name>).",
    )
    parser.add_argument(
        "--template-root",
        help="Override the template tree location (default: ./template alongside this script).",
    )
    parser.add_argument(
        "--inputs-json",
        help="Optional JSON file with the same keys as the flags above; flags win on conflict.",
    )

    args = parser.parse_args(argv)

    if args.inputs_json:
        data = json.loads(Path(args.inputs_json).read_text())
        for k in ("project_name", "cloud", "cicd_platform", "destination", "template_root"):
            if getattr(args, k, None) is None and k in data:
                setattr(args, k, data[k])

    dest = Path(args.destination) if args.destination else Path.cwd() / args.project_name
    out = scaffold(
        project_name=args.project_name,
        cloud=args.cloud,
        cicd_platform=args.cicd_platform,
        destination=dest,
        template_root=args.template_root,
    )
    print(_next_steps(args.project_name, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
