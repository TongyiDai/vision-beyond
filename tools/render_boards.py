#!/usr/bin/env python3
"""Deterministically render the repository's validated Geometry Board scenes."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

BLACK = "#111111"
GRAY = "#666666"
LIGHT = "#E8E8E8"
BLUE = "#2F6BFF"


def line(x1: float, y1: float, x2: float, y2: float, arrow: bool = False) -> str:
    marker = ' marker-end="url(#arrow)"' if arrow else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{BLACK}" stroke-width="1"{marker}/>'


def text(x: float, y: float, value: str, size: int = 16, anchor: str = "middle", color: str = BLACK, weight: int = 400) -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{color}" '
        f'font-family="Inter,PingFang SC,Helvetica Neue,sans-serif" font-size="{size}" font-weight="{weight}">'
        f'{html.escape(value)}</text>'
    )


def node(x: float, y: float, item: dict, radius: float = 38) -> str:
    accent = bool(item.get("accent"))
    stroke = BLUE if accent else BLACK
    fill = BLUE if accent else "#FFFFFF"
    label_color = "#FFFFFF" if accent else BLACK
    kind = item.get("type")
    if kind == "point":
        shape = f'<circle cx="{x}" cy="{y}" r="7" fill="{stroke}"/>'
        label = text(x, y + 34, item["label"], 15)
    elif kind == "circle":
        shape = f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        label = text(x, y + 5, item["label"], 16, color=label_color, weight=600)
    else:
        width, height = 150, 72
        shape = f'<rect x="{x-width/2}" y="{y-height/2}" width="{width}" height="{height}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        label = text(x, y + 5, item["label"], 16, color=label_color, weight=600)
    return shape + label


def axis_flow(scene: dict) -> str:
    items = scene["nodes"]
    xs = [130 + index * (940 / (len(items) - 1)) for index in range(len(items))]
    y = 370
    output = [line(xs[0], y, xs[-1], y, True)]
    output.extend(node(x, y, item, 48) for x, item in zip(xs, items))
    return "".join(output)


def radial_center(scene: dict) -> str:
    items = scene["nodes"]
    focus_id = scene["intent"]["focus_node"]
    center = next(item for item in items if item["id"] == focus_id)
    outer = [item for item in items if item["id"] != focus_id]
    positions = [(330, 260), (600, 205), (870, 260), (870, 475), (600, 530), (330, 475)]
    cx, cy = 600, 370
    output = [line(x, y, cx, cy) for (x, y) in positions[: len(outer)]]
    output.extend(node(x, y, item) for item, (x, y) in zip(outer, positions))
    output.append(node(cx, cy, center, 66))
    return "".join(output)


def matrix(scene: dict) -> str:
    left, right, top, bottom = 220, 1000, 190, 575
    output = [line(left, bottom, right, bottom, True), line(left, bottom, left, top, True)]
    output.extend(
        [
            text(right, bottom + 42, "工作价值 →", 14, anchor="end", color=GRAY),
            text(left - 22, top - 12, "未消费程度 ↑", 14, anchor="start", color=GRAY),
            f'<line x1="{(left+right)/2}" y1="{top}" x2="{(left+right)/2}" y2="{bottom}" stroke="{LIGHT}"/>',
            f'<line x1="{left}" y1="{(top+bottom)/2}" x2="{right}" y2="{(top+bottom)/2}" stroke="{LIGHT}"/>',
        ]
    )
    coordinates = {
        "low-low": (400, 485),
        "high-low": (820, 485),
        "low-high": (400, 295),
        "high-high": (820, 295),
    }
    output.extend(node(*coordinates[item["state"]], item, 54) for item in scene["nodes"])
    return "".join(output)


def input_process_output(scene: dict) -> str:
    items = {item["id"]: item for item in scene["nodes"]}
    focus_id = scene["intent"]["focus_node"]
    left_ids = [edge["from"] for edge in scene["edges"] if edge["to"] == focus_id]
    right_ids = [edge["to"] for edge in scene["edges"] if edge["from"] == focus_id]
    left_positions = [(260, 260), (260, 370), (260, 480)]
    right_positions = [(940, 260), (940, 370), (940, 480)]
    cx, cy = 600, 370
    output = [line(x, y, cx - 65, cy) for x, y in left_positions[: len(left_ids)]]
    output.extend(line(cx + 65, cy, x, y, True) for x, y in right_positions[: len(right_ids)])
    output.extend(node(x, y, items[item_id]) for item_id, (x, y) in zip(left_ids, left_positions))
    output.append(node(cx, cy, items[focus_id], 66))
    output.extend(node(x, y, items[item_id]) for item_id, (x, y) in zip(right_ids, right_positions))
    return "".join(output)


RENDERERS = {
    "axis-flow": axis_flow,
    "radial-center": radial_center,
    "matrix-2d": matrix,
    "input-process-output": input_process_output,
}


def render(scene: dict) -> str:
    width = scene["canvas"]["width"]
    height = scene["canvas"]["height"]
    title = scene["intent"]["core_message"]
    body = RENDERERS[scene["intent"]["composition"]](scene)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="{BLACK}"/></marker></defs>
{text(96, 88, title, 32, anchor="start", weight=650)}
{text(96, 122, "VISION BEYOND / 视野之外", 12, anchor="start", color=GRAY, weight=500)}
{body}
{text(1104, 624, "permission-aware · read-only · Top 5", 11, anchor="end", color=GRAY)}
</svg>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path("assets/boards"))
    args = parser.parse_args()
    for path in sorted(args.directory.glob("*.scene.json")):
        scene = json.loads(path.read_text(encoding="utf-8"))
        output = path.with_suffix("").with_suffix(".svg")
        output.write_text(render(scene), encoding="utf-8")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
