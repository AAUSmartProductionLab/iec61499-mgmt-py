' export_slides.vbs <deck.pptx> <out-dir> [width] [height]: every slide as sNN.png, rendered by PowerPoint
Dim args, app, pres, i, w, h, name
Set args = WScript.Arguments
w = 1600 : h = 900
If args.Count > 2 Then w = CInt(args(2))
If args.Count > 3 Then h = CInt(args(3))
Set app = CreateObject("PowerPoint.Application")
Set pres = app.Presentations.Open(args(0), True, False, False)
WScript.Echo pres.Slides.Count & " slides, " & pres.PageSetup.SlideWidth & " x " & pres.PageSetup.SlideHeight
For i = 1 To pres.Slides.Count
  name = args(1) & "\s" & Right("0" & i, 2) & ".png"
  pres.Slides(i).Export name, "PNG", w, h
Next
pres.Close
app.Quit
