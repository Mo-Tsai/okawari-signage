#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把所有段落編成提案頁要用的 mp4，輸出到 ../docs/preview/。

提案頁（docs/preview.html）放的是**實際輸出檔**，不是網頁特效 ——
業主在頁面上看到的，就是那一段真的上屏會長的樣子。所以這支腳本
跟正式發佈走同一條路：同一組 renderer、同一個畫布、同一套參數。

跑法：

    python _出提案影片.py            # 全部重編
    python _出提案影片.py bogo bonus  # 只編指定的幾段

畫布固定用台南小北的 960×120。中港是 1040×120，比例差 8%，
提案階段沒必要各出一套 —— 真正上屏前發佈流程會按各店畫布重編。
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import artwork                                   # noqa: E402

OUT = os.path.abspath(os.path.join(HERE, "..", "docs", "preview"))
COLS, ROWS = 960, 120
SCALE = 2                    # 輸出放大兩倍，網頁上比較好看（像素照樣是硬邊）

# 段落 → 提案頁上的名字。順序就是提案頁上的順序。
SEGMENTS = [
    ("opening", "開店"),
    ("noon", "中午"),
    ("siesta", "午後"),
    ("evening", "晚間"),
    ("combo1", "續飯 COMBO 1"),
    ("combo2", "續飯 COMBO 2"),
    ("combo3", "續飯 COMBO 3"),
    ("bonus", "滿額 1000"),
    ("bogo", "買一送一"),
    ("promo_open", "開幕全員集合"),
    ("promo_egg", "10 元溫泉蛋"),
    ("egg1", "彩蛋 手電筒巡邏"),
    ("egg2", "彩蛋 RICE POWER"),
    ("egg3", "彩蛋 接力賽"),
]
CHARS = ("person", "ricebowl")


def encode(frames, path, fps):
    """PNG 序列 → mp4。用 ffmpeg 的 -crf 18，肉眼看不出壓縮痕跡。

    像素風一定要 neighbor 縮放。用預設的雙線性會把硬邊糊掉，
    上屏之後看起來就是「怎麼有點髒」。
    """
    tmp = tempfile.mkdtemp()
    try:
        for i, im in enumerate(frames):
            im.resize((COLS * SCALE, ROWS * SCALE), 0).save(
                os.path.join(tmp, "f_%05d.png" % i))
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-framerate", str(fps), "-i", os.path.join(tmp, "f_%05d.png"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
             "-movflags", "+faststart", path],
            check=True)
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)


def main():
    want = set(sys.argv[1:])
    os.makedirs(OUT, exist_ok=True)
    todo = [x for x in SEGMENTS if not want or x[0] in want]
    if not todo:
        print("沒有這幾段：%s" % ", ".join(sorted(want)))
        return 2

    for key, label in todo:
        fn = artwork.RENDERERS.get(key)
        if not fn:
            print("  %-10s 還沒有美術，跳過" % key)
            continue
        for ch in CHARS:
            p = artwork.params({"character": ch})
            fps = int(p["%s_fps" % artwork.param_key(key)])
            frames = fn(COLS, ROWS, p)
            path = os.path.join(OUT, "%s_%s.mp4" % (key, ch))
            encode(frames, path, fps)
            print("  %-10s %-9s %3d 格 @ %2d fps = %4.1f 秒   %5.0f KB"
                  % (label, ch, len(frames), fps, len(frames) / fps,
                     os.path.getsize(path) / 1024))
    print("\n輸出到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
