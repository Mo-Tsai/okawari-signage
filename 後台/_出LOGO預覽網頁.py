# -*- coding: utf-8 -*-
"""把「整點 LOGO 跑燈」做成一頁可以直接傳給業主看的網頁。

    python _出LOGO預覽網頁.py           → docs/logo.html

★ 影片是用 base64 **包在 HTML 裡面**的，不是外連。
  這一頁的用途就是「傳給業主看」—— 走 LINE、走 email、存到桌面都要能開。
  外連 mp4 的話，離開 GitHub Pages 就變成一個破掉的播放器，
  而寄件的人不會知道對方看到的是破的。一個檔就是一個檔。

★ 影片是**真的要灌進卡裡的那一支**，不是另外做的示意動畫。
  來源是 `build/<店>/<店>_logo_*.mp4`，跟送上卡的是同一個檔。
  示意動畫跟成品之間一定會有落差，而落差會在驗收那天才被發現。
"""
import base64
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "docs", "logo.html")

STORES = [("tainan", "台南小北", "新光三越台南小北"),
          ("taichung", "台中港", "新光三越台中港")]


def data_uri(path):
    with open(path, "rb") as f:
        return "data:video/mp4;base64," + base64.b64encode(f.read()).decode("ascii")


def main():
    data = json.load(io.open(os.path.join(HERE, "stores.json"), encoding="utf-8"))
    by_id = {s["id"]: s for s in data["stores"]}

    cards, total = [], 0
    for sid, short, full in STORES:
        hits = glob.glob(os.path.join(HERE, "build", sid, "%s_logo_*.mp4" % sid))
        if not hits:
            raise SystemExit("找不到 %s 的 logo 影片。先跑：python _建全部.py %s"
                             % (sid, sid))
        path = max(hits, key=os.path.getmtime)
        st = by_id[sid]
        c = st["canvas"]
        slots = sorted(x["when"]["time"][0][:5] for x in st["contents"]
                       if x.get("logo_slot"))
        total += os.path.getsize(path)
        cards.append({
            "id": sid, "short": short, "full": full,
            "w": c["width"], "h": c["height"],
            "slots": slots,
            "open": st["schedule"]["open"], "close": st["schedule"]["close"],
            "src": data_uri(path),
        })
        print("  %s　%d×%d　%d 格　影片 %.0f KB"
              % (sid, c["width"], c["height"], len(slots),
                 os.path.getsize(path) / 1024.0))

    a = cards[0]
    tabs = "".join(
        '<button class="tab%s" data-i="%d">%s<em>%d×%d</em></button>'
        % (" on" if i == 0 else "", i, c["short"], c["w"], c["h"])
        for i, c in enumerate(cards))
    # ★ 每一支自己帶長寬比。兩家店的畫布比例不一樣（8:1 對 8.67:1），
    #   共用一個比例的話，比較寬的那一支會被 object-fit 加上黑邊 ——
    #   而黑邊在黑底的網頁上看不出來，業主會以為屏就是長那樣。
    vids = "".join(
        '<video class="panel%s" data-i="%d" style="aspect-ratio:%d/%d" src="%s" '
        'autoplay loop muted playsinline preload="auto"></video>'
        % ("" if i == 0 else " off", i, c["w"], c["h"], c["src"])
        for i, c in enumerate(cards))
    ticks = "".join('<i style="left:%.4f%%"><b>%s</b></i>'
                    % (pos(t, a["open"], a["close"]), t) for t in a["slots"])

    html = PAGE % {
        "tabs": tabs, "vids": vids, "ticks": ticks,
        "open": a["open"], "close": a["close"], "n": len(a["slots"]),
    }
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(html)
    print()
    print("寫好了 → %s（%.1f MB）"
          % (os.path.relpath(OUT, ROOT), os.path.getsize(OUT) / 1024.0 / 1024.0))
    print("  這一個檔就是完整的，影片包在裡面。可以直接傳給業主。")


def mins(t):
    p = t.split(":")
    return int(p[0]) * 60 + int(p[1])


def pos(t, a, b):
    return 100.0 * (mins(t) - mins(a)) / float(mins(b) - mins(a))


