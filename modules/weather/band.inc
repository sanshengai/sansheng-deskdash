; weather 带区(局部 Y,原点在带区顶;装配整体平移落位)。
; 段名带 Wx 前缀;中文/温度文本一律走 #变量#(data.inc/UTF-16),不在本文件内联。
; 7 列 x 中心走变量 #WxCol1X#..#WxCol7X#(collector.py 的 COLS_X 单一真源,band 不硬编码列 x)。
; 曲线为 CurveTo 贝塞尔(采集器 temp_curve 生成,相对曲线 meter 原点);曲线 meter 定位 Y=90 由装配平移器处理。
; ⚠ 改列几何只改 collector.py 的 COLS_X;drift-guard 测试断言 band 列 X 引用 == 采集器 Col*X 输出。

[WxCard]
Meter=Shape
Shape=Rectangle #PAD#,0,(#W#-2*#PAD#),150,8 | FillColor #cCardBg# | StrokeWidth 1 | StrokeColor #cCardLine#
DynamicVariables=1

[WxNowTemp]
Meter=String
X=#PAD#
Y=2
FontFace=#Font#
FontSize=#SizeL#
FontColor=#cText#
StringStyle=Bold
AntiAlias=1
DynamicVariables=1
Text=#WxNowTempText#

[WxNowDesc]
Meter=String
X=84
Y=6
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#WxNowDesc#

[WxNowSummary]
Meter=String
X=84
Y=26
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#WxNowSummary#

[WxD1Label]
Meter=String
X=#WxCol1X#
Y=54
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#WxD1Label#

[WxD2Label]
Meter=String
X=#WxCol2X#
Y=54
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#WxD2Label#

[WxD3Label]
Meter=String
X=#WxCol3X#
Y=54
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#WxD3Label#

[WxD4Label]
Meter=String
X=#WxCol4X#
Y=54
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#WxD4Label#

[WxD5Label]
Meter=String
X=#WxCol5X#
Y=54
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#WxD5Label#

[WxD6Label]
Meter=String
X=#WxCol6X#
Y=54
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#WxD6Label#

[WxD7Label]
Meter=String
X=#WxCol7X#
Y=54
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#WxD7Label#

[WxD1Tmax]
Meter=String
X=#WxCol1X#
Y=72
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=235,120,120,255
AntiAlias=1
DynamicVariables=1
Text=#WxD1TmaxText#

[WxD2Tmax]
Meter=String
X=#WxCol2X#
Y=72
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=235,120,120,255
AntiAlias=1
DynamicVariables=1
Text=#WxD2TmaxText#

[WxD3Tmax]
Meter=String
X=#WxCol3X#
Y=72
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=235,120,120,255
AntiAlias=1
DynamicVariables=1
Text=#WxD3TmaxText#

[WxD4Tmax]
Meter=String
X=#WxCol4X#
Y=72
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=235,120,120,255
AntiAlias=1
DynamicVariables=1
Text=#WxD4TmaxText#

[WxD5Tmax]
Meter=String
X=#WxCol5X#
Y=72
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=235,120,120,255
AntiAlias=1
DynamicVariables=1
Text=#WxD5TmaxText#

[WxD6Tmax]
Meter=String
X=#WxCol6X#
Y=72
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=235,120,120,255
AntiAlias=1
DynamicVariables=1
Text=#WxD6TmaxText#

[WxD7Tmax]
Meter=String
X=#WxCol7X#
Y=72
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=235,120,120,255
AntiAlias=1
DynamicVariables=1
Text=#WxD7TmaxText#

[WxMaxCurve]
Meter=Shape
X=0
Y=90
Shape=Path MaxP | StrokeWidth 2 | StrokeColor 235,120,120,235 | StrokeLineJoin Round | StrokeStartCap Round | StrokeEndCap Round | FillColor 0,0,0,0
MaxP=#WxMaxPath#
DynamicVariables=1

[WxMinCurve]
Meter=Shape
X=0
Y=90
Shape=Path MinP | StrokeWidth 2 | StrokeColor 90,160,235,235 | StrokeLineJoin Round | StrokeStartCap Round | StrokeEndCap Round | FillColor 0,0,0,0
MinP=#WxMinPath#
DynamicVariables=1

[WxD1Tmin]
Meter=String
X=#WxCol1X#
Y=126
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=90,160,235,255
AntiAlias=1
DynamicVariables=1
Text=#WxD1TminText#

[WxD2Tmin]
Meter=String
X=#WxCol2X#
Y=126
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=90,160,235,255
AntiAlias=1
DynamicVariables=1
Text=#WxD2TminText#

[WxD3Tmin]
Meter=String
X=#WxCol3X#
Y=126
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=90,160,235,255
AntiAlias=1
DynamicVariables=1
Text=#WxD3TminText#

[WxD4Tmin]
Meter=String
X=#WxCol4X#
Y=126
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=90,160,235,255
AntiAlias=1
DynamicVariables=1
Text=#WxD4TminText#

[WxD5Tmin]
Meter=String
X=#WxCol5X#
Y=126
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=90,160,235,255
AntiAlias=1
DynamicVariables=1
Text=#WxD5TminText#

[WxD6Tmin]
Meter=String
X=#WxCol6X#
Y=126
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=90,160,235,255
AntiAlias=1
DynamicVariables=1
Text=#WxD6TminText#

[WxD7Tmin]
Meter=String
X=#WxCol7X#
Y=126
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=90,160,235,255
AntiAlias=1
DynamicVariables=1
Text=#WxD7TminText#

