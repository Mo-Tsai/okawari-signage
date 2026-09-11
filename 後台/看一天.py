# -*- coding: utf-8 -*-
"""在真屏上把一整天演一次給人看。

用法：
    python 看一天.py                     → 測試卡
    python 看一天.py tainan <卡IP>
    python 看一天.py test 192.168.1.100 --hold 5   → 每支固定停 5 秒

★ 為什麼不能直接一支一支切
  卡只播「當下有資格播」的節目。晚上七點跑，opening／noon／siesta、
  11 支彩蛋、3 支開幕檔期**全部切不動** —— 切過去卡照樣回 kSuccess，
  但螢幕不動。所以要在真屏上看完整的一天，只能**先把卡的時間調到那一段**。

★ 開幕檔期要連日期一起改
  那三支的 playControl 有 date（9/1–9/30），只改時間沒有用。

★ 收尾一定要對時
  時間調過去之後如果沒對回來，整點彩蛋就會在錯的時刻放
  （2026-08-22 實測過測試卡快 9 分鐘，彩蛋就在 xx:51 出現）。
  所以還原包在 finally 裡，Ctrl-C 或中途出錯都會對回來。

★ 跑之前建議把 M5 的 USB 拔掉
  母機會一直佔著跟卡的 TCP 連線，兩邊搶容易出現 ConnectionReset。
"""
import argparse
import datetime
import io
import json
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(
    HERE, "..", "卡的SDK與工具", "02_程式端")))
sys.path.insert(0, HERE)

import hd_test as hd                                        # noqa: E402

# ★ 時區字串要跟 _對時.py 一字不差。2026-08-25 我自己編了個 "UTC+8"，
#   卡回 kInvalidParam —— 而我沒檢查回應，所以 14 次全部失敗、時間從頭到尾
#   沒被改過，畫面當然切不動，看起來像「節目壞了」。
#   **送出去的東西一定要看回應。**
TZ = "(UTC+08:00)Beijing,Chongqing,HongKong,Urumchi"

# (節目 key, 給人看的名字, 要把卡的時間假裝成什麼)
# 時間點都挑在該段時窗的中間，不要卡在邊界上。
DAY = [
    # ★ 2026-09-01 補：開店前／打烊後各半小時的睡覺畫面。
    #   原本這兩段不在清單裡，等於新加的內容完全驗不到。
    ("preopen",    "開店前・還在睡",            "2026-08-25 10:45:00"),
    ("opening",    "開店畫面",                  "2026-08-25 11:15:00"),
    ("noon",       "今天也要好好吃飯",          "2026-08-25 12:45:00"),
    ("siesta",     "午後發呆 Zzz",              "2026-08-25 15:45:00"),
    ("evening",    "今天辛苦了，吃飯吧",        "2026-08-25 19:45:00"),
    ("postclose",  "打烊後・睡了",              "2026-08-25 22:45:00"),
    # ★ 2026-09-10 加：整點 LOGO 跑燈。key 用哪一格都可以 —— 下面的
    #   resolve() 會照假時間自己挑當下有資格的那一支。
    ("logo_1250",  "整點 LOGO 跑燈",            "2026-08-25 12:50:20"),
    ("egg_12",     "整點彩蛋・手電筒巡邏",      "2026-08-25 12:00:20"),
    ("egg_13",     "整點彩蛋・接力賽",          "2026-08-25 13:00:20"),
    ("egg_14",     "整點彩蛋・RICE POWER",      "2026-08-25 14:00:20"),
    ("promo_open", "開幕：全員集合",            "2026-09-01 11:15:00"),
    ("promo_bogo", "買一送一（半顆愛心）",      "2026-09-01 19:00:00"),
    ("promo_egg",  "10 元溫泉蛋加價購",         "2026-09-01 19:00:00"),
    # ★ 2026-09-01 修：這四支**不是**全天窗。schedule.py 會給 trigger=manual
    #   的節目 open–close 的 playControl（現在是 10:30–23:00），所以在非營業
    #   時間切不動是正確行為。原本寫 None（不改時間）會讓它們沿用上一支留下的
    #   時間，剛好落在營業中才「碰巧會過」—— 單獨跑就會誤判成壞掉。
    ("combo1",     "續碗 COMBO 1（右鍵 +1）",   "2026-08-25 19:30:00"),
    ("combo2",     "續碗 COMBO 2",              "2026-08-25 19:30:00"),
    ("combo3",     "續碗 COMBO 3・火花全開",    "2026-08-25 19:30:00"),
    ("okawari",    "滿千送百 GOLDEN BOWL",      "2026-08-25 19:30:00"),
]


