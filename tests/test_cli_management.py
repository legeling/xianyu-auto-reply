from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from xianyu_cli.commands import accounts, cards, delivery, items, keywords, orders, publish
from xianyu_cli.main import main


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    def request(method, path, **kwargs):
        recorded.append((method, path, kwargs))
        return {"success": True, "data": {}}

    client = SimpleNamespace(request=request)
    for module in (accounts, cards, delivery, items, keywords, orders, publish):
        monkeypatch.setattr(module, "build_client", lambda args: client)
    return recorded


@pytest.mark.parametrize("arguments,method,path,body", [
    (["cards", "create", "-d", '{"name":"下载","type":"text","enabled":false,"text_content":"链接"}'],
     "POST", "/api/v1/cards", {"name":"下载","type":"text","enabled":False,"text_content":"链接"}),
    (["cards", "update", "7", "-d", '{"data_content":"a\\nb"}'], "PUT", "/api/v1/cards/7", {"data_content":"a\nb"}),
    (["cards", "disable", "7"], "PUT", "/api/v1/cards/7", {"enabled":False}),
    (["cards", "delete", "7"], "DELETE", "/api/v1/cards/7", None),
    (["cards", "bind", "-d", '{"card_ids":[7],"item_ids":["item"]}'], "POST", "/api/v1/cards/batch-bind", {"card_ids":[7],"item_ids":["item"]}),
    (["cards", "set-items", "7", "-d", '{"item_ids":[]}'], "PUT", "/api/v1/cards/7/items", {"item_ids":[]}),
    (["cards", "set-item-cards", "item/name", "-d", '{"card_items":[{"card_id":7,"source":"own"}]}'],
     "PUT", "/api/v1/cards/item/item%2Fname/cards", {"card_items":[{"card_id":7,"source":"own"}]}),
    (["cards", "unbind", "7", "item/name"], "DELETE", "/api/v1/cards/relation/7/item%2Fname", None),
    (["delivery", "switch", "seller/name", "auto_confirm", "false"], "PUT", "/api/v1/cookies/seller%2Fname/auto-confirm", {"auto_confirm":False}),
    (["delivery", "switch", "seller", "only_send_card", "true"], "PUT", "/api/v1/cookies/seller/only-send-card", {"only_send_card":True}),
    (["delivery", "block-rules", "set", "seller", "-d", '{"rules":[]}'], "PUT", "/api/v1/cookies/seller/delivery-block-rules", {"rules":[]}),
    (["delivery", "agree", "set", "seller", "-d", '{"enabled":false}'], "PUT", "/api/v1/agree-deliver/seller", {"enabled":False}),
    (["delivery", "refund", "get", "seller"], "GET", "/api/v1/refund-cancel/seller", None),
    (["items", "sync", "seller", "--page", "2"], "POST", "/api/v1/items/get-by-page", {"cookie_id":"seller","page":2}),
    (["items", "multi-quantity", "seller", "item", "true"], "PUT", "/api/v1/items/seller/item/multi-quantity-delivery", {"multi_quantity_delivery":True}),
    (["items", "offline", "seller", "--item-id", "one", "--item-id", "two"], "POST", "/api/v1/items/batch-offline", {"cookie_id":"seller","item_ids":["one","two"]}),
    (["items", "default-reply", "set", "seller", "item", "-d", '{"reply_content":"说明","enabled":false}'], "PUT", "/api/v1/items/seller/item/default-reply", {"reply_content":"说明","enabled":False}),
    (["orders", "sync", "--account-id", "seller"], "POST", "/api/v1/orders/fetch-xianyu", {"cookie_id":"seller"}),
    (["orders", "deliver", "order/name"], "POST", "/api/v1/orders/manual-delivery", {"order_no":"order/name"}),
    (["orders", "no-logistics", "order"], "POST", "/api/v1/orders/no-logistics-delivery", {"order_no":"order"}),
    (["orders", "cancel", "order"], "POST", "/api/v1/orders/cancel", {"order_no":"order"}),
    (["publish", "materials", "update", "9", "-d", '{"title":"修改"}'], "PUT", "/api/v1/product-publish/materials/9", {"title":"修改"}),
    (["publish", "personal-addresses", "delete", "3", "4"], "POST", "/api/v1/product-publish/personal-addresses/batch-delete", {"ids":[3,4]}),
    (["publish", "addresses", "set-enabled", "3", "false"], "PUT", "/api/v1/product-publish/addresses/3/status", {"is_enabled":False}),
    (["publish", "relist", "set", "9", "-d", '{"enabled":false,"expected_version":3}'], "PUT", "/api/v1/product-publish/materials/9/auto-relist", {"enabled":False,"expected_version":3}),
    (["keywords", "replace", "seller", "-d", '{"keywords":[]}'], "POST", "/api/v1/keywords-with-item-id/seller", {"keywords":[]}),
])
def test_management_commands_submit_one_canonical_request(calls, arguments, method, path, body):
    assert main(arguments) == 0
    assert len(calls) == 1
    actual_method, actual_path, kwargs = calls[0]
    assert (actual_method, actual_path, kwargs.get("data")) == (method, path, body)


def test_keyword_identifiers_and_query_are_not_combined(calls):
    assert main(["keywords", "delete", "seller/name", "价格 & 库存", "--item-id", "item&1", "--rule-id", "8"]) == 0
    method, path, kwargs = calls[0]
    assert method == "DELETE"
    assert path == "/api/v1/keywords-with-item-id/seller%2Fname/%E4%BB%B7%E6%A0%BC%20%26%20%E5%BA%93%E5%AD%98"
    assert kwargs["params"] == {"item_id":"item&1","rule_id":8}


