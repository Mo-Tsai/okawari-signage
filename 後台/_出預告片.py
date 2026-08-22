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
  背景、角色、字全部在邏輯畫布上畫完再一起放大 —— 所以字也是像素的，
  不會出現「平滑的字壓在硬邊的圖上」那種兩套語言打架的感覺。
  順便：漸變只算 129,600 個點，不是兩百萬個。

★ 三層排成三角形

  1080 寬放不下八隻並排的大角色。所以分三層：後排四隻橫滿上方、
  中排兩隻推到左右兩側、主角最大站正中間最下面。
  正面看過去是一個往下收的三角，而且每一層的頭都在前一層的上面 ——
  誰都沒有被蓋掉，縱深是這樣做出來的，不是畫背景。

★ 分鏡（15.000 秒，跟配樂同一個數字）

    0.00-0.03   全黑
    0.03-0.29   兩道探照燈交叉掃 —— 橘色是被照出來的，不是淡進來的
    0.29-0.34   燈全開，過曝一下
    0.36-0.53   啪、啪、啪、啪 —— 六位賓客原地彈出來
    0.58-0.70   小飯碗從天上砸下來
    0.70        落地：畫面震、全員被彈起來
    0.75-1.00   全員歡呼、紙花 ——「8.26 公開」在同一格跳出來

  0.75 就是配樂第 7 小節的重音。兩邊都照 128 BPM 算，不是後製對的。
"""

import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

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

BACK = [fs.ONSEN_CH, fs.CURRY_CH, fs.KARAAGE_CH, fs.BASQUE_CH]
MID = [fs.UDON_CH, fs.PURIN_CH]

# ---------------------------------------------------------------- 節拍
# 全部是 0→1 的比例。乘上 15 秒就是秒數。
#
# ★ 開場不是淡入，是探照燈掃出來的
#   「黑畫面慢慢變橘」是螢幕的語言 —— 那是一塊面板在調亮度。
#   探照燈掃過去、掃到哪裡哪裡才亮，那是空間的語言：暗的地方一直都在，
#   只是還沒被照到。這個梗跟整點彩蛋 egg1（手電筒巡邏）是同一個，
#   前後呼應得起來。
#
# ★ 賓客是「啪」一下彈出來的，不是走進來的
#   從畫面外走進來的東西看起來像跑馬燈在推東西過去。
#   原地彈出來（先扁後彈、帶一圈爆點）才是動畫的語言。
T_DARK = 0.03                      # 全黑，一下就好
T_SWEEP = 0.29                     # 探照燈掃到這裡
T_FLOOD = 0.34                     # 燈全開
T_POP, POP_STEP, POP_RUN = 0.36, 0.030, 0.022    # 啪啪啪啪，六隻
T_DROP, T_LAND = 0.575, 0.700      # 主角從上面砸下來
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


def _haze_mask(cols, rows, top_frac=0.58, peak=104):
    """下緣那層亮霧的遮罩。由上而下越來越亮。

    畫面下半是一大塊飽和的橘，加上白色的碗 —— 那是一個實心的重量塊，
    整個構圖會被壓在下面。壓一層半透明的暖白把底變淺，畫面才浮得起來。

    只算一次，每一格重複用 —— 每格重算要多花 375 倍的時間。
    """
    top = int(rows * top_frac)
    h = rows - top
    col = Image.new("L", (1, h))
    for y in range(h):
        u = y / max(1, h - 1)
        col.putpixel((0, y), int(peak * (u ** 1.5)))
    return top, col.resize((cols, h), Image.BILINEAR)


def _shadow(d, x, w, floor, s, col):
    """腳下一道暗影。三層角色浮在漸變上會分不出誰站在哪，
    有影子才有地面 —— 但不畫地平線，畫了就變成三層階梯。

    寬度只取角色的四成，貼著腳。第一版取七成，結果那不是影子，
    是角色底下一條懸空的黑槓。
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


