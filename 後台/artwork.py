#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 美術層

主要是 `OKAWARI 門頭屏模擬器 v1.0.html` 的移植：sprite、配色、勇者走路節奏、
劈石流程都照原設計。跟模擬器不同的地方都是 Mo 2026-08-10 當面指定的：

  1. 背景不再是三角波（紅→黃→紅 在空間上來回衝），改成固定的一段漸變，
     顏色只在時間上很慢地變。模擬器原本是 pos<0.5 ? pos*2 : (1-pos)*2。
  2. 多了一個壞人。巡迴不是勇者自己走過去，而是勇者追著壞人跑，
     而且兩個要同時在畫面上。
  3. 動作整體放慢，節奏以模擬器為準再慢一點。

輸出是 PNG 幀序列，由 compiler.py 打包成動畫 GIF 送進卡裡。
畫布尺寸完全由參數決定，所以同一份設計可以編出 960×120、1040×120，
測試卡則是 960×120 等比縮 1/3 之後裁出來的一個視窗。
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

# 中獎時閃的字，跟模擬器一樣
TEXT_HIT = "おかわり おめでとう!"
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msgothic.ttc",   # 模擬器用的就是 MS Gothic
    r"C:\Windows\Fonts\YuGothM.ttc",
    r"C:\Windows\Fonts\YuGothR.ttc",
]


def _font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return None


def text_mask(s, size):
    """把字轉成硬邊的點陣遮罩。

    模擬器是把字畫進離屏 canvas 再取 alpha>110 當作亮點，
    這裡照做 —— 不留半透明邊緣，才會是像素風而不是糊掉的字。
    """
    f = _font(size)
    if not f:
        return None
    bbox = f.getbbox(s)
    w, h = max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])
    im = Image.new("L", (w + 2, h + 2), 0)
    ImageDraw.Draw(im).text((1 - bbox[0], 1 - bbox[1]), s, font=f, fill=255)
    return im.point(lambda v: 255 if v > 110 else 0)

# ---------------------------------------------------------------- 品牌色
RED = (226, 58, 46)
ORG = (240, 120, 24)
YEL = (247, 179, 43)
WHT = (255, 253, 246)
STEEL = (214, 218, 228)
DARK = (26, 23, 33)

# ---------------------------------------------------------------- 勇者
SPR_A = [
    "....KKKK....", "..KKWWWWKK..", ".KWWWWWWWWK.", ".KWWWWWWWWK.",
    "KRRRRRRRRRRK", ".KWWKWWKWWK.", ".KWWWWWWWWK.", ".KWWWKKWWWK.",
    "..KKWWWWKK..", "...KOOOOK...", "..KOOOOOOK..", "...KK..KK...",
]
SPR_B = SPR_A[:11] + ["..KK....KK.."]
SPC = {"K": DARK, "W": WHT, "R": RED, "O": ORG}

SWORD_READY = [(11, 6, "G"), (12, 6, "S"), (13, 6, "S"),
               (14, 6, "S"), (15, 6, "S"), (16, 6, "S")]
SWORD_SLASH = [(11, 7, "G"), (12, 8, "S"), (13, 9, "S"),
               (14, 10, "S"), (15, 11, "S")]
SWC = {"S": STEEL, "G": YEL}

# ---------------------------------------------------------------- 壞人
# 兜帽黑影、紅眼睛、手上一把暗色的刀。刻意用跟勇者同一個 12 格網格，
# 這樣角色縮放的公式一套就同時管兩個人。
VIL_A = [
    "....DDDD....", "...DDDDDD...", "..DDEDDEDD..", "..DDDDDDDD..",
    ".DDDDDDDDDD.", ".DDDDDDDDDD.", ".DDDDDDDDDD.", "..DDDDDDDD..",
    "..DDD..DDD..", "...DD..DD...", "...DD..DD...", "..DD....DD..",
]
VIL_B = VIL_A[:8] + ["..DDD..DDD..", "...DD..DD...", "..DD....DD..", ".DD......DD."]
VLC = {"D": (34, 27, 38), "E": (255, 72, 48)}

