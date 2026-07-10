# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。对外版本号从 v0.1.0 起,与内部 git 提交脱钩。

## v0.1.0 - 2026-07-11

首个公开版本(P0「施工队可用」)。陌生用户装上 skill 说一句「帮我搭个桌面看板」,即可走完 体检 → 60 秒上墙 → 五问 → 装模块 / 现场造 → 常驻桌面 的完整链路。

### 新增

- **五工作流 SKILL.md**:初装 / 加模块(含现场造)/ 改布局 / 排障(半自动自愈)/ 升级与卸载;批量五问话术、探源红绿灯、不接清单、三审阅点、禁术语规则。
- **带区装配器 `assemble.py`**:模块 `band.inc`(局部 Y)按顺序累加拼整板 Rainmeter 皮肤,高度预算校验,`modules.lock.json` 单源;四布局不变量测试兜底。
- **调度器 `orchestrator.py`**:subprocess 隔离 + 强制超时跑各模块采集器,`health.json` 记账,`fail_streak≥3` 灰化,汇总写 `data.inc`(UTF-16);done_date 秒退 / daily_heavy / net-only / interval 四套节流。
- **契约层**:`widget.json` 双段(display + runtime)+ stdlib JSON Schema 子集校验器;结构化错误约定 + secret-canary 防泄漏。
- **官方 6 模块**:clock-calendar / weather / todo(交互旗舰)/ github / net-latency / server-status,均自包含 stdlib、真机截图。
- **部署三件 + 体检**:`deploy_skin.ps1`(UTF-8→UTF-16 + 备份轮换)/ `install_task.ps1`(计划任务,幂等)/ `uninstall.ps1`(防误删栏)/ `doctor.py`(环境体检 + 高度预算)。
- **造件工具**:`new_module.py` 骨架生成 + `validate_module.py`(契约校验 + config.example 过 schema + collector dry-run + 禁止项 AST 扫描)。
- **references 9 篇**:encoding / rainmeter-drawing / layout / interaction / data-sources / security / contribution / troubleshoot / backends。
- **模板与起步板**:`templates/module-skeleton/`(七件套骨架)+ `starter-boards/`(minimal / dev / life)。
- **registry 单源 + 双语 README**:`registry/registry.json` 驱动 `gen_readme_gallery.py` 幂等生成模块画廊;中文为主 README + 英文 README_EN;安全模型诚实声明(v1 无运行时沙箱,四层纵深边界)。

### 安全

- 采集器 stdlib-only 为默认,依赖白名单仅 `requests` / `Pillow`;禁 `eval`/`exec`/`shell=True`/`iwr|iex`。
- 密钥只进 gitignore 的 `config.json`,绝不进代码 / 日志 / 错误消息。
- PowerShell 一律 `-ExecutionPolicy Bypass -File` 调用,不改系统策略、全程无网络下载执行。

### 已知边界

- 仅 Windows。v1 无运行时网络沙箱(边界为声明制 + AST 静态扫描 + VALIDATE + 用户审阅四层)。
- 社区管线(module-ci 11 项 / 机器人自动合并 / 质量评级)属 P1,本版未含。
