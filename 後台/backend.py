#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 後台 v0（門店與內容登錄）

這一版只管「有哪些店、每店的畫布多大、每店要播哪些內容」。
發佈（編譯 → 送檔 → 建節目）之後接進來。

設計重點是兩層都能加減：
  店   可增可減（測試版不要了就停用或刪掉）
  內容 每店可增可減（之後要加「開店」「打烊」不用改程式）

資料就是旁邊的 stores.json，人可讀、可以直接手改，這支程式只是它的介面。
只用 Python 標準函式庫。
"""

import json
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "stores.json")


# ---------------------------------------------------------------- 存取
def load():
    with open(DB, "r", encoding="utf-8") as f:
        return json.load(f)


def save(data):
    """先備份再原子寫入，避免手滑把登錄檔弄壞。"""
    if os.path.exists(DB):
        shutil.copyfile(DB, DB + ".bak")
    tmp = DB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, DB)


def ask(prompt, default=""):
    try:
        s = input("%s%s：" % (prompt, ("（預設 %s）" % default) if default else "")).strip()
    except EOFError:
        raise KeyboardInterrupt
    return s or default


def find(data, sid):
    for s in data["stores"]:
        if s["id"] == sid:
            return s
    return None


# ---------------------------------------------------------------- 顯示
def canvas_str(s):
    c = s.get("canvas") or {}
    if c.get("width") and c.get("height"):
        return "%s × %s" % (c["width"], c["height"])
    return "未定"


def list_stores(data):
    print("")
    print("  %-10s %-22s %-12s %-6s %s" % ("代號", "店名", "畫布", "啟用", "內容"))
    print("  " + "─" * 68)
    for s in data["stores"]:
        on = [c["key"] for c in s.get("contents", []) if c.get("enabled")]
        print("  %-10s %-22s %-12s %-6s %s"
              % (s["id"], s["name"], canvas_str(s),
                 "是" if s.get("enabled") else "否",
                 ", ".join(on) or "（無）"))
    print("")


def show_store(data):
    sid = ask("要看哪一家（代號）")
    s = find(data, sid)
    if not s:
        print("  沒有這個代號。")
        return
    print("")
    print(json.dumps(s, ensure_ascii=False, indent=2))
    print("")


# ---------------------------------------------------------------- 店：增／減
def add_store(data):
    print("")
    sid = ask("新店代號（英文，例如 kaohsiung）")
    if not sid:
        return
    if find(data, sid):
        print("  這個代號已經有了。")
        return
    name = ask("店名", sid)
    w = ask("畫布寬 px（還不知道就直接 Enter）")
    h = ask("畫布高 px（還不知道就直接 Enter）")

    store = {
        "id": sid,
        "name": name,
        "enabled": False,
        "note": "由後台新增。",
        "canvas": {
            "width": int(w) if w.isdigit() else None,
            "height": int(h) if h.isdigit() else None,
            "pitch": None,
            "source": None,
        },
        "card": {"sdk_port": 10001, "ip_mode": "dhcp"},
        "hq": {"host": "", "port": 0},
        "network": {"uplink": "4g-router"},
        "contents": [
            {"key": k, "enabled": True, "variants": ["a"],
             "loop": (k == "idle"), "seconds": None}
            for k in ("idle", "patrol", "okawari")
        ],
    }
    data["stores"].append(store)
    save(data)
    print("  ✓ 加好了：%s（%s）。畫布沒填的話之後用選項 4 補。" % (name, sid))


def remove_store(data):
    sid = ask("要刪哪一家（代號）")
    s = find(data, sid)
    if not s:
        print("  沒有這個代號。")
        return
    print("  要刪的是：%s（%s），畫布 %s" % (s["name"], s["id"], canvas_str(s)))
    if ask("確定刪掉嗎？打 yes 才會執行").lower() != "yes":
        print("  取消。")
        return
    data["stores"].remove(s)
    save(data)
    print("  ✓ 刪掉了。（舊檔備份在 stores.json.bak）")


def toggle_store(data):
    sid = ask("要啟用／停用哪一家（代號）")
    s = find(data, sid)
    if not s:
        print("  沒有這個代號。")
        return
    s["enabled"] = not s.get("enabled")
    save(data)
    print("  ✓ %s 現在是「%s」" % (s["name"], "啟用" if s["enabled"] else "停用"))


def set_canvas(data):
    sid = ask("要設哪一家的畫布（代號）")
    s = find(data, sid)
    if not s:
        print("  沒有這個代號。")
        return
    print("  目前：%s" % canvas_str(s))
    w = ask("畫布寬 px")
    h = ask("畫布高 px")
    if not (w.isdigit() and h.isdigit()):
        print("  要輸入數字。")
        return
    pitch = ask("點距（P4 / P6，不知道就 Enter）")
    s["canvas"]["width"] = int(w)
    s["canvas"]["height"] = int(h)
    if pitch:
        s["canvas"]["pitch"] = pitch
    s["canvas"]["source"] = "後台手動輸入"
    save(data)
    print("  ✓ %s 的畫布設成 %s × %s" % (s["name"], w, h))


# ---------------------------------------------------------------- 內容：增／減
def add_content(data):
    sid = ask("要加內容到哪一家（代號）")
    s = find(data, sid)
    if not s:
        print("  沒有這個代號。")
        return
    print("")
    print("  已知的事件類型：")
    for k, v in data["event_types"].items():
        print("    %-10s %s" % (k, v))
    print("  （也可以打一個新的，例如 opening、closing）")
    key = ask("事件代號")
    if not key:
        return
    if any(c["key"] == key for c in s["contents"]):
        print("  這家店已經有這個事件了。")
        return
    n = ask("要做幾個變體（隨機挑一段播）", "1")
    try:
        n = max(1, int(n))
    except ValueError:
        n = 1
    s["contents"].append({
        "key": key,
        "enabled": True,
        "variants": [chr(ord("a") + i) for i in range(n)],
        "loop": (key == "idle"),
        "seconds": None,
    })
    if key not in data["event_types"]:
        data["event_types"][key] = ask("這個事件的說明（給以後的人看）", key)
    save(data)
    print("  ✓ %s 加了 %s（%d 個變體）" % (s["name"], key, n))


def remove_content(data):
    sid = ask("要從哪一家移除內容（代號）")
    s = find(data, sid)
    if not s:
        print("  沒有這個代號。")
        return
    print("  目前有：%s" % ", ".join(c["key"] for c in s["contents"]))
    key = ask("要移除哪個事件")
    hit = [c for c in s["contents"] if c["key"] == key]
    if not hit:
        print("  這家店沒有這個事件。")
        return
    s["contents"].remove(hit[0])
    save(data)
    print("  ✓ 移除了 %s" % key)


def toggle_content(data):
    sid = ask("哪一家（代號）")
    s = find(data, sid)
    if not s:
        print("  沒有這個代號。")
        return
    for c in s["contents"]:
        print("    %-10s %s" % (c["key"], "啟用" if c.get("enabled") else "停用"))
    key = ask("要切換哪個事件")
    hit = [c for c in s["contents"] if c["key"] == key]
    if not hit:
        print("  沒有這個事件。")
        return
    hit[0]["enabled"] = not hit[0].get("enabled")
    save(data)
    print("  ✓ %s 現在是「%s」" % (key, "啟用" if hit[0]["enabled"] else "停用"))


# ---------------------------------------------------------------- 主選單
MENU = """
╔══════════════════════════════════════════════════════╗
║   OKAWARI 門頭屏 · 後台 v0                           ║
╚══════════════════════════════════════════════════════╝

  1  看所有門店
  2  看某一家的完整資料
  3  ＋ 新增門店
  4  設定某一家的畫布尺寸
  5  － 刪除門店
  6  啟用 / 停用門店
  7  ＋ 幫某一家加內容（事件）
  8  － 從某一家移除內容
  9  啟用 / 停用某個內容
  0  結束
"""


def main():
    if not os.path.exists(DB):
        print("找不到 stores.json，它應該跟這支程式放在一起。")
        return
    actions = {
        "1": list_stores, "2": show_store, "3": add_store, "4": set_canvas,
        "5": remove_store, "6": toggle_store, "7": add_content,
        "8": remove_content, "9": toggle_content,
    }
    while True:
        data = load()
        print(MENU)
        c = ask("選一個", "1")
        if c == "0":
            break
        fn = actions.get(c)
        if not fn:
            print("  沒這個選項。")
            continue
        try:
            fn(data)
        except Exception as e:
            print("  出錯了：%r" % e)
        try:
            input("\n按 Enter 回選單...")
        except EOFError:
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中斷。")
