"""用 FGO 字体生成战斗技能 CD 的绿幕数字模板。

用法：python tools/battle_calib/generate_cd_digits.py --font <FGO 字体文件>

27 px 字形和 2 px 暗描边按 1280x720 战斗截图中的 CD 5、6 校准。
纯绿色区域由 MaaFramework 的 green_mask 排除；输出路径对应
自动战斗_感知.json 的 battle/digits/0.png ... 9.png。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


DEFAULT_OUTPUT = Path("assets/resource/base/image/battle/digits")
FONT_SIZE = 27
OUTLINE_RADIUS = 2
OUTLINE_GRAY = 40
FILL_GRAY = 235
GREEN = (0, 255, 0, 255)


def render_digit(font: ImageFont.FreeTypeFont, digit: int) -> Image.Image:
    canvas = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(canvas).text((8, 8), str(digit), font=font, fill=255)
    glyph = np.asarray(canvas)
    ys, xs = np.nonzero(glyph)
    if len(xs) == 0:
        raise ValueError(f"字体缺少数字 {digit}")

    # 保留字形原始抗锯齿，并为描边和绿幕各留出空间。
    glyph = glyph[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    pad = OUTLINE_RADIUS + 1
    glyph = cv2.copyMakeBorder(glyph, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * OUTLINE_RADIUS + 1, 2 * OUTLINE_RADIUS + 1)
    )
    outline = cv2.dilate(glyph, kernel) > 8

    gray = np.uint8(OUTLINE_GRAY + (FILL_GRAY - OUTLINE_GRAY) * glyph.astype(float) / 255)
    rgba = np.empty((*glyph.shape, 4), dtype=np.uint8)
    rgba[:] = GREEN
    rgba[outline, :3] = np.repeat(gray[:, :, None], 3, axis=2)[outline]
    return Image.fromarray(rgba)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True, help="FGO-Main-Font .otf 的路径")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    font = ImageFont.truetype(str(args.font), FONT_SIZE)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for digit in range(10):
        path = args.output_dir / f"{digit}.png"
        image = render_digit(font, digit)
        image.save(path)
        print(f"{path}: {image.width}x{image.height}")


if __name__ == "__main__":
    main()
