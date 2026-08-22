# -*- coding: utf-8 -*-
"""
按鈕機的桌上測試（在筆電上跑，M5Stack 沒到貨也能先驗證整條路）。

它跑的是跟 M5Stack 一模一樣的 hdlink.py 核心，
只是把三顆實體鍵換成鍵盤：

    Enter 或 空白鍵  = 中鍵（續碗）
    p                = 右鍵（滿千送百）
    r                = 左鍵（重新連線）
    q                = 離開

事前準備：
    1. 測試卡接電
    2. 筆電連上卡的 Wi-Fi 熱點（C16L-D24-000A2）
       （或分享器模式：筆電和卡連同一台分享器）
    3. python 做設定檔.py    ← 先產生 button_config.json
    4. python 桌上測試.py
"""

import json
import msvcrt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hdlink

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "button_config.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    print("=" * 56)
    print("OKAWARI 按鈕機 · 桌上測試")
    print("店：%s ／ 卡：%s" % (cfg.get("store_name", cfg["store"]),
                              cfg["card"]["ip"]))
    print("Enter/空白=續碗   p=滿千送百   r=重連   q=離開")
    print("=" * 56)

    core = hdlink.ButtonCore(cfg, log=lambda m: print("  ·", m))
    last = None
    while True:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch == "q":
                break
            r = None
            if ch in ("\r", " "):
                r = core.press("main")
            elif ch == "p":
                r = core.press("promo")
            elif ch == "r":
                r = core.press("reconnect")
            if r:
                print("  → %s" % r)

        core.tick()

        snap = (core.state, core.msg, int(core.remaining()))
        if snap != last:
            last = snap
            face = {"connect": "藍·連線中", "ready": "綠·就緒",
                    "playing": "橘·播放中", "error": "紅·錯誤"}[core.state]
            extra = "（剩 %d 秒）" % snap[2] if core.state == "playing" else ""
            print("[%s]%s %s ｜今日 %d 次"
                  % (face, extra, core.msg, core.count_today))

        time.sleep(0.05)

    print("結束。")


if __name__ == "__main__":
    main()
