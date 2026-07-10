; github 带区(局部 Y,原点在带区顶;装配整体平移落位)。
; 段名带 Gh 前缀;中文(相对时间/汇总)与仓名一律走 #变量#(data.inc/UTF-16,GBK 桥),不在本文件内联。
; 每行:语言色点 + 仓名(单击开 #GhRepoNUrl#)+ 右侧 ★star · 最近更新。表头右侧总 star / 开放 PR。

[GhCard]
Meter=Shape
Shape=Rectangle #PAD#,0,(#W#-2*#PAD#),150,8 | FillColor #cCardBg# | StrokeWidth 1 | StrokeColor #cCardLine#
DynamicVariables=1

[GhHd]
Meter=String
X=#PAD#
Y=6
FontFace=#Font#
FontSize=#SizeM#
FontColor=#cHead#
StringStyle=Bold
AntiAlias=1
DynamicVariables=1
Text=#GhTitle#

[GhSummary]
Meter=String
X=404
Y=8
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#GhSummaryText#

; —— 仓库 5 行(行 Y = 34 + (i-1)*24)——
[GhDot1]
Meter=Shape
X=#PAD#
Y=34
Shape=Ellipse 4,6,4 | FillColor #GhRepo1DotColor#
DynamicVariables=1
[GhName1]
Meter=String
X=30
Y=34
W=222
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo1Name#
LeftMouseUpAction=["#GhRepo1Url#"]
[GhMeta1]
Meter=String
X=404
Y=34
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo1MetaText#

[GhDot2]
Meter=Shape
X=#PAD#
Y=58
Shape=Ellipse 4,6,4 | FillColor #GhRepo2DotColor#
DynamicVariables=1
[GhName2]
Meter=String
X=30
Y=58
W=222
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo2Name#
LeftMouseUpAction=["#GhRepo2Url#"]
[GhMeta2]
Meter=String
X=404
Y=58
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo2MetaText#

[GhDot3]
Meter=Shape
X=#PAD#
Y=82
Shape=Ellipse 4,6,4 | FillColor #GhRepo3DotColor#
DynamicVariables=1
[GhName3]
Meter=String
X=30
Y=82
W=222
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo3Name#
LeftMouseUpAction=["#GhRepo3Url#"]
[GhMeta3]
Meter=String
X=404
Y=82
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo3MetaText#

[GhDot4]
Meter=Shape
X=#PAD#
Y=106
Shape=Ellipse 4,6,4 | FillColor #GhRepo4DotColor#
DynamicVariables=1
[GhName4]
Meter=String
X=30
Y=106
W=222
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo4Name#
LeftMouseUpAction=["#GhRepo4Url#"]
[GhMeta4]
Meter=String
X=404
Y=106
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo4MetaText#

[GhDot5]
Meter=Shape
X=#PAD#
Y=130
Shape=Ellipse 4,6,4 | FillColor #GhRepo5DotColor#
DynamicVariables=1
[GhName5]
Meter=String
X=30
Y=130
W=222
ClipString=1
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cText#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo5Name#
LeftMouseUpAction=["#GhRepo5Url#"]
[GhMeta5]
Meter=String
X=404
Y=130
StringAlign=Right
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#GhRepo5MetaText#
