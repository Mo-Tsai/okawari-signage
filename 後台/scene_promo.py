#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 活動畫面（滿額 1000、買一送一）

跟四段常駐分開放，理由是這兩段的生命週期不一樣：常駐畫面上線之後幾乎不會動，
活動是一檔一檔換的。分開放，改活動不必翻動常駐那支檔案。

分鏡工具（_blit、_confetti、角色切換那些）全部沿用 segment_art，
所以兩邊的比例、地面線、角色大小是同一套，接在一起播不會忽大忽小。
"""

import math

from PIL import ImageDraw

import artwork
import segment_art as sa

PROPS = sa.PROPS


# ---------------------------------------------------------------- 滿額 1000
# 客戶 2026-08-18：小勇士與巨石對峙 → 劈開 → 稀有金飯碗升起 → GOLDEN BOWL UNLOCKED!
# 店員觸發（消費滿 1000）。
#
# 客戶原文有「高高跳起使出最後一擊」和「金飯碗慢慢升起」——
# 屏只有 120 px 高，跳跟升的空間都很有限。所以改成：
# 跳躍用「退一步蓄力 + 短促上彈 + 落地全畫面震」換力道，
# 升起用「從碎石中間長出來 + 光芒同時擴散」，靠光補高度不夠的那一段。

STONE = [
    "..DDDDDDDD..",
    ".DDDDGGDDDD.",
    "DDDDDGGDDDDD",
    "DDDDGGGGDDDD",
    "DDDDDGGDDDDD",
    ".DDDDGGDDDD.",
    "..DDDDDDDD..",
]
STONE_PAL = {"D": (92, 86, 96), "G": (247, 179, 43)}

STONE_HALF = [                     # 劈開後的半邊，右半用 flip
    "..DDDD",
    ".DDDDD",
    "DDDDDD",
    "DDDDDD",
    "DDDDDD",
    ".DDDDD",
    "..DDDD",
]

# 劍要畫得比直覺大。在 120 px 高的屏上，照真實比例的劍只有幾個像素寬，
# 遠看是一根牙籤 —— 分不出是武器還是箭頭。所以刀身加粗、護手畫滿。
SWORD_UP = [                       # 舉起來
    ".KWWK.",
    ".KWWK.",
    ".KWWK.",
    ".KWWK.",
    ".KWWK.",
    "KYYYYK",                      # 護手
    "..YY..",
    "..KK..",                      # 握把
]
SWORD_CUT = [                      # 劈下去，刀身往石頭那邊伸
    "KK..........",
    "YYKWWWWWWWWK",
    "YYKWWWWWWWWK",
    "KK..........",
]

# 金飯碗。描一圈深色邊 —— 金色和背景的紅橙是鄰近色，
# 不描邊的話在 LED 上會糊成一片，看不出是一個碗。
GOLD_BOWL = [
    ".KYYYYYYK.",
    "KYWWYYYYYK",
    "KYYYYYYYYK",
    "KYYYYYYYYK",
    ".KYYYYYYK.",
    "..KYYYYK..",
    "...KKKK...",
]


def render_bonus(cols, rows, p=None):
    """滿額 1000：對峙 → 劈 → 石破 → 金飯碗升起 → 歡呼。

    節奏刻意留停頓 —— 對峙要停、蓄力要停、愣住要停。
    一路平推的話「稀有」這件事就不見了，會變成普通的過場動畫。
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = sa._ch(q)
    n = artwork.frame_count(q, "bonus")

    spr = SP.POSES["stand"]
    s = sa._scale(len(spr), rows, q)
    sw = max(len(r) for r in spr) * s
    sh = len(spr) * s
    floor = rows - max(1, s)

    st_s = max(1, int(rows * 0.52 / len(STONE)))
    st_w, st_h = len(STONE[0]) * st_s, len(STONE) * st_s
    st_x = int(cols * 0.56)
    st_y = floor - st_h

    hero_x = st_x - sw - s * 2
    gb_s = max(1, int(rows * 0.62 / len(GOLD_BOWL)))
    gb_w, gb_h = len(GOLD_BOWL[0]) * gb_s, len(GOLD_BOWL) * gb_s

    # 劍不跟角色同一個比例。照角色比例縮，劍只有兩三個像素寬，
    # 在 P4 屏上遠看就是一根牙籤 —— 分不出是武器。
    sd = max(1, int(s * 1.4))
    sx = hero_x + sw - s
    # 舉劍：刀尖要高過頭頂。放在胸口高度的話遠看是一塊白板，不是舉起來的劍。
    sy_up = floor - sh + 2 * s - len(SWORD_UP) * sd
    sy_cut = floor - int(sh * 0.55)

    def sword(d, up, dx=0, dy=0):
        if up:
            sa._blit_prop(d, SWORD_UP, sx + dx, sy_up + dy, sd)
        else:
            sa._blit_prop(d, SWORD_CUT, sx + dx, sy_cut + dy, sd)

    def slash(d, y):
        """劈下去的光痕。刀身本身動得太快看不清楚，靠這道斜線交代軌跡。"""
        d.line([sx, y - int(sh * 0.30), st_x + st_w, y + int(sh * 0.20)],
               fill=PROPS.PAL["W"], width=max(2, sd))

    txt = max(9, round(rows * 0.30))
    out = []
    for i in range(n):
        t = i / n
        # 落地那一下整個畫面震。只震三格，久了會像訊號不良。
        shake = sa._shake(i, max(1, s), period=1) if 0.50 < t < 0.56 else 0

        im = sc.gradient(phase=0.10 + 0.04 * t)
        d = ImageDraw.Draw(im)

        # 石縫的金光：全程脈動，愈接近劈開愈亮
        glow = 0.35 + 0.65 * min(1.0, t / 0.5)
        pal = dict(STONE_PAL)
        gv = int(120 + 135 * glow * (0.7 + 0.3 * math.sin(i * 0.5)))
        pal["G"] = (min(255, gv), min(255, int(gv * 0.72)), 43)

        if t < 0.56:
            sa._blit(d, STONE, st_x + shake, st_y, st_s, pal)

        if t < 0.10:
            # 對峙。兩邊都不動，畫面只有石縫在呼吸。
            sa._blit(d, SP.POSES["stand"], hero_x, floor - sh, s, SP.PAL)
            sword(d, True)

        elif t < 0.18:
            sa._blit(d, SP.POSES["stand"], hero_x, floor - sh, s, SP.PAL)
            sword(d, True)
            sa._text_at(im, "!?", hero_x + sw, floor - sh - txt, txt, artwork.WHT)

        elif t < 0.34:
            # 第一擊。CRACK!
            k = (t - 0.18) / 0.16
            cut = (i // 4) % 2 == 0
            sa._blit(d, SP.POSES["cheer"] if cut else SP.POSES["stand"],
                     hero_x, floor - sh, s, SP.PAL)
            sword(d, not cut)
            if cut:
                slash(d, sy_cut)
                sa._spark(d, st_x + st_w // 2, st_y + st_h // 2,
                          int(st_h * 0.7), st_s, PROPS.PAL["W"])
            if k > 0.3:
                sa._text_at(im, "CRACK!", int(cols * 0.06), int(rows * 0.24),
                            txt, artwork.WHT)

        elif t < 0.44:
            # 退一步蓄力。這一拍不能省 —— 沒有蓄力，最後一擊就沒有重量。
            k = (t - 0.34) / 0.10
            back = int(k * s * 4)
            sa._blit(d, SP.POSES["stand"], hero_x - back, floor - sh, s, SP.PAL)
            sword(d, True, dx=-back, dy=-int(k * s * 2))

        elif t < 0.56:
            # 跳起來、劈下去。BOOM!
            k = (t - 0.44) / 0.12
            hop = -int(math.sin(min(1.0, k * 1.6) * math.pi) * rows * 0.30)
            sa._blit(d, SP.POSES["cheer"], hero_x + int(k * s * 4),
                     floor - sh + hop, s, SP.PAL)
            sword(d, False, dx=int(k * s * 4), dy=hop)
            slash(d, sy_cut + hop)
            if k > 0.5:
                sa._text_at(im, "BOOM!", int(cols * 0.06), int(rows * 0.24),
                            txt, artwork.YEL)
                sa._spark(d, st_x + st_w // 2, st_y + st_h // 2,
                          int(st_h * (0.8 + k)), st_s, PROPS.PAL["W"])

        else:
            # 石頭裂成兩半往外推，金飯碗從中間長出來
            k = (t - 0.56) / 0.44
            spread = int(k * st_w * 0.95)   # 裂得夠開，兩半才不會被金飯碗蓋住
            half_w = len(STONE_HALF[0]) * st_s
            cx = st_x + st_w // 2
            sa._blit(d, STONE_HALF, cx - half_w - spread, st_y, st_s, STONE_PAL)
            sa._blit(d, STONE_HALF, cx + spread, st_y, st_s, STONE_PAL, flip=True)

            rise = int(max(0.0, 1.0 - k * 3.0) * gb_h)
            gx = cx - gb_w // 2
            gy = floor - gb_h + rise
            bob = -int(s * 1.2) if (k > 0.42 and (i // 5) % 2 == 0) else 0
            wob = sa._shake(i, max(1, s), period=7) if k > 0.42 else 0
            sa._blit_prop(d, GOLD_BOWL, gx + wob, gy + bob, gb_s)

            sa._confetti(d, cols, rows, 11, min(1.0, k * 1.4), 0.56, count=70)

            # 小勇士先愣一下，再舉劍歡呼。愣的那一拍是笑點，不要砍掉。
            if k < 0.24:
                sa._blit(d, SP.POSES["stand"], hero_x, floor - sh, s, SP.PAL)
                sword(d, True)
            else:
                cbob = -s if (i // 5) % 2 == 0 else 0
                sa._blit(d, SP.POSES["cheer"], hero_x, floor - sh + cbob, s, SP.PAL)
                sword(d, True, dy=cbob)

            if k > 0.44:
                sa._text_at(im, str(q.get("bonus_text") or "GOLDEN BOWL UNLOCKED!"),
                            int(cols * 0.04), int(rows * 0.20), txt, artwork.YEL)
        out.append(im)
    return out


# ---------------------------------------------------------------- 買一送一
# 客戶 2026-08-18：小飯碗掛著半顆愛心找另一半 → 找到同款 → PERFECT MATCH!
#
# ★ 兩店檔期不同（中港 9/1-2、小北 9/2-3），所以旗幟上的日期是參數，不是圖。
#   改 stores.json 的 params.bogo_date 就好，不必重畫、不必重編另一套美術。
#
# ★ 客戶原文「途中遇到烏龍麵、炸雞、布丁」—— 那三隻還沒畫，
#   這版先用另一個主角當路人。角色到位之後換掉 _passer 就好，分鏡不用動。

# 描邊。愛心是紅的，背景也是紅橙，不描邊在 LED 上整顆會不見。
# 寬度取單數，中間那一欄留空 —— 那條縫就是「兩半」看得出來的地方。
HEART = [
    ".KRR.RRK.",
    "KRRRRRRRK",
    "KRRRRRRRK",
    "KRRRRRRRK",
    ".KRRRRRK.",
    "..KRRRK..",
    "...KRK...",
    "....K....",
]


def _half_heart(right=False):
    """把整顆愛心切一半。是切出來的、不是另外畫的 —— 兩半才對得起來。"""
    w = len(HEART[0])
    mid = w // 2
    out = []
    for r in HEART:
        out.append("." * (mid + 1) + r[mid + 1:] if right
                   else r[:mid] + "." * (w - mid))
    return out


HEART_L = _half_heart(False)
HEART_R = _half_heart(True)


def _passer(SP):
    """路人。用另一個主角頂著 —— 烏龍麵、炸雞、布丁還沒畫。"""
    return sa.ricebowl_sprite if SP is sa.person_sprite else sa.person_sprite


def render_bogo(cols, rows, p=None):
    """買一送一：帶著半顆愛心找另一半，找到同款，愛心合起來。

    中間那段「失落地坐下」是整段的轉折 ——
    沒有那個低點，後面合起來的那一下就沒有落差，只剩兩隻角色站在一起。
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = sa._ch(q)
    OTHER = _passer(SP)
    n = artwork.frame_count(q, "bogo")

    spr = SP.POSES["stand"]
    s = sa._scale(len(spr), rows, q)
    sw = max(len(r) for r in spr) * s
    sh = len(spr) * s
    floor = rows - max(1, s)
    gy = floor - sh

    op = OTHER.POSES["stand"]
    os_ = sa._scale(len(op), rows, q)   # ★ 路人有自己的比例。
    oh = len(op) * os_                 #   人物 28 列、小飯碗 17 列，
                                       #   共用主角的 s 會高到爆出畫布。

    hs_ = max(1, s)
    hw = len(HEART[0]) * hs_
    txt = max(9, round(rows * 0.30))
    mid = cols // 2 - sw

    STOPS = [0.24, 0.44, 0.64]         # 中途停三次比對愛心，把過程攤在畫面上
    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.08 + 0.04 * t)
        d = ImageDraw.Draw(im)

        def hero(x, y, pose="walk_a", heart=True):
            sa._blit(d, SP.POSES[pose], x, y, s, SP.PAL)
            if heart:
                # 掛左胸，不要掛正中央 —— 正中央剛好在嘴巴下面，
                # 遠看像小飯碗吐舌頭。
                sa._blit_prop(d, HEART_L, x + int(sw * 0.12),
                              y + int(sh * 0.56), hs_)

        if t < 0.62:
            k = t / 0.62
            x = int(-sw + (mid + sw) * k)

            # 路人站定不動，主角從他們身邊經過
            for sp in STOPS:
                px = int(-sw + (mid + sw) * sp) + sw + int(cols * 0.06)
                sa._blit(d, op, px, floor - oh, os_, OTHER.PAL, flip=True)

            paused = any(abs(k - sp) < 0.055 for sp in STOPS)
            if paused:
                hero(x, gy, "cheer")                # 把半顆愛心舉起來比對
                sa._text_at(im, "not you...", int(cols * 0.05),
                            int(rows * 0.20), txt, artwork.WHT)
            else:
                hero(x, gy, "walk_a" if (i // 7) % 2 == 0 else "walk_b")

        elif t < 0.72:
            # 失落，坐下。整段的低點。
            k = (t - 0.62) / 0.10
            sit = SP.POSES["sit"]
            sit_h = len(sit) * s
            drop = int(min(1.0, k * 2.5) * s * 4)
            sa._blit(d, sit, mid, floor - sit_h + drop, s, SP.PAL)
            sa._blit_prop(d, HEART_L, mid + int(sw * 0.12),
                          floor - sit_h + drop + int(sh * 0.56), hs_)
            if k > 0.5:
                # 另一半愛心在畫面另一側露出一小角
                sa._blit_prop(d, HEART_R, int(cols * 0.92),
                              gy + int(sh * 0.56), hs_)

        elif t < 0.86:
            # 同款小飯碗走進來，兩個往中間靠
            k = (t - 0.72) / 0.14
            x1 = mid + int(k * sw * 0.7)
            x2 = int(cols * 0.88 - (cols * 0.88 - mid - sw * 1.6) * k)
            hero(x1, gy, "walk_a" if (i // 6) % 2 == 0 else "walk_b")
            sa._blit(d, SP.POSES["walk_a" if (i // 6) % 2 else "walk_b"],
                     x2, gy, s, SP.PAL, flip=True)
            sa._blit_prop(d, HEART_R, x2 + int(sw * 0.50),
                          gy + int(sh * 0.56), hs_)

        else:
            # 啪！合起來。兩個一起跳，小愛心往上冒，活動資訊最後才登場。
            k = (t - 0.86) / 0.14
            bob = -s if (i // 4) % 2 == 0 else 0
            x1, x2 = mid, mid + sw + s
            sa._blit(d, SP.POSES["cheer"], x1, gy + bob, s, SP.PAL)
            sa._blit(d, SP.POSES["cheer"], x2, gy + bob, s, SP.PAL, flip=True)
            big = max(1, int(hs_ * 1.8))
            bw_ = len(HEART[0]) * big
            sa._blit_prop(d, HEART, (x1 + x2 + sw) // 2 - bw_ // 2,
                          gy - int(sh * 0.30) + bob, big)

            for j in range(4):
                u = ((i * 0.5) + j * 6) % 24 / 24.0
                hy2 = gy - int(u * rows * 0.5)
                hx2 = (x1 + x2) // 2 + (j - 2) * 4 * s
                if hy2 > 0:
                    sa._blit_prop(d, HEART_L, hx2, hy2, max(1, hs_ // 2))

            sa._confetti(d, cols, rows, 23, min(1.0, k * 2.0), 0.5, count=70)
            sa._text_at(im, "PERFECT MATCH!", int(cols * 0.04),
                        int(rows * 0.14), txt, artwork.YEL)
            if k > 0.45:
                # 活動資訊。兩店檔期不同，所以日期走參數。
                sa._text_at(im, "%s   %s" % (q.get("bogo_text") or "BUY 1, GET 1",
                                             q.get("bogo_date") or ""),
                            int(cols * 0.04), int(rows * 0.54),
                            max(8, round(rows * 0.24)), artwork.WHT)
        out.append(im)
    return out


RENDERERS = {
    "bonus": render_bonus,
    "bogo": render_bogo,
}
