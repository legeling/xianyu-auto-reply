# CapMonster 与网页版登录续期（1.1.4）

管理员在「风控日志 → 远程过滑块配置」选择 CapMonster Cloud，填写 API Key 并保存。
点击「测试」仅查询美元余额，不创建收费验证码任务。密钥读取脱敏为 `***`，保存原占位符保留密钥，空字符串清空；更换供应商必须重新填写密钥。

CLI 使用同一后台接口、管理员鉴权和字段契约：

```sh
xianyu-cli captcha get
xianyu-cli captcha set --data-file /absolute/path/capmonster.json
xianyu-cli captcha test
```

配置文件内容为 `{"provider":"capmonster","secret_key":"填入真实密钥"}`，请限制文件权限为 0600，不将密钥放入命令参数或提交仓库。`set` 合并已有配置，保留未指定的开关和排队设置。供应商只支持 `capmonster` 或原有 `remote`。

CapMonster 固定使用 `https://api.capmonster.cloud`。接收闲鱼返回的 HTTPS `/punish` 链接，创建 Alibaba `CustomTask`，指定 `cookieRequired=true`，查询完成后仅合并验证主机适用域的 Cookie，必须含非空 `x5sec`。不传完整账号 Cookie；不重试创建收费任务。查询使用现有远程求解时间预算和官方每任务最多 120 次结果查询的约束。供应商响应错误与未返回 x5sec 均返回失败，不假报账号在线。网络及响应错误不回显密钥、Cookie 或验证链接。

接口：`GET/PUT /api/v1/captcha/remote-config` 新增 `provider` 字段，缺省为已有 `remote`；`POST /api/v1/captcha/slider-solve/test` 接收同样的 `provider/url/secret_key`。CapMonster 忽略自定义 URL，强制不传完整 Cookie。「禁止外部调用本机」与向 CapMonster 发出求解请求无关，无须关闭。

1.1.4 在创建任务前从官方 `https://capmonster.cloud/api/useragent/actual` 获取当前支持的 User-Agent，显式填入任务，使用同一个求解时间预算。完整链接须含 `x5secdata/x5step/action/pureCaptcha`，HTTPS 省略端口时补 `443`，保留原查询编码；不猜测 sceneId、prefix 或 region。失败记录区分 `userAgent/createTask/getTaskResult` 阶段，并保留已创建的 taskId，方便与供应商支持核对；不记录密钥、完整链接、Cookie 或供应商原始错误描述。User-Agent 获取失败不创建任务，不另建重试链。

协议参考：[Alibaba](https://docs.capmonster.cloud/docs/captchas/alibaba-task/)、[结果查询](https://docs.capmonster.cloud/docs/api/methods/get-task-result/)。未填写密钥时不调用 CapMonster；生产验收需填写密钥后得到平台接受的 Token 和实际在线状态。

## 网页登录

`REFRESH_TOKEN_EXPIRE_MINUTES` 默认 43200 分钟（30 天），访问令牌有效期由原 `ACCESS_TOKEN_EXPIRE_MINUTES` 管理。每次续期签发新的访问令牌和具有完整 30 天有效期的刷新令牌，不设置累计在线上限。打开网页版时自动处理过期访问令牌；页面在线时根据 JWT 到期时间安排一次续期，后台页恢复可见或网络恢复时检查是否需要续期。不使用固定频率轮询。网络中断不清空登录，令牌真正失效、账号禁用或主动退出仍须重新登录。

关闭网页超过刷新令牌期限后需重新登录。这里延长的是管理平台登录，不改变闲鱼平台自身 Cookie 的寿命或风控策略。

## 升级与回滚

无需表结构迁移。已有远程配置缺少 `captcha.remote_provider` 时按原自建服务读取；选择 CapMonster 写入该设置。部署新前端、backend-web、websocket 与共享 common；Compose 的刷新期限设为 43200，若部署环境显式覆盖旧值须一并修改。已有有效刷新令牌首次续期后获得新期限。

回滚保留旧镜像与 Compose 配置，恢复原刷新期限和原远程供应商设置；切回 `remote` 并恢复该服务的 URL/密钥，不能将 CapMonster 密钥发送给其他服务。已签发的 30 天令牌仍依原签名和到期时间验证，不需要清空用户登录。

从 1.1.3 升级 1.1.4 只更新包含共享 common 的三个应用镜像，前端、数据库、密钥及 30 天续期设置保持原值。回滚使用发布目录的 `rollback-images.json` 恢复旧镜像，保留任务日志以供排查。

验证命令（复用已有依赖）：Python 通过 `uv run --no-project --python <现有解释器> python -m pytest tests/test_capmonster.py tests/test_web_session.py`；前端通过 `pnpm exec node --test tests/session.test.mjs`、`pnpm build`。
