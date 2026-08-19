#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 四段常駐畫面

業主 2026-08-09 需求：畫面按時段換。
兩個角色：
    人物     person_sprite.py    戴紅帽的小孩，從業主 IG 的像素圖抽出來
    小飯碗   ricebowl_sprite.py  長出手腳的牛丼

    開店 11:00-11:30   布簾打開，睡醒伸懶腰，沿飯粒路徑走到一碗飯
    中午 11:30-14:00   端著熱騰騰的飯慢慢走過，冒 3 個蒸氣符號
    午後 14:00-17:30   躺在食物上睡覺，冒 ZZZ，偶爾翻身
    晚間 17:30-22:30   放下公事包，坐下拿起飯碗

排播時段不寫在這裡 —— 寫在 stores.json 的 when，最後變成節目的
playControl，由卡自己按時鐘播。這裡只負責畫。
"""

import math
import random

from PIL import ImageDraw

import artwork
import person_sprite
import ricebowl_sprite

# 主角是可以換的。stores.json 的 params.character 決定編出來是誰主演，
# 分鏡完全一樣 —— 業主要比較兩個角色時，比的才是角色本身，不是分鏡。
CHARACTERS = {
    "person":   person_sprite,      # 人物（IG 那個戴紅帽的小孩）
    "ricebowl": ricebowl_sprite,    # 小飯碗（長出手腳的牛丼）
}
SP = person_sprite           # 預設，_ch() 會覆寫
PROPS = person_sprite        # 碗、蒸氣這些道具不屬於任何角色，兩邊共用


def _ch(p):
    return CHARACTERS.get(str((p or {}).get("character", "person")), person_sprite)


def _blit(d, spr, ox, oy, s, pal=None, flip=False):
    """把 sprite 畫上去。s 是每格幾個像素。"""
    pal = pal or person_sprite.PAL
    w = max(len(r) for r in spr)
    for sy, row in enumerate(spr):
        for sx, ch in enumerate(row):
            if ch == "." or ch not in pal:
                continue
            x = (w - 1 - sx) if flip else sx
            x0, y0 = ox + x * s, oy + sy * s
            d.rectangle([x0, y0, x0 + s - 1, y0 + s - 1], fill=pal[ch])


def _blit_prop(d, spr, ox, oy, s, _pal=None):
    """畫道具。道具的顏色不跟著角色換。"""
    _blit(d, spr, ox, oy, s, PROPS.PAL)


def _scale(rows, canvas_h, p):
    """角色要多大。跟舊版共用 hero_scale，門市三塊屏才會是同一個比例。"""
    return max(1, round(canvas_h * p["hero_scale"] / rows))


def _walk_frame(i, SP=None):
    """走路兩幀交替。每 6 格換一次腳，跟模擬器的節奏一樣。"""
    SP = SP or person_sprite
    return SP.POSES["walk_a"] if (i // 6) % 2 == 0 else SP.POSES["walk_b"]


# ---------------------------------------------------------------- 中午
def render_noon(cols, rows, p=None):
    """今天也要好好吃飯：端著熱騰騰的飯慢慢走過，冒 3 個蒸氣符號。

    走完整條畫面，頭尾都在畫面外，所以循環接得起來。
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = _ch(q)
    n = artwork.frame_count(q, "noon")

    pose = SP.POSES["hold"]
    ph = len(pose)
    s = _scale(ph, rows, q)
    sw = max(len(r) for r in pose) * s

    bowl_w = len(PROPS.BOWL[0]) * s
    span = cols + sw * 2                      # 從左邊外面走到右邊外面

    out = []
    for i in range(n):
        im = sc.gradient(phase=0.10 + 0.04 * (i / n))
        d = ImageDraw.Draw(im)

        x = int(-sw + span * (i / n))
        y = rows - ph * s - max(1, s)

        # 端著飯走。走路的換腳交給 walk 兩幀，端東西的手勢用 hold，
        # 兩者交替就有「邊走邊端」的感覺，而且不必知道角色內部怎麼拆的。
        spr = pose if (i // 6) % 2 == 0 else _walk_frame(i, SP)
        _blit(d, spr, x, y, s, SP.PAL)

        # 碗端在身體前方
        bx = x + sw - s
        by = y + int(ph * 0.62) * s
        _blit_prop(d, PROPS.BOWL, bx, by, s)

        # 蒸氣：三道，各自相位不同，往上飄
        for k in range(3):
            t = (i * 0.5 + k * 4) % 12
            sy = by - int(t) * s - s
            sx = bx + (k + 1) * 2 * s
            if sy > 0:
                d.rectangle([sx, sy, sx + s - 1, sy + s - 1],
                            fill=PROPS.PAL["W"])
        out.append(im)
    return out


# ---------------------------------------------------------------- 午後
def render_siesta(cols, rows, p=None):
    """午後發呆 Zzz：靠著一碗飯打盹，冒 ZZZ，偶爾翻身。

    這一段刻意最安靜 —— 沒客人的時段，畫面不該一直動。
    但「不動」跟「壞掉」在屏上長得很像，所以還是要有呼吸感：
    緩慢的上下起伏 + 持續飄的 ZZZ，讓人一眼知道它還活著。
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = _ch(q)
    n = artwork.frame_count(q, "siesta")

    pose = SP.POSES["sleep"]
    ph = len(pose)
    s = _scale(ph, rows, q)
    sw = max(len(r) for r in pose) * s
    bw, bh = len(PROPS.BOWL[0]) * s, len(PROPS.BOWL) * s

    x = (cols - sw) // 2
    base_y = rows - ph * s - max(1, s)

    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.06 + 0.03 * t)
        d = ImageDraw.Draw(im)

        # 呼吸：很慢的一上一下，一輪呼吸大約四秒
        breathe = -s if int(t * n / max(1, int(q["siesta_fps"] * 2))) % 2 else 0
        y = base_y + breathe

        # 翻身：整段中間翻一次，翻的時候左右翻面
        flip = 0.44 < t < 0.56

        # 那碗飯擺在角色旁邊，不要疊在身上 ——
        # 疊上去的話碗會蓋住臉，遠看像長了紅鬍子。
        bx = x - bw - s if not flip else x + sw + s
        _blit_prop(d, PROPS.BOWL, bx, rows - bh - max(1, s), s)

        _blit(d, pose, x, y, s, SP.PAL, flip=flip)

        # ZZZ：三個往右上飄，越飄越高。用 2×2 的塊，一個像素太小看不到。
        for k in range(3):
            u = ((i * 0.6) + k * 7) % 21 / 21.0
            zx = x + sw + int(u * 14) * s
            zy = y - int(u * 9) * s - s
            if zy > 0 and zx + 2 * s < cols:
                d.rectangle([zx, zy, zx + 2 * s - 1, zy + 2 * s - 1],
                            fill=PROPS.PAL["W"])
        out.append(im)
    return out


# ---------------------------------------------------------------- 開店
def render_opening(cols, rows, p=None):
    """開店畫面：布簾打開 → 睡醒伸懶腰 → 沿飯粒路徑走 → 抵達一碗飯。

    分四拍。像 8-bit 遊戲開場，所以節奏要有停頓，不能一路平推。
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = _ch(q)
    n = artwork.frame_count(q, "opening")

    pose = SP.POSES["walk_a"]
    ph = len(pose)
    s = _scale(ph, rows, q)
    sw = max(len(r) for r in pose) * s
    gy = rows - ph * s - max(1, s)

    # 終點那碗飯放在右邊 82% 處
    bowl_x = int(cols * 0.82)
    bowl_y = rows - len(PROPS.BOWL) * s - max(1, s)

    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.08 + 0.05 * t)
        d = ImageDraw.Draw(im)

        # 目標那碗飯，全程都在
        _blit_prop(d, PROPS.BOWL, bowl_x, bowl_y, s)

        # 飯粒路徑：一顆一顆亮起來，像遊戲關卡的路標
        walk_from, walk_to = 0.30, 0.88
        for k in range(12):
            gxp = int(cols * 0.10 + k * (bowl_x - cols * 0.10) / 12)
            lit = t > walk_from + (walk_to - walk_from) * (k / 12) - 0.04
            d.rectangle([gxp, gy + ph * s - s, gxp + s - 1, gy + ph * s - 1],
                        fill=PROPS.PAL["W"] if lit else PROPS.PAL["B"])

        if t < 0.18:
            # 第一拍：布簾往兩邊拉開
            k = t / 0.18
            w = int(cols / 2 * (1 - k))
            d.rectangle([0, 0, w, rows], fill=PROPS.PAL["K"])
            d.rectangle([cols - w, 0, cols, rows], fill=PROPS.PAL["K"])
        elif t < 0.30:
            # 第二拍：站在左邊伸懶腰（手舉起來，上下晃一下）
            k = (t - 0.18) / 0.12
            bob = -s if int(k * 6) % 2 else 0
            _blit(d, SP.POSES["cheer"], int(cols * 0.08), gy + bob, s, SP.PAL)
        elif t < 0.88:
            # 第三拍：走過去
            k = (t - 0.30) / 0.58
            x = int(cols * 0.08 + (bowl_x - sw - cols * 0.08) * k)
            _blit(d, _walk_frame(i, SP), x, gy, s, SP.PAL)
        else:
            # 第四拍：抵達，舉手歡呼
            k = (t - 0.88) / 0.12
            bob = -s if int(k * 8) % 2 else 0
            _blit(d, SP.POSES["cheer"], bowl_x - sw, gy + bob, s, SP.PAL)

        out.append(im)
    return out


