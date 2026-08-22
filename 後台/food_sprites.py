#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 配角食物角色

業主 2026-08-21 的角色名單：
    溫泉蛋君、烏龍麵哥、布丁妹妹、牛丼、咖哩飯、炸雞、巴斯克

牛丼就是既有的小飯碗（ricebowl_sprite），不重畫 —— 它已經是主角，
再畫一隻一樣的東西只會讓人以為有兩個牛丼。這裡畫的是另外六隻。

★ 為什麼六隻長得像同一家人

  身體寬度一律 18 欄，跟人物、小飯碗一樣。手腳用同一組公式接上去，
  走路節奏、腳的位置、手伸出來的高度全部共用。這樣做的結果是：
  換角色的時候分鏡完全不用動，而且六隻站在一起看得出是同一組設定。

  差別只在「身體那一塊」—— 也就是食物本身。認角色靠剪影跟顏色，
  不靠細節：P4 屏遠看三公尺，睫毛畫了也是白畫。

★ 眼睛用 E / e 兩個字元標

  E 是上半眼、e 是下半眼。醒著的時候兩個都塗描邊色；睡著的時候
  E 塗回身體色、只留 e，眼睛就變成一條線。這樣睡姿不用另外畫一張。

★ 手腳的膚色 S 固定是那支淡黃（跟人物、小飯碗同一支）

  食物長手腳本來就有點荒謬，全組統一反而變成一個設定。
  每隻各配一個顏色的話，看起來只是六張不相干的貼圖。
