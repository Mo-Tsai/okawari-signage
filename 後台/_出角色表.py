#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把所有角色的 sprite 匯出成 ../docs/preview/sprites.json。

角色檢視頁（docs/characters.html）讀的就是這一份。以前這份 json 是手工維護的，
角色一多就會跟 Python 這邊對不起來 —— 網頁上看到的跟上屏的不是同一張，
那個頁面就沒有意義了。所以改成從 Python 直接匯出。

    python _出角色表.py

改完 sprite 就跑一次，然後 ../推上GitHub.bat。
"""

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import artwork               # noqa: E402  ← 一定要第一個。artwork 底部會反過來
                             #   import scene_promo，先載 scene_promo 會撞成循環引用
import food_sprites          # noqa: E402
import person_sprite         # noqa: E402
import ricebowl_sprite       # noqa: E402
import scene_promo           # noqa: E402

assert artwork               # 只是為了讓 lint 閉嘴，上面那個 import 是有作用的

OUT = os.path.abspath(os.path.join(HERE, "..", "docs", "preview", "sprites.json"))

# (key, 名字, 說明, 姿勢來源, 配色)
# 配色分開給，是因為金飯碗跟小飯碗共用同一組姿勢、只換色。
ROSTER = [
    ("person", "人物",
     "戴紅帽的小孩，從業主 IG 的像素圖直接抽出來的。",
     person_sprite, person_sprite.PAL),
    ("ricebowl", "小飯碗（牛丼）",
     "長出手腳的牛丼，碗身上兩顆眼睛。名單上的「牛丼」就是它。",
     ricebowl_sprite, ricebowl_sprite.PAL),
    ("gold", "金飯碗",
     "滿額 1000 才會出現的稀有版。同一張 sprite，只換配色。",
     ricebowl_sprite, scene_promo.GOLD_PAL),
]
ROSTER += [(c.key, c.name, c.desc, c, c.PAL) for c in food_sprites.FOODS.values()]


def hexes(pal):
    return {k: "#%02x%02x%02x" % tuple(v) for k, v in pal.items()}


def main():
    data = {}
    for key, name, desc, src, pal in ROSTER:
        poses = dict(src.POSES)
        poses.pop("sit", None)          # sit 是 sleep 的別名，不必列兩次
        data[key] = {
            "name": name,
            "desc": desc,
            "pal": hexes(pal),
            "poses": poses,
            "walk": ["walk_a", "walk_b"],
            "walk_every": 6,
        }

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print("%d 個角色 → %s" % (len(data), OUT))
    for key, v in data.items():
        p = v["poses"]["stand"]
        print("  %-9s %-14s %2d 列 × %2d 欄　%d 個姿勢"
              % (key, v["name"], len(p), max(len(r) for r in p), len(p and v["poses"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
