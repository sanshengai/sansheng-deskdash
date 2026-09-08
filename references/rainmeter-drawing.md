# rainmeter-drawing · Shape 绘图:贝塞尔曲线 / InlineSetting / 锚点 / 激活刷新

Rainmeter 的 `Meter=Shape` 用 Direct2D 画矢量。本篇记与"画曲线/上色/定位"相关的坑与手法,以及**首次激活**和**刷新**两条命令的关键区别。

## 1. 曲线用 `CurveTo` 贝塞尔,别用密集 `LineTo`

- **现象**:想画一条平滑温度曲线,用许多段短 `LineTo` 逼近,真机上看到**折线棱角 + 半透明描边处的重影**(overlap 叠加),放大尤其难看。(2026-07-10 真机实证。)
- **根因**:`LineTo` 是直线段;短段拼曲线在拐点有硬角,而半透明 `StrokeColor` 在相邻段接头处**重复叠色**产生重影。
- **解法**:每段用一个 **`CurveTo`(三次贝塞尔)**,由 D2D 原生平滑渲染,一条连续 Path 无接头重影:
  ```
  Shape=Path MyPath | StrokeWidth 2 | StrokeColor 235,120,120,235 | StrokeLineJoin Round | FillColor 0,0,0,0
  MyPath=44.0,20.0 | CurveTo x2,y2,c1x,c1y,c2x,c2y | CurveTo ...
  ```
  Path 字符串 = **起点** `x,y` + 若干 `CurveTo 终点x,终点y,控制1x,控制1y,控制2x,控制2y`,用 ` | ` 连接。整条 Path 由采集器算好写进变量(`MyPath=#WxMaxPath#`),meter 只绑变量。

## 2. Catmull-Rom 锚点 → 贝塞尔控制点换算

采集器手里是一串数据锚点(每天温度对应的 `(x,y)`)。要让曲线**过每个锚点**且平滑,用 Catmull-Rom→三次贝塞尔的标准换算(每相邻两锚点 P1→P2 一段):

```
C1 = P1 + (P2 - P0) / 6      # 前控制点,借前一个锚点 P0 定切线
C2 = P2 - (P3 - P1) / 6      # 后控制点,借后一个锚点 P3 定切线
```

- 端点无 P0/P3 → 用端点自身复制补齐(`ext = [pts[0]] + pts + [pts[-1]]`),曲线端部自然收尾。
- 有效锚点 < 2 → 输出空串,band 里那条 Path 就不画(避免单点 Path 报错)。
- 实现见 `scripts/lib/inc_writer.py::temp_curve`,以及 weather 采集器**内联的同款拷贝** `_temp_curve`(模块自包含要能拷走独立跑;两处由 `test_official_modules.py` 的 drift-guard 断言等价)。

## 3. `InlineSetting` 局部上色 / 分段样式

- `Meter=String` 可用 `InlineSetting` + `InlinePattern` 给**匹配到的子串**单独上色/加粗,而不切成多个 meter:
  ```
  InlineSetting=Color,235,120,120,255
  InlinePattern=\d+°           ; 只给温度数字染红
  InlineSetting2=Weight,700
  InlinePattern2=今天
  ```
- 适合"一行里高亮一个词"的场景;比拆成两个 String meter 再手工对齐省事、且不受字宽变化影响。

## 4. Ellipse 锚点(圆的坐标是圆心,不是左上角)

- `Shape=Ellipse cx,cy,rx[,ry]`:`cx,cy` 是**圆心**,`rx/ry` 是半径。与 `Rectangle x,y,w,h` 的**左上角**语义不同——画状态圆点时别把圆心当左上角,否则整体偏移半径。
- 平移工具 `shift_band.shift()` 对 Ellipse 认第 2 个参数(`cy`)为 y;Rectangle 认第 2 个(`y`);Line 认第 2、4 个(两端 y)。新增自定义 shape 时留意平移器只识别这三种(见 `layout.md`)。

## 5. `!ActivateConfig` vs `!RefreshApp`(最容易踩)

| 命令 | 作用 | 何时用 |
|---|---|---|
| `!ActivateConfig "Skin" "Skin.ini"` | **首次把皮肤加载到桌面**(注册 + 显示) | 新皮肤**第一次上墙**必须先跑;否则文件已部署但桌面看不到 |
| `!RefreshApp` | 重扫注册所有 config + 重载已激活皮肤(读新文件重绘);**但不显示未激活的皮肤** | 皮肤**已激活过**,之后每次改动重部署只需这个 |
| `!Refresh "Skin"` | 只重载指定皮肤 | 交互后定向刷新单个皮肤(todo 用),比 `!RefreshApp` 轻 |

