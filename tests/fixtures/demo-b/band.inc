; demo-b 带区(局部 Y,原点在带区顶)。
; [InfoCard] 是无定位 meter,Shape 携带绝对(局部)y —— 装配平移会移动其 y 参数。
[InfoCard]
Meter=Shape
Shape=Rectangle #PAD#,4,388,90,8 | FillColor #cCardBg# | StrokeWidth 1 | StrokeColor #cCardLine#
DynamicVariables=1
[InfoTitle]
Meter=String
X=28
Y=14
FontFace=#Font#
FontSize=#SizeM#
FontColor=#cText#
StringStyle=Bold
AntiAlias=1
DynamicVariables=1
Text=#InfoTitle#
[InfoValue]
Meter=String
X=28
Y=44
FontFace=#Font#
FontSize=#SizeL#
FontColor=#cAccent#
AntiAlias=1
DynamicVariables=1
Text=#InfoValue#
