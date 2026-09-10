# -*- coding: utf-8 -*-
"""在 stores.json 的時段表上，每小時挖一分鐘出來給 LOGO 跑燈。

    python _排整點LOGO.py tainan taichung      排入（預設每小時 45 分，跑一分鐘）
    python _排整點LOGO.py tainan --分 30       換一個分鐘
    python _排整點LOGO.py tainan --拿掉        全部還原成沒有 LOGO 的樣子

可以重複跑。它每次都先還原、再重排，所以跑第二次的結果跟第一次一樣。


★ 為什麼要「挖」，不是「疊一支上去」
================================================================
這張卡上，**一支節目切得動的充要條件，就是它現在正排在輪播名單裡**
（2026-08-24 真卡實測，見 schedule.py 的長註解）。

現在跑的是架構 B：櫃檯按鈕要能按，所以時段畫面是 `count=999` ——
一支播完接著播自己，五個半小時，**在時段結束前永遠輪不到別人**。
整點彩蛋和開幕檔期就是這樣被犧牲掉的，它們改由櫃檯 M5 主動送。

所以 LOGO 如果只是「多加一支有時段的節目」，它**永遠不會出現**。
唯一能讓卡自己放的辦法，是**把那一分鐘從時段畫面的窗裡挖掉** ——
時段畫面在那一分鐘沒資格，卡就只剩 LOGO 可播。

這樣做的好處是它**不依賴 M5**：
台南現在還沒裝按鈕機，彩蛋和檔期在那面屏上根本沒放過；
LOGO 走這條路，兩家店都會動，而且店員重灌之後也還在。


★ 為什麼一支節目一個窗，不用 SDK 的「多個 time 標籤」
================================================================
SDK 文件寫 `<time>` 「允许多个」，那樣做的話 noon 一支就能帶四個窗，
卡上的節目數完全不會增加 —— 比現在這個做法漂亮很多。

**但那個行為我們沒有在真卡上驗過。** 而它萬一只認第一個窗，
noon 就只有 11:30–11:45 有資格，11:45 之後整個中午沒有任何時段畫面
—— 卡會去輪到 COMBO（2026-08-17 那次「客人沒續碗卻自己跳出來」的事故）。
現場只有一次機會，不拿這個換好看。

一支一個窗是**今天台中屏上正在跑的行為**，沒有新東西。
代價是節目數從 24 變成 40 幾支，影片只多一支（所有碎片共用同一份美術）。


★ 為什麼窗是「一整分鐘」，影片只有 20 秒
================================================================
卡不是每秒鐘去比對時鐘的，它是**播完手上這一支才重新算「現在誰有資格」**。
時段影片一支 20 秒，所以窗開了之後，最久要 20 秒卡才會發現。

窗如果只給 20 秒，卡有機會整個錯過 —— 那會變成「有時候有、有時候沒有」，
是最難查的一種故障。給滿一分鐘，扣掉最壞的 20 秒還剩 40 秒，
**保證至少完整跑過一遍**（實際會跑兩到三遍）。

影片頭尾各留一段乾淨綠底（`logo_pad`），所以重播和被切走都落在綠底上，
看起來就只是綠底停了一下，不會看到 logo 跳回右邊。
"""
import argparse
import io
import json
import os
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
HERE = os.path.dirname(os.path.abspath(__file__))
STORES = os.path.join(HERE, "stores.json")

LOGO_ART = "logo"
SLOT_LEN = 60          # 窗開幾秒。理由見檔頭。


