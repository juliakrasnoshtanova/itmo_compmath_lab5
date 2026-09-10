#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import pathlib
import shutil
import subprocess
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
MERMAID_DIR = ROOT / "mermaid"
OUT_DIR = ROOT / "report_assets"

DIAGRAMS = [
    "solve",
    "interpolate",
    "lagrange",
    "razdel_raznosti",
    "newton_razdel",
    "konech_raznosti",
    "newton_konech",
]


def encode_live_state(code: str) -> str:
    payload = {
        "code": code,
        "mermaid": {"theme": "default"},
        "autoSync": True,
        "updateDiagram": True,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compressobj(level=9, wbits=-15)
    data = compressed.compress(raw) + compressed.flush()
    encoded = base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")
    return "pako:" + encoded


def render(source: pathlib.Path, target: pathlib.Path) -> None:
    mmdc = shutil.which("mmdc")
    if mmdc is None:
        raise RuntimeError("не найден mmdc, установите @mermaid-js/mermaid-cli")
    subprocess.run(
        [
            mmdc,
            "--input", str(source),
            "--output", str(target),
            "--theme", "default",
            "--backgroundColor", "transparent",
            "--scale", "2",
        ],
        check=True,
        capture_output=True,
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    links = []
    for name in DIAGRAMS:
        source = MERMAID_DIR / f"{name}.mmd"
        code = source.read_text(encoding="utf-8")
        target = OUT_DIR / f"{name}.png"
        render(source, target)
        links.append(f"https://mermaid.live/edit#{encode_live_state(code)}")
        print(f"saved {target}")

    (MERMAID_DIR / "links.txt").write_text("\n".join(links) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
