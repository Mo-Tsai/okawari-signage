# -*- coding: utf-8 -*-
"""
OKAWARI 續碗按鈕機 · 共用核心

同一份程式跑在兩個地方：
  - M5Stack Basic（MicroPython / UIFlow2 韌體）→ 由 main.py 呼叫
  - 筆電（一般 Python）→ 由 桌上測試.py 呼叫，M5Stack 沒到貨前先驗證整條路

只用兩邊都有的標準庫：socket / struct / time / re / random。
協議實作抄自 _明天帶去_LED實測_20260810/02_程式端/hd_test.py（2026-08-10 已實測）。

設計原則（見 實體按鈕_方案研究.md）：
  - 播完切回「按下前正在播的節目」，不假設有 idle —— 時段節目也照樣正確
  - 播放中：dice 類事件忽略連打；combo 類事件連按升級（combo1→2→3）
  - 任何錯誤 → error 狀態 → 每 5 秒自動重連，左鍵可手動催
"""

import socket
import struct
import time
import re
import random

CMD_HEARTBEAT_ASK = 0x005F
CMD_HEARTBEAT_ANS = 0x0060
CMD_ERROR         = 0x2000
CMD_SERVICE_ASK   = 0x2001
CMD_SERVICE_ANS   = 0x2002
CMD_SDK_ASK       = 0x2003
CMD_SDK_ANS       = 0x2004

LOCAL_TCP_VERSION = 0x1000009
XML_MAX           = 9200

SWITCH_XML = ('  <in method="SwitchProgram">\n'
              '    <program guid="%s"/>\n  </in>')


class CardError(Exception):
    pass


def attr(xml, tag, name):
    # MicroPython 的 re 不支援 \b，所以用寬鬆版。對已知回應格式夠用。
    m = re.search('<' + tag + '[^>]*' + name + '="([^"]*)"', xml)
    return m.group(1) if m else ""


def _tcp_connect(host, port, timeout):
    # MicroPython 沒有 socket.create_connection，自己組
    ai = socket.getaddrinfo(host, port)[0]
    s = socket.socket()
    s.settimeout(timeout)
    s.connect(ai[-1])
    return s


class CardLink:
    """一張灰度控制卡的連線（協議層，與 hd_test.py 的 HDCard 等價）。"""

    def __init__(self, ip, port=10001, timeout=8.0, log=None):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.log = log or (lambda m: None)
        self.sock = None
        self.buf = b""
        self.guid = ""

    def _read_packet(self):
        while True:
            if len(self.buf) >= 4:
                pkt_len, cmd = struct.unpack("<HH", self.buf[:4])
                if pkt_len == 0:
                    raise CardError("收到長度 0 的封包")
                if len(self.buf) >= pkt_len:
                    pkt = self.buf[:pkt_len]
                    self.buf = self.buf[pkt_len:]
                    return cmd, pkt[4:]
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CardError("控制卡把連線關掉了")
            self.buf += chunk

    def _pump(self, want_cmd, deadline):
        acc = b""
        while True:
            if time.time() > deadline:
                raise CardError("等控制卡回應逾時")
            cmd, payload = self._read_packet()
            if cmd in (CMD_HEARTBEAT_ASK, CMD_HEARTBEAT_ANS):
                self.sock.send(struct.pack("<HH", 4, CMD_HEARTBEAT_ASK))
                continue
            if cmd == CMD_ERROR:
                code = struct.unpack("<H", payload[:2])[0] if len(payload) >= 2 else -1
                raise CardError("卡回報錯誤碼 %d" % code)
            if cmd == want_cmd == CMD_SERVICE_ANS:
                return b""
            if cmd == CMD_SDK_ANS:
                if len(payload) < 8:
                    raise CardError("SDK 回應封包太短")
                total, _index = struct.unpack("<II", payload[:8])
                acc += payload[8:]
                if len(acc) >= total:
                    return acc
                continue
            self.log("(未預期封包 cmd=0x%04x，忽略)" % cmd)

    def connect(self):
        self.sock = _tcp_connect(self.ip, self.port, self.timeout)
        self.buf = b""
        # 一、版本協商
        self.sock.send(struct.pack("<HHI", 8, CMD_SERVICE_ASK, LOCAL_TCP_VERSION))
        self._pump(CMD_SERVICE_ANS, time.time() + self.timeout)
        # 二、拿通訊 guid
        xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<sdk guid="##GUID">\n'
               '  <in method="GetIFVersion">\n'
               '    <version value="1000000"/>\n'
               '  </in>\n'
               '</sdk>')
        text = self._send_xml(xml.encode("utf-8")).decode("utf-8")
        self.guid = attr(text, "sdk", "guid")
        self.log("握手完成 guid=%s" % (self.guid or "(空)"))

    def _send_xml(self, xml_bytes):
        total = len(xml_bytes)
        index = 0
        while index < total:
            chunk = xml_bytes[index:index + XML_MAX]
            head = struct.pack("<HHII", 12 + len(chunk), CMD_SDK_ASK, total, index)
            self.sock.send(head + chunk)
            index += len(chunk)
        return self._pump(CMD_SDK_ANS, time.time() + self.timeout)

    def call(self, inner_xml):
        xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<sdk guid="%s">\n%s\n</sdk>' % (self.guid, inner_xml))
        return self._send_xml(xml.encode("utf-8")).decode("utf-8")

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None


