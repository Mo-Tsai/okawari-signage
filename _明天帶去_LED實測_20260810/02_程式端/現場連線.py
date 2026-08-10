#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
現場一鍵連線 —— OKAWARI 門頭屏 / 灰度 C16L 控制卡

專門解決 2026-08-10 演習時踩到的那個坑：
卡的有線網路設成 DHCP，但現場那條線上沒有 DHCP 伺服器，
於是卡永遠拿不到 IP —— 此時掃描、探測、ping 全部必然失敗，
因為它根本沒有位址可以被找到。

這支程式會自己判斷狀況並解決：
  1. 先看筆電有沒有拿到正常 IP（有 → 現場有 DHCP，直接掃）
  2. 沒有的話，聽 UDP 67 有沒有卡在喊 DHCP DISCOVER
  3. 有在喊 → 筆電自己當一台極簡 DHCP 伺服器，配一個位址給它
  4. 連上後把設備資訊全查一遍，存檔

全程唯讀，不會寫入卡上任何設定。
只用 Python 標準函式庫，不需要安裝套件、不需要網路、不需要系統管理員權限。
"""

import binascii
import concurrent.futures
import datetime
import os
import socket
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_test as hd

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


SDK_PORT = 10001
DHCP_LEASE = 86400
OUTDIR = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "03_現場存檔"))


# ---------------------------------------------------------------- 紀錄
os.makedirs(OUTDIR, exist_ok=True)
_logpath = os.path.join(
    OUTDIR, "現場連線_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
_fh = open(_logpath, "a", encoding="utf-8")


def log(m=""):
    print(m, flush=True)
    _fh.write(str(m) + "\n")
    _fh.flush()


log.file_only = lambda m: (_fh.write(str(m) + "\n"), _fh.flush())


def title(t):
    log("")
    log("─" * 60)
    log("  " + t)
    log("─" * 60)


# ---------------------------------------------------------------- 網路現況
def local_ipv4s():
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


def real_ips(ips):
    """排除 169.254（Windows 拿不到 IP 時自己給的）。"""
    return [ip for ip in ips if not ip.startswith("169.254.")]


# ---------------------------------------------------------------- 掃描
def port_open(ip, port, timeout=0.5):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, port)) == 0
    except Exception:
        return False
    finally:
        s.close()


def scan(prefix, port=SDK_PORT):
    log("  掃描 %s.1 ~ %s.254 的 port %d ..." % (prefix, prefix, port))
    hits = []
    targets = ["%s.%d" % (prefix, i) for i in range(1, 255)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as pool:
        futs = {pool.submit(port_open, ip, port): ip for ip in targets}
        for f in concurrent.futures.as_completed(futs):
            if f.result():
                hits.append(futs[f])
    return sorted(hits, key=lambda x: int(x.rsplit(".", 1)[1]))


def verify(ip):
    c = hd.HDCard(ip, SDK_PORT, timeout=4.0, log=lambda m: None)
    try:
        c.connect()
        xml = hd.q_device_info(c)
        return {
            "ip": ip,
            "model": hd.attr(xml, "device", "model"),
            "id": hd.attr(xml, "device", "id"),
            "w": hd.attr(xml, "screen", "width"),
            "h": hd.attr(xml, "screen", "height"),
        }
    except Exception:
        return None
    finally:
        c.close()


# ---------------------------------------------------------------- DHCP
def sniff_dhcp(seconds=25):
    """聽卡有沒有在喊 DHCP DISCOVER。回傳 {mac: 廠商識別}。

    目的位址是 255.255.255.255，Windows 的 IP 層一定收，
    所以不需要跟卡同網段、也不需要系統管理員權限。
    """
    seen = {}
    stop = threading.Event()

    def run():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", 67))
        except Exception as e:
            log("  （UDP 67 綁不起來：%r）" % e)
            return
        s.settimeout(0.5)
        while not stop.is_set():
            try:
                data, _ = s.recvfrom(2048)
            except socket.timeout:
                continue
            except Exception:
                break
            if len(data) < 240 or data[0] != 1:
                continue
            mac = data[28:34]
            vendor = ""
            i = 240
            while i < len(data):
                c = data[i]
                if c == 255:
                    break
                if c == 0:
                    i += 1
                    continue
                ln = data[i + 1]
                if c == 60:
                    vendor = data[i + 2:i + 2 + ln].decode("utf-8", "replace")
                i += 2 + ln
            key = binascii.hexlify(mac, ":").decode().upper()
            if key not in seen:
                seen[key] = vendor
                log("  ★ 聽到 DHCP DISCOVER：MAC %s（%s）" % (key, vendor or "無廠商識別"))
        s.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    for i in range(seconds):
        time.sleep(1)
        if seen and i >= 12:
            break
    stop.set()
    time.sleep(0.6)
    return seen


def dhcp_option(code, payload):
    return bytes([code, len(payload)]) + payload


def build_reply(req, msg_type, offer_ip, server_ip, netmask):
    pkt = bytes([2, 1, 6, 0]) + req[4:8] + b"\x00\x00" + req[10:12]
    pkt += socket.inet_aton("0.0.0.0")
    pkt += socket.inet_aton(offer_ip)
    pkt += socket.inet_aton("0.0.0.0") * 2
    pkt += req[28:44] + b"\x00" * 192
    pkt += b"\x63\x82\x53\x63"
    pkt += dhcp_option(53, bytes([msg_type]))
    pkt += dhcp_option(54, socket.inet_aton(server_ip))
    pkt += dhcp_option(51, struct.pack("!I", DHCP_LEASE))
    pkt += dhcp_option(1, socket.inet_aton(netmask))
    pkt += b"\xff"
    return pkt + b"\x00" * max(0, 300 - len(pkt))


def serve_dhcp(target_mac, server_ip, offer_ip, netmask, timeout=90):
    """只服務指定 MAC、只從指定介面送。不會去干擾現場其它網路。"""
    mac = bytes.fromhex(target_mac.replace(":", ""))
    done = threading.Event()
    stop = threading.Event()

    send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    send.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    send.bind((server_ip, 0))

    def run():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            s.bind(("0.0.0.0", 67))
        except Exception as e:
            log("  ✗ UDP 67 綁不起來：%r" % e)
            done.set()
            return
        s.settimeout(0.5)
        while not stop.is_set():
            try:
                data, _ = s.recvfrom(2048)
            except socket.timeout:
                continue
            except Exception:
                break
            if len(data) < 240 or data[0] != 1 or data[28:34] != mac:
                continue
            mtype = 0
            i = 240
            while i < len(data):
                c = data[i]
                if c == 255:
                    break
                if c == 0:
                    i += 1
                    continue
                ln = data[i + 1]
                if c == 53:
                    mtype = data[i + 2]
                    break
                i += 2 + ln
            if mtype == 1:
                log("  ← DISCOVER，回 OFFER %s" % offer_ip)
                send.sendto(build_reply(data, 2, offer_ip, server_ip, netmask),
                            ("255.255.255.255", 68))
            elif mtype == 3:
                log("  ← REQUEST，回 ACK %s（遮罩 %s）" % (offer_ip, netmask))
                send.sendto(build_reply(data, 5, offer_ip, server_ip, netmask),
                            ("255.255.255.255", 68))
                done.set()
        s.close()

    threading.Thread(target=run, daemon=True).start()
    ok = done.wait(timeout)
    # 卡可能會再送一次 REQUEST 續約，多留一下再收攤
    time.sleep(3)
    stop.set()
    send.close()
    return ok


# ---------------------------------------------------------------- 主流程
def connect_and_query(ip):
    title("連上 %s，開始查（唯讀）" % ip)
    card = hd.HDCard(ip, SDK_PORT, timeout=10.0, log=log)
    try:
        card.connect()
    except Exception as e:
        log("✗ 握手失敗：%r" % e)
        return None
    try:
        hd.act_full_scan(card, log)
    except Exception as e:
        log("全查中途出錯：%r" % e)
    return card


def main():
    log("=" * 60)
    log("  OKAWARI 門頭屏 · 現場一鍵連線")
    log("  %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 60)
    log("紀錄檔：%s" % _logpath)

    title("第 1 步：看筆電自己的網路狀態")
    ips = local_ipv4s()
    log("  筆電 IPv4：%s" % (ips or "（一個都沒有）"))
    good = real_ips(ips)
    apipa = [ip for ip in ips if ip.startswith("169.254.")]
    for ip in good:
        log("    %-16s 這個介面有 DHCP" % ip)
    for ip in apipa:
        log("    %-16s 這個介面沒拿到 IP（169.254 = 線上沒有 DHCP）" % ip)

    card_ip = None

    # --- 第 2 步：先掃能掃的網段（含 169.254，卡可能已經有租約）---
    title("第 2 步：掃描找卡")
    for ip in good + apipa:
        prefix = ip.rsplit(".", 1)[0]
        for hit in scan(prefix):
            if hit == ip:
                continue
            info = verify(hit)
            if info:
                log("  ★ 找到卡：%s  %s  屏 %s×%s"
                    % (info["ip"], info["model"], info["w"], info["h"]))
                card_ip = info["ip"]
                break
        if card_ip:
            break
    if not card_ip:
        log("  掃不到。卡可能還沒有 IP，或交換器開了用戶端隔離。")

    # --- 第 3 步：卡沒有 IP 的話，聽它有沒有在喊 ---
    if not card_ip:
        title("第 3 步：聽卡有沒有在要 IP")
        log("  （卡設成 DHCP 卻沒人回應時，會每 10 秒廣播一次 DISCOVER）")
        found = sniff_dhcp(25)

        if not found:
            log("")
            log("  沒聽到任何 DHCP DISCOVER。依序檢查：")
            log("   1. 網路線有沒有確實插在「卡」的網路孔上（不是屏、不是電源）")
            log("   2. 卡有沒有通電（看卡上的電源燈）")
            log("   3. 網路孔的 link 燈會不會亮（不亮 = 換線或換孔）")
            log("   4. 轉接頭有沒有被電腦認到")
            log("")
            log("  也可以改走卡自己的 Wi-Fi 熱點：")
            log("     SSID  C16L-D24-000A2   密碼  88888888   卡在 192.168.6.1")
            log("     筆電連上那個熱點之後，重跑這支程式。")
            return

        mac = list(found.keys())[0]
        # 一定要用「沒拿到 IP 的那個介面」當伺服器，卡就掛在那條線上
        eth_ip = apipa[0] if apipa else (good[0] if good else None)
        if not eth_ip:
            log("  ✗ 筆電連 169.254 的位址都沒有，網路卡狀態不對。")
            return

        a, b, c, _ = eth_ip.split(".")
        offer = "%s.%s.%s.100" % (a, b, c)
        netmask = "255.255.0.0" if eth_ip.startswith("169.254.") else "255.255.255.0"
        if offer == eth_ip:
            offer = "%s.%s.%s.101" % (a, b, c)

        title("第 4 步：筆電自己當 DHCP 伺服器，發一個 IP 給卡")
        log("  只服務 MAC %s，只從 %s 這個介面送。" % (mac, eth_ip))
        log("  要配給卡的位址：%s（遮罩 %s）" % (offer, netmask))
        if not serve_dhcp(mac, eth_ip, offer, netmask):
            log("  ✗ 90 秒內沒完成交握。")
            return

        log("")
        log("  等卡把網路介面設好 ...")
        for i in range(12):
            time.sleep(2)
            if subprocess.call("ping -n 1 -w 1000 %s" % offer,
                               shell=True,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL) == 0:
                log("  ✓ ping %s 通了" % offer)
                card_ip = offer
                break
            log("  ... 還不通（第 %d 次）" % (i + 1))
        if not card_ip:
            log("  ✗ 配下去了但 ping 不通。")
            return

    card = connect_and_query(card_ip)
    if not card:
        return

    title("這趟要記下來的數字")
    try:
        dev = hd.q_device_info(card)
        log("  卡的 IP        ：%s" % card_ip)
        log("  卡型號         ：%s" % hd.attr(dev, "device", "model"))
        log("  設備 ID        ：%s" % hd.attr(dev, "device", "id"))
        log("  ★ 屏幕尺寸     ：%s × %s px   ← 畫布規格看這個"
            % (hd.attr(dev, "screen", "width"), hd.attr(dev, "screen", "height")))
        log("  韌體 app       ：%s" % hd.attr(dev, "version", "app"))
        log("  硬體           ：%s" % hd.attr(dev, "version", "hardware"))
    except Exception as e:
        log("  （讀不到：%r）" % e)
    card.close()

    log("")
    log("完成。整包 03_現場存檔 帶回來給我就好。")
    log("紀錄檔：%s" % _logpath)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n已中斷。")
    finally:
        try:
            input("\n按 Enter 關閉視窗...")
        except Exception:
            pass
        _fh.close()