"""

import ricebowl_sprite

# 全組共用的顏色。改這裡會六隻一起變。
K = ( 26,  23,  33)     # 描邊、眼睛、嘴
S = (252, 241, 146)     # 手腳（跟人物、小飯碗同一支）
W = (255, 253, 246)     # 純白高光

BODY_W = 18             # 身體寬度。六隻都一樣，手腳公式才共用得起來


# ---------------------------------------------------------------- 身體
# 每一隻＝一塊 18 欄寬的身體 ＋ 一組顏色。
# 眼睛用 E/e 標，睡著時上半眼會被塗回身體色。

ONSEN = [                          # 溫泉蛋君：蛋黃當帽子的白蛋
    "......KKKKKK......",
    "....KKYYYYYYKK....",
    "...KYYYYYYYYYYK...",
    "..KYYYYYYYYYYYYK..",
    ".KOYYYYYYYYYYYYOK.",
    ".KOOOOOOOOOOOOOOK.",
    "KOOOEEOOOOOOEEOOOK",
    "KOOOeeOOOOOOeeOOOK",
    "KOOOOOOOOOOOOOOOOK",
    "KOOOOOOOKKOOOOOOOK",
    ".KOOOOOOOOOOOOOOK.",
    "..KOOOOOOOOOOOOK..",
    "...KKKKKKKKKKKK...",
]
ONSEN_PAL = {"K": K, "S": S, "W": W,
             "O": (255, 253, 246),      # 蛋白
             "Y": (247, 179,  43),      # 蛋黃
             }
# 蛋白白、蛋黃品牌黃，兩個都亮。中間不加第三個顏色，
# 靠 K 描邊分界就夠 —— LED 上顏色越少越乾淨。

UDON = [                           # 烏龍麵哥：藍碗盛白麵
    "....NN...NN.NN....",
    "..NNNNN.NNNNNNN...",
    ".NNNNGNNNNNGNNNN..",
    ".NNNNNNNNNNNNNNNN.",
    ".KKKKKKKKKKKKKKKK.",
    "KLLLLLLLLLLLLLLLLK",
    "KBBBBBBBBBBBBBBBBK",
    "KBBEEBBBBBBBBEEBBK",
    "KBBeeBBBBBBBBeeBBK",
    "KBBBBBBBKKBBBBBBBK",
    ".KBBBBBBBBBBBBBBK.",
    "..KBBBBBBBBBBBBK..",
    "...KKKKKKKKKKKK...",
]
UDON_PAL = {"K": K, "S": S, "W": W,
            "B": ( 46,  76, 118),       # 碗身：深藍
            "L": (108, 150, 196),       # 碗緣：淺藍
            "N": (250, 244, 224),       # 麵
            "G": (110, 170,  92),       # 蔥花
            }
# 背景是紅橙漸變，藍是它的補色 —— 六隻裡就這一隻用冷色。
# 一群角色走過去有一隻是藍的，隊伍才不會糊成一條橘色。

PURIN = [                          # 布丁妹妹：梯形＋櫻桃
    "......KKKK........",
    "......KRRK........",
    "......KKKKKK......",
    ".....KCCCCCCK.....",
    "....KCCCCCCCCK....",
    "...KCCPCCCCPCCK...",
    "...KPPPPPPPPPPK...",
    "..KPPPPPPPPPPPPK..",
    "..KPPEEPPPPEEPPK..",
    "..KPPeePPPPeePPK..",
    ".KPPPPPPPPPPPPPPK.",
    ".KPPPPPPKKPPPPPPK.",
    "KPPPPPPPPPPPPPPPPK",
    "KPPPPPPPPPPPPPPPPK",
    ".KKKKKKKKKKKKKKKK.",
]
PURIN_PAL = {"K": K, "S": S, "W": W,
             "P": (250, 224, 130),      # 布丁
             "C": (150,  95,  50),      # 焦糖
             "R": (226,  58,  46),      # 櫻桃（OKAWARI 紅）
             }
# 上窄下寬是這隻唯一的辨識點。眼睛放在下半段的寬處 ——
# 放上面會擠進斜邊裡，遠看變成兩個雜點。

CURRY = [                          # 咖哩飯：又扁又寬的一盤
    "....KKKKKKKKKK....",
    "..KKWWWWWCCCCCKK..",
    ".KWWWWWWWCCCRCCCK.",
    ".KWWWWWWWCCCCCCCK.",
    ".KKKKKKKKKKKKKKKK.",
    "KDDDDDDDDDDDDDDDDK",
    "KDDEEDDDDDDDDEEDDK",
    "KDDeeDDDDDDDDeeDDK",
    "KDDDDDDDKKDDDDDDDK",
    ".KDDDDDDDDDDDDDDK.",
    "..KKKKKKKKKKKKKK..",
]
CURRY_PAL = {"K": K, "S": S, "W": (255, 253, 246),
             "C": (150,  95,  50),      # 咖哩
             "R": (226,  58,  46),      # 福神漬
             "D": (214, 218, 228),      # 盤子
             }
# 只有 11 列，是六隻裡最矮的。這是故意的 ——
# 都一樣高的話，隊伍走過去只是六個色塊在平移。

KARAAGE = [                        # 炸雞：骨頭朝上的雞腿
    "......KKKKKK......",
    "....KKOOKKOOKK....",          # 骨頭端的關節縫。只留一列 ——
    "....KOOOOOOOOK....",          # 縫超過一列，兩邊會被看成兔耳朵
    ".....KOOOOOOK.....",          # 骨幹
    "....KKFFFFFFKK....",
    "...KFHHFFFFFFFK...",          # 高光偏左上，不要對稱 ——
    "..KFFFFFFFFFFFFK..",          # 對稱會被當成第二對眼睛
    ".KFFEEFFFFFFEEFFK.",
    ".KFFeeFFFFFFeeFFK.",
    ".KFFFFFFFFFFFFFFK.",
    ".KFFFFFFKKFFFFFFK.",
    "..KFFFFFFFFFFFFK..",
    "...KKFFFFFFFFKK...",
    ".....KKKKKKKK.....",
]
KARAAGE_PAL = {"K": K, "S": S, "W": W,
               "F": (198, 124,  44),    # 炸衣
               "H": (247, 179,  43),    # 高光
               "O": (250, 244, 224),    # 骨頭
               }
# 炸雞的顏色最接近背景的橘，六隻裡最容易糊掉的就是它。
# 描邊一格都不能省，高光也要留 —— 那兩點是它唯一的立體感。

BASQUE = [                         # 巴斯克：燒焦的頂＋皺褶烤紙
    "....KKKKKKKKKK....",
    "..KKTTTTTTTTTTKK..",
    ".KTTTTTTTTTTTTTTK.",
    "KTTTTTTTTTTTTTTTTK",
    "KPPPPPPPPPPPPPPPPK",
    "KPPEEPPPPPPPPEEPPK",
    "KPPeePPPPPPPPeePPK",
    "KPPPPPPPKKPPPPPPPK",
    "KPPPPPPPPPPPPPPPPK",
    "KAPAPAPAPAPAPAPAPK",
    "KAPAPAPAPAPAPAPAPK",
    ".KKKKKKKKKKKKKKKK.",
]
BASQUE_PAL = {"K": K, "S": S, "W": W,
              "T": ( 92,  52,  30),     # 燒焦的頂
              "P": (246, 222, 168),     # 起司
              "A": (196, 168, 120),     # 烤紙的暗面
              }
# 燒焦那塊是深色，壓在紅橙背景上很沉 —— 頂邊不用另外描，
# 深色自己就是邊。


# ---------------------------------------------------------------- 手腳
# 手從身體兩側伸出去、腳接在正下方，位置按身體高度算，
# 不是每隻各填一組座標。六隻的動作因此天生同步。

def _arms(h, w, kind):
    """(dx, dy, 色) 清單。dx 可以是負的 —— 左手伸到身體外面。

    a 是肩膀高度，取身體的 55%。再高會長在臉上，再低像從腳邊長出來。
    """
    a = max(1, int(h * 0.55))
    r, l = w, -1                                  # 右手／左手的第一欄
    if kind == "down":
        p = [(r, a), (r + 1, a), (r, a + 1), (r + 1, a + 1), (r, a + 2)]
        q = [(l, a), (l - 1, a), (l, a + 1), (l - 1, a + 1), (l, a + 2)]
    elif kind == "swing":
        p = [(r, a - 1), (r + 1, a - 1), (r, a), (r + 1, a)]
        q = [(l, a + 1), (l - 1, a + 1), (l, a + 2), (l - 1, a + 2)]
    elif kind == "up":                            # 歡呼：兩手斜斜舉高
        p = [(r, a - 1), (r + 1, a - 2), (r + 2, a - 3), (r + 2, a - 4)]
        q = [(l, a - 1), (l - 1, a - 2), (l - 2, a - 3), (l - 2, a - 4)]
    else:                                          # hold：端東西，兩手往前
        p = [(r, a + 1), (r + 1, a + 1), (r, a + 2)]
        q = [(l, a + 1), (l - 1, a + 1), (l, a + 2)]
    return [(x, y, "S") for x, y in p + q if y >= 0]


# 腳沿用小飯碗那組 —— 都是 18 欄寬，位置對得起來，
# 而且所有角色的腳步是同一個節奏。
LEGS_STAND  = ricebowl_sprite.LEGS_STAND
LEGS_WALK_A = ricebowl_sprite.LEGS_WALK_A
LEGS_WALK_B = ricebowl_sprite.LEGS_WALK_B
LEGS_HOP    = ricebowl_sprite.LEGS_HOP
LEGS_TUCK   = ricebowl_sprite.LEGS_TUCK


def _eyes(body, fill, asleep=False):
    """E / e 換成真的顏色字元。asleep 時上半眼塗回身體色，只留一條線。"""
    top = fill if asleep else "K"
    return [r.replace("E", top).replace("e", "K") for r in body]


def _compose(body, arm, legs):
    """身體 ＋ 手 ＋ 腳。手會伸到負座標，所以整張往右墊再組。"""
    pad = max(0, -min([dx for dx, _, _ in arm] or [0]))
    w = len(body[0]) + pad
    rows = [list(("." * pad) + r) for r in body]

    for dx, dy, ch in arm:
        x = dx + pad
        while dy >= len(rows):
            rows.append(list("." * w))
        for r in rows:
            if len(r) <= x:
                r.extend("." * (x + 1 - len(r)))
        rows[dy][x] = ch

    w = max(len(r) for r in rows)
    for r in rows:
        r.extend("." * (w - len(r)))
    for lr in legs:
        rows.append(list((("." * pad) + lr).ljust(w, ".")))

    n = max(len(r) for r in rows)
    return ["".join(r).ljust(n, ".") for r in rows]


class Char(object):
    """一隻角色。介面跟 person_sprite / ricebowl_sprite 一樣：PAL ＋ POSES。

    分鏡只認 .PAL 和 .POSES，所以模組跟這個類別可以混著用。
    """

    def __init__(self, key, name, desc, body, pal):
        bad = [i for i, r in enumerate(body) if len(r) != len(body[0])]
        if bad:
            raise ValueError("%s 的第 %s 列寬度不一致" % (name, bad))

        self.key, self.name, self.desc = key, name, desc
        self.PAL = dict(pal)
        self.BODY = body

        fill = self._fill(body)
        awake = _eyes(body, fill)
        asleep = _eyes(body, fill, True)
        h, w = len(body), len(body[0])

        self.POSES = {
            "stand":  _compose(awake, _arms(h, w, "down"),  LEGS_STAND),
            "walk_a": _compose(awake, _arms(h, w, "swing"), LEGS_WALK_A),
            "walk_b": _compose(awake, _arms(h, w, "down"),  LEGS_WALK_B),
            "cheer":  _compose(awake, _arms(h, w, "up"),    LEGS_HOP),
            "hold":   _compose(awake, _arms(h, w, "hold"),  LEGS_WALK_A),
            "sleep":  _compose(asleep, _arms(h, w, "down"), LEGS_TUCK),
        }
        self.POSES["sit"] = self.POSES["sleep"]

    @staticmethod
    def _fill(body):
        """身體色＝眼睛左邊那一格。睡著時拿它把上半眼塗掉。"""
        for r in body:
            i = r.find("E")
            if i > 0:
                return r[i - 1]
        raise ValueError("身體裡沒有標眼睛（E/e）")

    def walk_frame(self, i, every=6):
        return self.POSES["walk_a" if (i // every) % 2 == 0 else "walk_b"]


ONSEN_CH = Char("onsen", "溫泉蛋君",
                "蛋黃當帽子的白蛋。全組最亮的一隻，站在暗處也看得到。",
                ONSEN, ONSEN_PAL)
UDON_CH = Char("udon", "烏龍麵哥",
               "藍碗盛白麵。六隻裡唯一的冷色，隊伍靠它斷開。",
               UDON, UDON_PAL)
PURIN_CH = Char("purin", "布丁妹妹",
                "上窄下寬的梯形加一顆櫻桃。剪影最好認的一隻。",
                PURIN, PURIN_PAL)
CURRY_CH = Char("curry", "咖哩飯",
                "又扁又寬的一盤。故意做得比別人矮，隊伍才有高低。",
                CURRY, CURRY_PAL)
KARAAGE_CH = Char("karaage", "炸雞",
                  "骨頭朝上的雞腿。顏色最接近背景，描邊和高光都不能省。",
                  KARAAGE, KARAAGE_PAL)
BASQUE_CH = Char("basque", "巴斯克",
                 "燒焦的頂加皺褶烤紙。深色的頂自己就是描邊。",
                 BASQUE, BASQUE_PAL)

# 牛丼＝小飯碗本人，不重畫。名單上有它，但它已經是主角了。
GYUDON_CH = ricebowl_sprite

FOODS = {
    "onsen":   ONSEN_CH,
    "udon":    UDON_CH,
    "purin":   PURIN_CH,
    "curry":   CURRY_CH,
    "karaage": KARAAGE_CH,
    "basque":  BASQUE_CH,
}

# 買一送一那段主角會停下來比對愛心的三個。順序＝畫面上從左到右遇到的順序。
# 業主 2026-08-18 原文就是「途中遇到烏龍麵、炸雞、布丁」，照抄。
PASSERS = [UDON_CH, KARAAGE_CH, PURIN_CH]

# 剩下三隻站右半邊看熱鬧，不參與「not you...」那三拍。
#
# 為什麼不讓六隻都停一次：那一段只有 8 秒，停三次每拍 2.7 秒剛好讀得完；
# 停六次每拍剩 1.3 秒，字還沒看清楚就換下一隻了。笑點是靠停頓撐的。
# 但六隻都畫了不上場也浪費 —— 而且原本主角只走過左半邊，
# 右邊六成是空的橘色。站在那裡剛好把畫面填滿，還多一層「在人群裡找」的意思。
CROWD = [ONSEN_CH, CURRY_CH, BASQUE_CH]
