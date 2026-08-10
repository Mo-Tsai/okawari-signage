#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 後台伺服器

跑在筆電上，手機或電腦用瀏覽器連進來操作。
筆電同時看得到卡（乙太網路）和手機（Wi-Fi），所以它就是中間人 ——
這也正是未來台南總部伺服器的角色，現在先由筆電扮演。

    手機 ──Wi-Fi──▶ 筆電（這支程式）──網路線──▶ 控制卡 ──▶ LED 屏

三個功能各自帶自己的設定；門店可以增減。
卡本身是輪播所有節目、不會自己回待機，所以事件播完由這裡切回 idle。
"""

import base64
import json
import os
import random
import re
import shutil
import socket
import struct
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "stores.json")
# 介面檔。資料夾叫 docs 是因為 GitHub Pages 只能從根目錄或 /docs 發佈，
# 用 docs 就不必再設一套 Actions。同一份檔案這台後台也端得出去。
WEB = os.path.abspath(os.path.join(HERE, "..", "docs"))
PORT = 8080

# 卡主動撥回來的埠。0 = 不開。開了之後把卡的 SetSDKTcpServer 指到
# 這台機器的公網位址:這個埠，卡就會自己連過來 —— 這是 4G 環境下唯一走得通的路。
HQ_PORT = int(os.environ.get("OKAWARI_HQ_PORT", "0") or 0)

import sys
sys.path.insert(0, os.path.abspath(os.path.join(
    HERE, "..", "_明天帶去_LED實測_20260810", "02_程式端")))
sys.path.insert(0, HERE)
import hd_test as hd          # noqa: E402
import compiler as comp       # noqa: E402


# ---------------------------------------------------------------- 資料
_dblock = threading.Lock()


def load():
    with open(DB, "r", encoding="utf-8") as f:
        return json.load(f)


def save(data):
    with _dblock:
        if os.path.exists(DB):
            shutil.copyfile(DB, DB + ".bak")
        tmp = DB + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, DB)


def get_store(data, sid):
    for s in data["stores"]:
        if s["id"] == sid:
            return s
    return None


# ---------------------------------------------------------------- 卡連線
_card = None
_card_store = None
_cardlock = threading.RLock()
_log = []


def note(m):
    _log.append(time.strftime("%H:%M:%S  ") + str(m))
    del _log[:-200]
    print(m, flush=True)


def local_prefixes():
    out = []
    try:
        for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = i[4][0]
            if ip.startswith("127."):
                continue
            p = ip.rsplit(".", 1)[0]
            if p not in out:
                out.append(p)
    except Exception:
        pass
    return out


def port_open(ip, port, t=0.4):
    s = socket.socket()
    s.settimeout(t)
    try:
        return s.connect_ex((ip, port)) == 0
    finally:
        s.close()


# ---------------------------------------------------------------- 卡主動回連
# 4G 路由器幾乎都是電信商的大 NAT（CGNAT），對外沒有可以連進來的位址，
# 所以「總部連去門市」這條路在 4G 上是走不通的，端口轉發也沒得設。
#
# 卡本身支援反過來做：SetSDKTcpServer 設好之後，卡會主動撥回我們指定的
# 位址與埠。連線一旦建立，SDK 協議的角色不變 —— 我們還是送 <in>、卡還是回
# <out>，只是這條 TCP 是它撥過來的。這樣不管門市在 4G、在店內 Wi-Fi、
# 還是在別人家的網路後面，都連得回來。
#
# ★ 這段還沒有在實體卡上驗證過。驗證方法寫在 遠端架構.md 的「測試一」。
_reverse = {}                # device_id -> ReverseCard
_revlock = threading.RLock()


class ReverseCard(hd.HDCard):
    """卡主動撥回來的那條連線。

    跟 HDCard 完全一樣，差別只在 socket 是 accept 出來的、不是我們 connect 的，
    所以 connect() 要跳過撥號，直接做版本協商與取 guid。
    """

    def __init__(self, sock, addr, log=print):
        hd.HDCard.__init__(self, addr[0], addr[1], timeout=20.0, log=log)
        self.sock = sock
        self.sock.settimeout(self.timeout)
        self.buf = b""
        self.device_id = ""
        self.last_seen = time.time()

    def connect(self):
        self._send_raw(struct.pack("<HHI", 8, hd.CMD_SERVICE_ASK, hd.LOCAL_TCP_VERSION))
        self._pump(hd.CMD_SERVICE_ANS, time.time() + self.timeout)
        xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<sdk guid="##GUID">\n'
               '  <in method="GetIFVersion">\n'
               '    <version value="1000000"/>\n'
               '  </in>\n'
               '</sdk>')
        text = self._send_xml_bytes(xml.encode("utf-8")).decode("utf-8", "replace")
        m = re.search(r'<sdk[^>]*guid="([^"]*)"', text)
        self.guid = m.group(1) if m else ""
        return text


def _hq_serve(conn, addr):
    c = ReverseCard(conn, addr, log=note)
    try:
        c.connect()
        info = c.call('  <in method="GetDeviceInfo"/>')
        # 一定要指名 <device> 那個標籤。回應的第一行是 <sdk guid="...">，
        # 直接抓 id=" 會先命中那個 guid —— 每次連線都不一樣，
        # reverse_for() 就永遠對不上 stores.json 裡的 device_id，
        # 結果是遠端悄悄地永遠連不上。
        #     <device cpu="RK.px30" model="C16L" name="BoxPlayer" id="C16L-D24-000A2"/>
        m = re.search(r'<device\b[^>]*\bid="([^"]+)"', info)
        c.device_id = m.group(1) if m else ("unknown@%s" % addr[0])
        with _revlock:
            old = _reverse.pop(c.device_id, None)
            if old:
                try:
                    old.close()
                except Exception:
                    pass
            _reverse[c.device_id] = c
        note("★ 卡從 %s 撥回來了：%s" % (addr[0], c.device_id))
    except Exception as e:
        note("撥回的連線握手失敗（%s）：%r" % (addr[0], e))
        try:
            conn.close()
        except Exception:
            pass


def hq_listener():
    """聽卡撥回來。順便定期戳一下，把卡的心跳吃掉、順便驗證線還活著。"""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", HQ_PORT))
    srv.listen(16)
    note("主動回連監聽中：0.0.0.0:%d" % HQ_PORT)

    def keepalive():
        while True:
            time.sleep(20)
            with _revlock:
                items = list(_reverse.items())
            for did, c in items:
                try:
                    c.call('  <in method="GetDeviceInfo"/>')
                    c.last_seen = time.time()
                except Exception:
                    note("撥回的連線斷了：%s" % did)
                    with _revlock:
                        _reverse.pop(did, None)
                    try:
                        c.close()
                    except Exception:
                        pass

    threading.Thread(target=keepalive, daemon=True).start()
    while True:
        try:
            conn, addr = srv.accept()
            threading.Thread(target=_hq_serve, args=(conn, addr), daemon=True).start()
        except Exception as e:
            note("監聽出錯：%r" % e)
            time.sleep(1)


def reverse_for(store):
    """這家店的卡有沒有撥回來？有的話直接用那條線，不必掃網段。"""
    did = (store.get("card") or {}).get("device_id")
    if not did:
        return None
    with _revlock:
        return _reverse.get(did)


def find_card_ip(store):
    port = (store.get("card") or {}).get("sdk_port", 10001)
    last = (store.get("card") or {}).get("last_known_ip")
    if last and port_open(last, port):
        return last
    import concurrent.futures
    for pre in local_prefixes():
        targets = ["%s.%d" % (pre, i) for i in range(1, 255)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=128) as pool:
            futs = {pool.submit(port_open, ip, port): ip for ip in targets}
            for f in concurrent.futures.as_completed(futs):
                if f.result():
                    ip = futs[f]
                    c = hd.HDCard(ip, port, timeout=4.0, log=lambda m: None)
                    try:
                        c.connect()
                        return ip
                    except Exception:
                        pass
                    finally:
                        c.close()
    return None


def connect(sid):
    global _card, _card_store
    with _cardlock:
        data = load()
        store = get_store(data, sid)
        if not store:
            raise ValueError("沒有這家店")

        # 卡自己撥回來的線優先。遠端的門市只會有這條，掃網段是掃不到的。
        rev = reverse_for(store)
        if rev:
            if _card and _card is not rev:
                try:
                    _card.close()
                except Exception:
                    pass
            _card = rev
            _card_store = sid
            note("已連上 %s（卡主動回連，來源 %s）" % (store["name"], rev.ip))
            return rev.ip

        ip = find_card_ip(store)
        if not ip:
            if HQ_PORT and (store.get("card") or {}).get("device_id"):
                raise RuntimeError(
                    "找不到卡。同網段掃不到，這張卡也還沒撥回來（在聽 %d 埠）。"
                    "遠端的門市只能等它自己撥，通常是幾十秒到幾分鐘。" % HQ_PORT)
            raise RuntimeError("找不到卡。檢查網路線，或跑 現場連線.bat")
        port = (store.get("card") or {}).get("sdk_port", 10001)
        if _card:
            try:
                _card.close()
            except Exception:
                pass
        _card = hd.HDCard(ip, port, timeout=20.0, log=note)
        _card.connect()
        _card_store = sid
        store.setdefault("card", {})["last_known_ip"] = ip
        save(data)
        note("已連上 %s（%s）" % (store["name"], ip))
        return ip


def card_or_raise():
    if not _card:
        raise RuntimeError("還沒連上卡，先按「連線」")
    return _card


def drop_reverse(card):
    """把一條已經死掉的回連線從名單裡拿掉。

    不拿掉的話 connect() 會再把同一個死掉的物件交回來 —— 重試永遠不會成功，
    而且還會擋住「退回去掃網段」這條路。
    """
    if not isinstance(card, ReverseCard):
        return
    with _revlock:
        if _reverse.get(card.device_id) is card:
            _reverse.pop(card.device_id, None)
            note("回連線已失效，等卡自己再撥回來：%s" % card.device_id)
    try:
        card.close()
    except Exception:
        pass


def call(xml):
    """對卡送一段指令，斷線就自動重連一次。"""
    with _cardlock:
        try:
            return card_or_raise().call(xml)
        except Exception:
            if _card_store:
                note("連線斷了，重連中…")
                drop_reverse(_card)
                connect(_card_store)
                return card_or_raise().call(xml)
            raise


# ---------------------------------------------------------------- 排程
_return_timer = [None]
_last_patrol = [0.0]


def switch_to(sid, key):
    data = load()
    store = get_store(data, sid)
    pub = (store.get("published") or {}).get(key)
    if not pub:
        return False
    out = call('  <in method="SwitchProgram">\n'
               '    <program guid="%s"/>\n  </in>' % pub["program"])
    return hd.attr(out, "out", "result") == "kSuccess"


def schedule_return_to_idle(sid, seconds):
    """事件播完自動切回待機。卡是輪播所有節目，不會自己回來。"""
    if _return_timer[0]:
        _return_timer[0].cancel()

    def back():
        try:
            if switch_to(sid, "idle"):
                note("播完了，回待機")
        except Exception as e:
            note("回待機失敗：%r" % e)

    t = threading.Timer(seconds + 0.5, back)
    t.daemon = True
    t.start()
    _return_timer[0] = t


def scheduler():
    """整點巡迴的自動觸發。patrol_every_minutes = 0 就是不自動。"""
    while True:
        time.sleep(20)
        try:
            if not _card_store:
                continue
            data = load()
            store = get_store(data, _card_store)
            if not store:
                continue
            prm = comp.merged_params(store, data)
            every = float(prm.get("patrol_every_minutes", 0) or 0)
            if every <= 0:
                continue
            now = time.time()
            if now - _last_patrol[0] < every * 60:
                continue
            _last_patrol[0] = now
            if switch_to(_card_store, "patrol"):
                note("整點巡迴自動觸發（每 %g 分鐘）" % every)
                pub = (store.get("published") or {}).get("patrol") or {}
                schedule_return_to_idle(_card_store, float(pub.get("seconds") or 12))
        except Exception:
            pass


# ---------------------------------------------------------------- API
def api(path, q, body):
    data = load()

    if path == "/api/params":
        if body:
            p = data.setdefault("params", {})
            for k, v in body.items():
                s = str(v).strip()
                try:                       # 數字存數字，其餘（例如中獎文字）存字串
                    p[k] = float(s) if "." in s else int(s)
                except ValueError:
                    p[k] = s
            save(data)
            note("參數更新：%s" % ", ".join("%s=%s" % kv for kv in body.items()))
        return {"params": comp.artwork.params(data.get("params"))}

    if path == "/api/stores":
        with _revlock:
            dialed = {k: {"ip": c.ip, "last_seen": int(time.time() - c.last_seen)}
                      for k, c in _reverse.items()}
        return {
            "stores": data["stores"],
            "params": comp.artwork.params(data.get("params")),
            "event_types": data["event_types"],
            "connected": _card_store,
            "card_ip": _card.ip if _card else None,
            "reverse": isinstance(_card, ReverseCard),
            "hq_port": HQ_PORT,
            "dialed_in": dialed,
            "log": _log[-30:],
        }

    # 心跳用。監控腳本每分鐘打這支就知道後台還活著、有幾張卡撥回來。
    if path == "/api/health":
        with _revlock:
            n = len(_reverse)
        return {"ok": True, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "connected": _card_store, "dialed_in": n, "hq_port": HQ_PORT}

    # 讀／寫卡的「主動回連」設定。這是遠端能不能控的關鍵，裝機當天一定要設。
    if path == "/api/hq":
        if body:
            host = str(body.get("host", "")).strip()
            port = int(body.get("port") or 0)
            out = call('  <in method="SetSDKTcpServer">\n'
                       '    <server port="%d" host="%s"/>\n  </in>' % (port, host))
            res = hd.attr(out, "out", "result")
            note("主動回連設成 %s:%d → %s" % (host or "(空)", port, res))
            if res == "kSuccess" and _card_store:
                st = get_store(data, _card_store)
                st.setdefault("hq", {}).update({"host": host, "port": port})
                save(data)
        out = call('  <in method="GetSDKTcpServer"/>')
        return {"ok": True,
                "host": hd.attr(out, "server", "host"),
                "port": hd.attr(out, "server", "port")}

    if path == "/api/connect":
        return {"ok": True, "ip": connect(q.get("store", [""])[0])}

    if path == "/api/publish":
        sid = q.get("store", [""])[0]
        store = get_store(data, sid)
        if _card_store != sid:
            connect(sid)
        note("── 開始編譯 %s ──" % store["name"])
        built = comp.build_store(store, data, log=note)
        with _cardlock:
            guids = comp.publish_store(card_or_raise(), store, built, data, log=note)
        store["published"] = guids
        save(data)
        note("發佈完成：%s" % ", ".join(guids))
        return {"ok": True, "published": guids}

    if path == "/api/switch":
        sid = q.get("store", [""])[0]
        key = q.get("key", [""])[0]
        store = get_store(data, sid)
        published = store.get("published") or {}
        prm = comp.merged_params(store, data)

        # 預錄節目沒有隨機性，所以骰子在這裡擲：
        # 續碗中獎播劈石那支，沒中播只跑過去那支。
        hit = None
        if key == "okawari" and "okawari_miss" in published:
            hit = random.random() < float(prm.get("okawari_hit_chance", 0.25))
            key = "okawari" if hit else "okawari_miss"

        pub = published.get(key)
        if not pub:
            raise RuntimeError("%s 還沒發佈，先按「發佈到卡」" % key)
        out = call('  <in method="SwitchProgram">\n'
                   '    <program guid="%s"/>\n  </in>' % pub["program"])
        res = hd.attr(out, "out", "result")
        if hit is None:
            note("切到 %s → %s" % (key, res))
        else:
            note("續碗擲骰：%s（機率 %.0f%%）"
                 % ("中獎！" if hit else "沒中", float(prm.get("okawari_hit_chance", .25)) * 100))

        if res == "kSuccess" and key != "idle" and "idle" in published:
            schedule_return_to_idle(sid, float(pub.get("seconds") or 10))
        return {"ok": res == "kSuccess", "result": res, "hit": hit}

    if path == "/api/brightness":
        v = int(q.get("value", ["50"])[0])
        # 四個子節點要送齊，少送卡會回 kParseXmlFailed
        out = call('  <in method="SetLuminancePloy">\n'
                   '    <mode value="default"/>\n'
                   '    <default value="%d"/>\n'
                   '    <ploy/>\n'
                   '    <sensor min="1" max="100" time="5"/>\n'
                   '  </in>' % v)
        res = hd.attr(out, "out", "result")
        note("亮度設成 %d → %s" % (v, res))
        return {"ok": res == "kSuccess", "result": res}

    if path == "/api/wipe":
        with _cardlock:
            n = comp.wipe_programs(card_or_raise(), log=note)
        st = get_store(data, _card_store)
        if st:
            st.pop("published", None)
            save(data)
        return {"ok": True, "deleted": n}

    if path == "/api/add_store":
        sid = (body.get("id") or "").strip().lower()
        if not sid or get_store(data, sid):
            raise ValueError("代號不能空白，也不能跟現有的重複")
        data["stores"].append({
            "id": sid,
            "name": body.get("name") or sid,
            "enabled": True,
            "canvas": {"width": int(body.get("width") or 0) or None,
                       "height": int(body.get("height") or 0) or None,
                       "pitch": None, "source": "後台新增"},
            "card": {"sdk_port": 10001, "ip_mode": "dhcp"},
            "hq": {"host": "", "port": 0},
            "network": {"uplink": "4g-router"},
            "contents": [
                {"key": k, "enabled": True, "variants": ["a"],
                 "loop": (k == "idle"), "seconds": None}
                for k in ("idle", "patrol", "okawari")
            ],
        })
        save(data)
        note("新增門店：%s（%s）" % (body.get("name") or sid, sid))
        return {"ok": True}

    if path == "/api/remove_store":
        s = get_store(data, body.get("id", ""))
        if not s:
            raise ValueError("沒有這家店")
        data["stores"].remove(s)
        save(data)
        note("刪除門店：%s" % s["name"])
        return {"ok": True}

    if path == "/api/set_canvas":
        s = get_store(data, body.get("id", ""))
        if not s:
            raise ValueError("沒有這家店")
        s["canvas"]["width"] = int(body.get("width") or 0) or None
        s["canvas"]["height"] = int(body.get("height") or 0) or None
        s["canvas"]["source"] = "後台設定"
        save(data)
        return {"ok": True}

    if path == "/api/toggle_content":
        s = get_store(data, body.get("id", ""))
        for c in s["contents"]:
            if c["key"] == body.get("key"):
                c["enabled"] = not c.get("enabled")
        save(data)
        return {"ok": True}

    raise ValueError("不認得的 API：%s" % path)


def screenshot():
    data = load()
    store = get_store(data, _card_store) if _card_store else None
    c = (store or {}).get("canvas") or {}
    w, h = c.get("width") or 160, c.get("height") or 40
    xml = call('  <in method="GetScreenshot2">\n'
               '    <image width="%d" height="%d"/>\n  </in>' % (w, h))
    b64 = hd.attr(xml, "image", "data")
    if not b64:
        return None, None
    raw = base64.b64decode(b64)
    ct = "image/png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return raw, ct


# ---------------------------------------------------------------- 網頁
# 介面已經搬到 ../web/index.html —— 同一份檔案同時給 GitHub Pages 和這台後台用，
# 所以不會有「手機上是舊版」這種事。這裡只負責把它端出去。


MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8", ".md": "text/plain; charset=utf-8",
        ".json": "application/json; charset=utf-8", ".png": "image/png",
        ".svg": "image/svg+xml", ".ico": "image/x-icon", ".mp4": "video/mp4"}


def static_file(path):
    """從 web/ 端出檔案。跟 GitHub Pages 上的是同一份，所以介面只有一版。"""
    rel = path.lstrip("/") or "index.html"
    full = os.path.abspath(os.path.join(WEB, rel))
    if not full.startswith(WEB) or not os.path.isfile(full):   # 不准跳出 web/
        return None, None
    with open(full, "rb") as f:
        return f.read(), MIME.get(os.path.splitext(full)[1].lower(),
                                  "application/octet-stream")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        """讓 GitHub Pages 上的頁面打得到這台後台。

        兩件事都要做：
          Allow-Origin          放行跨網域
          Allow-Private-Network Chrome 的 Private Network Access —— 公網頁面
                                要打區網／localhost 的服務，預檢時卡這個。

        這是門店內網的工具，不做帳號。真的要放到公網請走 Cloudflare Tunnel
        或反向代理，在那一層加驗證（見 遠端架構.md）。
        """
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send(self, code, ctype, payload):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, obj, code=200):
        self._send(code, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            raw, ct = static_file(u.path)
            if raw is not None:
                return self._send(200, ct, raw)
            if u.path in ("/", "/index.html"):
                return self._send(500, "text/html; charset=utf-8", (
                    "<meta charset=utf-8><body style='font:16px sans-serif;padding:40px'>"
                    "<h2>找不到介面檔</h2><p>應該要有這個檔：<code>%s</code>"
                    "<p>它跟後台是同一份、也是放上 GitHub 的那一份。"
                    "如果整個 web 資料夾不見了，從 GitHub 拉回來就好。"
                    % os.path.join(WEB, "index.html")).encode("utf-8"))
            return self._json({"error": "沒有這個頁面"}, 404)
        if u.path == "/api/shot":
            try:
                raw, ct = screenshot()
                if not raw:
                    return self._json({"error": "沒有畫面"}, 500)
                return self._send(200, ct, raw)
            except Exception as e:
                return self._json({"error": str(e)}, 500)
        try:
            return self._json(api(u.path, parse_qs(u.query), {}))
        except Exception as e:
            traceback.print_exc()
            return self._json({"error": str(e)}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}
        try:
            return self._json(api(u.path, parse_qs(u.query), body))
        except Exception as e:
            traceback.print_exc()
            return self._json({"error": str(e)}, 500)


def main():
    threading.Thread(target=scheduler, daemon=True).start()
    if HQ_PORT:
        threading.Thread(target=hq_listener, daemon=True).start()
    ips = [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
           if not i[4][0].startswith(("127.", "169.254."))]
    print("=" * 62)
    print("  OKAWARI 門頭屏 · 後台")
    print("=" * 62)
    print("")
    print("  這台電腦自己看：http://localhost:%d" % PORT)
    print("")
    print("  同一個 Wi-Fi 的手機或電腦：")
    for ip in dict.fromkeys(ips):
        print("      http://%s:%d" % (ip, PORT))
    print("")
    print("  介面也放在 GitHub Pages 上，那邊開的話「連線設定」填 http://localhost:%d" % PORT)
    if HQ_PORT:
        print("")
        print("  卡主動回連：正在聽 0.0.0.0:%d" % HQ_PORT)
    else:
        print("")
        print("  卡主動回連：沒開。要開的話設環境變數 OKAWARI_HQ_PORT=6000 再啟動。")
    print("")
    print("  關掉這個視窗就會停。")
    print("=" * 62)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
