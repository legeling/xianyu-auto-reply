#!/bin/bash
# ==========================================
# 闲鱼自动回复系统 - 一键部署脚本
# 自动生成远程镜像版 docker-compose.deploy.yml 并拉取镜像启动
# 用法: bash deploy.sh
# ==========================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

WORK_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$WORK_DIR/docker-compose.deploy.yml"
ENV_FILE="$WORK_DIR/.env"

echo "=========================================="
echo "  闲鱼自动回复系统 - 一键部署"
echo "=========================================="
echo ""

# ========== 检查环境 ==========
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装，请先安装 Docker${NC}"
    echo "安装教程: https://docs.docker.com/get-docker/"
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

export COMPOSE_PROJECT_NAME=xianyu-auto-reply
DC_CMD="$DC -f $COMPOSE_FILE --env-file $ENV_FILE"

echo -e "${CYAN}[信息] Docker: $(docker --version)${NC}"
echo -e "${CYAN}[信息] Compose: $DC${NC}"
echo -e "${CYAN}[信息] 项目目录: $WORK_DIR${NC}"
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

# ========== 生成 .env 配置文件 ==========
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}[提示] 首次部署，生成默认配置文件 .env${NC}"
    cat > "$ENV_FILE" << 'ENVEOF'
# ==========================================
# 闲鱼自动回复系统 - 环境变量配置
# ==========================================

# MySQL数据库配置（Docker内置，自动创建）
# 密码留空，部署脚本会自动生成随机值；已生成的值请勿随意修改（否则数据库无法登录）
MYSQL_ROOT_PASSWORD=
MYSQL_DATABASE=xianyu_data
MYSQL_USER=xianyu
MYSQL_PASSWORD=

# Redis缓存配置（Docker内置）
REDIS_PASSWORD=
REDIS_DB=0

# 说明：backend-web 的 JWT 密钥由数据库统一托管（首次启动自动生成并持久化），无需在此配置
# JWT_SECRET_KEY：promotion/backend 启动必填的 JWT 签名密钥（本地 promotion 服务使用，脚本自动生成随机值）
JWT_SECRET_KEY=
# INTERNAL_API_TOKEN：服务间内部 API 调用凭证（websocket/scheduler 校验 + backend-web/scheduler 调用方带头，脚本自动生成随机值）
INTERNAL_API_TOKEN=

# 端口配置
FRONTEND_PORT=9000
BACKEND_WEB_PORT=8089
WEBSOCKET_PORT=8090
SCHEDULER_PORT=8091

# 镜像配置
IMAGE_REGISTRY=registry.cn-shanghai.aliyuncs.com/zhinian-software
IMAGE_TAG=latest

# 基础镜像（MySQL / Redis，从阿里云仓库拉取，由 sync_base_images.sh 同步上传）
MYSQL_IMAGE=registry.cn-shanghai.aliyuncs.com/zhinian-software/xianyu-mysql:8.0
REDIS_IMAGE=registry.cn-shanghai.aliyuncs.com/zhinian-software/xianyu-redis:7-alpine

# 日志级别
LOG_LEVEL=INFO

# SQL 日志开关：true=打印每条执行的完整 SQL（默认，便于排查）；高并发生产环境可设为 false
SQL_ECHO=true

# IM Token 缓存（xy_token_cache 表）随机过期时间区间（小时），不配置默认 5~10 小时
TOKEN_CACHE_TTL_MIN_HOURS=5
TOKEN_CACHE_TTL_MAX_HOURS=10

# Token过期时间（分钟）
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# 定时任务间隔（分钟）
REDELIVERY_INTERVAL=5
RATE_INTERVAL=20

# 验证码并发数
MAX_CAPTCHA_CONCURRENT=3

# WebSocket 启动时是否自动连接账号
AUTO_START_WEBSOCKET=true
# 滑块验证 DrissionPage 兜底引擎（主引擎失败后重试）：开关 / 超时秒 / 无头
CAPTCHA_DRISSIONPAGE_FALLBACK_ENABLED=true
CAPTCHA_DRISSIONPAGE_TIMEOUT=25
CAPTCHA_DRISSIONPAGE_HEADLESS=true

# 分销卡券上游服务基址（「分销卡券」页面提货 + 个人设置一键创建对接卡密秘钥共用此基址）
# 上游 https 证书已于 2026-04-24 过期，暂保留 http；证书续期后请改为 https://backend.zhinianboke.com
CARD_DOCK_BASE_URL=http://backend.zhinianboke.com
# 个人设置「对接卡密秘钥」一键创建密钥的鉴权 key（基址复用 CARD_DOCK_BASE_URL）
# 必填：无默认值，请向上游申请后填写
EXTERNAL_API_KEY=

