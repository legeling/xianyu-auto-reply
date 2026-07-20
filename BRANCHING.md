# 分支管理规范

本仓库是上游 [zhinianboke/xianyu-auto-reply](https://github.com/zhinianboke/xianyu-auto-reply) 的 fork（`legeling/xianyu-auto-reply`，公开仓库）。为了既能持续吸收上游更新、又能维护本地定制（如移除广告模块、CLI 工具等），约定如下分支模型。

## 分支结构

```
upstream/main ──────────────────── 上游主分支（只读，禁止直接提交）
      │
      │  定期同步（merge / fast-forward）
      ▼
main ───────────────────────────── 本地稳定基线 = 上游 + 已验证的本地定制
      │
      │  日常开发在这里进行
      ▼
dev ────────────────────────────── 开发集成分支（本地定制的常驻分支）
      │
      ├── feature/xxx ───────────── 短期功能分支（从 dev 切出，完成即合回并删除）
      └── fix/xxx ───────────────── 问题修复分支（同上）
```

## 各分支职责

| 分支 | 远程 | 职责 | 规则 |
|------|------|------|------|
| `upstream/main` | `upstream`（只读） | 跟踪上游官方仓库 | 只 fetch，不 push |
| `main` | `origin` | 稳定基线 | 只接受来自 `dev` 的合并与上游同步；不直接开发 |
| `dev` | `origin` | 日常开发集成 | 本地定制的常驻分支；默认工作分支 |
| `feature/*`、`fix/*` | 可选 | 独立功能 / 修复 | 从 `dev` 切出，合并后删除本地与远程分支 |

## 远程配置

```bash
git remote add upstream https://github.com/zhinianboke/xianyu-auto-reply.git
# 禁止误推上游
git remote set-url --push upstream no_push
```

## 标准工作流

### 1. 日常开发

```bash
git checkout dev
# 直接提交小改动，或：
git checkout -b feature/我的功能
# 完成后合回 dev 并删除分支
git checkout dev && git merge --no-ff feature/我的功能
git branch -d feature/我的功能
```

### 2. 同步上游更新（建议每月或上游有大更新时）

```bash
git fetch upstream
git checkout main
git merge upstream/main        # main 无本地提交时可快进
git push origin main

git checkout dev
git merge main                 # 冲突集中在这里解决
# 验证（跑测试 / 起服务）后再提交推送
git push origin dev
```

原则：**冲突只在 `dev` 上解决**，`main` 永远保持"上游 + 已验证定制"的可发布状态。

### 2.1 本地定制保护清单（同步上游时不可丢失）

以下是本 fork 相对上游的主动定制。每次合并上游冲突时，**默认保留我方版本**，确认无误后才允许改动：

| 定制项 | 范围 | 冲突处理规则 |
|--------|------|--------------|
| 移除广告模块 | `backend-web/app/api/routes/advertisements.py`、`common/models/advertisement.py`、`frontend/src/api/advertisements.ts`、`frontend/src/pages/advertisements/**`、Dashboard 广告位、导航"广告"菜单、底部"广告申请"入口、系统设置中的 `ad_price.*` / `auth.footer_ad_html` | 上游对这些文件的修改**一律不采纳**（modify/delete 冲突选删除）；上游新增的广告相关代码块（菜单项、路由、组件、设置卡片）不并入。`REMOVED_SYSTEM_SETTING_KEYS` 过滤逻辑必须保留 |
| xianyu-cli 命令行工具 | `xianyu_cli/`、`tests/`、`scripts/xianyu_cli.py`、根级 `pyproject.toml` | 上游若新增同名文件需人工核对，不直接覆盖 |
| 分支与工程规范 | `BRANCHING.md`、`.gitignore` 中本地新增条目（如 `trajectory_history/`） | `.gitignore` 冲突时**两侧条目都保留** |
| 启动器精简 | `launcher/gui_dashboard.py` | 上游改动可合入，但需人工确认不引入已移除的广告相关入口 |

通用原则：

1. **我方删除的，不同步回来**：凡本清单中"移除"类定制，上游对应的新增/修改在冲突时一律以我方删除为准。
2. **上游新增的独立功能，正常吸收**：与定制无关的新功能（如弹窗公告、用户到期设置）照常合入；若与已移除模块有挂载关系（如弹窗公告原挂在"广告"菜单下），将其改挂到独立位置而非随菜单一并删除。
3. **同一处的双方修改，取并集**：如设置项过滤列表、`.gitignore`，双方各自新增的条目都保留。
4. **合并后必须验证**：前端 `cd frontend && npx tsc --noEmit` 通过、后端 `python -m compileall backend-web/app common` 通过、无残留引用（`grep -rn "advertisement" frontend/src backend-web/app common` 无意外命中）后才提交合并。
5. **新定制要登记**：今后再移除或重写上游功能时，同步把保护规则追加到上表。

### 3. 发布 / 上线

`dev` 验证稳定后：

```bash
git checkout main
git merge --no-ff dev
git push origin main
git checkout dev               # 切回日常分支
```

## 提交与推送规则

1. **提交信息**：使用中文动词开头，如 `完善xxx` / `修复xxx` / `移除xxx` / `新增xxx`，与现有历史风格保持一致；涉及模块时加前缀，如 `refactor: 移除广告模块`。
2. **敏感信息**：本仓库公开。提交前确认不包含 Cookie、密码、密钥、`.env`、真实用户数据；`data/`、`logs/`、`.env`、`trajectory_history/` 已在 `.gitignore` 中，新增同类目录需同步补充忽略规则。
3. **上游分支**：任何人不得向 `upstream` 推送；若要回馈上游，从干净分支单独提 PR。
4. **已合并分支**：合入 `main`/`dev` 后及时删除本地与远程的临时分支，保持分支列表干净。
5. **合并方式**：功能分支合入用 `--no-ff` 保留结构；上游同步用普通 merge（可快进则快进）。
