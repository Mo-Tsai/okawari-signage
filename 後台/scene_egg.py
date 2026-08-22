#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 整點隱藏彩蛋（三組）

業主 2026-08-09／08-21：
    egg1  手電筒巡邏「FOUND YOU!」
    egg2  RICE POWER 血條補滿
    egg3  全角色接力賽

★ 為什麼是三支影片、十一個時段

  stores.json 裡 12:00〜22:00 每個整點各是一個排播項目（egg_12…egg_22），
  但 art 欄位只有 egg1／egg2／egg3 三種，輪流指過去。卡的媒體空間和
  節目數都有限，編十一支一模一樣的東西只是浪費 —— 排播單位跟美術分開，
  就是為了這個。見 compiler.art_of()。

★ 每一段只有 12 秒，而且是「彩蛋」

  彩蛋的重點是路過的人剛好撞見。所以三段都必須在**前兩秒**就讓人知道
  現在發生的事跟平常不一樣：egg1 是整片畫面暗下來，egg2 是憑空多一條血條，
  egg3 是一整排角色衝進來。慢慢鋪陳的開場在這裡沒有用，看的人已經走掉了。

分鏡工具沿用 segment_art，所以角色大小、地面線跟常駐畫面是同一套。
"""

import math

from PIL import Image, ImageDraw

import artwork
import food_sprites
import person_sprite
import ricebowl_sprite
import segment_art as sa

PROPS = sa.PROPS


# ================================================================ egg1
# 手電筒巡邏。業主原文：「小飯碗拿手電筒巡邏，偷偷確認還有沒有人」
#
# 這一段的技術核心是「暗」。artwork 本來就有 RAMP_DIM（38% 亮度），
# 待機畫面沒在用，這裡剛好拿來當夜色 —— 不是另外調一組顏色，
# 是同一條色階壓暗，所以暗下來之後看起來還是同一塊屏，不是換了張圖。
#
# 光錐用 Image.composite 把亮版蓋回暗版上，不是畫一個半透明黃色三角形。
# 畫黃三角形的話光錐裡面會偏黃，看起來像打了一盞黃燈；用 composite
# 是「這一塊沒有變暗」，那才是手電筒。

FLASHLIGHT = [                     # 橫握，光從右邊出去
    ".KKKKK.",
    "KWWWWWK",
    "KWWWWYK",                     # 燈頭那一格是黃的
    "KWWWWWK",
    ".KKKKK.",
]
FLASH_PAL = {"K": (26, 23, 33), "W": (214, 218, 228), "Y": (247, 179, 43)}


def _silhouette(pal):
    """剪影配色：所有顏色壓成同一個暗色。

    躲著的那隻一直在畫面上，只是看不出是誰 —— 有輪廓、沒顏色。
    完全不畫的話「找到了」就變成憑空冒出來一隻，沒有「原來牠在那」。
    """
    return {k: (58, 28, 22) for k in pal}


def render_egg1(cols, rows, p=None):
    """手電筒巡邏：畫面暗下來 → 光錐掃過去 → 照到躲著的那隻 → FOUND YOU!"""
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = sa._ch(q)
    n = artwork.frame_count(q, "egg1")

    # 夜色不變 —— 巡邏的那十二秒裡顏色不該慢慢飄，
    # 而且這樣只算兩次漸變，比其他段還省。
    bright = sc.gradient(phase=0.12)
    night = sc.gradient(phase=0.12, dim=True)

    spr = SP.POSES["walk_a"]
    s = sa._scale(len(spr), rows, q)
    sw = max(len(r) for r in spr) * s
    sh = len(spr) * s
    floor = rows - max(1, s)

    # 躲著的那一隻。主角剛好是牠的話換一隻，不然是自己找自己。
    hide = next(c for c in (food_sprites.PURIN_CH, food_sprites.KARAAGE_CH)
                if c is not SP)
    hp = hide.POSES["stand"]
    hs = sa._scale(len(hp), rows, q)
    hw = max(len(r) for r in hp) * hs
    hh = len(hp) * hs
    hx = int(cols * 0.78)
    dark_pal = _silhouette(hide.PAL)

    fl = max(1, int(s * 0.8))
    txt = max(9, round(rows * 0.30))

    T_FIND = 0.66                  # 光錐掃到牠的時間點
    stop_x = hx - sw - s * 6       # 巡邏走到這裡就停

    out = []
    for i in range(n):
        t = i / n

        # --- 手電筒的位置與角度 ---
        walk = min(1.0, t / T_FIND)
        x = int(-sw + (stop_x + sw) * walk)
        y = floor - sh
        tip_x = x + sw + fl * 4
        tip_y = y + int(sh * 0.42)

        # 掃：光錐上下擺。找到之後定住指著牠 —— 還在擺的話
        # 「照到了」那一拍會被下一次擺動抹掉。
        if t < T_FIND:
            sway = math.sin(t * math.tau * 2.4) * rows * 0.30
        else:
            sway = (hh * -0.5) + (floor - tip_y)

        # --- 光錐 ---
        mask = Image.new("L", (cols, rows), 0)
        md = ImageDraw.Draw(mask)
        reach = cols * (0.62 if t < T_FIND else 1.10)
        spread = rows * (0.42 if t < T_FIND else 0.62)
        md.polygon([(tip_x, tip_y),
                    (tip_x + reach, tip_y + sway - spread),
                    (tip_x + reach, tip_y + sway + spread)], fill=255)

        if t > 0.88:
            # 找到之後燈整個亮起來，畫面回到白天。
            # 這一拍是給「彩蛋結束、回常駐」一個交代，不是硬切。
            md.rectangle([0, 0, cols, rows], fill=255)

        im = Image.composite(bright, night, mask)
        d = ImageDraw.Draw(im)

        # --- 躲著的那一隻 ---
        found = t >= T_FIND
        if found:
            # 被抓到，嚇一跳：往上彈 + 左右抖
            k = (t - T_FIND) / (1 - T_FIND)
            hop = -int(math.sin(min(1.0, k * 3.0) * math.pi) * hh * 0.30)
            wob = sa._shake(i, hs, period=3)
            sa._blit(d, hide.POSES["cheer"], hx + wob, floor - hh + hop,
                     hs, hide.PAL)
        else:
            sa._blit(d, hp, hx, floor - hh, hs, dark_pal)

        # --- 巡邏的主角 ---
        pose = SP.POSES["cheer" if found else
                        ("walk_a" if (i // 7) % 2 == 0 else "walk_b")]
        sa._blit(d, pose, x, y, s, SP.PAL)
        sa._blit(d, FLASHLIGHT, x + sw - s, tip_y - fl * 2, fl, FLASH_PAL)

        if found:
            sa._text_at(im, str(q.get("egg1_text") or "FOUND YOU!"),
                        int(cols * 0.06), int(rows * 0.16), txt, artwork.YEL)
            sa._spark(d, hx + hw // 2, floor - hh // 2, hh, hs, PROPS.PAL["W"])
        out.append(im)
    return out


# ================================================================ egg2
# RICE POWER。業主原文：「飯碗一碗接一碗堆高（堆長），像遊戲能力值上升」
#
# 「堆高」在 120 px 高的屏上堆不了幾碗就頂到天花板 ——
# 所以照原文括號裡那個字做：**堆長**。一條橫的血條吃滿 8:1 的畫面，
# 而且血條本來就是「能力值上升」最好懂的視覺語言，不用解釋。
#
# 血條的填色走品牌那條紅→橘→黃色階：越滿越黃。
# 用單一顏色的話，滿與不滿只差長度，遠看不夠有感。

CELLS = 8                          # 血條分幾格。一格一碗


def _bar_geom(cols, rows):
    """血條的位置與大小。回傳 (x, y, 寬, 高, 邊框粗細)。

    邊框刻意粗（4.5% 屏高）。血條的填色走的是品牌那條紅→橘→黃，
    跟背景是同一組顏色 —— 填到右邊的黃格會整片融進背景。
    粗黑框的作用不是裝飾，是給每一格一個深色的底，
    黃色才有東西可以壓。第一版框只有 3 px，右半條看不見。
    """
    bw = int(cols * 0.56)
    bh = max(8, int(rows * 0.30))
    return int(cols * 0.40), int(rows * 0.30), bw, bh, max(2, int(rows * 0.045))


def _lift(col, by=52):
    """把顏色提亮。填色格的上緣壓一條亮的，才有厚度。"""
    return tuple(min(255, v + by) for v in col)


def render_egg2(cols, rows, p=None):
    """RICE POWER：一碗一碗飛進血條，填滿之後全屏閃一下。"""
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = sa._ch(q)
    n = artwork.frame_count(q, "egg2")

    spr = SP.POSES["stand"]
    s = sa._scale(len(spr), rows, q)
    sw = max(len(r) for r in spr) * s
    sh = len(spr) * s
    floor = rows - max(1, s)
    hero_x = int(cols * 0.06)

    bx, by, bw, bh, bd = _bar_geom(cols, rows)
    cell = (bw - bd * 2) // CELLS

    bs = max(1, int(s * 0.9))                      # 飛過來的那碗多大
    bwid = len(PROPS.BOWL[0]) * bs
    bhei = len(PROPS.BOWL) * bs

    txt = max(9, round(rows * 0.28))
    label = max(8, round(rows * 0.20))

    T_FILL, T_FLASH = 0.74, 0.82   # 填完 / 閃白
    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.10 + 0.04 * t)
        d = ImageDraw.Draw(im)

        # --- 血條外框 ---
        d.rectangle([bx, by, bx + bw, by + bh], fill=PROPS.PAL["K"])
        d.rectangle([bx + bd, by + bd, bx + bw - bd, by + bh - bd],
                    fill=(78, 34, 26))             # 空槽：比背景暗，才看得出是槽

        # --- 已經填了幾格 ---
        prog = min(1.0, t / T_FILL)
        full = int(prog * CELLS)
        part = prog * CELLS - full                 # 正在填的那一格填了多少

        for c in range(full + 1):
            if c >= CELLS:
                break
            w = cell - max(1, bd) if c < full else int((cell - max(1, bd)) * part)
            if w <= 0:
                continue
            # 顏色照這一格在整條裡的位置取色階：左紅右黃
            u = (c + 0.5) / CELLS
            col = tuple(artwork.RAMP[min(255, int(u * 255))])
            x0 = bx + bd + c * cell
            d.rectangle([x0, by + bd, x0 + w, by + bh - bd], fill=col)
            # 上緣一條亮的。沒有這條，整格是一片平的色塊，
            # 遠看跟背景分不開；有了就讀得出「這一格是滿的」。
            d.rectangle([x0, by + bd, x0 + w, by + bd + max(1, bd // 2)],
                        fill=_lift(col))

        # --- 正在飛過來的那一碗 ---
        if t < T_FILL and full < CELLS:
            # 每一格一碗。碗從主角手上拋出去，落在正在填的那一格。
            k = part
            tx = bx + bd + full * cell + cell // 2 - bwid // 2
            sx = hero_x + sw
            fx = int(sx + (tx - sx) * k)
            arc = -int(math.sin(k * math.pi) * rows * 0.42)
            fy = int((floor - sh * 0.6) + (by + bh // 2 - (floor - sh * 0.6)) * k)
            sa._blit_prop(d, PROPS.BOWL, fx, fy + arc, bs)

        # --- 主角：一直在丟碗，填滿之後歡呼 ---
        done = t >= T_FILL
        bob = -s if (i // 4) % 2 == 0 and done else 0
        sa._blit(d, SP.POSES["cheer" if done else "hold"],
                 hero_x, floor - sh + bob, s, SP.PAL)

        # --- 標籤與收尾 ---
        # 滿了之後直接把標籤換成 MAX，不另外放一行大字 ——
        # 這塊屏上血條已經佔掉右邊六成，大字只能壓在血條上，兩個都讀不到。
        # 標籤本來就在看的人眼睛會去的地方（血條正上方），換字最有效。
        if t >= T_FLASH:
            # 閃是換顏色，不是一閃一滅。滅掉那半拍字整個不見，
            # 停格看會像壞掉 —— 黃白交替一樣有閃的感覺，字一直讀得到。
            sa._text_at(im, str(q.get("egg2_text") or "RICE POWER MAX!"),
                        bx, by - txt - max(2, bd), txt,
                        artwork.YEL if (i // 4) % 2 == 0 else artwork.WHT)
        else:
            sa._text_at(im, "RICE POWER", bx, by - label - max(2, bd),
                        label, artwork.WHT)

        if T_FLASH > t >= T_FILL:
            # 填滿到閃白之間留一拍。滿了就馬上閃，看的人會覺得沒滿就閃了。
            sa._spark(d, bx + bw, by + bh // 2, bh * 2, bd, PROPS.PAL["W"])
        elif t >= T_FLASH:
            k = (t - T_FLASH) / (1 - T_FLASH)
            if k < 0.10:
                im.paste(Image.new("RGB", (cols, rows), PROPS.PAL["W"]))
            else:
                sa._confetti(d, cols, rows, 31, min(1.0, (k - 0.10) * 2.2),
                             0.5, count=80)
        out.append(im)
    return out


# ================================================================ egg3
# 全角色接力賽。
#
# 八隻角色排成一列往右跑，飯碗當接力棒，從隊伍最後面一棒一棒往前傳，
# 最後一棒衝過終點線。
#
# ★ 為什麼是「跑過去」不是「跑進來排好」
#   跑進來排好那是開幕的全員集合（promo_open）。兩段都是八隻角色，
#   如果連動線都一樣，客人會覺得是同一支影片播了兩次。
#   接力賽是橫向的、有終點線、跑出畫面外；集合是走進來、停下、面向前。

BATON_HOLD = 0.11                  # 一棒佔整段時間的幾成


def _relay_team(SP):
    """跑者名單，順序是**從後到前**：索引 0 是最後一棒（最左邊），
    最後一個是第一棒（最右邊、衝線的那位，也就是主角）。

    這個順序不是隨便定的。_lineup 是由左往右排的，而接力棒要從隊伍後面
    往前傳 —— 名單順序跟畫面順序對齊，傳棒就只是索引 +1。
    兩套順序要換算的地方，就是之後會把棒子傳錯方向的地方。
    """
    rest = [person_sprite, ricebowl_sprite] + list(food_sprites.FOODS.values())
    rest = [c for c in rest if c is not SP]
    return rest + [SP]


def render_egg3(cols, rows, p=None):
    """接力賽：八隻排成一列往右跑，飯碗一棒一棒往前傳，衝過終點線。"""
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = sa._ch(q)
    n = artwork.frame_count(q, "egg3")

    team = _relay_team(SP)
    # 縮到六成五。八隻全尺寸排一列有一千多 px，960 的畫布裝不下，
    # 而且跑者本來就該比單獨出場時小一點 —— 一群人跑過去是遠景。
    lay = sa._lineup(team, cols, rows, q, scale=0.65,
                     gap=max(4, int(cols * 0.022)))
    pack = lay[-1][1] + lay[-1][3] - lay[0][1]

    floor = rows - max(1, sa._scale(len(SP.POSES["stand"]), rows, q))
    bs = max(1, int(rows * 0.18 / len(PROPS.BOWL)))
    bwid = len(PROPS.BOWL[0]) * bs

    line_x = int(cols * 0.80)      # 終點線
    lw = max(3, int(cols * 0.010))
    txt = max(9, round(rows * 0.30))

    # 隊伍從整包在畫面外跑進來，**減速停在終點線後面**，不是跑出畫面外。
    # 第一版是一路跑出去的，結果最後三秒畫面上一個人都沒有，
    # 只剩 GOAL! 掛在空的橘色上 —— 衝線的那一下沒有人在畫面裡。
    start = -pack - int(cols * 0.04)
    end = line_x + int(cols * 0.03) - (lay[-1][1] + lay[-1][3])

    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.10 + 0.04 * t)
        d = ImageDraw.Draw(im)

        # --- 終點線：黑白格，畫在角色後面 ---
        blk = max(2, int(rows * 0.10))
        for yy in range(0, rows, blk):
            col = PROPS.PAL["W"] if (yy // blk) % 2 == 0 else PROPS.PAL["K"]
            d.rectangle([line_x, yy, line_x + lw, yy + blk - 1], fill=col)

        # 減速：越接近終點跑得越慢，最後幾格幾乎停住。
        # 等速跑到底再硬停會像影片卡住，先減速才像「衝線之後煞車」。
        u = 1.0 - (1.0 - min(1.0, t / 0.88)) ** 2
        shift = int(start + (end - start) * u) - lay[0][1]

        # --- 接力棒在誰手上 ---
        # 從隊伍最後面（索引 0、最左邊）往前傳到第一棒（索引 -1）。
        # 傳到最後一棒就一直在他手上衝終點。
        leg = min(len(team) - 1, int(t / BATON_HOLD))
        holder = leg
        handing = (t / BATON_HOLD - leg) > 0.72 and holder < len(team) - 1

        for j, (c, x, s, w, h) in enumerate(lay):
            rx = x + shift
            if rx + w < 0 or rx > cols:
                continue
            # 跑步：換腳 + 一格上下，兩件事一起才像在跑不是在滑
            step = (i // 4 + j) % 2
            pose = c.POSES["walk_a" if step == 0 else "walk_b"]
            bob = -s if step == 0 else 0
            sa._blit(d, pose, rx, floor - h + bob, s, c.PAL)

            if j == holder and not handing:
                sa._blit_prop(d, PROPS.BOWL, rx + w - bwid // 2,
                              floor - h + int(h * 0.34) + bob, bs)

        if handing:
            # 交棒的那一拍：碗在兩隻中間飛。
            # 沒有這一拍的話碗會憑空從一隻手上跳到另一隻手上。
            k = (t / BATON_HOLD - leg - 0.72) / 0.28
            a = lay[holder]
            b = lay[holder + 1]
            ax = a[1] + shift + a[3] - bwid // 2
            bx2 = b[1] + shift + b[3] - bwid // 2
            fx = int(ax + (bx2 - ax) * k)
            fy = floor - a[4] + int(a[4] * 0.34) - int(math.sin(k * math.pi) * rows * 0.22)
            sa._blit_prop(d, PROPS.BOWL, fx, fy, bs)

        # --- 第一棒過線 ---
        lead_x = lay[-1][1] + shift + lay[-1][3]
        if lead_x > line_x:
            k = min(1.0, (lead_x - line_x) / max(1.0, cols * 0.16))
            sa._confetti(d, cols, rows, 43, k, 0.80, count=70)
            sa._text_at(im, str(q.get("egg3_text") or "GOAL!"),
                        int(cols * 0.06), int(rows * 0.18), txt, artwork.YEL)
        out.append(im)
    return out


RENDERERS = {
    "egg1": render_egg1,
    "egg2": render_egg2,
    "egg3": render_egg3,
}
