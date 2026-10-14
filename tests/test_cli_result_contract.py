from __future__ import annotations

import io
import json
from typing import ClassVar

import pytest

from xianyu_cli import client
from xianyu_cli.client import ApiClient, _extract_error_message, _save_response
from xianyu_cli.exceptions import CliError
from xianyu_cli.output import print_output


class Response(io.BytesIO):
    headers: ClassVar[dict[str, str]] = {"Content-Type":"application/json"}


def test_http_200_business_failure_does_not_overwrite_export(monkeypatch,tmp_path):
    target=tmp_path/"cards.xlsx"
    target.write_bytes(b"previous export")
    monkeypatch.setattr(client,"urlopen",lambda *args,**kwargs:Response(b'{"success":false,"message":"export denied"}'))
    with pytest.raises(CliError,match="export denied"):
        ApiClient("http://test.invalid").request("GET","/export",output_path=str(target))
    assert target.read_bytes()==b"previous export"
    assert list(tmp_path.iterdir())==[target]


def test_business_failure_is_detected_before_printing(monkeypatch,capsys):
    monkeypatch.setattr(client,"urlopen",lambda *args,**kwargs:Response(b'{"success":false,"message":"rejected"}'))
    with pytest.raises(CliError,match="rejected"):
        ApiClient("http://test.invalid").request("POST","/operation",data={})
    assert capsys.readouterr().out==""


def test_validation_errors_do_not_echo_secret_inputs():
    raw=json.dumps({"detail":[{"loc":["body","data_content"],"msg":"invalid value","input":"private-card-stock"}]}).encode()
    message=_extract_error_message(raw)
    assert message=="body.data_content: invalid value"
    assert "private-card-stock" not in message


def test_json_output_masks_secrets_and_handles_list_envelope(capsys):
    print_output({"data":{"list":[{"id":7,"data_content":"private-stock","api_config":{"headers":"private-header"}}]}},json_output=True)
    result=json.loads(capsys.readouterr().out)
    card=result["data"]["list"][0]
    assert card["data_content"]==card["api_config"]["headers"]=="****"
    print_output({"data":{"list":[{"id":7,"name":"下载"}]}},columns=["id","name"])
    assert "下载" in capsys.readouterr().out


def test_table_output_masks_scalar_secrets_before_selecting_columns(capsys):
    print_output({"list":[{"id":7,"data_content":"private-stock","Token":"private-token"}]})
    output=capsys.readouterr().out
    assert "private-stock" not in output and "private-token" not in output
    assert output.count("****")==2


def test_export_is_private_and_failed_replace_preserves_previous_file(monkeypatch,tmp_path):
    target=tmp_path/"export.json"
    _save_response(b"previous",str(target),"application/json")
    assert target.stat().st_mode & 0o777 == 0o600
    def fail(*args):
        raise OSError("cannot replace")
    monkeypatch.setattr(client.os,"replace",fail)
    with pytest.raises(CliError):
        _save_response(b"replacement",str(target),"application/json")
    assert target.read_bytes()==b"previous"
    assert list(tmp_path.iterdir())==[target]


def test_cli_and_web_share_the_fork_release_number():
    from common.version import CURRENT_VERSION
    from xianyu_cli import __version__
    assert __version__==CURRENT_VERSION