# 前端公网访问地址（用于生成前端页面分享链接，留空则使用默认）
FRONTEND_PUBLIC_URL=
# 启动时是否自动启动 Goofish 定时采集任务
AUTO_START_CRAWL_JOBS=true
# 远程官方服务基址（仪表盘广告、系统公告 = 本地内容 + 远程官方内容）
REMOTE_OFFICIAL_BASE_URL=https://xy.zhinianboke.com
# 是否启用远程官方广告合并展示（官方服务器自身部署建议设为 false）
ENABLE_REMOTE_ADS=true
# 是否启用远程官方公告合并展示（官方服务器自身部署建议设为 false）
ENABLE_REMOTE_ANNOUNCEMENTS=true
# 是否启用远程官方弹窗公告合并展示（官方服务器自身部署建议设为 false）
ENABLE_REMOTE_POPUP_ANNOUNCEMENTS=true
ENVEOF
    echo -e "${GREEN}✓ 已生成 .env 文件${NC}"
    echo -e "${YELLOW}[提示] 如需修改配置（如端口等），请编辑 $ENV_FILE 后重新运行${NC}"
    echo ""
fi

# 补齐缺失/为空的密钥（已存在的值保持不变；老部署的密码不受影响）
ensure_env_secret MYSQL_ROOT_PASSWORD
ensure_env_secret MYSQL_PASSWORD
ensure_env_secret REDIS_PASSWORD
ensure_env_secret JWT_SECRET_KEY
ensure_env_secret INTERNAL_API_TOKEN

# ========== 生成 docker-compose.deploy.yml（远程镜像版） ==========
echo "[信息] 生成 docker-compose.deploy.yml（远程镜像版）..."
cat > "$COMPOSE_FILE" << 'COMPOSEEOF'
# Docker Compose 配置文件 - 远程镜像部署版
# 闲鱼自动回复系统 - 从镜像仓库拉取预构建镜像
# 由 deploy.sh 自动生成，请勿手动修改

