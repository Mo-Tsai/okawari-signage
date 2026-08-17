#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 時段

業主 2026-08-09 的需求是「按時段換畫面」：開店、中午、午後、晚間，
再加上開幕期間的限定活動。

做法上有兩條路，這裡走的是第二條：

  A. 後台每隔幾秒看時鐘，時間到了就送 SwitchProgram
     → 筆電不在就停在原地不動。門市沒有常駐主機，所以這條不能用。

  B. 把時段寫進節目自己的 playControl，卡按自己的時鐘播
     → 筆電關掉、拔掉、帶回台北都沒差，卡自己會換。★ 用這條

SDK 的 playControl 支援三種條件（ProgramDefine/节目单标签属性.md）：

    <time start="hh:mm:ss" end="hh:mm:ss"/>    每天的哪個時段
    <date start="YYYY-MM-DD" end="YYYY-MM-DD"/> 哪幾天（開幕活動用這個，過期自動消失）
    <week enable="Mon,Tue,..."/>                星期幾

所以「9/1-2 買一送一」設好日期就會自己上、自己下，不必記得回去關掉。
"""

import datetime
import re

# 星期的寫法是 SDK 訂的，不能自己改（Thur 不是 Thu）
WEEKDAYS = ["Mon", "Tue", "Wed", "Thur", "Fri", "Sat", "Sun"]


def parse_hhmm(s):
    """'11:30' 或 '11:30:00' → 當天的第幾秒。看不懂就回 None。"""
    if not s:
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", str(s).strip())
    if not m:
        return None
    h, mi, se = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if not (0 <= h <= 23 and 0 <= mi <= 59 and 0 <= se <= 59):
        return None
    return h * 3600 + mi * 60 + se


def hhmmss(s):
    """正規化成 SDK 要的 hh:mm:ss。"""
    t = parse_hhmm(s)
    if t is None:
        return None
    return "%02d:%02d:%02d" % (t // 3600, (t % 3600) // 60, t % 60)


def in_time_window(start, end, now_sec):
    """now_sec 在不在 [start, end) 裡面。

    跨午夜要另外處理：22:30〜02:00 這種區間，start > end，
    代表它中間隔了一個午夜，要拆成兩段看。門頭屏目前用不到，
    但寫進來免得以後有人設了夜間時段卻整段不播。
    """
    a, b = parse_hhmm(start), parse_hhmm(end)
    if a is None or b is None:
        return True                     # 沒設條件 = 隨時可播
    if a <= b:
        return a <= now_sec < b
    return now_sec >= a or now_sec < b   # 跨午夜


def in_date_window(start, end, today):
    """today（datetime.date）在不在 [start, end] 裡面。兩端都含。"""
    def d(s):
        if not s:
            return None
        try:
            return datetime.date(*[int(x) for x in str(s).split("-")])
        except Exception:
            return None
    a, b = d(start), d(end)
    if a and today < a:
        return False
    if b and today > b:
        return False
    return True


def in_week(enable, today):
    """enable 是 'Mon,Tue' 這種字串。空的 = 每天都播。"""
    if not enable:
        return True
    want = {w.strip() for w in str(enable).split(",") if w.strip()}
    return not want or WEEKDAYS[today.weekday()] in want


def is_active(when, now=None):
    """這個 when 條件現在成不成立。

    when 長這樣（每一項都可以省略）：
        {"time": ["11:30", "14:00"],
         "date": ["2026-09-01", "2026-09-02"],
         "week": "Mon,Tue,Wed,Thur,Fri"}
    """
    now = now or datetime.datetime.now()
    when = when or {}
    t = when.get("time") or []
    d = when.get("date") or []
    now_sec = now.hour * 3600 + now.minute * 60 + now.second
    if t and not in_time_window(t[0], t[1] if len(t) > 1 else None, now_sec):
        return False
    if d and not in_date_window(d[0], d[1] if len(d) > 1 else None, now.date()):
        return False
    return in_week(when.get("week"), now.date())


def play_control_xml(item):
    """把一個內容項目的排播條件變成 playControl 的 XML。

    手動觸發的內容（續碗那種）要給一個永遠不會成立的時間窗，
    否則卡會把它排進日常輪播，客人沒續碗畫面也會自己跳出來。
    真正要播的時候由後台送 SwitchProgram 強制切過去。

    ★ 「SwitchProgram 能不能切到一個時間窗不成立的節目」還沒在實體卡上驗證過。
      驗不過的話退路是：手動內容不設時間窗，改成 disabled="true"，
      或者乾脆讓它留在輪播裡但長度設很短。上機第一件事就測這個。
    """
    if item.get("trigger") == "manual":
        return ('<playControl count="1"><time start="00:00:00" end="00:00:01"/>'
                '</playControl>')

    when = item.get("when") or {}
    bits = []

    t = when.get("time") or []
    if len(t) >= 2 and hhmmss(t[0]) and hhmmss(t[1]):
        bits.append('<time start="%s" end="%s"/>' % (hhmmss(t[0]), hhmmss(t[1])))

    d = when.get("date") or []
    if len(d) >= 2 and d[0] and d[1]:
        bits.append('<date start="%s" end="%s"/>' % (d[0], d[1]))

    w = when.get("week")
    if w:
        bits.append('<week enable="%s"/>' % w)

    if not bits:
        return '<playControl count="1"/>'
    return '<playControl count="1">%s</playControl>' % "".join(bits)


def active_now(contents, now=None):
    """現在這個時間，哪些常駐內容該播。手動觸發的不算。

    回傳 key 的清單。正常情況應該剛好一個；
    是空的代表這個時間沒有東西可播（時段沒排滿），
    多於一個代表時段重疊了 —— 兩種都要在後台警告出來。
    """
    out = []
    for c in contents or []:
        if not c.get("enabled") or c.get("trigger") == "manual":
            continue
        if is_active(c.get("when"), now):
            out.append(c["key"])
    return out


def coverage_gaps(contents, open_at, close_at):
    """檢查營業時間有沒有哪一段沒人顧。

    回傳 [(起, 迄), ...]，空的就是排滿了。
    這是給後台顯示用的 —— 排漏了會是「某個時間屏上什麼都沒有」，
    那種問題很難用眼睛看出來，要算給人看。
    """
    a, b = parse_hhmm(open_at), parse_hhmm(close_at)
    if a is None or b is None or a >= b:
        return []

    # 只看沒有日期限制的常駐內容。開幕活動是疊在上面的，不算基本盤。
    spans = []
    for c in contents or []:
        if not c.get("enabled") or c.get("trigger") == "manual":
            continue
        when = c.get("when") or {}
        if when.get("date"):
            continue
        t = when.get("time") or []
        if len(t) < 2:
            return []               # 有一個內容是全天候的，那就不可能有空隙
        s, e = parse_hhmm(t[0]), parse_hhmm(t[1])
        if s is not None and e is not None and s < e:
            spans.append((max(s, a), min(e, b)))

    spans.sort()
    gaps, cur = [], a
    for s, e in spans:
        if s > cur:
            gaps.append((cur, s))
        cur = max(cur, e)
    if cur < b:
        gaps.append((cur, b))
    return [(fmt(g[0]), fmt(g[1])) for g in gaps if g[1] > g[0]]


def overlaps(contents):
    """有沒有兩個常駐內容的時段疊在一起。疊到的話卡會兩個輪流播。"""
    items = []
    for c in contents or []:
        if not c.get("enabled") or c.get("trigger") == "manual":
            continue
        when = c.get("when") or {}
        if when.get("date"):
            continue                # 活動本來就是疊在常駐上面的，不算衝突
        t = when.get("time") or []
        if len(t) >= 2:
            s, e = parse_hhmm(t[0]), parse_hhmm(t[1])
            if s is not None and e is not None and s < e:
                items.append((s, e, c["key"]))
    items.sort()
    out = []
    for i in range(len(items) - 1):
        if items[i][1] > items[i + 1][0]:
            out.append((items[i][2], items[i + 1][2],
                        fmt(items[i + 1][0]), fmt(items[i][1])))
    return out


def fmt(sec):
    return "%02d:%02d" % (sec // 3600, (sec % 3600) // 60)


def switch_time_xml(open_at, close_at, enable=True):
    """卡自己的定時開關屏。

    這個一定要設在卡上，不能靠後台 —— 打烊之後筆電早就不在了。
    在 start〜end 之間是開屏狀態，其餘時間卡自己把屏關掉。
    """
    o, c = hhmmss(open_at), hhmmss(close_at)
    if not (o and c) or not enable:
        return ('  <in method="SetSwitchTime">\n'
                '    <open enable="true"/>\n'
                '    <ploy enable="false"/>\n  </in>')
    return ('  <in method="SetSwitchTime">\n'
            '    <open enable="true"/>\n'
            '    <ploy enable="true">\n'
            '      <item enable="true" start="%s" end="%s"/>\n'
            '    </ploy>\n  </in>' % (o, c))
