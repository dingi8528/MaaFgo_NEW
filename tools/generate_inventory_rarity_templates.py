#!/usr/bin/env python3
"""把解包稀有度关键色图转换为库存小图标识别用绿幕模板。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def read_image(path: Path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def write_image(path: Path, image):
    encoded, buffer = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeError(f"无法编码 PNG：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer.tofile(path)


def convert(image, scale: float):
    # 解包图没有有效 alpha，纯黑是关键色背景。只排除纯黑，保留非零深色描边。
    foreground = np.any(image != 0, axis=2).astype(np.uint8) * 255
    width = max(3, round(image.shape[1] * scale))
    height = max(3, round(image.shape[0] * scale))
    resized = cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)
    mask = cv2.resize(foreground, (width, height), interpolation=cv2.INTER_NEAREST)
    # 外围 1px 纯绿用于 MaaFramework green_mask；不要在缩放后混合绿幕色。
    output = np.full((height + 2, width + 2, 3), (0, 255, 0), dtype=np.uint8)
    output[1:-1, 1:-1][mask > 0] = resized[mask > 0]
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="包含 rarity*.png 的解包目录")
    parser.add_argument("output", type=Path, help="输出绿幕模板目录")
    parser.add_argument("--scale", type=float, default=0.74)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parent
        / "manifests"
        / "inventory_rarity_templates.json",
        help="生成记录输出路径（默认写入 tools/manifests，不进入 Maa 资源目录）",
    )
    args = parser.parse_args()
    if not 0 < args.scale <= 2:
        raise SystemExit("--scale 必须位于 (0, 2]")
    sources = sorted(args.source.glob("rarity*.png"))
    if not sources:
        raise SystemExit(f"没有找到 rarity*.png：{args.source}")
    manifest = {
        "schema_version": 1,
        "purpose": "构建个人从者礼装库的小图标星级网格定位",
        "scale": args.scale,
        "interpolation": "Bilinear",
        "key_color": "#000000",
        "green_mask": "#00FF00",
        "files": [],
    }
    for source in sources:
        image = read_image(source)
        if image is None:
            raise RuntimeError(f"无法读取：{source}")
        output = convert(image, args.scale)
        target = args.output / source.name
        write_image(target, output)
        manifest["files"].append(
            {
                "name": source.name,
                "source_size": [image.shape[1], image.shape[0]],
                "output_size": [output.shape[1], output.shape[0]],
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"generated={len(sources)} output={args.output} manifest={args.manifest}"
    )


if __name__ == "__main__":
    main()
