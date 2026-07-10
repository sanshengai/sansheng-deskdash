# __ID__ · __NAME__

> 由 `scripts/new_module.py __ID__` 生成的骨架。把每个 **TODO** 换成真东西,跑 `python scripts/validate_module.py modules/__ID__` 直到全绿。

- **prefix**:`__PREFIX__` / **分类**:misc(改成合适的:time/weather/tasks/dev/system/network…) / **交互**:无

## 用途(what)

TODO:一句话说清这个模块在桌面上显示什么。

## 数据源与探源灯

TODO:数据从哪来?先过探源红绿灯(SKILL §2.4):
- 🟢 公开 API / 用户自备 key 的 API / 本地文件与局域网设备 → 可造、可回流。
- 🟡 需用户自己 cookie 的私有服务 → 仅本地自用,不回流。
- 🔴 绕登录风控 / 反爬 / ToS 禁止 → 不接。

## 配置(config)

复制 `config.example.json` 为 `config.json` 后填。TODO:列出每个配置项含义;**密钥字段**要在 `widget.json` 的 `config.secrets` 报名,示例里留空。

## 依赖与安全

- **依赖**:无(纯 stdlib)。TODO:若真要 requests/Pillow,写进 `widget.json` 的 `deps`(仅这两个被白名单允许)。
- **网络**:TODO 填 `widget.json` 的 `privacy.network`(实际请求域必须与声明一致,validate 会 AST 核对)。**读/写本地**:TODO 填 `privacy.local_read`/`local_write`(只写自身/board 目录)。
- 无 `eval`/`exec`/`shell=True`;`subprocess` 用 list 参数;网络调用带 `timeout`;子进程自限。
- 🔒 密钥只进 gitignore 的 `config.json`,永不入仓/日志/异常。

## 自验

```bash
python collector.py --config config.example.json      # → 单行 JSON,过 output.schema
python ../../scripts/validate_module.py .              # → 全绿才可回流(见 references/contribution.md)
```

## band 带区

见 `band.inc`。约束:局部 Y、段名带 `__PREFIX__` 前缀、中文走 `#变量#`、`band.height` 要诚实容得下内容(references/layout.md)。
