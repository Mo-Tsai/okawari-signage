#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI 門頭屏 · 內容編譯器 v3（影片）

把「一份設計」編譯成「每家店各自畫布的節目」。
美術本體在 artwork.py，這裡負責尺寸適配、編碼成影片、送檔、建節目。

為什麼是影片（2026-08-10 一路試出來的結論）：
  圖片序列   duration 最小 1（0.1 秒），但卡實測只跑得動約 6 fps，
             而且停留時間短時會不斷銷毀重建區域資源 —— 畫面會出現一條
             垂直線掃過去、動作會頓。灰度文件自己就寫了
             「effect 標籤的停留時間盡量長，避免不斷銷毀區域資源」。
  動畫 GIF   卡不支援，只顯示第一幀（用紅→藍交替的探針 GIF 實測確認）。
  影片       卡原生支援，25 fps 沒問題。這是唯一能到位的路。

兩種店：
  主畫布店   自己就是設計基準（台南 960×120、台中 1040×120）
  鏡像店     某個主畫布等比縮小之後的一個視窗。測試卡 160×40 就是台南的 1/3，
             縮完寬度 320、卡只有 160，所以取中間那段。
"""

import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
sys.path.insert(0, os.path.abspath(os.path.join(
    HERE, "..", "_明天帶去_LED實測_20260810", "02_程式端")))
sys.path.insert(0, HERE)

import hd_test as hd          # noqa: E402
import hd_send as hs          # noqa: E402
import artwork                # noqa: E402
import schedule as sched      # noqa: E402


# ---------------------------------------------------------------- ffmpeg
def find_ffmpeg():
    """PATH 找不到就去 winget 的安裝位置找。

    winget 裝完之後，這個 shell 的 PATH 還是舊的，要重開視窗才會更新，
    所以直接去它的安裝目錄撈。
    """
    p = shutil.which("ffmpeg")
    if p:
        return p
    for pat in (
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\bin\ffmpeg.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe"),
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ):
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    return None


def align16(n):
    """進位到 16 的倍數。"""
    return ((int(n) + 15) // 16) * 16


def encode_video(frames, path, fps, log=print, scale=2):
    """把畫面序列丟給 ffmpeg 編成 H.264 影片。

    用 rawvideo 從 stdin 餵進去，不落地成一堆 PNG。
    baseline profile + yuv420p 是相容性最好的組合，嵌入式播放器通常只吃這個。

    ★ 編碼尺寸要放大再對齊 16。2026-08-10 在 C16L 上實測出來的：

        160×40   卡收得下、認得是 video，但播出來全黑
        160×48   一樣全黑（高度對齊 16 了還是不行）
        320×80   正常播放 ★

    所以光「對齊 16」不夠，解碼器對太小的畫面也不吃。
    做法是先整數放大（預設 2 倍）再對齊 16，卡會用 aspectRatio="false"
    把它拉回區域大小，幾何上等於沒變。放大用最近鄰，保住像素風的硬邊。
    """
    exe = find_ffmpeg()
    if not exe:
        raise RuntimeError(
            "找不到 ffmpeg。用 winget install Gyan.FFmpeg 安裝，"
            "或把 ffmpeg.exe 放進專案資料夾。")

    w0, h0 = frames[0].size
    w, h = align16(w0 * scale), align16(h0 * scale)
    if (w, h) != (w0, h0):
        frames = [im.resize((w, h), Image.NEAREST) for im in frames]
        log("    編碼尺寸 %d×%d → %d×%d（放大 %d 倍再對齊 16，卡會縮回來）"
            % (w0, h0, w, h, scale))
    cmd = [
        exe, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-",
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0",
        "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
        "-movflags", "+faststart", path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for im in frames:
        proc.stdin.write(im.convert("RGB").tobytes())
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace")
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg 編碼失敗：%s" % err.strip()[:400])
    return path


# ---------------------------------------------------------------- 尺寸適配
def merged_params(store, data):
    """全域參數 → 該店覆寫。都沒設就用 artwork 的預設。"""
    return artwork.params({**(data.get("params") or {}),
                           **(store.get("params") or {})})


def resolve_canvas(store, data):
    """回傳 (主畫布寬, 主畫布高, 輸出寬, 輸出高, 對齊方式)。"""
    c = store.get("canvas") or {}
    ow, oh = c.get("width"), c.get("height")
    if not (ow and oh):
        raise ValueError("%s 還沒有畫布尺寸" % store["id"])

    m = store.get("mirror") or {}
    ref = m.get("of")
    if not ref:
        return ow, oh, ow, oh, "center"

    master = next((s for s in data["stores"] if s["id"] == ref), None)
    if not master:
        raise ValueError("%s 的 mirror.of 指向不存在的店：%s" % (store["id"], ref))
    mc = master.get("canvas") or {}
    mw, mh = mc.get("width"), mc.get("height")
    if not (mw and mh):
        raise ValueError("主畫布 %s 還沒有尺寸" % ref)
    return mw, mh, ow, oh, m.get("align", "center")


def fit(im, mw, mh, ow, oh, align="center"):
    """把主畫布的一幀等比縮到目標高度，再依對齊方式裁成目標寬度。"""
    if (mw, mh) == (ow, oh):
        return im
    ratio = oh / mh
    sw = max(1, round(mw * ratio))
    im = im.resize((sw, oh), Image.BOX)
    if sw == ow:
        return im
    if sw < ow:
        bg = Image.new("RGB", (ow, oh), (0, 0, 0))
        bg.paste(im, ((ow - sw) // 2, 0))
        return bg
    if align == "left":
        x0 = 0
    elif align == "right":
        x0 = sw - ow
    else:
        x0 = (sw - ow) // 2
    return im.crop((x0, 0, x0 + ow, oh))


# ---------------------------------------------------------------- 編譯
def art_of(item):
    """這個排播項目用哪一支美術。

    key 是「排播單位」，art 是「美術」。兩者分開之後，同一支美術可以掛在
    好幾個時段上 —— 整點彩蛋就是這樣做的：11 個整點共用 3 支影片，
    不必編 11 次，也不必往卡上送 11 個檔（卡的空間和節目數都有限）。
    沒寫 art 就是 key 自己，舊的設定檔不用改。
    """
    return item.get("art") or item["key"]


def build_store(store, data, log=print):
    """算出一家店所有啟用內容的影片。回傳 {key: mp4 路徑}。"""
    mw, mh, ow, oh, align = resolve_canvas(store, data)
    prm = merged_params(store, data)
    if (mw, mh) != (ow, oh):
        log("  [%s] 鏡像自 %s×%s，等比縮到 %s×%s（%.2f 倍）後裁切 %s"
            % (store["id"], mw, mh, ow, oh, oh / mh, align))

    outdir = os.path.join(BUILD, store["id"])
    os.makedirs(outdir, exist_ok=True)
    for old in os.listdir(outdir):
        if old.endswith((".png", ".gif", ".mp4")):
            os.remove(os.path.join(outdir, old))

    result = {}
    cache = {}                     # 美術代號 → 影片路徑。同一支只算一次。
    for item in store.get("contents", []):
        if not item.get("enabled"):
            continue
        a = art_of(item)
        for key in artwork.VARIANTS.get(a, [a]):
            # 有變體時用變體名當索引（okawari／okawari_miss），
            # 沒有的話用排播單位的名字 —— 這樣同一支美術掛在不同時段才不會互相蓋掉。
            out_key = key if key != a else item["key"]
            if key in cache:
                result[out_key] = cache[key]
                log("  [%s] %-13s 共用 %s 的影片" % (store["id"], out_key, key))
                continue

            fn = artwork.RENDERERS.get(key)
            if not fn:
                log("  [%s] %s 還沒有對應的美術，跳過" % (store["id"], out_key))
                continue

            pk = artwork.param_key(key)
            fps = int(prm["%s_fps" % pk])
            frames = [fit(im, mw, mh, ow, oh, align) for im in fn(mw, mh, prm)]
            tmp = os.path.join(outdir, "_tmp_%s.mp4" % key)
            encode_video(frames, tmp, fps, log,
                         scale=int(prm.get("video_scale", 2)))

        # 檔名帶內容雜湊：內容一變檔名就變。
        # 不這樣做的話會踩到送檔協議的斷點續傳 —— 同名但內容不同時，
        # 卡回報的是舊檔的長度，我們只補送尾巴，卡上就變成新舊混雜的壞檔，
        # 傳輸與建節目全部回 kSuccess，但畫面是黑的（2026-08-10 實測踩過）。
            with open(tmp, "rb") as f:
                digest = hashlib.md5(f.read()).hexdigest()[:8]
            path = os.path.join(outdir,
                                "%s_%s_%s.mp4" % (store["id"], key, digest))
            if os.path.exists(path):
                os.remove(path)
            os.replace(tmp, path)
            cache[key] = path
            result[out_key] = path
            log("  [%s] %-13s %d 幀 @ %d fps = %.1f 秒，影片 %.0f KB"
                % (store["id"], out_key, len(frames), fps, len(frames) / fps,
                   os.path.getsize(path) / 1024))
    return result


def parse_files(xml):
    """把 GetFiles 的回應拆成 [{name, md5, existSize, type, size}, ...]。

    ★ 不能用「照順序」的正則去比對。卡回來的屬性順序不固定 ——
      2026-08-17 實測是 existSize → name → md5 → type → size，
      跟原本假設的 name → md5 → existSize 不一樣，結果每個檔都被判成
      「卡上找不到」，明明檔案都上去了。發佈會整批靜悄悄地失敗。
    """
    out = []
    for node in re.findall(r'<file\s([^>]*?)/?>', xml):
        attrs = dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', node))
        if attrs.get("name"):
            out.append(attrs)
    return out


def card_file_info(card, name):
    """問卡某個檔案的狀態。沒有就回 None。"""
    for f in parse_files(card.call('  <in method="GetFiles"/>')):
        if f["name"] == name:
            return f
    return None


def clean_media(card, keep, log=print):
    """把卡上用不到的圖檔與影片刪掉。

    每次發佈都送新檔卻不清舊檔的話，卡上的檔案會一直累積，
    最後 AddProgram 會回 kDownloadingFile → kDownloadFileFailed。
    """
    files = parse_files(card.call('  <in method="GetFiles"/>'))
    dead = [f["name"] for f in files
            if f.get("type") in ("image", "video") and f["name"] not in keep]
    if not dead:
        return 0
    for i in range(0, len(dead), 40):
        body = "".join('<file name="%s"/>' % n for n in dead[i:i + 40])
        card.call('  <in method="DeleteFiles">\n'
                  '    <files>%s</files>\n  </in>' % body)
    log("  清掉卡上 %d 個用不到的媒體檔" % len(dead))
    return len(dead)


def publish_store(card, store, built, data, log=print):
    """送檔 + 建節目。回傳 {key: {program, area, seconds, file}}。"""
    _, _, ow, oh, _ = resolve_canvas(store, data)
    prm = merged_params(store, data)
    by_key = {c["key"]: c for c in store.get("contents", [])}
    guids = {}

    # 先把卡上舊的節目全部刪掉，再重建。
    #
    # 不清的話每發佈一次就多一批 —— 舊節目的檔案雖然被 clean_media 刪了，
    # 節目本身還在，而且沒有時段限制，會混進日常輪播。
    # 2026-08-17 實測踩到：卡上累積了 10 個節目，其中兩個沒有時段的「續碗」
    # 會自己跳出來播，客人根本沒續碗。
    n = wipe_programs(card, log)
    if n:
        log("  清掉卡上 %d 個舊節目" % n)

    clean_media(card, {os.path.basename(p) for p in built.values()}, log)

    sent = {}                      # 檔名 → 送成功沒有。共用的美術只送一次。
    for key, path in built.items():
        name = os.path.basename(path)
        if name not in sent:
            hs.send_file(card, path, file_type=hs.FILE_TYPE_VIDEO, progress=False)

            # 對一次 md5。壞檔要當場抓出來，不要等到看見黑屏才知道。
            with open(path, "rb") as f:
                want = hashlib.md5(f.read()).hexdigest().lower()
            got = card_file_info(card, name)
            ok = bool(got)
            if not got:
                log("    ✗ 卡上找不到 %s，跳過" % name)
            elif (got.get("md5", "").lower() != want
                  or int(got.get("existSize", -1)) != os.path.getsize(path)):
                log("    ✗ 卡上的 %s 對不起來（md5 %s vs %s），跳過"
                    % (name, got.get("md5", "")[:8], want[:8]))
                ok = False
            sent[name] = ok
        if not sent[name]:
            continue

        item0 = by_key.get(key) or by_key.get(artwork.param_key(key)) or {}
        secs = prm["%s_seconds" % artwork.param_key(art_of(item0) if item0 else key)]
        log("  [%s] %s：送了 %s（%.0f KB，%.1f 秒）"
            % (store["id"], key, name, os.path.getsize(path) / 1024, secs))

        # 一個區域只有一個影片資源，卡自己播，不會反覆銷毀重建區域。
        #
        # playControl 帶排播條件（時段／日期／星期），卡就會自己按時鐘換節目，
        # 不需要後台在線上輪詢。開幕活動設了日期還會自己過期。
        # 條件寫在 stores.json 的 contents[].when，見 schedule.py。
        item = item0
        pc = sched.play_control_xml(item)
        if item.get("when") or item.get("trigger") == "manual":
            log("    排播：%s" % pc.replace('<playControl count="1">', '')
                                   .replace('</playControl>', '').replace('/>', '/> '))

        pg, ag = hs.new_guid(), hs.new_guid()
        screen = (
            '    <screen width="%d" height="%d">'
            '<program guid="%s" type="normal">%s'
            '<area guid="%s" alpha="255">'
            '<rectangle x="0" y="0" width="%d" height="%d"/>'
            '<resources><video guid="%s" aspectRatio="false">'
            '<file name="%s"/></video></resources>'
            '</area></program></screen>'
            % (ow, oh, pg, pc, ag, ow, oh, hs.new_guid(), name)
        )

        result = ""
        for attempt in range(60):
            out = card.call('  <in method="AddProgram">\n%s\n  </in>' % screen)
            result = hd.attr(out, "out", "result")
            if result not in ("kDownloadingFile", "kProcessing"):
                break
            if attempt == 0:
                log("    卡還在寫檔，等它…")
            time.sleep(1.0)
        if result != "kSuccess":
            log("    ✗ AddProgram 失敗：%s" % result)
            continue

        for _ in range(40):
            r = card.call('  <in method="SwitchProgram">\n'
                          '    <program guid="%s"/>\n  </in>' % pg)
            if hd.attr(r, "out", "result") == "kSuccess":
                break
            time.sleep(0.25)

        guids[key] = {"program": pg, "area": ag, "seconds": secs, "file": name}
        log("    ✓ %s → %s" % (key, pg))

    return guids


def wipe_programs(card, log=print):
    """把卡上現有的節目全部刪掉，回到乾淨狀態。"""
    import re
    xml = card.call('  <in method="GetProgram"/>')
    pairs = re.findall(
        r'<program guid="([^"]+)"[^>]*>.*?<area guid="([^"]+)"', xml, re.S)
    for pg, ag in pairs:
        hs.delete_program(card, pg, ag)
    return len(pairs)


# 舊名字還有人叫，留著
clean_images = clean_media
