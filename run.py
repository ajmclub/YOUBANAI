#!/usr/bin/env python
"""游伴 AI (YOUBAN AI) · 一键启动脚本。

    python run.py

可选参数：
    python run.py --reseed        重新播种数据库（清空并重建演示数据）
    python run.py --port 8080     指定端口
    python run.py --host 0.0.0.0  指定监听地址

端口策略：默认 8770（刻意避开常被其它项目占用的 8000）。
若该端口已被占用，会自动向上寻找一个空闲端口并在终端提示。
"""
from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def port_is_free(host: str, port: int) -> bool:
    """尝试真实绑定，判断端口是否可用。

    注意：**不能**设置 SO_REUSEADDR。Windows 下 SO_REUSEADDR 允许绑定到
    一个已被占用的端口（与 Linux 语义不同），会导致探测永远返回「可用」，
    而 uvicorn 随后以独占方式绑定失败（WinError 10048）。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(host: str, start: int, tries: int = 40) -> int | None:
    for p in range(start, start + tries):
        if port_is_free(host, p):
            return p
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="游伴 AI 启动器")
    parser.add_argument("--reseed", action="store_true", help="重新播种数据库")
    parser.add_argument("--host", default=None, help="监听地址")
    parser.add_argument("--port", type=int, default=None, help="监听端口")
    args = parser.parse_args()

    from app import db, seed
    from app.config import HOST, PORT

    if args.reseed:
        print("[游伴 AI] 正在重新播种数据库……")
        stats = seed.seed_all(force=True)
        print("[游伴 AI] 播种完成：")
        for k, v in stats.items():
            print(f"    {k:12s} {v}")
    else:
        db.init_db(force=False)
        if not db.is_seeded():
            print("[游伴 AI] 首次启动，正在播种演示数据……")
            seed.seed_all(force=False)

    host = args.host or HOST
    want = args.port or PORT

    if not port_is_free(host, want):
        alt = find_free_port(host, want + 1)
        print(f"[游伴 AI] 端口 {want} 已被占用。", end=" ")
        if alt is None:
            print("且未找到可用端口，请用 --port 指定其它端口。")
            return 1
        print(f"已自动改用 {alt}。")
        print(f"          如需固定端口，请执行： python run.py --port <端口>")
        port = alt
    else:
        port = want

    import uvicorn

    bar = "=" * 66
    print(bar)
    print("  游伴 AI · YOUBAN AI     带着它，去发现世界。")
    print(bar)
    print(f"  项目门户   http://{host}:{port}/")
    print(f"  C 端 H5    http://{host}:{port}/c/")
    print(f"  B 端后台   http://{host}:{port}/admin/")
    print(f"  API 文档   http://{host}:{port}/docs")
    print(bar)
    print("  演示账号   user_id = 1（小小探险家 · 王家）")
    print("  演示激活码 YB-XA-2026-0001 / YB-BJ-2026-0002 / YB-HZ-2026-0003")
    print(bar)
    print("  按 Ctrl+C 停止服务。")
    print()

    uvicorn.run("app.main:app", host=host, port=port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
