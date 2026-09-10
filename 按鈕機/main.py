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
import sprites
# ★ 2026-09-01 新增。讓筆電在店內網路上直接更新設定檔，不用把機器拆下來接 USB。
#   匯入失敗也不能影響按鈕機本業 —— 沒有它就是回到「只能用 USB 推檔」。
try:
    import cfgserv
except Exception as _e:
    cfgserv = None
    print("cfgserv 匯入失敗，設定接收埠停用：%s" % _e)

# ------------------------------------------------------------ 設定
def load_cfg():
    for path in ("/sd/button_config.json", "/flash/button_config.json",
                 "button_config.json"):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def no_config_screen():
    """找不到設定檔時，在螢幕上講清楚，然後停住。

    ★ 2026-08-24 修無限重開：原本這裡是 `raise SystemExit(...)`。
      SystemExit 不是 Exception 的子類別，所以 boot.py 的 except Exception
      攔不到，它一路往上拋 → MicroPython 軟重開 → boot.py 再跑一次 →
      又拋 → **無限重開迴圈**。實機上看到的就是 `MPY: soft reboot` 一直刷。

      在門市這會很難查：機器不是顯示錯誤，是一直重啟，看起來像電源接觸不良。
      改成畫一面看得懂的畫面然後停住 —— 壞掉的方式要能被看見。
    """
    try:
        Lcd.fillScreen(C_RED)
        Lcd.setTextColor(C_WHITE, C_RED)
        Lcd.setTextSize(2)
        Lcd.setCursor(10, 60)
        Lcd.print("NO CONFIG")
        Lcd.setTextSize(1)
        Lcd.setCursor(10, 110)
        Lcd.print("button_config.json missing")
        Lcd.setCursor(10, 130)
        Lcd.print("run: python 做設定檔.py <store>")
        Lcd.setCursor(10, 150)
        Lcd.print("then: python 傳檔到M5.py")
    except Exception as e:
        print("連錯誤畫面都畫不出來:", e)
    print("找不到 button_config.json —— 停在這裡，不重開")
    while True:              # 停住就好，不要讓例外往上拋造成重開迴圈
        time.sleep(1)


# ------------------------------------------------------------ 畫面
#
# 版面（320×240）：
#   y   0– 36  狀態列 —— 整條換底色當狀態燈，遠看一眼分辨
#   y  36–205  角色區 —— 小飯碗在這裡走來走去、發呆、歡呼、睡覺
#   y 205–240  三顆鍵的標示，對齊機器上三顆實體鍵的位置
#
# 素材只有角色的小圖（後台/_出按鈕機畫面.py 產的），其餘都用 Lcd 畫。
# 這樣狀態色能隨時換，而且一張角色圖才幾百 bytes。
# 實測 drawPng：走路那張 13 ms、最大那張 46 ms，清角色區 21 ms。夠快。

C_BLUE, C_GREEN, C_ORANGE, C_RED = 0x1050A0, 0x108030, 0xC07010, 0xA02020
C_WHITE = 0xFFFFFF
C_BG = 0x141010          # 角色區底色，跟提案頁的 --bg 同一支
C_DIM = 0x6F625B

BAR_H = 36               # 狀態列高 = 字高 30 ＋ 上下各 3 的留白
FLOOR = 205              # 角色區下緣（按鍵列縮小 20%，角色多 7px）
KEY_Y = 212              # 按鍵符號的 y
SPR = "/flash/screen/"

STATE_COLOR = {"connect": C_BLUE, "ready": C_GREEN,
               "playing": C_ORANGE, "error": C_RED, "sleep": 0x201828}
STATE_WORD = {"connect": "WAIT", "ready": "READY",
              "playing": "GO!", "error": "ERROR", "sleep": "CLOSED"}

_bar = None              # 狀態列上次畫的內容
_keys = False            # 按鍵標示畫過沒
_prev_box = None         # 角色上次佔的方框，用來擦掉
_draw_fail = False       # 畫圖失敗只印一次，不要洗版


# 三顆實體按鍵在螢幕座標上的中心。2026-08-24 從實機照片量出來的：
# 原本用 60/160/260，右邊兩顆偏左了幾個像素。
KEY_CX = (64, 165, 266)


def draw_keys(labels):
    """三顆鍵的標示。COMBO 的大圖會蓋過來，所以要能重畫。"""
    global _keys
    Lcd.fillRect(0, FLOOR, 320, 240 - FLOOR, 0x000000)
    Lcd.setTextColor(C_WHITE, 0x000000)
    Lcd.setTextSize(2)
    for i, lab in enumerate(labels):
        # ★ 一定要用 Lcd.textWidth 跟螢幕問，不要自己算。
        #   2026-08-24 就是自己算（用 12px）撞出 "OKAWAF$1000"，
        #   實際 textSize 2 每字 18.3px。
        w = Lcd.textWidth(lab)
        x = KEY_CX[i] - w // 2
        Lcd.setCursor(min(max(2, x), 318 - w), KEY_Y)
        Lcd.print(lab)
        if i:
            sep = (KEY_CX[i - 1] + KEY_CX[i]) // 2
            Lcd.drawLine(sep, FLOOR + 3, sep, 234, C_DIM)
    _keys = True