def test_old_order_and_keyword_queries_keep_their_existing_contract(calls):
    assert main(["orders", "--account-id", "seller"]) == 0
    assert calls[-1][2]["params"]["cookie_id"] == "seller"
    assert main(["orders", "list", "--account-id", "seller", "--delivery-method", "auto"]) == 0
    assert calls[-1][2]["params"]["delivery_method"] == "auto"
    assert main(["keywords", "--account-id", "seller"]) == 0
    assert calls[-1][1] == "/api/v1/keywords-with-item-id/seller"


def test_order_table_uses_the_backend_order_response_fields(monkeypatch,capsys):
    response={"success":True,"data":[{"order_id":"example-order","cookie_id":"example-account","amount":"28.00",
                                       "item_id":"example-item","delivery_content":"private-stock"}]}
    monkeypatch.setattr(orders,"build_client",lambda args:SimpleNamespace(request=lambda *args,**kwargs:response))
    assert main(["orders","list"])==0
    output=capsys.readouterr().out
    assert all(value in output for value in ['example-order','example-account','28.00'])
    assert 'private-stock' not in output
    assert main(["--json","orders","list"])==0
    assert json.loads(capsys.readouterr().out)['data'][0]['delivery_content']=='****'


def test_automatic_delivery_logs_select_actual_delivery_messages(calls):
    assert main(["delivery", "logs", "--account-id", "seller", "--send-status", "failed"]) == 0
    assert calls[0][2]["params"]["message_type"] == "auto_delivery"
    assert calls[0][2]["params"]["send_status"] == "failed"


def test_card_list_is_paginated_and_does_not_fetch_all_secrets(calls):
    assert main(["cards", "list"]) == 0
    assert calls[0][2]["params"]["lite"] is True
    assert calls[0][2]["params"]["page_size"] is None


def test_batch_save_detects_missing_bindings_without_retry(monkeypatch,capsys):
    recorded=[]
    def request(*args,**kwargs):
        recorded.append(args)
        return {"success":True,"data":{"card_id":7,"bind_count":1}}
    monkeypatch.setattr(cards,"build_client",lambda args:SimpleNamespace(request=request))
    assert main(["--json","cards","batch-save","-d",'{"item_ids":["one","two"],"name":"test","type":"text"}'])==1
    assert len(recorded)==1
    output=capsys.readouterr()
    assert json.loads(output.out)["data"]["card_id"]==7
    assert "未自动重复提交" in output.err


def test_upload_preserves_repeated_files_field(calls, tmp_path):
    paths = [str(tmp_path / "a.png"), str(tmp_path / "b.png")]
    assert main(["publish", "upload-images", *paths]) == 0
    assert [(part.field,part.path) for part in calls[0][2]["files"]] == [("files",path) for path in paths]


@pytest.mark.parametrize("arguments", [
    ["cards","create"], ["delivery","block-rules","set","seller"],
    ["items","edit","seller","item"], ["publish","relist","set","9"],
])
def test_missing_mutation_payload_never_reaches_backend(calls, arguments):
    with pytest.raises(SystemExit):
        main(arguments)
    assert calls == []


@pytest.mark.parametrize("arguments", [["orders","deliver","order"],["delivery","switch","seller","auto_confirm","true"],["cards","enable","7"]])
def test_business_rejection_is_nonzero_and_not_retried(monkeypatch, arguments):
    calls=[]
    def request(*args, **kwargs):
        calls.append(args)
        return {"success":False,"message":"业务拒绝"}
    for module in (orders,delivery,cards):
        monkeypatch.setattr(module,"build_client",lambda args:SimpleNamespace(request=request))
    assert main(arguments) == 1
    assert len(calls) == 1


def test_finished_batch_with_failures_is_not_reported_as_success(monkeypatch):
    client=SimpleNamespace(request=lambda *args,**kwargs:{"success":True,"data":{"finished":True,"failed":1}})
    monkeypatch.setattr(publish,"build_client",lambda args:client)
    assert main(["publish","status","batch"]) == 1


def test_stock_counts_nonempty_lines_without_leaking_card_data(monkeypatch,capsys):
    client=SimpleNamespace(request=lambda *args,**kwargs:{"id":7,"type":"data","enabled":False,"data_content":"secret-one\n\n secret-two\r\n"})
    monkeypatch.setattr(cards,"build_client",lambda args:client)
    assert main(["--json","cards","stock","7"]) == 0
    result=json.loads(capsys.readouterr().out)
    assert result["remaining_line_count"] == 2
    assert "data_content" not in result


def test_account_lookup_selects_exact_match_and_pages(monkeypatch,capsys):
    calls=[]
    def request(method,path,**kwargs):
        page=kwargs["params"]["page"]
        calls.append(page)
        return {"data":[{"id":"seller-extra" if page==1 else "seller","value":"private-cookie"}],"total_pages":2}
    monkeypatch.setattr(accounts,"build_client",lambda args:SimpleNamespace(request=request))
    assert main(["--json","accounts","get","seller"]) == 0
    result=json.loads(capsys.readouterr().out)
    assert result["id"] == "seller"
    assert result["value"] == "****"
    assert calls == [1,2]
