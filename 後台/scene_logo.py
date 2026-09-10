#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 整點 LOGO 跑燈

業主 2026-09-10：「每一個小時跑一次 logo，照他的綠底 logo 字。」

★ 素材是業主的原始檔，不是我們重畫的
  `素材/okawari_logo.png`（＝ `LOGO/OKAWARI LOGO_工作區域 1.png` 的複本）。
  底色、紅、金、白都從那張圖上**取樣**出來，沒有一個顏色是這裡手打的 ——
  手打的色號跟業主的品牌手冊一定會慢慢飄掉，而屏上飄掉沒有人會發現。
  複製一份進 `素材/` 是為了讓後台自己站得住：門頭屏這一包有自己的 git，
  往上兩層的 `LOGO/` 不在裡面，搬資料夾就會斷。

★ 為什麼是「滑進來 → 停住 → 滑出去」，不是等速跑過去
  8:1 的屏，logo 等比放到快滿版高度也只佔三成寬。等速跑過去的話，
  它在可讀位置只停留一兩秒，賣場走過去的人根本來不及看完。
  停住那幾秒才是這支的目的 —— 跑燈只是把人的眼睛帶過來。
  要純跑燈就把 `logo_hold` 設 0。

★ 為什麼頭尾一定要留空綠
  這支在卡上是 count=999（跟時段畫面同一個機制，見 後台/schedule.py）：
  窗還開著它就一直重播。所以第一幀和最後一幀都必須是「乾淨的綠底」——
  這樣接回去看起來就只是綠底停了一下，不會看到 logo 突然跳回右邊。
  卡在窗到期時把畫面切走，也一定切在綠底上。

★ 尺寸全部從 rows 推
  這一支要同時出 960×120、1040×120，以後可能還有別的畫布。
  寫死像素會在小畫布上糊成一坨、在大畫布上看不見（見 skill: led-panel-art）。
