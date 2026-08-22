#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 預告片 · 一支動畫（不是門頭屏的模擬圖）

    python _出預告片.py            # 出 IG Reels 直式 + 貼文 4:5 兩支
    python _出預告片.py reels

輸出到 ../docs/teaser/。

★ 這支片不是產品照

  第一版把門頭屏畫成一條發光的橫條、上下掛品牌字，那是規格書的語言 ——
  看的人先看到「一塊螢幕」，才看到裡面有東西。這版整個畫面就是場景，
  沒有框、沒有品牌字、沒有屏：角色直接站在紅橙漸變裡，放到最大。
  是一支動畫，不是一張產品模擬圖。

  角色的畫法完全沒變，還是 food_sprites／ricebowl_sprite 那一套，
  跟真的會上屏的是同一張 sprite。改的只有「怎麼取景」。

★ 整張畫面是同一個像素格

  邏輯畫布 270×480，最後用 NEAREST 放大四倍變成 1080×1920。
  背景、角色、字全部在邏輯畫布上畫完再一起放大 —— 所以字也是像素的，
  不會出現「平滑的字壓在硬邊的圖上」那種兩套語言打架的感覺。
  順便：漸變只算 129,600 個點，不是兩百萬個。

★ 直式很窄，所以縱深分三層

  1080 寬放不下八隻並排的大角色（一隻就佔三分之一）。
  所以改成三層：後排四隻小、中排兩隻中、小飯碗前排大。
  遠的小、站得高、被前面的蓋住 —— 縱深是這樣做出來的，不是畫背景。

★ 分鏡（15.000 秒，跟配樂同一個數字）

    0.00-0.10   空景，紅橙漸變在呼吸
    0.10-0.45   六隻配角依序進場：後排四隻先到，中排兩隻再到
    0.45-0.72   小飯碗從左邊走進來，前排、最大
    0.72-0.75   走到正中間，停
    0.75-1.00   全員歡呼、紙花 ——「8.26 公開」在同一格跳出來

  0.75 就是配樂第 7 小節的重音。兩邊都照 128 BPM 算，不是後製對的。
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw  # noqa: E402

import artwork              # noqa: E402
import food_sprites as fs   # noqa: E402
import ricebowl_sprite      # noqa: E402
import segment_art as sa    # noqa: E402

OUT = os.path.abspath(os.path.join(HERE, "..", "docs", "teaser"))

FPS = 25
SECONDS = 15.0                     # ＝ teaser_music.DUR
PIXEL = 4                          # 一個邏輯像素放大成幾個實際像素

# 邏輯畫布。乘以 PIXEL 就是輸出尺寸。
FORMATS = {
    "reels": (270, 480),           # 1080×1920　IG Reels／限動
    "post": (270, 338),            # 1080×1352　IG 貼文 4:5
}

REVEAL_TEXT = "8.26 公開"          # 要改字改這裡

# 三層。(角色們, 佔畫面高度的幾成, 地面線在畫面的幾成)
BACK = [fs.ONSEN_CH, fs.CURRY_CH, fs.KARAAGE_CH, fs.BASQUE_CH]
MID = [fs.UDON_CH, fs.PURIN_CH]

T_BACK, BACK_RUN, BACK_STEP = 0.10, 0.15, 0.045
T_MID, MID_RUN, MID_STEP = 0.28, 0.16, 0.075
T_HERO, T_STOP = 0.45, 0.72
T_CHEER = 0.75                     # ★ 配樂第 7 小節的重音


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
    lead = max(1, len(box) - 1)
    gap = (x1 - x0 - used) // lead          # 排不下就變負的，讓它們略為交疊
    out, x = [], x0
    for c, s, w, h in box:
        out.append((c, x, s, w, h, floor))
        x += w + gap
    return out


def _shadow(d, x, w, floor, s, col):
    """腳下一道暗影。三層角色浮在漸變上會分不出誰站在哪，
    有影子才有地面 —— 但不畫地平線，畫了就變成三層階梯。

    寬度只取角色的四成，貼著腳。第一版取七成，結果那不是影子，
    是角色底下一條懸空的黑槓 —— 影子要比腳掌大一點點就好，
    大到跟身體一樣寬就變成一條線了。
    """
    pad = int(w * 0.30)
    d.rectangle([x + pad, floor, x + w - pad, floor + max(1, s // 3)],
                fill=col)


def _pixel_text(im, text, cy, size, colour, shadow):
    """把字畫在邏輯畫布上，置中。

    用 artwork.text_mask —— 它是硬邊的點陣遮罩，跟角色同一個世界。
    在 1080 那一層畫平滑的字會很漂亮，但那是海報的語言，不是動畫的。
    """
    m = artwork.text_mask(text, size)
    if m is None:
        return
    x = (im.width - m.width) // 2
    y = int(cy - m.height / 2)
    dark = Image.new("RGB", m.size, shadow)
    for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 0), (0, -1), (-1, -1)):
        im.paste(dark, (x + dx, y + dy), m)
    im.paste(Image.new("RGB", m.size, colour), (x, y), m)


