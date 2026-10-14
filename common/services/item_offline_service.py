"""使用闲鱼商品详情页的卖家下架接口，保留逐项批量结果。"""
from __future__ import annotations

from common.services.xianyu_mtop import mtop_call

OFFLINE_ITEM_API = "mtop.taobao.idle.item.downshelf"
OFFLINE_ITEM_VERSION = "2.0"


async def batch_offline_items_from_xianyu(
    account_id: str,
    cookies_str: str,
    item_ids: list[str],
    *,
    owner_id: int | None = None,
) -> dict:
    """逐项下架；下架不删除商品或本地发货关联。

    官网接口每次接受一个 itemId。签名、登录态和 Cookie 更新由共享 MTOP 客户端负责。
    至少一项成功时 success 为 True，调用方仍须检查 fail_count。
    """
    cleaned_ids = list(dict.fromkeys(key for raw in item_ids or [] if (key := str(raw or "").strip())))
    results = []
    first_error = ""
    account_invalid = False
    for item_id in cleaned_ids:
        if account_invalid:
            results.append({"item_id": item_id, "success": False})
            continue
        response = await mtop_call(
            account_id,
            cookies_str,
            OFFLINE_ITEM_API,
            OFFLINE_ITEM_VERSION,
            {"itemId": item_id},
            owner_id=owner_id,
            referer=f"https://www.goofish.com/item?id={item_id}",
        )
        cookies_str = response.get("cookies_str") or cookies_str
        success = bool(response.get("success"))
        results.append({"item_id": item_id, "success": success})
        if not success and not first_error:
            first_error = response.get("error") or "下架失败"
        account_invalid = bool(response.get("account_invalid"))

    suc_count = sum(result["success"] for result in results)
    fail_count = len(results) - suc_count
    message = f"下架成功 {suc_count} 个，失败 {fail_count} 个"
    if not cleaned_ids:
        message = "没有有效的商品ID"
    elif not suc_count:
        message = first_error
    return {
        "success": suc_count > 0,
        "message": message,
        "suc_count": suc_count,
        "fail_count": fail_count,
        "results": results,
        "cookies_str": cookies_str,
    }