def set_time(card, when):
    body = ('    <timezone value="%s"/>\n'
            '    <summer enable="false"/>\n'
            '    <sync value="none"/>\n'
            '    <time value="%s"/>\n'
            '    <server list="pool.ntp.org,time.windows.com"/>\n'
            '    <rf>\n'
            '      <enable value="false"/>\n'
            '      <master value="false"/>\n'
            '      <channel value="-1"/>\n'
            '    </rf>' % (TZ, when))
    return hd.attr(card.call('  <in method="SetTimeInfo">\n%s\n  </in>' % body),
                   "out", "result")


def reconnect(card):
    try:
        card.close()
    except Exception:
        pass
    try:
        card.connect()
        return True
    except Exception:
        return False


def with_retry(card, fn, what, tries=5):
    """★ 2026-09-01：卡會自己把 socket 切掉（實測第 4 次 SetTimeInfo 就斷）。

    原本這支沒有重連，一斷就整支死在半路 —— 連 finally 的對時都送不出去，
    卡的時間就被留在假造的 2026-08-25 上，整點彩蛋和開幕檔期全部會錯。
    這不是偶發，是這張卡在連續下指令時的固定行為。
    """
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            print("   （%s 斷線：%s，重連第 %d 次）"
                  % (what, type(e).__name__, i + 1))
            time.sleep(2.0)
            reconnect(card)
    raise last


