"""用指定字体生成战斗技能 CD 的绿幕数字模板。

用法：python tools/battle_calib/generate_cd_digits.py --font <字体文件> [--region base|cn]

base 参数按日服 1280x720 截图中的 CD 5、6 校准。
cn 参数按国服截图中的 0–8 校准，其中 1、3、5 使用本目录的截图字形参考。
纯绿色区域由 MaaFramework 的 green_mask 排除；输出路径对应
自动战斗_感知.json 的 battle/digits/0.png ... 9.png。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


OUTLINE_GRAY = 40
FILL_GRAY = 235
GREEN = (0, 255, 0, 255)


@dataclass(frozen=True)
class DigitStyle:
    font_size: int
    x_scale: float = 1.0
    y_scale: float = 1.0
    outline_radius: int = 2
    mask_cutoff: int = 8


BASE_STYLE = DigitStyle(27)
CN_STYLE = DigitStyle(30, 1.1)
CN_OVERRIDES = {
    0: DigitStyle(31, 1.1, 1.1, 1),
    6: DigitStyle(30, 1.1),
    7: DigitStyle(31, 1.1, 1.05, 1),
    8: DigitStyle(32, 1.1, 0.95),
}
CN_REFERENCES = {
    1: ("cn_cd_1.png", 130, 20, 2, True),
    3: ("cn_cd_3.png", 90, 20, 2, False),
    5: ("cn_cd_5.png", 70, 20, 1, False),
}
REFERENCE_DIR = Path(__file__).resolve().parent / "reference"


def render_digit(font: ImageFont.FreeTypeFont, digit: int, style: DigitStyle) -> Image.Image:
    canvas = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(canvas).text((8, 8), str(digit), font=font, fill=255)
    glyph = np.asarray(canvas)
    ys, xs = np.nonzero(glyph)
    if len(xs) == 0:
        raise ValueError(f"字体缺少数字 {digit}")

    # 保留字形原始抗锯齿，并为描边和绿幕各留出空间。
    glyph = glyph[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    new_size = (round(glyph.shape[1] * style.x_scale), round(glyph.shape[0] * style.y_scale))
    if new_size != (glyph.shape[1], glyph.shape[0]):
        glyph = cv2.resize(glyph, new_size, interpolation=cv2.INTER_LINEAR)

    pad = style.outline_radius + 1
    glyph = cv2.copyMakeBorder(glyph, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * style.outline_radius + 1, 2 * style.outline_radius + 1)
    )
    outline = cv2.dilate(glyph, kernel) > style.mask_cutoff

    gray = np.uint8(OUTLINE_GRAY + (FILL_GRAY - OUTLINE_GRAY) * glyph.astype(float) / 255)
    rgba = np.empty((*glyph.shape, 4), dtype=np.uint8)
    rgba[:] = GREEN
    rgba[outline, :3] = np.repeat(gray[:, :, None], 3, axis=2)[outline]
    return Image.fromarray(rgba)


def render_cn_reference_digit(digit: int) -> Image.Image:
    filename, floor, saturation, radius, grayscale = CN_REFERENCES[digit]
    path = REFERENCE_DIR / filename
    raw = cv2.imread(str(path))
    if raw is None:
        raise FileNotFoundError(path)

    high = raw.max(axis=2)
    low = raw.min(axis=2)
    white = np.uint8((low >= floor) & ((high - low) <= saturation)) * 255
    count, labels, stats, _ = cv2.connectedComponentsWithStats(white, 8)
    if count < 2:
        raise ValueError(f"参考图中没有数字：{path}")
    largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    core = np.uint8(labels == largest) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    mask = cv2.dilate(core, kernel) > 0

    pixels = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY) if grayscale else raw
    if grayscale:
        pixels = cv2.cvtColor(pixels, cv2.COLOR_GRAY2BGR)
    rgb = cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)
    rgba = np.empty((*raw.shape[:2], 4), dtype=np.uint8)
    rgba[:] = GREEN
    rgba[mask, :3] = rgb[mask]
    return Image.fromarray(rgba)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True, help="用于生成数字的 .otf/.ttf 路径")
    parser.add_argument("--region", choices=("base", "cn"), default="base")
    parser.add_argument("--output-dir", type=Path, help="覆盖区域对应的输出目录")
    args = parser.parse_args()

    output_dir = args.output_dir or Path(f"assets/resource/{args.region}/image/battle/digits")
    output_dir.mkdir(parents=True, exist_ok=True)
    fonts: dict[int, ImageFont.FreeTypeFont] = {}
    for digit in range(10):
        path = output_dir / f"{digit}.png"
        if args.region == "cn" and digit in CN_REFERENCES:
            image = render_cn_reference_digit(digit)
        else:
            style = CN_OVERRIDES.get(digit, CN_STYLE) if args.region == "cn" else BASE_STYLE
            if style.font_size not in fonts:
                fonts[style.font_size] = ImageFont.truetype(str(args.font), style.font_size)
            image = render_digit(fonts[style.font_size], digit, style)
        image.save(path)
        print(f"{path}: {image.width}x{image.height}")


if __name__ == "__main__":
    main()