BLADE = [(-1, 5, "B"), (-2, 5, "B"), (-3, 6, "B"), (-4, 6, "B"), (-5, 7, "B")]
BLC = {"B": (128, 66, 62)}

STONE = ["..SSSS..", ".SSSSDS.", "SSWSSSDS", "SSSSDSSS", ".SDSSSS.", "..SSSS.."]
STC = {"S": (148, 150, 160), "D": (92, 94, 104), "W": (205, 208, 218)}

# ---------------------------------------------------------------- 色階查表
RAMP, RAMP_DIM = [], []
for _i in range(256):
    _t = _i / 255.0
    if _t < 0.5:
        _u = _t * 2
        _c = tuple(RED[k] + (ORG[k] - RED[k]) * _u for k in range(3))
    else:
        _u = (_t - 0.5) * 2
        _c = tuple(ORG[k] + (YEL[k] - ORG[k]) * _u for k in range(3))
    RAMP.append(bytes(int(v) for v in _c))
    RAMP_DIM.append(bytes(int(v * 0.38) for v in _c))


# ---------------------------------------------------------------- 可調參數
# 這些都是「要用眼睛看了才知道對不對」的值，所以開放在後台調，不寫死。
# 改成 GIF 之後幀率不再被卡的 0.1 秒下限綁住，可以直接照模擬器的手感給。
DEFAULT_PARAMS = {
    "idle_seconds": 30,      # 畫布：一輪幾秒
    "idle_fps": 2,           # 畫布只是慢慢變色，不需要高幀率
    "idle_scroll": 0,        # 漸層跑動：一輪跑幾趟。0 = 不跑，只在原地慢慢變色
                             # （模擬器原本是會跑的，Mo 說看了不舒服，所以預設關掉）
    "patrol_every_minutes": 0,   # 整點巡迴自動觸發的間隔，0 = 不自動
    "patrol_seconds": 12,    # 整點巡迴：追逐全程幾秒
    "patrol_fps": 25,        # 25 fps 就是模擬器的流暢度
    "okawari_seconds": 8,    # 促銷活動（續碗）：幾秒
    "okawari_fps": 25,
    "okawari_hit_chance": 0.25,   # 續碗中獎機率，模擬器的 stoneChance 就是 0.25
    "okawari_text": TEXT_HIT,     # 中獎時閃的字，可以改

    "patrol_gap": 30,        # 巡迴：勇者落後壞人幾個身位單位
    "okawari_stone": 0.55,   # 續碗：石頭放在畫面幾成的位置
    "gradient_window": 0.72,  # 漸變一次用掉多少色階，越小顏色跨度越窄
    "dither": 0.22,          # 顆粒強度，0 就是完全乾淨的漸層
    "hero_scale": 0.72,      # 角色佔畫面高度的比例

    # 小飯碗的四段常駐（業主 2026-08-09 需求）。時段本身寫在 stores.json 的 when，
    # 這裡只管每一段多長、多流暢。
    "noon_seconds": 16, "noon_fps": 25,
    "siesta_seconds": 20, "siesta_fps": 12,     # 睡覺不用高幀率
    "opening_seconds": 14, "opening_fps": 25,
    "evening_seconds": 16, "evening_fps": 25,
}


def params(p=None):
    return {**DEFAULT_PARAMS, **(p or {})}


def frame_count(p, key):
    q = params(p)
    return max(1, int(round(q["%s_seconds" % key] * q["%s_fps" % key])))


def frame_delay_ms(p, key):
    """GIF 每幀間隔，毫秒。"""
    return max(20, int(round(1000.0 / params(p)["%s_fps" % key])))


