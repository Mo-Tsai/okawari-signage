#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灰度 (HuiDu) 全彩控制卡 —— 現場測試工具
OKAWARI 門頭屏專案 / 次元光電實測用

依據：灰度 SDK V3.1 原始碼 (HDSDK.cpp / SDKInfo.h) 實作
通訊：TCP，預設 port 10001

只用 Python 標準函式庫，不需要安裝任何套件、不需要網路。
"""

import base64
import concurrent.futures
import datetime
import os
import re
import socket
import struct
import sys
import time

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


# ---------------------------------------------------------------- 協議常數
CMD_HEARTBEAT_ASK = 0x005F
CMD_HEARTBEAT_ANS = 0x0060
CMD_ERROR         = 0x2000
CMD_SERVICE_ASK   = 0x2001
CMD_SERVICE_ANS   = 0x2002
CMD_SDK_ASK       = 0x2003
CMD_SDK_ANS       = 0x2004

LOCAL_TCP_VERSION = 0x1000009
XML_MAX           = 9200

DEFAULT_PORT      = 10001


# 錯誤碼（取自 SDK 文件 Protocol/錯誤碼定義）
ERROR_CODES = [
    "正常", "寫檔完成", "流程錯誤", "版本過低", "設備被佔用",
    "檔案被佔用", "回讀檔案的使用者過多", "封包長度錯誤", "無效的參數",
    "儲存空間不夠", "建立檔案失敗", "寫檔失敗", "讀檔失敗", "無效的檔案資料",
    "檔案內容出錯", "開檔失敗", "定位檔案失敗", "重新命名失敗", "找不到檔案",
    "檔案還沒接收完", "xml 指令過長", "無效的 xml 索引值（節目 index/guid 不存在）",
    "解析 xml 出錯", "無效的方法名（這張卡不認得這個指令）", "記憶體錯誤",
    "系統錯誤", "不支援的影片", "不是多媒體檔", "解析影片失敗",
    "不支援的幀率", "不支援的解析度（影片）", "不支援的格式（影片）",
    "不支援的影片長度", "下載檔案失敗", "下載檔案中", "處理中",
    "顯示屏節點為空", "節點已存在", "節點不存在", "外掛不存在",
    "校驗 license 失敗", "找不到 wifi 模組", "測試 wifi 模組失敗",
    "執行錯誤", "不支援的方法", "非法的 guid", "韌體格式錯誤",
    "標籤不存在", "屬性不存在", "建立標籤失敗", "不支援的設備型號",
    "權限不足", "密碼太簡單", "USB 未插入",
]


def error_text(code):
    if 0 <= code < len(ERROR_CODES):
        return "%d（%s）" % (code, ERROR_CODES[code])
    return "%d（未知錯誤碼）" % code


# ---------------------------------------------------------------- 紀錄檔
class Logger:
    def __init__(self, path):
        self.path = path
        self.fh = open(path, "a", encoding="utf-8")
        self.fh.write("\n" + "=" * 70 + "\n")
        self.fh.write("測試開始：%s\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.fh.write("=" * 70 + "\n")
        self.fh.flush()

    def __call__(self, msg, screen=True):
        if screen:
            print(msg)
        self.fh.write(str(msg) + "\n")
        self.fh.flush()

    def file_only(self, msg):
        self.fh.write(str(msg) + "\n")
        self.fh.flush()


# ---------------------------------------------------------------- 控制卡
class CardError(Exception):
    pass


class HDCard:
    """一張灰度控制卡的連線。"""

    def __init__(self, ip, port=DEFAULT_PORT, timeout=8.0, log=print):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.log = log
        self.sock = None
        self.buf = b""
        self.guid = ""

    # -------------------------------------------------- 低階收送
    def _send_raw(self, data):
        self.sock.sendall(data)

    def _read_packet(self):
        """讀出一個完整封包，回傳 (cmd, payload)。payload 不含 4 byte 表頭。"""
        while True:
            if len(self.buf) >= 4:
                pkt_len, cmd = struct.unpack_from("<HH", self.buf, 0)
                if pkt_len == 0:
                    raise CardError("收到長度為 0 的封包，協議異常")
                if len(self.buf) >= pkt_len:
                    pkt = self.buf[:pkt_len]
                    self.buf = self.buf[pkt_len:]
                    return cmd, pkt[4:]
            chunk = self.sock.recv(65536)
            if not chunk:
                raise CardError("控制卡把連線關掉了")
            self.buf += chunk

    def _pump(self, want_cmd, deadline):
        """一直收封包直到拿到想要的 cmd。中途自動回心跳。"""
        acc = b""
        total = None
        while True:
            if time.time() > deadline:
                raise CardError("等待控制卡回應逾時")
            cmd, payload = self._read_packet()

            if cmd in (CMD_HEARTBEAT_ASK, CMD_HEARTBEAT_ANS):
                self._send_raw(struct.pack("<HH", 4, CMD_HEARTBEAT_ASK))
                continue

            if cmd == CMD_ERROR:
                code = struct.unpack_from("<H", payload, 0)[0] if len(payload) >= 2 else -1
                raise CardError("控制卡回報錯誤 %s" % error_text(code))

            if cmd == want_cmd == CMD_SERVICE_ANS:
                return b""

            if cmd == CMD_SDK_ANS:
                if len(payload) < 8:
                    raise CardError("SDK 回應封包太短")
                total, index = struct.unpack_from("<II", payload, 0)
                acc += payload[8:]
                if len(acc) >= total:
                    return acc
                continue

            # 其它未預期的封包，記下來繼續等
            self.log("  （收到未預期封包 cmd=0x%04x，忽略）" % cmd)

    # -------------------------------------------------- 連線 / 握手
    def connect(self):
        self.log("連線中 %s:%d ..." % (self.ip, self.port))
        self.sock = socket.create_connection((self.ip, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        self.buf = b""

        # 第一步：版本協商
        self._send_raw(struct.pack("<HHI", 8, CMD_SERVICE_ASK, LOCAL_TCP_VERSION))
        self._pump(CMD_SERVICE_ANS, time.time() + self.timeout)

        # 第二步：取得這次連線的 guid
        xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<sdk guid="##GUID">\n'
               '  <in method="GetIFVersion">\n'
               '    <version value="1000000"/>\n'
               '  </in>\n'
               '</sdk>')
        resp = self._send_xml_bytes(xml.encode("utf-8"))
        text = resp.decode("utf-8", errors="replace")
        m = re.search(r'<sdk[^>]*guid="([^"]*)"', text)
        self.guid = m.group(1) if m else ""
        self.log("連線成功。通訊 guid = %s" % (self.guid or "(空)"))
        return text

    def _send_xml_bytes(self, xml_bytes):
        total = len(xml_bytes)
        index = 0
        while index < total:
            chunk = xml_bytes[index:index + XML_MAX]
            head = struct.pack("<HHII", 12 + len(chunk), CMD_SDK_ASK, total, index)
            self._send_raw(head + chunk)
            index += len(chunk)
        return self._pump(CMD_SDK_ANS, time.time() + self.timeout)

    def call(self, inner_xml):
        """送一段 <in .../> 內容，回傳控制卡的 XML 字串。"""
        xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<sdk guid="%s">\n%s\n</sdk>' % (self.guid, inner_xml))
        resp = self._send_xml_bytes(xml.encode("utf-8"))
        return resp.decode("utf-8", errors="replace")

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------- 指令包裝
def q_device_info(card):
    return card.call('  <in method="GetDeviceInfo"/>')


def q_current_program(card):
    return card.call('  <in method="GetCurrentPlayProgramGUID"/>')


def q_sdk_tcp_server(card):
    return card.call('  <in method="GetSDKTcpServer"/>')


def q_luminance(card):
    return card.call('  <in method="GetLuminancePloy"/>')


def q_switch_time(card):
    return card.call('  <in method="GetSwitchTime"/>')


def q_time_info(card):
    return card.call('  <in method="GetTimeInfo"/>')


def q_device_name(card):
    return card.call('  <in method="GetDeviceName"/>')


def q_mul_screen_sync(card):
    """多屏同步。SDK 文件明講：切節目前要先關掉這個，否則切不動。"""
    return card.call('  <in method="GetMulScreenSync"/>')


def q_network_info(card):
    """卡目前走哪一種網路（有線 / pppoe / wifi），以及有沒有 wifi 模組。"""
    return card.call('  <in method="GetNetworkInfo"/>')


def q_eth_info(card):
    """有線網路的 IP / 遮罩 / 閘道 / DNS，以及是不是 DHCP。"""
    return card.call('  <in method="GetEth0Info"/>')


def do_set_brightness(card, percent):
    """設成固定亮度（default 模式）。百貨室內一定會用到。

    四個子節點 mode / default / ploy / sensor 一定要送齊，
    少送任何一個卡都會回 kParseXmlFailed（2026-08-10 實測）。
    """
    body = ('  <in method="SetLuminancePloy">\n'
            '    <mode value="default"/>\n'
            '    <default value="%d"/>\n'
            '    <ploy/>\n'
            '    <sensor min="1" max="100" time="5"/>\n'
            '  </in>' % int(percent))
    return card.call(body)


def do_reboot(card, delay=3):
    return card.call('  <in method="Reboot" delay="%d"/>' % int(delay))


def do_switch_program(card, index=None, guid=None):
    if guid:
        body = '  <in method="SwitchProgram">\n    <program guid="%s"/>\n  </in>' % guid
    else:
        body = '  <in method="SwitchProgram">\n    <program index="%d"/>\n  </in>' % int(index)
    return card.call(body)


def q_screenshot(card, width, height):
    body = ('  <in method="GetScreenshot2">\n'
            '    <image width="%d" height="%d"/>\n  </in>' % (int(width), int(height)))
    return card.call(body)


# ---------------------------------------------------------------- 小工具
def attr(xml, tag, name):
    m = re.search(r'<%s\b[^>]*\b%s="([^"]*)"' % (tag, name), xml)
    return m.group(1) if m else ""


def pretty(xml):
    """把 XML 換行排一下，看起來不那麼痛苦。"""
    s = re.sub(r">\s*<", ">\n<", xml.strip())
    out, depth = [], 0
    for line in s.splitlines():
        line = line.strip()
        if line.startswith("</"):
            depth = max(0, depth - 1)
        out.append("    " + "  " * depth + line)
        if line.startswith("<") and not line.startswith("</") \
                and not line.endswith("/>") and not line.startswith("<?"):
            depth += 1
    return "\n".join(out)


def ask(prompt, default=""):
    s = input("%s%s：" % (prompt, ("（預設 %s）" % default) if default else "")).strip()
    return s or default


# ---------------------------------------------------------------- 找卡
def local_ipv4s():
    """筆電身上所有的 IPv4（不含 127.x）。"""
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127.") or ip in ips:
                continue
            ips.append(ip)
    except Exception:
        pass
    return ips


def local_prefixes():
    """筆電自己身上有哪些 192.168.x 之類的網段（排除沒拿到 IP 的 169.254）。"""
    found = []
    for ip in local_ipv4s():
        if ip.startswith("169.254."):
            continue
        pre = ip.rsplit(".", 1)[0]
        if pre not in found:
            found.append(pre)
    return found


def no_ip_yet():
    """筆電有沒有卡在「沒拿到 IP」的狀態（169.254 是 Windows 拿不到 IP 時給的）。"""
    ips = local_ipv4s()
    return bool(ips) and all(ip.startswith("169.254.") for ip in ips)


def port_open(ip, port, timeout=0.4):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, port)) == 0
    except Exception:
        return False
    finally:
        s.close()


def scan_subnet(prefix, port=DEFAULT_PORT, log=print):
    """把整個 x.x.x.1~254 掃一遍，找出 port 10001 開著的機器。"""
    hits = []
    targets = ["%s.%d" % (prefix, i) for i in range(1, 255)]
    log("  掃描 %s.1 ~ %s.254 ..." % (prefix, prefix))
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        futures = {pool.submit(port_open, ip, port): ip for ip in targets}
        for fut in concurrent.futures.as_completed(futures):
            if fut.result():
                hits.append(futures[fut])
    return sorted(hits, key=lambda x: int(x.rsplit(".", 1)[1]))


def verify_card(ip, port=DEFAULT_PORT):
    """真的握手一次，確認那台是灰度卡而不是別的東西。"""
    c = HDCard(ip, port, timeout=3.0, log=lambda m: None)
    try:
        c.connect()
        xml = q_device_info(c)
        return {
            "ip": ip,
            "model": attr(xml, "device", "model") or attr(xml, "device", "id"),
            "name": attr(xml, "device", "name"),
            "w": attr(xml, "screen", "width"),
            "h": attr(xml, "screen", "height"),
        }
    except Exception:
        return None
    finally:
        c.close()


def find_cards(log, prefix=None):
    """不知道 IP 的時候用這個。回傳找到的卡清單。"""
    prefixes = [prefix] if prefix else local_prefixes()
    if not prefixes:
        if no_ip_yet():
            log("")
            log("  ⚠ 你的筆電沒拿到 IP（現在是 169.254.x.x）。")
            log("")
            log("  這幾乎一定是「網路線直接接到卡」的情況——這條線上沒有")
            log("  分配 IP 的設備，所以要你自己指定一個。")
            log("")
            log("  怎麼做（大約一分鐘）：")
            log("   1. 先跟廠商問到卡的 IP，假設是 192.168.0.100")
            log("   2. 設定 → 網路和網際網路 → 乙太網路 → IP 指派 → 編輯 → 手動")
            log("   3. 開啟 IPv4，填：")
            log("        IP 位址   192.168.0.50    ← 前三段跟卡一樣，最後一段隨便挑")
            log("        子網路遮罩 255.255.255.0")
            log("        （閘道和 DNS 留空就好）")
            log("   4. 存檔，回來這裡選 9 重新連線")
            log("")
            log("  ★ 改之前先拍一張原本設定的照片，回家才好改回去。")
        else:
            log("  找不到筆電自己的網段。網路線可能沒插好，或轉接頭沒被認到。")
        return []

    cards = []
    for pre in prefixes:
        hits = scan_subnet(pre, log=log)
        if not hits:
            log("  %s.x 這個網段沒有找到東西。" % pre)
            continue
        log("  %s.x 有 %d 台機器開著 10001，逐一確認中..." % (pre, len(hits)))
        for ip in hits:
            info = verify_card(ip)
            if info:
                cards.append(info)
                log("  ★ 找到控制卡：%s（%s，屏 %s×%s）"
                    % (info["ip"], info["model"] or "型號不明",
                       info["w"] or "?", info["h"] or "?"))
    return cards


# ---------------------------------------------------------------- 各項測試
def act_full_scan(card, log):
    """一鍵全查：把架構文件 §9 待確認清單能問的全部問一遍。"""
    log("")
    log("──────── 一鍵全查 ────────")

    items = [
        ("設備資訊 GetDeviceInfo", q_device_info),
        ("設備名稱 GetDeviceName", q_device_name),
        ("卡上時間 GetTimeInfo", q_time_info),
        ("目前播放節目 GetCurrentPlayProgramGUID", q_current_program),
        ("網路現況 GetNetworkInfo", q_network_info),
        ("有線網路設定 GetEth0Info", q_eth_info),
        ("主動回連設定 GetSDKTcpServer", q_sdk_tcp_server),
        ("多屏同步 GetMulScreenSync", q_mul_screen_sync),
        ("亮度策略 GetLuminancePloy", q_luminance),
        ("開關屏時間 GetSwitchTime", q_switch_time),
    ]

    dev_xml = ""
    sync_xml = ""
    net_xml = ""
    for title, fn in items:
        log("")
        log("▶ %s" % title)
        try:
            xml = fn(card)
            log(pretty(xml))
            if fn is q_device_info:
                dev_xml = xml
            if fn is q_mul_screen_sync:
                sync_xml = xml
            if fn is q_network_info:
                net_xml = xml
        except CardError as e:
            log("    ✗ 失敗：%s" % e)
        except Exception as e:
            log("    ✗ 例外：%r" % e)

    if dev_xml:
        w = attr(dev_xml, "screen", "width")
        h = attr(dev_xml, "screen", "height")
        model = attr(dev_xml, "device", "model")
        log("")
        log("──────── 重點結論 ────────")
        log("  卡型號       ：%s" % (model or "(沒讀到)"))
        log("  卡認定的屏尺寸：%s × %s px   ← 這就是畫布尺寸，記下來" % (w or "?", h or "?"))
        log("  韌體 app     ：%s" % (attr(dev_xml, "version", "app") or "(沒讀到)"))
        log("  韌體 kernel  ：%s" % (attr(dev_xml, "version", "kernel") or "(沒讀到)"))

    if net_xml:
        mode = attr(net_xml, "network", "mode")
        has_wifi = re.search(r'<wifi\b[^>]*valid="true"', net_xml) is not None
        log("  卡目前走的網路：%s" % (mode or "(沒讀到)"))
        log("  這張卡有沒有 Wi-Fi：%s" % ("有，而且接上了" if has_wifi
                                          else "沒有接上（可能沒模組，要問廠商）"))

    if 'value="true"' in sync_xml:
        log("")
        log("  ⚠ 多屏同步是開的。SDK 文件明講切節目前要先關掉，")
        log("    否則第 2 項延遲測試會失敗。請廠商關掉再測。")
    log("")


def act_latency(card, log):
    """§8 唯一的技術風險：SwitchProgram 切換延遲實測。"""
    log("")
    log("──────── 切節目延遲實測（今天最重要的一項）────────")
    log("先請廠商在卡裡放兩個看得出差別的節目（例如一個全紅、一個全藍）。")
    log("")

    mode = ask("用 index 還是 guid 指定節目？(i/g)", "i").lower()
    if mode.startswith("g"):
        a = ask("節目 A 的 guid")
        b = ask("節目 B 的 guid")
        target = lambda x: dict(guid=x)
    else:
        a = ask("節目 A 的 index", "0")
        b = ask("節目 B 的 index", "1")
        target = lambda x: dict(index=int(x))

    try:
        rounds = int(ask("來回切幾次", "5"))
    except ValueError:
        rounds = 5

    log("")
    log("流程：程式送出切換指令 → 你盯著屏 → 畫面一變就按 Enter")
    log("（眼睛計時含你的反應時間約 0.2~0.3 秒，判讀時記得扣掉）")
    input("準備好了按 Enter 開始...")

    acks, eyes = [], []
    for i in range(rounds * 2):
        which = a if i % 2 == 0 else b
        label = "A" if i % 2 == 0 else "B"
        t0 = time.perf_counter()
        try:
            resp = do_switch_program(card, **target(which))
            t1 = time.perf_counter()
        except CardError as e:
            log("  第 %d 次（切到 %s）✗ 失敗：%s" % (i + 1, label, e))
            continue

        res = attr(resp, "out", "result")
        if res and res != "kSuccess":
            log("  第 %d 次（切到 %s）✗ 卡回 result=%s" % (i + 1, label, res))
            if res == "kInvalidXmlIndex":
                log("      → 這個 index/guid 卡上沒有。跟廠商確認節目編號。")
            continue

        input("  第 %d 次：已送出「切到節目 %s」→ 看到畫面變了就按 Enter" % (i + 1, label))
        t2 = time.perf_counter()

        ack_ms = (t1 - t0) * 1000
        eye_ms = (t2 - t0) * 1000
        acks.append(ack_ms)
        eyes.append(eye_ms)
        log("      卡回應 %.0f ms ｜ 眼睛看到 %.0f ms" % (ack_ms, eye_ms))
        log.file_only("      回應 XML：%s" % resp.replace("\n", " "))

    log("")
    if acks:
        log("──────── 延遲統計 ────────")
        log("  卡回應（ACK）  最快 %.0f / 平均 %.0f / 最慢 %.0f ms"
            % (min(acks), sum(acks) / len(acks), max(acks)))
        log("  眼睛看到畫面變 最快 %.0f / 平均 %.0f / 最慢 %.0f ms"
            % (min(eyes), sum(eyes) / len(eyes), max(eyes)))
        avg_eye = sum(eyes) / len(eyes) - 250  # 扣掉人的反應時間
        log("")
        log("  扣掉反應時間後，實際感受延遲大約 %.0f ms" % max(0, avg_eye))
        if avg_eye < 500:
            log("  → 判讀：即時觸發可行。「按續碗 → 勇者衝出來」做得起來。")
        elif avg_eye < 1200:
            log("  → 判讀：邊緣。即時感會打折，但還能用。")
        else:
            log("  → 判讀：太慢。架構文件 §8 的備案要啟動，")
            log("           改成每 30 秒累積結算式，動畫要多做幾版。")
    else:
        log("  一次都沒成功。把上面的錯誤訊息拍下來，回來給我看。")
    log("")


def act_screenshot(card, log, outdir):
    log("")
    w = ask("截圖寬度 px", "1200")
    h = ask("截圖高度 px", "120")
    try:
        xml = q_screenshot(card, w, h)
    except CardError as e:
        log("✗ 截圖失敗：%s" % e)
        return

    data_b64 = attr(xml, "image", "data")
    if not data_b64:
        log("✗ 回應裡沒有圖片資料。原始回應：")
        log(pretty(xml))
        return

    try:
        raw = base64.b64decode(data_b64)
    except Exception as e:
        log("✗ base64 解碼失敗：%r" % e)
        return

    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        ext = "png"
    elif raw[:2] == b"\xff\xd8":
        ext = "jpg"
    elif raw[:2] == b"BM":
        ext = "bmp"
    else:
        ext = "bin"

    name = "螢幕截圖_%s.%s" % (datetime.datetime.now().strftime("%H%M%S"), ext)
    path = os.path.join(outdir, name)
    with open(path, "wb") as f:
        f.write(raw)
    log("✓ 截圖存好了：%s（%d bytes）" % (path, len(raw)))


def act_brightness(card, log):
    """百貨室內一定會用到。出廠亮度全開在室內是刺眼的，而且傷屏。"""
    log("")
    log("──────── 設亮度 ────────")
    try:
        log("目前設定：")
        log(pretty(q_luminance(card)))
    except CardError as e:
        log("（讀不到目前亮度：%s）" % e)

    log("")
    log("室內百貨建議 40〜60。全開（100）在室內會刺眼，也縮短屏的壽命。")
    v = ask("要設成多少（1-100，直接 Enter 放棄）")
    if not v:
        return
    try:
        n = int(v)
    except ValueError:
        log("要輸入數字。")
        return
    if not 1 <= n <= 100:
        log("範圍是 1 到 100。")
        return

    try:
        resp = do_set_brightness(card, n)
    except CardError as e:
        log("✗ 設定失敗：%s" % e)
        return

    res = attr(resp, "out", "result")
    if res and res != "kSuccess":
        log("✗ 卡回 result=%s" % res)
    else:
        log("✓ 亮度已設成 %d%%。抬頭看一下屏，確認真的變了。" % n)


def act_reboot(card, log):
    log("")
    log("──────── 重開控制卡 ────────")
    log("卡重開大約要 30〜60 秒，期間屏會黑掉，連線也會斷。")
    log("重開完要選 9 重新連線。")
    if ask("確定要重開嗎？打 yes 才會執行").lower() != "yes":
        log("取消。")
        return
    try:
        do_reboot(card, 3)
        log("✓ 指令送出了，卡會在 3 秒後重開。")
        log("  等屏亮回來（約 30〜60 秒），再選 9 重新連線。")
        log("  **順便觀察：重開後卡會不會自己接著播節目？** 這題很重要，")
        log("  因為店裡跳電之後沒有人會去手動開。")
    except CardError as e:
        log("✗ 失敗：%s" % e)


def act_raw(card, log):
    log("")
    log("進階：直接送一段 <in .../>。廠商如果報給你某個指令名稱，用這個。")
    log("範例：<in method=\"GetWifiInfo\"/>")
    body = ask("輸入 in 標籤內容")
    if not body:
        return
    try:
        log(pretty(card.call("  " + body)))
    except CardError as e:
        log("✗ 失敗：%s" % e)


# ---------------------------------------------------------------- 主程式
HEADER = """
╔══════════════════════════════════════════════════════╗
║   灰度控制卡 現場測試工具  ·  OKAWARI 門頭屏         ║
╚══════════════════════════════════════════════════════╝
"""

MENU = """
╔══════════════════════════════════════════════════════╗
║   灰度控制卡 現場測試工具  ·  OKAWARI 門頭屏         ║
╚══════════════════════════════════════════════════════╝

  1  一鍵全查        （接上卡先按這個，把卡的底細全問出來）
  2  切節目延遲實測  （★ 決定「按續碗→勇者衝出來」做不做得成）
  3  設亮度          （百貨室內一定會用到，練熟它）
  4  抓螢幕截圖      （之後總部遠端巡檢各店就靠這個）
  5  重開控制卡      （順便看：重開後會不會自己接著播）
  6  只讀設備資訊
  7  進階：送任意指令
  9  重新連線 / 換一張卡 / 重新掃描
  0  結束

