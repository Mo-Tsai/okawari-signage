# -*- coding: utf-8 -*-
"""
產生按鈕機的 button_config.json（在筆電上跑，不是在 M5Stack 上）。

用法：
    python 做設定檔.py                → 用 test 店（測試卡）
    python 做設定檔.py tainan        → 用台南店
    python 做設定檔.py test --router MyWiFi 12345678 192.168.50.60
                                      → 門店走 4G 分享器模式：
                                        M5Stack 連分享器的 Wi-Fi，卡接分享器網路線
                                        （最後一個參數是卡在分享器上拿到的 IP）

沒帶 --router 就是預設的「卡熱點模式」：
    M5Stack 直連卡自己發的 Wi-Fi（C16L-D24-xxx），卡固定在 192.168.6.1。

★ 每次重新「發佈到卡」之後，節目 guid 會換，要重跑這支再把
  button_config.json 傳回 M5Stack，不然按了會被卡拒絕。
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STORES = os.path.join(HERE, "..", "後台", "stores.json")
OUT = os.path.join(HERE, "button_config.json")

CARD_AP_IP = "192.168.6.1"

# 累積熱度的門檻：今天第幾碗開始升級。
#   1–9 碗 → COMBO 1 ／ 10–29 碗 → COMBO 2 ／ 30 碗以後 → COMBO 3
# ★ 門市要調就改這兩個數字。機器上不會顯示，店員不知道下一碗會不會出 COMBO。
THRESHOLDS = [10, 30]

# 檔期畫面每隔幾秒插播一次（彩蛋是整點放一次，不走這個）。
PROMO_EVERY = 180     # 檔期插播間隔（秒）。2026-09-01 台中開幕日：賣場反應
#                       「都沒有看到活動」。實際不是沒送，是 600 秒送一次、
#                       每次 13 秒 —— 檔期只佔螢幕時間的 3.8%，走過去看一眼
#                       幾乎遇不到。改 180 秒後佔比約 13%。
EGG_EVERY = 1800      # 彩蛋插播間隔（秒）。2026-09-01 Mo：「彩蛋半小時」
#
# ★ 彩蛋原本是「整點那一分鐘放一次，一天一次」（窗 12:00:00–12:01:00，沒有 every）。
#   賣場反應畫面不夠忙，改成每半小時一次。做法是把窗從「一分鐘」放寬成
#   「那整個小時」，再配 every=1800 —— 於是 12:00 放一次、12:30 再放一次，
#   13:00 換下一支。每支彩蛋各自佔一個小時，不會互相搶（_auto_tick 是
#   照清單順序挑第一支到期的，同一時間只有一支彩蛋在窗內）。


def hhmmss(v):
    """"22:30" → "22:30:00"；已經是 HH:MM:SS 就原樣。空的回 None。"""
    if not v:
        return None
    p = str(v).split(":")
    while len(p) < 3:
        p.append("00")
    return "%02d:%02d:%02d" % (int(p[0]), int(p[1]), int(p[2]))


def main():
    args = sys.argv[1:]
    sid = args[0] if args and not args[0].startswith("--") else "test"

    with open(STORES, encoding="utf-8") as f:
        data = json.load(f)
    store = None
    for s in data["stores"]:
        if s["id"] == sid:
            store = s
            break
    if not store:
        raise SystemExit("stores.json 裡沒有店號「%s」" % sid)

    published = store.get("published") or {}
    if not published:
        raise SystemExit("「%s」還沒發佈過節目，先在後台按「發佈到卡」" % sid)

    if "--router" in args:
        i = args.index("--router")
        ssid, pw, card_ip = args[i + 1], args[i + 2], args[i + 3]
        mode = "router（4G 分享器）"
    else:
        ap = (store.get("card") or {}).get("wifi_ap") or {}
        ssid = ap.get("ssid") or ""
        pw = ap.get("password") or ""
        card_ip = CARD_AP_IP
        mode = "card-ap（卡自己的熱點）"
        if not ssid:
            raise SystemExit("stores.json 裡這家店沒有 wifi_ap 資料，"
                             "改用 --router 模式或補上熱點資訊")

    programs = {k: {"guid": v["program"], "seconds": v.get("seconds") or 10}
                for k, v in published.items()}

    # 按鍵 → 事件的對應。
    #
    # ★ 2026-08-24 兩個改動（Mo）：
    #   1. 左右對調。「+1」移到**右鍵**（靠客人那一側），滿千送百移到中間鍵。
    #   2. 續碗改成 type="streak"（累積熱度）：級數由今天累計第幾碗決定，
    #      不是靠三秒內連打。門檻寫在下面的 THRESHOLDS，之後門市要調就改
    #      這個數字 —— **機器上不顯示級距**，店員也不該知道下一碗會不會出
    #      COMBO，那件事要一直是驚喜。
    keys = {}

    if all(k in programs for k in ("combo1", "combo2", "combo3")):
        streak = {"type": "streak", "label": "續碗", "symbol": "+1",
                  "stages": ["combo1", "combo2", "combo3"],
                  "thresholds": THRESHOLDS}
    else:
        streak = {"type": "dice", "label": "續碗", "symbol": "+1",
                  "hit": "okawari", "miss": "okawari_miss", "chance": 0.25}
    keys["promo"] = streak            # promo = 右鍵（BtnC）
    # 滿額 1000 發佈了就自動掛上右鍵。
    # 注意 key 的歷史包袱：續碗原本是擲骰（okawari／okawari_miss），後來改成
    # COMBO 三段，舊的 okawari 這個 key 就被「滿額 1000：劈石 → GOLDEN BOWL」
    # 接手了（stores.json 裡它的 art 是 bonus、trigger 是 manual／店員觸發）。
    # 所以這裡兩個名字都認：man1000 是將來若改名用的，okawari 是現況。
    for k in ("man1000", "okawari"):
        if k in programs:
            keys["main"] = {"type": "single", "label": "滿千送百",
                            "symbol": "$", "key": k}   # main = 中間鍵（BtnB）
            break

    # ★ 自動插播清單，**只有架構 B 才產生**。
    #
    #   架構 A（manual_trigger = false）：整點彩蛋和檔期由卡自己輪播。
    #       M5 絕對不能再送一次 —— 兩邊都放的話同一支會連放兩次。
    #       這裡直接留空，M5 就只剩兩顆按鍵。
    #   架構 B（manual_trigger = true）：時段畫面 count=999，卡輪不到彩蛋和檔期，
    #       改由 M5 主動送 SwitchProgram。
    manual_ok = bool((store.get("schedule") or {}).get("manual_trigger"))
    auto = []
    for c in (store.get("contents") or []) if manual_ok else []:
        k = c.get("key")
        if not c.get("enabled") or k not in programs:
            continue
        w = c.get("when") or {}
        if k.startswith("egg_"):
            tw = w.get("time")
            if tw:
                # 「整點那一分鐘」→「那整個小時」，收尾不超過關屏時間
                h = int(tw[0][:2])
                end = "%02d:00:00" % (h + 1) if h < 23 else "23:59:59"
                close = hhmmss((store.get("schedule") or {}).get("close")) or end
                tw = [tw[0], min(end, close)]
            auto.append({"key": k, "label": c.get("name") or k,
                         "time": tw, "every": EGG_EVERY})
        elif k.startswith("promo_"):
            e = {"key": k, "label": c.get("name") or k,
                 "time": w.get("time"), "every": PROMO_EVERY}
            if w.get("date"):
                e["date"] = w["date"]
            auto.append(e)

    cfg = {
        "store": store["id"],
        "store_name": store["name"],
        "wifi": {"ssid": ssid, "password": pw},
        "card": {"ip": card_ip, "port": 10001},
        "keys": keys,
        # 哪些 key 算「時段畫面」。播完插播要切回這裡面的其中一支 ——
        # 不限制的話，剛放完彩蛋時抓到的會是彩蛋，之後就越跑越歪。
        #
        # ★ 整點 LOGO 跑燈（logo_slot）雖然也掛在 base 層，但**不算時段畫面**。
        #   它一個小時只開一分鐘。M5 如果在那一分鐘記下它當回歸點，
        #   之後每放完一支插播都會想切回 LOGO —— 而那時窗早就關了，
        #   卡切不動，畫面就會留在插播上。排除掉，那一分鐘 M5 沿用舊的回歸點。
        "segments": [c["key"] for c in (store.get("contents") or [])
                     if c.get("enabled") and c.get("layer") == "base"
                     and not c.get("logo_slot")],
        "auto": auto,
        "programs": programs,
    }
    # ★ 2026-08-24：保留舊設定檔裡「這支不會產生」的欄位（nap、brightness…）。
    #   原本每重產一次就把現場調好的值洗掉一次 —— 亮度 200、午睡節奏都是在
    #   實機上試出來的，不該因為節目換 guid 就歸零。這天就真的洗掉過一次。
    kept = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                kept = {k: v for k, v in json.load(f).items() if k not in cfg}
        except Exception as e:
            print("  （舊設定檔讀不到，沒有東西可以保留：%r）" % e)
    if kept:
        print("  保留舊設定：%s" % "、".join(sorted(kept)))
    cfg.update(kept)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("寫好了 → %s" % OUT)
    print("  店：%s（%s）" % (store["name"], store["id"]))
    print("  模式：%s" % mode)
    print("  Wi-Fi：%s ／ 卡位址：%s" % (ssid, card_ip))
    print("  節目 %d 支：%s" % (len(programs), ", ".join(sorted(programs))))
    # ★ 2026-08-25 修：這裡原本寫 main_key["type"]，但那個名字根本不存在 ——
    #   NameError。檔案是寫完了才爆，所以「以為只是印訊息壞掉」很容易忽略，
    #   但它會讓後面「接下來把設定檔傳進 M5」那句提示也印不出來。
    for side, k in (("中鍵", "main"), ("右鍵", "promo")):
        act = keys.get(k)
        if act:
            print("  %s：%s（%s）" % (side, act.get("label", "?"),
                                      act.get("type", "?")))
        else:
            print("  %s：（還沒發佈對應的節目，先空著）" % side)
    print("接下來把 button_config.json 傳進 M5Stack（見 怎麼燒錄.md）")


if __name__ == "__main__":
    main()
