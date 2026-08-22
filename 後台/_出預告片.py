#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 預告片 · 一支動畫（不是門頭屏的模擬圖）

    python _出預告片.py            # 出 IG Reels 直式 + 貼文 4:5 兩支
    python _出預告片.py reels

輸出到 ../docs/teaser/。

★ 這支片不是產品照

  最早那版把門頭屏畫成一條發光的橫條、上下掛品牌字，那是規格書的語言 ——
  看的人先看到「一塊螢幕」，才看到裡面有東西。現在整個畫面就是場景，
  沒有框、沒有品牌字、沒有屏：角色直接站在紅橙漸變裡，放到最大。

  角色的畫法完全沒變，還是 food_sprites／ricebowl_sprite 那一套，
  跟真的會上屏的是同一張 sprite。改的只有「怎麼取景」。

★ 整張畫面是同一個像素格

  邏輯畫布 270×480，最後用 NEAREST 放大四倍變成 1080×1920。
  背景、角色、字全部在邏輯畫布上畫完再一起放大。

★ 日期不是貼上去的字，是布條

  一行大字疊在畫面上，不管怎麼排都是「後製加的字」—— 它不屬於那個世界。
  改成小飯碗從地上拉一條布條起來搖，日期寫在布條上：
  它有厚度、會跟著擺、被角色拿在手上，是畫面裡的一個東西。
  布條上的字也是小尺寸的遮罩放大出來的，每一畫都是幾格見方的方塊，
  跟角色同一種顆粒 —— 不是細邊的印刷字。

★ 分鏡（20.000 秒，跟配樂同一個數字）

    0.0-0.4s    全黑
    0.4-6.0s    一顆圓形探照燈在全黑的舞台上掃，一拍閃一下。
                照到誰誰才從黑裡浮出來 —— 其他地方完全看不到底
    6.0-7.5s    ★ 形體顯現：光散開，所有人的輪廓一起浮出來，再沉回去
    7.5-8.0s    黑幕
    8.0s        燈亮（＝配樂第 5 小節，全部樂器進來）
    8.3-13.9s   六位賓客從四面八方走進來，快慢不一、路線不一
    15.1-16.0s  小飯碗從天上砸下來（只有主角是掉下來的）
    16.0s       ★ 落地：畫面震、全員被彈起（＝配樂第 9 小節的重音）
    16.7-20.0s  小飯碗拉起布條搖，紙花，下緣一行小字
