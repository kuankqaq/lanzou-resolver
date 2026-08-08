"""蓝奏云密码分享解析/下载核心（仅标准库）。"""

from __future__ import annotations

import gzip
import hashlib
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path

ACW_PERMUTATION = (
    0x0F, 0x23, 0x1D, 0x18, 0x21, 0x10, 0x01, 0x26, 0x0A, 0x09,
    0x13, 0x1F, 0x28, 0x1B, 0x16, 0x17, 0x19, 0x0D, 0x06, 0x0B,
    0x27, 0x12, 0x14, 0x08, 0x0E, 0x15, 0x20, 0x1A, 0x02, 0x1E,
    0x07, 0x04, 0x11, 0x05, 0x03, 0x1C, 0x22, 0x25, 0x0C, 0x24,
)
ACW_XOR_KEY = "3000176000856006061501533003690027800375"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

LANZOU_DOMAINS = (
    "lanzou.com", "lanzou.cn", "lanzoui.com", "lanzoux.com",
    "lanzouw.com", "lanzouv.com", "lanzouo.com", "lanzoup.com",
    "lanzouq.com", "lanzouj.com", "lanzoug.com", "lanzouf.com",
    "lanzouh.com", "lanzoue.com", "lanzoud.com", "lanzouc.com",
    "lanzoub.com", "lanzoua.com", "lanzous.com", "lanzouy.com",
    "lanzoul.com",
)

__all__ = [
    "LANZOU_DOMAINS",
    "LanzouError",
    "ResolveResult",
    "LanzouClient",
]


class LanzouError(RuntimeError):
    pass


@dataclass
class ResolveResult:
    share_url: str
    file_id: str
    filename: str
    landing_url: str
    direct_url: str


def compute_acw_sc_v2(arg1: str) -> str:
    if not re.fullmatch(r"[0-9A-Fa-f]{40}", arg1):
        raise LanzouError(f"unexpected arg1 value: {arg1!r}")
    reordered = "".join(arg1[index - 1] for index in ACW_PERMUTATION)
    return "".join(
        f"{int(reordered[i:i + 2], 16) ^ int(ACW_XOR_KEY[i:i + 2], 16):02x}"
        for i in range(0, 40, 2)
    )


def _decode_response(response: urllib.response.addinfourl, body: bytes) -> str:
    charset = response.headers.get_content_charset() or "utf-8"
    return body.decode(charset, errors="replace")


def _safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "download.bin"


class LanzouClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def _open(
        self,
        url: str,
        *,
        data: dict[str, str] | None = None,
        referer: str | None = None,
        ajax: bool = False,
    ) -> tuple[urllib.response.addinfourl, bytes]:
        payload = None if data is None else urllib.parse.urlencode(data).encode("utf-8")
        headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
        if referer:
            headers["Referer"] = referer
        if ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        request = urllib.request.Request(url, data=payload, headers=headers)
        try:
            response = self.opener.open(request, timeout=self.timeout)
            body = response.read()
            encoding = response.headers.get("Content-Encoding", "").lower()
            if encoding == "gzip":
                body = gzip.decompress(body)
            elif encoding == "deflate":
                body = zlib.decompress(body)
            return response, body
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise LanzouError(f"HTTP {exc.code} for {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LanzouError(f"request failed for {url}: {exc.reason}") from exc

    def _set_acw_cookie(self, url: str, value: str) -> None:
        host = urllib.parse.urlsplit(url).hostname
        if not host:
            raise LanzouError(f"invalid URL: {url}")
        cookie = http.cookiejar.Cookie(
            version=0,
            name="acw_sc__v2",
            value=value,
            port=None,
            port_specified=False,
            domain=host,
            domain_specified=False,
            domain_initial_dot=False,
            path="/",
            path_specified=True,
            secure=False,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False,
        )
        self.cookies.set_cookie(cookie)

    def get_share_page(self, share_url: str) -> str:
        response, body = self._open(share_url)
        html = _decode_response(response, body)
        challenge = re.search(r"var\s+arg1\s*=\s*['\"]([0-9A-Fa-f]{40})", html)
        if challenge:
            self._set_acw_cookie(share_url, compute_acw_sc_v2(challenge.group(1)))
            response, body = self._open(share_url)
            html = _decode_response(response, body)
        # 新版页面走 ajaxm.php，旧版无密码页面走 /fn? 的 iframe
        if "ajaxm.php" not in html and "/fn?" not in html:
            raise LanzouError("share page did not expose the expected download API")
        return html

    @staticmethod
    def parse_share_page(html: str) -> tuple[str, str]:
        active = re.sub(r"/\*.*?\*/", "", html, flags=re.DOTALL)
        endpoint_match = re.search(r"['\"](/ajaxm\.php\?file=(\d+))['\"]", active)
        sign_match = re.search(r"['\"]sign['\"]\s*:\s*['\"]([^'\"]+)['\"]", active)
        if not endpoint_match or not sign_match:
            raise LanzouError("could not parse file id/sign from share page")
        return endpoint_match.group(1), sign_match.group(1)

    def resolve(self, share_url: str, password: str | None = None) -> ResolveResult:
        html = self.get_share_page(share_url)
        # 页面含密码输入框说明该分享设置了密码
        requires_password = 'id="pwd"' in html or "passwddiv" in html
        if requires_password and not password:
            raise LanzouError("该分享需要密码")

        filename_hint: str | None = None
        if "ajaxm.php" in html:
            # 新版页面：签名直接在分享页 JS 中
            endpoint, sign = self.parse_share_page(html)
            file_id = urllib.parse.parse_qs(urllib.parse.urlsplit(endpoint).query)["file"][0]
            payload: dict[str, str] = {
                "action": "downprocess",
                "sign": sign,
                "kd": "1" if requires_password else "0",
                "p": password if requires_password else "",
            }
        else:
            # 旧版无密码页面：签名在 iframe /fn? 加载的脚本中
            fid_match = re.search(r"var\s+fid\s*=\s*(\d+)", html)
            iframe_match = re.search(r"iframe[^>]*src=['\"](/fn\?[^'\"]+)", html)
            if not fid_match or not iframe_match:
                raise LanzouError("unsupported fallback share page structure")
            file_id = fid_match.group(1)
            endpoint = f"/ajaxm.php?file={file_id}"
            fn_response, fn_body = self._open(
                urllib.parse.urljoin(share_url, iframe_match.group(1)), referer=share_url
            )
            fn_html = _decode_response(fn_response, fn_body)
            sign_match = re.search(r"var\s+wp_sign\s*=\s*['\"]([^'\"]+)['\"]", fn_html)
            ajaxdata_match = re.search(r"var\s+ajaxdata\s*=\s*['\"]([^'\"]*)['\"]", fn_html)
            if not sign_match:
                raise LanzouError("could not parse sign from fallback download page")
            ajaxdata = ajaxdata_match.group(1) if ajaxdata_match else ""
            payload = {
                "action": "downprocess",
                "sign": sign_match.group(1),
                "websignkey": ajaxdata,
                "signs": ajaxdata,
                "websign": "",
                "kd": "0",
                "ves": "1",
            }
            title = re.search(r"<title>([^<]+?)\s*[_-]\s*蓝奏云", html)
            filename_hint = title.group(1).strip() if title else None

        api_url = urllib.parse.urljoin(share_url, endpoint)
        response, body = self._open(api_url, data=payload, referer=share_url, ajax=True)
        result = json.loads(_decode_response(response, body))
        if str(result.get("zt")) != "1":
            raise LanzouError(f"password API rejected request: {result.get('inf', result)!r}")

        filename = result.get("inf") or filename_hint or "download.bin"
        dom = result.get("dom") or "https://slssctm.dmpdmp.com"
        landing_url = dom.rstrip("/") + "/file/" + result["url"]
        response, body = self._open(landing_url, referer=share_url)
        content_type = response.headers.get_content_type()
        if content_type != "text/html":
            return ResolveResult(
                share_url=share_url,
                file_id=file_id,
                filename=filename,
                landing_url=landing_url,
                direct_url=response.geturl(),
            )

        landing_html = _decode_response(response, body)
        active = re.sub(r"/\*.*?\*/", "", landing_html, flags=re.DOTALL)
        file_match = re.search(r"['\"]file['\"]\s*:\s*['\"]([^'\"]+)['\"]", active)
        sign_match = re.search(r"['\"]sign['\"]\s*:\s*['\"]([^'\"]+)['\"]", active)
        ajax_match = re.search(r"url\s*:\s*['\"]([^'\"]*ajax\.php)['\"]", active)
        if not file_match or not sign_match or not ajax_match:
            raise LanzouError("download landing page did not expose its verification API")
        verify_url = urllib.parse.urljoin(landing_url, ajax_match.group(1))
        time.sleep(2.1)
        response, body = self._open(
            verify_url,
            data={"file": file_match.group(1), "el": "2", "sign": sign_match.group(1)},
            referer=landing_url,
            ajax=True,
        )
        verify = json.loads(_decode_response(response, body))
        if str(verify.get("zt")) != "1" or not verify.get("url"):
            raise LanzouError(f"download verification failed: {verify!r}")
        return ResolveResult(
            share_url=share_url,
            file_id=file_id,
            filename=filename,
            landing_url=landing_url,
            direct_url=verify["url"],
        )

    def download(self, result: ResolveResult, output_dir: Path) -> tuple[Path, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / _safe_filename(result.filename)
        response, body = self._open(result.direct_url, referer=result.landing_url)
        path.write_bytes(body)
        return path, hashlib.sha256(body).hexdigest()