# ---------------------------------------------------------------- 晚間
# 2026-08-18 客戶問：「上班族小角色」是主角換造型，還是另外一個角色？
# 答案是換造型，不是新角色。理由兩個：
#   1. 小飯碗是「被吃的那一方」。讓它端起飯碗吃飯，世界觀會打架 —— 碗吃碗。
#   2. 彩蛋二（RICE POWER）已經定好這組關係：累的是人，端飯過來的是小飯碗。
#      晚間段講的是同一件事（累了 → 吃飯 → 恢復），角色分工要一致。
# 所以造型做成 prop 疊層，character 換誰主演都成立，不必再畫第三隻角色。

BRIEFCASE = [
    "..KKKK..",
    ".K....K.",                    # 提把要挖空，實心的話遠看是一塊磚
    "KKKKKKKK",
    "KBBBBBBK",
    "KBWWWWBK",                    # 鎖扣
    "KBBBBBBK",
    "KKKKKKKK",
]

# 上班族造型。2026-08-19 業主：「沒有看出來有差異。」
#
# 原本只加了一條 2 格寬的領帶和一個小公事包 —— 在 960×120 上，
# 角色只有 85 px 高，那條領帶是 6 px 寬的紅點，等於沒有。
#
# 真正在遠處讀得出來的只有兩件事：**大面積的顏色** 和 **輪廓**。
# 所以改成三管齊下：
#   1. 綠上衣整片換成西裝深藍 —— 這是最大的一塊，一眼就知道換了衣服
#   2. 白襯衫領口 + 紅領帶，畫成看得見的大小
#   3. 公事包放大，加提把和鎖扣
SUIT = (44, 52, 78)                # 西裝深藍

