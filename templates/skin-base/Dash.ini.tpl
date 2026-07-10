; ============================================================
;  sansheng-deskdash 皮肤外壳模板(Dash.ini.tpl)
;  由 scripts/assemble.py 装配:占位符 {{...}} 全部替换后即为可部署 .ini。
;  · 仓内此模板与装配产物均为 UTF-8;部署副本转 UTF-16 LE+BOM 由 deploy 脚本负责。
;  · 数据一律走 @Include 变量(data.inc / todos.inc),皮肤段绝不内联中文字面量
;    (Rainmeter 读中文需 UTF-16,内联易 GBK 乱码 —— 见 references/encoding.md)。
;  占位符清单(供调度器 orchestrator.py / 部署脚本 deploy_skin.ps1 对接;下方用不带花括号的名字以免被自身替换):
;    H         总高度(装配算出,整数)                    → 见 [Variables] H=
;    SIZE_FONT 本次装配选中的档位字号(S/M/L → 数字)      → 见 [Variables] Size=
;    DATA_INC  data.inc 绝对路径(orchestrator 运行时生成,UTF-16) → 见 @Include
;    TODOS_INC todos.inc 绝对路径(交互模块运行时生成,UTF-16)    → 见 @Include2
;    BANDS     带区装配结果注入处(各模块 band.inc 已落位 + 段间分隔线)
; ============================================================

[Rainmeter]
Update=1000
AccurateText=1
DynamicWindowSize=1

[Metadata]
Name=Deskdash
Author=sansheng-deskdash
Information=由 sansheng-deskdash 装配生成的桌面看板皮肤
Version=0.1.0

; ============ 变量 ============
[Variables]
; —— 尺寸(W 可配;H 由装配按各带区高度累加算出)——
W=420
H={{H}}
PAD=16
; —— 三档字号(band.inc 作者按需选用;#Size# 为本次装配选中的档)——
SizeS=9
SizeM=11
SizeL=13
Size={{SIZE_FONT}}
; —— 通用配色(中性,无品牌专属;用户可自行改)——
Font=Microsoft YaHei UI
cStroke=255,255,255,20
cDivider=255,255,255,26
cText=228,235,243,255
cSub=150,160,175,255
cHead=140,150,165,255
cAccent=90,170,255,255
cCardBg=255,255,255,8
cCardLine=255,255,255,18
cBarTrack=255,255,255,16
; —— 看板标题(可配)——
BoardTitle=我的看板

; 运行时数据(orchestrator 生成,UTF-16);首次装配后文件可能尚不存在,Rainmeter 缺文件容错。
@Include={{DATA_INC}}
@Include2={{TODOS_INC}}

; ============ 背景面板 ============
[Panel]
Meter=Shape
Shape=Rectangle 0,0,#W#,#H#,13 | StrokeWidth 1 | StrokeColor #cStroke# | Fill LinearGradient PanelGrad
PanelGrad=90 | 18,22,30,235 ; 0.0 | 24,30,42,225 ; 1.0
DynamicVariables=1

; ============ 品牌行(标题可配)============
[BoardTitle]
Meter=String
X=#PAD#
Y=14
FontFace=#Font#
FontSize=#SizeM#
FontColor=#cText#
StringStyle=Bold
AntiAlias=1
DynamicVariables=1
Text=#BoardTitle#

; ============ 首条分隔线(品牌行下方基线)============
[BandDiv0]
Meter=Shape
Shape=Rectangle #PAD#,48,(#W#-2*#PAD#),1 | FillColor #cDivider#
DynamicVariables=1

; ============ 带区装配结果 ============
{{BANDS}}

; ============================================================
; 本文件由 scripts/assemble.py 生成,请勿手改。
; 改布局:改 modules.lock.json 里模块顺序后重跑 assemble;或用 scripts/shift_band.py 补偿平移。
; 改完务必跑 `python -m pytest tests/test_layout.py` 验证四布局不变量再部署。
; ============================================================
