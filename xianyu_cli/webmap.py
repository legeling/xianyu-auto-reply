"""Mapping between frontend pages and backend API features."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WebPage:
    key: str
    label: str
    path: str
    features: tuple[str, ...]


WEB_PAGES: tuple[WebPage, ...] = (
    WebPage("login", "登录", "/login", ("auth", "system-settings", "captcha", "geetest")),
    WebPage("register", "注册", "/register", ("auth", "system-settings", "captcha")),
    WebPage("forgot-password", "找回密码", "/forgot-password", ("auth", "system-settings", "captcha")),
    WebPage("get-activation", "获取激活码", "/get-activation", ("activation",)),
    WebPage("renew-activation", "续期激活码", "/renew-activation", ("activation",)),
    WebPage("get-local-version", "获取本地版本", "/get-local-version", ("qrcode",)),
    WebPage("get-source-code", "获取源码", "/get-source-code", ("qrcode",)),
    WebPage("shared-scan-page", "共享扫码加入页", "/shared-scan-page", ("shared-scan",)),
    WebPage("dashboard", "仪表盘", "/dashboard", ("cookies", "admin", "announcements", "system-settings", "health")),
    WebPage("data-overview", "数据总览", "/data-analysis/overview", ("data-analysis", "cookies")),
    WebPage(
        "accounts",
        "账号管理",
        "/accounts",
        (
            "cookies",
            "qr-login",
            "password-login",
            "shared-scan",
            "proxy",
            "face-verification",
            "cookie-refresh",
            "default-replies",
            "auto-rate",
            "ai-reply-settings",
            "ai-reply-test",
            "confirm-receipt-messages",
            "auth",
        ),
    ),
    WebPage("accounts-shared-scan", "共享扫码管理", "/accounts/shared-scan", ("shared-scan",)),
    WebPage("online-chat-new", "在线聊天", "/online-chat-new", ("chat-new", "orders", "messages")),
    WebPage("items", "商品管理", "/items", ("items", "search", "cards", "distribution", "cookies")),
    WebPage("item-search", "商品搜索", "/item-search", ("items", "search")),
    WebPage("goofish-compass", "Goofish 数据罗盘", "/goofish-compass", ("goofish", "compass")),
    WebPage("goofish-scheduled-crawler", "Goofish 定时采集", "/goofish-scheduled-crawler", ("goofish", "cookies")),
    WebPage("cards", "卡券管理", "/cards", ("cards", "card-dock")),
    WebPage("orders", "订单管理", "/orders", ("orders",)),
    WebPage("distribution-sources", "货源管理", "/distribution/sources", ("distribution",)),
    WebPage("distribution-supply", "货源广场", "/distribution/supply", ("distribution",)),
    WebPage("distribution-card-pickup", "分销卡券", "/distribution/card-pickup", ("card-dock", "distribution")),
    WebPage("distribution-docked", "对接的商品", "/distribution/docked", ("distribution",)),
    WebPage("distribution-agent-orders", "代理订单", "/distribution/agent-orders", ("distribution",)),
    WebPage("distribution-dealers", "分销商管理", "/distribution/dealers", ("distribution",)),
    WebPage("distribution-sub-dealers", "下级分销商", "/distribution/sub-dealers", ("distribution",)),
    WebPage("product-publish-materials", "素材库", "/product-publish/materials", ("product-publish", "cookies")),
    WebPage("product-publish-single", "单品发布", "/product-publish/single", ("product-publish", "cookies")),
    WebPage("product-publish-batch", "批量发布", "/product-publish/batch", ("product-publish", "cookies")),
    WebPage("product-publish-addresses", "随机地址库", "/product-publish/addresses", ("product-publish",)),
    WebPage("product-publish-logs", "发布日志", "/product-publish/logs", ("product-publish", "cookies")),
    WebPage(
        "keywords",
        "自动回复",
        "/keywords",
        ("keywords-with-item-id", "default-replies", "ai-reply-settings", "ai-reply-test", "cookies", "items"),
    ),
    WebPage("message-logs", "消息日志", "/message-logs", ("auto-reply-logs", "cookies")),
    WebPage("risk-logs", "风控日志", "/risk-logs", ("risk-control-logs", "cookies", "admin")),
    WebPage("message-filters", "消息过滤", "/message-filters", ("message-filters", "cookies")),
    WebPage("notification-channels", "通知渠道", "/notification-channels", ("notification-channels",)),
    WebPage(
        "message-notifications",
        "消息通知",
        "/message-notifications",
        ("message-notifications", "notification-channels", "cookies"),
    ),
    WebPage("blacklist", "黑名单管理", "/blacklist", ("blacklist", "cookies", "items")),
    WebPage("personal-settings", "个人设置", "/personal-settings", ("user-settings", "payment", "users", "system-settings")),
    WebPage("settings", "系统设置", "/settings", ("system-settings", "qrcode", "admin", "users", "user-settings", "ai-reply-settings")),
    WebPage("admin-users", "用户管理", "/admin/users", ("admin", "users")),
    WebPage("admin-system-logs", "系统日志", "/admin/logs", ("admin",)),
    WebPage("admin-data", "数据管理", "/admin/data", ("admin",)),
    WebPage("admin-redelivery-batches", "补发货日志", "/admin/redelivery-batches", ("admin",)),
    WebPage("admin-redelivery-batch-detail", "补发货日志详情", "/admin/redelivery-batches/:batchId", ("admin",)),
    WebPage("admin-account-login-logs", "账号登录日志", "/admin/account-login-logs", ("account-login-logs", "admin", "cookies")),
    WebPage("admin-rate-batches", "补评价日志", "/admin/rate-batches", ("admin",)),
    WebPage("admin-rate-batch-detail", "补评价日志详情", "/admin/rate-batches/:batchId", ("admin",)),
    WebPage("admin-polish-batches", "擦亮日志", "/admin/polish-batches", ("admin",)),
    WebPage("admin-polish-batch-detail", "擦亮日志详情", "/admin/polish-batches/:batchId", ("admin",)),
    WebPage("admin-login-renew-batches", "登录续期日志", "/admin/login-renew-batches", ("admin",)),
    WebPage("admin-login-renew-batch-detail", "登录续期日志详情", "/admin/login-renew-batches/:batchId", ("admin",)),
    WebPage("admin-cookies-refresh-batches", "COOKIES刷新日志", "/admin/cookies-refresh-batches", ("admin",)),
    WebPage("admin-cookies-refresh-batch-detail", "COOKIES刷新日志详情", "/admin/cookies-refresh-batches/:batchId", ("admin",)),
    WebPage("admin-api-cookie-renew-batches", "接口续期Cookies日志", "/admin/api-cookie-renew-batches", ("admin",)),
    WebPage("admin-api-cookie-renew-batch-detail", "接口续期Cookies日志详情", "/admin/api-cookie-renew-batches/:batchId", ("admin",)),
    WebPage("admin-close-notice-batches", "消息通知关闭日志", "/admin/close-notice-batches", ("admin",)),
    WebPage("admin-close-notice-batch-detail", "消息通知关闭日志详情", "/admin/close-notice-batches/:batchId", ("admin",)),
    WebPage("admin-red-flower-batches", "求小红花日志", "/admin/red-flower-batches", ("admin",)),
    WebPage("admin-red-flower-batch-detail", "求小红花日志详情", "/admin/red-flower-batches/:batchId", ("admin",)),
    WebPage("admin-db-backup-logs", "数据库备份日志", "/admin/db-backup-logs", ("db-backup-logs",)),
    WebPage("admin-scheduled-tasks", "定时任务", "/admin/scheduled-tasks", ("admin",)),
    WebPage("admin-announcements", "公告管理", "/admin/announcements", ("announcements",)),
    WebPage("admin-fund-flows", "资金流水", "/admin/fund-flows", ("distribution",)),
    WebPage("tutorial", "使用教程", "/tutorial", ()),
    WebPage("feedback", "意见反馈", "/feedback", ("feedbacks", "cookies", "upload")),
    WebPage("disclaimer", "免责声明", "/disclaimer", ("system-settings",)),
    WebPage("about", "关于", "/about", ("version", "qrcode")),
)


def find_page(key: str) -> WebPage | None:
    normalized = _normalize_lookup(key)
    for page in WEB_PAGES:
        if normalized in _page_lookup_values(page):
            return page
    return None


def _normalize_lookup(value: str) -> str:
    return value.strip().strip("/").lower()


def _page_lookup_values(page: WebPage) -> set[str]:
    return {
        _normalize_lookup(page.key),
        _normalize_lookup(page.label),
        _normalize_lookup(page.path),
    }
