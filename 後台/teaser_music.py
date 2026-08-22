#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 預告片 · 配樂（原創 chiptune）

★ 為什麼是自己合成，不是去找免費曲庫

  1. 授權乾淨。這支片要交給業主、要上 IG，用曲庫的東西就得追授權條款、
     要不要標示、能不能商用、平台會不會誤判 —— 每一項都是之後的麻煩。
     自己算出來的波形沒有這個問題。
  2. 長度剛好。120 BPM、10 小節＝20.000 秒，跟影片的 500 格是同一個數字，
     不必淡出、不必剪。
  3. 音色對。畫面是像素的，方波就是像素的聲音。

★ 曲子的結構是照分鏡寫的，不是寫好一段循環播完

  一開始就全部樂器下去，畫面再怎麼安排都會顯得平。所以分成三段：

    第 1-3 小節（0-6 秒）  探照燈。只有一個低音長音 ＋ 每一拍一顆高音「嗶」。
                           那顆嗶就是燈閃的那一下 —— 聲音和畫面同一拍。
                           沒有鼓、沒有旋律，因為這時候畫面上什麼都沒有。
    第 4 小節（6-8 秒）    形體顯現 → 黑幕。低音壓住，後半進一個 riser
                           （音高一路往上爬 ＋ 雜訊變大），最後一拍全部收掉。
                           那個空白就是黑幕。
    第 5-10 小節（8-20 秒）燈亮，全部樂器一起進來。第 9 小節第一拍是
                           主角落地的重音：大和弦 ＋ 一記 crash。

  和弦走 C - G - Am - F - G - C。和弦進行本身不受著作權保護
  （受保護的是旋律），旋律是這裡自己寫的，沒有引用任何既有曲子。

聲部：
    lead     方波 50% —— 主旋律
    harmony  方波 25% —— 琶音襯底
    blip     方波 12.5% —— 探照燈那三小節的高音點
    bass     三角波 —— 根音與五度
    perc     雜訊 —— hi-hat／snare／kick／crash

    python teaser_music.py out.wav
