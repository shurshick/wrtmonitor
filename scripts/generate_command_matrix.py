from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.command_registry import COMMAND_REGISTRY  # noqa: E402


SURFACE_EQUIVALENTS = json.loads(
    (ROOT / "contracts" / "surface-equivalents.json").read_text(encoding="utf-8")
)
SURFACE_EXCLUSIONS = json.loads(
    (ROOT / "contracts" / "surface-exclusions.json").read_text(encoding="utf-8")
)


def source_text(*parts: str) -> str:
    root = ROOT.joinpath(*parts)
    if root.is_file():
        return root.read_text(encoding="utf-8")
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".html", ".kt", ".py", ".sh"}
    )


def exact_reference(source: str, command: str) -> bool:
    return bool(
        re.search(rf"(?<![A-Za-z0-9_.]){re.escape(command)}(?![A-Za-z0-9_.])", source)
    )


def without_line_comments(source: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def build_matrix() -> dict[str, Any]:
    web = source_text("backend", "app", "templates") + source_text(
        "backend", "app", "web"
    )
    android = without_line_comments(
        source_text("android", "app", "src", "main", "java")
    )
    agent = source_text("openwrt-agent", "lib")
    rows: list[dict[str, Any]] = []
    for command, metadata in sorted(COMMAND_REGISTRY.items()):
        reliability = metadata["reliability"]
        equivalents = SURFACE_EQUIVALENTS.get(command, {})
        exclusions = SURFACE_EXCLUSIONS.get(command, {})
        web_reference = exact_reference(web, command)
        android_reference = exact_reference(android, command)
        if equivalents.get("web"):
            web_reference = web_reference or equivalents["web"] in web
        if equivalents.get("android"):
            android_reference = android_reference or equivalents["android"] in android
        row = {
            "command": command,
            "subsystem": reliability["subsystem"],
            "surfaces": {
                "api": True,
                "web": web_reference,
                "android": android_reference,
                "agent": exact_reference(agent, command),
            },
            "capability": metadata["capability"],
            "risk": metadata["risk_level"],
            "confirmation": metadata["requires_confirmation"],
            "idempotency": reliability["idempotency"],
            "timeout_seconds": reliability["delivery"]["timeout_seconds"],
            "max_deliveries": reliability["delivery"]["max_deliveries"],
            "post_condition": reliability["post_condition"],
            "verification": reliability["verification"],
            "rollback": reliability["rollback"],
            "surface_equivalents": equivalents,
        }
        if exclusions:
            row["surface_exclusions"] = exclusions
        rows.append(row)
    return {"command_count": len(rows), "commands": rows}


def markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Матрица команд WrtMonitor",
        "",
        "Файл генерируется из исполнимого контракта и исходников командой",
        "`python scripts/generate_command_matrix.py --write`. Ручное редактирование запрещено.",
        "",
        f"Всего команд: **{matrix['command_count']}**.",
        "",
        "| Команда | Web | Android | API | Agent | Capability | Риск | Post-condition | Rollback |",
        "|---|:---:|:---:|:---:|:---:|---|---|---|---|",
    ]

    def mark(value: bool, excluded: bool) -> str:
        if excluded:
            return "искл."
        return "да" if value else "нет"

    for row in matrix["commands"]:
        surfaces = row["surfaces"]
        exclusions = row.get("surface_exclusions", {})
        lines.append(
            "| {command} | {web} | {android} | {api} | {agent} | {capability} | "
            "{risk} | {post_condition} | {rollback} |".format(
                command=f"`{row['command']}`",
                web=mark(surfaces["web"], "web" in exclusions),
                android=mark(surfaces["android"], "android" in exclusions),
                api=mark(surfaces["api"], "api" in exclusions),
                agent=mark(surfaces["agent"], "agent" in exclusions),
                capability=f"`{row['capability']}`",
                risk=row["risk"],
                post_condition=row["post_condition"],
                rollback=row["rollback"],
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    matrix = build_matrix()
    json_rendered = json.dumps(matrix, ensure_ascii=False, indent=2) + "\n"
    md_rendered = markdown(matrix)
    targets = {
        ROOT / "contracts" / "command-matrix.json": json_rendered,
        ROOT / "docs" / "command-matrix.md": md_rendered,
    }
    if args.write:
        for target, rendered in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
    stale = [
        str(target.relative_to(ROOT))
        for target, rendered in targets.items()
        if not target.is_file() or target.read_text(encoding="utf-8") != rendered
    ]
    if stale:
        print(f"command matrix is stale: {', '.join(stale)}", file=sys.stderr)
        return 1
    missing_agent = [
        row["command"] for row in matrix["commands"] if not row["surfaces"]["agent"]
    ]
    if missing_agent:
        print(f"agent surface missing: {missing_agent}", file=sys.stderr)
        return 1
    missing_user_surfaces = {
        surface: [
            row["command"]
            for row in matrix["commands"]
            if not row["surfaces"][surface]
            and surface not in row.get("surface_exclusions", {})
        ]
        for surface in ("web", "android")
    }
    missing_user_surfaces = {
        surface: commands
        for surface, commands in missing_user_surfaces.items()
        if commands
    }
    if missing_user_surfaces:
        print(f"operation parity missing: {missing_user_surfaces}", file=sys.stderr)
        return 1
    print(f"command matrix OK: {matrix['command_count']} commands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
