; demo-a 带区(局部 Y,原点在带区顶;装配时整体平移落位)。
; 定位 meter(带 Y=)内部 Shape 原点锚定;无定位 meter 的 Shape 携带绝对(局部)y。
[DemoTime]
Meter=String
X=#PAD#
Y=6
FontFace=#Font#
FontSize=#SizeL#
FontColor=#cText#
StringStyle=Bold
AntiAlias=1
DynamicVariables=1
Text=#DemoTime#
[DemoDate]
Meter=String
X=#PAD#
Y=40
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#DemoDate#
[DemoBar]
Meter=Shape
Y=70
Shape=Rectangle 0,0,120,6,3 | FillColor #cAccent#
DynamicVariables=1
