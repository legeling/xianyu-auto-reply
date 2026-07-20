#!/bin/bash
# ==========================================
# 闲鱼自动回复系统 - 本地源码构建并部署脚本
# 从源码构建Docker镜像，无需从远程仓库拉取
# 用法: bash build.sh [rebuild|start|stop|restart|logs|status]
# ==========================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

WORK_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$WORK_DIR/docker-compose.yml"
ENV_FILE="$WORK_DIR/.env"

# 项目容器名前缀
PROJECT_NAME="xianyu-auto-reply"
# 本项目的容器名列表
CONTAINERS=(
    "xianyu-mysql"
    "xianyu-redis"
    "xianyu-websocket"
    "xianyu-backend-web"
    "xianyu-scheduler"
    "xianyu-frontend"
)

echo "=========================================="
echo "  闲鱼自动回复系统 - 本地源码构建"
echo "=========================================="
echo ""

# ========== 检查环境 ==========
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    exit 1
fi

if docker compose version &> /dev/null; then
    DC="docker compose"
elif command -v docker-compose &> /dev/null; then
    DC="docker-compose"
else
    echo -e "${RED}错误: Docker Compose 未安装${NC}"
    exit 1
fi

export COMPOSE_PROJECT_NAME="$PROJECT_NAME"
DC_CMD="$DC -f $COMPOSE_FILE"

# 如果存在 .env 文件则使用
if [ -f "$ENV_FILE" ]; then
    DC_CMD="$DC -f $COMPOSE_FILE --env-file $ENV_FILE"
fi

echo "[信息] Docker: $(docker --version)"
echo "[信息] Compose: $DC"
echo "[信息] 项目目录: $WORK_DIR"
echo ""

# ========== 密钥工具函数 ==========
# 生成随机密钥（24位字母数字，安全无特殊字符）
generate_random_secret() {
    openssl rand -base64 24 | tr -d '=+/' | cut -c1-24
}

# 确保 .env 中某个 key 存在且非空；缺失或为空时写入随机值
# 注意：已存在的值必须保留不变，否则现有数据库密码被改会导致服务无法连接
ensure_env_secret() {
    local key="$1"
    local current
    current=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d '=' -f2- | tr -d '\r')
    if [ -z "$current" ]; then
        local value
        value=$(generate_random_secret)
        if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
            # key 存在但值为空，原地替换（sed -i.bak 兼容 GNU/BSD）
            sed -i.bak "s|^${key}=.*|${key}=${value}|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
        else
            echo "${key}=${value}" >> "$ENV_FILE"
        fi
        echo -e "${YELLOW}[安全] 已为 ${key} 生成随机密码/密钥，请妥善保管 $ENV_FILE${NC}"
    fi
}

# ========== 生成 .env（首次） ==========
generate_env() {
    if [ -f "$ENV_FILE" ]; then
        # 已存在 .env：仅补齐缺失/为空的密钥，已有值保持不变
        ensure_env_secret MYSQL_ROOT_PASSWORD
        ensure_env_secret MYSQL_PASSWORD
        ensure_env_secret REDIS_PASSWORD
        ensure_env_secret JWT_SECRET_KEY
        ensure_env_secret INTERNAL_API_TOKEN
        return
    fi
    echo -e "${YELLOW}[提示] 首次构建，生成默认 .env 配置${NC}"
    cat > "$ENV_FILE" << 'ENVEOF'
# ==========================================
# 闲鱼自动回复系统 - 环境变量配置（本地构建）
# ==========================================

# MySQL数据库（密码留空，构建脚本会自动生成随机值；已生成的值请勿随意修改）
MYSQL_ROOT_PASSWORD=
MYSQL_DATABASE=xianyu_data
MYSQL_USER=xianyu
MYSQL_PASSWORD=

# Redis
REDIS_PASSWORD=
REDIS_DB=0

# 说明：backend-web 的 JWT 密钥由数据库统一托管（首次启动自动生成并持久化），无需在此配置
# JWT_SECRET_KEY：promotion/backend 启动必填的 JWT 签名密钥（本地 promotion 服务使用，脚本自动生成随机值）
JWT_SECRET_KEY=
# INTERNAL_API_TOKEN：服务间内部 API 调用凭证（websocket/scheduler 校验 + backend-web/scheduler 调用方带头，脚本自动生成随机值）
INTERNAL_API_TOKEN=

# 端口
FRONTEND_PORT=9000
BACKEND_WEB_PORT=8089
WEBSOCKET_PORT=8090
SCHEDULER_PORT=8091

# 日志级别
LOG_LEVEL=INFO

# Token过期时间（分钟）
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# 定时任务间隔（秒）
REDELIVERY_INTERVAL=5
RATE_INTERVAL=20

# 验证码并发数
MAX_CAPTCHA_CONCURRENT=3
ENVEOF
    # 填充随机密钥（模板中密钥留空）
    ensure_env_secret MYSQL_ROOT_PASSWORD
    ensure_env_secret MYSQL_PASSWORD
    ensure_env_secret REDIS_PASSWORD
    ensure_env_secret JWT_SECRET_KEY
    ensure_env_secret INTERNAL_API_TOKEN
    echo -e "${GREEN}✓ 已生成 .env 文件，如需修改请编辑后重新运行${NC}"
    echo ""
    # 重新设置 DC_CMD 以包含 env-file
    DC_CMD="$DC -f $COMPOSE_FILE --env-file $ENV_FILE"
}

