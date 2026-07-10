; net-latency 带区(局部 Y,原点在带区顶;装配整体平移落位)。
; 段名带 Net 前缀;中文一律走 #变量#(data.inc/UTF-16),不在本文件内联。
; 右列 X=404(=模板 W420-PAD16);随行状态色 #NetT{n}Color#。

[NetCard]
Meter=Shape
Shape=Rectangle #PAD#,0,(#W#-2*#PAD#),150,8 | FillColor #cCardBg# | StrokeWidth 1 | StrokeColor #cCardLine#
DynamicVariables=1

[NetHd]
Meter=String
X=#PAD#
Y=6
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cHead#
StringStyle=Bold
AntiAlias=1
DynamicVariables=1
Text=#NetTitle#

[NetL1]
Meter=String
X=28
Y=30
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#NetT1Label#

[NetV1]
Meter=String
X=404
Y=30
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#NetT1Color#
AntiAlias=1
DynamicVariables=1
Text=#NetT1Text#

[NetL2]
Meter=String
X=28
Y=54
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#NetT2Label#

[NetV2]
Meter=String
X=404
Y=54
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#NetT2Color#
AntiAlias=1
DynamicVariables=1
Text=#NetT2Text#

[NetL3]
Meter=String
X=28
Y=78
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#NetT3Label#

[NetV3]
Meter=String
X=404
Y=78
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#NetT3Color#
AntiAlias=1
DynamicVariables=1
Text=#NetT3Text#

[NetL4]
Meter=String
X=28
Y=102
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#NetT4Label#

[NetV4]
Meter=String
X=404
Y=102
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#NetT4Color#
AntiAlias=1
DynamicVariables=1
Text=#NetT4Text#

[NetL5]
Meter=String
X=28
Y=126
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#NetT5Label#

[NetV5]
Meter=String
X=404
Y=126
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#NetT5Color#
AntiAlias=1
DynamicVariables=1
Text=#NetT5Text#

