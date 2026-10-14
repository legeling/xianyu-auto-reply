from __future__ import annotations

import ast
import random
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

ROOT=Path(__file__).resolve().parents[1]


def load_functions(path,names,namespace):
    source=ast.parse((ROOT/path).read_text())
    nodes=[node for node in source.body if isinstance(node,ast.ImportFrom) and node.module=='__future__']
    for node in source.body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id in names for target in node.targets):nodes.append(node)
        if isinstance(node,ast.FunctionDef) and node.name in names:nodes.append(node)
        if isinstance(node,ast.ClassDef):
            nodes.extend(child for child in node.body if isinstance(child,ast.FunctionDef) and child.name in names)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(ROOT/path),'exec',dont_inherit=False),namespace)  # noqa: S102 -- Only selected local functions, without app imports or external input.
    return namespace


@pytest.fixture
def payloads():
    namespace={'Any':object,'Dict':dict,'urlsplit':urlsplit}
    return load_functions('common/utils/xianyu_utils.py',{'SLIDER_COOKIE_DOMAINS','trans_cookies','build_slider_cookie_payloads'},namespace)['build_slider_cookie_payloads']


def test_cookie_payload_is_host_scoped_and_preserves_equals(payloads):
    result=payloads('https://h5api.m.goofish.com/punish?secret=challenge','unb=123;session=abc=def;x5sec=old')
    assert result==[{'name':name,'value':value,'domain':'h5api.m.goofish.com','path':'/','secure':True}
                    for name,value in [('unb','123'),('session','abc=def'),('x5sec','old')]]
    assert payloads('https://sec.taobao.com/punish','session=value')[0]['domain']=='sec.taobao.com'


@pytest.mark.parametrize('url',['https://example.com/punish','https://goofish.com.evil.test/punish',
                                'http://h5api.m.goofish.com/punish','https://user:password@h5api.m.goofish.com/punish',
                                'https://h5api.m.goofish.com:8080/punish'])
def test_cookie_payload_rejects_untrusted_origin_without_echoing_credentials(payloads,url):
    with pytest.raises(ValueError) as error:payloads(url,'session=private-session')
    assert 'private-session' not in str(error.value) and 'password' not in str(error.value)


def test_no_session_keeps_the_public_solver_contract(payloads):
    assert payloads('https://example.com/punish','')==[]


def test_actual_browser_run_loads_session_before_navigation_and_closes(payloads,monkeypatch):
    events=[]
    class Timer:
        def __init__(self,*args):pass
        def start(self):events.append('timer started')
        def cancel(self):events.append('timer canceled')
    monkeypatch.setattr(threading,'Timer',Timer)
    logger=SimpleNamespace(**{level:lambda *args:None for level in ['info','warning','error','debug']})
    namespace={'build_slider_cookie_payloads':payloads,'time':SimpleNamespace(time=time.monotonic,sleep=lambda *_:None),
               'random':random,'logger':logger,'urlsplit':urlsplit}
    run=load_functions('common/services/captcha/slider_stealth.py',{'run'},namespace)['run']
    context=SimpleNamespace(add_cookies=lambda cookies:events.append(('cookies',cookies)))
    page=SimpleNamespace(goto=lambda *args,**kwargs:events.append('navigation'),title=lambda:'healthy',content=lambda:'healthy page')
    service=SimpleNamespace(pure_user_id='test',context=context,page=page,_cdp_touch_enabled=True,
                            init_browser=lambda:events.append('init'),close=lambda:events.append('closed'),
                            _check_browser_timeout=lambda *args:False)
    assert run(service,'https://h5api.m.goofish.com/punish',existing_cookies_str='session=private-session')==(True,None)
    assert events[1][0]=='cookies' and events.index('navigation')>1
    assert events[-2:]==['timer canceled','closed']
    events.clear()
    assert run(service,'https://evil.test/punish',existing_cookies_str='session=private-session')==(False,None)
    assert events==['closed']


def test_actual_orchestrator_and_wrapper_forward_the_session():
    captured={}
    slider=SimpleNamespace(run=lambda *args,**kwargs:(captured.update(kwargs) or (True,{'x5sec':'new'})),close=lambda:None)
    logger=SimpleNamespace(**{level:lambda *args:None for level in ['info','warning','error']})
    namespace={'PlaywrightSliderService':lambda **kwargs:slider,'logger':logger,
               'is_real_mouse_slider_mode':lambda *args:False}
    load_functions('common/services/captcha/slider_stealth.py',{'run_slider_verification'},namespace)
    load_functions('common/services/captcha/orchestrator.py',{'_has_x5sec','run_slider_verification_with_fallback'},namespace)
    result=namespace['run_slider_verification_with_fallback']('test','https://h5api.m.goofish.com/punish',existing_cookies_str='session=private-session')
    assert result==(True,{'x5sec':'new'},'playwright')
    assert captured['existing_cookies_str']=='session=private-session'
