"""使用部署 owner 注入的 MinIO 客户端保存内容寻址历史证据。

模块导入仅依赖标准库 SDK；可选工厂及 SDK 异常识别按需加载存储依赖。
部署 owner 负责命名空间、有限 IO 与不可变保留策略。
"""
from __future__ import annotations

import hashlib
import io
import ipaddress
import math
import re
import sys
import time
from urllib.parse import urlsplit

from . import strict_json
from .history_runner import canonical_bytes

__all__ = ["MinioEvidenceSink", "create_minio_evidence_sink", "EvidenceUnavailable", "EvidenceConflict"]

MAX_BYTES = 16 * 1024 * 1024


class EvidenceUnavailable(OSError):
    """存储结果不可用或未知，后续同摘要读取可核实恢复。"""


class EvidenceConflict(ValueError):
    """证据身份、规范内容或受管命名空间冲突。"""


def _configuration(bucket, prefix, timeout, max_bytes):
    if (type(bucket) is not str or not 3 <= len(bucket) <= 63
            or re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", bucket) is None
            or any(not label or label.startswith("-") or label.endswith("-") for label in bucket.split("."))):
        raise EvidenceConflict("history evidence namespace invalid")
    try:
        ipaddress.ip_address(bucket)
    except ValueError:
        pass
    else:
        raise EvidenceConflict("history evidence namespace invalid")
    if (type(prefix) is not str or not 1 <= len(prefix) <= 512
            or any(part in ("", ".", "..") or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", part) is None
                   for part in prefix.split("/"))):
        raise EvidenceConflict("history evidence namespace invalid")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 1 <= timeout <= 30:
        raise EvidenceConflict("history evidence budget invalid")
    if type(max_bytes) is not int or not 1024 <= max_bytes <= MAX_BYTES:
        raise EvidenceConflict("history evidence size limit invalid")


