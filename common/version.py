"""本分支的产品版本；上游版本只记录合入来源，不参与升级比较。"""

CURRENT_VERSION = "1.1.6"
UPSTREAM_VERSION = "1.0.10"
UPSTREAM_COMMIT = "1be6493c36f8c66547b91d3940ac32580b1937b9"


def get_release_info() -> dict[str, str]:
    return {
        "version": CURRENT_VERSION,
        "upstream_version": UPSTREAM_VERSION,
        "upstream_commit": UPSTREAM_COMMIT,
    }


def get_update_info() -> dict:
    return {
        "has_update": False,
        "current_version": CURRENT_VERSION,
        "upstream_version": UPSTREAM_VERSION,
        "remote_version": "",
        "description": (
            f"当前为独立分支 v{CURRENT_VERSION}，合入上游 v{UPSTREAM_VERSION}。"
            "本分支通过本仓库构建、部署更新，不安装上游发布包。"
            "1.1.1 完善上架与自动发货CLI管理，修复停用卡券创建状态。"
            "1.1.2 修复浏览器验证时未载入账号会话的问题。"
            "1.1.3 接入 CapMonster、验证码CLI配置和网页版30天滚动续期。"
            "1.1.4 补齐 CapMonster 官方 User-Agent、完整验证链接校验与任务编号诊断。"
            "1.1.5 修复普通卖家在网页版及CLI中下架商品的接口。"
            "1.1.6 统一擦亮接口版本，按平台完成状态记录每日擦亮结果。"
        ),
        "filename": "",
        "download_url": "",
    }