def draw_bar(state, word, count):
    """狀態列 = 燈點 ＋ 一個詞 ＋ 今日次數。內容沒變就不重畫。

    ★ v2（2026-08-24）：店名拿掉了（它從來不會變，只在開機時顯示兩秒），
      COMBO 也不再疊在角色身上 —— 直接把這裡的詞換成 COMBO 2。
      文字只出現在這一條，角色區從此乾乾淨淨，不會有殘字。
    """
    global _bar
    snap = (state, word, count)
    if snap == _bar:
        return
    _bar = snap
    color = STATE_COLOR.get(state, C_RED)
    Lcd.fillRect(0, 0, 320, BAR_H, color)
    Lcd.setTextColor(C_WHITE, color)
    Lcd.fillCircle(16, BAR_H // 2, 6, C_WHITE)      # 燈點
    Lcd.setTextSize(2)
    # ★ 2026-08-24 修「下緣參差 ＋ 冒出橘色殘影」：字高不能自己算。
    #   textSize 2 的實際 fontHeight 是 30 px（不是直覺的 16），原本
    #   setCursor 到 (BAR_H-16)//2 = 7，字就佔到 y 7–36、比 30 px 的底色條
    #   多凸出 7 列。setTextColor 帶背景色會把那幾列塗成當下的狀態色，
    #   而 fillRect 只重畫 0–29 —— 於是播放中（橘）切回就緒（綠）時，
    #   橘色就永遠留在字底下。跟字寬同一個教訓：一律跟螢幕問，不要自己算。
    top = (BAR_H - Lcd.fontHeight()) // 2
    Lcd.setCursor(32, top)
    Lcd.print(word)
    c = "x%d" % count
    Lcd.setCursor(316 - Lcd.textWidth(c), top)
    Lcd.print(c)
    # 下緣再抹一條，保證這條的底是齊的（也順手清掉舊版留下的那一列殘影）
    Lcd.fillRect(0, BAR_H, 320, 4, C_BG)


# 每張角色圖的實際大小。用來只擦「移開的那一條」，不要整塊重塗。
# 每個「圖名」其實是同一批網格的不同參數：(姿勢, 每格幾像素, 要不要金色, 要不要翻面)
#
# ★ 2026-08-25 不再用 PNG。`drawPng`／`drawImage` 在這台機器上會**靜默失敗** ——
#   不拋錯、回 None，成功失敗長得一模一樣，而且只在「聲音 ＋ Wi-Fi 都在」
#   且**冷開機**的時候才發作。查了三輪，每輪都要人用眼睛回報。
#   素材本來就是一格一格的方塊，PNG 只是中間產物 —— 直接用 fillRect 畫格子，
#   沒有解碼器、沒有圖檔、不吃記憶體，這個失敗模式永久消失。
#   順帶：/flash/screen/*.png 不用再推了，少一個「漏了就沒飯碗」的坑。
SPRITE = {
    "stand":    ("stand",  7, 0, 0),
    "sleep":    ("sleep",  7, 0, 0),
    "drink":    ("hold",   7, 0, 0),
    "walk_a":   ("walk_a", 7, 0, 0),
    "walk_b":   ("walk_b", 7, 0, 0),
    "walk_a_f": ("walk_a", 7, 0, 1),
    "walk_b_f": ("walk_b", 7, 0, 1),
    "cheer":    ("cheer",  7, 0, 0),
    "gold":     ("cheer",  7, 1, 0),
    "gold_big": ("cheer", 10, 1, 0),
    "combo1":   ("cheer",  8, 0, 0),     # 小
    "combo2":   ("cheer",  9, 0, 0),     # 中
    "combo3":   ("cheer", 11, 0, 0),     # 大
}

# 尺寸用算的，不要再手寫 —— 以前 SIZE 表跟實際圖對不上就是爆屏的來源之一
SIZE = {}
for _n, (_p, _s, _g, _f) in SPRITE.items():
    _rows = sprites.POSES[_p]
    SIZE[_n] = (max(len(_r) for _r in _rows) * _s, len(_rows) * _s)


def _blit(name, x, y):
    """把角色一格一格畫上去。同色的連續格會併成一次 fillRect。

    22×15 的網格如果一格一次 fillRect 是 330 次；併過之後大約 80 次。
    實測 drawPng 走路那張是 13 ms，這邊同一個量級。
    """
    pose, s, gold, flip = SPRITE[name]
    rows = sprites.POSES[pose]
    pal = sprites.GOLD if gold else sprites.PAL
    w = max(len(r) for r in rows)
    for sy in range(len(rows)):
        # ★ MicroPython 的 str 沒有 ljust（那是 CPython 才有的），自己補
        row = rows[sy]
        if len(row) < w:
            row = row + "." * (w - len(row))
        yy = y + sy * s
        i = 0
        while i < w:
            ch = row[i]
            j = i + 1
            while j < w and row[j] == ch:
                j += 1
            # ★ 透明的格子也要畫成底色，不能跳過。
            #   以前的 PNG 是連背景一起畫的（產生器有填底色），所以每一幀會
            #   完整蓋掉上一幀。改成格子畫法之後如果跳過 "."，上一幀的殘影就
            #   留在那裡 —— 角色一走動就疊成變形。2026-08-25 Mo 看到的。
            c = pal.get(ch, C_BG)
            # ★ 翻面用鏡射座標算，不要反轉字串 ——
            #   MicroPython 不支援 row[::-1]（只支援 step=1 的切片）。
            Lcd.fillRect(x + ((w - j) if flip else i) * s,
                         yy, (j - i) * s, s, c)
            i = j


# 播放中每張圖畫在哪。★ 2026-08-25 Mo 在母機上看到 COMBO 2／3 爆屏。
#
# 原因：三張圖一律畫在 y = CHAR_Y - 10 = 60，但角色區只到 FLOOR = 205，
# 而 combo2 高 165、combo3 高 225 —— 一個穿過按鍵列，一個直接掉出螢幕
# （combo3 還寬 360，比螢幕的 320 還寬，當初是「故意撐出去」但高度沒跟著算）。
#
# 現在每張各自算好位置，橫向置中、縱向放在 36–205 這 169 px 裡面，
# 全部不外溢。gold_big 原本也超出 5 px，一起修掉。
PLAY_POS = {
    "combo1":   (64, 60),      # 小 192×120 → 佔 60–180
    "combo2":   (52, 53),      # 中 216×135 → 佔 53–188
    "combo3":   (28, 38),      # 大 264×165 → 佔 38–203
    "gold":     (76, 60),      # 168×105 → 佔 60–165
    "gold_big": (40, 55),      # 240×150 → 佔 55–205
    "cheer":    (76, 60),      # 168×105 → 佔 60–165
}


def draw_char(name, x, y):
    """把角色畫在 (x, y)。

    ★ 2026-08-24 修閃爍：原本每幀先 fillRect 整塊角色區再畫圖，那一下塗黑
      就是肉眼看到的閃爍，而且清的範圍（372×232）比角色（154×105）大得多。
      改成「先畫角色、再只擦掉它剛移開的那幾條」—— 角色自己會蓋掉舊位置的
      絕大部分，只有邊緣需要補擦，畫面就不會整片黑一下。
    """
    global _prev_box, _draw_fail
    w, h = SIZE.get(name, (154, 105))
    try:
        _blit(name, x, y)
    except Exception as e:
        if not _draw_fail:
            _draw_fail = True
            print("畫角色失敗（%s）:" % name, repr(e))

    if _prev_box:
        ox, oy, ow, oh = _prev_box
        if ox < x:                                    # 舊的露在左邊
            Lcd.fillRect(ox, oy, min(ow, x - ox), oh, C_BG)
        if ox + ow > x + w:                           # 舊的露在右邊
            Lcd.fillRect(x + w, oy, ox + ow - (x + w), oh, C_BG)
        if oy < y:                                    # 舊的露在上面
            Lcd.fillRect(max(ox, x), oy, min(ow, w), y - oy, C_BG)
        if oy + oh > y + h:                           # 舊的露在下面
            Lcd.fillRect(max(ox, x), y + h, min(ow, w), oy + oh - (y + h), C_BG)
    _prev_box = (x, y, w, h)
    # COMBO 的大圖（combo2 265×165、combo3 360×225）會蓋掉下面那排按鍵標示，
    # 蓋完要補回來，不然標示就永久消失了。2026-08-24 從實機照片發現。
    return y + h > FLOOR


_said = None        # 上次 say() 畫的方框 (x, y, w, h)，用來擦得剛剛好


def clear_say(y=None, h=None):
    """擦掉上次 say() 印的那塊字。

    ★ 2026-08-24 修 zZz 殘影（Mo 在實機上看到的）：
      原本是 `clear_say(CHAR_Y - 26, 30)` —— 寫死擦 30 列。
      但 zZz 是 textSize 3，**實際字高是 45 px**（size 1/2/3 = 15/30/45，
      今天量出來的），字畫在 y=48 佔到 y=92，只擦 30 列等於**下面 19 列
      永遠留著**。跟狀態列那個「字高不能自己算」是同一類 bug。

      而且午睡時角色會走動，zZz 跟著移動，舊位置也沒人擦。
      改成記住上次畫在哪、擦的時候照那個框擦，位置一變就先擦舊的。
    """
    global _said
    if y is not None:                      # 指定範圍的舊用法，留著相容
        Lcd.fillRect(0, y, 320, h or 30, C_BG)
        _said = None
        return
    if _said:
        sx, sy, sw, sh = _said
        Lcd.fillRect(sx, sy, sw, sh, C_BG)
        _said = None


def say(text, x=8, y=BAR_H + 6, size=2, color=0xF7B32B):
    """在角色區印一小段字（COMBO、Zzz 之類）。"""
    global _said
    if not text:
        return
    Lcd.setTextSize(size)
    # ★ 一律跟螢幕問寬高，不要自己算（見 clear_say 的說明）
    w, h = Lcd.textWidth(text), Lcd.fontHeight()
    if _said and (_said[0] != x or _said[1] != y):
        clear_say()                        # 位置移動了，先把舊的擦掉
        Lcd.setTextSize(size)
    Lcd.setTextColor(color, C_BG)
    Lcd.setCursor(x, y)
    Lcd.print(text)
    _said = (x, y, w, h)


def bar_word(state, msg, remain):
    """狀態列要顯示哪個詞。COMBO 和滿額都走這裡，不再疊在角色身上。"""
    if state != "playing":
        return STATE_WORD.get(state, "?")
    if msg.startswith("COMBO"):
        return msg                      # COMBO 1 / COMBO 2 / COMBO 3 / COMBO MAX
    if msg.startswith("滿") or msg.startswith("$"):
        return "GOLD!"          # 滿額 1000 ／ 滿千送百，label 改名不用動這裡
    return "%ds" % int(remain + 0.9)


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
    """連上卡的熱點。連不上也會回傳，讓主迴圈自己重試。

    ★ 2026-08-24 實機踩到：UIFlow2 韌體開機時已經把 STA 介面初始化過了，
      這裡直接 wlan.active(True) 會丟 OSError: Wifi Internal State Error。
      要先 active(False) 把驅動的狀態清乾淨，隔一下再打開才行。
    """
    wlan = network.WLAN(network.STA_IF)

    # ★★ 已經連著就直接回傳，什麼都別動。
    #    2026-08-24 的黑屏就是這裡寫反了：原本 active(False) 寫在
    #    isconnected() 檢查的前面，於是每次呼叫都先把好好的連線打掉再重連，
    #    主迴圈只要有一瞬間讀到沒連線，就會拆 Wi-Fi、清空螢幕、卡 25 秒。
    if wlan.isconnected():
        return wlan

    # 真的沒連線才做介面重置（UIFlow2 開機已初始化過 STA，直接 active(True)
    # 會丟 OSError: Wifi Internal State Error，要先關再開）
    try:
        wlan.active(False)
        time.sleep(0.5)
    except Exception:
        pass
    try:
        wlan.active(True)
        time.sleep(0.3)
    except Exception as e:
        print("Wi-Fi 介面打不開:", e)
        return wlan
    ssid = cfg["wifi"]["ssid"]
    # ★ 這行以前傳 4 個參數，v2 把 draw_bar 改成 3 個之後就一直丟 TypeError，
    #   又被 except 吞掉 —— 結果連線期間整片都是背景色，看起來就是黑屏。
    #   2026-08-24 修。簽名要跟著改，try/except 不能拿來蓋住這種錯。
    try:
        draw_bar("connect", "WAIT", 0)
    except Exception as e:
        print("畫連線畫面失敗:", e)
    try:
        wlan.connect(ssid, cfg["wifi"]["password"])
    except Exception as e:
        print("Wi-Fi connect 失敗:", e)
        return wlan
    t0 = time.time()
    while not wlan.isconnected():
        if time.time() - t0 > 25:
            return wlan   # 連不上也回傳，主迴圈會再試
        time.sleep(0.3)
    return wlan


# ------------------------------------------------------------ 角色
#
# 小飯碗像電子雞一樣待在櫃檯上：待機時走來走去、偶爾停下來發呆，
# 按了就歡呼，COMBO 一段比一段大，打烊就躺下睡。
# Mo 2026-08-24 定的方向。

WALK_L, WALK_R = 20, 150         # 走動範圍（角色寬 154，走到 150 就貼右邊）
CHAR_Y = 70                      # 角色在角色區的 y


class Bowl:
    """角色的動畫狀態。只管畫，不管邏輯。"""

    def __init__(self):
        self.x = 60
        self.dir = 1               # 1 往右、-1 往左
        self.tick_n = 0
        self.doze = 0              # >0 表示正在發呆，數到 0 才繼續走
        self.boom_i = -1           # >=0 表示正在放爆炸
        self.nap_t0 = 0            # 午睡循環的起點

    def frame_idle(self):
        """待機：走走停停。回傳 (圖名, x)。"""
        self.tick_n += 1
        if self.doze > 0:
            self.doze -= 1
            return "stand", self.x
        # 每走一段路就有機會停下來發呆
        if self.tick_n % 90 == 0 and (self.tick_n // 90) % 3 == 0:
            self.doze = 45
            return "stand", self.x
        self.x += self.dir * 2
        if self.x >= WALK_R:
            self.x, self.dir = WALK_R, -1
        elif self.x <= WALK_L:
            self.x, self.dir = WALK_L, 1
        base = "walk_a" if (self.tick_n // 6) % 2 == 0 else "walk_b"
        return (base if self.dir > 0 else base + "_f"), self.x

    def frame_playing(self, msg):
        """播放中：COMBO 大中小三段。回傳 (圖名, x, y)。

        ★ 2026-08-25 Mo：「COMBO 2 跟 COMBO 3 在母機上都會爆屏……
          做大、中、小三個變化就好了。」
          所以 (1) 三段尺寸重算成塞得進角色區、(2) 位置改成查 PLAY_POS
          不再寫死 y、(3) COMBO 3 收尾的爆炸拿掉。
          爆炸的圖還在機器上，要接回來的話尺寸已經縮到 165×165 了。
        """
        self.tick_n += 1
        if msg.startswith("COMBO 3") or msg.startswith("COMBO MAX"):
            return ("combo3",) + PLAY_POS["combo3"]
        if msg.startswith("COMBO 2"):
            return ("combo2",) + PLAY_POS["combo2"]
        if msg.startswith("COMBO 1"):
            return ("combo1",) + PLAY_POS["combo1"]
        # ★ 這裡原本比對的是 "滿額"，但設定檔的 label 早就改成「滿千送百」了，
        #   所以一直比不中 —— 狀態列亮 GOLD!（那邊用的是 startswith("滿")），
        #   角色卻退回普通的歡呼碗，**金色飯碗從來沒出現過**。
        #   跟 bar_word 用同一種比法，label 之後再改名也不會再壞。
        if msg.startswith("滿") or msg.startswith("$"):
            # 金色小飯碗，一大一小交替，像門頭屏的 GOLDEN BOWL
            if (self.tick_n // 8) % 2 == 0:
                return ("gold_big",) + PLAY_POS["gold_big"]
            return ("gold",) + PLAY_POS["gold"]
        return ("cheer",) + PLAY_POS["cheer"]      # 續碗

    # ---------------------------------------------------------- 午睡
    #
    # 門頭屏在播「午後發呆 Zzz」的時候，櫃檯這隻也跟著午睡。
    # 但不是一直躺著 —— 每隔一段時間會爬起來走一走、喝口水，再躺回去。
    # Mo 2026-08-24：「睡午覺的時間大概 15 分鐘左右會起來走一走，先喝個水，然後再起來。」
    #
    # 一輪 = 睡 NAP_SLEEP 秒 → 走 NAP_WALK 秒 → 喝 NAP_DRINK 秒 → 回去睡
    NAP_SLEEP = 15 * 60      # 睡 15 分鐘
    NAP_WALK = 20            # 起來走 20 秒
    NAP_DRINK = 6            # 喝水 6 秒

    def frame_nap(self, now):
        """午睡循環。回傳 (圖名, x, 要不要顯示 Zzz)。"""
        if self.nap_t0 == 0:
            self.nap_t0 = now
        cycle = self.NAP_SLEEP + self.NAP_WALK + self.NAP_DRINK
        t = (now - self.nap_t0) % cycle

        if t < self.NAP_SLEEP:                      # 睡
            return "sleep", self.x, True
        if t < self.NAP_SLEEP + self.NAP_WALK:      # 爬起來走走
            self.tick_n += 1
            self.x += self.dir * 2
            if self.x >= WALK_R:
                self.x, self.dir = WALK_R, -1
            elif self.x <= WALK_L:
                self.x, self.dir = WALK_L, 1
            base = "walk_a" if (self.tick_n // 6) % 2 == 0 else "walk_b"
            return (base if self.dir > 0 else base + "_f"), self.x, False
        return "drink", self.x, False               # 喝口水

    def reset(self):
        self.boom_i = -1



# ------------------------------------------------------------ 聲音
#
# Mo 2026-08-25：滿千送百要有聲音；續碗中獎的時候要有另一種聲音。
#
# ★★ 為什麼不用 M5 的 Speaker（試過，兩次都被它咬）
#
#   M5 的 `Speaker` 走 I2S ＋ DMA ＋ 背景任務。對「放幾聲嗶」來說太重，
#   而且在這台機器上連續害了兩件事：
#
#   1. **喇叭只要開著，跟卡的 socket 就會逾時**，而且那條錯誤路徑有時候
#      直接引爆 C 層的 `abort()` 整台重開（現場看起來像機器自己重啟）。
#      實測：關聲音 75 秒 0 次；開著 75 秒 3 次逾時 2 次重開；
#      把取樣率從 96000 降到 16000 也一樣，所以不是頻寬問題。
#   2. 改成「用完就關」之後 1. 解決了，但出現新症狀：**按一下按鈕之後，
#      `Lcd.drawPng` 就永遠畫不出東西了** —— 小飯碗整個消失，而且不會回來。
#      `drawPng` 不拋錯、回 None，`draw_char` 又用 `except Exception: pass`
#      包住，所以一點徵兆都沒有。
#      `gc.mem_free()` 還有 92 KB —— 但那是 MicroPython 的堆積，
#      `Speaker.begin()` 吃的是 **C 層的堆積**，量不到。begin/end 一輪就把
#      它切碎，PNG 解碼要的連續記憶體再也配置不到。
#
#   驗證過程（記在建置紀錄裡）：只含畫面修改的版本 → 碗正常；
#   再加 `Mic.end()` → 碗正常；加上完整聲音 → 開機時碗在，**按下去就不見**。
#
# ★ 所以改用 GPIO25 直接 PWM 推喇叭
#
#   M5Stack Basic 的喇叭就接在 GPIO25。PWM 出方波直接推它：
#   沒有 I2S、沒有 DMA、沒有背景任務、**不配置任何記憶體**。
#   兩個問題一起消失，而且 `Mic.end()` 也不需要了（不碰 I2S 就不用跟它搶）。
#   音色是方波，顆粒感跟像素飯碗剛好是同一種語言。
#
# ★ 節奏一樣不能用 sleep 排
#   主迴圈一停，角色動畫就卡住，而且卡太久會被看門狗判定當機（建置紀錄第 6 條）。
#   所以整段用絕對時間排好，主迴圈每輪推一格。

# 每個音是 (頻率Hz, 響多久ms, 到下一個音隔多久ms)
SND_DING = [(1760, 120, 140)]                       # 續碗：確認按到了，不搶戲

SND_WIN = [(523, 60, 70), (659, 60, 70), (784, 60, 70),      # 中獎：往上爬
           (1047, 60, 60), (1319, 60, 55), (1568, 60, 50),   # 越爬越急
           (1976, 320, 350)]                                  # 收在長高音

SND_COIN = [(1319, 90, 100), (1976, 450, 500)]      # 滿千送百：金幣音


class Sound:
    """用 GPIO25 的 PWM 發聲。play() 排好整段，tick() 每輪主迴圈推一格。"""

    PIN = 25                 # M5Stack Basic 的喇叭腳

    def __init__(self, vol):
        self.pwm = None
        self.duty = 0
        self.plan = []       # [(什麼時候響, 頻率, 什麼時候停), ...] 絕對時間
        self.i = 0
        self.off_at = 0
        if not vol:
            return           # None／0 = 這台不出聲
        try:
            from machine import Pin, PWM
            self.pwm = PWM(Pin(self.PIN), freq=1000)
            self.pwm.duty_u16(0)
            # 方波 50% 佔空比最大聲。vol 是 0–255，換算成 duty。
            self.duty = int(32768 * min(255, max(0, int(vol))) / 255)
            print("蜂鳴就緒（GPIO%d PWM），音量 %d" % (self.PIN, vol))
        except Exception as e:
            print("開蜂鳴失敗（之後就沒聲音，但機器照跑）:", e)
            self.pwm = None

    def play(self, seq):
        if not self.pwm:
            return
        # ★ 用絕對時間排，不要每格再累加 —— 主迴圈一格 40ms，
        #   相對計時會一路累積誤差，琶音會越拖越慢。
        now = time.ticks_ms()
        t = 0
        self.plan = []
        for f, dur, gap in seq:
            self.plan.append((time.ticks_add(now, t), f,
                              time.ticks_add(now, t + dur)))
            t += gap
        self.i = 0
        self.off_at = 0

    def tick(self):
        if not self.pwm:
            return
        now = time.ticks_ms()
        while self.i < len(self.plan):
            when, f, end = self.plan[self.i]
            if time.ticks_diff(now, when) < 0:
                break                       # 還沒到這個音的時間
            self.i += 1
            try:
                self.pwm.freq(f)
                self.pwm.duty_u16(self.duty)
            except Exception as e:
                print("放聲音失敗:", e)
            self.off_at = end
        if self.off_at and time.ticks_diff(now, self.off_at) >= 0:
            try:
                self.pwm.duty_u16(0)        # 靜音，但 PWM 物件留著不重配置
            except Exception:
                pass
            self.off_at = 0


# ------------------------------------------------------------ 主程式
def run():
    M5.begin()
    Lcd.setRotation(1)

    # ★★ 螢幕不准自己睡。
    #    2026-08-24：Mo 反覆看到黑屏，一開始以為是我用 mpremote 打斷程式造成的，
    #    後來查到 Lcd 有 powerSaveOn/Off，出廠預設會自己暗掉。
    #    這台是整天放在櫃檯上的機器，螢幕暗掉店員會以為機器壞了。
    #    出廠亮度只有 127（滿值 255），櫃檯偏暗，一起調亮。
    try:
        Lcd.powerSaveOff()
    except Exception as e:
        print("關螢幕休眠失敗:", e)
    cfg = load_cfg()
    if not cfg:
        no_config_screen()          # 停在這裡，不會回來（見那支的說明）
    # ★ sound 開關（2026-08-25 加）。預設開；設成 false 就完全不碰喇叭 ——
    #   `Speaker.begin()` 會開一個背景 I2S/DAC 任務一直跑，懷疑它會把跟卡的
    #   socket 餓到逾時。現場真的出問題時這也是最快的緊急關閉。
    # 聲音的音量與開關都在 button_config.json：
    #   "sound": false 完全不出聲；"volume": 0–255
    vol = int(cfg.get("volume", 255)) if cfg.get("sound", True) else None
    if vol is None:
        print("聲音關閉（button_config.json 的 sound = false）")
    store = cfg.get("store", "?")
    try:
        Lcd.setBrightness(int(cfg.get("brightness", 200)))
    except Exception as e:
        print("設亮度失敗:", e)
    keys = cfg.get("keys", {})
    # Mo 2026-08-24：「不要有字，放符號。續碗放 +1，滿額放錢的符號。」
    # +1 跟門頭屏 COMBO 1 畫面上打的字是同一個語言。
    #
    # ★ 符號改成跟著設定檔走，不要寫死在這裡。2026-08-24 Mo 把「+1」移到
    #   右鍵（靠客人那一側）、滿千送百移到中間鍵 —— 寫死的話按鍵和標示
    #   就會對不上，而且對不上這件事在現場很難發現。
    main_label = (keys.get("main") or {}).get("label")
    labels = ("RE",
              (keys.get("main") or {}).get("symbol", "-"),
              (keys.get("promo") or {}).get("symbol", "-"))

    Lcd.fillScreen(C_BG)
    draw_keys(labels)
    # 店名只在開機時露臉兩秒，之後把畫面讓給角色
    Lcd.setTextColor(C_WHITE, C_BG)
    Lcd.setTextSize(2)
    Lcd.setCursor(8, 60)
    Lcd.print("OKAWARI")
    Lcd.setCursor(8, 92)
    Lcd.print(store)
    time.sleep(2)
    Lcd.fillRect(0, BAR_H, 320, FLOOR - BAR_H, C_BG)
    draw_bar("connect", "WAIT", 0)      # 連線期間也要有東西看，不能是黑的
    draw_char("stand", 110, CHAR_Y)

    wlan = wifi_connect(cfg)
    core = hdlink.ButtonCore(cfg, log=print)
    bowl = Bowl()
    snd = Sound(vol)
    # ★ 中獎的定義：今天第一次爬到新的級數（門檻 thresholds 寫在設定檔，
    #   店員不知道，所以那一聲才會是驚喜）。第一碗本來就是 COMBO 1，
    #   不算中獎 —— 所以起點是 1，不是 0。
    best_level = 1
    last_count = 0
    # 午睡的節奏可以在 button_config.json 用 "nap" 覆蓋，不用改程式：
    #   "nap": {"sleep": 900, "walk": 20, "drink": 6}
    nap = cfg.get("nap") or {}
    bowl.NAP_SLEEP = nap.get("sleep", Bowl.NAP_SLEEP)
    bowl.NAP_WALK = nap.get("walk", Bowl.NAP_WALK)
    bowl.NAP_DRINK = nap.get("drink", Bowl.NAP_DRINK)
    print("午睡節奏：睡 %ds → 走 %ds → 喝 %ds"
          % (bowl.NAP_SLEEP, bowl.NAP_WALK, bowl.NAP_DRINK))
    was_playing = False
    just_left_playing = False
    zzz = 0
    next_wifi_try = 0

    # ★ 設定接收埠。開不起來就是 None，主迴圈那邊會跳過。
    cfgsrv = None
    if cfgserv is not None:
        try:
            cfgsrv = cfgserv.Server(log=print)
        except Exception as e:
            print("設定接收埠建立失敗，略過：%s" % e)

    while True:
        M5.update()

        # 設定接收埠：非阻塞，沒人連進來就是微秒等級。
        # 包在 try 裡 —— 這支出事也不能拖垮櫃檯按鈕。
        if cfgsrv is not None:
            try:
                cfgsrv.tick()
            except Exception as e:
                print("設定接收埠出錯，停用：%s" % e)
                cfgsrv = None

        # Wi-Fi 斷了先救 Wi-Fi。
        # 只在真的斷線、而且距離上次嘗試超過 10 秒才重連 ——
        # 不然一次瞬斷就會把畫面整個清掉、卡在重連迴圈裡。
        if not wlan.isconnected() and time.time() >= next_wifi_try:
            next_wifi_try = time.time() + 10
            core.state = "error"
            core.msg = "wifi"
            wlan = wifi_connect(cfg)
            if wlan.isconnected():
                Lcd.fillScreen(C_BG)
                draw_keys(labels)
                core.press("reconnect")

        if BtnA.wasPressed():
            core.press("reconnect")
        if BtnB.wasPressed():
            r = core.press("main")
            if r:
                print("[BtnB]", r)
            # 只有真的觸發成功才放金幣音。回「播放中，再等等」那種
            # 就只給一聲「叮」，不然店員會以為滿千送百放出去了。
            snd.play(SND_COIN if r == main_label else SND_DING)

        if BtnC.wasPressed():
            r = core.press("promo")
            if r:
                print("[BtnC]", r)
            if core.count_today < last_count:      # 跨日歸零了，重新開始算
                best_level = 1
            last_count = core.count_today
            lv = 0
            if r and r.startswith("COMBO"):
                try:
                    lv = int(r.split()[1])
                except Exception:
                    lv = 0
            if lv > best_level:
                best_level = lv
                snd.play(SND_WIN)                  # ★ 中獎
                print("★ 中獎：第 %d 碗爬到 COMBO %d" % (core.count_today, lv))
            else:
                snd.play(SND_DING)

        core.tick()
        snd.tick()

        # 門頭屏關屏了，這隻也跟著睡 —— 店員一眼就知道現在是打烊狀態
        asleep = (core.state == "ready" and not core.screen_on)
        napping = (core.state == "ready" and core.screen_on
                   and core.segment.split("_")[0] == "siesta")
        # ★ split("_")[0]：2026-09-10 整點 LOGO 把 siesta 的窗切成
        #   siesta / siesta_2 / siesta_3…，硬比對字串的話午睡只在第一段成立。
        # ★ 午睡不進狀態列。Mo 2026-08-24：「siesta 可以不顯示嗎」——
        #   狀態列那個詞是給店員看「現在能不能按」的，午睡期間照樣能按，
        #   寫 SIESTA 反而讓人以為機器不能用。午睡純粹由角色表演。
        shown = "sleep" if asleep else core.state

        word = bar_word(shown, core.msg, core.remaining())
        draw_bar(shown, word, core.count_today)

        if core.state == "playing":
            name, x, y = bowl.frame_playing(core.msg)
            if draw_char(name, x, y):
                draw_keys(labels)          # 大圖壓到了，把按鍵符號補回來
            was_playing = True
            just_left_playing = True
        elif asleep:
            if was_playing:
                bowl.reset(); was_playing = False
            draw_char("sleep", bowl.x, CHAR_Y + 8)
            zzz += 1
            if zzz % 40 < 20:
                say("z Z z", bowl.x + 100, CHAR_Y - 22, 3, 0x9FD4FF)
            elif zzz % 40 == 20:
                clear_say()
        elif core.state == "ready" and core.segment.split("_")[0] == "siesta":
            # 門頭屏在播午後發呆 → 這隻也午睡，中途會爬起來走走喝水
            if was_playing:
                bowl.reset(); was_playing = False
            name, x, show_zzz = bowl.frame_nap(time.time())
            draw_char(name, x, CHAR_Y + (8 if name == "sleep" else 0))
            zzz += 1
            if show_zzz and zzz % 40 < 20:
                say("z Z z", x + 100, CHAR_Y - 22, 3, 0x9FD4FF)
            elif zzz % 40 == 20 or not show_zzz:
                clear_say()
        elif core.state == "ready":
            if was_playing:
                bowl.reset(); was_playing = False
            bowl.nap_t0 = 0
            name, x = bowl.frame_idle()
            draw_char(name, x, CHAR_Y)
            if just_left_playing:
                draw_keys(labels)
                just_left_playing = False
        else:
            draw_char("stand", bowl.x, CHAR_Y)

        snd.tick()
        time.sleep(0.04)


run()
