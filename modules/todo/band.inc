; todo 带区(局部 Y,原点在带区顶;装配整体平移落位)。交互旗舰:勾选/单击切换/双击编辑/删除/行内新增。
; 段名带 Td 前缀;中文/图标一律走 #变量#(data.inc·todos.inc/UTF-16,GBK 桥),不在本文件内联。
;
; 交互接线(band Action 调同目录 todo_action.py;#TdPyw#/#TdScript#/#TdConfig# 由 collector 出):
;   · 勾选框     → toggle N   立即切完成态
;   · 文字单击   → click  N   双击防抖:确属单击才 toggle(双击窗内计数≥2 判双击,不误切)
;   · 文字双击   → 就地开输入框 [TdInput](预填原文改错字),提交走 input N(settext)
;   · ＋ 添加    → 开 [TdInput](空)提交走 input 0(新增到末尾)
;   · 删除 ✕     → del N
; ⚠ 输入框 [TdInput] 用固定数字字面量 Y=2(装配平移器只移数字字面量 Y=,#变量# 形式的 Y 不会被平移到
;   绝对坐标)。故不用源仓的动态"行内 Y=#TodoInputY#",改为单输入框在表头就地弹出、由 #TdEditRow# 判增/改
;   (行为等价、装配正确;详见 README「为什么输入框不跟随行号」)。

[TdCard]
Meter=Shape
Shape=Rectangle #PAD#,0,(#W#-2*#PAD#),172,8 | FillColor #cCardBg# | StrokeWidth 1 | StrokeColor #cCardLine#
DynamicVariables=1

[TdHd]
Meter=String
X=#PAD#
Y=6
FontFace=#Font#
FontSize=#SizeM#
FontColor=#cHead#
StringStyle=Bold
AntiAlias=1
DynamicVariables=1
Text=#TdTitle#

[TdAdd]
Meter=String
X=404
Y=6
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=104,224,158,255
AntiAlias=1
DynamicVariables=1
Text=#TdAddLabel#
LeftMouseUpAction=[!SetVariable TdEditRow "0"][!SetOption TdInput DefaultValue ""][!CommandMeasure TdInput "ExecuteBatch 1"]

; 行内输入框:＋添加(EditRow=0=新增)/ 双击某行(EditRow=N=改写)共用;仅 Enter 提交,点框外/Esc=取消。
[TdInput]
Measure=Plugin
Plugin=InputText
X=40
Y=2
W=336
H=19
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
SolidColor=24,31,43,255
FocusDismiss=1
DefaultValue=
Command1=["#TdPyw#" "#TdScript#" input "#TdEditRow#" "$UserInput$" "#TdConfig#"]
DismissAction=[!Refresh]
DynamicVariables=1

; —— 待办 6 行(行 Y = 32 + (i-1)*24)——
[TdBox1]
Meter=Shape
X=#PAD#
Y=32
Shape=Rectangle 0,0,14,14,4 | StrokeWidth 1.5 | StrokeColor #TdRow1Check# | FillColor 0,0,0,1
DynamicVariables=1
LeftMouseUpAction=["#TdPyw#" "#TdScript#" toggle 1 "#TdConfig#"]
[TdMark1]
Meter=String
X=23
Y=32
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cAccent#
AntiAlias=1
DynamicVariables=1
Text=#TdRow1Mark#
[TdTxt1]
Meter=String
X=40
Y=32
W=336
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#TdRow1Color#
AntiAlias=1
DynamicVariables=1
Text=#TdRow1Text#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" click 1 "#TdConfig#"]
LeftMouseDoubleClickAction=[!SetVariable TdEditRow "1"][!SetOption TdInput DefaultValue "#TdRow1Text#"][!CommandMeasure TdInput "ExecuteBatch 1"]
[TdDel1]
Meter=String
X=404
Y=32
StringAlign=Right
FontFace=#Font#
FontSize=#SizeM#
FontColor=#TdRow1DelColor#
AntiAlias=1
DynamicVariables=1
Text=#TdDelIcon#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" del 1 "#TdConfig#"]

[TdBox2]
Meter=Shape
X=#PAD#
Y=56
Shape=Rectangle 0,0,14,14,4 | StrokeWidth 1.5 | StrokeColor #TdRow2Check# | FillColor 0,0,0,1
DynamicVariables=1
LeftMouseUpAction=["#TdPyw#" "#TdScript#" toggle 2 "#TdConfig#"]
[TdMark2]
Meter=String
X=23
Y=56
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cAccent#
AntiAlias=1
DynamicVariables=1
Text=#TdRow2Mark#
[TdTxt2]
Meter=String
X=40
Y=56
W=336
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#TdRow2Color#
AntiAlias=1
DynamicVariables=1
Text=#TdRow2Text#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" click 2 "#TdConfig#"]
LeftMouseDoubleClickAction=[!SetVariable TdEditRow "2"][!SetOption TdInput DefaultValue "#TdRow2Text#"][!CommandMeasure TdInput "ExecuteBatch 1"]
[TdDel2]
Meter=String
X=404
Y=56
StringAlign=Right
FontFace=#Font#
FontSize=#SizeM#
FontColor=#TdRow2DelColor#
AntiAlias=1
DynamicVariables=1
Text=#TdDelIcon#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" del 2 "#TdConfig#"]

[TdBox3]
Meter=Shape
X=#PAD#
Y=80
Shape=Rectangle 0,0,14,14,4 | StrokeWidth 1.5 | StrokeColor #TdRow3Check# | FillColor 0,0,0,1
DynamicVariables=1
LeftMouseUpAction=["#TdPyw#" "#TdScript#" toggle 3 "#TdConfig#"]
[TdMark3]
Meter=String
X=23
Y=80
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cAccent#
AntiAlias=1
DynamicVariables=1
Text=#TdRow3Mark#
[TdTxt3]
Meter=String
X=40
Y=80
W=336
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#TdRow3Color#
AntiAlias=1
DynamicVariables=1
Text=#TdRow3Text#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" click 3 "#TdConfig#"]
LeftMouseDoubleClickAction=[!SetVariable TdEditRow "3"][!SetOption TdInput DefaultValue "#TdRow3Text#"][!CommandMeasure TdInput "ExecuteBatch 1"]
[TdDel3]
Meter=String
X=404
Y=80
StringAlign=Right
FontFace=#Font#
FontSize=#SizeM#
FontColor=#TdRow3DelColor#
AntiAlias=1
DynamicVariables=1
Text=#TdDelIcon#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" del 3 "#TdConfig#"]

[TdBox4]
Meter=Shape
X=#PAD#
Y=104
Shape=Rectangle 0,0,14,14,4 | StrokeWidth 1.5 | StrokeColor #TdRow4Check# | FillColor 0,0,0,1
DynamicVariables=1
LeftMouseUpAction=["#TdPyw#" "#TdScript#" toggle 4 "#TdConfig#"]
[TdMark4]
Meter=String
X=23
Y=104
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cAccent#
AntiAlias=1
DynamicVariables=1
Text=#TdRow4Mark#
[TdTxt4]
Meter=String
X=40
Y=104
W=336
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#TdRow4Color#
AntiAlias=1
DynamicVariables=1
Text=#TdRow4Text#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" click 4 "#TdConfig#"]
LeftMouseDoubleClickAction=[!SetVariable TdEditRow "4"][!SetOption TdInput DefaultValue "#TdRow4Text#"][!CommandMeasure TdInput "ExecuteBatch 1"]
[TdDel4]
Meter=String
X=404
Y=104
StringAlign=Right
FontFace=#Font#
FontSize=#SizeM#
FontColor=#TdRow4DelColor#
AntiAlias=1
DynamicVariables=1
Text=#TdDelIcon#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" del 4 "#TdConfig#"]

[TdBox5]
Meter=Shape
X=#PAD#
Y=128
Shape=Rectangle 0,0,14,14,4 | StrokeWidth 1.5 | StrokeColor #TdRow5Check# | FillColor 0,0,0,1
DynamicVariables=1
LeftMouseUpAction=["#TdPyw#" "#TdScript#" toggle 5 "#TdConfig#"]
[TdMark5]
Meter=String
X=23
Y=128
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cAccent#
AntiAlias=1
DynamicVariables=1
Text=#TdRow5Mark#
[TdTxt5]
Meter=String
X=40
Y=128
W=336
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#TdRow5Color#
AntiAlias=1
DynamicVariables=1
Text=#TdRow5Text#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" click 5 "#TdConfig#"]
LeftMouseDoubleClickAction=[!SetVariable TdEditRow "5"][!SetOption TdInput DefaultValue "#TdRow5Text#"][!CommandMeasure TdInput "ExecuteBatch 1"]
[TdDel5]
Meter=String
X=404
Y=128
StringAlign=Right
FontFace=#Font#
FontSize=#SizeM#
FontColor=#TdRow5DelColor#
AntiAlias=1
DynamicVariables=1
Text=#TdDelIcon#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" del 5 "#TdConfig#"]

[TdBox6]
Meter=Shape
X=#PAD#
Y=152
Shape=Rectangle 0,0,14,14,4 | StrokeWidth 1.5 | StrokeColor #TdRow6Check# | FillColor 0,0,0,1
DynamicVariables=1
LeftMouseUpAction=["#TdPyw#" "#TdScript#" toggle 6 "#TdConfig#"]
[TdMark6]
Meter=String
X=23
Y=152
StringAlign=Center
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cAccent#
AntiAlias=1
DynamicVariables=1
Text=#TdRow6Mark#
[TdTxt6]
Meter=String
X=40
Y=152
W=336
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#TdRow6Color#
AntiAlias=1
DynamicVariables=1
Text=#TdRow6Text#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" click 6 "#TdConfig#"]
LeftMouseDoubleClickAction=[!SetVariable TdEditRow "6"][!SetOption TdInput DefaultValue "#TdRow6Text#"][!CommandMeasure TdInput "ExecuteBatch 1"]
[TdDel6]
Meter=String
X=404
Y=152
StringAlign=Right
FontFace=#Font#
FontSize=#SizeM#
FontColor=#TdRow6DelColor#
AntiAlias=1
DynamicVariables=1
Text=#TdDelIcon#
LeftMouseUpAction=["#TdPyw#" "#TdScript#" del 6 "#TdConfig#"]