class Screen:
    """一塊畫布。尺寸相關的量全部從 cols/rows 推出來，跟模擬器同一套公式。"""

    def __init__(self, cols, rows, p=None):
        self.p = params(p)
        self.cols = cols
        self.rows = rows
        self.scale = max(1, round(rows * self.p["hero_scale"] / 12))
        self.sh = 12 * self.scale
        self.stone_h = 6 * self.scale
        d = self.p["dither"]
        self.dither = [((k / 17.0) - 0.5) * d for k in range(17)]

    def gradient(self, phase=0.0, dim=False):
        """一段紅→黃的漸變，空間上固定不動。

        Mo 2026-08-10：「顏色這樣推著跑」看了不舒服，一定要拿掉。
        所以漸變不在空間上捲動；phase 只是把整片取用的色階區間整體平移一點點，
        效果是全屏顏色一起慢慢變，而不是有東西橫著衝過去。

        保留模擬器的 ordered dither 顆粒，那是像素風質感的來源，
        也順便避免 LED 上出現整齊的色帶。
        """
        cols, rows = self.cols, self.rows
        ramp = RAMP_DIM if dim else RAMP
        span = max(1, cols - 1)
        win = self.p["gradient_window"]
        base = [phase + (x / span) * win for x in range(cols)]
        dth = self.dither

        buf = bytearray()
        for y in range(rows):
            d13 = 13 * y
            for x in range(cols):
                t = base[x] + dth[(7 * x + d13) % 17]
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                buf += ramp[int(t * 255)]
        return Image.frombytes("RGB", (cols, rows), bytes(buf))

    def blit(self, im, spr, ox, oy, pal):
        s = self.scale
        d = ImageDraw.Draw(im)
        for sy, row in enumerate(spr):
            for sx, ch in enumerate(row):
                if ch == ".":
                    continue
                x0, y0 = ox + sx * s, oy + sy * s
                d.rectangle([x0, y0, x0 + s - 1, y0 + s - 1], fill=pal[ch])

    def blit_cells(self, im, cells, ox, oy, pal, facing=1):
        s = self.scale
        d = ImageDraw.Draw(im)
        for cx, cy, ch in cells:
            sx = (11 - cx) if facing < 0 else cx
            x0, y0 = ox + sx * s, oy + cy * s
            d.rectangle([x0, y0, x0 + s - 1, y0 + s - 1], fill=pal[ch])

    def gradient_wave(self, offset=0.0, dim=False):
        """模擬器原本的漸層：三角波，紅→黃→紅，會在空間上跑。

        Mo 說一直跑看了不舒服，所以預設關掉（idle_scroll=0 走 gradient()）。
        但要跑的時候是這一支，速度由 idle_scroll 決定。
        """
        cols, rows = self.cols, self.rows
        ramp = RAMP_DIM if dim else RAMP
        period = cols * 1.6
        base = []
        for x in range(cols):
            pos = ((x + offset) % period) / period
            base.append(pos * 2 if pos < 0.5 else (1 - pos) * 2)
        dth = self.dither

        buf = bytearray()
        for y in range(rows):
            d13 = 13 * y
            for x in range(cols):
                t = base[x] + dth[(7 * x + d13) % 17]
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                buf += ramp[int(t * 255)]
        return Image.frombytes("RGB", (cols, rows), bytes(buf))

    def draw_text(self, im, s, colour=YEL):
        """置中畫一行字，位置照模擬器放在上緣。"""
        size = max(7, round(self.rows * 0.26))
        m = text_mask(s, size)
        if m is None:
            return
        if m.width > self.cols:
            m = m.resize((self.cols, max(1, round(m.height * self.cols / m.width))),
                         Image.NEAREST)
        x = (self.cols - m.width) // 2
        y = max(0, round(self.rows * 0.06))
        im.paste(Image.new("RGB", m.size, colour), (x, y), m)

    def burst(self, im, cx, cy, r, colour=WHT):
        n = max(10, int(r * 3))
        px = im.load()
        for i in range(n):
            a = i / n * math.pi * 2
            x = round(cx + math.cos(a) * r)
            y = round(cy + math.sin(a) * r * 0.6)
            if 0 <= x < self.cols and 0 <= y < self.rows:
                px[x, y] = colour