def frames(cols, rows, n, p=None):
    """整支片的每一格，邏輯尺寸。"""
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = ricebowl_sprite                       # 主角固定小飯碗

    # 三層的高度與地面線。數字是量出來的，不是估的：
    # 主角佔畫面高度三成，一隻就吃掉八成寬 —— 直式的寬度是硬限制。
    # 後排四隻會略為交疊，那是刻意的，一排人站在後面本來就會擋到彼此。
    back = _tier(BACK, cols, rows, 0.105, 0.48, spread=(0.00, 1.00))
    mid = _tier(MID, cols, rows, 0.175, 0.63, spread=(0.02, 0.98))

    hp = SP.POSES["stand"]
    hs = max(1, round(rows * 0.30 / len(hp)))
    hw = max(len(r) for r in hp) * hs
    hh = len(hp) * hs
    # 腳踩在 0.82，不是踩到底。IG 下面兩成會被留言欄和按鈕蓋掉，
    # 踩到底的話手機上看就是腳被切掉。
    hfloor = int(rows * 0.82)
    hero_x = cols // 2 - hw // 2

    shadow = (108, 40, 30)                     # 比背景暗一階的暖色，不是純黑
    txt = max(10, int(rows * 0.10))

    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.09 + 0.05 * t)
        d = ImageDraw.Draw(im)
        cheer = t >= T_CHEER

        def tier(layout, t0_base, run, step):
            """畫一層。由遠而近，所以後排先畫、會被前面的蓋住。"""
            for j, (c, x, s, w, h, floor) in enumerate(layout):
                k = (t - (t0_base + j * step)) / run
                if k <= 0:
                    continue
                left_side = j % 2 == 0         # 左右輪流，才像從兩邊聚過來
                if k < 1:
                    x0 = -w if left_side else cols
                    rx = int(x0 + (x - x0) * k)
                    pose = c.POSES["walk_a" if (i // 5) % 2 == 0 else "walk_b"]
                    bob = 0
                elif cheer:
                    rx, pose = x, c.POSES["cheer"]
                    bob = -s * 2 if ((i + j * 2) // 5) % 2 == 0 else 0
                else:
                    # 站定等主角。相位各差一點，同時起伏會像一起在跳。
                    rx, pose = x, c.POSES["stand"]
                    bob = -s if ((i + j * 9) // 14) % 3 == 0 else 0
                _shadow(d, rx, w, floor, s, shadow)
                sa._blit(d, pose, rx, floor - h + bob, s, c.PAL,
                         flip=not left_side)

        tier(back, T_BACK, BACK_RUN, BACK_STEP)
        tier(mid, T_MID, MID_RUN, MID_STEP)

        # --- 前排：小飯碗 ---
        if t >= T_HERO:
            k = min(1.0, (t - T_HERO) / (T_STOP - T_HERO))
            hx = int(-hw + (hero_x + hw) * k)
            if cheer:
                pose = SP.POSES["cheer"]
                bob = -hs * 2 if (i // 5) % 2 == 0 else 0
            elif k < 1:
                pose = SP.POSES["walk_a" if (i // 6) % 2 == 0 else "walk_b"]
                bob = 0
            else:
                pose, bob = SP.POSES["stand"], 0
            _shadow(d, hx, hw, hfloor, hs, shadow)
            sa._blit(d, pose, hx, hfloor - hh + bob, hs, SP.PAL)

        # --- 收尾 ---
        if cheer:
            k = (t - T_CHEER) / (1 - T_CHEER)
            sa._confetti(d, cols, rows, 71, min(1.0, k * 1.5), 0.5, count=150)
            kk = min(1.0, k / 0.22)
            # 白過渡到黃。直接給黃的話跳出來那一格不夠亮，
            # 少了跟重音對上的那一下。
            col = tuple(int(artwork.WHT[c] + (artwork.YEL[c] - artwork.WHT[c])
                            * kk) for c in range(3))
            cy = int(rows * 0.22) + int((1 - kk) * rows * 0.02)
            _pixel_text(im, REVEAL_TEXT, cy, txt, col, artwork.DARK)
        out.append(im)
    return out


def encode(frames_, wav, path, scale):
    """邏輯畫布 → PNG 序列 → mp4。

    放大一律 NEAREST。用預設的雙線性會把硬邊糊掉，
    整支片的像素感就沒了。yuv420p 是 IG 唯一保證吃的像素格式。
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
    print("配樂　%.3f 秒　%d BPM　原創 chiptune" % (teaser_music.DUR,
                                                    int(teaser_music.BPM)))

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
