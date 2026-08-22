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

    # 按鍵 → 事件的對應。發佈了 combo1~3 就用 combo，否則退回擲骰版。
    if all(k in programs for k in ("combo1", "combo2", "combo3")):
        main_key = {"type": "combo", "label": "續碗",
                    "stages": ["combo1", "combo2", "combo3"]}
    else:
        main_key = {"type": "dice", "label": "續碗",
                    "hit": "okawari", "miss": "okawari_miss", "chance": 0.25}

    keys = {"main": main_key}
    if "man1000" in programs:            # 滿千送百之後發佈了就自動掛上右鍵
        keys["promo"] = {"type": "single", "label": "滿千送百", "key": "man1000"}

    cfg = {
        "store": store["id"],
        "store_name": store["name"],
        "wifi": {"ssid": ssid, "password": pw},
        "card": {"ip": card_ip, "port": 10001},
        "keys": keys,
        "programs": programs,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("寫好了 → %s" % OUT)
    print("  店：%s（%s）" % (store["name"], store["id"]))
    print("  模式：%s" % mode)
    print("  Wi-Fi：%s ／ 卡位址：%s" % (ssid, card_ip))
    print("  節目 %d 支：%s" % (len(programs), ", ".join(sorted(programs))))
    print("  中鍵：%s" % main_key["type"])
    print("  右鍵：%s" % ("man1000" if "promo" in keys else "（滿千送百還沒發佈，先空著）"))
    print("接下來把 button_config.json 傳進 M5Stack（見 怎麼燒錄.md）")


if __name__ == "__main__":
    main()
