#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI QUEST 門頭屏 —— 實體 LED 板驅動程式（打樣機專用）
從 okawari-signage-demo/index.html (v0.4) 移植。

※ 這支只服務手邊那片 64x32 實驗屏，跟正式版 128x32 模擬器互不影響。

比例邏輯：正式規格是 128x32（4:1）。手邊的屏是 64x32（2:1），
所以只用中間 64x16 那一條顯示內容、上下各留 8 排不亮，
構圖比例與正式版完全等比（所有元素剛好各縮一半）。

兩種模式：
  1) 上板（Raspberry Pi + rpi-rgb-led-matrix）
       sudo python3 okawari_panel.py
  2) 預覽（Windows / 任何有 Pillow+numpy 的電腦，不需要硬體）
       python okawari_panel.py --gif preview.gif --frames 600

觸發「續碗」：
  - 終端機按 Enter
  - 或 touch /tmp/okawari  （之後接按鈕 / 後台就靠這個）
  - 或 --auto 8  每 8 秒自動來一碗（展示用）
"""

import argparse, os, random, sys, threading, time
import numpy as np
from PIL import Image

# ================= 品牌色 =================
RED = np.array([226,  58,  46], dtype=np.float32)
ORG = np.array([240, 120,  24], dtype=np.float32)
YEL = np.array([247, 179,  43], dtype=np.float32)
WHT = (255, 253, 246)
STEEL = (214, 218, 228)

# ================= 小勇者 sprite（12x12，兩幀走路） =================
SPR_A = [
    "....KKKK....", "..KKWWWWKK..", ".KWWWWWWWWK.", ".KWWWWWWWWK.",
    "KRRRRRRRRRRK", ".KWWKWWKWWK.", ".KWWWWWWWWK.", ".KWWWKKWWWK.",
    "..KKWWWWKK..", "...KOOOOK...", "..KOOOOOOK..", "...KK..KK...",
]
SPR_B = SPR_A[:11] + ["..KK....KK.."]
SPC = {"K": (26, 23, 33), "W": WHT, "R": tuple(RED.astype(int)), "O": tuple(ORG.astype(int))}

def mirror(spr):
    return [row[::-1] for row in spr]

SPR_A_L, SPR_B_L = mirror(SPR_A), mirror(SPR_B)

# ================= 劍（相對勇者 12x12 原點的 cell 座標） =================
SWORD_READY = [(11,6,'G'),(12,6,'S'),(13,6,'S'),(14,6,'S'),(15,6,'S'),(16,6,'S')]
SWORD_SLASH = [(11,7,'G'),(12,8,'S'),(13,9,'S'),(14,10,'S'),(15,11,'S')]
SWC = {"S": STEEL, "G": tuple(YEL.astype(int))}

# ================= 石頭 sprite（8x6） =================
STONE = ["..SSSS..", ".SSSSDS.", "SSWSSSDS", "SSSSDSSS", ".SDSSSS.", "..SSSS.."]
STC = {"S": (148,150,160), "D": (92,94,104), "W": (205,208,218)}

# ================= 字幕點陣「おかわり おめでとう!」 =================
# 在 Windows 用 MS Gothic 11px 預先轉點陣後內嵌，Pi 上不需要任何日文字型。
TXT_EGG = [
    "0001000000000010000000000100000000010000100000000000010000000000001000000000000000000010000000000110000000000000",
    "0001000100000010001000000100000000010000100000000000010001000001011100000111111110000010000000000001100000100000",
    "0111110010001111000100011101110000010000100000000001111100100001101010000000010000000010000000000000000000100000",
    "0001000000000100100100000110001000010100100000000000010000000001001001000000100110000010011000000111100000100000",
    "0001111100000100100100000100001000011000100000000000011111000010101001000001000000000001100000001000010000100000",
    "0011000010000100101100001100001000010000100000000000110000100010101001000001000000000010000000000000010000100000",
    "0101000010001000100000010100001000000000100000000001010000100010010001000001000000000100000000000000010000000000",
    "0101010010001000100000000100001000000001000000000001010100100001100010000000100000000100000000000000100000110000",
    "0011001100001011000000000100110000000110000000000000110011000000000100000000011000000011111000000111000000000000",
]
TXT_W, TXT_H = len(TXT_EGG[0]), len(TXT_EGG)

# 窄版字幕：內容帶只有 16 排時，日文 9px 會佔掉一半高度，改用 3x5 英數點陣。
FONT35 = {
    "O": ["111", "101", "101", "101", "111"],
    "K": ["101", "101", "110", "101", "101"],
    "A": ["010", "101", "111", "101", "101"],
    "W": ["10001", "10001", "10101", "11011", "10001"],
    "R": ["110", "101", "110", "101", "101"],
    "I": ["111", "010", "010", "010", "111"],
    "!": ["1", "1", "1", "0", "1"],
    " ": ["0", "0", "0", "0", "0"],
}

def build_text(s):
    """把字串排成點陣列（每個字之間留 1px）。"""
    glyphs = [FONT35[c] for c in s if c in FONT35]
    rows = []
    for y in range(5):
        rows.append(" ".join(g[y] for g in glyphs).replace(" ", "0"))
    w = max(len(r) for r in rows)
    return [r.ljust(w, "0") for r in rows]

TXT_SMALL = build_text("OKAWARI!")


# ================================================================
#  畫布
# ================================================================
class Stage:
    """一塊 COLS x ROWS 的 RGB 畫布，所有繪圖都寫進 numpy 陣列。"""

    def __init__(self, cols, rows, cfg):
        self.COLS, self.ROWS = cols, rows
        self.cfg = cfg
        self.buf = np.zeros((rows, cols, 3), dtype=np.float32)

        # 漸變抖動網格（對應原版 ((x*7+y*13)%17)/17-0.5 乘 0.22）
        xs = np.arange(cols)[None, :]
        ys = np.arange(rows)[:, None]
        self.dither = (((xs * 7 + ys * 13) % 17) / 17.0 - 0.5) * 0.22
        self.period = cols * 1.6

        self.off = 0.0
        self.frame = 0
        self.runners = []
        self.patrol = None
        self.patrol_next = 0
        self.schedule_patrol()

        self.scale = cfg.scale
        self.SH = 12 * self.scale                 # 勇者高
        self.STONE_H = 6 * self.scale             # 石頭高

        # 內容帶夠高才放得下日文字幕，否則用窄版英數
        self.txt = TXT_EGG if rows >= 24 else TXT_SMALL
        self.txt_w, self.txt_h = len(self.txt[0]), len(self.txt)

    # ---------- 事件 ----------
    def schedule_patrol(self):
        sec = self.cfg.patrol_min + random.random() * (self.cfg.patrol_max - self.cfg.patrol_min)
        self.patrol_next = self.frame + int(sec * self.cfg.fps)

    def okawari(self):
        """續碗 +1：擲骰決定前方會不會出現石頭。"""
        hit = random.random() < self.cfg.stone_chance
        start_x = -16 * self.scale // 2
        if self.runners:
            start_x = min(start_x, self.runners[-1]["x"] - 22)
        stone_x = int(self.COLS * (0.38 + random.random() * 0.3)) if hit else -999
        self.runners.append({"x": float(start_x), "t": 0, "stone_x": stone_x,
                             "state": "run", "aT": 0, "debris": None})

    def spawn_patrol(self):
        d = 1 if random.random() < 0.5 else -1
        self.patrol = {"x": float(-14 if d > 0 else self.COLS + 2), "dir": d, "t": 0}

    # ---------- 繪圖工具 ----------
    def px(self, x, y, color):
        if 0 <= x < self.COLS and 0 <= y < self.ROWS:
            self.buf[y, x] = color

    def blit(self, spr, ox, oy, pal):
        s = self.scale
        for sy, row in enumerate(spr):
            y0 = oy + sy * s
            if y0 + s <= 0 or y0 >= self.ROWS:
                continue
            for sx, ch in enumerate(row):
                if ch == ".":
                    continue
                x0 = ox + sx * s
                if x0 + s <= 0 or x0 >= self.COLS:
                    continue
                self.buf[max(0, y0):min(self.ROWS, y0 + s),
                         max(0, x0):min(self.COLS, x0 + s)] = pal[ch]

    def blit_cells(self, cells, ox, oy, direction):
        s = self.scale
        for cx, cy, ch in cells:
            sx = (11 - cx) if direction < 0 else cx
            x0, y0 = ox + sx * s, oy + cy * s
            if x0 + s <= 0 or x0 >= self.COLS or y0 + s <= 0 or y0 >= self.ROWS:
                continue
            self.buf[max(0, y0):min(self.ROWS, y0 + s),
                     max(0, x0):min(self.COLS, x0 + s)] = SWC[ch]

    def draw_text(self, ox, oy, color):
        for y, row in enumerate(self.txt):
            Y = oy + y
            if not (0 <= Y < self.ROWS):
                continue
            for x, v in enumerate(row):
                if v == "1":
                    X = ox + x
                    if 0 <= X < self.COLS:
                        self.buf[Y, X] = color

    def burst(self, cx, cy, r, color):
        n = max(8, int(r * 3))
        for i in range(n):
            a = i / n * 6.2831853
            self.px(int(round(cx + np.cos(a) * r)), int(round(cy + np.sin(a) * r * 0.6)), color)

    # ---------- 底層漸變 ----------
    def gradient(self, dim):
        xs = np.arange(self.COLS)[None, :].astype(np.float32)
        pos = ((xs + self.off) % self.period) / self.period
        base = np.where(pos < 0.5, pos * 2.0, (1.0 - pos) * 2.0)
        t = np.clip(base + self.dither, 0.0, 1.0)[..., None]
        lo = t < 0.5
        u = np.where(lo, t * 2.0, (t - 0.5) * 2.0)
        a = np.where(lo, RED, ORG)
        b = np.where(lo, ORG, YEL)
        c = a + (b - a) * u
        return c * 0.22 if dim else c

    # ---------- 主更新 ----------
    def tick(self):
        self.frame += 1
        busy = len(self.runners) > 0
        self.off += 0.25 if busy else 0.6
        self.buf[:] = self.gradient(busy)

        # --- 待機巡邏 ---
        if not busy:
            if self.patrol:
                p = self.patrol
                p["x"] += 0.45 * p["dir"]
                p["t"] += 1
                walk = p["t"] % 20 < 10
                if p["dir"] > 0:
                    spr = SPR_A if walk else SPR_B
                else:
                    spr = SPR_A_L if walk else SPR_B_L
                hx, hy = int(round(p["x"])), self.ROWS - self.SH
                self.blit(spr, hx, hy, SPC)
                self.blit_cells(SWORD_READY, hx, hy, p["dir"])
                if p["x"] > self.COLS + 4 or p["x"] < -20:
                    self.patrol = None
                    self.schedule_patrol()
            elif self.frame >= self.patrol_next:
                self.spawn_patrol()
        else:
            self.patrol = None

        # --- 續碗勇者 ---
        for r in self.runners:
            hx, hy = int(round(r["x"])), self.ROWS - self.SH

            if r["state"] == "run":
                r["x"] += 0.9
                r["t"] += 1
                if r["stone_x"] >= 0:
                    self.blit(STONE, r["stone_x"], self.ROWS - self.STONE_H, STC)
                self.blit(SPR_A if r["t"] % 16 < 8 else SPR_B, hx, hy, SPC)
                self.blit_cells(SWORD_READY, hx, hy, 1)
                if r["stone_x"] >= 0 and r["x"] + 17 * self.scale >= r["stone_x"]:
                    r["state"], r["aT"] = "strike", 0

            elif r["state"] == "strike":
                r["aT"] += 1
                self.blit(STONE, r["stone_x"], self.ROWS - self.STONE_H, STC)
                self.blit(SPR_A, hx, hy, SPC)
                slash = (r["aT"] % 14) >= 7
                self.blit_cells(SWORD_SLASH if slash else SWORD_READY, hx, hy, 1)
                if slash:
                    self.burst(r["stone_x"] + 8, self.ROWS - self.STONE_H + 2, 3, WHT)
                if r["aT"] >= 28:
                    r["state"], r["aT"] = "burst", 0
                    r["debris"] = [{"x": float(r["stone_x"] + 8), "y": float(self.ROWS - 6),
                                    "vx": -1.0 + random.random() * 2.4,
                                    "vy": -2.2 + random.random() * 1.2} for _ in range(12)]

            else:  # burst
                r["aT"] += 1
                bx, by = r["stone_x"] + 8, self.ROWS - 8
                self.blit(SPR_A, hx, hy, SPC)
                self.blit_cells(SWORD_SLASH, hx, hy, 1)
                ph = r["aT"] % 18
                self.burst(bx, by, 2 + ph * 0.9, tuple(YEL.astype(int)))
                if ph > 4:
                    self.burst(bx, by, ph * 0.7, WHT)
                for d in r["debris"]:
                    d["x"] += d["vx"]; d["y"] += d["vy"]; d["vy"] += 0.09
                    self.px(int(round(d["x"])), int(round(d["y"])), STC["S"])
                # 字幕：塞得下就置中閃爍，塞不下就橫向捲
                fits = self.txt_w <= self.COLS - 4
                ty = max(1, self.ROWS // 16)
                if fits:
                    if r["aT"] % 14 < 10:
                        self.draw_text((self.COLS - self.txt_w) // 2, ty, tuple(YEL.astype(int)))
                else:
                    self.draw_text(self.COLS - int(r["aT"] * 1.6), ty, tuple(YEL.astype(int)))
                if r["aT"] > (84 if fits else int((self.COLS + self.txt_w) / 1.6)):
                    r["state"], r["stone_x"] = "run", -999

        self.runners = [r for r in self.runners if r["x"] <= self.COLS + 4]

    def image(self):
        return Image.fromarray(np.clip(self.buf, 0, 255).astype(np.uint8), "RGB")


# ================================================================
#  觸發來源
# ================================================================
def start_triggers(stage, cfg):
    def stdin_loop():
        for _ in sys.stdin:
            stage.okawari()
    try:
        if sys.stdin and sys.stdin.isatty():
            threading.Thread(target=stdin_loop, daemon=True).start()
    except Exception:
        pass

    def take(path):
        """檔案存在就吃掉它並回傳內容（當作一次觸發）。"""
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                body = f.read().strip()
        except OSError:
            body = ""
        try:
            os.remove(path)
        except OSError:
            pass
        return body

    def file_loop():
        base = cfg.trigger_file
        while True:
            if take(base) is not None:
                stage.okawari()
            if take(base + "_patrol") is not None:
                if not stage.patrol and not stage.runners:
                    stage.spawn_patrol()
            v = take(base + "_chance")
            if v:
                try:
                    cfg.stone_chance = max(0.0, min(1.0, float(v)))
                except ValueError:
                    pass
            time.sleep(0.1)
    threading.Thread(target=file_loop, daemon=True).start()


# ================================================================
def main():
    ap = argparse.ArgumentParser(description="OKAWARI QUEST 門頭屏")
    ap.add_argument("--cols", type=int, default=64, help="單片模組寬（預設 64）")
    ap.add_argument("--rows", type=int, default=32, help="單片模組高（預設 32）")
    ap.add_argument("--chain", type=int, default=1, help="串接片數（預設 1）")
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--brightness", type=int, default=60, help="亮度 1-100")
    ap.add_argument("--slowdown", type=int, default=4, help="Pi4 建議 4")
    ap.add_argument("--gpio-mapping", default="regular",
                    help="regular / adafruit-hat / adafruit-hat-pwm")
    ap.add_argument("--content-cols", type=int, default=0,
                    help="內容帶寬度（0＝跟屏一樣寬）")
    ap.add_argument("--content-rows", type=int, default=16,
                    help="內容帶高度，上下留黑維持 4:1 比例（0＝滿版）")
    ap.add_argument("--scale", type=int, default=1, help="sprite 放大倍率（1 或 2）")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--stone-chance", type=float, default=0.25)
    ap.add_argument("--patrol-min", type=float, default=18)
    ap.add_argument("--patrol-max", type=float, default=40)
    ap.add_argument("--auto", type=float, default=0, help="每 N 秒自動續碗（0=關）")
    ap.add_argument("--trigger-file", default="/tmp/okawari")
    ap.add_argument("--gif", default=None, help="不上板，輸出預覽 GIF")
    ap.add_argument("--frames", type=int, default=600, help="GIF 幀數")
    ap.add_argument("--zoom", type=int, default=6, help="GIF 放大倍率")
    cfg = ap.parse_args()

    # 屏的實體像素
    PW = cfg.cols * cfg.chain
    PH = cfg.rows * cfg.parallel
    # 內容帶（置中，上下留黑）
    CW = cfg.content_cols or PW
    CH = cfg.content_rows or PH
    CW, CH = min(CW, PW), min(CH, PH)
    OX, OY = (PW - CW) // 2, (PH - CH) // 2

    stage = Stage(CW, CH, cfg)

    def compose():
        """把內容帶貼進屏尺寸的畫布，其餘留黑。"""
        if (CW, CH) == (PW, PH):
            return stage.image()
        canvas = Image.new("RGB", (PW, PH), (0, 0, 0))
        canvas.paste(stage.image(), (OX, OY))
        return canvas

    # ---------- 預覽模式 ----------
    if cfg.gif:
        frames = []
        for i in range(cfg.frames):
            if i in (40, 150, 260, 380):
                stage.okawari()
            stage.tick()
            frames.append(compose().resize((PW * cfg.zoom, PH * cfg.zoom), Image.NEAREST))
        frames[0].save(cfg.gif, save_all=True, append_images=frames[1:],
                       duration=int(1000 / cfg.fps), loop=0, optimize=True)
        print("已輸出 %s  屏 %dx%d／內容帶 %dx%d，%d 幀"
              % (cfg.gif, PW, PH, CW, CH, cfg.frames))
        return

    # ---------- 上板模式 ----------
    from rgbmatrix import RGBMatrix, RGBMatrixOptions

    o = RGBMatrixOptions()
    o.rows, o.cols = cfg.rows, cfg.cols
    o.chain_length, o.parallel = cfg.chain, cfg.parallel
    o.brightness = cfg.brightness
    o.gpio_slowdown = cfg.slowdown
    o.hardware_mapping = cfg.gpio_mapping
    o.drop_privileges = False
    matrix = RGBMatrix(options=o)
    canvas = matrix.CreateFrameCanvas()

    start_triggers(stage, cfg)
    print("OKAWARI 執行中 —— 屏 %dx%d／內容帶 %dx%d，按 Enter 續碗，Ctrl+C 結束"
          % (PW, PH, CW, CH))

    dt = 1.0 / cfg.fps
    next_auto = time.time() + cfg.auto if cfg.auto else None
    try:
        while True:
            t0 = time.time()
            if next_auto and t0 >= next_auto:
                stage.okawari()
                next_auto = t0 + cfg.auto
            stage.tick()
            canvas.SetImage(compose())
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(max(0, dt - (time.time() - t0)))
    except KeyboardInterrupt:
        matrix.Clear()
        print("\n結束")


if __name__ == "__main__":
    main()