# ---------------------------------------------------------------- 時間
def sec(t):
    """'11:30' 或 '11:30:00' → 當天的第幾秒。"""
    p = [int(x) for x in str(t).split(":")]
    while len(p) < 3:
        p.append(0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def hms(s):
    return "%02d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def subtract(span, cuts):
    """從一段時間裡挖掉好幾段，回傳剩下的段落。"""
    out = [span]
    for c0, c1 in cuts:
        nxt = []
        for a, b in out:
            if c1 <= a or c0 >= b:          # 沒碰到
                nxt.append((a, b))
                continue
            if a < c0:
                nxt.append((a, c0))
            if c1 < b:
                nxt.append((c1, b))
        out = nxt
    return out


# ---------------------------------------------------------------- 還原
def origin(c):
    """這個碎片是從哪一支切出來的。沒切過就是它自己。"""
    return c.get("carved_from") or c["key"]


def restore(store):
    """把 LOGO 的碎片拆掉，時段畫面合併回原本的一整段。"""
    kept, groups = [], {}
    for c in store.get("contents", []):
        if c.get("logo_slot"):
            continue                        # LOGO 那幾支直接丟掉
        if c.get("carved_from") or c.get("carved"):
            groups.setdefault(origin(c), []).append(c)
        else:
            kept.append(c)

    for gid, parts in groups.items():
        head = next((p for p in parts if p["key"] == gid), parts[0])
        spans = [(sec(p["when"]["time"][0]), sec(p["when"]["time"][1]))
                 for p in parts if (p.get("when") or {}).get("time")]
        if spans:
            head["when"]["time"] = [hms(min(a for a, _ in spans)),
                                    hms(max(b for _, b in spans))]
        head.pop("carved_from", None)
        head.pop("carved", None)
        head["key"] = gid
        kept.append(head)

    store["contents"] = kept
    return store


# ---------------------------------------------------------------- 排入
def slots(store, minute):
    """整點過 `minute` 分，開屏時間內每個小時各一格。"""
    sc = store.get("schedule") or {}
    a, b = sec(sc.get("open") or "11:00"), sec(sc.get("close") or "22:30")
    out = []
    for h in range(24):
        s = h * 3600 + minute * 60
        if a <= s and s + SLOT_LEN <= b:
            out.append((s, s + SLOT_LEN))
    return out


def carve(store, minute):
    cuts = slots(store, minute)
    if not cuts:
        raise SystemExit("開屏時間 %s–%s 裡排不進任何整點格"
                         % ((store.get("schedule") or {}).get("open"),
                            (store.get("schedule") or {}).get("close")))

    out, made = [], 0
    for c in store.get("contents", []):
        t = (c.get("when") or {}).get("time")
        # 只切「時段畫面」。彩蛋、檔期、手動觸發是疊在上面的，不歸卡輪播管
        if c.get("layer") != "base" or not c.get("enabled") or not t:
            out.append(c)
            continue

        parts = subtract((sec(t[0]), sec(t[1])), cuts)
        if not parts:
            out.append(c)                   # 整段被挖光了？那就不動它
            continue

        art = c.get("art") or c["key"]
        gid = c["key"]
        for i, (a, b) in enumerate(parts):
            if i == 0:
                # 第一段沿用原本的 key。下游全部靠這個名字認人：
                # M5 的 segments 清單、看一天.py 的驗收清單、_一天的內容.py。
                p = c
                p["when"]["time"] = [hms(a), hms(b)]
            else:
                p = dict(c)
                p["key"] = "%s_%d" % (gid, i + 1)
                p["art"] = art
                p["when"] = {"time": [hms(a), hms(b)]}
                p["note"] = ("由 _排整點LOGO.py 從「%s」切出來的第 %d 段。"
                             "美術跟原段共用同一支影片。" % (gid, i + 1))
                made += 1
            # 每一段都要留記號（第一段也是），不然 restore() 會把
            # 「沒記號的第一段」和「合併回來的那一段」變成兩支同名節目。
            p["carved_from"] = gid
            out.append(p)

    for a, b in cuts:
        out.append({
            "key": "logo_%02d%02d" % (a // 3600, (a % 3600) // 60),
            "art": LOGO_ART,
            "name": "整點 LOGO 跑燈 %s" % hms(a)[:5],
            "enabled": True,
            "layer": "base",
            "logo_slot": True,
            "when": {"time": [hms(a), hms(b)]},
            "note": "業主 2026-09-10：每小時跑一次 logo。由 _排整點LOGO.py 產生，"
                    "不要手改 —— 改分鐘就重跑那支。",
        })

    # 依開始時間排序，讀 stores.json 的人才看得懂這一天的順序
    def order(c):
        t = (c.get("when") or {}).get("time")
        return (0, sec(t[0])) if (c.get("layer") == "base" and t) else (1, 0)

    base = sorted([c for c in out if order(c)[0] == 0], key=order)
    store["contents"] = base + [c for c in out if order(c)[0] != 0]
    return len(cuts), made


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stores", nargs="*", default=[])
    ap.add_argument("--分", dest="minute", type=int, default=45,
                    help="整點過幾分開始跑（預設 45，避開 M5 在 :00 和 :30 插播彩蛋）")
    ap.add_argument("--拿掉", dest="remove", action="store_true")
    a = ap.parse_args()

    data = json.load(io.open(STORES, encoding="utf-8"))
    ids = a.stores or [s["id"] for s in data["stores"] if s["id"] != "test"]

    bak = STORES + ".備份_排LOGO前_%s" % time.strftime("%Y%m%d_%H%M")
    shutil.copy2(STORES, bak)
    print("先備份：%s" % os.path.basename(bak))
    print()

    for sid in ids:
        store = next((s for s in data["stores"] if s["id"] == sid), None)
        if not store:
            print("!! 沒有這家店：%s" % sid)
            continue

        before = len([c for c in store.get("contents", []) if c.get("enabled")])
        restore(store)
        if a.remove:
            after = len([c for c in store.get("contents", []) if c.get("enabled")])
            print("%s（%s）　拿掉 LOGO：節目 %d → %d 支"
                  % (sid, store["name"], before, after))
            continue

        n, made = carve(store, a.minute)
        after = len([c for c in store.get("contents", []) if c.get("enabled")])
        sc = store.get("schedule") or {}
        print("%s（%s）" % (sid, store["name"]))
        print("  開屏 %s–%s，每小時 %02d 分跑一分鐘 → %d 格"
              % (sc.get("open"), sc.get("close"), a.minute, n))
        print("  時段畫面被切成 %d 段（多出來的 %d 段共用原本的影片）"
              % (n + made, made))
        print("  卡上的節目：%d → %d 支，影片只多一支（logo）" % (before, after))
        print()

    json.dump(data, io.open(STORES, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("寫回 stores.json。")
    print()
    print("接下來：")
    print("  python _建全部.py <店>          先只編影片，不碰卡")
    print("  python _一天的內容.py <店>      看排出來的一天對不對")
    print("  python _打包現場包.py           打包給現場的隨身碟")


if __name__ == "__main__":
    main()
