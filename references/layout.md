# layout · 带区模型 / 四不变量 / 平移语义 / 高度预算

看板是多个模块的 `band.inc` **自上而下堆叠**拼成的一张皮肤。本篇讲装配的坐标约定、四条布局不变量、平移工具的语义边界,以及 Path/高度这两个测试盲区的补救。

> ## 🔒 社区模块写法铁律(先看这条)
> **自包含内联优先于 DRY**:一个模块要能把整个目录**拷走独立跑**——所以 collector **不 import 仓内 `scripts/lib`**,orchestrator 也**不给它注 `PYTHONPATH`**。需要的小工具(温度曲线、`_san`、`_emit`)**内联复制**进模块。代价是"两处代码可能漂移",对策是:**凡内联了非平凡算法(如 Catmull-Rom 曲线),必须加一条 drift-guard 测试**断言内联版与 `lib` 版等价(见 `tests/test_official_modules.py::test_weather_temp_curve_matches_lib`)。平凡工具(`_san`/`_emit`)约定同语义即可,不强制测。

## 1. 带区模型(band model)

- 每个模块交一个 `band.inc`,用**局部坐标**:原点在**该带区顶** `y=0`,内部所有定位都相对带区顶算。
- `assemble.py` 按 `modules.lock.json` 顺序:首带区顶 = 品牌行下基线(size 档决定,如 M 档 `first_y=60`);第 i 带区顶 = 上带区顶 + 上带区 `height` + 段间距;每段调 `shift_band.shift(band_lines, 0, 顶Y)` **整体平移到位**;相邻带区间插一条分隔线;总高 `H = 末带区底 + 底部留白`。
- **装配器不缩放内容**,只平移。带区自身多高由模块 `widget.json` 的 `band.height` 声明。

## 2. 四布局不变量(`tests/test_layout.py`,对装配产物跑)

平移类改动最容易悄悄错位,四条不变量兜底:

1. **有 `Y=` 定位的 meter**:内部 `Shape` 必须**原点锚定**(`y ≤ 8`)。定位交给 `Y=` 选项,Shape 只画相对形状。违反 = 典型"双重平移"(见 §4)。
2. **无定位 meter**(默认 `0,0`):`Shape` 携带**绝对局部 y**(装配后落到 ≥ 40 的真实位置);背景面板 `[Panel]` 是白名单例外。
3. **分隔线**(段名含 `Div`):沿文件顺序各自首个 shape y **严格递增且不重合**。
4. **内容不超面板高** `H`:最深的定位 y + 14 ≤ `H`。

改完布局(改 lock 顺序 / 跑 shift_band)**必跑** `python -m pytest tests/test_layout.py` 再部署。

## 3. 平移语义:只动数字字面量 `Y=`

`shift_band.shift(lines, from_y, dy)` 把所有绝对 `y ≥ from_y` 的定位加 `dy`,但它**只认**:

- **`Y=<数字>`**(定位 meter 的 Y 选项);
- 无定位 meter 里 **`Rectangle`/`Ellipse`/`Line`** 的数字 y 参数。

它**不动**:`Y=#变量#` / `Y=(公式)` 动态定位,以及 **`Path` / 自定义 shape** 的坐标。

> **铁律:曲线 / Path meter 的 `Y=` 必须是数字字面量。** 写成 `Y=#变量#` 会被 `shift()` 漏移,装配后跑到错误位置。weather 的曲线 meter 定位 `Y=90` 就是硬编码数字(不敢用变量);todo 输入框也因此从源仓的动态 `Y=#TodoInputY#` 改成固定 `Y=2`(见 `interaction.md`)。

## 4. 曾发生的双重平移 bug(不变量 1 的由来)

- **现象**:一次布局调整后,某些卡片底板 + 色点整体下移了两倍距离。
- **根因**:一次性正则平移脚本把**有 `Y=` 定位的 meter** 内部的相对 Shape **也 `+dy`** 了——定位 meter 已经靠 `Y=` 落位,内部 Shape 再被移一次 = 双重下移。
- **解法**:① 纵向平移一律走 `shift_band.shift()`(它对定位 meter 只动 `Y=`,不碰内部 Shape),**不再手写正则**;② 不变量 1 把"定位 meter 的内部 Shape 必须原点锚定"锁成测试,双重平移会立即红灯。

## 5. Path 不被四不变量校验 → 需模块级交叉校验

- 四不变量的取坐标只认 `Rectangle/Ellipse/Line`,**不解析 `Path`**。所以一条曲线 Path 即使**画到带区外**(越底、盖住下一个模块)四不变量也测不出来。
- **补救**:模块自己加一条交叉校验测试——`曲线 meter 的定位 Y= + 该 Path 生成的最大相对 y ≤ band.height`。范本见 `test_official_modules.py::test_weather_curve_path_fits_band`(跑真实生成路径,取 Path 里所有 y 的 max,断言不越带底)。**任何用 Path 画东西的新模块都应照做**。

## 6. band 作者须诚实声明 height

- `band.height` 是装配堆叠与高度预算的**唯一依据**,但四不变量的"内容不超 H"是对**整板总高**校验的。**一个中间带区如果内容超出自己声明的 height,但因为后面还有别的带区、它的落点仍 < 总 H,重叠不会被任何测试抓到**——只会在真机上和下一个模块糊在一起。
- 所以:**声明的 height 必须真的容得下你的内容**(最深元素相对 y + 文字/图形高)。宁可略微高估留白,不可低报。§5 的 Path 交叉校验就是帮你验证"曲线没超过你声明的 height"。

## 7. 高度预算(height_budget)

- `doctor.py` 读屏幕逻辑工作区高,减上下边距(各 `24px`,`TOP_MARGIN/BOTTOM_MARGIN`,偏保守可按需调)得 `height_budget`,喂 `assemble --budget`。
- 装配后总高超预算 → `assemble.py` 抛结构化错误,**列出各模块高度 + 建议裁掉最高的模块 / 换 S 档**(压缩间距与留白)。agent 拿这个和用户商量,**别手改成品 `.ini` 的 Y**(改布局的正道见 SKILL §3)。
- S/M/L 档只调**字号 + 段间距 + 留白**,不缩带区内容;真正的紧凑内容变体留 P1。