"""

import math
import struct
import sys
import wave

import numpy as np

SR = 44100
BPM = 120.0
BEAT = 60.0 / BPM                  # 0.5 秒
BAR = BEAT * 4                     # 2.0 秒
BARS = 10
DUR = BAR * BARS                   # 20.000 秒，剛好

BAND_IN = 4                        # 第幾小節開始全部樂器進來（0 起算）
ACCENT_BAR = 8                     # 主角落地的那一小節（0 起算＝第 9 小節）

# ---------------------------------------------------------------- 音高
NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def hz(name):
    """'A4' → 440.0。'-' 是延續、'.' 是休止，都回 0。"""
    if not name or name in ("-", "."):
        return 0.0
    step = NAMES[name[0]]
    i = 1
    if len(name) > 1 and name[1] in "#b":
        step += 1 if name[1] == "#" else -1
        i = 2
    return 440.0 * (2.0 ** ((step - 9) / 12.0 + (int(name[i:]) - 4)))


# ---------------------------------------------------------------- 波形
def _phase(f, n):
    """一段固定頻率的相位。用累加而不是 linspace ——
    音跟音接起來的地方要連續，不然每個音頭都有一聲 click。"""
    return np.cumsum(np.full(n, f / SR))


def square(f, n, duty=0.5):
    return np.where((_phase(f, n) % 1.0) < duty, 1.0, -1.0)


def triangle(f, n):
    p = _phase(f, n) % 1.0
    return 4.0 * np.abs(p - 0.5) - 1.0


def noise(n, seed):
    """固定種子。每次跑要產生一模一樣的檔 ——
    跟 _shake／_confetti 同一個理由，重編不該變成新檔。"""
    return np.random.RandomState(seed).uniform(-1.0, 1.0, n)


def env(n, attack=0.004, decay=0.10, sustain=0.62, release=0.05):
    """音量包絡。chiptune 的重點在快起音 + 明顯衰減，
    不做的話每個音都是一塊方磚，聽起來像警報器不像旋律。"""
    a = max(1, int(attack * SR))
    d = max(1, int(decay * SR))
    r = max(1, int(release * SR))
    s = max(0, n - a - d - r)
    return np.concatenate([
        np.linspace(0.0, 1.0, a),
        np.linspace(1.0, sustain, d),
        np.full(s, sustain),
        np.linspace(sustain, 0.0, r),
    ])[:n]


# ---------------------------------------------------------------- 譜
# 每一行是一小節，八個八分音符。'-' 是延續（不重新起音）、'.' 是休止。
#
# 分鏡對照（0 起算的小節）：
#   0-2  探照燈掃、一閃一閃          只有 bass 長音 + blip
#   3    形體顯現 → 黑幕             低音壓住 + riser，最後一拍全空
#   4-7  燈亮、賓客陸續走進來        全部進來
#   8    ★ 主角落地                  大和弦 + crash
#   9    布條搖起來 → 收             解決到主和弦

LEAD = [
    ". . . . . . . .",
    ". . . . . . . .",
    ". . . . . . . .",
    ". . . . . . . .",
    "E5 - G5 A5 G5 E5 C5 -",
    "D5 - G5 B5 A5 G5 D5 -",
    "C5 - E5 A5 G5 E5 C5 -",
    "A4 C5 F5 A5 G5 F5 E5 D5",
    "C6 - - - - - - -",                 # ★ 落地
    "C6 - - - G5 A5 B5 C6",             # 布條
]

HARMONY = [
    ". . . . . . . .",
    ". . . . . . . .",
    ". . . . . . . .",
    ". . . . . . . .",
    "C4 E4 G4 E4 C4 E4 G4 E4",
    "B3 D4 G4 D4 B3 D4 G4 D4",
    "A3 C4 E4 C4 A3 C4 E4 C4",
    "F3 A3 C4 A3 F3 A3 C4 A3",
    "E4 G4 C5 G4 E4 G4 C5 G4",
    "C4 E4 G4 C5 G4 E4 C4 -",
]

# 探照燈那三小節的高音點。每一拍一顆，跟畫面上燈閃的那一下同一拍。
BLIP = [
    "E6 . . . B5 . . .",
    "E6 . . . B5 . . .",
    "F6 . . . C6 . . .",
    ". . . . . . . .",
]

BASS = [
    "C2 - - - - - - -",                 # 探照燈：一個低音長音壓著
    "C2 - - - - - - -",
    "A2 - - - - - - -",                 # 開始有點不安
    "F2 - - - - - - -",                 # 形體顯現 → 黑幕
    "C2 - C2 - G2 - G2 -",
    "G2 - G2 - D2 - D2 -",
    "A2 - A2 - E2 - E2 -",
    "F2 - F2 - C2 - C2 -",
    "C2 - - - C2 - - -",                # ★ 落地
    "C2 - - - G2 - C2 -",
]


def _render(score, voice, gain):
    """把一份譜變成一條音軌。"""
    out = np.zeros(int(DUR * SR) + SR, dtype=np.float64)
    step = BEAT / 2.0                       # 八分音符
    for b, bar in enumerate(score):
        toks = bar.split()
        j = 0
        while j < len(toks):
            if toks[j] == ".":
                j += 1
                continue
            hold = 1                        # 後面接幾個 '-' 就延長幾個八分
            while j + hold < len(toks) and toks[j + hold] == "-":
                hold += 1
            f = hz(toks[j])
            if f > 0:
                i0 = int((b * BAR + j * step) * SR)
                n = int(step * hold * SR)
                # 長音衰減要慢，不然拉長的音會先斷掉再空一段
                e = env(n, decay=0.10 if hold < 3 else 0.45,
                        sustain=0.62 if hold < 3 else 0.42)
                out[i0:i0 + n] += voice(f, n) * e * gain
            j += hold
    return out[:int(DUR * SR)]


def _riser(out, start, dur):
    """黑幕前的那一段爬升。音高一路往上 ＋ 雜訊同時變大。

    這是給「等一下要發生事情」用的。沒有它，黑幕只是聲音突然停掉，
    聽起來像檔案壞了，不像屏息。
    """
    n = int(dur * SR)
    i0 = int(start * SR)
    f = np.linspace(180.0, 1500.0, n)
    tone = np.where((np.cumsum(f / SR) % 1.0) < 0.5, 1.0, -1.0)
    swell = np.linspace(0.0, 1.0, n) ** 2.2
    out[i0:i0 + n] += tone * swell * 0.16
    out[i0:i0 + n] += noise(n, 23) * swell * 0.10
    return out


def _drums():
    """hi-hat 每個八分、snare 在第 2、4 拍、kick 在第 1、3 拍。

    第 5 小節（BAND_IN）才進來。前面畫面上什麼都沒有，鼓一下去就滿了。
    """
    out = np.zeros(int(DUR * SR), dtype=np.float64)

    def put(t, w, g):
        i0 = int(t * SR)
        if i0 + len(w) <= len(out):
            out[i0:i0 + len(w)] += w * g

    hat = noise(int(0.030 * SR), 7) * env(int(0.030 * SR), 0.001, 0.010,
                                          0.05, 0.018)
    sn = noise(int(0.15 * SR), 11) * env(int(0.15 * SR), 0.001, 0.06,
                                         0.22, 0.085)
    kn = int(0.14 * SR)
    kick = (np.sin(2 * math.pi * np.cumsum(
        np.linspace(115.0, 40.0, kn)) / SR) * env(kn, 0.001, 0.05, 0.30, 0.08))
    cn = int(1.10 * SR)
    crash = noise(cn, 31) * (np.linspace(1.0, 0.0, cn) ** 2.4)

    for b in range(BAND_IN, BARS):
        for e8 in range(8):
            put(b * BAR + e8 * BEAT / 2.0, hat, 0.10 if e8 % 2 else 0.16)
        put(b * BAR + 0 * BEAT, kick, 0.55)
        put(b * BAR + 2 * BEAT, kick, 0.50)
        put(b * BAR + 1 * BEAT, sn, 0.26)
        put(b * BAR + 3 * BEAT, sn, 0.26)

    # ★ 主角落地那一拍：重音 ＋ crash。畫面上是全員被彈起來的那一格。
    put(ACCENT_BAR * BAR, kick, 0.95)
    put(ACCENT_BAR * BAR, crash, 0.30)
    return out


def build():
    """回傳 (左聲道, 右聲道)，float64，範圍已經壓在 ±1 內。"""
    lead = _render(LEAD, lambda f, n: square(f, n, 0.5), 0.26)
    harm = _render(HARMONY, lambda f, n: square(f, n, 0.25), 0.13)
    blip = _render(BLIP, lambda f, n: square(f, n, 0.125), 0.14)
    bass = _render(BASS, triangle, 0.30)
    drum = _drums()

    mix = lead + harm + blip + bass + drum
    mix = _riser(mix, 3 * BAR + 2 * BEAT, BEAT * 1.6)

    # 黑幕：最後半拍全部收掉。那個空白是畫面全黑的那一段。
    gap0 = int((3 * BAR + 3.6 * BEAT) * SR)
    gap1 = int(BAND_IN * BAR * SR)
    mix[gap0:gap1] *= np.linspace(1.0, 0.0, max(1, gap1 - gap0))

    # 收尾淡出半拍。硬切在 IG 上會是「啪」一聲
    fade = int(BEAT * 0.6 * SR)
    mix[-fade:] *= np.linspace(1.0, 0.0, fade)

    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.90

    # 立體聲：主旋律偏右一點點、琶音偏左一點點。
    # 手機喇叭是單聲道，但戴耳機的人會覺得比較開。
    left = mix - lead * 0.06 / peak + harm * 0.06 / peak
    right = mix + lead * 0.06 / peak - harm * 0.06 / peak
    return np.clip(left, -1, 1), np.clip(right, -1, 1)


def write(path):
    left, right = build()
    inter = np.empty(len(left) * 2, dtype=np.int16)
    inter[0::2] = (left * 32000).astype(np.int16)
    inter[1::2] = (right * 32000).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(struct.pack("<%dh" % len(inter), *inter))
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "teaser.wav"
    write(out)
    print("%s  %.3f 秒  %d BPM  %d 小節" % (out, DUR, int(BPM), BARS))
