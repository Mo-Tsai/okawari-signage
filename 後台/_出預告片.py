#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 預告片（ON Design Lab 先行釋出）

    python _出預告片.py            # 出 IG Reels 直式 + 貼文直式兩支
    python _出預告片.py reels      # 只出其中一支

輸出到 ../docs/teaser/。

★ 這支片跟上屏的東西是同一套 sprite

  不是另外做的宣傳素材 —— 畫面裡那條門頭屏跑的就是 food_sprites 和
  segment_art 那一套，跟真的會上屏的是同一張圖。這件事本身就是說服力：
  業主看到的預告，就是他之後每天會在門口看到的東西。

★ 分鏡（15.000 秒，跟配樂同一個數字）

    0.00-0.10   空的門頭屏，只有紅橙漸變在呼吸
    0.10-0.42   六隻配角從左右輪流跑進來，站成後排
    0.46-0.72   小飯碗從左邊走進來，前排，全尺寸
    0.72-0.75   走到正中間，停
    0.75-1.00   全員歡呼、紙花 ——「8.26 公開」在同一格跳出來

  0.75 這個點就是配樂第 7 小節的重音。畫面和聲音是同一拍，
  不是後製對出來的，是兩邊都照 128 BPM 算的。

★ 前後景用比例做

  屏只有 120 px 高，沒有 Z 軸。所以「配角在後面」是靠兩件事表達的：
  配角縮到 52%、地面線往上抬 —— 遠的東西小，而且站得比較高。
  主角全尺寸站在下緣，走過去的時候會蓋住配角，前後關係就成立了。
