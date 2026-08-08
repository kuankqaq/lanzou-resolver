#!/usr/bin/env python3
"""lanzou-resolver 命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .client import LanzouClient, LanzouError


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="lanzou-resolver",
        description="解析蓝奏云分享链接（支持带密码/无密码/旧版页面），可选直接下载。",
    )
    parser.add_argument("url", help="蓝奏云分享链接")
    parser.add_argument("password", nargs="?", default=None, help="分享密码（无密码分享可省略）")
    parser.add_argument("--download", action="store_true", help="解析后直接下载文件")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd(), help="下载目录")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP 超时秒数")
    args = parser.parse_args()

    try:
        client = LanzouClient(timeout=args.timeout)
        result = client.resolve(args.url, args.password)
        output = asdict(result)
        if args.download:
            path, digest = client.download(result, args.output_dir)
            output.update(downloaded_to=str(path.resolve()), sha256=digest)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (LanzouError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