def _mid(w):
    """一個時間窗的中點，回 "HH:MM:SS"。挑中點是因為邊界最危險 ——
    卡的時鐘跟筆電差個一兩秒，落在邊界上就會忽成忽敗。"""
    def sec(t):
        q = [int(x) for x in str(t).split(":")]
        while len(q) < 3:
            q.append(0)
        return q[0] * 3600 + q[1] * 60 + q[2]
    m = (sec(w[0]) + sec(w[1])) // 2
    return "%02d:%02d:%02d" % (m // 3600, (m % 3600) // 60, m % 60)


def plan(key, fake, store, pub):
    """回傳 (要切哪一支, 要把卡的時間假裝成什麼)。兩個都從 stores.json 推。

    ★ 2026-09-11 加。原本只有 key 會自己挑，假時間還是寫死的 ——
      於是今天台南把 postclose 從 22:30 移到 21:40 之後，清單還在假裝 22:45，
      那支就切不動；買一送一的日期寫的是台中的 9/1，台南是 9/2–9/3，也切不動。
      **兩次都不是內容壞掉，是清單過期。** 而它報出來的樣子跟真的壞掉一模一樣。

      所以假時間也改成算的：日期落在檔期窗裡，時間落在它自己的窗中點。
    """
    c0 = next((c for c in store.get("contents", []) if c["key"] == key), None)
    if not c0:
        return key, fake
    day, _, clock = fake.partition(" ")

    w = (c0.get("when") or {})
    d = w.get("date") or []
    if len(d) == 2 and not (d[0] <= day <= d[1]):
        day = d[0]                      # 檔期：假日期一定要落在檔期裡

    t = w.get("time") or []
    if len(t) == 2:
        a, b = hhmmss_or(t[0]), hhmmss_or(t[1])
        if a and b and not (a <= clock < b):
            clock = _mid([a, b])        # 時間窗：落在窗中點，不要卡邊界

    fake2 = "%s %s" % (day, clock)
    return resolve(key, fake2, store, pub), fake2


def hhmmss_or(t):
    try:
        q = [int(x) for x in str(t).split(":")]
    except Exception:
        return None
    while len(q) < 3:
        q.append(0)
    return "%02d:%02d:%02d" % (q[0], q[1], q[2])


def resolve(key, fake, store, pub):
    """假時間到了之後，真正該切的是哪一支。

    ★ 2026-09-10 加。原本這裡是「key 寫死、時間寫死」，兩邊要自己對上。
      整點 LOGO 把時段的窗切成 noon / noon_2 / noon_3…之後，
      12:45 有資格的已經不是 `noon` 了 —— 硬切 `noon` 會被卡拒絕，
      而畫面明明是對的。那會看起來像新內容壞掉，其實只是清單過期。

      所以改成問 schedule：這個假時間，哪一支時段畫面有資格？
      有資格的那一支才切得動，這是這張卡的鐵則。
      彩蛋、檔期、手動那幾支不走這條（它們不是 base），維持原本的 key。
    """
    import datetime
    import schedule as sched
    c0 = next((c for c in store.get("contents", []) if c["key"] == key), None)
    if not c0 or c0.get("layer") != "base":
        return key
    try:
        now = datetime.datetime.strptime(fake, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return key
    hit = [c["key"] for c in store.get("contents", [])
           if sched.is_base(c) and not (c.get("when") or {}).get("date")
           and c["key"] in pub and sched.is_active(c.get("when"), now)]
    return hit[0] if hit else key


def guid_of(e):
    return (e.get("program") or e.get("guid") or "") if isinstance(e, dict) else (e or "")


def current(card):
    try:
        return hd.attr(hd.q_current_program(card), "program", "guid").lower()
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("store", nargs="?", default="test")
    ap.add_argument("ip", nargs="?", default=None)
    ap.add_argument("--hold", type=float, default=0,
                    help="每支固定停幾秒（不給就照影片長度）")
    a = ap.parse_args()

    data = json.load(io.open(os.path.join(HERE, "stores.json"), encoding="utf-8"))
    store = next(s for s in data["stores"] if s["id"] == a.store)
    ip = a.ip or (store.get("card") or {}).get("last_known_ip")
    pub = store.get("published") or {}

    card = hd.HDCard(ip, 10001, timeout=15.0)
    card.connect()
    print("=" * 60)
    print("在真屏上演一次一天 —— %s（%s）" % (store["name"], ip))
    print("看完會自動把卡的時間對回來")
    print("=" * 60)

    try:
        with_retry(card, lambda: card.call('  <in method="OpenScreen"/>'), "開屏")
        for key, name, fake in DAY:
            key, fake = plan(key, fake, store, pub)
            if key not in pub:
                print("  跳過 %s（沒發佈）" % key)
                continue
            g = guid_of(pub[key])
            secs = pub[key].get("seconds", 10) if isinstance(pub[key], dict) else 10
            hold = a.hold or max(4, float(secs))
            if fake:
                r = with_retry(card, lambda: set_time(card, fake), "設定時間")
                if r != "kSuccess":
                    raise SystemExit(
                        "把卡的時間設成 %s 失敗（%s）—— 停下來，"
                        "不要繼續演一場假的" % (fake, r))
                time.sleep(2.0)            # 讓卡重新算「現在有資格播什麼」
            with_retry(card, lambda: hd.do_switch_program(card, guid=g), "切節目")
            time.sleep(1.5)
            ok = current(card) == g.lower()
            print("  %-12s %-26s %s  停 %.0f 秒"
                  % (key, name, "▶ 播出來了" if ok else "✗ 沒切過去", hold))
            time.sleep(hold)
    except KeyboardInterrupt:
        print("\n（中斷）")
    finally:
        # ★ 一定要把時間對回來，不然整點彩蛋會在錯的時刻放。
        #   2026-09-01：改成重連重試 —— 原本只試一次，斷線就放棄。
        done = False
        for i in range(8):
            try:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                r = set_time(card, now)
                if r == "kSuccess":
                    print("")
                    print("收尾：對時回 %s → %s" % (now, r))
                    done = True
                    break
                print("   （對時回應 %s，重試）" % r)
            except Exception as e:
                print("   （對時第 %d 次失敗：%s）" % (i + 1, type(e).__name__))
            time.sleep(2.0)
            reconnect(card)
        if done:
            try:
                card.call('  <in method="OpenScreen"/>')
            except Exception:
                pass
        else:
            print("")
            print("！！對時 8 次都失敗，卡的時間還是錯的。手動跑：")
            print("   python _對時.py %s" % ip)
        try:
            card.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
