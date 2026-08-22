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
import food_sprites
import segment_art as sa

PROPS = sa.PROPS


# ---------------------------------------------------------------- 滿額 1000
# 客戶 2026-08-18／19：小飯碗拿刀與巨石對峙 → 切開 → 稀有金飯碗升起
# → GOLDEN BOWL UNLOCKED!
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

# 拿的是**刀**不是劍。2026-08-19 業主：切的人是小飯碗，不是人物。
# 一碗飯舉著騎士劍很怪，菜刀才對 —— 而且菜刀是塊狀的，
# 在 P4 屏上遠看比細長的劍好認得多。
# 刀是**橫握**的，不是舉直的。
# 舉直的白刀身在 120 px 高的屏上就是一面白旗 —— 看不出是刀，
# 而且跟小飯碗的手接不起來（它的手是從碗身兩側伸出來的，舉不高）。
# 橫握還有一個好處：刀尖直接指著石頭，對峙那一拍不用再解釋。
KNIFE_READY = [                    # 舉著，刀尖指向石頭
    "..KK........",
    ".KBBK.......",
    ".KBBKKKKKKKK",                # 刀背
    ".KBBKWWWWWWW",
    ".KBBKWWWWWWW",
    "..KK.KKKKKKK",                # 刃口
]
KNIFE_CUT = KNIFE_READY            # 同一把刀，差別在高度和那道光痕

# 金飯碗。2026-08-19 業主：劈開來要是「跟小飯碗一樣的角色，但是金色的」。
#
# 所以它不是一個道具碗，是**小飯碗本人的稀有版** —— 同一張 sprite、
# 同一組姿勢，只換配色。這樣一來：
#   1. 客人一眼認得出「那是小飯碗」，稀有感才有對照組
#   2. 它會走、會跳、會歡呼，因為姿勢表本來就有
#   3. 之後小飯碗改造型，金色版自動跟著改，不會有兩套要維護
#
# 配色是整組換金，只留白色高光和深色描邊。金色跟背景的紅橙是鄰近色，
# 描邊不能省 —— 不描邊在 LED 上會糊成一團，看不出輪廓。
GOLD_PAL = {
    "K": ( 26,  23,  33),   # 描邊，照原本的
    "W": (255, 198, 56),    # 碗身：白 → 金（要夠亮，背景壓暗才拉得開）
    "R": (198, 132, 22),    # 碗緣：紅 → 深金（要比碗身暗，不然邊界不見）
    "M": (176, 118, 20),    # 肉片 → 暗金
    "N": (222, 168, 46),    # 蔥花 → 中金
    "S": (255, 226, 138),   # 手腳 → 亮金
    "Y": (255, 253, 246),   # 高光 → 純白，這是「閃」的來源
}


