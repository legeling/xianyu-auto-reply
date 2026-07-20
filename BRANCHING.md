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
