#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二個角色：丼飯本人。

一碗牛丼長出手腳、碗身上兩顆眼睛。矮一點、寬一點，
才不會看起來只是「小飯碗換個頭」—— 站在一起要一眼分得出誰是誰。

配色沿用小飯碗那組（bowl_sprite.PAL），兩個角色才像同一個世界的。
碗身白、碗緣 OKAWARI 紅、上面褐色肉片配綠蔥花，照品牌簡報那張牛丼照。

網格 20 欄 × 17 列。小飯碗是 18×28，所以丼飯明顯矮胖。
"""

PAL = {
    "K": ( 26,  23,  33),   # 描邊、眼睛
    "W": (255, 253, 246),   # 碗身、白飯
    "R": (226,  58,  46),   # 碗緣（OKAWARI 紅）
    "M": (150,  95,  50),   # 肉片
    "N": (110, 170,  92),   # 蔥花
    "S": (252, 241, 146),   # 手腳（跟小飯碗的膚色同一支）
    "Y": (247, 179,  43),   # 蛋黃／高光
}

# 碗身（不含手腳）。上面三列是配料，露在碗口外面。
BOWL_BODY = [
    ".....MMMMMMMM.....",
    "...MMNMMMMNMMMM...",     # 蔥花散開，不然遠看只是一坨褐色
    "..MMMMMNMMMMNMMMM.",
    "..WWWWWWWWWWWWWWW.",     # 白飯從肉片下面透出來
    ".KKKKKKKKKKKKKKKK.",
    "KRRRRRRRRRRRRRRRRK",     # 碗緣：OKAWARI 紅
    "KWWWWWWWWWWWWWWWWK",
    "KWWKKWWWWWWWWKKWWK",     # 眼睛
    "KWWKKWWWWWWWWKKWWK",
    "KWWWWWWWKKWWWWWWWK",     # 嘴：收窄成兩格，比較憨
    ".KWWWWWWWWWWWWWWK.",
    "..KWWWWWWWWWWWWK..",
    "...KKKKKKKKKKKK...",
]

# 手：從碗身兩側伸出去。(dx, dy, 色)
ARM_DOWN  = [(18, 7, "S"), (19, 7, "S"), (18, 8, "S"), (19, 8, "S"), (18, 9, "S"),
             (-1, 7, "S"), (-2, 7, "S"), (-1, 8, "S"), (-2, 8, "S"), (-1, 9, "S")]
ARM_SWING = [(18, 6, "S"), (19, 6, "S"), (18, 7, "S"), (19, 7, "S"),
             (-1, 8, "S"), (-2, 8, "S"), (-1, 9, "S"), (-2, 9, "S")]
ARM_UP    = [(18, 6, "S"), (19, 5, "S"), (20, 4, "S"), (20, 3, "S"),
             (-1, 6, "S"), (-2, 5, "S"), (-3, 4, "S"), (-3, 3, "S")]
ARM_HOLD  = [(18, 8, "S"), (19, 8, "S"), (18, 9, "S"),
             (-1, 8, "S"), (-2, 8, "S"), (-1, 9, "S")]

# 腳：接在碗底下方
LEGS_STAND = [
    "......SS....SS....",
    "....KKKK..KKKK....",
]
LEGS_WALK_A = [
    ".....SS......SS...",
    "...KKKK.....KKKK..",
]
LEGS_WALK_B = [
    ".......SS..SS.....",
    "....KKKK..KKKK....",
]
LEGS_HOP = [
    "......SS....SS....",
    ".....KKKK..KKKK...",
]


def _compose(arm, legs):
    """碗身 ＋ 手 ＋ 腳。手可能伸到左邊負座標，所以整張要往右墊。"""
    pad = max(0, -min([dx for dx, _, _ in arm] or [0]))
    w = len(BOWL_BODY[0]) + pad
    rows = [list(("." * pad) + r) for r in BOWL_BODY]

    for dx, dy, ch in arm:
        x = dx + pad
        while dy >= len(rows):
            rows.append(list("." * w))
        for r in rows:
            if len(r) <= x:
                r.extend("." * (x + 1 - len(r)))
        rows[dy][x] = ch

    w = max(len(r) for r in rows)
    for r in rows:
        r.extend("." * (w - len(r)))
    for lr in legs:
        rows.append(list((("." * pad) + lr).ljust(w, ".")))

    n = max(len(r) for r in rows)
    return ["".join(r).ljust(n, ".") for r in rows]


POSES = {
    "stand":  _compose(ARM_DOWN,  LEGS_STAND),
    "walk_a": _compose(ARM_SWING, LEGS_WALK_A),
    "walk_b": _compose(ARM_DOWN,  LEGS_WALK_B),
    "cheer":  _compose(ARM_UP,    LEGS_HOP),
    "hold":   _compose(ARM_HOLD,  LEGS_WALK_A),
}


def walk_frame(i, every=6):
    """走路兩幀交替，節奏跟小飯碗一致。"""
    return POSES["walk_a"] if (i // every) % 2 == 0 else POSES["walk_b"]
