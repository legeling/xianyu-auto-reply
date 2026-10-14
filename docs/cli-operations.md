# CLI 上架与自动发货管理

适用独立分支 1.1.6。CLI 在本机执行，使用生产后台接口；普通闲鱼卖家可以完成新商品发布、下架与发货配置。现有平台商品编辑、改价/库存接口仅适配鱼小铺，`items update-local` 只修改本地配置，不能冒充线上修改。

2026-10-06已现场核验普通卖家的原位正文编辑能力：闲鱼[发布页脚本](https://g.alicdn.com/idle-pc/xy-site/0.0.176/js/p_publish-index.js)使用`mtop.idle.pc.idleitem.editDetail`读取当前商品，以`mtop.idle.pc.idleitem.edit`（1.0）提交带`itemId`的编辑载荷。商品1088597030202的正文已经此接口修改并逐字回读，售价、图片、地址及商品ID保持一致。本次通过SSH复用生产共享MTOP客户端执行；CLI的`items edit`尚未接入普通卖家分支，不能把现有CLI限制视为平台不支持编辑。操作前保留平台详情快照，提交后核对正文及未修改字段；需要撤销时用原正文和当前详情按同一接口编辑，不重复上架。

## 连接与基本约定

在仓库根目录，复用现有 Python，不安装整个后端：

```sh
xianyu-cli() { uv run --no-project --python 3.12 scripts/xianyu_cli.py "$@"; }
xianyu-cli config set-url https://xianyu.lingxiaotian.com
xianyu-cli auth whoami
# access token 到期而 refresh token 仍有效时更新登录态
xianyu-cli auth refresh
xianyu-cli accounts list
```

全局 `--json` / `--base-url` 放在子命令前。所有 JSON 请求均支持互斥的 `-d` 与 `--data-file`，字段直接使用后端规范名；业务校验由后端负责。CLI 不复制接口默认容量、时间或重试值。后台用户登录和闲鱼扫码登录是两种登录态；已有闲鱼账号直接复用，无需再次导入 Cookie。

CLI 登录态默认保存在仓库外的 `~/.xianyu-auto-reply-cli.json`，也可通过 `XIANYU_CLI_CONFIG` 指定本机路径；保存时设置文件权限为 `0600`。仓库中的[脱敏配置示例](examples/xianyu-cli.config.example.json)展示完整字段结构，令牌为空，用户资料为占位值。真实登录文件不提交到 Git；首次使用运行 `auth login --username 用户名`，按提示输入密码，由登录接口填写令牌。不要用示例覆盖已有登录态。

普通输出与 JSON 输出均脱敏 Cookie、密码、令牌、请求头、文本发货内容和卡密内容。批量卡券列表默认分页、轻量读取；只在查询单卡券详情/库存时读取内容。`cards stock` 的 `remaining_line_count` 是数据卡券非空行数量，不展示卡密，也不消费库存。库存更新是替换 `data_content`，不是追加或消费。

## 商品上架

先维护 [本地商品目录](products/README.md) 中的 `product.json`，核对商品内容、价格、图片与交付物，再生成本次发布载荷调用以下命令。发布结果和商品/卡券ID回写本地档案；商品目录文件不直接作为后台请求。目前这些命令提供各步骤的操作能力，尚无自动扫描本地目录的一键同步命令。

```sh
xianyu-cli publish check-account ACCOUNT
xianyu-cli publish upload-images ./main.png ./detail.png
xianyu-cli publish recommend-category --data-file ./category-request.json
xianyu-cli publish materials create --data-file ./material.json
xianyu-cli publish materials list
xianyu-cli publish materials get MATERIAL_ID
xianyu-cli publish materials update MATERIAL_ID --data-file ./material-update.json
xianyu-cli publish single --data-file ./single.json
xianyu-cli publish batch --account-id ACCOUNT --material-id MATERIAL_ID
xianyu-cli publish status BATCH_ID
xianyu-cli publish logs --account-id ACCOUNT --status failed
xianyu-cli items sync ACCOUNT --page 1
xianyu-cli items list --account-id ACCOUNT
```

上传图片结果中的 `data.paths` 用作商品 JSON 的 `images`。分类推荐返回的分类路径与属性保持完整，写回素材或发布请求；不能用一个猜测的分类名称代替平台属性。`MaterialCreateRequest` 与 `PublishSingleRequest` 的规范字段在 `backend-web/app/api/routes/product_publish.py`；`single` 还需 `account_id`。价格、出售范围、图片、交付方式应确认后填入，不自动编造。已提交批量任务只查结果，不自动重发。

素材 CRUD 与批量删除、视频上传均有命令；`publish addresses` 管理随机地址，`publish personal-addresses` 管理个人地址并支持 Excel 导入/导出。个人地址优先参与发布。修改地址用 `{"address":"真实地址"}`；删除用 `delete ID [ID ...]`，随机地址启停用 `set-enabled ID true|false`。

## 平台下架

```sh
xianyu-cli items offline ACCOUNT --item-id ITEM_ID
# 多件商品重复传 --item-id，返回每件结果
xianyu-cli items offline ACCOUNT --item-id ITEM_ID_1 --item-id ITEM_ID_2
```

网页版和CLI共用`POST /api/v1/items/batch-offline`。1.1.5将原来的鱼小铺批量接口改为闲鱼官网商品详情页的卖家接口`mtop.taobao.idle.item.downshelf`（2.0），按`itemId`逐项调用，适用于普通卖家。来源为[闲鱼官网商品详情页脚本](https://g.alicdn.com/idle-pc/xy-site/0.0.176/js/p_item-index.js)。每个唯一ID一次调用，沿用共享MTOP客户端的鉴权及Cookie刷新；账号会话失效后停止余下调用并计为失败。账号权限校验、请求与响应结构保持不变；部分失败时CLI仍返回非零。下架保留本地记录、卡券和历史订单，下架后通过平台商品同步核对在售列表。

升级仅替换后端镜像中的下架服务、路由和独立版本文件，无数据库迁移或新增依赖；WebSocket、调度和前端无须重启。保留旧后端镜像及发布覆盖文件，回滚只恢复后端镜像，不恢复业务数据库。回滚代码不会重新上架已下架商品。

## 发货内容与商品关联

先准备可实际交付的链接、文本、逐行卡密或 API 配置。文本卡券示例仅说明字段，示例网址不是真实交付物：

```json
{"name":"商品交付说明","type":"text","enabled":false,"text_content":"下载地址：https://example.com/download；使用说明见文件","delay_seconds":0}
```

```sh
xianyu-cli cards create --data-file ./card.json
xianyu-cli cards get CARD_ID
xianyu-cli cards update CARD_ID --data-file ./card-update.json
xianyu-cli cards bind -d '{"card_ids":[7],"item_ids":["实际商品ID"]}'
xianyu-cli cards for-item ITEM_ID
xianyu-cli cards enable CARD_ID
xianyu-cli cards disable CARD_ID
xianyu-cli cards stock DATA_CARD_ID
```

`type` 与内容字段：`text`→`text_content`，`data`→`data_content`（非空行逐次消费），`image`→`image_url/image_urls`，`api`→`api_config`。卡券启用才参与发货。`cards upload-image` 上传交付图片，发布图片用 `publish upload-images`，两者职责不同。

`bind` 增加关联；`set-items CARD_ID` 以 `{"item_ids":[...]}` 替换此卡券的完整关联；`set-item-cards ITEM_ID` 以 `{"card_items":[{"card_id":7,"source":"own"}]}` 替换商品的完整关联（支持后端的对接来源）。`unbind CARD_ID ITEM_ID` 只移除指定关联；`clear-item-cards` 以 `{"item_ids":[...]}` 清空商品关联，保留卡券。批量保存、删除使用 `cards batch-save`、`cards batch-delete`。

## 自动发货配置

```sh
xianyu-cli delivery config ACCOUNT
xianyu-cli delivery inspect ACCOUNT ITEM_ID
xianyu-cli delivery switch ACCOUNT auto_confirm true
xianyu-cli delivery switch ACCOUNT send_before_confirm true
xianyu-cli delivery switch ACCOUNT scheduled_redelivery true
xianyu-cli items multi-quantity ACCOUNT ITEM_ID true
xianyu-cli delivery block-rule-types
xianyu-cli delivery block-rules get ACCOUNT
xianyu-cli delivery block-rules set ACCOUNT --data-file ./block-rules.json
xianyu-cli delivery agree get ACCOUNT
xianyu-cli delivery agree set ACCOUNT --data-file ./agree.json
xianyu-cli delivery refund get ACCOUNT
xianyu-cli delivery refund set ACCOUNT --data-file ./refund.json
```

账号开关使用后端规范名：`auto_confirm` 自动确认发货，`scheduled_redelivery` 定时补发货，`confirm_before_send` 发货确认成功再发卡券，`send_before_confirm` 卡券发送成功再确认，`only_send_card` 只发卡券不确认。这些开关分开保存，模式的判定和优先级由后端处理；不能把一项关闭当成所有发货模式都关闭。需要停用某卡券时直接 `cards disable`，需要停用整个账号则 `accounts disable`。

自动发货以平台订单/消息事件触发，不是 CLI 在本机轮询。定时补发货复用生产 scheduler 的配置。`inspect` 只读取账号、商品、关联卡券、禁止发货规则和同意后发货配置，不能证明真实订单已发货。

禁止发货规则的请求为 `{"rules":[...]}`，合法规则类型与字段以 `block-rule-types` / 后端 `AccountDeliveryBlockRulesUpdate` 为准。同意后发货配置为 `enabled/notify_message/pickup_url`；开启时需要真实 http(s) 提货 URL，可用 `delivery pickup-url` 查询建议。退款注销配置为 `enabled/url/timeout`，填写业务允许的实际注销接口，不发起虚构注销测试。

自动续售使用 `publish relist get|set|events MATERIAL_ID`、`all-events`。设置沿用 `AutoRelistRuleRequest`，包括账号、当前商品、卡券、开关与 `expected_version`；对账用 `reconcile` 或 `mark-failed`，不能在结果未知时重新发布。

## 订单、回复与发货结果

```sh
xianyu-cli orders list --account-id ACCOUNT --delivery-method none
xianyu-cli orders sync --account-id ACCOUNT
xianyu-cli orders get ORDER_NO
# 以下操作会产生真实业务结果，仅对确需处理的订单执行
xianyu-cli orders deliver ORDER_NO
xianyu-cli orders no-logistics ORDER_NO
xianyu-cli delivery logs --account-id ACCOUNT --item-id ITEM_ID --send-status failed
xianyu-cli delivery redelivery-logs list
xianyu-cli delivery redelivery-logs get BATCH_ID
xianyu-cli keywords list --account-id ACCOUNT
xianyu-cli items default-reply set ACCOUNT ITEM_ID --data-file ./reply.json
```

`orders deliver` 走后端手动发货链路，会发送关联卡券并处理发货；`no-logistics` 只提交无需物流发货，两者不能互换。`orders cancel` 关闭闲鱼订单；`orders delete` / `batch-delete` 只删除本地记录。按 `delivery_method`、`delivery_send_status`、日期等过滤订单；以实际订单状态和发送日志验证交付，不只看 HTTP 200。

`keywords replace` 替换账号全部文本/位置关键词，字段为 `{"keywords":[...]}`；单条更新用 `update`，删除用 `delete`，并支持图片、Excel导入导出。原来的 `orders --account-id ...` 与 `keywords --account-id ...` 查询保持有效。

## 错误、覆盖与升级

业务 `success=false` 即使 HTTP 200 也返回非零；完成的批量发布含失败、卡券绑定部分失败、商品批量操作部分失败、订单批量删除部分失败也返回非零并保留结果。没有自动重试。JSON 文件错误在提交前失败；参数错误不回显原始发货内容。导出原子替换目标文件，权限0600；接口报错或文件替换失败不覆盖已有导出。

`web verify` 审计真实前端调用、后端OpenAPI与页面映射；已补充同意后发货、提货、退款注销、AI铺货、商品监控、弹窗、系统控制和公开接口的功能关联。所有后端API仍可通过 `features/routes/web/api` 调用，不必给每个接口复制一套专用实现。

升级只需更新 CLI 目录，以及1.1.1后端的卡券创建状态修复；没有数据库迁移或新增运行时依赖。保留用户现有CLI配置和生产业务配置。后端用独立新镜像替换并保留旧镜像；回滚恢复原镜像与CLI文件，不恢复或覆盖业务数据库。已创建的业务记录按明确ID清理，不删除用户既有数据。

## 登录态自动验证

1.1.2 修复了编排层到普通浏览器验证引擎的账号会话传递：浏览器在访问验证页面前载入账号 Cookie，范围仅为实际闲鱼/淘宝 HTTPS 验证主机；不把登录凭据注入任意网址。Cookie 通过 Playwright [BrowserContext.add_cookies](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-cookies) 设置，保留原有验证结果和新 Token 判定。日志只记录会话是否存在，不记录 x5sec 值。

验证通过后仍由原有服务写回 Cookie、取得并缓存 Token、恢复 WebSocket。仅凭浏览器动作结束不能判定账号已恢复；必须检查新 Token 和在线状态。当前 Linux 无头引擎若仍被平台拒绝，则自动验证尚未验收；现有远程验证服务配置未填写，不能以已经支持该接口冒充远程服务已部署。没有数据库迁移或新增依赖，回滚使用上一个发布目录的镜像覆盖文件，保留业务数据库。

## 验证码服务

`captcha get` 读取脱敏配置，`captcha set --data-file /absolute/path/config.json` 更新配置并保留其余设置，`captcha test` 测试已保存的服务。CapMonster 测试仅查余额，不创建收费任务。管理员配置示例及网页续期说明见 [CapMonster 与登录续期](capmonster-session.md)。

## 每日自动擦亮

账号开关通过现有通用API命令管理，无需另建外部定时任务：

```sh
xianyu-cli api PUT /api/v1/cookies/3073157444_1/auto-polish --data '{"auto_polish":true}'
xianyu-cli api GET /api/v1/admin/scheduled-tasks
xianyu-cli api GET /api/v1/admin/polish-batches --query page=1 --query page_size=5
```

开关按账号生效，新上架商品会加入。调度中的`polish`扫描未擦亮商品，`day_switch`按北京时间每天重置擦亮状态；两项均须启用。扫描间隔不等于对同一商品重复擦亮的频率。停止该账号自动擦亮只需将同一请求中的`auto_polish`设为`false`，不关闭其他账号的全局调度。历史已下架商品仍留在目录时可能产生不支持操作日志，可通过批次详情核对具体商品；擦亮成功不代表曝光或销量保证。


### 1.1.6 擦亮完成判定修复

此前擦亮URL为1.0、参数v为2.0，且仅凭`SUCCESS`就设置`is_polished=true`；2026-10-05零点返回商品仍为`canPolish=true`，却停止了当天后续执行。1.1.6将URL和参数统一为1.0，由同一`POLISH_API_VERSION`生成。成功回包必须包含目标商品ID和`canPolish=false`才确认完成；缺失或仍可擦亮时保留未完成状态，由既有60秒调度继续处理。平台明确返回`FAIL_BIZ_IDLEITEM_POLISH_AGAIN`时说明今日已擦亮，日志保留“本次未重复擦亮”，与本次新擦亮区分。泛化的频率提示不再自动算作成功。

此修复不改变账号开关、跨日重置、发货或续售配置，没有新增数据库字段、依赖或重试策略。部署只更新scheduler及后端版本说明，保留旧镜像与覆盖配置；回滚恢复这两项镜像，不恢复业务数据库。历史“调用成功”日志保留，不据此认定当时的App状态已更新。每日自动擦亮不承诺曝光或销量；跨日后的新一次实际效果仍须由平台状态核验。