"""


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.abspath(os.path.join(here, "..", "03_現場存檔"))
    os.makedirs(outdir, exist_ok=True)

    logname = "現場紀錄_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M")
    log = Logger(os.path.join(outdir, logname))

    print(HEADER)
    log("紀錄檔會自動存到：%s" % os.path.join(outdir, logname))
    log("")
    log("先連上控制卡。知道 IP 就直接打；不知道就按 Enter，我幫你掃。")
    log("")

    card = None
    while True:
        if card is None:
            ip = ask("控制卡 IP（不知道就直接按 Enter 讓我掃描）")
            if not ip:
                log("")
                log("──────── 掃描找卡 ────────")
                cards = find_cards(log)
                if not cards:
                    log("")
                    log("  沒找到。可能的原因：")
                    log("   1. 卡跟筆電不同網段（卡常見出廠值是 192.168.0.x 或 192.168.1.x）")
                    log("      → 可以指定網段再掃一次，例如打 192.168.0")
                    log("   2. 網路線沒插好，或轉接頭沒供電")
                    log("   3. 中間的交換器/AP 開了「用戶端隔離」，兩台機器互相看不到")
                    pre = ask("要指定網段掃嗎？（例如 192.168.0，不用就按 Enter）")
                    if pre:
                        cards = find_cards(log, prefix=pre.strip().rstrip("."))
                if not cards:
                    log("還是沒找到。請廠商直接告訴你卡的 IP。")
                    continue
                if len(cards) == 1:
                    ip = cards[0]["ip"]
                    log("  只有一台，直接用 %s" % ip)
                else:
                    log("")
                    for i, c in enumerate(cards):
                        log("   %d) %s  %s  屏 %s×%s"
                            % (i + 1, c["ip"], c["model"] or "", c["w"] or "?", c["h"] or "?"))
                    sel = ask("要連哪一台（打編號）", "1")
                    try:
                        ip = cards[int(sel) - 1]["ip"]
                    except Exception:
                        ip = cards[0]["ip"]
            port = ask("Port", str(DEFAULT_PORT))
            card = HDCard(ip, int(port), log=log)
            try:
                card.connect()
            except Exception as e:
                log("✗ 連不上：%r" % e)
                log("")
                log("  檢查這幾件事：")
                log("   1. 網路線有沒有插好（筆電 ↔ 卡 或 ↔ 同一台交換器）")
                log("   2. 筆電 IP 有沒有跟卡同一個網段")
                log("      （卡是 192.168.1.x，筆電就要設 192.168.1.某個沒人用的號碼）")
                log("   3. 關掉筆電防火牆再試一次")
                log("   4. 用 ping <卡的IP> 確認通不通")
                card = None
                continue

        print(MENU)
        choice = ask("選一個", "1")

        try:
            if choice == "1":
                act_full_scan(card, log)
            elif choice == "2":
                act_latency(card, log)
            elif choice == "3":
                act_brightness(card, log)
            elif choice == "4":
                act_screenshot(card, log, outdir)
            elif choice == "5":
                act_reboot(card, log)
            elif choice == "6":
                log(pretty(q_device_info(card)))
            elif choice == "7":
                act_raw(card, log)
            elif choice == "9":
                card.close()
                card = None
            elif choice == "0":
                break
            else:
                print("沒這個選項。")
        except CardError as e:
            log("✗ 通訊出錯：%s" % e)
            log("  （可能是連線斷了，選 9 重新連線）")
        except KeyboardInterrupt:
            print("\n(中斷)")
        except Exception as e:
            log("✗ 程式例外：%r" % e)

        input("\n按 Enter 回選單...")

    if card:
        card.close()
    log("")
    log("測試結束。紀錄檔：%s" % os.path.join(outdir, logname))
    input("按 Enter 關閉視窗...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中斷。")
