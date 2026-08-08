# lanzou-resolver

蓝奏云（lanzou）分享链接解析/下载 Python 客户端，仅使用标准库，无任何第三方依赖。

- 支持新版页面（带密码 `kd=1` / 无密码 `kd=0`）
- 支持旧版无密码页面（iframe `/fn?` 流程）
- 自动处理 CDN `acw_sc__v2` JavaScript 挑战
- 解析落地页二次验证，直接返回最终直链
- 附带命令行工具，可选直接下载

## 安装

```bash
pip install lanzou-resolver
```

## Python 使用

```python
from lanzou_resolver import LanzouClient

client = LanzouClient()

# 无密码分享
result = client.resolve("https://wwbou.lanzouq.com/i9te83mgt7cf")

# 带密码分享
result = client.resolve("https://wwbou.lanzouq.com/i0zxZ3d30m8f", "fosv")

print(result.filename)
print(result.direct_url)

# 直接下载
path, sha256 = client.download(result, ".")
```

解析失败或缺少密码时抛出 `LanzouError`。

## 命令行

```bash
# 仅解析
lanzou-resolver "https://wwbou.lanzouq.com/i0zxZ3d30m8f" "fosv"

# 无密码分享可省略密码
lanzou-resolver "https://wwbou.lanzouq.com/i9te83mgt7cf"

# 解析并下载
lanzou-resolver --download --output-dir . "https://wwbou.lanzouq.com/i0zxZ3d30m8f" "fosv"
```

输出为 JSON，包含 `file_id`、文件名、落地页 URL、最终直链；下载模式额外输出保存路径和 SHA-256。

## 限制

- 非官方接口，站点随时可能更换字段、混淆、域名或验证方式，失效需重新逆向
- 不尝试绕过 CAPTCHA；若站点升级为交互式验证码，应停止并人工处理

## 免责声明

本项目仅供学习与技术交流使用，请在使用前仔细阅读并同意以下条款：

1. 本项目基于蓝奏云公开网页的请求流程实现，为非官方工具，与蓝奏云官方无任何关联，不保证持续可用。
2. 本项目仅支持解析**用户已合法获取分享链接及密码**的文件，不得用于绕过访问控制、破解密码或获取无权限访问的内容。
3. 禁止将本项目用于任何违反法律法规、平台规则或侵犯他人权益的用途（包括但不限于批量抓取、盗链、传播侵权或违法违规内容）。
4. 使用者须遵守蓝奏云的服务条款及当地法律法规，因使用本项目产生的任何直接或间接后果，由使用者自行承担，作者不承担任何责任。
5. 如本站点升级验证机制或禁止此类访问，应立即停止使用本项目。

- 源码仓库：<https://github.com/kuankqaq/lanzou-resolver>
