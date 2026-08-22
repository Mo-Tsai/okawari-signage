#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
出一張可以直接丟 LINE 的角色圖 → ../docs/preview/角色表.png

上半：全部角色站成一排，背景就是門頭屏的紅橙漸變。
下半：買一送一那段「遇到路人」的一格，證明三隻真的接進分鏡了。

    python _出角色圖.py

不加字。字用門頭屏那支像素字型在 120 px 高的畫布上只有幾個像素，
縮圖丟到 LINE 上根本讀不出來 —— 要標名字在 LINE 裡打就好。
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw   # noqa: E402

import artwork                     # noqa: E402
import food_sprites                # noqa: E402
import person_sprite               # noqa: E402
import ricebowl_sprite             # noqa: E402
import scene_promo                 # noqa: E402
import segment_art as sa           # noqa: E402

OUT = os.path.abspath(os.path.join(HERE, "..", "docs", "preview", "角色表.png"))
COLS, ROWS = 1180, 120         # 比台南的 960 寬一點，八隻才排得下
SCALE = 2
GAP = 16


def line_up(chars, p):
    """一排角色站在漸變背景上。"""
    sc = artwork.Screen(COLS, ROWS, p)
    im = sc.gradient(phase=0.10)
    d = ImageDraw.Draw(im)
    floor = ROWS - 2

    total = 0
    sizes = []
    for c in chars:
        spr = c.POSES["stand"]
        s = sa._scale(len(spr), ROWS, p)
        sizes.append((spr, s, max(len(r) for r in spr) * s, len(spr) * s))
        total += sizes[-1][2]
    x = (COLS - total - GAP * (len(chars) - 1)) // 2

    for c, (spr, s, w, h) in zip(chars, sizes):
        sa._blit(d, spr, x, floor - h, s, c.PAL)
        x += w + GAP
    return im


def main():
    p = artwork.params({"character": "ricebowl"})

    top = line_up([person_sprite, ricebowl_sprite] +
                  list(food_sprites.FOODS.values()), p)

    # 買一送一：主角停在第一個路人旁邊比對愛心的那一格。
    # 用跟上排一樣的畫布寬度，兩排才切齊 —— 這張是給人看的圖，不是規格書。
    frames = scene_promo.render_bogo(COLS, ROWS, p)
    stop = frames[int(len(frames) * 0.62 * 0.24)]

    sheet = Image.new("RGB", (COLS, ROWS * 2 + 8), (20, 16, 16))
    sheet.paste(top, (0, 0))
    sheet.paste(stop, (0, ROWS + 8))

    sheet.resize((sheet.width * SCALE, sheet.height * SCALE), 0).save(OUT)
    print("%s  %d×%d" % (OUT, sheet.width * SCALE, sheet.height * SCALE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
