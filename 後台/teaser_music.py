#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 預告片 · 配樂（原創 chiptune）

★ 為什麼是自己合成，不是去找免費曲庫

  1. 授權乾淨。這支片要交給業主、要上 IG，用曲庫的東西就得追授權條款、
     要不要標示、能不能商用、平台會不會誤判 —— 每一項都是之後的麻煩。
     自己算出來的波形沒有這個問題。
  2. 長度剛好。128 BPM、8 小節＝15.000 秒，跟影片的 375 格是同一個數字，
     不必淡出、不必剪。段落分界也對得上分鏡：第 7 小節那個大和弦
     就是「8.26 公開」跳出來的那一格。
  3. 音色對。畫面是像素的，方波就是像素的聲音。真樂器配 8-bit 畫面
     會有一種「配錯了」的違和感。

★ 和弦走向是 C - G - Am - F

  最常見的四個和弦，理由就是它最好聽也最不容易出錯。
  和弦進行本身不受著作權保護（受保護的是旋律），
  旋律是這裡自己寫的，沒有引用任何既有曲子。

聲部：
    lead     方波 50% —— 主旋律
    harmony  方波 25% —— 琶音襯底，比主旋律低一個八度
    bass     三角波 —— 根音與五度
    perc     雜訊 —— hi-hat 與 snare

    python teaser_music.py out.wav
"""

import math
import struct
import sys
import wave

import numpy as np

SR = 44100
BPM = 128.0
BEAT = 60.0 / BPM                  # 0.46875 秒
BAR = BEAT * 4                     # 1.875 秒
BARS = 8
DUR = BAR * BARS                   # 15.000 秒，剛好

# ---------------------------------------------------------------- 音高
NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def hz(name):
    """'A4' → 440.0。'-' 是休止，回 0。"""
    if not name or name == "-":
        return 0.0
    step = NAMES[name[0]]
    i = 1
    if len(name) > 1 and name[1] in "#b":
        step += 1 if name[1] == "#" else -1
        i = 2
    octave = int(name[i:])
    return 440.0 * (2.0 ** ((step - 9) / 12.0 + (octave - 4)))


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
# 分鏡對照：
#   1-2  空屏 → 配角開始進場        （琶音鋪底，不搶戲）
#   3-4  配角站定                    （旋律進來）
#   5-6  小飯碗從左邊走進來          （旋律往上走）
#   7    到位、歡呼 → 8.26 公開跳出  （★ 這一拍是全曲最高點）
#   8    收尾                        （解決到主和弦）

LEAD = [
    ". . . . . . . .",
    ". . . . . . . .",
    "E5 - G5 A5 G5 E5 C5 -",
    "D5 - G5 B5 A5 G5 D5 -",
    "C5 - E5 A5 G5 E5 C5 -",
    "A4 C5 F5 A5 G5 F5 E5 D5",
    "C6 - - - G5 A5 B5 C6",          # ★ 第 7 小節：衝上去
    "C6 - - - - - - -",
]

HARMONY = [
    "C4 E4 G4 E4 C4 E4 G4 E4",
    "D4 G4 B4 G4 D4 G4 B4 G4",
    "C4 E4 G4 E4 C4 E4 G4 E4",
    "B3 D4 G4 D4 B3 D4 G4 D4",
    "A3 C4 E4 C4 A3 C4 E4 C4",
    "F3 A3 C4 A3 F3 A3 C4 A3",
    "E4 G4 C5 G4 E4 G4 C5 G4",
    "C4 E4 G4 C5 G4 E4 C4 -",
]

BASS = [
    "C2 - G2 - C2 - G2 -",
    "G2 - D2 - G2 - D2 -",
    "C2 - C2 - G2 - G2 -",
    "G2 - G2 - D2 - D2 -",
    "A2 - A2 - E2 - E2 -",
    "F2 - F2 - C2 - C2 -",
    "G2 - G2 - G2 - G2 -",
    "C2 - - - C2 - - -",
]


def _render(score, voice, gain, seed=0):
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
            # 後面接幾個 '-' 就延長幾個八分音符
            hold = 1
            while j + hold < len(toks) and toks[j + hold] == "-":
                hold += 1
            f = hz(toks[j])
            if f > 0:
                t0 = b * BAR + j * step
                n = int(step * hold * SR)
                i0 = int(t0 * SR)
                # 長音的衰減要慢一點，不然拉長的音會先斷掉再空一段
                e = env(n, decay=0.10 if hold < 3 else 0.30,
                        sustain=0.62 if hold < 3 else 0.55)
                out[i0:i0 + n] += voice(f, n) * e * gain
            j += hold
    return out[:int(DUR * SR)]


def _drums():
    """hi-hat 每個八分、snare 在第 2、4 拍、kick 在第 1、3 拍。

    第 1-2 小節只有 hi-hat —— 鼓一開始就全下去的話，
    後面旋律進來就沒有「多了一層」的感覺。
    """
    out = np.zeros(int(DUR * SR), dtype=np.float64)

    def put(t, wave_, g):
        i0 = int(t * SR)
        n = len(wave_)
        if i0 + n <= len(out):
            out[i0:i0 + n] += wave_ * g

    hat = noise(int(0.030 * SR), 7) * env(int(0.030 * SR), 0.001, 0.010,
                                          0.05, 0.018)
    sn = noise(int(0.14 * SR), 11) * env(int(0.14 * SR), 0.001, 0.06,
                                         0.22, 0.08)
    kn = int(0.13 * SR)
    kick = (np.sin(2 * math.pi * np.cumsum(
        np.linspace(110.0, 42.0, kn)) / SR) *
        env(kn, 0.001, 0.05, 0.30, 0.07))

    for b in range(BARS):
        for e8 in range(8):
            t = b * BAR + e8 * BEAT / 2.0
            put(t, hat, 0.10 if e8 % 2 else 0.16)
        if b >= 2:                                   # 第 3 小節才進鼓組
            put(b * BAR + 0 * BEAT, kick, 0.55)
            put(b * BAR + 2 * BEAT, kick, 0.50)
            put(b * BAR + 1 * BEAT, sn, 0.26)
            put(b * BAR + 3 * BEAT, sn, 0.26)
    # 第 7 小節第一拍：重音。畫面上「8.26 公開」就是這一格跳出來的
    put(6 * BAR, kick, 0.85)
    put(6 * BAR, sn, 0.38)
    return out


def build():
    """回傳 (左聲道, 右聲道)，float64，範圍已經壓在 ±1 內。"""
    lead = _render(LEAD, lambda f, n: square(f, n, 0.5), 0.26)
    harm = _render(HARMONY, lambda f, n: square(f, n, 0.25), 0.13)
    bass = _render(BASS, triangle, 0.30)
    drum = _drums()

    # 前兩小節整體壓低，讓「東西一層一層加進來」聽得出來
    ramp = np.ones(len(lead))
    intro = int(2 * BAR * SR)
    ramp[:intro] = np.linspace(0.45, 1.0, intro)

    mix = (lead + harm + bass) * ramp + drum
    # 收尾淡出半拍。硬切在 IG 上會是「啪」一聲
    fade = int(BEAT * 0.5 * SR)
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