COLLAR = [
    "WW.KK.WW",
    "WWWKKWWW",
    ".WWRRWW.",
    "..WRRW..",
    "...RR...",
    "...RR...",
    "...RR...",
    "....R...",
]


def _suit_pal(SP):
    """把角色身上最大一塊布料換成西裝色。

    人物的 G 是綠上衣，換掉就是換衣服。
    小飯碗身上沒有布料（整個身體就是一個碗），所以不動它的配色 ——
    它靠領口和公事包表達，換碗的顏色只會讓人以為換了一隻角色。
    """
    if "G" not in SP.PAL:
        return SP.PAL
    return {**SP.PAL, "G": SUIT}


def _tie(d, x, y, w, h, s, SP):
    """襯衫領口 + 領帶。畫在胸口中線，不去碰角色內部是怎麼拆的。

    兩個角色都給 —— 小飯碗雖然沒有胸口，但領口那兩塊白配紅領帶
    壓在碗身上，讀起來就是「這碗飯上班去了」，比只掛個公事包清楚得多。
    """
    cs = max(1, int(s * 0.9))
    cw = len(COLLAR[0]) * cs
    cx = x + w // 2 - cw // 2
    cy = y + int(h * (0.46 if SP is person_sprite else 0.40))
    _blit(d, COLLAR, cx, cy, cs, PROPS.PAL)