services:
  # ====== 基础设施 ======

  # MySQL数据库（默认从阿里云仓库拉取，可通过 MYSQL_IMAGE 覆盖）
  mysql:
    image: ${MYSQL_IMAGE:-registry.cn-shanghai.aliyuncs.com/zhinian-software/xianyu-mysql:8.0}
    container_name: xianyu-mysql
    restart: unless-stopped
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD must be set in .env}
      - MYSQL_DATABASE=${MYSQL_DATABASE:-xianyu_data}
      - MYSQL_USER=${MYSQL_USER:-xianyu}
      - MYSQL_PASSWORD=${MYSQL_PASSWORD:?MYSQL_PASSWORD must be set in .env}
      - TZ=Asia/Shanghai
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --max-connections=300
      - --max-allowed-packet=256M
      - --default-time-zone=+08:00
    volumes:
      - ./xianyu_auto_reply/mysql/data:/var/lib/mysql
    networks:
      - xianyu-network
    healthcheck:
      # 密码通过 MYSQL_PWD 环境变量传入，避免出现在进程命令行参数中（ps 不可见）
      test: ["CMD-SHELL", "MYSQL_PWD=$${MYSQL_ROOT_PASSWORD} mysqladmin ping -h 127.0.0.1 -u root --silent"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s

  # Redis缓存（默认从阿里云仓库拉取，可通过 REDIS_IMAGE 覆盖）
  redis:
    image: ${REDIS_IMAGE:-registry.cn-shanghai.aliyuncs.com/zhinian-software/xianyu-redis:7-alpine}
    container_name: xianyu-redis
    restart: unless-stopped
    command: >
      redis-server
      --requirepass ${REDIS_PASSWORD:?REDIS_PASSWORD must be set in .env}
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
    environment:
      - TZ=Asia/Shanghai
    volumes:
      - ./xianyu_auto_reply/redis/data:/data
    networks:
      - xianyu-network
    healthcheck:
      # 密码通过 REDISCLI_AUTH 环境变量传入，避免出现在进程命令行参数中（ps 不可见）
      test: ["CMD-SHELL", "REDISCLI_AUTH=$${REDIS_PASSWORD} redis-cli --no-auth-warning ping | grep -q PONG"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  # ====== 应用服务（远程镜像） ======

  # Backend-Web 服务
  backend-web:
    image: ${IMAGE_REGISTRY:-registry.cn-shanghai.aliyuncs.com/zhinian-software}/xianyu-backend-web:${IMAGE_TAG:-latest}
    container_name: xianyu-backend-web
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - MYSQL_HOST=mysql
      - MYSQL_PORT=3306
      - MYSQL_USER=${MYSQL_USER:-xianyu}
      - MYSQL_PASSWORD=${MYSQL_PASSWORD:?MYSQL_PASSWORD must be set in .env}
      - MYSQL_DATABASE=${MYSQL_DATABASE:-xianyu_data}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD:?REDIS_PASSWORD must be set in .env}
      - REDIS_DB=${REDIS_DB:-0}
      - BACKEND_WEB_PORT=8089
      - HOST=0.0.0.0
      - JWT_ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES:-1440}
      - REFRESH_TOKEN_EXPIRE_MINUTES=${REFRESH_TOKEN_EXPIRE_MINUTES:-10080}
      - CORS_ORIGINS=*
      - WEBSOCKET_SERVICE_URL=http://websocket:8090
      - SCHEDULER_SERVICE_URL=http://scheduler:8091
      # 服务间内部 API 调用凭证（websocket/scheduler 校验 + backend-web/scheduler 调用方带头）
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN:?INTERNAL_API_TOKEN must be set in .env}
      - STATIC_DIR=/app/static
      - BACKUP_DIR=/app/backups
      - BACKEND_WEB_PUBLIC_URL=${BACKEND_WEB_PUBLIC_URL:-}
      # 上游 https 证书已于 2026-04-24 过期，暂保留 http；证书续期后请改为 https://backend.zhinianboke.com
      - CARD_DOCK_BASE_URL=${CARD_DOCK_BASE_URL:-http://backend.zhinianboke.com}
      # 必填：向上游申请的鉴权 key，无默认值，请在 .env 中配置
      - EXTERNAL_API_KEY=${EXTERNAL_API_KEY:-}
      - FRONTEND_PUBLIC_URL=${FRONTEND_PUBLIC_URL:-}
      - AUTO_START_CRAWL_JOBS=${AUTO_START_CRAWL_JOBS:-true}
      - REMOTE_OFFICIAL_BASE_URL=${REMOTE_OFFICIAL_BASE_URL:-https://xy.zhinianboke.com}
      - ENABLE_REMOTE_ADS=${ENABLE_REMOTE_ADS:-true}
      - ENABLE_REMOTE_ANNOUNCEMENTS=${ENABLE_REMOTE_ANNOUNCEMENTS:-true}
      - ENABLE_REMOTE_POPUP_ANNOUNCEMENTS=${ENABLE_REMOTE_POPUP_ANNOUNCEMENTS:-true}
      - BROWSER_HEADLESS=true
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - SQL_ECHO=${SQL_ECHO:-true}
      - TOKEN_CACHE_TTL_MIN_HOURS=${TOKEN_CACHE_TTL_MIN_HOURS:-5}
      - TOKEN_CACHE_TTL_MAX_HOURS=${TOKEN_CACHE_TTL_MAX_HOURS:-10}
      - TZ=Asia/Shanghai
    volumes:
      - ./xianyu_auto_reply/logs/backend_web:/app/backend-web/logs
      - ./xianyu_auto_reply/static:/app/static
      - ./xianyu_auto_reply/backups:/app/backups
    ports:
      - "${BACKEND_WEB_PORT:-8089}:8089"
    networks:
      - xianyu-network
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8089/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # WebSocket 服务
  websocket:
    image: ${IMAGE_REGISTRY:-registry.cn-shanghai.aliyuncs.com/zhinian-software}/xianyu-websocket:${IMAGE_TAG:-latest}
    container_name: xianyu-websocket
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - MYSQL_HOST=mysql
      - MYSQL_PORT=3306
      - MYSQL_USER=${MYSQL_USER:-xianyu}
      - MYSQL_PASSWORD=${MYSQL_PASSWORD:?MYSQL_PASSWORD must be set in .env}
      - MYSQL_DATABASE=${MYSQL_DATABASE:-xianyu_data}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD:?REDIS_PASSWORD must be set in .env}
      - REDIS_DB=${REDIS_DB:-0}
      - WEBSOCKET_PORT=8090
      - HOST=0.0.0.0
      - MAX_CAPTCHA_CONCURRENT=${MAX_CAPTCHA_CONCURRENT:-3}
      - BROWSER_HEADLESS=true
      - AUTO_START_WEBSOCKET=${AUTO_START_WEBSOCKET:-true}
      - CAPTCHA_DRISSIONPAGE_FALLBACK_ENABLED=${CAPTCHA_DRISSIONPAGE_FALLBACK_ENABLED:-true}
      - CAPTCHA_DRISSIONPAGE_TIMEOUT=${CAPTCHA_DRISSIONPAGE_TIMEOUT:-25}
      - CAPTCHA_DRISSIONPAGE_HEADLESS=${CAPTCHA_DRISSIONPAGE_HEADLESS:-true}
      - BACKEND_WEB_SERVICE_URL=http://backend-web:8089
      # 服务间内部 API 调用凭证（internal API 校验 + 回调 backend-web 带头）
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN:?INTERNAL_API_TOKEN must be set in .env}
      - STATIC_DIR=/app/static
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - SQL_ECHO=${SQL_ECHO:-true}
      - TOKEN_CACHE_TTL_MIN_HOURS=${TOKEN_CACHE_TTL_MIN_HOURS:-5}
      - TOKEN_CACHE_TTL_MAX_HOURS=${TOKEN_CACHE_TTL_MAX_HOURS:-10}
      - TZ=Asia/Shanghai
    volumes:
      - ./xianyu_auto_reply/logs/websocket:/app/websocket/logs
      - ./xianyu_auto_reply/static:/app/static
      - ./xianyu_auto_reply/browser_data:/app/browser_data
    ports:
      # 仅绑定回环：WebSocket 服务仅供宿主机/容器间内部调用，不对公网暴露
      - "127.0.0.1:${WEBSOCKET_PORT:-8090}:8090"
    networks:
      - xianyu-network
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
      backend-web:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8090/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # Scheduler 服务
  scheduler:
    image: ${IMAGE_REGISTRY:-registry.cn-shanghai.aliyuncs.com/zhinian-software}/xianyu-scheduler:${IMAGE_TAG:-latest}
    container_name: xianyu-scheduler
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - MYSQL_HOST=mysql
      - MYSQL_PORT=3306
      - MYSQL_USER=${MYSQL_USER:-xianyu}
      - MYSQL_PASSWORD=${MYSQL_PASSWORD:?MYSQL_PASSWORD must be set in .env}
      - MYSQL_DATABASE=${MYSQL_DATABASE:-xianyu_data}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD:?REDIS_PASSWORD must be set in .env}
      - REDIS_DB=${REDIS_DB:-0}
      - SCHEDULER_PORT=8091
      - HOST=0.0.0.0
      - REDELIVERY_INTERVAL=${REDELIVERY_INTERVAL:-5}
      - RATE_INTERVAL=${RATE_INTERVAL:-20}
      - WEBSOCKET_SERVICE_URL=http://websocket:8090
      - BACKEND_WEB_SERVICE_URL=http://backend-web:8089
      # 服务间内部 API 调用凭证（internal API 校验 + 调用 websocket/backend-web 带头）
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN:?INTERNAL_API_TOKEN must be set in .env}
      - STATIC_DIR=/app/static
      - BACKUP_DIR=/app/backups
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - SQL_ECHO=${SQL_ECHO:-true}
      - TZ=Asia/Shanghai
    volumes:
      - ./xianyu_auto_reply/logs/scheduler:/app/scheduler/logs
      - ./xianyu_auto_reply/static:/app/static:ro
      - ./xianyu_auto_reply/backups:/app/backups
    ports:
      # 仅绑定回环：Scheduler 服务仅供宿主机/容器间内部调用，不对公网暴露
      - "127.0.0.1:${SCHEDULER_PORT:-8091}:8091"
    networks:
      - xianyu-network
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
      websocket:
        condition: service_healthy
      backend-web:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8091/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # 前端服务
  frontend:
    image: ${IMAGE_REGISTRY:-registry.cn-shanghai.aliyuncs.com/zhinian-software}/xianyu-frontend:${IMAGE_TAG:-latest}
    container_name: xianyu-frontend
    restart: unless-stopped
    environment:
      - TZ=Asia/Shanghai
    ports:
      # 前端容器内 nginx 以非 root 运行监听 8080（见 docker/frontend/Dockerfile）
      - "${FRONTEND_PORT:-9000}:8080"
    networks:
      - xianyu-network
    depends_on:
      backend-web:
        condition: service_healthy