"""

import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import artwork              # noqa: E402
import food_sprites as fs   # noqa: E402
import ricebowl_sprite      # noqa: E402
import segment_art as sa    # noqa: E402

OUT = os.path.abspath(os.path.join(HERE, "..", "docs", "teaser"))

FPS = 25
SECONDS = 20.0                     # ＝ teaser_music.DUR
PIXEL = 4                          # 一個邏輯像素放大成幾個實際像素
BEAT = 0.5                         # ＝ teaser_music 的 120 BPM，燈閃的節拍

FORMATS = {
    "reels": (270, 480),           # 1080×1920　IG Reels／限動
    "post": (270, 338),            # 1080×1352　IG 貼文 4:5
}

REVEAL_TEXT = "8/26"               # 布條和下緣小字都用這個

BACK = [fs.ONSEN_CH, fs.CURRY_CH, fs.KARAAGE_CH, fs.BASQUE_CH]
MID = [fs.UDON_CH, fs.PURIN_CH]

BLACK = (0, 0, 0)

# ---------------------------------------------------------------- 節拍
# 全部是 0→1 的比例。乘上 20 秒就是秒數。
T_DARK = 0.02                      # 起手全黑
T_SPOT = 0.30                      # 圓形探照燈掃到這裡
T_CURTAIN = 0.375                  # 形體顯現（T_SPOT→這裡），然後全黑
T_FLOOD = 0.40                     # 燈亮 ＝ 配樂第 5 小節
T_WALK = 0.415                     # 賓客開始走進來
T_DROP, T_LAND = 0.755, 0.80       # 主角砸下來 ＝ 配樂第 9 小節
T_BANNER = 0.835                   # 布條拉起來
LAND_SQUASH = 0.014

# 賓客怎麼進場。(從哪邊, 起點高出定位多少（比例）, 出發時間偏移, 走多久)
#
# ★ 六隻不能用同一組數字算出來
#   一隻一隻等距、等速、從同一邊進來，那是跑馬燈在推東西過去。
#   左右交錯、快慢不一、有的斜斜地從後面走下來 —— 亂一點才像一群人。
ENTRIES = [
    (-1, 0.11, 0.000, 0.128),
    (+1, 0.00, 0.036, 0.098),
    (+1, 0.15, 0.074, 0.136),
    (-1, 0.00, 0.104, 0.092),
    (-1, 0.07, 0.142, 0.118),
    (+1, 0.03, 0.178, 0.104),
]


def _tier(chars, cols, rows, h_frac, floor_frac, spread=(0.02, 0.98)):
    """一層角色。回傳 [(角色, x, 每格幾px, 寬, 高, 地面線)]。

    每一層自己一個比例。同一層裡各隻的列數不一樣（咖哩飯 11 列、
    布丁 17 列），所以是先決定「這一層多高」再各自回推 s ——
    共用一個 s 的話矮的會縮成一團、高的會爆出上緣。
    """
    target = rows * h_frac
    floor = int(rows * floor_frac)
    box = []
    for c in chars:
        pose = c.POSES["stand"]
        s = max(1, round(target / len(pose)))
        box.append((c, s, max(len(r) for r in pose) * s, len(pose) * s))

    x0, x1 = int(cols * spread[0]), int(cols * spread[1])
    used = sum(b[2] for b in box)
    gap = (x1 - x0 - used) // max(1, len(box) - 1)
    out, x = [], x0
    for c, s, w, h in box:
        out.append((c, x, s, w, h, floor))
        x += w + gap
    return out


def _haze_mask(cols, rows, top_frac=0.58, peak=104):
    """下緣那層亮霧的遮罩。由上而下越來越亮。

    畫面下半是一大塊飽和的橘，加上白色的碗 —— 那是一個實心的重量塊，
    整個構圖會被壓在下面。壓一層半透明的暖白把底變淺，畫面才浮得起來。
    只算一次，每一格重複用。
    """
    top = int(rows * top_frac)
    h = rows - top
    col = Image.new("L", (1, h))
    for y in range(h):
        col.putpixel((0, y), int(peak * ((y / max(1, h - 1)) ** 1.5)))
    return top, col.resize((cols, h), Image.BILINEAR)


def _shadow(d, x, w, floor, s, col):
    """腳下一道暗影。角色浮在漸變上會分不出誰站在哪，有影子才有地面 ——
    但不畫地平線，畫了就變成三層階梯。寬度只取角色的四成，貼著腳。"""
    pad = int(w * 0.30)
    d.rectangle([x + pad, floor, x + w - pad, floor + max(1, s // 3)],
                fill=col)


# 手寫的 3×5 像素數字。日期只會用到數字和斜線，所以不必整套字型。
#
# ★ 為什麼不用系統字型縮小再放大
#   縮到 8 px 的「8」已經不成形了，放大只是把糊掉的地方放大。
#   3×5 是像素字的最小可讀單位，每一畫都是實心的一格 ——
#   放大幾倍就是幾格見方的方塊，跟角色是同一種顆粒。
GLYPHS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "/": ("001", "001", "010", "100", "100"),
    ".": ("000", "000", "000", "000", "010"),
    " ": ("000", "000", "000", "000", "000"),
}
GLYPH_W, GLYPH_H, GLYPH_GAP = 3, 5, 1


def _blocky(text, cell):
    """把字排成一張遮罩。cell 是一格畫幾個邏輯像素。"""
    chars = [c for c in text if c in GLYPHS]
    if not chars:
        return None
    cols_ = len(chars) * GLYPH_W + (len(chars) - 1) * GLYPH_GAP
    m = Image.new("L", (cols_ * cell, GLYPH_H * cell), 0)
    d = ImageDraw.Draw(m)
    for k, ch in enumerate(chars):
        ox = k * (GLYPH_W + GLYPH_GAP) * cell
        for gy, row in enumerate(GLYPHS[ch]):
            for gx, v in enumerate(row):
                if v == "1":
                    x0, y0 = ox + gx * cell, gy * cell
                    d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1],
                                fill=255)
    return m


def _blit2(d, spr, ox, oy, sx, sy, pal, flip=False):
    """跟 sa._blit 一樣，但橫向和縱向可以不同倍率。

    ★ 每一格的右下角要算到「下一格的起點減一」，不能用「起點加寬度」。
      sx／sy 是小數，用寬度算會四捨五入，格與格之間多出一條縫，
      角色被切成一條一條的百葉窗。
    """
    w = max(len(r) for r in spr)
    for py, row in enumerate(spr):
        y0 = oy + int(py * sy)
        y1 = max(y0, oy + int((py + 1) * sy) - 1)
        for px, ch in enumerate(row):
            if ch == "." or ch not in pal:
                continue
            cx = (w - 1 - px) if flip else px
            x0 = ox + int(cx * sx)
            x1 = max(x0, ox + int((cx + 1) * sx) - 1)
            d.rectangle([x0, y0, x1, y1], fill=pal[ch])


def _spotlight(cols, rows, u, secs):
    """一顆圓形光斑在舞台上掃，而且一拍閃一下。

    u 是 0→1 的掃動進度，secs 是這一格的絕對秒數（拿來對節拍）。

    ★ 光斑要走過三層
      只左右掃的話永遠只照得到同一排。加上上下漂（週期跟左右不同），
      光斑會繞出一條利薩如曲線，前排後排都會被掃到。

    ★ 閃是「每拍最亮、然後衰減」，不是開關
      硬切開關看起來像壞掉的日光燈。每一拍打一下再暗下去，
      才像探照燈在轉。而且這個拍子跟配樂那顆高音「嗶」是同一個
      120 BPM —— 聲音和畫面同一拍。
    """
    x = cols * (0.5 + 0.40 * math.sin(u * math.tau * 1.6 - math.pi / 2))
    y = rows * (0.50 + 0.15 * math.sin(u * math.tau * 2.7))
    rx, ry = rows * 0.19, rows * 0.145

    m = Image.new("L", (cols, rows), 0)
    ImageDraw.Draw(m).ellipse([x - rx, y - ry, x + rx, y + ry], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(rows * 0.030))

    beat = (secs / BEAT) % 1.0
    gain = max(0.10, 1.0 - beat * 1.7)
    return m.point(lambda v: int(v * gain))


def _drop(d, pose, x, floor, s, w, h, pal, k, flip=False):
    """從畫面上方掉下來。k 是 0→1，到 1 就是站定。

    落下用 k² —— 等速掉下來沒有重量，那是電梯不是跳下來。
    順便拖兩條速度線，這是像素動畫交代「很快」的標準做法。
    """
    y = int(-h + floor * k * k)
    for dx in (int(w * 0.30), int(w * 0.70)):
        y0, y1 = max(0, y - int(h * 1.1)), y
        if y1 > y0:
            d.rectangle([x + dx, y0, x + dx + max(1, s // 3), y1],
                        fill=artwork.WHT)
    sa._blit(d, pose, x, y, s, pal, flip=flip)


def _land(d, pose, x, floor, s, w, h, pal, k, flip=False):
    """落地那一下的擠壓：矮一截、寬一點。k 是 0→1，1 就恢復原狀。"""
    sq = 1.0 - 0.24 * (1.0 - k)
    wide = 1.0 + 0.20 * (1.0 - k)
    _blit2(d, pose, int(x - w * (wide - 1) / 2), int(floor - h * sq),
           s * wide, s * sq, pal, flip)


def _make_banner(cols, rows):
    """一條布：白底、深色描邊、上下各一條紅壓條，中間是塊狀的日期。"""
    # 寬度和高度都收過：布條是拿在主角手上的，不是橫幅廣告。
    # 太寬會把後面兩排整個蓋掉，太高會壓到主角的臉。
    w, h = int(cols * 0.62), int(rows * 0.092)
    im = Image.new("RGB", (w, h), (255, 250, 236))
    d = ImageDraw.Draw(im)
    edge = max(2, h // 11)
    d.rectangle([0, 0, w - 1, h - 1], outline=(26, 23, 33), width=edge)
    bar = max(1, edge // 2)
    d.rectangle([edge, edge, w - 1 - edge, edge + bar], fill=(226, 58, 46))
    d.rectangle([edge, h - 1 - edge - bar, w - 1 - edge, h - 1 - edge],
                fill=(226, 58, 46))

    # 一格 = 內高的五分之一左右（3×5 的字有五列）
    m = _blocky(REVEAL_TEXT, max(2, int((h - edge * 2) * 0.62 / GLYPH_H)))
    if m is not None:
        im.paste(Image.new("RGB", m.size, (26, 23, 33)),
                 ((w - m.width) // 2, (h - m.height) // 2), m)
    return im


def _wave(canvas, ban, x, y, ph, amp):
    """把布條一條一條貼上去，每一條上下錯開 —— 布在擺。

    整張直接貼是一塊硬板子。一次貼四欄（不是一欄），
    48 次貼圖跟 194 次的差別在這支片是兩秒鐘。
    """
    step = 4
    for c0 in range(0, ban.width, step):
        c1 = min(ban.width, c0 + step)
        dy = int(math.sin(c0 * 0.085 + ph) * amp)
        canvas.paste(ban.crop((c0, 0, c1, ban.height)), (x + c0, y + dy))


def frames(cols, rows, n, p=None):
    """整支片的每一格，邏輯尺寸。"""
    sc = artwork.Screen(cols, rows, p)
    SP = ricebowl_sprite                       # 主角固定小飯碗

    # 三層排成三角形：後排四隻橫滿上方、中排兩隻推到左右兩側、
    # 主角最大站正中間最下面。每一層的頭都在前一層上面，誰都沒被蓋掉。
    back = _tier(BACK, cols, rows, 0.085, 0.44, spread=(0.00, 1.00))
    mid = _tier(MID, cols, rows, 0.145, 0.60, spread=(0.00, 1.00))
    guests = back + mid

    hp = SP.POSES["stand"]
    hs = max(1, round(rows * 0.24 / len(hp)))
    hw = max(len(r) for r in hp) * hs
    hh = len(hp) * hs
    hfloor = int(rows * 0.82)                  # 不踩到底，IG 下面兩成有介面
    hero_x = cols // 2 - hw // 2

    shadow = (108, 40, 30)
    black = Image.new("RGB", (cols, rows), BLACK)
    haze_top, haze_mask = _haze_mask(cols, rows)
    haze = Image.new("RGB", (cols, rows - haze_top), (255, 238, 206))

    ban = _make_banner(cols, rows)
    ban_x = cols // 2 - ban.width // 2
    # 布條停在「中排兩隻的頭以下」—— 它是拿在主角手上舉到胸口上方，
    # 不是掛在天上的橫幅。停太高會把烏龍麵哥和布丁妹妹的臉切掉。
    # 0.35 是量出來的：再低一點布條會把主角頭上那層肉片整個蓋掉，
    # 小飯碗就變成一個空白的碗；再高一點會切到布丁妹妹的臉。
    ban_hi = int(max(f - hgt + hgt * 0.35 for _, _, _, _, hgt, f in mid))
    ban_lo = hfloor - int(hh * 0.40)

    # 下緣小字：同一套像素字，一格小一點
    small = _blocky(REVEAL_TEXT, max(2, int(rows * 0.030 / GLYPH_H)))

    out = []
    for i in range(n):
        t = i / n
        secs = t * SECONDS
        base = sc.gradient(phase=0.09 + 0.05 * t)

        # ------------------------------------------------ 全黑
        if t < T_DARK:
            out.append(black.copy())
            continue

        # ------------------------------------------------ 圓形探照燈
        if t < T_SPOT:
            lit = base.copy()
            dl = ImageDraw.Draw(lit)
            for j, (c, x, s, w, h, floor) in enumerate(guests):
                sa._blit(dl, c.POSES["stand"], x, floor - h, s, c.PAL,
                         flip=j % 2 == 1)
            u = (t - T_DARK) / (T_SPOT - T_DARK)
            out.append(Image.composite(lit, black,
                                       _spotlight(cols, rows, u, secs)))
            continue

        # ------------------------------------------------ 形體顯現 → 沉回去
        if t < T_CURTAIN:
            # 光散開成一片很淡的底，所有人的輪廓一起浮出來，再沉回去。
            # 這一拍不給顏色 —— 認得出有幾個人、認不出是誰，才有下一段。
            k = math.sin(((t - T_SPOT) / (T_CURTAIN - T_SPOT)) * math.pi)
            stage = Image.blend(black, base, 0.30)
            ds = ImageDraw.Draw(stage)
            for j, (c, x, s, w, h, floor) in enumerate(guests):
                sa._blit(ds, c.POSES["stand"], x, floor - h, s,
                         dict.fromkeys(c.PAL, (96, 52, 44)), flip=j % 2 == 1)
            out.append(Image.blend(black, stage, k))
            continue

        # ------------------------------------------------ 黑幕
        if t < T_FLOOD:
            out.append(black.copy())
            continue

        # ------------------------------------------------ 燈亮
        flood = (t - T_FLOOD) / 0.014
        if flood < 1.0:
            im = Image.blend(black, base, min(1.0, flood * 2.0))
            out.append(Image.blend(im, Image.new("RGB", (cols, rows),
                                                 (255, 252, 244)),
                                   (1.0 - flood) * 0.85))
            continue

        # ------------------------------------------------ 正片
        im = base
        im.paste(Image.composite(haze, im.crop((0, haze_top, cols, rows)),
                                 haze_mask), (0, haze_top))
        d = ImageDraw.Draw(im)
        cheer = t >= T_LAND

        land = (t - T_LAND) / LAND_SQUASH
        impact = 0.0 <= land < 1.0
        jolt = int((1 - land) * max(1, hs) * 1.6) if impact else 0

        # --- 賓客：從四面八方走進來 ---
        for j, (c, x, s, w, h, floor) in enumerate(guests):
            side, rise, delay, run = ENTRIES[j % len(ENTRIES)]
            k = (t - (T_WALK + delay)) / run
            if k <= 0:
                continue
            flip = side > 0                    # 面向走的方向
            if k < 1.0:
                # 出發點在畫面外，而且比定位高一點 —— 斜斜地走下來，
                # 讀起來就是「從後面走上前」。全部平走會像貼紙在平移。
                m = int(cols * 0.06)
                sx0 = (-w - m) if side < 0 else (cols + m)
                e = 1.0 - (1.0 - k) ** 2       # 收尾放慢，才有走到定位的感覺
                rx = int(sx0 + (x - sx0) * e)
                ry = int(floor - h - rows * rise * (1.0 - e))
                pose = c.POSES["walk_a" if (i // 5) % 2 == 0 else "walk_b"]
                sa._blit(d, pose, rx, ry, s, c.PAL, flip=flip)
                continue

            if cheer:
                pose = c.POSES["cheer"]
                bob = -s * 2 if ((i + j * 2) // 4) % 2 == 0 else 0
            elif impact:
                pose, bob = c.POSES["cheer"], -jolt
            else:
                pose = c.POSES["stand"]
                bob = -s if ((i + j * 7) // 11) % 3 == 0 else 0
            _shadow(d, x, w, floor, s, shadow)
            sa._blit(d, pose, x, floor - h + bob, s, c.PAL, flip=flip)

        # --- 主角：只有它是從天上掉下來的 ---
        if t >= T_DROP:
            k = min(1.0, (t - T_DROP) / (T_LAND - T_DROP))
            if k < 1.0:
                _drop(d, SP.POSES["stand"], hero_x, hfloor, hs, hw, hh,
                      SP.PAL, k)
            elif impact:
                _shadow(d, hero_x, hw, hfloor, hs, shadow)
                _land(d, SP.POSES["stand"], hero_x, hfloor, hs, hw, hh,
                      SP.PAL, land)
                sa._spark(d, hero_x + hw // 2, hfloor,
                          int(hw * (0.5 + land)), max(1, hs // 2), artwork.WHT)
            else:
                bob = -hs * 2 if (i // 4) % 2 == 0 else 0
                _shadow(d, hero_x, hw, hfloor, hs, shadow)
                sa._blit(d, SP.POSES["cheer"], hero_x, hfloor - hh + bob,
                         hs, SP.PAL)

        # --- 收尾：紙花、下緣小字、布條 ---
        if cheer:
            k = (t - T_LAND) / (1 - T_LAND)
            sa._confetti(d, cols, rows, 71, min(1.0, k * 1.3), 0.5, count=170)

        if cheer and small is not None:
            # 下緣一行小字。布條是笑點，這一行是資訊 ——
            # 布條在擺的時候未必每一格都讀得清楚，這一行永遠讀得到。
            sx = (cols - small.width) // 2
            sy = int(rows * 0.94)
            im.paste(Image.new("RGB", small.size, artwork.DARK),
                     (sx + 1, sy + 1), small)
            im.paste(Image.new("RGB", small.size, artwork.WHT), (sx, sy),
                     small)

        if t >= T_BANNER:
            # 從主角身後拉起來，然後開始擺。
            u = min(1.0, (t - T_BANNER) / 0.030)
            y = int(ban_lo + (ban_hi - ban_lo) * (1.0 - (1.0 - u) ** 2))
            amp = max(1, int(rows * 0.008)) if u >= 1.0 else 0
            _wave(im, ban, ban_x, y, secs * 7.0, amp)

        if impact:
            amp = max(2, int(rows * 0.012))
            im = im.transform(im.size, Image.AFFINE,
                              (1, 0, sa._shake(i, amp, 1), 0, 1, amp),
                              resample=Image.NEAREST)
        out.append(im)
    return out


def encode(frames_, wav, path, scale):
    """邏輯畫布 → PNG 序列 → mp4。

    放大一律 NEAREST。用預設的雙線性會把硬邊糊掉，整支片的像素感就沒了。
    yuv420p 是 IG 唯一保證吃的像素格式。
    """
    tmp = tempfile.mkdtemp()
    try:
        for i, im in enumerate(frames_):
            im.resize((im.width * scale, im.height * scale),
                      Image.NEAREST).save(os.path.join(tmp, "f_%05d.png" % i))
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-framerate", str(FPS), "-i", os.path.join(tmp, "f_%05d.png")]
        if wav:
            cmd += ["-i", wav, "-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                "-movflags", "+faststart", path]
        subprocess.run(cmd, check=True)
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)


def main():
    want = set(a.lower() for a in sys.argv[1:]) or set(FORMATS)
    bad = want - set(FORMATS)
    if bad:
        print("沒有這個版位：%s（有的是 %s）"
              % (", ".join(sorted(bad)), ", ".join(sorted(FORMATS))))
        return 2

    os.makedirs(OUT, exist_ok=True)
    n = int(round(SECONDS * FPS))

    import teaser_music
    wav = os.path.join(OUT, "teaser.wav")
    teaser_music.write(wav)
    print("配樂　%.3f 秒　%d BPM　%d 小節　原創 chiptune"
          % (teaser_music.DUR, int(teaser_music.BPM), teaser_music.BARS))

    for key in sorted(want):
        cols, rows = FORMATS[key]
        print("算 %s…（%d 格 %d×%d → %d×%d）"
              % (key, n, cols, rows, cols * PIXEL, rows * PIXEL))
        fr = frames(cols, rows, n)
        path = os.path.join(OUT, "OKAWARI_預告_%s.mp4" % key)
        encode(fr, wav, path, PIXEL)
        print("  %-6s %4.1f 秒  %5.0f KB  %s"
              % (key, n / FPS, os.path.getsize(path) / 1024,
                 os.path.basename(path)))

    print("\n輸出到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