def _blit2(d, spr, ox, oy, sx, sy, pal, flip=False):
    """跟 sa._blit 一樣，但橫向和縱向可以不同倍率。

    彈出來那一下要「先扁後彈」—— 扁就是 sx 大、sy 小。
    只有一個 s 的話做不出擠壓，角色只會憑空變大，那不叫彈出來。

    ★ 每一格的右下角要算到「下一格的起點減一」，不能用「起點加寬度」。
      sx／sy 是小數（6×0.85＝5.1），用寬度算會四捨五入成 5，
      但下一格的起點是 int(6×5.1)＝30 —— 每一格之間就多出一條縫，
      角色會被切成一條一條的百葉窗。
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


def _pop(d, pose, cx, floor, s, pal, k, flip=False):
    """原地彈出來。k 是 0→1 的進度。

    三拍：扁 → 過衝拉高 → 回正。中間那個過衝不能省 ——
    直接長到定值只是「變大」，有過衝才是「彈」。
    """
    if k < 0.34:
        u = k / 0.34
        fx, fy = 1.45 - 0.35 * u, 0.45 + 0.35 * u
    elif k < 0.68:
        u = (k - 0.34) / 0.34
        fx, fy = 1.10 - 0.14 * u, 0.80 + 0.32 * u
    else:
        u = (k - 0.68) / 0.32
        fx, fy = 0.96 + 0.04 * u, 1.12 - 0.12 * u
    sx, sy = max(1.0, s * fx), max(1.0, s * fy)
    w = max(len(r) for r in pose) * sx
    h = len(pose) * sy
    _blit2(d, pose, int(cx - w / 2), int(floor - h), sx, sy, pal, flip)


def _beams(cols, rows, ph):
    """兩道從畫面下緣兩側射上去的探照燈。ph 是 0→1 的掃動進度。

    首映會那種交叉光柱。從下往上射 —— 從上往下射看起來像審訊，
    不像開幕。兩道的擺動相位差 180 度，所以會在天上交叉。

    ★ 角度要往上：y 是往下長的，所以「上」是負的 sin，
      也就是角度落在 -180°〜0° 之間。第一版寫成 ±62°，
      其中一道的 sin 是正的 —— 那一道整個射到畫面下面去了。

    ★ 光柱要細、要短。三角形從一個點張開，張角一大、射程一長，
      到了畫面上緣就寬到把整個畫面蓋住 —— 那不是探照燈，是開燈。

    遮罩最後糊一下。硬邊的三角形是一塊橘色的色片，糊過的才是光。
    """
    m = Image.new("L", (cols, rows), 0)
    md = ImageDraw.Draw(m)
    reach = rows * 1.45
    half = math.radians(4.2 + 1.8 * math.sin(ph * math.tau * 5.0))
    for side in (-1, 1):
        ax = cols * (0.5 + side * 0.55)
        ay = rows * 1.10
        base = math.radians(-90.0 - side * 26.0)      # 往上、往內
        swing = math.radians(26.0) * math.sin(
            ph * math.tau * 2.5 + (0.0 if side < 0 else math.pi))
        a = base + swing
        md.polygon([
            (ax, ay),
            (ax + math.cos(a - half) * reach, ay + math.sin(a - half) * reach),
            (ax + math.cos(a + half) * reach, ay + math.sin(a + half) * reach),
        ], fill=255)
    return m.filter(ImageFilter.GaussianBlur(3.5))


def frames(cols, rows, n, p=None):
    """整支片的每一格，邏輯尺寸。"""
    sc = artwork.Screen(cols, rows, p)
    SP = ricebowl_sprite                       # 主角固定小飯碗

    # 三層排成三角形。主角縮到畫面高度 24%（寬 65%）——
    # 上一版是 30% 高、80% 寬，站到中間就把中排兩隻整個吃掉，
    # 布丁妹妹只剩右邊露出一小塊黃色。
    # 中排的地面線抬到主角頭頂上方，交疊的就只剩它們的腳。
    back = _tier(BACK, cols, rows, 0.085, 0.44, spread=(0.00, 1.00))
    mid = _tier(MID, cols, rows, 0.145, 0.60, spread=(0.00, 1.00))
    guests = back + mid

    hp = SP.POSES["stand"]
    hs = max(1, round(rows * 0.24 / len(hp)))
    hw = max(len(r) for r in hp) * hs
    hh = len(hp) * hs
    # 腳踩在 0.82，不是踩到底。IG 下面兩成會被留言欄和按鈕蓋掉。
    hfloor = int(rows * 0.82)
    hero_x = cols // 2 - hw // 2

    shadow = (108, 40, 30)                     # 比背景暗一階的暖色，不是純黑
    txt = max(10, int(rows * 0.10))
    night = Image.new("RGB", (cols, rows), (12, 8, 10))
    haze_top, haze_mask = _haze_mask(cols, rows)
    haze = Image.new("RGB", (cols, rows - haze_top), (255, 238, 206))

    out = []
    for i in range(n):
        t = i / n
        base = sc.gradient(phase=0.09 + 0.05 * t)

        # ------------------------------------------------ 開場：探照燈
        if t < T_DARK:
            out.append(night.copy())
            continue
        if t < T_FLOOD:
            u = (t - T_DARK) / (T_SWEEP - T_DARK)
            if u < 1.0:
                # 被照到的地方比底色再亮一階 —— 光要比背景亮才是光，
                # 照出原本的顏色只是「露出來」。
                lit = ImageChops.add(base, Image.new("RGB", (cols, rows),
                                                     (46, 32, 18)))
                out.append(Image.composite(lit, night, _beams(cols, rows, u)))
            else:
                # 掃完 → 燈全開。中間過曝一下，那是「全亮」的重音。
                k = (t - T_SWEEP) / (T_FLOOD - T_SWEEP)
                im = Image.blend(night, base, min(1.0, k * 2.2))
                if k < 0.5:
                    # 往純白 blend，不是整片加亮。加亮是把橘色墊高，
                    # 出來是一片濁掉的米色；blend 才是真的「閃白」。
                    im = Image.blend(im, Image.new("RGB", (cols, rows),
                                                   (255, 252, 244)),
                                     (0.5 - k) * 1.7)
                out.append(im)
            continue

        im = base
        # 下緣壓一層半透明暖白，把底變淺
        im.paste(Image.composite(haze, im.crop((0, haze_top, cols, rows)),
                                 haze_mask), (0, haze_top))
        d = ImageDraw.Draw(im)
        cheer = t >= T_CHEER

        # 主角砸下來那一下：全員被彈起、畫面震
        land = (t - T_LAND) / 0.05
        impact = 0.0 <= land < 1.0
        jolt = int((1 - land) * max(1, hs) * 1.6) if impact else 0

        # ------------------------------------------------ 賓客：啪啪啪啪
        for j, (c, x, s, w, h, floor) in enumerate(guests):
            k = (t - (T_POP + j * POP_STEP)) / POP_RUN
            if k <= 0:
                continue
            flip = j % 2 == 1
            if k < 1:
                _pop(d, c.POSES["stand"], x + w / 2, floor, s, c.PAL, k, flip)
                if k < 0.45:                   # 冒出來那一圈爆點
                    sa._spark(d, int(x + w / 2), int(floor - h * 0.5),
                              int(h * (0.5 + k)), max(1, s // 2), artwork.WHT)
                continue
            if cheer:
                pose = c.POSES["cheer"]
                bob = -s * 2 if ((i + j * 2) // 4) % 2 == 0 else 0
            elif impact:
                pose, bob = c.POSES["cheer"], -jolt   # 被震得跳起來
            else:
                # 等主角。相位各差一點，同時起伏會像一起在跳。
                pose = c.POSES["stand"]
                bob = -s if ((i + j * 7) // 11) % 3 == 0 else 0
            _shadow(d, x, w, floor, s, shadow)
            sa._blit(d, pose, x, floor - h + bob, s, c.PAL, flip=flip)

        # ------------------------------------------------ 主角：從天上砸下來
        if t >= T_DROP:
            k = min(1.0, (t - T_DROP) / (T_LAND - T_DROP))
            if k < 1.0:
                # 加速度落下。等速掉下來沒有重量。
                # y 是身體上緣：從整隻在畫面外（-hh）掉到落地位置。
                y = int(-hh + hfloor * k * k)
                for dx in (int(hw * 0.30), int(hw * 0.70)):   # 落下的速度線
                    y1 = min(rows - 1, y)
                    y0 = max(0, y - int(rows * 0.20))
                    if y1 > y0:                  # 還在畫面外就沒有拖尾可畫
                        d.rectangle([hero_x + dx, y0,
                                     hero_x + dx + max(1, hs // 3), y1],
                                    fill=artwork.WHT)
                sa._blit(d, SP.POSES["stand"], hero_x, y, hs, SP.PAL)
            elif impact:
                # 落地擠壓：矮一截、寬一點，腳下噴一圈
                _shadow(d, hero_x, hw, hfloor, hs, shadow)
                sq = 1.0 - 0.22 * (1 - land)
                _blit2(d, SP.POSES["stand"], int(hero_x - hw * 0.09),
                       int(hfloor - hh * sq), hs * 1.18, hs * sq, SP.PAL)
                sa._spark(d, hero_x + hw // 2, hfloor,
                          int(hw * (0.5 + land)), max(1, hs // 2), artwork.WHT)
            else:
                if cheer:
                    pose = SP.POSES["cheer"]
                    bob = -hs * 2 if (i // 4) % 2 == 0 else 0
                else:
                    pose, bob = SP.POSES["stand"], 0
                _shadow(d, hero_x, hw, hfloor, hs, shadow)
                sa._blit(d, pose, hero_x, hfloor - hh + bob, hs, SP.PAL)

        # ------------------------------------------------ 收尾
        if cheer:
            k = (t - T_CHEER) / (1 - T_CHEER)
            sa._confetti(d, cols, rows, 71, min(1.0, k * 1.5), 0.5, count=150)
            kk = min(1.0, k / 0.22)
            # 白過渡到黃。直接給黃的話跳出來那一格不夠亮，
            # 少了跟重音對上的那一下。
            col = tuple(int(artwork.WHT[c] + (artwork.YEL[c] - artwork.WHT[c])
                            * kk) for c in range(3))
            cy = int(rows * 0.155) + int((1 - kk) * rows * 0.02)
            _pixel_text(im, REVEAL_TEXT, cy, txt, col, artwork.DARK)

        # 落地那一下畫面震。只震那幾格，久了會像訊號不良。
        if impact:
            amp = max(2, int(rows * 0.012))
            im = im.transform(im.size, Image.AFFINE,
                              (1, 0, sa._shake(i, amp, 1), 0, 1, amp),
                              resample=Image.NEAREST)
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
    print("配樂　%.3f 秒　%d BPM　原創 chiptune"
          % (teaser_music.DUR, int(teaser_music.BPM)))

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
