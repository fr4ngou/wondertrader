"""本机UI写入口的共同Origin政策；不承担用户认证或交易许可。"""

from urllib.parse import urlsplit

from fastapi import HTTPException


def require_ui_origin(request, message):
    """沿既有回测同源规则；重复身份头和畸形Origin统一拒绝。"""
    for name in ("origin", "host", "sec-fetch-site"):
        if len(request.headers.getlist(name)) > 1:
            raise HTTPException(403, message)
    origin = request.headers.get("origin")
    if origin is not None:
        try:
            parsed = urlsplit(origin)
            allowed = (bool(origin) and not parsed.path and not parsed.query and not parsed.fragment
                       and not parsed.username and not parsed.password
                       and parsed.scheme == request.url.scheme
                       and parsed.netloc == request.headers.get("host"))
        except ValueError:
            allowed = False
        if not allowed:
            raise HTTPException(403, message)
    if request.headers.get("sec-fetch-site") not in (None, "same-origin", "none"):
        raise HTTPException(403, message)
