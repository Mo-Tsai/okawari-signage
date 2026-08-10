#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灰度控制卡 —— 送檔案 / 建節目（協議層）

依據 SDK 文件 Protocol/SDK发送文件流程.md 與 SDKNetApi 的 HStruct.h 實作。

送檔流程（文件明講：中途不能插入 SDK 資料，否則會丟失 SDK 協商並回報流程錯誤）：
    kFileStartAsk(0x8001)  →  kFileStartAnswer(0x8002)   帶錯誤碼與「已存在大小」
    kFileContentAsk(0x8003) × N                           每包上限 9*1024-4 bytes
    kFileEndAsk(0x8005)    →  kFileEndAnswer(0x8006)      收到這個才回到 SDK 通訊狀態

搭配 hd_test.py 的 HDCard 使用。
只用 Python 標準函式庫。
"""

import hashlib
import os
import struct
import time
import uuid

from hd_test import CardError, error_text

CMD_HEARTBEAT_ASK = 0x005F
CMD_HEARTBEAT_ANS = 0x0060
CMD_ERROR = 0x2000

CMD_FILE_START_ASK = 0x8001
CMD_FILE_START_ANS = 0x8002
CMD_FILE_CONTENT_ASK = 0x8003
CMD_FILE_CONTENT_ANS = 0x8004
CMD_FILE_END_ASK = 0x8005
CMD_FILE_END_ANS = 0x8006

CHUNK_MAX = 9 * 1024 - 4          # 文件寫死的每包上限

FILE_TYPE_IMAGE = 0
FILE_TYPE_VIDEO = 1
FILE_TYPE_FONT = 2
FILE_TYPE_TEMP_IMAGE = 128        # 存在記憶體，全部加起來不能超過 10MB
FILE_TYPE_TEMP_VIDEO = 129


def new_guid():
    return "{%s}" % uuid.uuid4()


def _pump_file(card, want_cmd, deadline):
    """收封包直到拿到想要的 cmd。中途自動回心跳。

    不能用 HDCard._pump —— 那支只認得 SDK 回應封包（0x2004），
    會把檔案流程的封包當成「未預期」丟掉。
    """
    while True:
        if time.time() > deadline:
            raise CardError("等待控制卡回應逾時（cmd=0x%04x）" % want_cmd)
        cmd, payload = card._read_packet()

        if cmd in (CMD_HEARTBEAT_ASK, CMD_HEARTBEAT_ANS):
            card._send_raw(struct.pack("<HH", 4, CMD_HEARTBEAT_ASK))
            continue

        if cmd == CMD_ERROR:
            code = struct.unpack_from("<H", payload, 0)[0] if len(payload) >= 2 else -1
            raise CardError("控制卡回報錯誤 %s" % error_text(code))

        if cmd == want_cmd:
            return payload

        card.log("  （送檔中收到未預期封包 cmd=0x%04x，忽略）" % cmd)


def send_file(card, path, file_type=FILE_TYPE_IMAGE, name=None, progress=True):
    """把一個檔案送進卡裡。回傳實際送出的位元組數。

    卡若回報檔案已存在（existSize > 0），只補送缺的部分（斷點續傳）。
    """
    name = name or os.path.basename(path)
    with open(path, "rb") as f:
        data = f.read()

    size = len(data)
    md5 = hashlib.md5(data).hexdigest().lower().encode("ascii")
    if len(md5) != 32:
        raise CardError("md5 長度不對")
    md5_field = md5 + b"\x00"                      # 33 bytes
    name_field = name.encode("utf-8") + b"\x00"

    pkt_len = 2 + 2 + 33 + 8 + 2 + len(name_field)
    if pkt_len > 0xFFFF:
        raise CardError("檔名太長")

    head = (struct.pack("<HH", pkt_len, CMD_FILE_START_ASK)
            + md5_field
            + struct.pack("<Q", size)
            + struct.pack("<H", file_type)
            + name_field)

    card.log("  送檔 %s（%d bytes，type=%d，md5=%s）"
             % (name, size, file_type, md5.decode()))
    card._send_raw(head)

    ans = _pump_file(card, CMD_FILE_START_ANS, time.time() + card.timeout)
    if len(ans) < 2:
        raise CardError("檔案開始回應太短")
    status = struct.unpack_from("<H", ans, 0)[0]
    exist = struct.unpack_from("<Q", ans, 2)[0] if len(ans) >= 10 else 0
    if status != 0:
        # 文件要求：出錯也要送結束包，把設備狀態切回來
        card._send_raw(struct.pack("<HH", 4, CMD_FILE_END_ASK))
        try:
            _pump_file(card, CMD_FILE_END_ANS, time.time() + card.timeout)
        except Exception:
            pass
        raise CardError("卡拒絕接收檔案：%s" % error_text(status))

    if exist >= size:
        card.log("    卡上已經有一模一樣的檔案，不用再送")
        offset = size
    else:
        offset = exist
        if offset:
            card.log("    卡上已有 %d bytes，續傳剩下的" % offset)

    sent = 0
    while offset < size:
        chunk = data[offset:offset + CHUNK_MAX]
        card._send_raw(struct.pack("<HH", 4 + len(chunk), CMD_FILE_CONTENT_ASK) + chunk)
        offset += len(chunk)
        sent += len(chunk)
        if progress and size > CHUNK_MAX:
            card.log("    ... %d / %d bytes" % (offset, size))

    card._send_raw(struct.pack("<HH", 4, CMD_FILE_END_ASK))
    end = _pump_file(card, CMD_FILE_END_ANS, time.time() + max(card.timeout, 20))
    code = struct.unpack_from("<H", end, 0)[0] if len(end) >= 2 else -1
    if code != 0:
        raise CardError("檔案結束回報錯誤：%s" % error_text(code))

    card.log("    ✓ 送完了")
    return sent


# ---------------------------------------------------------------- 節目
def q_program(card):
    return card.call('  <in method="GetProgram"/>')


def add_program(card, screen_xml):
    return card.call('  <in method="AddProgram">\n%s\n  </in>' % screen_xml)


def delete_program(card, program_guid, area_guid=None):
    body = ['    <program guid="%s" type="normal">' % program_guid]
    if area_guid:
        body.append('      <area guid="%s" alpha="255"/>' % area_guid)
    body.append("    </program>")
    return card.call('  <in method="DeleteProgram">\n%s\n  </in>' % "\n".join(body))


def build_image_program(width, height, filename,
                        program_guid=None, area_guid=None, res_guid=None,
                        duration=50):
    """單張圖的節目單。

    注意：SDK 文件裡沒有定義 <image> 資源節點的屬性，這是照
    <text> 節點的形狀與 GetProgram 讀回來的實際結構推的，要靠真卡驗證。
    """
    program_guid = program_guid or new_guid()
    area_guid = area_guid or new_guid()
    res_guid = res_guid or new_guid()
    return (
        '    <screen width="%d" height="%d">\n'
        '      <program guid="%s" type="normal">\n'
        '        <playControl count="1"/>\n'
        '        <area guid="%s" alpha="255">\n'
        '          <rectangle x="0" y="0" width="%d" height="%d"/>\n'
        '          <resources>\n'
        '            <image guid="%s">\n'
        '              <effect in="0" out="0" inSpeed="4" outSpeed="4" duration="%d"/>\n'
        '              <file name="%s"/>\n'
        '            </image>\n'
        '          </resources>\n'
        '        </area>\n'
        '      </program>\n'
        '    </screen>'
        % (width, height, program_guid, area_guid,
           width, height, res_guid, duration, filename)
    ), {"program": program_guid, "area": area_guid, "resource": res_guid}