def _hash(sha256):
    if type(sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise EvidenceConflict("history evidence digest invalid")


def _missing(error):
    # 仅 SDK 的明确缺失码可授予写入；普通异常和同名属性不构成证明。
    try:
        from minio.error import S3Error
    except ImportError:
        return False
    return isinstance(error, S3Error) and error.code in {"NoSuchKey", "NoSuchObject", "NotFound"}


class MinioEvidenceSink:
    """固定命名空间内的证据读写，不创建 bucket、列举、删除或自动重发写入。

    timeout 是完整 put/get 复合调用的预算，注入客户端同时须限制 IO 并关闭重试。
    截止检查无法抢占阻塞的 owner 调用及资源清理，强制执行上界由外部监督者负责。
    """
    def __init__(self, client, *, bucket: str, prefix: str, timeout: float, max_bytes: int = MAX_BYTES):
        _configuration(bucket, prefix, timeout, max_bytes)
        if not callable(getattr(client, "get_object", None)) or not callable(getattr(client, "put_object", None)):
            raise EvidenceConflict("history evidence client invalid")
        if getattr(type(client), "history_single_exchange", None) is not True:
            raise EvidenceConflict("history evidence single exchange contract required")
        # SDK 实例必然已加载模块；这里不为普通 owner wrapper 引入可选依赖。
        sdk_type = getattr(sys.modules.get("minio"), "Minio", None)
        if sdk_type is not None and isinstance(client, sdk_type) and type(client)._execute is sdk_type._execute:
            raise EvidenceConflict("history evidence SDK retry contract invalid")
        self.client, self.bucket, self.prefix = client, bucket, prefix
        self.timeout, self.max_bytes = float(timeout), max_bytes

    def _object(self, sha256):
        _hash(sha256)
        return self.prefix + "/" + sha256 + ".json"

    @staticmethod
    def _check(deadline):
        if time.monotonic() >= deadline:
            raise EvidenceUnavailable("history evidence deadline exceeded") from None

    def _validate(self, sha256, payload):
        if type(payload) is not bytes or not payload or len(payload) > self.max_bytes:
            raise EvidenceConflict("history evidence content invalid")
        try:
            if hashlib.sha256(payload).hexdigest() != sha256 or canonical_bytes(strict_json(payload)) != payload:
                raise ValueError
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
            raise EvidenceConflict("history evidence content invalid") from None

    def _read(self, sha256, name, deadline, *, allow_missing=False):
        self._check(deadline)
        try:
            response = self.client.get_object(self.bucket, name)
        except Exception as error:
            self._check(deadline)
            if allow_missing and _missing(error):
                return None
            raise EvidenceUnavailable("history evidence read unavailable") from None
        cleanup_failed = False
        try:
            self._check(deadline)
            headers = getattr(response, "headers", {})
            length = headers.get("Content-Length")
            if length is not None:
                if (type(length) is not str or not length.isascii() or not length.isdecimal()
                        or len(length) > 9 or int(length) > self.max_bytes):
                    raise EvidenceConflict("history evidence response limit invalid")
            chunks, count = [], 0
            while True:
                self._check(deadline)
                chunk = response.read(min(65536, self.max_bytes + 1 - count))
                self._check(deadline)
                if type(chunk) is not bytes:
                    raise EvidenceUnavailable("history evidence read unavailable")
                if not chunk:
                    break
                chunks.append(chunk)
                count += len(chunk)
                if count > self.max_bytes:
                    raise EvidenceConflict("history evidence content exceeds limit")
            if length is not None and count != int(length):
                raise EvidenceUnavailable("history evidence response truncated")
            payload = b"".join(chunks)
        finally:
            try:
                response.close()
            except Exception:
                cleanup_failed = True
            try:
                response.release_conn()
            except Exception:
                cleanup_failed = True
        self._check(deadline)
        if cleanup_failed:
            raise EvidenceUnavailable("history evidence response cleanup unavailable")
        self._validate(sha256, payload)
        self._check(deadline)
        return payload

    def get(self, sha256: str) -> bytes:
        """按摘要读取并验真内容，每条返回路径均释放响应资源。"""
        name = self._object(sha256)
        deadline = time.monotonic() + self.timeout
        try:
            return self._read(sha256, name, deadline)
        except (EvidenceUnavailable, EvidenceConflict):
            raise
        except Exception:
            raise EvidenceUnavailable("history evidence read unavailable") from None

    def resolve(self, object_ref: str) -> bytes:
        """只读取本 sink 派生的完整 URI，摘要与规范内容继续由 get 验证。"""
        if type(object_ref) is not str or len(object_ref) > 2048:
            raise EvidenceConflict("history evidence reference invalid")
        match = re.fullmatch(re.escape("minio://" + self.bucket + "/" + self.prefix + "/")
                             + r"([0-9a-f]{64})\.json", object_ref)
        if match is None:
            raise EvidenceConflict("history evidence reference invalid")
        return self.get(match.group(1))

    def put(self, sha256: str, canonical: bytes) -> str:
        """先核查同摘要对象，缺失才单次写入，读回完整一致后返回受管引用。"""
        name = self._object(sha256)
        deadline = time.monotonic() + self.timeout
        self._validate(sha256, canonical)
        try:
            current = self._read(sha256, name, deadline, allow_missing=True)
            if current is None:
                self._check(deadline)
                # 上限内固定单次 PUT，避免 SDK 隐式多段上传及后台并行生命周期。
                self.client.put_object(self.bucket, name, io.BytesIO(canonical), len(canonical), content_type="application/json",
                                       part_size=MAX_BYTES, num_parallel_uploads=1)
                self._check(deadline)
                current = self._read(sha256, name, deadline)
            if current != canonical:
                raise EvidenceConflict("history evidence immutable content conflict")
            self._check(deadline)
            return "minio://" + self.bucket + "/" + name
        except (EvidenceUnavailable, EvidenceConflict):
            raise
        except Exception:
            raise EvidenceUnavailable("history evidence write result unknown") from None


def create_minio_evidence_sink(*, endpoint: str, bucket: str, prefix: str, access_key: str,
                               secret_key: str, secure: bool = True, region: str,
                               timeout: float, max_bytes: int = MAX_BYTES, session_token: str | None = None):
    """storage extra 可选工厂，所有运行配置由调用者显式提供。

    TLS 保持验证；明文 HTTP 仅接受字面 loopback IP。
    显式 region 避免隐式发现请求；工厂不读取环境变量。
    """
    _configuration(bucket, prefix, timeout, max_bytes)
    try:
        if (type(endpoint) is not str or not endpoint or len(endpoint) > 512
                or any(ord(c) <= 32 or ord(c) > 126 for c in endpoint) or "\\" in endpoint):
            raise ValueError
        url = urlsplit("//" + endpoint)
        if not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
            raise ValueError
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError
        if type(secure) is not bool or (not secure and not ipaddress.ip_address(url.hostname).is_loopback):
            raise ValueError
        if type(region) is not str or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", region) is None:
            raise ValueError
        for value in (access_key, secret_key) + (() if session_token is None else (session_token,)):
            if type(value) is not str or not 1 <= len(value) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in value):
                raise ValueError
    except (ValueError, TypeError):
        raise EvidenceConflict("history evidence transport configuration invalid") from None
    try:
        import minio
        import urllib3
        from minio import Minio

        if minio.__version__ != "7.2.20" or urllib3.__version__ != "2.7.0":
            raise EvidenceUnavailable("history evidence storage version unavailable")

        class SingleExchangeMinio(Minio):
            # 私有接缝只适用于已核实的精确版本；升级依赖必须重新验真。
            # 官方 _execute 会在 RetryHead 后重发任意 method，包括已提交的 PUT。
            # 保留官方签名/序列化/错误解析，只将交换入口统一收敛为一次调用。
            history_single_exchange = True

            def _execute(self, method, bucket_name=None, object_name=None, body=None, headers=None,
                         query_params=None, preload_content=True, no_body_trace=False):
                region = self._get_region(bucket_name)
                return self._url_open(method, region, bucket_name=bucket_name, object_name=object_name,
                                      body=body, headers=headers, query_params=query_params,
                                      preload_content=preload_content, no_body_trace=no_body_trace)

        http = urllib3.PoolManager(timeout=urllib3.Timeout(total=float(timeout), connect=float(timeout), read=float(timeout)),
                                   retries=False, cert_reqs="CERT_REQUIRED")
        client = SingleExchangeMinio(endpoint, access_key=access_key, secret_key=secret_key, session_token=session_token,
                                     secure=secure, region=region, http_client=http, cert_check=True)
        return MinioEvidenceSink(client, bucket=bucket, prefix=prefix, timeout=timeout, max_bytes=max_bytes)
    except EvidenceUnavailable:
        raise
    except Exception:
        raise EvidenceUnavailable("history evidence storage dependency unavailable") from None