"""

import os

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

import artwork

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_PNG = os.path.join(HERE, "素材", "okawari_logo.png")

# 取樣結果快取。同一次編譯要出好幾家店，圖只讀一次。
_CACHE = {}


def _load_logo():
    """讀業主的 logo，回傳 (去背後的 RGBA、底色 RGB)。

    去背的做法是「跟四個角同色的就是背景」。logo 是純色去背的向量輸出，
    邊緣有一點點反鋸齒，所以容差開到 18 —— 太嚴會在字的外緣留一圈綠邊，
    太鬆會把 logo 裡面深色的部分也吃掉。
    """
    if "logo" in _CACHE:
        return _CACHE["logo"]
    if not os.path.exists(LOGO_PNG):
        raise IOError("找不到 logo 素材：%s\n"
                      "  從 專案根目錄/LOGO/ 複製一份過去。" % LOGO_PNG)

    src = Image.open(LOGO_PNG).convert("RGB")
    bg = src.getpixel((1, 1))

    # 背景遮罩：跟底色差很少的畫素 → 透明。
    # 用 ImageChops 整張一次算完，不要逐畫素跑迴圈 —— 這張圖 2153×2153，
    # 純 Python 迴圈要跑掉半分鐘，而它每編一家店就會被叫一次。
    flat = Image.new("RGB", src.size, bg)
    diff = ImageChops.difference(src, flat).convert("L")
    alpha = diff.point(lambda v: 255 if v > 18 else 0)

    rgba = src.copy()
    rgba.putalpha(alpha)
    box = alpha.getbbox()               # 只留有東西的那一塊
    if box:
        rgba = rgba.crop(box)
    _CACHE["logo"] = (rgba, bg)
    return _CACHE["logo"]


def _ease_out(t):
    """快進慢停。滑進來用這個，煞車感才像有重量。"""
    return 1.0 - (1.0 - t) ** 3


def _ease_in(t):
    """慢起快出。滑出去用這個。"""
    return t ** 3


def _shine(logo, k, width_frac):
    """在 logo 上掃一道亮帶，回傳新的 RGBA。

    只提亮 logo 自己的畫素，綠底完全不碰 —— 連底一起閃在 LED 上會變成
    整片跳一下，遠看像訊號不良。亮帶是斜的，寬度照 logo 寬度算。
    """
    w, h = logo.size
    band = max(2, int(w * width_frac))
    # k：0 → 亮帶在左邊界外，1 → 在右邊界外
    cx = -band + k * (w + 2 * band)

    # 亮帶做成一張遮罩，再用 composite 把「提亮版」蓋回原圖。
    # 逐畫素改顏色也做得到，但那是 300×100 × 上百幀的迴圈，白等。
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    slant = h * 0.6
    d.polygon([(cx - band * 0.5 + slant, 0), (cx + band * 0.5 + slant, 0),
               (cx + band * 0.5 - slant, h), (cx - band * 0.5 - slant, h)],
              fill=255)
    # 邊緣要糊掉。硬邊的亮帶在紅字上會變成一條「換了顏色的直線」，
    # 遠看不像反光，像色塊破圖。
    mask = mask.filter(ImageFilter.GaussianBlur(max(1.0, band * 0.30)))
    # logo 以外的地方不准亮：跟 alpha 取交集，綠底完全不動
    mask = ImageChops.multiply(mask, logo.getchannel("A"))

    bright = ImageEnhance.Brightness(logo.convert("RGB")).enhance(1.28)
    out = Image.composite(bright, logo.convert("RGB"), mask)
    out.putalpha(logo.getchannel("A"))
    return out


def render_logo(cols, rows, p=None):
    """整點 LOGO 跑燈：綠底，logo 從右邊滑進來、停住、往左滑出去。"""
    q = artwork.params(p)
    n = artwork.frame_count(q, "logo")

    logo, bg = _load_logo()

    # ---- 尺寸：照畫布高度算，不寫死 ----
    lh = max(8, int(round(rows * float(q.get("logo_height", 0.82)))))
    lw = max(8, int(round(logo.width * lh / logo.height)))
    logo = logo.resize((lw, lh), Image.LANCZOS)
    ly = (rows - lh) // 2

    base = Image.new("RGB", (cols, rows), bg)

    # ---- 時間軸（都是整支長度的比例）----
    pad = float(q.get("logo_pad", 0.06))        # 頭尾各留多少空綠
    hold = float(q.get("logo_hold", 0.28))      # 停在中間多久
    move = max(0.02, (1.0 - 2 * pad - hold) / 2.0)   # 滑進、滑出各多久
    t_in0, t_in1 = pad, pad + move
    t_hd1 = t_in1 + hold
    t_ot1 = t_hd1 + move

    x_right = cols                    # 完全在右邊界外
    x_mid = (cols - lw) // 2
    x_left = -lw                      # 完全在左邊界外

    shine_w = float(q.get("logo_shine", 0.16))  # 亮帶寬度（佔 logo 寬），0 = 關掉

    out = []
    for i in range(n):
        t = i / float(max(1, n))
        im = base.copy()

        if t < t_in0 or t >= t_ot1:
            out.append(im)            # 乾淨的綠底：頭尾各一段
            continue

        art = logo
        if t < t_in1:
            k = _ease_out((t - t_in0) / move)
            x = int(round(x_right + (x_mid - x_right) * k))
        elif t < t_hd1:
            x = x_mid
            if shine_w > 0:
                # 停住那幾秒掃兩道亮帶，中間空一拍
                k = (t - t_in1) / hold
                if k < 0.34:
                    art = _shine(logo, k / 0.34, shine_w)
                elif k > 0.60:
                    art = _shine(logo, (k - 0.60) / 0.40, shine_w)
        else:
            k = _ease_in((t - t_hd1) / move)
            x = int(round(x_mid + (x_left - x_mid) * k))

        im.paste(art, (x, ly), art)
        out.append(im)
    return out


RENDERERS = {"logo": render_logo}
