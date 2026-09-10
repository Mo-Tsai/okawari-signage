# -*- coding: utf-8 -*-
"""把 stores.json ＋ button_config.json 攤成「這面屏一天到底放什麼」。

資料來源就是要灌進卡的那一份，不是手寫的。
卡的行為：把當下「有資格播」的節目**輪流**播一遍（count=1 各播一次），
所以某個時刻的畫面 = 那一刻有資格的清單，照順序繞圈。

用法：
    python _一天的內容.py taichung
    python _一天的內容.py tainan > 一天的內容_台南.md

★ 2026-09-01 改寫。原本寫死 test 店、寫死四個時段、寫死 9/1–9/2 的檔期，
  而且還在描述架構 A（按鈕節目永遠不出現）。現在全部從 stores.json 推導：
  時段清單、檔期日期、開屏時間、按鈕節目的排播窗都是算出來的。
"""
import io, json, os, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
HERE = os.path.dirname(os.path.abspath(__file__))
sid = sys.argv[1] if len(sys.argv) > 1 else "test"

data = json.load(io.open(os.path.join(HERE, "stores.json"), encoding="utf-8"))
st = next(x for x in data["stores"] if x["id"] == sid)
cfg = json.load(io.open(os.path.join(HERE, "..", "按鈕機", "button_config.json"),
                encoding="utf-8"))
if cfg.get("store") != sid:
    sys.stderr.write("⚠ button_config.json 目前是「%s」的，秒數可能不準。\n"
                     "  先跑：python 做設定檔.py %s --router ...\n"
                     % (cfg.get("store"), sid))
SEC = {k: v["seconds"] for k, v in cfg["programs"].items()}

# ★ 2026-09-10：秒數不能只靠 button_config.json。
#   整點 LOGO 把時段切成 noon / noon_2 / noon_3…，設定檔裡沒有這些新 key，
#   查不到就落到預設的 10 秒 —— 表格會印出「今天也要好好吃飯 10s」，
#   而那一段其實是 20 秒。**一份會說謊的對帳表比沒有對帳表更糟。**
#   查不到就回頭問美術參數，那才是編影片時真正用的值。
import artwork                                                  # noqa: E402
PRM = artwork.params({**(data.get("params") or {}),
                      **(st.get("params") or {})})
C = {c["key"]: c for c in st["contents"] if c.get("enabled")}
sc = st["schedule"]


def mins(t):
    p = t.split(":")
    return int(p[0]) * 60 + int(p[1])


def hhmm(t):
    return t[:5]


def win(k):
    return (C[k].get("when") or {}).get("time") or []


def overlap(a, b):
    return mins(a[0]) < mins(b[1]) and mins(b[0]) < mins(a[1])


def sec(k):
    if k in SEC:
        return SEC[k]
    a = (C[k].get("art") or k) if k in C else k
    return PRM.get("%s_seconds" % artwork.param_key(a), 10)


BASE = sorted([k for k in C if C[k].get("layer") == "base" and win(k)],
              key=lambda k: mins(win(k)[0]))
EGGS = sorted(k for k in C if k.startswith("egg_"))
PROMOS = sorted(k for k in C if k.startswith("promo_"))
MANUAL = [k for k in C if C[k].get("trigger") == "manual"]
manual_ok = bool(sc.get("manual_trigger"))

print("# OKAWARI 門頭屏｜一天的內容 —— %s" % st["name"])
print()
print("> 由 `後台/_一天的內容.py %s` 從 `stores.json` 生成。" % sid)
print("> 卡的行為：把當下有資格播的節目**輪流各播一次**，播完繞回第一支。")
print()
print("**開屏時間：%s – %s**（其餘時間卡自己把屏關掉）" % (sc["open"], sc["close"]))
print()
print("> 這裡的 %s–%s 是「屏亮著的時間」，不是賣飯時間。"
      % (sc["open"], sc["close"]))
