# -*- coding: utf-8 -*-
"""
OKAWARI 續碗按鈕機 · M5Stack Basic 主程式（UIFlow2 / MicroPython）

檔案佈局（全部放 M5Stack 的 /flash）：
  main.py             ← 這支，開機自動執行
  hdlink.py           ← 協議與狀態機（與桌上測試共用）
  button_config.json  ← 這台機器屬於哪家店（用 做設定檔.py 產生）

按鍵：
  BtnA（左）  = 重新連線
  BtnB（中）  = 續碗（依設定檔：dice 或 combo）
  BtnC（右）  = 滿千送百（設定檔沒填就沒作用）

畫面：整片底色就是狀態燈 ——
  藍 = 連線中     綠 = 就緒（可以按）
  橘 = 播放中（大字倒數）    紅 = 有問題（按左鍵）
螢幕字型先用內建英文字（LCD 內建字型沒有中文；中文/像素動畫版之後再加）。

註：實機到手後 Lcd/Btn 的 API 名稱若有出入（UIFlow2 版本差異），
    只需要改這支的畫面段，hdlink.py 不用動。
"""

import time
import json
import network

import M5
from M5 import Lcd, BtnA, BtnB, BtnC

import hdlink

# ------------------------------------------------------------ 設定
def load_cfg():
    for path in ("/sd/button_config.json", "/flash/button_config.json",
                 "button_config.json"):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    raise SystemExit("找不到 button_config.json")


# ------------------------------------------------------------ 畫面
C_BLUE, C_GREEN, C_ORANGE, C_RED = 0x1050A0, 0x108030, 0xC07010, 0xA02020
C_WHITE = 0xFFFFFF

_last = None

def draw(state, msg, remain, count, store):
    global _last
    snap = (state, msg, int(remain), count)
    if snap == _last:
        return
    _last = snap
    color = {"connect": C_BLUE, "ready": C_GREEN,
             "playing": C_ORANGE, "error": C_RED}.get(state, C_RED)
    Lcd.fillScreen(color)
    Lcd.setTextColor(C_WHITE, color)

    Lcd.setTextSize(2)
    Lcd.setCursor(8, 6)
    Lcd.print("OKAWARI  %s" % store)

    Lcd.setTextSize(4)
    Lcd.setCursor(8, 70)
    if state == "connect":
        Lcd.print("WAIT...")
    elif state == "ready":
        Lcd.print("READY")
    elif state == "playing":
        Lcd.print("%ds  GO!" % int(remain + 0.9))
    else:
        Lcd.print("ERROR")

    Lcd.setTextSize(2)
    Lcd.setCursor(8, 130)
    Lcd.print("today: %d" % count)

    # 底部按鍵提示（對齊三顆實體鍵的位置）
    Lcd.setTextSize(2)
    Lcd.setCursor(14, 218);  Lcd.print("RE")
    Lcd.setCursor(130, 218); Lcd.print("GO")
    Lcd.setCursor(242, 218); Lcd.print("$$")


def ascii_label(msg):
    """core 的訊息轉成 LCD 內建字型印得出來的版本。"""
    table = {"中獎！": "HIT!", "沒中": "MISS", "就緒": "", "連線中": ""}
    if msg in table:
        return table[msg]
    if msg.startswith("COMBO"):
        return msg
    return ""


# ------------------------------------------------------------ Wi-Fi
def wifi_connect(cfg):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan
    ssid = cfg["wifi"]["ssid"]
    draw("connect", "wifi", 0, 0, cfg.get("store", ""))
    wlan.connect(ssid, cfg["wifi"]["password"])
    t0 = time.time()
    while not wlan.isconnected():
        if time.time() - t0 > 25:
            return wlan   # 連不上也回傳，主迴圈會再試
        time.sleep(0.3)
    return wlan


# ------------------------------------------------------------ 主程式
def run():
    M5.begin()
    Lcd.setRotation(1)
    cfg = load_cfg()
    store = cfg.get("store", "?")

    wlan = wifi_connect(cfg)
    core = hdlink.ButtonCore(cfg, log=print)

    while True:
        M5.update()

        # Wi-Fi 斷了先救 Wi-Fi
        if not wlan.isconnected():
            core.state = "error"
            core.msg = "wifi"
            wlan = wifi_connect(cfg)
            if wlan.isconnected():
                core.press("reconnect")

        if BtnA.wasPressed():
            core.press("reconnect")
        if BtnB.wasPressed():
            r = core.press("main")
            if r:
                print("[BtnB]", r)
        if BtnC.wasPressed():
            r = core.press("promo")
            if r:
                print("[BtnC]", r)

        core.tick()
        draw(core.state, core.msg, core.remaining(), core.count_today, store)
        if core.state == "playing":
            label = ascii_label(core.msg)
            if label:
                Lcd.setTextSize(3)
                Lcd.setCursor(8, 170)
                Lcd.print(label)
        time.sleep(0.03)


run()