def _spark(d, cx, cy, r, s, colour):
    """精神恢復的那一下。放射狀短線，不是光圈 ——
    光圈在屏上會變成頭頂一個橢圓，看起來像光環不像「亮起來」。"""
    for k in range(6):
        a = (k / 6.0) * math.tau + 0.26
        x0 = cx + math.cos(a) * r * 0.55
        y0 = cy + math.sin(a) * r * 0.40
        x1 = cx + math.cos(a) * r
        y1 = cy + math.sin(a) * r * 0.72
        d.line([x0, y0, x1, y1], fill=colour, width=max(1, s // 2))


def _text_at(im, txt, x, y, size, colour):
    """在指定位置畫字。artwork.Screen.draw_text 只會置中，
    但這塊屏是 8:1，字擠在中間會壓到角色，要能自己挑位置。"""
    m = artwork.text_mask(txt, size)
    if m is None:
        return 0
    # 先壓一層深色影子。字直接畫在紅橙漸層上，在 LED 上會糊成一片 ——
    # 描一格深色邊，遠看才切得開。
    dark = artwork.Image.new("RGB", m.size, PROPS.PAL["K"])
    for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)):
        im.paste(dark, (int(x) + dx, int(y) + dy), m)
    im.paste(artwork.Image.new("RGB", m.size, colour), (int(x), int(y)), m)
    return m.width


