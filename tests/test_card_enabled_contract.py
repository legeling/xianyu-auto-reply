from __future__ import annotations

import ast
import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel


@pytest.mark.parametrize("handler,model", [("create_card","CardCreate"),("batch_save_card","BatchSaveCardRequest")])
@pytest.mark.parametrize("enabled,expected", [(False,False),(True,True),(None,True)])
def test_card_creation_preserves_explicit_disabled_state(monkeypatch,handler,model,enabled,expected):
    # Exercise the real request model and complete async handler body without starting a database or app.
    path=Path(__file__).resolve().parents[1]/"backend-web/app/api/routes/cards.py"
    source=ast.parse(path.read_text())
    nodes=[]
    for node in source.body:
        if (isinstance(node,ast.ImportFrom) and node.module=="__future__") or (isinstance(node,ast.ClassDef) and node.name==model):
            nodes.append(node)
        elif isinstance(node,ast.AsyncFunctionDef) and node.name==handler:
            node.decorator_list=[]
            node.args.defaults=[ast.Constant(None) for _ in node.args.defaults]
            nodes.append(node)
    module=ModuleType("card_creation_contract")
    monkeypatch.setitem(sys.modules,module.__name__,module)
    module.__dict__.update(BaseModel=BaseModel,Any=Any,Dict=dict,List=list,Optional=Optional,
                           _validate_card_payload=lambda *args,**kwargs:None,
                           ApiResponse=lambda **kwargs:kwargs)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),"exec"),module.__dict__)  # noqa: S102 -- Only selected local handler bodies; no imports or external input.
    payload={"name":"测试发货内容","type":"text","enabled":enabled,"text_content":"测试内容"}
    if handler=="batch_save_card":
        payload["item_ids"]=["fixture-item"]
    request=module.__dict__[model](**payload)
    service=SimpleNamespace(create_card=AsyncMock(return_value=7),
                            batch_save_and_bind=AsyncMock(return_value={"bind_count":1}))
    asyncio.run(module.__dict__[handler](request,SimpleNamespace(id=1),service))
    call=service.create_card if handler=="create_card" else service.batch_save_and_bind
    assert call.await_count==1
    assert call.await_args.kwargs["enabled"] is expected
