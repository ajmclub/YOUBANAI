#!/usr/bin/env python
"""端口探测自检：验证 port_is_free 能正确识别占用端口，以及自动回退逻辑。"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT))

import run as runner  # noqa: E402

HOST = "127.0.0.1"

print("=" * 70)
print("端口探测自检")
print("=" * 70)

# 1) 已知被占用 / 空闲端口的判定
print("\n【1】占用判定（8000 与 8770 已被本机其它项目占用）")
for p in (8000, 8770, 8899, 9001):
    print(f"    {p:<6} -> {'free' if runner.port_is_free(HOST, p) else 'BUSY'}")

# 2) 真实占住一个端口，确认探测返回 BUSY
print("\n【2】真实占住 9101 后探测（应返回 BUSY）")
holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
holder.bind((HOST, 9101))
holder.listen(1)
try:
    busy = runner.port_is_free(HOST, 9101)
    print(f"    9101 占用中 -> {'free（错误！）' if busy else 'BUSY（正确）'}")
    # 3) 自动回退应跳过 9101
    alt = runner.find_free_port(HOST, 9101)
    print(f"    find_free_port(9101) -> {alt} （应 > 9101）")
    ok_skip = alt is not None and alt > 9101
    print(f"    跳过占用端口: {'正确' if ok_skip else '错误'}")
finally:
    holder.close()

# 4) 释放后应变为 free
print("\n【3】释放 9101 后探测（应返回 free）")
after = runner.port_is_free(HOST, 9101)
print(f"    9101 已释放 -> {'free（正确）' if after else 'BUSY（错误）'}")

# 5) 从真实默认端口出发能找到可用端口
print("\n【4】从默认端口出发寻找可用端口")
found = runner.find_free_port(HOST, 8770)
print(f"    find_free_port(8770) -> {found}")
print(f"    绑定性验证: ", end="")
if found:
    t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        t.bind((HOST, found))
        print("成功（该端口确实可用）")
    except OSError as e:
        print(f"失败：{e}")
    finally:
        t.close()