- **典型 bug**:deploy 脚本只写文件 + `!RefreshApp`,新皮肤第一次却"文件在、桌面没有"——`!RefreshApp` 会**重扫并注册**新 config(它在 Rainmeter 配置树里认得),但**不会显示未激活的皮肤**;要让皮肤真正上墙,得靠 `!ActivateConfig`。**故新皮肤第一次必须显式 `!ActivateConfig`**(SKILL.md 初装流程已固化此步)。
- Rainmeter.exe 路径从 `doctor.py` 输出的 `checks.rainmeter.path` 取(独立字段,别去解析中文 `detail`)。

## 6. 其它常用规则

- meter 引用变量、或 Path 内含 `#...#` 时,该 meter 必须 `DynamicVariables=1`,否则变量不更新(显示首帧或空)。
- 透明 = alpha 通道 `r,g,b,0`;空槽位常用 `0,0,0,0` 让 meter 存在但不可见(采集器给空数据时统一发透明色,布局不塌)。
- `AntiAlias=1` 给文字/曲线抗锯齿;`AccurateText=1`(模板 `[Rainmeter]` 段已开)让 String 宽度测量精确,避免右对齐飘移。

## 7. 三个"默认值"坑(不看文档发现不了,上墙才现形)

### 7.1 `Shape` 的默认描边是 **1px 纯黑**

画一条 1px 高的分隔线:

```
Shape=Rectangle 0,0,300,1 | FillColor 255,255,255,26
```

写的是 10% 白,屏幕上出来的是**一条 3px 高、正中间 #000000 的黑带**——`StrokeWidth` 不写默认为 1,`StrokeColor` 默认黑,描边裹在 1px 的填充外面。整屏几十条这样的线,观感就是"刺眼、把页面割得特别碎"。

🔴 **每条线形 Shape 都必须显式写 `| StrokeWidth 0`。** 判据不是肉眼("看着是深色的"骗不了人也骗得了人),是**取像素**:截图后读线心的 RGB,是不是 `#000000`。

### 7.2 字形的墨迹 ≠ 字号

`‹` `›` `«` `»` 这类**标点字形**在中文字体里画得很小:实测 Microsoft YaHei UI 里,`‹` 的墨迹在 `FontSize=8` 时只有 4×4px、`18` 时 7×9px、`28` 时才 10×13px——**大约只有字号的三分之一**。所以"把翻页箭头调大一点"要的字号,可能比正文大一倍还多,写出来像笔误,得在注释里说明原因。

想换个更粗的字形也未必行:`◀` `❮` `⟨` `˂` `▸` 这些在雅黑里**根本没有字形**,会掉进系统兜底字体,画出来的形状和这一屏的其它字不搭。换字形前先验一下当前字体里有没有:

```python
from PIL import Image, ImageDraw, ImageFont
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 24)
im = Image.new("L", (90, 70), 0); ImageDraw.Draw(im).text((25, 12), "\u276e", font=f, fill=255)
print(im.getbbox())     # 一批候选都返回同一个尺寸 = 都是缺字的兜底方框
```

雅黑里确实存在、又比标点大的替代:`〈` `〉`(U+3008/3009,墨迹 8×23,细高)。

### 7.3 Rainmeter 量不到文字实宽——变宽文本要用 `CenterCenter` 隔离

`Meter=String` 渲染多宽,装配期算不出来(`AccurateText=1` 只让 Rainmeter 自己量准,不把结果给你)。所以**一段宽度会变的文本旁边不能靠"估宽"摆固定元素**。

典型翻车:月份标题 `LeftCenter` 定在 X,右边按估算摆一个箭头。`2026年9月` 和 `2026年11月` 差一个字宽,两位数月份时标题就把箭头**整个盖住**——屏幕上看起来"那个按钮没了",查半天以为是漏画。

解法是让宽度变化**对称地被吃掉**:文本用 `StringAlign=CenterCenter` 钉在中心,左右两侧的元素按"最宽的一种"留出净空,位置就与文本长短无关了。最宽值别估,**取像素量一次**:截图后扫标题那条带里属于文字颜色的像素范围。

同理,一段变宽文本后面**不要**再跟固定 X 的第二段文本——把后面那段也改成从一个固定锚点起排,或者干脆换行。
