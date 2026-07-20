# 闲鱼自动回复系统

基于 FastAPI + React + MySQL + Redis + Playwright 的闲鱼多账号自动化系统。

主系统负责账号管理、消息收发、自动回复、自动发货、商品发布与后台管理；`promotion` 子项目负责返佣账号、选品规则、素材库、发布规则、删除规则和相关修复任务。

## 🔴 说明

> **🔴 诚邀各位开发者提交pr，完善系统**
>
> **🔴 承接各类项目定制，各类项目均可，有需要可联系，另外我菜，不一定都会**

## 🔴 最新源码地址(建议转存)

> 🔴 我用夸克网盘给你分享了「自动发货」，点击链接或复制整段内容，打开「夸克网盘APP」即可获取。
> 
> 🔴 /~79313YhCQU~:/
> 
> 🔴 **链接：https://pan.quark.cn/s/af567356cba7**

## 交流群

| 微信群 | QQ群 | 微信公众号 | Telegram | 赞赏支持 |
|:---:|:---:|:---:|:---:|:---:|
| ![微信群](https://xy.zhinianboke.com/static/qrcode/wechat-group.jpg) | ![QQ群](https://xy.zhinianboke.com/static/qrcode/qq-group.jpg) | ![微信公众号](https://xy.zhinianboke.com/static/qrcode/wechat-official-group.jpg) | ![Telegram](https://xy.zhinianboke.com/static/qrcode/telegram-group.png) | ![赞赏支持](https://xy.zhinianboke.com/static/qrcode/reward-group.png) |
| 扫码加入微信交流群 | 扫码加入QQ交流群 | 关注公众号发送"最新源码"获取最新代码 | 扫码加入Telegram群 | 如果觉得好用，请作者喝杯咖啡 |

如群二维码过期，请关注公众号获取最新群链接。

---

## 功能概览

### 主系统

| 模块 | 说明 |
|------|------|
| 多账号管理 | 支持多个闲鱼账号登录、状态切换、Cookie 维护与登录续期 |
| 自动回复 | 支持文本关键词、图片关键词、默认回复、商品专属回复 |
| AI 回复 | 支持大模型上下文对话与智能回复 |
| 自动发货 | 支持卡券、虚拟商品、自动补发、发送结果记录 |
| 在线聊天 | 支持会话列表、消息收发、聊天联动 |
| 商品发布 | 支持素材库、地址库、单品发布、批量发布、发布日志 |
| 订单与评价 | 订单拉取、自动评价、求小红花、状态跟踪 |
| 商品采集与分销 | Goofish 采集、货源管理、对接记录、结算链路 |
| 通知与风控 | 支持消息通知、风控日志、系统反馈与公告管理 |

### 返佣子系统

| 模块 | 说明 |
|------|------|
| 返佣账号 | 返佣账号登录、状态管理、Cookie 维护 |
| 选品规则 | 按规则抓取候选商品并自动写入素材库 |
| 素材库 | 管理标题、图片、详情、淘口令、短链、库存、发布状态 |
| 发布规则 | 定时发布返佣商品，复用公共发布能力 |
| 删除规则 | 定时删除已发布商品 |
| 补偿任务 | 已发布商品 ID 回写、短链修复、卡券补偿等 |

## 技术栈

### 后端与自动化

| 技术 | 说明 |
|------|------|
| FastAPI | 主系统与返佣后端 API 服务 |
| SQLAlchemy 2.0 | ORM 与数据库访问 |
| MySQL 8.0 | 主数据存储 |
| Redis 7 | 缓存、会话与任务辅助 |
| Playwright | 登录、Cookie 刷新、发布等浏览器自动化 |
| APScheduler | 定时任务调度 |
| Loguru | 日志管理 |

### 前端

| 技术 | 说明 |
|------|------|
| React 18 + TypeScript | 主系统与返佣前端 |
| Vite | 开发与构建 |
| TailwindCSS | 主系统 UI 样式 |
| Zustand | 状态管理 |
| Lucide React | 图标体系 |

### 部署

| 技术 | 说明 |
|------|------|
| Docker / Docker Compose | 容器化部署 |
| Nginx | 前端静态资源与反向代理 |

## 系统要求

### 开发环境

- Python 3.11+
- Node.js 18+
- MySQL 8.0+
- Redis 6+
- Chromium / Chrome（Playwright 相关功能）

### 生产环境

- Docker 20.10+
- Docker Compose 2.0+
- 最低 2 核 CPU / 4GB 内存
- 推荐 4 核 CPU / 8GB 内存

## 分支管理

本仓库的上游为 [zhinianboke/xianyu-auto-reply](https://github.com/zhinianboke/xianyu-auto-reply)。分支模型（`main` 稳定基线 / `dev` 日常开发 / `feature/*` 短期功能）与上游同步流程见 [BRANCHING.md](BRANCHING.md)。

## 项目结构

```text
xianyu-auto-reply/
├── backend-web/          # 主 Web API 服务（端口 8089）
├── websocket/            # 闲鱼连接与消息处理服务（端口 8090）
├── scheduler/            # 定时任务服务（端口 8091）
├── common/               # 主系统与返佣系统共享模块
├── frontend/             # 主系统前端（端口 9000）
├── launcher/             # Windows 桌面启动器（Nuitka 打包为 EXE）
├── promotion/
│   ├── backend/          # 返佣后端（端口 8092）
│   └── frontend/         # 返佣前端（端口 9001）
├── scripts/              # CI/CD 与工具脚本
├── docker/frontend/      # 前端 Dockerfile 与 Nginx 配置
├── docker-compose.yml    # 本地源码构建编排
├── deploy.sh             # 一键部署脚本（自动生成远程镜像版 compose）
├── update.sh             # 一键更新脚本（拉取最新远程镜像）
├── build.sh              # 本地源码全量构建脚本
├── build_frontend.sh     # 单独构建并重启 Frontend
├── build_backend_web.sh  # 单独构建并重启 Backend-Web
├── build_websocket.sh    # 单独构建并重启 WebSocket
├── build_scheduler.sh    # 单独构建并重启 Scheduler
├── EXE打包构建.bat       # Windows 桌面启动器打包脚本
├── 离线依赖打包.bat      # Windows 离线依赖打包脚本
└── README.md
```

### 服务职责

| 服务 | 默认端口 | 说明 |
|------|----------|------|
| `frontend` | 9000 | 主系统前端 |
| `backend-web` | 8089 | 主系统 API 网关、业务接口 |
| `websocket` | 8090 | 闲鱼 WebSocket、消息收发、登录与订单联动 |
| `scheduler` | 8091 | 定时任务执行器 |
| `promotion/backend` | 8092 | 返佣后端 API |
| `promotion/frontend` | 9001 | 返佣前端 |

### 架构说明

- 主系统采用多服务拆分：
  - `frontend` 负责界面与交互
  - `backend-web` 负责大部分业务 API
  - `websocket` 负责闲鱼实时连接、扫码登录、消息处理
  - `scheduler` 负责自动发货、评价、订单拉取、Cookie 刷新等定时任务
  - `common` 提供模型、数据库、自检、公共服务与工具
- 返佣子系统位于 `promotion/` 目录，前后端独立，当前不在根目录 Docker Compose 编排内
- 主系统三个后端服务都提供 `/health` 健康检查接口
- Docker 依赖链：mysql/redis → backend-web → websocket → scheduler；frontend → backend-web

## 快速开始

### 方式一：服务器一键部署（推荐）

服务器已安装 Docker 与 Docker Compose 后，直接执行一键部署脚本即可：

```bash
curl -fsSL https://xy-update.zhinianboke.com/deploy.sh | sed 's/\r$//' | bash
```

该脚本会自动完成部署所需的配置生成、镜像拉取、旧容器清理与服务启动。

更新版本，直接执行一键更新脚本即可：

```bash
curl -fsSL https://xy-update.zhinianboke.com/update.sh | sed 's/\r$//' | bash
```

### 方式二：克隆仓库部署

```bash
git clone https://github.com/zhinianboke/xianyu-auto-reply.git
cd xianyu-auto-reply
bash deploy.sh
```

- 首次运行会自动生成 `.env` 配置文件和 `docker-compose.deploy.yml`
- 从阿里云镜像仓库拉取预构建镜像并启动
- 如果检测到加密版容器会自动清理（保留数据卷）
- 部署完成后默认访问地址：
  - 前端：`http://服务器IP:9000`
  - API 文档：`http://服务器IP:8089/docs`
  - 默认账号：`admin` / `admin123`

后续更新：

```bash
bash update.sh
```

### 方式三：本地源码 Docker 构建

```bash
bash build.sh rebuild
```

常用命令：

| 命令 | 说明 |
|------|------|
| `bash build.sh rebuild` | 删除旧容器与镜像，重新构建并启动 |
| `bash build.sh start` | 启动服务 |
| `bash build.sh stop` | 停止服务 |
| `bash build.sh restart` | 重启服务 |
| `bash build.sh logs` | 查看实时日志 |
| `bash build.sh status` | 查看服务状态 |

单独重建某个服务（不影响其他服务）：

```bash
bash build_frontend.sh      # 重建前端
bash build_backend_web.sh   # 重建 Backend-Web
bash build_websocket.sh     # 重建 WebSocket
bash build_scheduler.sh     # 重建 Scheduler
```

### 方式四：源码本地开发

#### 1. 准备基础服务

可以使用本机 MySQL / Redis，也可以仅用 Docker 启动基础设施：

```bash
docker compose up -d mysql redis
```

#### 2. 创建服务配置

主系统常用 `.env` 配置示例：

```env
ENVIRONMENT=development
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=xianyu_data
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
CORS_ORIGINS=*
BACKEND_WEB_PORT=8089
WEBSOCKET_PORT=8090
SCHEDULER_PORT=8091
WEBSOCKET_SERVICE_URL=http://127.0.0.1:8090
SCHEDULER_SERVICE_URL=http://127.0.0.1:8091
BACKEND_WEB_SERVICE_URL=http://127.0.0.1:8089
STATIC_DIR=static
TZ=Asia/Shanghai
```

#### 3. 启动主系统后端

```bash
# Backend-Web 服务
cd backend-web
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
python -m playwright install chromium
python main.py
```

```bash
# WebSocket 服务
cd websocket
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
python -m playwright install chromium
python main.py
```

```bash
# Scheduler 服务
cd scheduler
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
python -m playwright install chromium
python main.py
```

#### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

#### 5. 使用命令行客户端

项目提供一个正式 CLI 包，直接调用 `backend-web` 已有 API，适合不想在页面里反复点击的批量查看和基础操作。

CLI 目录结构：

```text
xianyu_cli/
├── client.py            # HTTP 客户端与认证头处理
├── config.py            # 本地配置与 token 存储
├── output.py            # 表格/JSON 输出
├── openapi.py           # OpenAPI 路由发现、功能分组与 operationId 调用
├── frontend.py          # 前端 API 调用静态扫描与覆盖审计
├── websocket_client.py  # 在线聊天实时推送 WebSocket 监听
├── request_args.py      # JSON、表单、文件上传和下载参数解析
├── webmap.py            # 前端路由/页面到后端功能模块的映射
├── main.py              # xianyu-cli 入口
└── commands/            # 按功能拆分的命令模块
    ├── accounts.py      # 账号快捷命令
    ├── auth.py          # 登录、token 和当前用户
    ├── items.py         # 商品快捷查询
    ├── orders.py        # 订单快捷查询
    ├── settings.py      # 系统设置快捷命令
    ├── web.py           # 按网页版页面浏览、覆盖检查和调用 API
    ├── features.py      # 按后端功能模块浏览和调用 API
    └── routes.py        # 按原始 OpenAPI operationId 调用 API
```

```bash
# 在项目根目录执行
python scripts/xianyu_cli.py config set-url http://127.0.0.1:8089

# 检查后端地址、健康检查、OpenAPI 和 token 是否可用
python scripts/xianyu_cli.py doctor

# 也可以离线读取本地 OpenAPI JSON 做接口审计
python scripts/xianyu_cli.py --openapi-file ./openapi.json web coverage

# 登录后会把 token 保存到 ~/.xianyu-auto-reply-cli.json
python scripts/xianyu_cli.py auth login -u admin

# 查看当前登录用户
python scripts/xianyu_cli.py auth whoami

# 常用查询
python scripts/xianyu_cli.py health
python scripts/xianyu_cli.py accounts list --page-size 50
python scripts/xianyu_cli.py items list --account-id <账号ID>
python scripts/xianyu_cli.py orders --search <订单号或商品ID>
python scripts/xianyu_cli.py keywords --account-id <账号ID>

# 常用操作
python scripts/xianyu_cli.py accounts disable <账号ID>
python scripts/xianyu_cli.py accounts enable <账号ID>
python scripts/xianyu_cli.py accounts remark <账号ID> "备用账号"

# Cookie 较长时建议从 stdin 输入
pbpaste | python scripts/xianyu_cli.py accounts cookie <账号ID>

# 兜底：直接调用任意 backend-web API
python scripts/xianyu_cli.py api GET /api/v1/system-settings
python scripts/xianyu_cli.py api PUT /api/v1/system-settings/registration_enabled -d '{"value":"false"}'

# 文件上传、导入和导出也走同一套调用能力
python scripts/xianyu_cli.py api POST /api/v1/upload/upload-image -F image=./card.png
python scripts/xianyu_cli.py api POST /api/v1/cookies/import -F file=./accounts.xlsx -f enable_all=true
python scripts/xianyu_cli.py api POST /api/v1/cookies/export -d '{}' -o ./accounts_export.xlsx
```

`features` 和 `routes` 命令会读取后端 `/openapi.json`。`features` 按网页版功能模块分组，适合日常使用；`routes` 保留原始 OpenAPI 视角，适合精确排查。

`web ops`、`features ops` 和 `routes list` 输出里的 `inputs` 字段用于提示调用参数：
`path:name*` 对应 `-p name=...`，`query:name` 对应 `-q name=...`，`body:json*` 对应 `-d '{...}'`，`body:multipart*` 对应 `-f key=value` / `-F file=...`；`*` 表示 OpenAPI 标记为必填。

如果不想手写参数，可以先生成完整调用模板。默认只生成必填参数；加 `--include-optional` 会把 OpenAPI 里的可选字段也放进模板：

```bash
python scripts/xianyu_cli.py web examples accounts --search import
python scripts/xianyu_cli.py features examples cookies --search status
python scripts/xianyu_cli.py routes template list_cookie_details_paginated_api_v1_cookies_details_paginated_get
```

`web` 命令按前端页面组织接口，更接近网页版菜单：

```bash
# 列出网页版页面与对应 API 功能模块
python scripts/xianyu_cli.py web pages

# 检查网页版页面是否都有后端 OpenAPI 映射
python scripts/xianyu_cli.py web coverage
python scripts/xianyu_cli.py web coverage --only missing
python scripts/xianyu_cli.py web coverage --unmapped-features
python scripts/xianyu_cli.py --openapi-file ./openapi.json web coverage --only missing

# 审计前端源码实际调用的 API 是否都存在于 OpenAPI，并且都能映射到页面 feature
python scripts/xianyu_cli.py web audit
python scripts/xianyu_cli.py web audit --only missing_openapi
python scripts/xianyu_cli.py web audit --only unmapped_feature
python scripts/xianyu_cli.py --openapi-file ./openapi.json web audit --frontend-root frontend/src

# 按 frontend/src/api 里的导出函数查 CLI 调用模板，更贴近网页版源码
python scripts/xianyu_cli.py web functions --search getAccountDetails
python scripts/xianyu_cli.py web functions --search accounts --include-optional
python scripts/xianyu_cli.py --openapi-file ./openapi.json web functions --frontend-root frontend/src
# 精确查看某个前端函数；组合式函数会展开成多条后端接口模板
python scripts/xianyu_cli.py web function addKeyword
# 一对一函数可直接用 web function-call

# 聚合门禁：同时检查页面映射、后端 feature 映射、前端源码 API；默认有问题就返回非 0
python scripts/xianyu_cli.py web verify
python scripts/xianyu_cli.py web verify accounts
python scripts/xianyu_cli.py web verify --skip-frontend
python scripts/xianyu_cli.py web verify --allow-failures

# 运行只读 smoke 测试：只会自动挑选无必填参数的 GET JSON 接口；默认有失败就返回非 0
python scripts/xianyu_cli.py web smoke --dry-run
python scripts/xianyu_cli.py web smoke accounts --dry-run
python scripts/xianyu_cli.py web smoke accounts --limit 10 --fail-fast
python scripts/xianyu_cli.py web smoke accounts --allow-failures
python scripts/xianyu_cli.py web smoke login --no-auth --limit 5

# 查看某个页面能调用哪些 API，页面可用 key、路径或中文标题
python scripts/xianyu_cli.py web ops accounts
python scripts/xianyu_cli.py web ops /accounts
python scripts/xianyu_cli.py web ops 账号管理

# 生成页面下某些操作的可复制 CLI 调用模板
python scripts/xianyu_cli.py web examples accounts --search import

# 按页面调用接口，操作名来自 web ops 的 feature.operation，也可用页面内唯一操作名或 operationId
python scripts/xianyu_cli.py web call accounts cookies.get-details-paginated -q page=1 -q page_size=50
python scripts/xianyu_cli.py web call 账号管理 cookies.get-details-paginated -q page=1 -q page_size=50

# 也可以直接按前端 API 函数名调用；重名时用 module.function
python scripts/xianyu_cli.py web function-call accounts.getAccountDetails
python scripts/xianyu_cli.py web function-call getAccountDetails

# 监听在线聊天实时推送。WebSocket 不在 OpenAPI 里，CLI 单独提供 web ws
python scripts/xianyu_cli.py web ws <账号ID>
python scripts/xianyu_cli.py web ws <账号ID> --limit 10 --timeout 60

# 页面维度调用同样支持文件上传/下载
python scripts/xianyu_cli.py web call accounts cookies.post-import -F file=./accounts.xlsx -f enable_all=true
python scripts/xianyu_cli.py web call accounts cookies.post-export -d '{}' -o ./accounts_export.xlsx
```

```bash
# 按功能模块列出接口，例如 cookies、items、orders、chat-new、product-publish
python scripts/xianyu_cli.py features list

# 查看某个功能模块有哪些操作
python scripts/xianyu_cli.py features ops cookies

# 生成模块下某些操作的可复制 CLI 调用模板
python scripts/xianyu_cli.py features examples cookies --search export

# 按功能模块调用，操作名来自 features ops
python scripts/xianyu_cli.py features call cookies get-details-paginated -q page=1 -q page_size=50
python scripts/xianyu_cli.py features call cookies put-account-id-status -p account_id=<账号ID> -d '{"enabled":false}'
```

`routes` 可发现和调用网页版使用的全部后端接口：

```bash
# 列出全部接口
python scripts/xianyu_cli.py routes list

# 搜索账号相关接口
python scripts/xianyu_cli.py routes list --search cookies

# 查看某个 operationId 的完整定义
python scripts/xianyu_cli.py routes show list_cookie_details_paginated_api_v1_cookies_details_paginated_get

# 生成单个 operationId 的可复制 CLI 调用模板
python scripts/xianyu_cli.py routes template list_cookie_details_paginated_api_v1_cookies_details_paginated_get

# 按 operationId 调用接口，-p 传路径参数，-q 传查询参数，-d 传 JSON 请求体
python scripts/xianyu_cli.py routes call list_cookie_details_paginated_api_v1_cookies_details_paginated_get -q page=1 -q page_size=50
```

安装为可执行命令后也可以直接使用：

```bash
pip install -e .
xianyu-cli accounts list
```

如果后端开启了登录滑动验证码，CLI 的用户名密码登录会被后端拦截。可先在页面完成登录后复制 access token，再写入 CLI：

```bash
python scripts/xianyu_cli.py auth token set <access-token>
```

#### 6. 启动返佣子系统

```bash
# 返佣后端
cd promotion/backend
pip install -e .
python main.py

# 返佣前端
cd promotion/frontend
npm install
npm run dev
```

## 配置说明

### 关键环境变量

| 变量 | 说明 |
|------|------|
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | MySQL 连接 |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` / `REDIS_DB` | Redis 连接 |
| `JWT_SECRET_KEY` | JWT 密钥，由数据库统一托管（首次启动自动生成并持久化），无需手动配置 |
| `BACKEND_WEB_PORT` / `WEBSOCKET_PORT` / `SCHEDULER_PORT` | 各服务端口 |
| `WEBSOCKET_SERVICE_URL` / `SCHEDULER_SERVICE_URL` / `BACKEND_WEB_SERVICE_URL` | 服务间调用地址 |
| `BACKEND_WEB_PUBLIC_URL` | 对外访问地址，用于生成文件 URL |
| `CORS_ORIGINS` | CORS 白名单 |
| `BROWSER_HEADLESS` | Playwright 是否无头运行 |

### 数据库与初始化

- 主系统启动时自动建表、自检、缺失字段补齐、默认数据初始化
- 默认管理员：`admin` / `admin123`
- 返佣系统启动时执行独立的数据库自检
- 返佣系统表统一使用 `fy_` 前缀
- 不依赖外键约束，关系由代码维护
- 所有时间统一使用北京时间（`Asia/Shanghai`）

### 统一响应格式

后端采用统一响应包装，业务异常也返回 HTTP 200：

```json
{
  "success": true,
  "code": 200,
  "message": "操作成功",
  "data": {}
}
```

## 构建脚本速查

| 脚本 | 平台 | 作用 |
|------|------|------|
| `deploy.sh` | Linux | 生成远程镜像版 compose 并拉取镜像启动（首次部署） |
| `update.sh` | Linux | 拉取最新远程镜像并重建应用容器（后续更新） |
| `build.sh` | Linux | 从源码全量构建所有 Docker 镜像并启动 |
| `build_frontend.sh` | Linux | 单独重建并重启 Frontend 服务 |
| `build_backend_web.sh` | Linux | 单独重建并重启 Backend-Web 服务 |
| `build_websocket.sh` | Linux | 单独重建并重启 WebSocket 服务 |
| `build_scheduler.sh` | Linux | 单独重建并重启 Scheduler 服务 |
| `EXE打包构建.bat` | Windows | 使用 Nuitka 打包桌面启动器 EXE |
| `离线依赖打包.bat` | Windows | 打包所有 Python 依赖供离线安装 |
| `scripts/Pipeline脚本-xianyu-auto-reply.groovy` | Jenkins | CI/CD 流水线，构建多架构镜像并推送到阿里云 ACR |

## 安全说明

- **JWT 认证**：主系统与返佣系统都使用 JWT 做登录态控制
- **密码存储**：密码使用哈希方式保存
- **SQL 注入防护**：数据库访问使用参数化查询
- **XSS 防护**：前端输入与展示做好校验与转义
- **CORS 控制**：生产环境应限制到明确域名

### 生产环境建议

1. 立即修改默认管理员密码
2. JWT 密钥由数据库统一托管，首次启动自动生成强随机密钥（无需手动设置）
3. 设置正确的 `BACKEND_WEB_PUBLIC_URL` 与反向代理地址
4. 为外网入口配置 HTTPS
5. 定期备份 MySQL 与静态资源目录
6. 确保 Playwright 浏览器已正确安装

## 常见问题

### 根目录 Docker Compose 没有启动返佣系统？

当前 `docker-compose.yml` 只覆盖主系统。返佣系统需要单独启动。

### 登录或发布时报浏览器缺失？

在对应 Python 环境执行：`python -m playwright install chromium`。Docker 环境依赖各服务 Dockerfile 内已安装的浏览器。

### Docker 部署端口冲突？

修改根目录 `.env` 中的端口配置后重新部署。

### 执行脚本报 `/bin/bash^M: 坏的解释器`？

脚本文件包含 Windows 换行符（CRLF），Linux 无法识别。解决方法：

```bash
# 方法一：用 sed 去除 \r 后执行
sed -i 's/\r$//' deploy.sh
bash deploy.sh

# 方法二：通过管道执行（推荐远程脚本使用）
curl -fsSL https://xy-update.zhinianboke.com/deploy.sh | sed 's/\r$//' | bash
```

## 许可证

本项目采用 [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE) 开源协议。

**⚠️ 禁止商业用途：本项目仅供学习研究使用，严禁任何形式的商业用途。**

## 免责声明

本项目仅供技术学习和研究使用，使用者需自行承担使用风险。请遵守相关平台的使用条款和法律法规。

- 本项目不对使用本系统造成的任何后果负责
- 请勿用于违反闲鱼平台规则的行为
- 请勿用于商业用途
- 使用本系统可能存在账号风险，请谨慎使用

## 🧸 特别鸣谢

本项目参考了以下开源项目：

- **[XianYuApis](https://github.com/cv-cat/XianYuApis)** - 提供了闲鱼API接口的技术参考
- **[XianyuAutoAgent](https://github.com/shaxiu/XianyuAutoAgent)** - 提供了自动化处理的实现思路
- **[myfish](https://github.com/Kaguya233qwq/myfish)** - 提供了扫码登录的实现思路


感谢这些优秀的开源项目为本项目的开发提供了宝贵的参考和启发！


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=zhinianboke/xianyu-auto-reply&type=Date)](https://www.star-history.com/#zhinianboke/xianyu-auto-reply&Date)
