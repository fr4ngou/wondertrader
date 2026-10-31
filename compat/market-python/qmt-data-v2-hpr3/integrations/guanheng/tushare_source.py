"""可选 Tushare 只读能力探测；使用运行环境凭证，保持与 QMT 分钟数据集分离。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TushareSource:
    """仅调用固定只读接口；一次请求、校验证书、禁代理/重定向，不回显远端消息。

    code=0 只证明这一次接口调用成功，行数/时间边界/许可仍需独立核验。
    token 没有可打印属性，异常仅返回固定诊断，结果保留公开字段及行数。
    """

    _APIS = frozenset({"daily", "fund_daily", "stk_mins", "etf_mins", "rt_min", "rt_etf_min"})
    _URL = "https://api.tushare.pro"

    def __init__(self, token: str, *, timeout: float = 10, max_response_bytes: int = 1048576):
        if not isinstance(token, str) or not token or len(token) > 4096 or any(c.isspace() for c in token):
            raise ValueError("缺少有效 TUSHARE_TOKEN")
        if type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise ValueError("Tushare 请求预算越界")
        if type(max_response_bytes) is not int or not 1024 <= max_response_bytes <= 16777216:
            raise ValueError("Tushare 响应预算越界")
        self.__token = token
        self.timeout, self.max_response_bytes = timeout, max_response_bytes
        self._opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), _NoRedirect())

    @classmethod
    def from_env(cls, **kwargs):
        return cls(os.environ.get("TUSHARE_TOKEN", ""), **kwargs)

    def query(self, api_name: str, params: dict, fields: str = "") -> dict:
        """原始表结构独立返回；未合格分钟资料不能通过此入口写入 WT 历史。"""
        if api_name not in self._APIS or not isinstance(params, dict) or not isinstance(fields, str):
            raise ValueError("Tushare 操作或参数不支持")
        payload = json.dumps({"api_name": api_name, "token": self.__token, "params": params, "fields": fields},
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(payload) > 16384:
            raise ValueError("Tushare 请求超过预算")
        request = Request(self._URL, payload, {"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    return {"state": "unavailable", "reason": "HTTP 状态异常"}
                raw = response.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                return {"state": "unavailable", "reason": "响应超过预算"}
            result = json.loads(raw)
            if not isinstance(result, dict) or type(result.get("code")) is not int:
                raise ValueError("schema")
            if result["code"] != 0:
                message = result.get("msg", "")
                category = "source_rejected"
                if isinstance(message, str):
                    if any(word in message for word in ("每分钟", "每小时", "频次", "频率", "次数", "访问该接口")):
                        category = "rate_or_quota"
                    elif any(word in message for word in ("权限", "积分", "开通")):
                        category = "permission"
                return {"state": "unavailable", "reason": "来源接口拒绝请求", "source_code": result["code"],
                        "category": category}
            # 对端可在成功表格或键中回显输入；任何凭证片段均阻断，不流向调用者或探测日志。
            todo = [(result, 0)]
            nodes = 0
            while todo:
                value, depth = todo.pop()
                nodes += 1
                if depth > 16 or nodes > 100000:
                    raise ValueError("response budget")
                if isinstance(value, str) and self.__token in value:
                    raise ValueError("credential echo")
                if isinstance(value, dict):
                    todo.extend((v, depth + 1) for pair in value.items() for v in pair)
                elif isinstance(value, list):
                    todo.extend((v, depth + 1) for v in value)
            data = result.get("data")
            if (not isinstance(data, dict) or not isinstance(data.get("fields"), list)
                    or not all(isinstance(x, str) for x in data["fields"]) or len(set(data["fields"])) != len(data["fields"])
                    or not isinstance(data.get("items"), list)
                    or any(not isinstance(row, list) or len(row) != len(data["fields"]) for row in data["items"])):
                raise ValueError("schema")
            return {"state": "read_verified", "data": data, "qualification": "sample_only"}
        except (HTTPError, URLError, TimeoutError, OSError):
            return {"state": "unavailable", "reason": "TLS/网络请求失败"}
        except (ValueError, TypeError, RecursionError):
            return {"state": "unavailable", "reason": "来源响应格式不合格"}


def main():
    parser = argparse.ArgumentParser(description="使用环境凭证进行有限只读能力探测，输出不含凭证和原始远端错误")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = TushareSource.from_env()
    checks = (
        ("daily", {"ts_code": "600000.SH", "start_date": "20240102", "end_date": "20240102"}),
        ("stk_mins", {"ts_code": "600000.SH", "freq": "1min", "start_date": "2024-01-02 09:31:00", "end_date": "2024-01-02 09:32:00"}),
        ("etf_mins", {"ts_code": "510300.SH", "freq": "1min", "start_date": "2024-01-02 09:31:00", "end_date": "2024-01-02 09:32:00"}),
    )
    receipt = {"endpoint": source._URL, "tls_verified": True, "scope": "sample-and-permission-probe", "checks": {}}
    for name, params in checks:
        result = source.query(name, params)
        table = result.pop("data", None)
        if table is not None:
            result.update(fields=table["fields"], row_count=len(table["items"]))
        receipt["checks"][name] = result
    # TLS 只有实际表读取或业务拒绝响应才能证明，网络失败不授予端点资格。
    receipt["tls_verified"] = any("source_code" in r or r["state"] == "read_verified" for r in receipt["checks"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
