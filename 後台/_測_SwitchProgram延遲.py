#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · SwitchProgram 延遲量測

**這支腳本決定續飯 COMBO 能不能做成三段累積式。**

客戶 2026-08-18 的故事線裡，客人每按一次續飯按鈕，畫面就要震一下、大一圈，
按三次爆成巨碗。這要求「按下去馬上有反應」。但我們切節目是靠
SwitchProgram，而這條路上有三件事沒人驗證過：

  一、SwitchProgram 能不能切到一個「時間窗不成立」的節目？
      手動觸發的內容（COMBO、滿額破石）都被 schedule.play_control_xml
      設成 00:00:00〜00:00:01 的假時間窗，免得它混進日常輪播。
      如果卡不肯切到這種節目，整個手動觸發的設計要重做。

  二、一次 SwitchProgram 來回要幾秒？
      超過 1.5 秒的話，客人按下按鈕要等一秒多畫面才動，
      第二下第三下更接不上 —— COMBO 的節奏會散掉。

  三、連續三次快速切換，卡撐不撐得住？
      會不會回 kProcessing、會不會掉封包、會不會愈切愈慢。

跑法（先把筆電接到卡的同一個網段）：

    python _測_SwitchProgram延遲.py            # 用 stores.json 裡的 IP
    python _測_SwitchProgram延遲.py 192.168.1.100

**前提：那張卡上要先發佈過內容**（後台按「發佈到卡」），
否則 stores.json 裡沒有 published，沒有節目可以切。
"""

import io
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(
    HERE, "..", "_明天帶去_LED實測_20260810", "02_程式端")))
sys.path.insert(0, HERE)

import hd_test as hd          # noqa: E402

SLOW = 1.5        # 秒。超過這個數字，三段累積式的 COMBO 就別做了。


def load_store(sid=None):
    d = json.load(io.open(os.path.join(HERE, "stores.json"), encoding="utf-8"))
    for s in d["stores"]:
        if sid and s["id"] != sid:
            continue
        if s.get("published") and (s.get("card") or {}).get("last_known_ip"):
            return s
    return None


def timed(fn, *a, **k):
    t0 = time.perf_counter()
    try:
        out = fn(*a, **k)
        return (time.perf_counter() - t0), out, None
    except Exception as e:
        return (time.perf_counter() - t0), None, e


def stats(name, xs):
    if not xs:
        print("  %-22s 沒有樣本" % name)
        return None
    print("  %-22s 中位 %5.0f ms   最慢 %5.0f ms   最快 %5.0f ms   (%d 次)"
          % (name, statistics.median(xs) * 1000, max(xs) * 1000,
             min(xs) * 1000, len(xs)))
    return statistics.median(xs)


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    ip = argv[0] if argv else None

    store = load_store()
    if not store and not ip:
        print("stores.json 裡找不到「有發佈過而且有 IP」的店。")
        print("先在後台把內容發佈到卡上，或直接在命令列給 IP。")
        return 2
    ip = ip or store["card"]["last_known_ip"]
    pub = (store or {}).get("published") or {}
    print("卡 %s ／ 店 %s ／ 卡上有 %d 個節目\n"
          % (ip, (store or {}).get("name", "?"), len(pub)))

    card = hd.HDCard(ip, log=lambda *a: None)
    card.connect()

    # ---------------------------------------------------------- 基準
    # 先量一個最便宜的查詢。SwitchProgram 減掉這個，才知道多出來的是
    # 「卡真的在換畫面」還是單純網路慢。
    print("[1] 網路基準（GetTimeInfo）")
    base = []
    for _ in range(10):
        dt, _, err = timed(hd.q_time_info, card)
        if not err:
            base.append(dt)
    base_med = stats("查詢來回", base) or 0.0

    # ---------------------------------------------------------- 能不能切
    print("\n[2] 切得到「時間窗不成立」的節目嗎？（手動觸發的都是這種）")
    manual = [k for k in pub if k.startswith("combo") or k == "okawari"]
    normal = [k for k in pub if k not in manual]
    if not manual:
        print("  卡上沒有手動觸發的節目，這題測不了。")
        print("  先在 stores.json 把 combo1〜3 設 enabled，發佈一次再回來。")
    else:
        k = manual[0]
        dt, out, err = timed(hd.do_switch_program, card, guid=pub[k]["program"])
        res = hd.attr(out or "", "out", "result") if not err else repr(err)
        ok = res == "kSuccess"
        print("  切到 %-10s → %s（%.0f ms）" % (k, res, dt * 1000))
        cur = hd.attr(hd.q_current_program(card), "program", "guid")
        print("  卡回報現在在播：%s%s"
              % (cur or "(沒回)", "  ← 對得上" if cur == pub[k]["program"] else ""))
        if not ok:
            print("\n  ✗ 切不過去。手動觸發的設計要改 ——")
            print("    退路 A：手動內容不設假時間窗，改用 disabled=\"true\"")
            print("    退路 B：留在輪播裡但長度設到最短")

    # ---------------------------------------------------------- 有多快
    print("\n[3] SwitchProgram 來回要多久")
    pair = (normal + manual)[:2]
    swaps = []
    if len(pair) < 2:
        print("  節目不到兩個，沒辦法來回切。")
    else:
        for i in range(10):
            k = pair[i % 2]
            dt, out, err = timed(hd.do_switch_program, card,
                                 guid=pub[k]["program"])
            if not err and hd.attr(out, "out", "result") == "kSuccess":
                swaps.append(dt)
            time.sleep(0.4)
    sw_med = stats("切節目來回", swaps)
    if sw_med is not None:
        print("  %-22s %5.0f ms（扣掉網路基準）" % ("卡自己花的時間",
                                                (sw_med - base_med) * 1000))

    # ---------------------------------------------------------- COMBO
    print("\n[4] COMBO 模擬：連按三次，中間不等")
    combo = [k for k in ("combo1", "combo2", "combo3") if k in pub]
    if len(combo) < 3:
        print("  卡上沒有完整的 combo1〜3，這題測不了。")
    else:
        t0 = time.perf_counter()
        each = []
        for k in combo:
            dt, out, err = timed(hd.do_switch_program, card,
                                 guid=pub[k]["program"])
            r = hd.attr(out or "", "out", "result") if not err else repr(err)
            each.append((k, dt, r))
        total = time.perf_counter() - t0
        for k, dt, r in each:
            print("  %-8s %5.0f ms  %s" % (k, dt * 1000, r))
        print("  三段合計 %.2f 秒" % total)

    # ---------------------------------------------------------- 結論
    print("\n" + "=" * 58)
    if sw_med is None:
        print("樣本不夠，判斷不了。先把內容發佈到卡上再跑一次。")
    elif sw_med <= SLOW:
        print("結論：%.0f ms ≤ %.1f 秒 → **三段累積式的 COMBO 可以做**。"
              % (sw_med * 1000, SLOW))
        print("      客人按下按鈕到畫面動，感覺得到但不會出戲。")
    else:
        print("結論：%.0f ms > %.1f 秒 → **三段累積式的 COMBO 不要做**。"
              % (sw_med * 1000, SLOW))
        print("      退路：三段併成一段（combo1+2+3 接成一支 14 秒的影片），")
        print("      客人按一次就播完整的三連震。故事一樣完整，")
        print("      只是失去「愈按愈大」的累積互動感。")
    print("=" * 58)
    card.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
