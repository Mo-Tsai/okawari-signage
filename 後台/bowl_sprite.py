# -*- coding: utf-8 -*-
"""小飯碗 sprite：從業主 IG 的像素圖抽出來，再把糊掉的地方修乾淨。

原圖 行銷資料夾/小勇者形象/Screenshot 2026-08-17 142303.png
抽法：像素格 4px、每格取眾數色、收斂成 5 色。
修的地方只有臉（眼睛在 4px 格下被壓成一團）和領口的雜點，
帽子、衣服、褲子、比例全部照原圖。

拆成「身體 / 手 / 腿」三部分，才能組出不同動作。
"""

PAL = {
    "H": (169,  66,  27),   # 帽子
    "K": ( 26,  23,  33),   # 描邊、瀏海、鞋
    "S": (252, 241, 146),   # 膚色
    "G": ( 83, 137,  92),   # 綠衣
    "Y": (246, 232,  61),   # 黃褲
    "W": (255, 253, 246),   # 眼白／高光
    "R": (226,  58,  46),   # 碗
    "B": (196, 148,  92),   # 飯／木頭
}

# 身體：帽子到衣襬，不含手腳。18 欄寬。
BODY = [
    "..HHHHHHHHHHHHHH..",
    "..HHHHHHHHHHHHHH..",
    ".HHHHHHHHHHHHHHHH.",
    ".HHHHHHHHHHHHHHHH.",
    ".HHHHHHHHHHHHHHHH.",
    "HHHHHHHHHHHHHHHHHH",
    "HHHHHHHHHHHHHHHHHH",
    "KKKKKKKKKKKKKKKKKK",
    "KKSSSSSSSSSSSSSSKK",
    "KSSSSSSSSSSSSSSSSK",
    "SSSSKKSSSSSSKKSSSS",   # ← 眼睛修過：原本被壓成 KKKG/KGGK
    "SSSSKKSSSSSSKKSSSS",
    "SSSSSSSSSSSSSSSSSS",
    "SSSSSSSSSKKSSSSSSS",   # 嘴
    "SSSSSSSSSSSSSSSSSS",
    "..SSSSSSSSSSSSSS..",
    "...GGGGGGGGGGGG...",   # ← 領口修過：原本有雜點
    "...GGGGGGGGGGGG...",
    "...GGGGGGGGGGGG...",
    "...GGGGGGGGGGGG...",
    "...GGGGGGGGGGGG...",
    "...GGGGGGGGGGGG...",
    "...YYYYYYYYYYYY...",
    "...YYYYYYYYYYYY...",
]

# 手：(dx, dy, 色)。衣服佔第 3〜14 欄，所以手要從第 2／第 15 欄接出去，
# 不然會變成飄在空中的一撇。左右各一隻。
ARM_UP    = [(15,16,"S"),(16,15,"S"),(17,14,"S"),(17,13,"S"),(17,12,"S"),
             (2,17,"S"),(2,18,"S"),(2,19,"S")]                    # 右手舉起（原圖姿勢）
ARM_SWING = [(15,17,"S"),(15,18,"S"),(16,19,"S"),
             (2,17,"S"),(2,18,"S"),(1,19,"S")]                    # 走路擺動
ARM_DOWN  = [(15,17,"S"),(15,18,"S"),(15,19,"S"),
             (2,17,"S"),(2,18,"S"),(2,19,"S")]                    # 垂下
ARM_HOLD  = [(15,17,"S"),(16,18,"S"),(17,18,"S"),
             (2,17,"S"),(1,18,"S"),(0,18,"S")]                    # 端東西（雙手往前）

# 腿：接在身體下方（dy 從身體底部往下算）
LEGS_STAND = [
    "...YYYY..YYYY.....",
    "...SSSS..SSSS.....",
    "...SSSS..SSSS.....",
    "..KKKKK..KKKKK....",
]
LEGS_WALK_A = [                      # 右腿前、左腿後
    "...YYYY..YYYY.....",
    "....SSSS..SSS.....",
    ".....SSSS..SSS....",
    "....KKKKK...KKKK..",
]
LEGS_WALK_B = [                      # 換腳
    "...YYYY..YYYY.....",
    "...SSS..SSSS......",
    "..SSS....SSSS.....",
    ".KKKK....KKKKK....",
]
LEGS_SIT = [
    "...YYYYYYYYYYYYY..",
    "...SSSS......SSS..",
    "..KKKK.......KKK..",
    "..................",
]

# 道具
BOWL = [
    ".RRRRRR.",
    "RBBBBBBR",
    "RRRRRRRR",
    ".RRRRRR.",
    "..RRRR..",
]
STEAM = ["..W.", ".W..", "..W.", ".W.."]      # 蒸氣，一列一個相位
ZZZ   = ["W..", ".W.", "..W"]


def compose(arm=None, legs=None):
    """把身體＋手＋腿組成一張完整的 sprite。"""
    rows = [list(r) for r in BODY]
    w = len(BODY[0])
    if arm:
        for dx, dy, ch in arm:
            while dy >= len(rows):
                rows.append(list("." * w))
            if dx >= len(rows[dy]):
                for r in rows:
                    r.extend("." * (dx + 1 - len(r)))
            rows[dy][dx] = ch
    if legs:
        w2 = max(w, max(len(r) for r in rows))
        for r in rows:
            r.extend("." * (w2 - len(r)))
        for lr in legs:
            rows.append(list(lr.ljust(w2, ".")))
    n = max(len(r) for r in rows)
    return ["".join(r).ljust(n, ".") for r in rows]


POSES = {
    "stand":  compose(ARM_DOWN,  LEGS_STAND),
    "walk_a": compose(ARM_SWING, LEGS_WALK_A),
    "walk_b": compose(ARM_DOWN,  LEGS_WALK_B),
    "cheer":  compose(ARM_UP,    LEGS_WALK_A),      # 原圖那個姿勢
    "hold":   compose(ARM_HOLD,  LEGS_WALK_A),      # 端著飯
    "sit":    compose(ARM_HOLD,  LEGS_SIT),
}

POSES["sleep"] = POSES["sit"]      # 兩個角色的姿勢名稱要一致
