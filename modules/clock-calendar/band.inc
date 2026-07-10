; clock-calendar 带区(局部 Y,原点在带区顶;装配时整体平移落位)。
; 段名带 Clk 前缀避免跨模块冲突;中文一律走 #变量#(data.inc,UTF-16 GBK 桥),不在本文件内联。
; 活的 HH:MM 由原生 [ClkMeasureTime](Measure=Time)每秒刷;日期/日历由采集器出变量。

; —— 原生时间测量:皮肤 Update=1000 每秒刷,无需采集器参与 ——
[ClkMeasureTime]
Measure=Time
Format=%H:%M

; —— 大号时钟(绑定测量,活的)——
[ClkTime]
Meter=String
MeasureName=ClkMeasureTime
X=#PAD#
Y=2
FontFace=#Font#
FontSize=#SizeL#
FontColor=#cText#
StringStyle=Bold
AntiAlias=1
Text=%1

; —— 日期 + 星期(采集器每轮出;每天变一次)——
[ClkDate]
Meter=String
X=#PAD#
Y=44
FontFace=#Font#
FontSize=#SizeS#
FontColor=#cSub#
AntiAlias=1
DynamicVariables=1
Text=#ClkDateText#

; —— 当月日历 PNG(采集器渲染,绝对路径经 #ClkCalPng# 传入;空则不显示)——
[ClkCal]
Meter=Image
X=#PAD#
Y=72
W=336
H=248
ImageName=#ClkCalPng#
AntiAlias=1
DynamicVariables=1