# ========== 停止并清理旧容器和镜像 ==========
clean_old() {
    echo -e "${YELLOW}[步骤 1/3] 停止并删除本项目旧容器...${NC}"
    $DC_CMD down 2>/dev/null || true

    # 删除可能残留的容器
    for c in "${CONTAINERS[@]}"; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${c}$"; then
            echo "  删除残留容器: $c"
            docker rm -f "$c" 2>/dev/null || true
        fi
    done
    echo -e "${GREEN}✓ 旧容器已清理${NC}"
    echo ""

    echo -e "${YELLOW}[步骤 2/3] 删除本项目旧镜像...${NC}"
    # 只删除本compose文件构建的镜像，不影响其他项目
    $DC_CMD down --rmi local 2>/dev/null || true
    echo -e "${GREEN}✓ 旧镜像已清理${NC}"
    echo ""
}

# ========== 从源码构建镜像 ==========
build_images() {
    echo -e "${YELLOW}[步骤 3/3] 从源码构建镜像（可能需要较长时间）...${NC}"
    echo ""

    echo -e "${CYAN}>>> 构建 Backend-Web 镜像...${NC}"
    $DC_CMD build backend-web
    echo -e "${GREEN}✓ Backend-Web 镜像构建完成${NC}"
    echo ""

    echo -e "${CYAN}>>> 构建 WebSocket 镜像（含Playwright）...${NC}"
    $DC_CMD build websocket
    echo -e "${GREEN}✓ WebSocket 镜像构建完成${NC}"
    echo ""

    echo -e "${CYAN}>>> 构建 Scheduler 镜像（含Playwright）...${NC}"
    $DC_CMD build scheduler
    echo -e "${GREEN}✓ Scheduler 镜像构建完成${NC}"
    echo ""

    echo -e "${CYAN}>>> 构建 Frontend 镜像（Node编译+Nginx）...${NC}"
    $DC_CMD build frontend
    echo -e "${GREEN}✓ Frontend 镜像构建完成${NC}"
    echo ""

    echo -e "${GREEN}✓ 全部镜像构建完成！${NC}"
}

# ========== 启动服务 ==========
start_services() {
    echo -e "${YELLOW}启动所有服务...${NC}"
    $DC_CMD up -d
    echo ""
    echo "[信息] 等待服务启动..."
    sleep 15
    $DC_CMD ps
    echo ""
    echo -e "${GREEN}=========================================="
    echo "  部署完成！"
    echo "==========================================${NC}"
    echo ""
    echo "服务访问地址："
    echo "  前端:         http://localhost:9000"
    echo "  Backend-Web:  http://localhost:8089"
    echo "  WebSocket:    http://localhost:8090"
    echo "  Scheduler:    http://localhost:8091"
    echo ""
    echo "默认账号: admin / admin123"
    echo ""
    echo "常用命令："
    echo "  查看日志: bash $0 logs"
    echo "  停止服务: bash $0 stop"
    echo "  重启服务: bash $0 restart"
    echo "  重新构建: bash $0 rebuild"
    echo "  服务状态: bash $0 status"
    echo ""
}

# ========== 命令分发 ==========
CMD="${1:-rebuild}"

case "$CMD" in
    rebuild)
        generate_env
        clean_old
        build_images
        start_services
        ;;
    start)
        generate_env
        echo -e "${YELLOW}启动服务...${NC}"
        $DC_CMD up -d
        sleep 10
        $DC_CMD ps
        ;;
    stop)
        echo -e "${YELLOW}停止服务...${NC}"
        $DC_CMD down
        echo -e "${GREEN}✓ 服务已停止${NC}"
        ;;
    restart)
        echo -e "${YELLOW}重启服务...${NC}"
        $DC_CMD restart
        sleep 10
        $DC_CMD ps
        ;;
    logs)
        $DC_CMD logs -f --tail=100
        ;;
    status)
        $DC_CMD ps
        ;;
    *)
        echo "用法: bash $0 [rebuild|start|stop|restart|logs|status]"
        echo ""
        echo "  rebuild  - 删除旧容器和镜像，重新从源码构建并启动（默认）"
        echo "  start    - 启动服务（不重新构建）"
        echo "  stop     - 停止所有服务"
        echo "  restart  - 重启所有服务"
        echo "  logs     - 查看实时日志"
        echo "  status   - 查看服务状态"
        exit 1
        ;;
esac
