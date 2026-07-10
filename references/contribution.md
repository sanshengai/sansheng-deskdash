# contribution · 回流流程(P0 版)

把现场造的好模块脱敏后提回社区仓,别人就能直接装。**P0 只讲回流流程与本地自查**;CI 十一项、机器人自动合并、质量评级细则留 P1。

> ## 🔒 社区模块写法铁律(所有贡献者必读)
> **自包含内联优先于 DRY**:模块要能把整个目录**拷走独立跑**——collector **不 import 仓内 `scripts/lib`**,orchestrator **不注 `PYTHONPATH`**;需要的小工具**内联复制**进模块。若内联了**非平凡算法**(如温度曲线的 Catmull-Rom 换算),**必须加一条 drift-guard 测试**断言内联版与 `lib` 版等价(范本 `tests/test_official_modules.py::test_weather_temp_curve_matches_lib`)。这条不是洁癖,是"模块可移植"这个核心属性的代价与保险。

## 1. agent 是第一贡献者(流程要能被 agent 全自动走完)

回流的每一步——生成骨架、写 collector、本地校验、写 PR 材料、往 registry 追加一条——都**设计成 agent 能自动完成**,用户只需**点头**。所以话术、命令、模板都要"agent 照着就能跑",不留只有人能做的隐性步骤。

## 2. 模块目录七件套

一个合规模块目录 `modules/<id>/` 含:

| 文件 | 作用 |
|---|---|
| `collector.py` | 采集器(`--config`,stdout 单行 JSON;自包含 stdlib) |
| `band.inc` | 带区(局部 Y;段名带 prefix;中文走 `#变量#`) |
| `widget.json` | 契约(display + runtime 双段) |
| `output.schema.json` | 输出契约(扁平标量;字段只增不删) |
| `config.schema.json` | 配置契约(`additionalProperties:false`) |
| `config.example.json` | 配置示例(**不含真密钥**) |
| `README.md` | 用途 / 配置 / 依赖与安全 / 自验 |

(外加发布时补 `screenshot.png` ≥ 640×360;P0 造件不强制,发布前补。)

## 3. 回流步骤(agent 自动走)

```
python scripts/new_module.py <id>          # 1. 生成骨架(拷自 templates/module-skeleton/,替换 id/prefix/name)
# 2. 编辑 modules/<id>/collector.py 写只读采集逻辑;band.inc 画带区;填 widget.json 的 privacy/output.schema
python scripts/validate_module.py modules/<id>   # 3. 本地校验(与未来 CI 同款),必须先绿
# 4. registry/registry.json 追加一条(id / 双语 name / category / owner)
# 5. 开 PR(PR 模板勾选清单;附 validate 通过截图/输出)
```

- **`validate_module.py` 本地先绿**是硬门:它做 widget 契约校验、config.example 过 schema、schema 关键字"假信心"检查、AST 禁用调用 + 域名核对、`network-opaque` 标记、VALIDATE 试跑打印真实网络目标与输出。绿了才提 PR(见 `validate_module.py` 与 `security.md`)。
- **registry 恰好追加一条**,且 `id == 目录名`;不改别人的条目。

## 4. 质量分级(概念,机器人评定,禁自评)

分级**由机器人评定并存进 registry,作者不能自己标**:

| tier | 达标 |
|---|---|
| **Bronze** | CI 全绿(契约 / 校验 / 布局不变量 / 安全静态项全过) |
| **Silver** | Bronze + fixture 测试 + 降级路径 + `config.example` 完整 |
| **Gold** | Silver + 连续 4 周 weekly-probe 活体探测(仅无密钥 API)+ owner 30 天响应承诺 |

展示按 `tier → updated_at` 排序。P0 先把六个官方模块 + 起步板铺上,货架不空;评级机制本体是 P1/P2 的事。

## 5. 回流邀请话术(装好之后,别省)

装好一个现场造的模块后,主动邀请:

> "愿意的话,我把它脱敏整理成 PR 提到社区仓,其他 <同类用户> 就能直接装——我把代码、说明、截图都写好,你只要点个头。"

- **🟡 黄灯源**(需用户自己 cookie 的私有服务,如自家 NAS/路由器):**仅本地自用,不回流**。造归造,不进公开仓——话术里说清"这是你自己的凭据,只在你机器上用"。
- **🔴 红灯源**(绕登录风控 / 反爬 / ToS 禁止):直接拒绝造,更不回流(见 SKILL §2.4/2.5)。

## 6. PR 应包含

- 新增 `modules/<id>/` 七件套;
- `registry/registry.json` 追加一条;
- `validate_module.py` 通过的证据(输出粘贴);
- README 里的 privacy 三元组与降级说明对得上 widget.json。

**CI 细节(11 项检查、机器人评论、自动合并阈值、owner/adoption/attic 治理)见 P1 计划,不在本篇。**

## 7. registry.json 结构(单源画廊数据)

`registry/registry.json` 是模块画廊的**单一数据源**:`scripts/gen_readme_gallery.py` 读它幂等生成中英 README 里 `<!-- GALLERY:START -->` / `<!-- GALLERY:END -->` 之间的表格(勿手改表格,改数据源后重跑脚本)。

```jsonc
{
  "schema_version": 1,
  "modules": [
    {
      "id": "clock-calendar",           // = 模块目录名(唯一)
      "name": "时钟日历",                // 中文名(= widget.json display.name)
      "name_en": "Clock & Calendar",    // 英文名(= display.name_en)
      "category": "time",               // 类目(= display.category)
      "author": "sansheng",             // 作者(= display.author)
      "version": "0.1.0",               // 版本(= display.version)
      "tier": "bronze",                 // 质量评级:bronze|silver|gold —— 由社区机器人评定,作者禁自评
      "screenshot": "modules/clock-calendar/screenshot.png",  // 相对仓根的截图路径(≥640×360)
      "description": "……",             // 中文一句话说明
      "description_en": "……"           // 英文一句话说明
    }
  ]
}
```

字段与各模块 `widget.json` 的 `display` 段一一对应(单一事实源在 widget.json,registry 是聚合视图);回流 PR 时**恰好追加一条**,`id == 目录名`,不改别人的条目(见 §3)。
