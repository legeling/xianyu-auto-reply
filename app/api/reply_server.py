import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from loguru import logger

from app.api.dependencies import SESSION_TOKENS, TOKEN_EXPIRE_TIME
from app.services import cookie_manager
from app.services.file_log_collector import setup_file_logging

from app.api.routes import accounts, auth, management, messages, qr_login


app = FastAPI(
    title="Xianyu Auto Reply API",
    version="1.0.0",
    description="闲鱼自动回复系统API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 注册子路由
app.include_router(auth.router)
app.include_router(messages.router)
app.include_router(accounts.router)
app.include_router(qr_login.router)
app.include_router(management.router)

# 初始化文件日志收集器
setup_file_logging()

logger.info("Web服务器启动，文件日志收集器已初始化")

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.time()

    # 获取用户信息
    user_info = "未登录"
    try:
        # 从请求头中获取Authorization
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if token in SESSION_TOKENS:
                token_data = SESSION_TOKENS[token]
                # 检查token是否过期
                if time.time() - token_data['timestamp'] <= TOKEN_EXPIRE_TIME:
                    user_info = f"【{token_data['username']}#{token_data['user_id']}】"
    except Exception:
        pass

    logger.info(f"🌐 {user_info} API请求: {request.method} {request.url.path}")

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(f"✅ {user_info} API响应: {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")

    return response

PROJECT_ROOT = Path(__file__).resolve().parents[2]
static_dir = PROJECT_ROOT / 'static'
static_dir.mkdir(parents=True, exist_ok=True)

app.mount('/static', StaticFiles(directory=str(static_dir)), name='static')

# 确保图片上传目录存在
uploads_dir = static_dir / 'uploads' / 'images'
uploads_dir.mkdir(parents=True, exist_ok=True)
logger.info(f"图片上传目录准备就绪: {uploads_dir}")

# 健康检查端点
@app.get('/health')
async def health_check():
    """健康检查端点，用于Docker健康检查和负载均衡器"""
    try:
        # 检查Cookie管理器状态
        manager_status = "ok" if cookie_manager.manager is not None else "error"

        # 检查数据库连接
        from app.repositories.db_manager import db_manager
        try:
            db_manager.get_all_cookies()
            db_status = "ok"
        except Exception:
            db_status = "error"

        # 获取系统状态
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()

        status = {
            "status": "healthy" if manager_status == "ok" and db_status == "ok" else "unhealthy",
            "timestamp": time.time(),
            "services": {
                "cookie_manager": manager_status,
                "database": db_status
            },
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_info.percent,
                "memory_available": memory_info.available
            }
        }

        if status["status"] == "unhealthy":
            raise HTTPException(status_code=503, detail=status)

        return status

    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "error": str(e)
        }


# 重定向根路径到登录页面
@app.get('/', response_class=HTMLResponse)
async def root():
    login_path = static_dir / 'login.html'
    if login_path.exists():
        return HTMLResponse(login_path.read_text(encoding='utf-8'))
    else:
        return HTMLResponse('<h3>Login page not found</h3>')


# 登录页面路由
@app.get('/login.html', response_class=HTMLResponse)
async def login_page():
    login_path = static_dir / 'login.html'
    if login_path.exists():
        return HTMLResponse(login_path.read_text(encoding='utf-8'))
    else:
        return HTMLResponse('<h3>Login page not found</h3>')


# 注册页面路由
@app.get('/register.html', response_class=HTMLResponse)
async def register_page():
    # 检查注册是否开启
    from app.repositories.db_manager import db_manager
    registration_enabled = db_manager.get_system_setting('registration_enabled')
    if registration_enabled != 'true':
        return HTMLResponse('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>注册已关闭</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .message { color: #666; font-size: 18px; }
                .back-link { margin-top: 20px; }
                .back-link a { color: #007bff; text-decoration: none; }
            </style>
        </head>
        <body>
            <h2>🚫 注册功能已关闭</h2>
            <p class="message">系统管理员已关闭用户注册功能</p>
            <div class="back-link">
                <a href="/">← 返回首页</a>
            </div>
        </body>
        </html>
        ''', status_code=403)

    register_path = static_dir / 'register.html'
    if register_path.exists():
        return HTMLResponse(register_path.read_text(encoding='utf-8'))
    else:
        return HTMLResponse('<h3>Register page not found</h3>')


# 管理页面（不需要服务器端认证，由前端JavaScript处理）
@app.get('/admin', response_class=HTMLResponse)
async def admin_page():
    index_path = static_dir / 'index.html'
    if not index_path.exists():
        return HTMLResponse('<h3>No front-end found</h3>')
    return HTMLResponse(index_path.read_text(encoding='utf-8'))
















# 登录接口