class ButtonCore:
    """按鈕機的狀態機。UI 只要做三件事：呼叫 tick()、把按鍵交給 press()、把
    state / msg / remaining() 畫出來。

    state: connect / ready / playing / error
    """

    KEEPALIVE = 15   # 秒。順便持續記住「現在在播哪個常駐節目」
    RETRY     = 5    # 斷線後幾秒重試

    def __init__(self, cfg, log=None):
        self.cfg = cfg
        self.log = log or (lambda m: None)
        self.link = None
        self.state = "connect"
        self.msg = "連線中"
        self.until = 0          # playing 結束時刻
        self.resident = ""      # 按下前正在播的節目 guid（回歸點）
        self.combo_stage = 0    # 0 = 不在 combo 中
        self.count_today = 0    # 今日觸發次數（斷電歸零，夠用）
        self._next_keepalive = 0
        self._next_retry = 0

    # ------------------------------------------------ 對外
    def tick(self):
        now = time.time()
        if self.state == "connect":
            try:
                self._connect()
            except Exception as e:
                self._fail(e)
            return
        if self.state == "error":
            if now >= self._next_retry:
                self.state = "connect"
                self.msg = "連線中"
            return
        if self.state == "ready" and now >= self._next_keepalive:
            try:
                out = self.link.call('  <in method="GetCurrentPlayProgramGUID"/>')
                g = attr(out, "program", "guid")
                if g:
                    self.resident = g
                self._next_keepalive = now + self.KEEPALIVE
            except Exception as e:
                self._fail(e)
            return
        if self.state == "playing" and now >= self.until:
            try:
                if self.resident:
                    self.link.call(SWITCH_XML % self.resident)
                self.state = "ready"
                self.msg = "就緒"
                self.combo_stage = 0
                self._next_keepalive = now + self.KEEPALIVE
            except Exception as e:
                self._fail(e)

    def press(self, which):
        """which: 'main'(中鍵) / 'promo'(右鍵) / 'reconnect'(左鍵)。
        回傳給 UI 顯示的一句話。"""
        if which == "reconnect":
            self._drop()
            self.state = "connect"
            self.msg = "重新連線"
            return self.msg
        act = (self.cfg.get("keys") or {}).get(which)
        if not act:
            return None
        if self.state == "playing":
            if which == "main" and act.get("type") == "combo" and self.combo_stage:
                return self._combo_up(act)
            return "播放中，再等等"
        if self.state != "ready":
            return "還沒連上卡"
        if act.get("type") == "dice":
            return self._do_dice(act)
        if act.get("type") == "combo":
            self.combo_stage = 1
            return self._play(act["stages"][0], "COMBO 1")
        if act.get("type") == "single":
            return self._play(act["key"], act.get("label", act["key"]))
        return None

    def remaining(self):
        if self.state != "playing":
            return 0
        r = self.until - time.time()
        return r if r > 0 else 0

    # ------------------------------------------------ 內部
    def _connect(self):
        card = self.cfg["card"]
        self.link = CardLink(card["ip"], card.get("port", 10001),
                             timeout=8.0, log=self.log)
        self.link.connect()
        # 多屏同步開著會切不動節目（SDK 文件），開機檢查一次
        try:
            out = self.link.call('  <in method="GetMulScreenSync"/>')
            if attr(out, "sync", "enable") == "true":
                self.log("警告：卡的多屏同步是開的，SwitchProgram 可能無效")
        except Exception:
            pass
        self.state = "ready"
        self.msg = "就緒"
        self._next_keepalive = 0   # 馬上抓一次目前節目
        self.log("已連上卡 %s" % card["ip"])

    def _do_dice(self, act):
        progs = self.cfg["programs"]
        hit = random.random() < float(act.get("chance", 0.25))
        key = act["hit"] if hit else act["miss"]
        if key not in progs:            # 沒發佈沒中版就一律播中獎版
            key, hit = act["hit"], True
        label = "中獎！" if hit else "沒中"
        return self._play(key, label)

    def _combo_up(self, act):
        stages = act["stages"]
        if self.combo_stage >= len(stages):
            return "COMBO MAX"
        self.combo_stage += 1
        return self._play(stages[self.combo_stage - 1],
                          "COMBO %d" % self.combo_stage)

    def _play(self, key, label):
        pub = self.cfg["programs"].get(key)
        if not pub:
            return "「%s」還沒發佈到卡" % key
        try:
            out = self.link.call(SWITCH_XML % pub["guid"])
            res = attr(out, "out", "result")
            if res != "kSuccess":
                return "卡拒絕了：%s" % (res or "(無回應)")
            self.state = "playing"
            self.until = time.time() + float(pub.get("seconds") or 10) + 0.5
            self.count_today += 1
            self.msg = label
            self.log("觸發 %s（%s）" % (key, label))
            return label
        except Exception as e:
            self._fail(e)
            return self.msg

    def _fail(self, e):
        self._drop()
        self.state = "error"
        self.msg = "連線失敗：%s" % e
        self._next_retry = time.time() + self.RETRY
        self.log(self.msg)

    def _drop(self):
        if self.link:
            self.link.close()
        self.link = None
        self.combo_stage = 0
