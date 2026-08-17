#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 四段常駐畫面

業主 2026-08-09 需求：畫面按時段換。
兩個角色：
    人物     person_sprite.py    戴紅帽的小孩，從業主 IG 的像素圖抽出來
    小飯碗   ricebowl_sprite.py  長出手腳的牛丼

    開店 11:00-11:30   布簾打開，睡醒伸懶腰，沿飯粒路徑走到一碗飯
    中午 11:30-14:00   端著熱騰騰的飯慢慢走過，冒 3 個蒸氣符號
    午後 14:00-17:30   躺在食物上睡覺，冒 ZZZ，偶爾翻身
    晚間 17:30-22:30   放下公事包，坐下拿起飯碗

排播時段不寫在這裡 —— 寫在 stores.json 的 when，最後變成節目的
playControl，由卡自己按時鐘播。這裡只負責畫。
"""

from PIL import ImageDraw

import artwork
import person_sprite
import ricebowl_sprite

# 主角是可以換的。stores.json 的 params.character 決定編出來是誰主演，
# 分鏡完全一樣 —— 業主要比較兩個角色時，比的才是角色本身，不是分鏡。
CHARACTERS = {
    "person":   person_sprite,      # 人物（IG 那個戴紅帽的小孩）
    "ricebowl": ricebowl_sprite,    # 小飯碗（長出手腳的牛丼）
}
SP = person_sprite           # 預設，_ch() 會覆寫
PROPS = person_sprite        # 碗、蒸氣這些道具不屬於任何角色，兩邊共用


def _ch(p):
    return CHARACTERS.get(str((p or {}).get("character", "person")), person_sprite)


def _blit(d, spr, ox, oy, s, pal=None, flip=False):
    """把 sprite 畫上去。s 是每格幾個像素。"""
    pal = pal or person_sprite.PAL
    w = max(len(r) for r in spr)
    for sy, row in enumerate(spr):
        for sx, ch in enumerate(row):
            if ch == "." or ch not in pal:
                continue
            x = (w - 1 - sx) if flip else sx
            x0, y0 = ox + x * s, oy + sy * s
            d.rectangle([x0, y0, x0 + s - 1, y0 + s - 1], fill=pal[ch])


def _blit_prop(d, spr, ox, oy, s, _pal=None):
    """畫道具。道具的顏色不跟著角色換。"""
    _blit(d, spr, ox, oy, s, PROPS.PAL)


def _scale(rows, canvas_h, p):
    """角色要多大。跟舊版共用 hero_scale，門市三塊屏才會是同一個比例。"""
    return max(1, round(canvas_h * p["hero_scale"] / rows))


def _walk_frame(i, SP=None):
    """走路兩幀交替。每 6 格換一次腳，跟模擬器的節奏一樣。"""
    SP = SP or person_sprite
    return SP.POSES["walk_a"] if (i // 6) % 2 == 0 else SP.POSES["walk_b"]


# ---------------------------------------------------------------- 中午
def render_noon(cols, rows, p=None):
    """今天也要好好吃飯：端著熱騰騰的飯慢慢走過，冒 3 個蒸氣符號。

    走完整條畫面，頭尾都在畫面外，所以循環接得起來。
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = _ch(q)
    n = artwork.frame_count(q, "noon")

    pose = SP.POSES["hold"]
    ph = len(pose)
    s = _scale(ph, rows, q)
    sw = max(len(r) for r in pose) * s

    bowl_w = len(PROPS.BOWL[0]) * s
    span = cols + sw * 2                      # 從左邊外面走到右邊外面

    out = []
    for i in range(n):
        im = sc.gradient(phase=0.10 + 0.04 * (i / n))
        d = ImageDraw.Draw(im)

        x = int(-sw + span * (i / n))
        y = rows - ph * s - max(1, s)

        # 端著飯走。走路的換腳交給 walk 兩幀，端東西的手勢用 hold，
        # 兩者交替就有「邊走邊端」的感覺，而且不必知道角色內部怎麼拆的。
        spr = pose if (i // 6) % 2 == 0 else _walk_frame(i, SP)
        _blit(d, spr, x, y, s, SP.PAL)

        # 碗端在身體前方
        bx = x + sw - s
        by = y + int(ph * 0.62) * s
        _blit_prop(d, PROPS.BOWL, bx, by, s)

        # 蒸氣：三道，各自相位不同，往上飄
        for k in range(3):
            t = (i * 0.5 + k * 4) % 12
            sy = by - int(t) * s - s
            sx = bx + (k + 1) * 2 * s
            if sy > 0:
                d.rectangle([sx, sy, sx + s - 1, sy + s - 1],
                            fill=PROPS.PAL["W"])
        out.append(im)
    return out


# ---------------------------------------------------------------- 午後
def render_siesta(cols, rows, p=None):
    """午後發呆 Zzz：躺在食物上睡覺，冒 ZZZ，偶爾翻身。"""
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = _ch(q)
    n = artwork.frame_count(q, "siesta")

    pose = SP.POSES["sleep"]
    ph = len(pose)
    s = _scale(ph, rows, q)
    sw = max(len(r) for r in pose) * s

    out = []
    for i in range(n):
        im = sc.gradient(phase=0.06 + 0.03 * (i / n))
        d = ImageDraw.Draw(im)

        x = (cols - sw) // 2
        y = rows - ph * s - max(1, s)

        # 偶爾翻身：整段有兩次，翻身時左右翻面
        flip = (0.42 < (i / n) < 0.58)
        _blit(d, pose, x, y, s, SP.PAL, flip=flip)

        # 底下墊一碗飯
        _blit_prop(d, PROPS.BOWL, x + sw // 2 - len(PROPS.BOWL[0]) * s // 2,
              rows - len(PROPS.BOWL) * s - max(1, s), s)

        # ZZZ 往右上飄，三個字母錯開
        for k in range(3):
            t = ((i * 0.35) + k * 5) % 15
            zx = x + sw + int(t) * s
            zy = y - s + int(t * 0.6) * s
            zy = y - int(t) * s // 2
            if 0 < zy < rows and zx < cols:
                d.rectangle([zx, zy, zx + s - 1, zy + s - 1], fill=PROPS.PAL["W"])
        out.append(im)
    return out


# ---------------------------------------------------------------- 開店
def render_opening(cols, rows, p=None):
    """開店畫面：布簾打開 → 睡醒伸懶腰 → 沿飯粒路徑走 → 抵達一碗飯。

    分四拍。像 8-bit 遊戲開場，所以節奏要有停頓，不能一路平推。
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = _ch(q)
    n = artwork.frame_count(q, "opening")

    pose = SP.POSES["walk_a"]
    ph = len(pose)
    s = _scale(ph, rows, q)
    sw = max(len(r) for r in pose) * s
    gy = rows - ph * s - max(1, s)

    # 終點那碗飯放在右邊 82% 處
    bowl_x = int(cols * 0.82)
    bowl_y = rows - len(PROPS.BOWL) * s - max(1, s)

    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.08 + 0.05 * t)
        d = ImageDraw.Draw(im)

        # 目標那碗飯，全程都在
        _blit_prop(d, PROPS.BOWL, bowl_x, bowl_y, s)

        # 飯粒路徑：一顆一顆亮起來，像遊戲關卡的路標
        walk_from, walk_to = 0.30, 0.88
        for k in range(12):
            gxp = int(cols * 0.10 + k * (bowl_x - cols * 0.10) / 12)
            lit = t > walk_from + (walk_to - walk_from) * (k / 12) - 0.04
            d.rectangle([gxp, gy + ph * s - s, gxp + s - 1, gy + ph * s - 1],
                        fill=PROPS.PAL["W"] if lit else PROPS.PAL["B"])

        if t < 0.18:
            # 第一拍：布簾往兩邊拉開
            k = t / 0.18
            w = int(cols / 2 * (1 - k))
            d.rectangle([0, 0, w, rows], fill=PROPS.PAL["K"])
            d.rectangle([cols - w, 0, cols, rows], fill=PROPS.PAL["K"])
        elif t < 0.30:
            # 第二拍：站在左邊伸懶腰（手舉起來，上下晃一下）
            k = (t - 0.18) / 0.12
            bob = -s if int(k * 6) % 2 else 0
            _blit(d, SP.POSES["cheer"], int(cols * 0.08), gy + bob, s, SP.PAL)
        elif t < 0.88:
            # 第三拍：走過去
            k = (t - 0.30) / 0.58
            x = int(cols * 0.08 + (bowl_x - sw - cols * 0.08) * k)
            _blit(d, _walk_frame(i, SP), x, gy, s, SP.PAL)
        else:
            # 第四拍：抵達，舉手歡呼
            k = (t - 0.88) / 0.12
            bob = -s if int(k * 8) % 2 else 0
            _blit(d, SP.POSES["cheer"], bowl_x - sw, gy + bob, s, SP.PAL)

        out.append(im)
    return out


# ---------------------------------------------------------------- 晚間
def render_evening(cols, rows, p=None):
    """今天辛苦了，吃飯吧：放下公事包，坐下拿起飯碗。"""
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = _ch(q)
    n = artwork.frame_count(q, "evening")

    stand = SP.POSES["walk_a"]
    ph = len(stand)
    s = _scale(ph, rows, q)
    sw = max(len(r) for r in stand) * s
    gy = rows - ph * s - max(1, s)

    mid = int(cols * 0.46)
    bag_w, bag_h = 5 * s, 4 * s

    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.04 + 0.03 * t)
        d = ImageDraw.Draw(im)

        if t < 0.42:
            # 走進來，手上拎著公事包
            k = t / 0.42
            x = int(-sw + (mid + sw) * k)
            _blit(d, _walk_frame(i, SP), x, gy, s, SP.PAL)
            d.rectangle([x + sw, gy + int(ph * 0.72) * s,
                         x + sw + bag_w, gy + int(ph * 0.72) * s + bag_h],
                        fill=PROPS.PAL["K"])
        else:
            # 包放地上，人坐下，碗端起來
            k = (t - 0.42) / 0.58
            d.rectangle([mid + sw, rows - bag_h - max(1, s),
                         mid + sw + bag_w, rows - max(1, s)], fill=PROPS.PAL["K"])
            sit = SP.POSES["sit"]
            drop = int(min(1.0, k * 4) * 3) * s          # 坐下去的那一沉
            _blit(d, sit, mid, rows - len(sit) * s - max(1, s) + 0, s)
            bx = mid - len(PROPS.BOWL[0]) * s
            _blit_prop(d, PROPS.BOWL, bx, rows - len(PROPS.BOWL) * s - max(1, s) - drop, s)
            # 熱氣
            if k > 0.3:
                for kk in range(2):
                    tt = (i * 0.4 + kk * 5) % 10
                    yy = rows - len(PROPS.BOWL) * s - max(1, s) - drop - int(tt) * s
                    if yy > 0:
                        d.rectangle([bx + (kk + 1) * 2 * s, yy,
                                     bx + (kk + 1) * 2 * s + s - 1, yy + s - 1],
                                    fill=PROPS.PAL["W"])
        out.append(im)
    return out


RENDERERS = {
    "opening": render_opening,
    "noon": render_noon,
    "siesta": render_siesta,
    "evening": render_evening,
}