"""

import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont  # noqa: E402

import artwork              # noqa: E402
import food_sprites         # noqa: E402
import segment_art as sa    # noqa: E402

OUT = os.path.abspath(os.path.join(HERE, "..", "docs", "teaser"))

FPS = 25
SECONDS = 15.0                     # ＝ teaser_music.DUR
COLS, ROWS = 960, 120              # 台南小北的畫布，1:1 貼上去不縮放

# 版位。IG Reels／限動是 9:16，貼文是 4:5。
FORMATS = {
    "reels": (1080, 1920),
    "post": (1080, 1350),
}

BG = (18, 14, 14)
DIM = (150, 132, 122)
WHT = (255, 253, 246)
YEL = (247, 179, 43)
RED = (226, 58, 46)

FONT_REG = r"C:\Windows\Fonts\msjh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msjhbd.ttc"

# 文案。要改字改這裡，不必動程式。
COPY = {
    "title": "OKAWARI",
    "sub": "門頭屏 · 動態設計",
    "reveal": "8.26 公開",
    "mark": "ON DESIGN LAB",
}


# ================================================================ 屏的內容
def strip_frames(n, p=None):
    """門頭屏那一條的每一格。回傳 n 張 960×120。"""
    sc = artwork.Screen(COLS, ROWS, p)
    q = sc.p
    SP = sa.ricebowl_sprite                     # 主角固定小飯碗，不跟 params 換

    crowd = list(food_sprites.FOODS.values())   # 六隻配角
    lay = sa._lineup(crowd, COLS, ROWS, q, scale=0.52, left=0.05, right=0.95)
    back_floor = ROWS - int(ROWS * 0.26)        # 後排的地面線抬高 —— 遠的東西站得高

    spr = SP.POSES["stand"]
    s = sa._scale(len(spr), ROWS, q)
    sw = max(len(r) for r in spr) * s
    sh = len(spr) * s
    front_floor = ROWS - max(1, s)
    hero_x = COLS // 2 - sw // 2

    T_IN, IN_RUN, IN_STEP = 0.10, 0.16, 0.052   # 配角進場
    T_HERO, T_STOP = 0.46, 0.72                 # 主角走進來
    T_CHEER = 0.75                              # ★ 跟配樂第 7 小節同一拍

    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.09 + 0.05 * t)
        d = ImageDraw.Draw(im)
        cheer = t >= T_CHEER

        # --- 後排：六隻配角 ---
        for j, (c, x, cs, w, h) in enumerate(lay):
            t0 = T_IN + j * IN_STEP
            k = (t - t0) / IN_RUN
            if k <= 0:
                continue
            left_side = j % 2 == 0              # 左右輪流進場，才像從兩邊聚過來
            if k < 1:
                x0 = -w if left_side else COLS
                rx = int(x0 + (x - x0) * k)
                pose = c.POSES["walk_a" if (i // 5) % 2 == 0 else "walk_b"]
                bob = 0
            elif cheer:
                rx = x
                pose = c.POSES["cheer"]
                bob = -cs * 2 if ((i + j * 2) // 5) % 2 == 0 else 0
            else:
                # 站定等主角。呼吸的相位各差一點，六隻同時起伏會像一起在跳。
                rx = x
                pose = c.POSES["stand"]
                bob = -cs if ((i + j * 9) // 14) % 3 == 0 else 0
            sa._blit(d, pose, rx, back_floor - h + bob, cs, c.PAL,
                     flip=not left_side)

        # --- 前排：小飯碗 ---
        if t >= T_HERO:
            k = min(1.0, (t - T_HERO) / (T_STOP - T_HERO))
            hx = int(-sw + (hero_x + sw) * k)
            if cheer:
                pose = SP.POSES["cheer"]
                bob = -s * 2 if (i // 5) % 2 == 0 else 0
            elif k < 1:
                pose = SP.POSES["walk_a" if (i // 6) % 2 == 0 else "walk_b"]
                bob = 0
            else:
                pose = SP.POSES["stand"]
                bob = 0
            sa._blit(d, pose, hx, front_floor - sh + bob, s, SP.PAL)

        if cheer:
            k = (t - T_CHEER) / (1 - T_CHEER)
            sa._confetti(d, COLS, ROWS, 71, min(1.0, k * 1.6), 0.5, count=110)
        out.append(im)
    return out


# ================================================================ 版面
def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _centred(d, text, cx, y, font, fill, track=0):
    """置中畫字，可以給字距。

    PIL 沒有字距，所以一個字一個字畫。標題和署名要拉開才有設計感 ——
    正黑體原本的字距在大字級下會擠成一團。
    """
    ws = [d.textlength(ch, font=font) for ch in text]
    total = sum(ws) + track * (len(text) - 1)
    x = cx - total / 2.0
    for ch, w in zip(text, ws):
        d.text((x, y), ch, font=font, fill=fill)
        x += w + track
    return total


def _bezel(canvas, strip, x, y):
    """把屏貼上去，加外框和光暈。

    光暈是把屏本身放大模糊之後加回背景 —— 不是畫一圈光。
    畫一圈光的話顏色是固定的；用屏本身當光源，畫面紅的時候光是紅的，
    黃的時候是黃的，那才像一塊在暗處發亮的 LED。
    """
    w, h = strip.size
    glow = strip.resize((int(w * 1.7), int(h * 6.0)), Image.BILINEAR)
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    glow = glow.point(lambda v: int(v * 0.46))

    # 上下要自己收掉。光源是一個實心亮矩形，高斯模糊只糊得動裡面，
    # 糊不掉外緣 —— 不收的話畫面上會出現一條看得見的水平硬邊。
    gw, gh = glow.size
    fall = Image.new("L", (1, gh))
    for yy in range(gh):
        u = abs(yy - gh / 2.0) / (gh / 2.0)
        fall.putpixel((0, yy), int(255 * max(0.0, 1.0 - u * u) ** 1.6))
    glow = ImageChops.multiply(glow, fall.resize((gw, gh)).convert("RGB"))

    gx = x + w // 2 - glow.width // 2
    gy = y + h // 2 - glow.height // 2

    region = canvas.crop((gx, gy, gx + glow.width, gy + glow.height))
    canvas.paste(ImageChops.add(region, glow), (gx, gy))

    d = ImageDraw.Draw(canvas)
    d.rectangle([x - 6, y - 6, x + w + 5, y + h + 5], outline=(48, 38, 34),
                width=3)
    canvas.paste(strip, (x, y))
    # 上緣一條細亮線：那是外殼的高光，屏才不會像一張貼上去的圖
    d.line([x - 6, y - 7, x + w + 5, y - 7], fill=(86, 70, 62), width=2)


def compose(strip, W, H, t):
    """把一格屏放進版面。t 是 0→1，用來決定「8.26 公開」出來了沒。"""
    im = Image.new("RGB", (W, H), BG)

    sx = (W - COLS) // 2
    sy = int(H * 0.48) - ROWS // 2
    _bezel(im, strip, sx, sy)

    d = ImageDraw.Draw(im)
    cx = W // 2

    # --- 上面：專案 ---
    f_title = _font(FONT_BOLD, int(H * 0.036))
    f_sub = _font(FONT_REG, int(H * 0.017))
    _centred(d, COPY["title"], cx, int(H * 0.195), f_title, WHT,
             track=int(H * 0.012))
    _centred(d, COPY["sub"], cx, int(H * 0.247), f_sub, DIM,
             track=int(H * 0.002))

    # --- 下面：8.26 公開 ---
    T_REVEAL = 0.75
    if t >= T_REVEAL:
        k = min(1.0, (t - T_REVEAL) / 0.055)
        f_big = _font(FONT_BOLD, int(H * 0.062))
        y = int(H * 0.600) + int((1 - k) * H * 0.014)   # 往上滑一點點才有落下感
        # 顏色從白過渡到黃。直接給黃的話，跳出來那一格不夠亮，
        # 壓在暗背景上少了「閃一下」的重音。
        col = tuple(int(WHT[c] + (YEL[c] - WHT[c]) * k) for c in range(3))
        _centred(d, COPY["reveal"], cx, y, f_big, col, track=int(H * 0.006))

        if k < 1.0:
            # 出現那一瞬間整片畫面提亮一階。跟配樂第 7 小節的重音同一格。
            #
            # 第一版是在屏上緣加一條白帶，結果那是一條線不是一道光 ——
            # 停格看就是畫面上多了一條白槓。整片加亮才讀得成「閃了一下」。
            fl = int((1 - k) * 26)
            im = ImageChops.add(im, Image.new("RGB", (W, H), (fl, fl, fl)))
            d = ImageDraw.Draw(im)

    # --- 最下面：署名 ---
    bar_w, bar_h = int(W * 0.13), max(4, int(H * 0.006))
    bx, by = cx - bar_w // 2, int(H * 0.805)
    for k in range(bar_w):
        u = k / max(1, bar_w - 1)
        d.rectangle([bx + k, by, bx + k + 1, by + bar_h],
                    fill=tuple(artwork.RAMP[min(255, int(u * 255))]))

    f_mark = _font(FONT_REG, int(H * 0.0155))
    _centred(d, COPY["mark"], cx, int(H * 0.828), f_mark, DIM,
             track=int(H * 0.008))
    return im


# ================================================================ 輸出
def encode(frames, wav, path):
    """PNG 序列 + wav → mp4。

    像素風一定要 neighbor 縮放 —— 但這裡畫布已經是 1:1 貼上去的，
    所以只要不讓 ffmpeg 再縮就好。yuv420p 是 IG 唯一保證吃的像素格式。
    """
    tmp = tempfile.mkdtemp()
    try:
        for i, im in enumerate(frames):
            im.save(os.path.join(tmp, "f_%05d.png" % i))
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
    print("配樂　%.3f 秒　%d BPM　原創 chiptune" % (teaser_music.DUR,
                                                    int(teaser_music.BPM)))

    print("算門頭屏那一條…（%d 格）" % n)
    strip = strip_frames(n)

    for key in sorted(want):
        W, H = FORMATS[key]
        frames = [compose(strip[i], W, H, i / n) for i in range(n)]
        path = os.path.join(OUT, "OKAWARI_預告_%s.mp4" % key)
        encode(frames, wav, path)
        print("  %-6s %4d×%-4d  %4.1f 秒  %5.0f KB  %s"
              % (key, W, H, n / FPS, os.path.getsize(path) / 1024,
                 os.path.basename(path)))

    print("\n輸出到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
