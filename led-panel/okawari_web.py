#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKAWARI QUEST 門頭屏 —— 手機遙控網頁

在 Pi 上跑一個小網站，手機連同一個網路、開瀏覽器就能控制門頭屏。
指令是用「碰一個檔案」的方式傳給 okawari_panel.py，兩支程式互不依賴。

    sudo python3 okawari_web.py            # 預設 80 埠
    sudo python3 okawari_web.py --port 8080
"""

import argparse
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

TRIGGER = "/tmp/okawari"

PAGE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>OKAWARI QUEST 遙控</title>
<style>
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{margin:0;min-height:100dvh;background:#0d0b12;color:#d8d3e0;
       font-family:"Microsoft JhengHei","PingFang TC",sans-serif;
       display:flex;flex-direction:column;align-items:center;
       padding:28px 18px calc(28px + env(safe-area-inset-bottom));gap:18px}
  h1{margin:0;font-size:14px;letter-spacing:3px;color:#a79fb3;font-weight:600}
  h1 b{color:#f7b32b}
  #big{width:100%;max-width:420px;aspect-ratio:1/.62;border-radius:22px;border:none;
       background:linear-gradient(160deg,#e23a2e,#f07818 55%,#f7b32b);
       color:#1a1520;font-size:30px;font-weight:800;letter-spacing:2px;
       font-family:inherit;cursor:pointer;box-shadow:0 10px 30px rgba(240,120,24,.28);
       transition:transform .08s ease,filter .08s ease}
  #big:active{transform:scale(.965);filter:brightness(1.12)}
  #big small{display:block;font-size:14px;font-weight:600;opacity:.72;margin-top:8px;letter-spacing:1px}
  .row{width:100%;max-width:420px;display:flex;gap:10px}
  .row button,select{flex:1;background:#1f1a2a;color:#fff;border:1px solid #3a3348;
       border-radius:12px;padding:15px 12px;font-size:15px;font-family:inherit;cursor:pointer}
  .row button:active{border-color:#f7b32b;color:#f7b32b}
  select{appearance:none;-webkit-appearance:none;text-align:center;text-align-last:center}
  #log{font-size:12px;color:#6e6a72;font-family:"Courier New",monospace;
       min-height:18px;text-align:center}
  #count{font-size:12px;color:#6e6a72;letter-spacing:1px}
  #off{margin-top:auto;width:100%;max-width:420px;background:transparent;
       color:#6e6a72;border:1px solid #2a2535;border-radius:12px;padding:14px;
       font-size:14px;font-family:inherit;cursor:pointer}
  #off.arm{color:#e23a2e;border-color:#e23a2e}
</style>
</head>
<body>
  <h1><b>OKAWARI QUEST</b>　門頭屏遙控</h1>

  <button id="big" onclick="hit('okawari','＋1 碗　勇者出發！')">
    續　碗
    <small>OKAWARI　點幾碗就按幾次</small>
  </button>

  <div class="row">
    <button onclick="hit('patrol','小勇者巡邏中…')">巡邏</button>
    <select id="chance" onchange="setChance(this.value)">
      <option value="0.1">破石 10%</option>
      <option value="0.25">破石 25%</option>
      <option value="0.5">破石 50%</option>
      <option value="1" selected>破石 100%</option>
    </select>
  </div>

  <div id="count">今日累計 <b id="n">0</b> 碗</div>
  <div id="log">連線正常</div>

  <button id="off" onclick="shutdown()">安全關機</button>

<script>
let n = 0;
let armed = false, armTimer = null;
async function shutdown(){
  const b = document.getElementById('off');
  if (!armed){
    armed = true; b.classList.add('arm');
    b.textContent = '再按一次確認關機';
    log('關機前請先確認展示已結束');
    armTimer = setTimeout(() => {
      armed = false; b.classList.remove('arm'); b.textContent = '安全關機';
      log('已取消關機');
    }, 4000);
    return;
  }
  clearTimeout(armTimer); armed = false;
  b.classList.remove('arm'); b.textContent = '關機中…';
  log('關機中，等綠燈停止閃爍後才可拔電');
  try { await fetch('/shutdown', {method:'POST'}); } catch(e){}
}
function log(m){ document.getElementById('log').textContent = m; }
function buzz(){ if (navigator.vibrate) navigator.vibrate(18); }
async function hit(cmd, msg){
  buzz();
  if (cmd === 'okawari'){ n++; document.getElementById('n').textContent = n; }
  log(msg);
  try { await fetch('/' + cmd, {method:'POST'}); }
  catch(e){ log('連線失敗，檢查手機跟屏是否在同一個網路'); }
}
async function setChance(v){
  buzz();
  log('破石機率 → ' + Math.round(v*100) + '%');
  try { await fetch('/chance?v=' + v, {method:'POST'}); }
  catch(e){ log('連線失敗'); }
}
</script>
</body>
</html>"""


def fire(name, body=""):
    with open(name, "w") as f:
        f.write(body)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def route(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/okawari":
            fire(TRIGGER)
            return self._send(200, "ok")
        if u.path == "/patrol":
            fire(TRIGGER + "_patrol")
            return self._send(200, "ok")
        if u.path == "/chance":
            v = parse_qs(u.query).get("v", ["0.25"])[0]
            fire(TRIGGER + "_chance", v)
            return self._send(200, "ok")
        if u.path == "/shutdown":
            self._send(200, "shutting down")
            subprocess.Popen(["/sbin/shutdown", "-h", "now"])
            return
        if u.path == "/health":
            return self._send(200, "alive")
        return self._send(404, "not found")

    do_GET = route
    do_POST = route

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=80)
    cfg = ap.parse_args()
    srv = ThreadingHTTPServer(("0.0.0.0", cfg.port), Handler)
    print("OKAWARI 遙控網頁：http://<Pi 的 IP>:%d" % cfg.port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