def render_evening(cols, rows, p=None):
    """今天辛苦了，吃飯吧：拖著腳步進場 → 放下公事包 → 坐下 → 看到飯精神恢復。

    2026-08-18 改版。原本只有「放下包、坐下」，現在多了最後一拍：
    看到飯的那一瞬間整個人亮起來。**那一拍才是這段的重點** ——
    前面走得越累，最後那一下越有效，所以走路刻意放慢、肩膀刻意壓低。

    四拍：
        0.00-0.38  拖著腳步走進來（換腳放慢、肩膀垂一格、包拎在手上）
        0.38-0.50  停下，包落地（帶一下彈跳，才有重量）
        0.50-0.64  坐下（有一沉）
        0.64-1.00  飯端上來 → 精神恢復（挺起來、冒光、蒸氣變旺）
    """
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = _ch(q)
    n = artwork.frame_count(q, "evening")

    stand = SP.POSES["walk_a"]
    ph = len(stand)
    s = _scale(ph, rows, q)
    sw = max(len(r) for r in stand) * s
    sh = ph * s

    floor = rows - max(1, s)          # 地面線，所有東西都站在這上面
    gy = floor - sh

    sit = SP.POSES["sit"]
    sit_h = len(sit) * s

    bw, bh = len(PROPS.BOWL[0]) * s, len(PROPS.BOWL) * s
    bs = max(1, int(s * 1.5))     # 公事包比角色比例大一點，遠看才認得出
    cw, chh = len(BRIEFCASE[0]) * bs, len(BRIEFCASE) * bs

    suit = _suit_pal(SP)
    mid = int(cols * 0.46)
    bag_x = mid + sw - s              # 包落地之後的位置，就在人的右手邊

    T_WALK, T_DROP, T_SIT = 0.38, 0.50, 0.64
    SIT_DROP = 5 * s                  # 坐下比站著矮多少

    # 客戶原文的那句台詞。屏是 8:1，角色只佔中間一小塊，
    # 右邊那片空的正好給這句話 —— 不放的話畫面有八成是空的。
    line_size = max(9, round(rows * 0.26))
    line_x = mid + sw + int(cols * 0.06)
    line_y = int(rows * 0.30)

    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.04 + 0.03 * t)
        d = ImageDraw.Draw(im)

        if t < T_WALK:
            # 第一拍：拖著腳步。換腳從 6 格拉長到 10 格，走起來就明顯比中午沉。
            k = t / T_WALK
            x = int(-sw + (mid + sw) * k)
            spr = SP.POSES["walk_a"] if (i // 10) % 2 == 0 else SP.POSES["walk_b"]
            sag = s                                   # 肩膀垂下來一格
            _blit(d, spr, x, gy + sag, s, suit)
            _tie(d, x, gy + sag, sw, sh, s, SP)
            sway = s if (i // 10) % 2 == 0 else 0     # 包隨步伐晃
            # 手的高度是照角色比例算的，但包是放大過的 —— 小飯碗矮胖，
            # 不夾一下的話包會穿過地面。夾在地面上，看起來就是「快提不動了」。
            by = min(gy + sag + int(sh * 0.60) + sway, floor - chh)
            _blit_prop(d, BRIEFCASE, x + sw - s, by, bs)

        elif t < T_DROP:
            # 第二拍：停下來，手一鬆，包掉到地上。
            k = (t - T_WALK) / (T_DROP - T_WALK)
            _blit(d, SP.POSES["stand"], mid, gy + s, s, suit)
            _tie(d, mid, gy + s, sw, sh, s, SP)

            y0 = min(gy + s + int(sh * 0.60), floor - chh)
            y1 = floor - chh
            u = min(1.0, k * k * 1.25)                # 加速度，不是等速落下
            by = int(y0 + (y1 - y0) * u)
            if u > 0.88:                              # 落地彈一下才有重量
                by -= s if int(k * 14) % 2 else 0
            _blit_prop(d, BRIEFCASE, bag_x, by, bs)

        else:
            # 包已經在地上了，後面兩拍它都不動
            _blit_prop(d, BRIEFCASE, bag_x, floor - chh, bs)

            if t < T_SIT:
                # 第三拍：坐下去的那一沉。
                k = (t - T_DROP) / (T_SIT - T_DROP)
                # 沉下去 5 格。腳會被地面切掉 —— 那正是「坐下」的樣子，
                # 站著跟坐著如果一樣高，這一拍等於沒演。
                settle = SIT_DROP - int(max(0.0, 1.0 - k * 2.5) * 3) * s
                _blit(d, sit, mid, floor - sit_h + settle, s, suit)
                _tie(d, mid, floor - sit_h + settle, sw, sit_h, s, SP)
            else:
                # 第四拍：飯端上來 → 精神恢復。
                k = (t - T_SIT) / (1.0 - T_SIT)
                woke = k > 0.34                       # 「看到飯」的那一格

                # 挺起來 + 開心的上下晃
                perk = -s if woke else 0
                bob = -s if (woke and (i // 5) % 2 == 0) else 0
                sy = floor - sit_h + SIT_DROP + perk + bob
                _blit(d, sit, mid, sy, s, suit)
                _tie(d, mid, sy, sw, sit_h, s, SP)

                # 碗從下面端上來
                rise = int(max(0.0, 1.0 - k * 3.2) * 6) * s
                bx = mid - bw
                by = floor - bh - int(sit_h * 0.30) + rise
                _blit_prop(d, PROPS.BOWL, bx, by, s)

                # 精神恢復的那一下：頭上炸開一圈光。只閃 4 格，多了會變成裝飾。
                if 0.34 < k < 0.48:
                    _spark(d, mid + sw // 2, sy + s, int(sh * 0.52), s,
                           PROPS.PAL["W"])

                # 蒸氣。醒過來之後從兩道加到三道，畫面自己會變熱鬧。
                for kk in range(3 if woke else 2):
                    tt = (i * 0.45 + kk * 4) % 11
                    yy = by - int(tt) * s - s
                    xx = bx + (kk + 1) * 2 * s
                    if yy > 0:
                        d.rectangle([xx, yy, xx + s - 1, yy + s - 1],
                                    fill=PROPS.PAL["W"])

                # 台詞。2026-08-19 業主怕中文在屏上糊掉 —— 這個顧慮是對的：
                # 這句有「辛」「苦」「飯」三個筆畫密的字，在 120 px 高的屏上
                # 只能給到 31 px，P4 的點距遠看會糊成一團。
                # 所以預設不放字，要放的話在後台填 evening_text。
                line = str(q.get("evening_text") or "").strip()
                if woke and line:
                    _text_at(im, line, line_x, line_y, line_size, artwork.WHT)
        out.append(im)
    return out


# ---------------------------------------------------------------- 續飯 COMBO
# 2026-08-18 客戶新增。客人每按一次續飯按鈕，小飯碗震一下、大一圈，
# 第三次爆成巨碗。三段是**接續**的 —— combo2 的起始大小＝combo1 的結束大小，
# 所以三段連著播才對得起來，單獨播 combo2 會看起來莫名其妙。
#
# ★ 能不能真的做成「累積」，取決於卡的 SwitchProgram 來回要幾秒。
#   量測腳本：_測_SwitchProgram延遲.py。超過 1.5 秒的話退路是三段併成一段。
#
# ★ 客戶寫「膨脹成超大飯碗，幾乎占滿整個橫向畫面」—— 這個字面上做不到。
#   屏是 960×120（8:1），等比放大到頂天，寬度也只有畫面的兩成，
#   硬拉寬會變成一條香腸。所以改成**撐破上下緣**：碗放大到超過畫面高度、
#   被上下切掉，只看得到碗的中段。看起來是「大到裝不下」，比塞滿橫向更兇。

_STEP = {"combo1": (0, 1), "combo2": (1, 2), "combo3": (2, 2)}
#         段名       (起始, 結束)  加在基準格數上。三段接得起來靠這張表。


def _draw_bowl(d, SP, cols, rows, s, cx=0.5, dx=0, dy=0, flip=False, clip=False):
    """把角色畫在畫面上。

    clip=True 是「大到裝不下」用的：改成垂直置中，讓它自然被上下切掉。
    平常是站在地面上。
    """
    spr = SP.POSES["stand"]
    w = max(len(r) for r in spr) * s
    h = len(spr) * s
    x = int(cols * cx) - w // 2 + dx
    y = (rows - h) // 2 + dy if clip else rows - h - 1 + dy
    _blit(d, spr, x, y, s, SP.PAL, flip=flip)
    return x, y, w, h


def _shake(i, amp, period=3):
    """震動偏移。用 i 算，不用亂數 —— 卡是靠 md5 認檔案的，
    同樣參數每次要編出一模一樣的影片，不然每次發佈都被當成新檔。"""
    return amp if (i // period) % 2 == 0 else -amp


def _confetti(d, cols, rows, seed, u, cx, count=90):
    """紙花、星星、飯粒。u 是 0→1 的擴散進度。

    亂數固定種子，同一段每次編出來完全一樣（理由同 _shake）。
    顆粒給到 2〜3 px —— 1 px 在 P4 屏上遠看是雜訊，不是紙花。
    """
    if u <= 0:
        return
    rnd = random.Random(seed)
    pal = PROPS.PAL
    palette = [pal["Y"], pal["W"], pal["R"], pal["B"], pal["W"]]
    ox, oy = int(cols * cx), rows // 2
    for _ in range(count):
        a = rnd.uniform(0, math.tau)
        v = rnd.uniform(0.30, 1.0)
        sz = rnd.choice([2, 2, 3])
        c = rnd.choice(palette)
        x = int(ox + math.cos(a) * v * cols * 0.46 * u)
        y = int(oy + math.sin(a) * v * rows * 1.30 * u + (u * u) * rows * 0.60)
        if -sz < x < cols and -sz < y < rows:
            d.rectangle([x, y, x + sz, y + sz], fill=c)


def _render_combo(cols, rows, p, key):
    """三段共用的骨架。差別只在震幾下、長多大、噴不噴。"""
    sc = artwork.Screen(cols, rows, p)
    q = sc.p
    SP = _ch(q)
    n = artwork.frame_count(q, key)

    spr = SP.POSES["stand"]
    base = _scale(len(spr), rows, q)      # 跟四段常駐同一個基準，接得起來
    g0, g1 = _STEP[key]
    s0, s1 = base + g0, base + g1
    giant = int(base * 2.6)               # 撐破上下緣

    txt_size = max(9, round(rows * 0.30))
    out = []
    for i in range(n):
        t = i / n
        im = sc.gradient(phase=0.12 + 0.05 * t)
        d = ImageDraw.Draw(im)

        if key == "combo1":
            # 還搞不清楚發生什麼事 → 震一下 → 左右看看自己 → 悄悄長大一點
            if t < 0.22:
                _draw_bowl(d, SP, cols, rows, s0)
            elif t < 0.40:
                _draw_bowl(d, SP, cols, rows, s0, dx=_shake(i, s0))
            elif t < 0.62:
                _draw_bowl(d, SP, cols, rows, s0, flip=(i // 7) % 2 == 0)
            else:
                x, y, w, h = _draw_bowl(d, SP, cols, rows, s1)
                _text_at(im, "+1", x + w + s1 * 2, y, txt_size, artwork.YEL)

        elif key == "combo2":
            # 連震兩下，幅度更大 → 被震得彈起來 → 落地又大一圈
            if t < 0.30:
                _draw_bowl(d, SP, cols, rows, s0, dx=_shake(i, s0 * 2, period=2))
            elif t < 0.58:
                k = (t - 0.30) / 0.28
                hop = -int(math.sin(k * math.pi) * rows * 0.30)
                x, y, w, h = _draw_bowl(d, SP, cols, rows, s0, dy=hop)
                _text_at(im, "!?", x + w + s0, y, txt_size, artwork.WHT)
            else:
                x, y, w, h = _draw_bowl(d, SP, cols, rows, s1)
                _text_at(im, "+2", x + w + s1 * 2, y, txt_size, artwork.YEL)

        else:
            # 震！震！震！→ 砰！撐破畫面 → 噴發 → 開心跳晃 → 噗——縮回
            # 巨碗擺在畫面 64% 處，左邊那片空的留給字。
            # 8:1 的屏一定要橫向分工，全部擠中間的話兩側等於沒用到。
            CX = 0.64
            if t < 0.26:
                amp = int(s0 * (1 + 4 * t))               # 越震越大力
                _draw_bowl(d, SP, cols, rows, s0, cx=CX,
                           dx=_shake(i, amp, period=2),
                           dy=_shake(i + 1, max(1, amp // 2), period=2))
            elif t < 0.35:
                # 砰！一口氣撐開。這幾格是整段的重心，不要拉長。
                k = (t - 0.26) / 0.09
                s_now = max(1, int(s0 + (giant - s0) * k))
                _draw_bowl(d, SP, cols, rows, s_now, cx=CX, clip=k > 0.55)
                _confetti(d, cols, rows, 7, k * 0.55, CX)
            elif t < 0.78:
                k = (t - 0.35) / 0.43
                bob = -int(base * 1.2) if (i // 5) % 2 == 0 else 0
                _draw_bowl(d, SP, cols, rows, giant, cx=CX, clip=True,
                           dx=_shake(i, base, period=6), dy=bob)
                _confetti(d, cols, rows, 7, min(1.0, 0.55 + k * 1.1), CX)
                _text_at(im, "okawari combo!", int(cols * 0.05),
                         int(rows * 0.30), txt_size, artwork.YEL)
            else:
                # 洩氣。縮回去比脹大慢三倍，才有「噗——」的感覺。
                k = (t - 0.78) / 0.22
                s_now = max(1, int(giant - (giant - s1) * k))
                _draw_bowl(d, SP, cols, rows, s_now, cx=CX,
                           clip=s_now * len(spr) > rows)
        out.append(im)
    return out


def render_combo1(cols, rows, p=None):
    """續飯第一次：震一下，悄悄長大一點。+1"""
    return _render_combo(cols, rows, p, "combo1")


def render_combo2(cols, rows, p=None):
    """續飯第二次：連震兩下，被震得彈起來，落地又大一圈。!? +2"""
    return _render_combo(cols, rows, p, "combo2")


def render_combo3(cols, rows, p=None):
    """續飯第三次：全畫面震動，砰地撐破畫面，噴發，然後洩氣縮回。"""
    return _render_combo(cols, rows, p, "combo3")


RENDERERS = {
    "opening": render_opening,
    "noon": render_noon,
    "siesta": render_siesta,
    "evening": render_evening,
    "combo1": render_combo1,
    "combo2": render_combo2,
    "combo3": render_combo3,
}
