"""游伴 AI (YOUBAN AI) · FastAPI 应用入口。

启动：
    python run.py                 # 或
    python -m uvicorn app.main:app --port 8770

访问（默认端口 8770）：
    http://127.0.0.1:8770/          项目门户
    http://127.0.0.1:8770/c/        C 端 H5
    http://127.0.0.1:8770/admin/    B 端 SaaS 后台
    http://127.0.0.1:8770/docs      API 文档（Swagger）
"""
from __future__ import annotations

import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, observability, seed
from .config import (APP_NAME, APP_NAME_EN, BRAND, HOST, MECHANISM, PORT,
                     TAGLINE, VERSION, WEB_DIR)
from .routers import admin, c_end


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时确保数据库存在且已播种。"""
    db.init_db(force=False)
    if not db.is_seeded():
        stats = seed.seed_all(force=False)
        print("[游伴 AI] 首次启动，已自动播种：")
        for k, v in stats.items():
            print(f"    {k:12s} {v}")
    else:
        print(f"[游伴 AI] 数据库就绪：{db.DB_FILE}")
    yield


app = FastAPI(
    title=f"{APP_NAME} · {APP_NAME_EN} API",
    description=(
        f"**{APP_NAME}** — AI × 潮玩 × 文旅 × 剧本游\n\n"
        f"- 品牌主张：{TAGLINE}\n"
        f"- 产品机制：{MECHANISM}\n\n"
        "© 游伴 AI"
    ),
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- 可观测性中间件
_ID_SEGMENT = re.compile(r"/\d+")


def _normalize(path: str) -> str:
    """把 /api/c/task/12 归一化为 /api/c/task/{id}，便于按端点聚合指标。"""
    return _ID_SEGMENT.sub("/{id}", path)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - started) * 1000
        path = _normalize(request.url.path)
        observability.record(request.method, path, 500, elapsed)
        observability.log_line(request.method, path, 500, elapsed)
        raise
    elapsed = (time.perf_counter() - started) * 1000
    path = _normalize(request.url.path)
    observability.record(request.method, path, response.status_code, elapsed)
    if observability.should_log(request.url.path):
        observability.log_line(request.method, path, response.status_code, elapsed)
    response.headers["X-Response-Time"] = f"{elapsed:.1f}ms"
    return response

# ---------------------------------------------------------------- 路由
app.include_router(c_end.router)
app.include_router(admin.router)


@app.get("/health", tags=["系统"], summary="健康检查")
def health():
    try:
        db.scalar("SELECT COUNT(*) FROM parks")
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {type(exc).__name__}"
    snap = observability.snapshot()
    return {"ok": True, "db": db_status, "version": VERSION,
            "app": APP_NAME, "app_en": APP_NAME_EN,
            "uptime_seconds": snap["uptime_seconds"],
            "requests_total": snap["requests_total"],
            "avg_ms": snap["avg_ms"],
            "error_rate": snap["error_rate"]}


@app.get("/api/metrics", tags=["系统"], summary="可观测性指标（请求 + 业务）")
def metrics():
    """请求指标来自进程内存，业务计数来自数据库实时统计。"""
    return {"requests": observability.snapshot(),
            "business": observability.business_counters()}


@app.get("/api/meta", tags=["系统"], summary="项目元信息")
def meta():
    """品牌常量与项目结构，供前端与文档使用。"""
    return {
        "app": APP_NAME, "app_en": APP_NAME_EN, "version": VERSION,
        "tagline": TAGLINE, "mechanism": MECHANISM,
        "definition": "AI 潮玩 × 景区剧本游 × 儿童成长",
        "positioning": "儿童 AI 旅行陪伴与文旅探索平台",
        "brand": BRAND,
        "vision": "让世界每一个值得去的地方，都拥有一个属于孩子的故事。",
        "entries": {"portal": "/", "c_end": "/c/", "admin": "/admin/", "docs": "/docs"},
        "counts": {
            "parks": int(db.scalar("SELECT COUNT(*) FROM parks")),
            "scenarios": int(db.scalar("SELECT COUNT(*) FROM scenarios")),
            "nodes": int(db.scalar("SELECT COUNT(*) FROM nodes")),
            "tasks": int(db.scalar("SELECT COUNT(*) FROM tasks")),
            "badges": int(db.scalar("SELECT COUNT(*) FROM badges")),
            "materials": int(db.scalar("SELECT COUNT(*) FROM materials")),
            "users": int(db.scalar("SELECT COUNT(*) FROM users")),
        },
    }


@app.exception_handler(404)
async def not_found(request: Request, exc):  # noqa: ARG001
    if request.url.path.startswith("/api/"):
        detail = getattr(exc, "detail", "资源不存在")
        return JSONResponse(status_code=404, content={"ok": False, "error": detail})
    return HTMLResponse(
        "<body style='background:#0B1020;color:#F5F1E8;font-family:system-ui;"
        "display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>"
        "<div style='text-align:center'>"
        "<h1 style='color:#E8B45A;font-size:56px;margin:0'>404</h1>"
        "<p style='opacity:.7'>这条剧情线还没有被写下来。</p>"
        "<p><a href='/' style='color:#E8B45A'>← 返回游伴门户</a></p>"
        "</div></body>", status_code=404)


# ---------------------------------------------------------------- 静态资源
PORTAL_FILE = WEB_DIR / "index.html"


@app.get("/", include_in_schema=False)
def portal():
    if PORTAL_FILE.exists():
        return FileResponse(PORTAL_FILE)
    return HTMLResponse("<h1>游伴 AI</h1><p>门户文件缺失，请访问 /c/ 或 /admin/</p>")


for _path, _name in [("c", "c"), ("admin", "admin")]:
    _directory = WEB_DIR / _path
    if _directory.exists():
        app.mount(f"/{_name}", StaticFiles(directory=str(_directory), html=True), name=_name)


def main() -> None:
    import uvicorn

    bar = "=" * 66
    print(bar)
    print(f"  {APP_NAME} · {APP_NAME_EN}  v{VERSION}")
    print(f"  {TAGLINE}")
    print(bar)
    print(f"  项目门户   http://{HOST}:{PORT}/")
    print(f"  C 端 H5    http://{HOST}:{PORT}/c/")
    print(f"  B 端后台   http://{HOST}:{PORT}/admin/")
    print(f"  API 文档   http://{HOST}:{PORT}/docs")
    print(bar)
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