def render_bonus(cols, rows, p=None):
    """滿額 1000：對峙 → 劈 → 石破 → 金飯碗升起 → 歡呼。

    節奏刻意留停頓 —— 對峙要停、蓄力要停、愣住要停。
    一路平推的話「稀有」這件事就不見了，會變成普通的過場動畫。
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    n = artwork.frame_count(q, "bonus")

    # ★ 這一段兩個角色都是小飯碗，不跟著 params.character 換。
    #   2026-08-19 業主：「不是那個人物，是小飯碗，拿著刀子切下去變成金飯碗。」
    #   拿刀的是白的那隻，石頭裂開之後升起來的是金的那隻 —— 同一張 sprite、
    #   只有配色不同，所以「那是小飯碗的稀有版」一眼就讀得出來。
    SP = sa.ricebowl_sprite

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

    # 金飯碗＝同一隻小飯碗的稀有版。要認得出「是同一個角色」，
    # 稀有感才有對照組 —— 換一隻沒看過的角色反而沒有升級的感覺。
    GB = SP                                            # 就是小飯碗本人
    gb_pose = GB.POSES["stand"]
    gb_s = max(1, int(rows * 0.88 / len(gb_pose)))     # 比白的那隻大一圈，它是主角
    gb_w = max(len(r) for r in gb_pose) * gb_s
    gb_h = len(gb_pose) * gb_s

    # 劍不跟角色同一個比例。照角色比例縮，劍只有兩三個像素寬，
    # 在 P4 屏上遠看就是一根牙籤 —— 分不出是武器。
    sd = max(1, int(sh * 0.42 / len(KNIFE_READY)))
    sx = hero_x + int(sw * 0.78)
    # 刀柄要落在手上。小飯碗的手從碗身兩側伸出來，大約在身高四成的位置。
    sy_up = floor - sh + int(sh * 0.30)
    sy_cut = floor - sh + int(sh * 0.52)

    def knife(d, up, dx=0, dy=0):
        if up:
            sa._blit_prop(d, KNIFE_READY, sx + dx, sy_up + dy, sd)
        else:
            sa._blit_prop(d, KNIFE_CUT, sx + dx, sy_cut + dy, sd)

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

        # 石破之後背景壓暗。金色和背景的紅橙是鄰近色 —— 不壓暗，
        # 金飯碗會整隻融進去（第一版就是這樣，完全看不到）。
        # 壓暗同時也剛好是「聚光燈打在稀有道具上」的語言。
        im = sc.gradient(phase=0.10 + 0.04 * t, dim=t >= 0.56)
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
            sa._blit(d, SP.POSES["cheer"], hero_x, floor - sh, s, SP.PAL)
            knife(d, True)

        elif t < 0.18:
            sa._blit(d, SP.POSES["cheer"], hero_x, floor - sh, s, SP.PAL)
            knife(d, True)
            sa._text_at(im, "!?", hero_x + sw, floor - sh - txt, txt, artwork.WHT)

        elif t < 0.34:
            # 第一擊。CRACK!
            k = (t - 0.18) / 0.16
            cut = (i // 4) % 2 == 0
            sa._blit(d, SP.POSES["cheer"] if cut else SP.POSES["stand"],
                     hero_x, floor - sh, s, SP.PAL)
            knife(d, not cut)
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
            sa._blit(d, SP.POSES["cheer"], hero_x - back, floor - sh, s, SP.PAL)
            knife(d, True, dx=-back, dy=-int(k * s * 2))

        elif t < 0.56:
            # 跳起來、劈下去。BOOM!
            k = (t - 0.44) / 0.12
            hop = -int(math.sin(min(1.0, k * 1.6) * math.pi) * rows * 0.30)
            sa._blit(d, SP.POSES["cheer"], hero_x + int(k * s * 4),
                     floor - sh + hop, s, SP.PAL)
            knife(d, False, dx=int(k * s * 4), dy=hop)
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

            if k <= 0.42:
                # 還在升起。站著不動，讓「冒出來」這件事單獨講完。
                sa._blit(d, gb_pose, gx, gy, gb_s, GOLD_PAL)
            else:
                # 升上來之後開始跳舞。左右晃 + 上下彈 + 換腳，
                # 三件事同時做才像在跳，只做一件會像卡住。
                step = (i // 5) % 4
                pose = GB.POSES["walk_a" if step % 2 == 0 else "walk_b"]
                bob = -int(gb_s * 1.6) if step in (1, 3) else 0
                wob = sa._shake(i, gb_s, period=5)
                sa._blit(d, pose, gx + wob, gy + bob, gb_s, GOLD_PAL,
                         flip=step >= 2)
                # 閃光：三顆星輪流在碗身周圍亮，這是「閃閃發亮」那句
                for j in range(3):
                    u = ((i * 0.7) + j * 5) % 15 / 15.0
                    if u > 0.55:
                        continue
                    a = (j / 3.0) * math.tau + i * 0.12
                    px = int(gx + gb_w / 2 + math.cos(a) * gb_w * 0.62)
                    py = int(gy + gb_h / 2 + math.sin(a) * gb_h * 0.52)
                    d.rectangle([px, py, px + gb_s - 1, py + gb_s - 1],
                                fill=PROPS.PAL["W"])

            sa._confetti(d, cols, rows, 11, min(1.0, k * 1.4), 0.56, count=70)

            # 白的那隻先愣一下，再舉刀歡呼。愣的那一拍是笑點，不要砍掉。
            # 金飯碗比白的那隻大一圈，站原位會把它擋掉。讓它往左退開。
            step_back = int(min(1.0, k * 4) * sw * 0.55)
            if k < 0.24:
                # 愣住那一拍靠「不動」表達，不是靠換姿勢 ——
                # 換回 stand 手會垂下來，劍就脫手了。
                sa._blit(d, SP.POSES["cheer"], hero_x - step_back, floor - sh,
                         s, SP.PAL)
                knife(d, True, dx=-step_back)
            else:
                cbob = -s if (i // 5) % 2 == 0 else 0
                sa._blit(d, SP.POSES["cheer"], hero_x - step_back,
                         floor - sh + cbob, s, SP.PAL)
                knife(d, True, dx=-step_back, dy=cbob)

            if k > 0.44:
                # 縮一階、擺到左上角。用原本的大小會壓在白飯碗身上，
                # 兩個東西疊在一起，字讀不出來、角色也看不清楚。
                sa._text_at(im, str(q.get("bonus_text") or "GOLDEN BOWL UNLOCKED!"),
                            int(cols * 0.03), int(rows * 0.06),
                            max(8, round(rows * 0.22)), artwork.YEL)
        out.append(im)
    return out


# ---------------------------------------------------------------- 買一送一
# 客戶 2026-08-18：小飯碗掛著半顆愛心找另一半 → 找到同款 → PERFECT MATCH!
#
# ★ 兩店檔期不同（中港 9/1-2、小北 9/2-3），所以旗幟上的日期是參數，不是圖。
#   改 stores.json 的 params.bogo_date 就好，不必重畫、不必重編另一套美術。
#
# ★ 客戶原文「途中遇到烏龍麵、炸雞、布丁」—— 2026-08-21 這三隻畫好了，
#   放在 food_sprites.PASSERS，順序照原文排。之前是拿另一個主角頂著，
#   三個路人長一樣；現在三個各是各的，「一路找過去都不是」才讀得出來。

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


def _passers(SP, rows, q):
    """三個路人，各自算好姿勢和比例。回傳 [(sprite, 每格幾px, 高度, 配色)]。

    比例要各算各的 —— 咖哩飯 11 列、布丁 17 列，共用一個 s 的話
    矮的會縮成一團、高的會爆出畫布上緣。

    主角本身就是其中一隻的時候（業主拿食物角色當主角試看），
    把撞名的那隻換成沒排到的角色。自己跟自己比對愛心說「not you」很怪。
    """
    spare = [c for c in food_sprites.CROWD]
    out = []
    for c in food_sprites.PASSERS:
        if c is SP and spare:
            c = spare.pop(0)
        pose = c.POSES["stand"]
        s = sa._scale(len(pose), rows, q)
        out.append((pose, s, len(pose) * s, c.PAL))
    return out


CROWD_SCALE = 0.62      # 相對主角。看熱鬧的縮一階，畫面才有前後景


def _crowd(SP, cols, rows, q, keep_out):
    """右半邊看熱鬧的三隻。回傳 [(角色, x, 每格幾px, 高度)]。

    keep_out 是主角這一段會用到的最右邊 —— 人群要站在它右邊。
    最後合體那一拍主角會往右挪，用畫布比例寫死的話會被主角壓掉一隻。

    縮到主角的 62%：一來它們是背景，二來全尺寸三隻根本塞不進剩下的空間。
    位置從右邊往回排，不是寫死的比例 —— 台南 960、中港 1040，
    寫死比例的話中港那台最右邊那隻會被切掉一半。
    """
    chars = [c for c in food_sprites.CROWD if c is not SP] or food_sprites.CROWD
    box = []
    for c in chars:
        pose = c.POSES["stand"]
        s = max(1, round(rows * q["hero_scale"] * CROWD_SCALE / len(pose)))
        box.append((c, s, max(len(r) for r in pose) * s, len(pose) * s))

    right = cols - max(4, int(cols * 0.01))
    used = sum(b[2] for b in box)
    lead = max(1, len(box) - 1)
    gap = max(int(cols * 0.012), (right - keep_out - used) // lead)

    x = max(keep_out, right - used - gap * lead)
    out = []
    for c, s, w, h in box:
        out.append((c, x, s, h))
        x += w + gap
    return out


def render_bogo(cols, rows, p=None):
    """買一送一：帶著半顆愛心找另一半，找到同款，愛心合起來。

    中間那段「失落地坐下」是整段的轉折 ——
    沒有那個低點，後面合起來的那一下就沒有落差，只剩兩隻角色站在一起。
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = sa._ch(q)
    PASS = _passers(SP, rows, q)
    n = artwork.frame_count(q, "bogo")

    spr = SP.POSES["stand"]
    s = sa._scale(len(spr), rows, q)
    sw = max(len(r) for r in spr) * s
    sh = len(spr) * s
    floor = rows - max(1, s)
    gy = floor - sh

    hs_ = max(1, s)
    hw = len(HEART[0]) * hs_
    txt = max(9, round(rows * 0.30))
    mid = cols // 2 - sw

    STOPS = [0.24, 0.44, 0.64]         # 中途停三次比對愛心，把過程攤在畫面上
    # 最後合體那一拍，右邊那隻主角站在 mid + sw + s，身體再佔 sw。
    # 看熱鬧的要站在那之後，不然會被壓掉一隻。
    CROWD = _crowd(SP, cols, rows, q, mid + 2 * sw + 3 * s)
    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.08 + 0.04 * t)
        d = ImageDraw.Draw(im)

        # 看熱鬧的先畫，所以會被主角和另一半蓋過去 —— 它們是背景。
        # 另一半是從右邊走進來的，正好從人群裡穿出來。
        for j, (cc, cx, cs, ch) in enumerate(CROWD):
            if t < 0.86:
                # 站著呼吸。相位各差一點，三隻同時上下會像一起在跳。
                bob = -cs if ((i + j * 9) // 14) % 3 == 0 else 0
                pose = cc.POSES["stand"]
            else:
                # 最後一起歡呼。跟主角同一個節奏，但慢半拍，才像跟著起鬨。
                bob = -cs * 2 if ((i + j * 3) // 5) % 2 == 0 else 0
                pose = cc.POSES["cheer"]
            sa._blit(d, pose, cx, floor - ch + bob, cs, cc.PAL,
                     flip=j % 2 == 1)

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

            # 路人站定不動，主角從他們身邊經過。三個各站一站，各是各的角色。
            for sp, (op, os_, oh, opal) in zip(STOPS, PASS):
                px = int(-sw + (mid + sw) * sp) + sw + int(cols * 0.06)
                sa._blit(d, op, px, floor - oh, os_, opal, flip=True)

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


# ---------------------------------------------------------------- 溫泉蛋加價購
# 客戶 2026-08-09：「10元溫泉蛋加價購：把蛋打進飯碗裡 → 10元升級」
# Mo 2026-08-21：「溫泉蛋君呆萌登場 →『咻！』衝進碗裡 → +10 EGG UPGRADE!」
#
# ★ 呆萌是靠「停」表達的，不是靠表情
#   P4 屏遠看三公尺，表情就是兩顆黑點，畫不出呆。呆是節奏：
#   慢慢晃進來 → 停一下 → 再停一下 → 然後突然全速衝出去。
#   前面停得越久，「咻」那一下越好笑。所以前半段刻意拖，不要覺得空。
#
# ★ 蛋打進去之後不能就這樣結束
#   客戶要的是「升級」，不是「蛋不見了」。所以蛋黃會留在碗上 ——
#   看得到那顆蛋，10 元才有付出去的感覺。

YOLK = [                           # 打進碗裡之後留在飯上的那顆蛋黃
    "..KKKK..",
    ".KYYYYK.",
    "KYYWYYYK",                    # 高光偏左上，跟炸雞同一個方向
    "KYYYYYYK",
    ".KYYYYK.",
    "..KKKK..",
]
YOLK_PAL = {"K": (26, 23, 33), "Y": (247, 179, 43), "W": (255, 253, 246)}


def _speed_lines(d, x, y, w, h, s, colour, count=4):
    """速度線。畫在角色後面，長度不一，不要等長 ——
    等長的四條線在屏上像柵欄，不像快。"""
    for k in range(count):
        yy = y + int(h * (0.22 + 0.18 * k))
        ln = int(w * (0.5 + 0.35 * ((k * 7) % 3)))
        d.rectangle([x - ln, yy, x - s, yy + max(1, s // 2)], fill=colour)


def render_promo_egg(cols, rows, p=None):
    """10 元溫泉蛋：呆萌晃進來 → 停 → 咻！衝進碗裡 → +10 EGG UPGRADE!"""
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = sa._ch(q)
    n = artwork.frame_count(q, "promo_egg")

    EGG = food_sprites.ONSEN_CH
    if EGG is SP:                       # 主角就是溫泉蛋君的話，碗那邊換人
        SP = sa.ricebowl_sprite

    spr = SP.POSES["stand"]
    s = sa._scale(len(spr), rows, q)
    sw = max(len(r) for r in spr) * s
    sh = len(spr) * s
    floor = rows - max(1, s)
    bowl_x = int(cols * 0.30)

    ep = EGG.POSES["stand"]
    es = sa._scale(len(ep), rows, q)
    ew = max(len(r) for r in ep) * es
    eh = len(ep) * es
    egg_from = cols + ew
    egg_to = bowl_x + sw - int(ew * 0.35)

    # 蛋黃比角色小一階，而且要**坐在飯上面**，不是貼在臉上。
    # 第一版跟角色同一個比例、放在身高兩成的位置，結果那顆蛋黃
    # 剛好落在兩顆眼睛中間 —— 看起來像小飯碗長了一顆鼻子。
    ys = max(1, int(s * 0.7))
    yw = len(YOLK[0]) * ys
    yy_off = -int(len(YOLK) * ys * 0.35)          # 稍微露出碗口上緣
    txt = max(9, round(rows * 0.30))

    # 呆萌的三拍：晃進來、停、再往前一點又停。然後才衝。
    T_IN, T_HOLD, T_DASH, T_HIT = 0.30, 0.46, 0.54, 0.60
    STOPS = (0.34, 0.42)

    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.09 + 0.04 * t)
        d = ImageDraw.Draw(im)

        hit = t >= T_HIT

        # --- 碗 ---
        bob = -s if hit and (i // 4) % 2 == 0 else 0
        sa._blit(d, SP.POSES["cheer" if hit else "stand"],
                 bowl_x, floor - sh + bob, s, SP.PAL)
        if hit:
            # 蛋黃落在碗口正上方。小飯碗的配料在最上面三列，
            # 蛋黃壓在那裡才是「打進飯裡」，再低就變成掛在臉上。
            sa._blit_prop(d, YOLK, bowl_x + sw // 2 - yw // 2,
                          floor - sh + yy_off + bob, ys)

        # --- 溫泉蛋君 ---
        if t < T_IN:
            k = t / T_IN
            ex = int(egg_from + (int(cols * 0.72) - egg_from) * k)
            pose = EGG.POSES["walk_a" if (i // 9) % 2 == 0 else "walk_b"]
            sa._blit(d, pose, ex, floor - eh, es, EGG.PAL, flip=True)
        elif t < T_HOLD:
            # 停住發呆。愣的那兩拍靠「完全不動」，換姿勢就不呆了。
            k = (t - T_IN) / (T_HOLD - T_IN)
            ex = int(cols * (0.72 - 0.10 * k))
            still = any(abs(t - sp) < 0.03 for sp in STOPS)
            pose = EGG.POSES["stand"] if still else \
                EGG.POSES["walk_a" if (i // 9) % 2 == 0 else "walk_b"]
            sa._blit(d, pose, ex, floor - eh, es, EGG.PAL, flip=True)
        elif t < T_HIT:
            # 咻！速度線 + 一路衝過去
            k = (t - T_DASH) / (T_HIT - T_DASH) if t >= T_DASH else 0.0
            base = int(cols * 0.62)
            ex = int(base + (egg_to - base) * min(1.0, k))
            _speed_lines(d, ex + ew, floor - eh, ew, eh, es, PROPS.PAL["W"])
            sa._blit(d, EGG.POSES["walk_a"], ex, floor - eh, es, EGG.PAL,
                     flip=True)
        elif t < T_HIT + 0.05:
            # 撞上那一格：蛋不畫（已經進去了），只留衝擊。
            sa._spark(d, bowl_x + sw // 2, floor - sh // 2, sh, s,
                      PROPS.PAL["W"])

        # --- 收尾 ---
        if hit:
            k = (t - T_HIT) / (1 - T_HIT)
            sa._confetti(d, cols, rows, 53, min(1.0, k * 1.6), 0.30, count=60)
            if k > 0.10:
                sa._text_at(im, str(q.get("promo_egg_text") or
                                    "+10   EGG UPGRADE!"),
                            int(cols * 0.52), int(rows * 0.34), txt,
                            artwork.YEL)
        out.append(im)
    return out


# ---------------------------------------------------------------- 開幕全員集合
# 客戶 2026-08-09：「小飯碗角色從左右跑進來，紙花噴一下『飯迎光臨 OKAWARI START！』」
# Mo 2026-08-21：「小飯碗與小勇士帶頭，牛丼、烏龍麵、咖哩、炸雞、布丁、巴斯克
#                 依序跟上 → WELCOME TO OKAWARI!」
#
# ★ 名單上的「牛丼」就是小飯碗本人
#   小飯碗已經帶頭了，後面不能再跟一隻一模一樣的。那個位置給溫泉蛋君 ——
#   結果是八隻角色一個不漏全部到齊，這才是「全員集合」。
#
# ★ 字放上面、角色放下面
#   八隻排開會吃掉整個畫面寬度，字沒地方去。這塊屏是 8:1，
#   把角色縮到六成六、壓在下緣，上面那條剛好塞得下一行字，
#   兩邊都不用讓。買一送一那段字放左邊是因為那裡只有兩隻角色。

def _parade(SP):
    """出場順序，從**前到後**：索引 0 是帶頭的，會站在最右邊。

    帶頭的先跑進來、跑得最遠（停在最右邊），後面的依序停在它左邊。
    這樣「帶頭」在畫面上才是真的在前面 —— 第一版把帶頭的擺在最左邊，
    看起來變成小飯碗被六隻食物推著走。
    """
    lead = [sa.ricebowl_sprite, sa.person_sprite]   # 小飯碗 + 小勇士（人物）
    if SP not in lead:
        lead = [SP] + lead[:1]
    tail = [c for c in (food_sprites.ONSEN_CH, food_sprites.UDON_CH,
                        food_sprites.CURRY_CH, food_sprites.KARAAGE_CH,
                        food_sprites.PURIN_CH, food_sprites.BASQUE_CH)
            if c not in lead]
    return lead + tail


def render_promo_open(cols, rows, p=None):
    """開幕：八隻依序跑進來站成一排 → 紙花 → WELCOME TO OKAWARI!"""
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = sa._ch(q)
    n = artwork.frame_count(q, "promo_open")

    team = _parade(SP)
    # 名單是「前 → 後」，但畫面是由左往右排的，所以排版要倒過來 ——
    # 倒過來之後 lay 的最後一個就是帶頭的，站最右邊。
    # gap 交給 _lineup 自己算（不指定），八隻才會平均攤開吃滿整條屏；
    # 指定固定間距的話會全部擠在左邊，右邊空三成。
    order = list(reversed(team))
    lay = sa._lineup(order, cols, rows, q, scale=0.66, left=0.02, right=0.98)

    # 排不下就整排再縮。八隻的寬度是各自算的，窄畫布會超出去 ——
    # 與其讓最右邊那隻被切掉，不如大家一起小一點。
    scale = 0.66
    while scale > 0.40 and lay[-1][1] + lay[-1][3] > cols - int(cols * 0.02):
        scale -= 0.06
        lay = sa._lineup(order, cols, rows, q, scale=scale,
                         left=0.02, right=0.98)

    floor = rows - max(1, sa._scale(len(SP.POSES["stand"]), rows, q))
    txt = max(9, round(rows * 0.26))

    # 依序跑進來：帶頭的（最右邊，lay 的最後一個）先跑，路也最長。
    STEP, RUN = 0.075, 0.24
    T_ALL = STEP * (len(team) - 1) + RUN          # 全員到齊的時間
    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.08 + 0.05 * t)
        d = ImageDraw.Draw(im)

        for j, (c, x, s, w, h) in enumerate(lay):
            t0 = (len(lay) - 1 - j) * STEP        # 越右邊的越早出發
            k = (t - t0) / RUN
            if k <= 0:
                continue                            # 還沒進場
            if k < 1:
                # 跑進來
                rx = int(-w + (x + w) * k)
                pose = c.POSES["walk_a" if (i // 5) % 2 == 0 else "walk_b"]
                bob = 0
            else:
                # 到位。全員到齊之前站著喘，到齊之後一起跳。
                rx = x
                if t < T_ALL:
                    pose = c.POSES["stand"]
                    bob = -s if ((i + j * 5) // 12) % 4 == 0 else 0
                else:
                    pose = c.POSES["cheer"]
                    bob = -s * 2 if ((i + j * 2) // 5) % 2 == 0 else 0
            sa._blit(d, pose, rx, floor - h + bob, s, c.PAL)

        if t >= T_ALL:
            k = (t - T_ALL) / max(0.01, 1 - T_ALL)
            sa._confetti(d, cols, rows, 61, min(1.0, k * 1.5), 0.5, count=110)
            if k > 0.08:
                # 字壓在上緣。角色縮到六成六就是為了空出這一條。
                s2 = str(q.get("promo_open_text") or "WELCOME TO OKAWARI!")
                m = artwork.text_mask(s2, txt)
                x2 = (cols - m.width) // 2 if m else int(cols * 0.2)
                sa._text_at(im, s2, x2, max(1, int(rows * 0.04)), txt,
                            artwork.YEL)
        out.append(im)
    return out


RENDERERS = {
    "bonus": render_bonus,
    "bogo": render_bogo,
    "promo_egg": render_promo_egg,
    "promo_open": render_promo_open,
}