# ---------------------------------------------------------------- 三段內容
def render_idle(cols, rows, p=None):
    """畫布：一段紅→黃的漸變，空間上不動，顏色很慢地變。

    phase 走三角波，所以最後一幀接回第一幀不會跳。
    """
    sc = Screen(cols, rows, p)
    frames = frame_count(sc.p, "idle")
    scroll = float(sc.p.get("idle_scroll", 0) or 0)

    out = []
    if scroll > 0:
        # 會跑的版本：一輪剛好跑完整數趟，所以尾接頭不會跳
        period = cols * 1.6
        for i in range(frames):
            out.append(sc.gradient_wave(offset=(i / frames) * period * scroll))
    else:
        # 不跑的版本：原地慢慢變色，phase 走三角波，收尾接得回去
        room = 1.0 - sc.p["gradient_window"]
        for i in range(frames):
            q = i / frames
            tri = q * 2 if q < 0.5 else (1 - q) * 2
            out.append(sc.gradient(phase=room * tri))
    return out


def render_patrol(cols, rows, p=None):
    """整點巡迴：勇者追著壞人跑，兩個都從左邊進、右邊出。"""
    sc = Screen(cols, rows, p)
    frames = frame_count(sc.p, "patrol")
    fps = sc.p["patrol_fps"]
    bg = sc.gradient()
    hy = rows - sc.sh

    # 兩個要同時在畫面上。所以起點抓成「壞人剛要進畫面」，
    # 勇者就在他後面一個身位，追逐全程兩個都看得到。
    gap = int(sc.p["patrol_gap"]) * sc.scale
    start = -14 * sc.scale - gap
    end = cols + 14 * sc.scale
    travel = end - start
    step = max(1, int(round(fps / 5.0)))      # 每秒換五次腳，跟走路速度無關

    out = []
    for i in range(frames):
        im = bg.copy()
        q = i / max(1, frames - 1)
        walk = (i // step) % 2 == 0

        vx = round(start + gap + travel * q)
        sc.blit(im, VIL_A if walk else VIL_B, vx, hy, VLC)
        sc.blit_cells(im, BLADE, vx, hy, BLC, 1)

        hx = round(start + travel * q)
        sc.blit(im, SPR_A if walk else SPR_B, hx, hy, SPC)
        sc.blit_cells(im, SWORD_READY, hx, hy, SWC, 1)

        out.append(im)
    return out


def render_okawari_miss(cols, rows, p=None):
    """續碗沒中獎：勇者跑過去，沒有石頭、沒有字。

    模擬器裡是 `const hit = Math.random() < stoneChance`，沒中就不生石頭。
    骰子不能在卡上擲（預錄節目沒有隨機性），所以中獎與沒中獎各編一支影片，
    後台在觸發的當下擲骰決定切哪一支。
    """
    sc = Screen(cols, rows, p)
    frames = frame_count(sc.p, "okawari")
    fps = sc.p["okawari_fps"]
    bg = sc.gradient()
    hy = rows - sc.sh
    start = -16 * sc.scale
    end = cols + 16 * sc.scale
    step = max(1, int(round(fps / 5.0)))

    out = []
    for i in range(frames):
        im = bg.copy()
        x = round(start + (end - start) * (i / max(1, frames - 1)))
        sc.blit(im, SPR_A if (i // step) % 2 == 0 else SPR_B, x, hy, SPC)
        sc.blit_cells(im, SWORD_READY, x, hy, SWC, 1)
        out.append(im)
    return out


def render_okawari(cols, rows, p=None):
    """續碗中獎：勇者衝出來，劈石，碎裂，閃「おかわり おめでとう!」。

    照模擬器 startClip('okawari')：石頭在 55% 位置，狀態 run → strike → burst。
    """
    sc = Screen(cols, rows, p)
    frames = frame_count(sc.p, "okawari")
    fps = sc.p["okawari_fps"]
    bg = sc.gradient()
    bg_dim = sc.gradient(dim=True)
    hy = rows - sc.sh
    stone_x = round(cols * sc.p["okawari_stone"])
    start = -16 * sc.scale

    run_end = int(frames * 0.55)
    strike_end = int(frames * 0.78)
    step = max(1, int(round(fps / 5.0)))
    slash_step = max(1, int(round(fps / 6.0)))

    out = []
    for i in range(frames):
        im = (bg_dim if i >= run_end else bg).copy()

        if i < run_end:
            x = round(start + (stone_x - 17 * sc.scale - start) * (i / max(1, run_end - 1)))
            sc.blit(im, STONE, stone_x, rows - sc.stone_h, STC)
            sc.blit(im, SPR_A if (i // step) % 2 == 0 else SPR_B, x, hy, SPC)
            sc.blit_cells(im, SWORD_READY, x, hy, SWC, 1)
        elif i < strike_end:
            x = round(stone_x - 17 * sc.scale)
            sc.blit(im, STONE, stone_x, rows - sc.stone_h, STC)
            sc.blit(im, SPR_A, x, hy, SPC)
            slash = ((i - run_end) // slash_step) % 2 == 1
            sc.blit_cells(im, SWORD_SLASH if slash else SWORD_READY, x, hy, SWC, 1)
            if slash:
                sc.burst(im, stone_x + 4 * sc.scale,
                         rows - sc.stone_h + 2 * sc.scale, 3 * sc.scale)
        else:
            x = round(stone_x - 17 * sc.scale)
            spread = (i - strike_end) * max(1, sc.scale // 2)
            d = ImageDraw.Draw(im)
            for s in (-1, 1):
                x0 = stone_x + s * spread
                d.rectangle([x0, rows - sc.stone_h + sc.scale,
                             x0 + 3 * sc.scale, rows - sc.scale], fill=STC["D"])
            sc.blit(im, SPR_A, x, hy, SPC)
            sc.blit_cells(im, SWORD_READY, x, hy, SWC, 1)
            sc.burst(im, stone_x + 4 * sc.scale,
                     rows - sc.stone_h + 2 * sc.scale, 3 * sc.scale + spread)

        # 中獎的字。石頭碎掉之後開始閃，節奏照模擬器的 t%30<22
        if i >= strike_end and ((i - strike_end) // max(1, slash_step)) % 4 < 3:
            sc.draw_text(im, str(sc.p.get("okawari_text") or TEXT_HIT))

        out.append(im)
    return out


RENDERERS = {
    "idle": render_idle,
    "patrol": render_patrol,
    "okawari": render_okawari,             # 中獎
    "okawari_miss": render_okawari_miss,   # 沒中獎
}

# 一個內容要編成好幾支影片時寫在這裡。播的時候由後台擲骰決定切哪一支。
VARIANTS = {"okawari": ["okawari", "okawari_miss"]}


def param_key(key):
    """okawari_miss 的秒數／幀率設定跟 okawari 共用。"""
    return "okawari" if key.startswith("okawari") else key


# ---------------------------------------------------------------- 新角色
# 2026-08-17 業主確認：主角是人物或小飯碗（兩案並陳），勇者與壞人停用。
# 舊的 render_patrol / render_okawari 先留著，續碗還在用。
try:
    import segment_art
    RENDERERS.update(segment_art.RENDERERS)
except Exception as _e:          # 美術還沒到位時不要讓整個後台起不來
    print("角色美術載入失敗，先跳過：%r" % (_e,))
