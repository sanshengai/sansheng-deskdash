; __ID__ 带区骨架(局部 Y,原点在带区顶;装配整体平移落位)。
; 段名带 __PREFIX__ 前缀,跨模块唯一;中文/数据一律走 #变量#(data.inc/UTF-16),不在本文件内联。
; TODO: 按你的 output 键补 meter;widget.json 的 band.height 要真的容得下你画的内容(见 references/layout.md)。
; 约束速记:有 Y= 的 meter 内部 Shape 原点锚定(y≤8);曲线/Path meter 的 Y= 必须数字字面量;
;           禁用保留段名 [Rainmeter]/[Metadata]/[Variables]/[Panel]/[BoardTitle]/[BandDiv<n>]。

[__PREFIX__Card]
Meter=Shape
Shape=Rectangle #PAD#,0,(#W#-2*#PAD#),60,8 | FillColor #cCardBg# | StrokeWidth 1 | StrokeColor #cCardLine#
DynamicVariables=1

[__PREFIX__Title]
Meter=String
X=#PAD#
Y=8
FontFace=#Font#
FontSize=#SizeM#
FontColor=#cText#
StringStyle=Bold
AntiAlias=1
DynamicVariables=1
Text=#__PREFIX__Title#

[__PREFIX__Status]
Meter=String
X=#PAD#
Y=32
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#__PREFIX__Status#
