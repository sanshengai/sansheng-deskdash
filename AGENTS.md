# AGENTS.md — sansheng-deskdash 多宿主桥

给非 Claude-Code 宿主(Codex / Cursor 等)的入口说明。本仓的**大脑是 `SKILL.md`**,先读它。

## 这是什么

一个让 AI Agent 当"桌面看板施工队"的工具仓(**仅 Windows**):体检环境 → 现场写只读采集器 → 把数据装配成 Rainmeter 皮肤贴壁纸常驻 → 坏了半自动重修。面向非程序员设计。

## 五工作流(全在 SKILL.md)

初装 / 加模块(含现场造) / 改布局 / 排障 / 升级与卸载。每个分支的具体命令行在 `SKILL.md` 对应小节,别自行发明流程。

## 入口命令(真实签名见 SKILL.md 通用速查表)

- `python scripts/doctor.py` — 环境体检,输出 JSON(含 `height_budget`)。
- `python scripts/assemble.py --board <board> --size M [--budget N] [--modules a,b,c] [--out path]` — band.inc 拼整板 .ini。
- `python scripts/orchestrator.py --board <board> [--net-only] [--only a,b]` — 跑采集器写 `data.inc`。
- `python scripts/validate_module.py <module_dir>` / `python scripts/new_module.py <id>` — 校验门 / 造件。
- `powershell -ExecutionPolicy Bypass -File scripts/deploy_skin.ps1 -Board <board> -SkinName Deskdash` — 部署皮肤。
- `powershell -ExecutionPolicy Bypass -File scripts/install_task.ps1 -Board <board>` — 注册常驻任务。
- `powershell -ExecutionPolicy Bypass -File scripts/uninstall.ps1 -Board <board> -Force` — 卸载(无 `-Force` 只打印)。

## 契约与踩坑文档

- 模块契约:`schemas/widget.schema.json`(display + runtime 双段);官方模块在 `modules/`(6 个)。
- 踩坑沉淀:`references/`(encoding / rainmeter-drawing / layout / interaction / data-sources / security / contribution / troubleshoot / backends)。

## 安全红线(不可越,详见 SKILL.md §6/§7 与 references/security.md)

- 三审阅点:装模块前朗读 privacy 三元组 / 现场写码后 VALIDATE 展示网络目标与输出 / 注册计划任务前确认。
- collector 只读外部、只写自身目录;禁 `eval`/`exec`/`shell=True`/`iwr|iex`;禁读浏览器 cookie/凭据;禁访问未声明域名;皮肤禁 `!Execute`/远程加载。
- 依赖 `deps ⊆ [requests, Pillow]`,stdlib-only 为默认;密钥只进 gitignore 的 `config.json`,绝不进代码/日志/错误。
- 探源红绿灯:🟢 公开 API/自备 key/局域网 → 造;🟡 用户自供 cookie 的私有服务 → 仅本地自用不回流;🔴 绕登录风控/反爬/ToS 禁止(银行券商社交私有接口)→ 拒绝。

契约与脚本本身宿主无关;v1 主打 Claude Code,不为其他宿主做专门实现。