PAGE = u"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OKAWARI 門頭屏｜整點 LOGO 跑燈</title>
<style>
  :root{
    --ink:#f2efe6; --dim:#8e8b83; --line:#2a2823;
    --green:#12552e; --gold:#eec238; --red:#af1e24;
  }
  *{box-sizing:border-box}
  body{
    margin:0; background:#111008; color:var(--ink);
    font:16px/1.75 "Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:1100px; margin:0 auto; padding:56px 24px 80px}
  header{border-bottom:1px solid var(--line); padding-bottom:28px; margin-bottom:40px}
  .kicker{color:var(--gold); letter-spacing:.22em; font-size:12px; font-weight:700}
  h1{margin:.4em 0 .3em; font-size:31px; line-height:1.3; letter-spacing:-.01em}
  .lead{color:var(--dim); margin:0; max-width:44em}

  .tabs{display:flex; gap:8px; margin:0 0 14px}
  .tab{
    background:none; border:1px solid var(--line); color:var(--dim);
    padding:9px 16px; border-radius:999px; cursor:pointer; font:inherit;
    font-size:14px; display:flex; align-items:baseline; gap:9px;
    transition:border-color .15s, color .15s;
  }
  .tab:hover{border-color:#4a463d; color:var(--ink)}
  .tab em{font-style:normal; font-size:11px; opacity:.6; letter-spacing:.04em}
  .tab.on{border-color:var(--gold); color:var(--gold)}

  .stage{
    background:#000; border:1px solid var(--line); border-radius:4px;
    padding:18px; overflow-x:auto;
  }
  .panel{
    display:block; width:100%%; min-width:440px;
    background:var(--green);
  }
  .panel.off{display:none}
  .cap{color:var(--dim); font-size:13px; margin:12px 2px 0}

  h2{font-size:14px; letter-spacing:.16em; color:var(--gold);
     margin:56px 0 18px; font-weight:700}

  .bar{position:relative; height:70px; margin:26px 0 8px}
  .bar>hr{
    position:absolute; top:26px; left:0; right:0; height:2px; margin:0;
    border:0; background:linear-gradient(90deg,#2a2823,#4a463d,#2a2823);
  }
  .bar i{position:absolute; top:0; transform:translateX(-50%%); text-align:center}
  .bar i:before{
    content:""; display:block; width:3px; height:22px; margin:0 auto;
    background:var(--gold); border-radius:2px;
  }
  .bar i b{
    display:block; margin-top:12px; font-size:11px; font-weight:400;
    color:var(--dim); letter-spacing:.02em;
  }
  .ends{display:flex; justify-content:space-between; color:var(--dim); font-size:12px}

  .notes{
    margin:26px 0 0; padding:0; list-style:none;
    display:grid; gap:2px; grid-template-columns:1fr;
  }
  .notes li{
    border-top:1px solid var(--line); padding:16px 0;
    display:grid; grid-template-columns:9em 1fr; gap:20px; align-items:start;
  }
  .notes b{font-weight:700; color:var(--gold); font-size:13px; letter-spacing:.06em}
  .notes span{color:var(--dim)}
  .notes span strong{color:var(--ink); font-weight:400}

  footer{
    margin-top:64px; padding-top:22px; border-top:1px solid var(--line);
    color:#5f5c55; font-size:12px;
  }
  @media (max-width:640px){
    .wrap{padding:36px 16px 60px}
    .stage{padding:10px}
    h1{font-size:24px}
    .notes li{grid-template-columns:1fr; gap:6px}
    .bar i b{font-size:10px}
  }
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="kicker">OKAWARI 門頭屏</div>
    <h1>整點 LOGO 跑燈</h1>
    <p class="lead">
      每個整點過 45 分，門頭屏會換成品牌綠底，LOGO 從右邊滑進來、停在正中間，
      再往左邊滑出去。一分鐘之後回到原本的時段畫面。
    </p>
  </header>

  <div class="tabs">%(tabs)s</div>
  <div class="stage">%(vids)s</div>
  <p class="cap">
    這是實際要灌進控制卡的影片，不是示意動畫 —— 屏上看到的就是這樣。
    上面兩個分頁是兩家店各自的畫布尺寸。
  </p>

  <h2>一天跑幾次</h2>
  <div class="bar"><hr>%(ticks)s</div>
  <div class="ends"><span>%(open)s 開屏</span><span>%(close)s 關屏</span></div>

  <ul class="notes">
    <li><b>時間</b><span>開屏時間內每個整點過 45 分，一天 <strong>%(n)s 次</strong>。
      避開整點 —— 整點那一分鐘留給隱藏彩蛋。</span></li>
    <li><b>長度</b><span>一次一分鐘，LOGO 會完整跑過兩到三遍。
      前後都是乾淨的綠底，所以進場和退場都不會看到 LOGO 卡在半路。</span></li>
    <li><b>素材</b><span>直接用貴公司提供的 LOGO 原始檔。
      綠、紅、金、白四個顏色都是從那張圖上取樣的，沒有重新配色。</span></li>
    <li><b>其餘時間</b><span>照原本的時段畫面走：開店前、開店、中午、午後、
      晚間、打烊後，加上整點彩蛋和活動檔期。這一支是疊在上面的，不取代任何東西。</span></li>
  </ul>

  <footer>OKAWARI × 新光三越台南小北・台中港　門頭 LED 屏　2026 年第一季</footer>
</div>

<script>
  var tabs = document.querySelectorAll('.tab');
  var vids = document.querySelectorAll('.panel');
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].addEventListener('click', function () {
      var n = this.dataset.i;
      for (var j = 0; j < tabs.length; j++) {
        tabs[j].classList.toggle('on', tabs[j].dataset.i === n);
        vids[j].classList.toggle('off', vids[j].dataset.i !== n);
        // 切回來要從頭放，不然使用者看到的是一段停在中間的綠底
        if (vids[j].dataset.i === n) { vids[j].currentTime = 0; vids[j].play(); }
      }
    });
  }
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