networks:
  xianyu-network:
    driver: bridge
COMPOSEEOF
echo -e "${GREEN}✓ docker-compose.deploy.yml 已生成${NC}"
echo ""

# ========== 检测并清理加密版残留 ==========
ENC_CONTAINERS=(
    "xianyu-enc-frontend"
    "xianyu-enc-backend-web"
    "xianyu-enc-websocket"
    "xianyu-enc-scheduler"
    "xianyu-enc-mysql"
    "xianyu-enc-redis"
)

enc_found=0
for container in "${ENC_CONTAINERS[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        enc_found=1
        break
    fi
done

if [ $enc_found -eq 1 ]; then
    echo -e "${YELLOW}[信息] 检测到加密版容器，清理中（保留数据卷）...${NC}"
    for container in "${ENC_CONTAINERS[@]}"; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo -e "${CYAN}  停止并删除容器: ${container}${NC}"
            docker stop "$container" 2>/dev/null || true
            docker rm "$container" 2>/dev/null || true
        fi
    done
    # 清理加密版应用镜像
    for name in "xianyu-enc-frontend" "xianyu-enc-backend-web" "xianyu-enc-websocket" "xianyu-enc-scheduler"; do
        image_ids=$(docker images --filter "reference=*/${name}*" --format '{{.ID}}' 2>/dev/null | sort -u)
        for id in $image_ids; do
            docker rmi "$id" --force 2>/dev/null || true
        done
    done
    # 清理加密版网络
    for enc_network in $(docker network ls --format '{{.Name}}' | grep -i "enc" | grep -i "xianyu"); do
        docker network rm "$enc_network" 2>/dev/null || true
    done
    echo -e "${GREEN}✓ 加密版已清理（数据卷已保留）${NC}"
    echo ""