print()

# 情境 = 依檔期日期切
scenes = [("A・平常日（所有檔期都結束後）", [])]
allp = [k for k in PROMOS if (C[k].get("when") or {}).get("date")]
if allp:
    short = [k for k in allp if C[k]["when"]["date"][1] < max(
        C[x]["when"]["date"][1] for x in allp)]
    if short:
        # ★ 標題用「短檔期自己的日期」，不是所有檔期裡最早的那天 ——
        #   台南的買一送一是 9/2–9/3，但 promo_open 從 9/1 就開始，
        #   取 min 會寫成 9/1–9/3，是錯的。
        bs = min(C[k]["when"]["date"][0] for k in short)
        be = min(C[k]["when"]["date"][1] for k in short)
        scenes.append(("B・%s–%s（%s 期間）" % (bs, be,
                       "＋".join(C[k]["name"] for k in short)), allp))
        rest = [k for k in allp if k not in short]
        if rest:
            scenes.append(("C・%s 之後的檔期（到 %s）" % (
                be, max(C[k]["when"]["date"][1] for k in rest)), rest))
    else:
        scenes.append(("B・檔期期間", allp))

for title, active in scenes:
    print("\n---\n")
    print("## %s" % title)
    print()
    print("| 時段 | 輪播內容（依序） | 一圈長度 |")
    print("|---|---|---|")
    for s in BASE:
        w = win(s)
        ks = [s] + [p for p in active if win(p) and overlap(w, win(p))]
        names = " → ".join("%s %ss" % (C[k]["name"], sec(k)) for k in ks)
        print("| %s–%s | %s | **%d 秒** |"
              % (hhmm(w[0]), hhmm(w[1]), names, sum(sec(k) for k in ks)))
    print()
    print("**整點彩蛋**（插在上面的輪播裡，每個窗只有一分鐘）：")
    print()
    print("| 時刻 | 內容 | 長度 |")
    print("|---|---|---|")
    for e in EGGS:
        w = win(e)
        print("| %s–%s | %s | %s 秒 |"
              % (w[0], w[1], C[e]["name"].split("・")[-1], sec(e)))
    print()
    print("**彩蛋放得到的機率**（窗 12 秒 ÷ 輪播一圈）：")
    print()
    print("| 時段 | 一圈 | 放得到的機率 |")
    print("|---|---|---|")
    for s in BASE:
        w = win(s)
        ks = [s] + [p for p in active if win(p) and overlap(w, win(p))]
        T = sum(sec(k) for k in ks)
        if not any(overlap(w, win(e)) for e in EGGS):
            print("| %s | %d 秒 | —（這個時段沒有彩蛋） |" % (C[s]["name"], T))
            continue
        pct = 100.0 * min(12, T) / T
        mark = "" if pct > 99 else ("　⚠️" if pct < 50 else "")
        print("| %s | %d 秒 | **%.0f%%**%s |" % (C[s]["name"], T, pct, mark))
    print()

print("\n---\n")
print("## 手動觸發（櫃檯按鈕）")
print()
print("| 節目 | 長度 | 排播窗 |")
print("|---|---|---|")
for k in MANUAL:
    w = ("`%s–%s`" % (sc["open"], sc["close"])) if manual_ok \
        else "`00:00:00–00:00:01`（等於永遠沒資格）"
    print("| %s | %s 秒 | %s |" % (C[k]["name"], sec(k), w))
print()
if manual_ok:
    print("架構 B：這四支的排播窗＝開屏時間，所以 **%s–%s 按鈕都按得動**。"
          % (sc["open"], sc["close"]))
    print("代價是卡輪不到整點彩蛋和檔期，那兩者改由櫃檯 M5 主動送。")
else:
    print("架構 A：窗設在凌晨零點那一秒，而那時候屏是關的，")
    print("所以這四支**永遠不會出現在屏上**，它們躺在卡上等一個觸發路徑。")
