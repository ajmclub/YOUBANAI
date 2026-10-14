#!/usr/bin/env python
"""游伴 AI · 统一测试入口。

一次跑完五套验证并打印汇总：

    python tests/run_all.py                 # 全部（需要服务已在 --base 上运行）
    python tests/run_all.py --start         # 自动选空闲端口启动服务，跑完自动关闭
    python tests/run_all.py --base http://127.0.0.1:8802
    python tests/run_all.py --no-browser    # 跳过真实浏览器验证（不需要 Playwright）

顺序说明：browser_check 会在开头重置数据库为初始演示状态，
e2e_check / round2_check 会写库，因此脚本最后会再重置一次，保证演示状态干净。
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(host: str, start: int, tries: int = 60) -> int | None:
    for p in range(start, start + tries):
        if port_is_free(host, p):
            return p
    return None


def wait_ready(base: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/health", timeout=3):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)
    return False


def run(title: str, args: list[str]) -> tuple[int, str]:
    print("\n" + "=" * 74)
    print(f"▶ {title}")
    print("=" * 74, flush=True)
    proc = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out.rstrip()[-4000:] if len(out) > 4000 else out.rstrip())
    return proc.returncode, out


def main() -> int:
    ap = argparse.ArgumentParser(description="游伴 AI 统一测试入口")
    ap.add_argument("--base", default=None, help="已运行服务的地址")
    ap.add_argument("--start", action="store_true", help="自动启动服务后再跑")
    ap.add_argument("--no-browser", action="store_true", help="跳过真实浏览器验证")
    ap.add_argument("--port", type=int, default=8801, help="--start 时优先使用的端口")
    args = ap.parse_args()

    proc = None
    base = args.base
    if args.start:
        port = args.port if port_is_free("127.0.0.1", args.port) else find_free_port(
            "127.0.0.1", args.port + 1)
        if port is None:
            print("未找到空闲端口")
            return 1
        base = f"http://127.0.0.1:{port}"
        print(f"启动服务：{base}")
        proc = subprocess.Popen([sys.executable, "run.py", "--port", str(port)],
                                cwd=str(ROOT), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        if not wait_ready(base):
            print("服务启动超时")
            proc.terminate()
            return 1
    elif not base:
        base = "http://127.0.0.1:8801"

    if not wait_ready(base, timeout=5):
        print(f"服务未在 {base} 运行。请先执行：python run.py --port "
              f"{base.rsplit(':', 1)[-1]}   或加 --start 自动启动。")
        if proc:
            proc.terminate()
        return 1

    results: list[tuple[str, int, str]] = []
    py = sys.executable

    # final_audit 断言的是「与原型一致的演示状态」，所以先重置一次再开始。
    run("准备：重置为初始演示状态", [py, "-c",
                                     "import sys;sys.path.insert(0,'.');"
                                     "from app import seed;seed.seed_all(force=True);"
                                     "print('演示数据已重置')"])

    # 顺序很重要：
    #   e2e_check / round2_check 会写库，会破坏「演示状态」断言；
    #   final_audit 必须跑在干净数据上；
    #   browser_check 会在开头自行重置数据。
    # 因此先跑只读检查，再跑会写库的检查，最后统一恢复。
    code, out = run("① 前后端契约一致性（contract_check · 只读）",
                    [py, str(TESTS / "contract_check.py")])
    summary = next((ln for ln in out.splitlines() if ln.startswith("契约检查：")), "")
    results.append(("① 契约一致性", code, summary))

    code, out = run("② 交付一致性终检（final_audit · 只读，需干净演示数据）",
                    [py, str(TESTS / "final_audit.py")])
    summary = next((ln for ln in out.splitlines() if ln.startswith("终检：")), "")
    results.append(("② 交付一致性终检", code, summary))

    if args.no_browser:
        results.append(("③ 真实浏览器验证", -1, "已按要求跳过"))
    else:
        code, out = run("③ 真实浏览器验证（browser_check · Playwright · 自动重置数据）",
                        [py, str(TESTS / "browser_check.py"), base])
        summary = next((ln for ln in out.splitlines() if ln.startswith("浏览器验证：")), "")
        if "No module named 'playwright'" in out:
            summary = "未安装 Playwright（可加 --no-browser 跳过）"
            code = -1
        results.append(("③ 真实浏览器验证", code, summary))

    code, out = run("④ 接口端到端自检（e2e_check · 会写库）",
                    [py, str(TESTS / "e2e_check.py"), base])
    summary = next((ln for ln in out.splitlines() if ln.startswith("通过 ")), "")
    results.append(("④ 接口端到端自检", code, summary))

    code, out = run("⑤ 第二轮功能自检（round2_check · 新剧本 / 家长模式 / 可观测性）",
                    [py, str(TESTS / "round2_check.py"), base])
    summary = next((ln for ln in out.splitlines() if ln.startswith("第二轮自检：")), "")
    results.append(("⑤ 第二轮功能自检", code, summary))

    code, out = run("⑥ 数据体检（inspect_data · 刷新 tests/_inspect.txt）",
                    [py, str(TESTS / "inspect_data.py")])
    summary = "报告已刷新" if code == 0 else "失败"
    results.append(("⑥ 数据体检", code, summary))

    # 恢复初始演示状态
    print("\n" + "=" * 74)
    print("▶ 恢复初始演示状态（清除测试写入）")
    print("=" * 74, flush=True)
    code, out = run("reseed", [py, "-c",
                               "import sys;sys.path.insert(0,'.');"
                               "from app import seed;seed.seed_all(force=True);"
                               "print('演示数据已重置')"])
    results.append(("⑦ 恢复演示数据", code, "演示数据已重置" if code == 0 else "失败"))

    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("\n服务已关闭。")

    print("\n" + "=" * 74)
    print("游伴 AI · 验证汇总")
    print("=" * 74)
    failed = 0
    for name, code, summary in results:
        if code == 0:
            status = "PASS"
        elif code == -1:
            status = "SKIP"
        else:
            status = "FAIL"
            failed += 1
        print(f"  [{status}] {name:<26} {summary}")
    print("=" * 74)
    print(f"  总计 {len(results)} 套，失败 {failed} 套")
    print(f"  地址：{base}")
    print("=" * 74)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