fi

# ========== 创建挂载目录 ==========
mkdir -p \
    "$WORK_DIR/xianyu_auto_reply/mysql/data" \
    "$WORK_DIR/xianyu_auto_reply/redis/data" \
    "$WORK_DIR/xianyu_auto_reply/logs/backend_web" \
    "$WORK_DIR/xianyu_auto_reply/logs/websocket" \
    "$WORK_DIR/xianyu_auto_reply/logs/scheduler" \
    "$WORK_DIR/xianyu_auto_reply/static" \
    "$WORK_DIR/xianyu_auto_reply/backups" \
    "$WORK_DIR/xianyu_auto_reply/browser_data"

# ========== 部署 ==========
echo -e "${YELLOW}步骤 1/3: 停止旧容器（仅本项目）...${NC}"
$DC_CMD down 2>/dev/null || true
echo -e "${GREEN}✓ 旧容器已清理${NC}"

echo ""
echo -e "${YELLOW}步骤 2/3: 拉取最新镜像...${NC}"
$DC_CMD pull
echo -e "${GREEN}✓ 镜像拉取完成${NC}"

echo ""
echo -e "${YELLOW}步骤 3/3: 启动服务...${NC}"
$DC_CMD up -d
echo -e "${GREEN}✓ 服务已启动${NC}"

echo ""
echo "[信息] 等待服务启动..."
sleep 15
$DC_CMD ps

# 读取端口配置
frontend_port=$(grep -E "^FRONTEND_PORT=" "$ENV_FILE" 2>/dev/null | cut -d '=' -f2 | tr -d '\r' || echo "9000")
backend_web_port=$(grep -E "^BACKEND_WEB_PORT=" "$ENV_FILE" 2>/dev/null | cut -d '=' -f2 | tr -d '\r' || echo "8089")
websocket_port=$(grep -E "^WEBSOCKET_PORT=" "$ENV_FILE" 2>/dev/null | cut -d '=' -f2 | tr -d '\r' || echo "8090")
scheduler_port=$(grep -E "^SCHEDULER_PORT=" "$ENV_FILE" 2>/dev/null | cut -d '=' -f2 | tr -d '\r' || echo "8091")

frontend_port="${frontend_port:-9000}"
backend_web_port="${backend_web_port:-8089}"
websocket_port="${websocket_port:-8090}"
scheduler_port="${scheduler_port:-8091}"

echo ""
echo -e "${GREEN}=========================================="
echo "  部署完成！"
echo "==========================================${NC}"
echo ""
echo "服务访问地址："
echo "  前端:        http://服务器IP:${frontend_port}"
echo "  Backend-Web: http://服务器IP:${backend_web_port}"
echo "  WebSocket:   http://127.0.0.1:${websocket_port}（仅本机回环，不对外暴露）"
echo "  Scheduler:   http://127.0.0.1:${scheduler_port}（仅本机回环，不对外暴露）"
echo ""
echo "常用命令："
echo "  查看日志: $DC_CMD logs -f"
echo "  停止服务: $DC_CMD down"
echo "  重启服务: $DC_CMD restart"
echo "  更新版本: bash update.sh"
echo ""
