' video_slide.vbs <deck.pptx> <slide-number> <out.mp4>: one slide as a video, its clicks played in turn
Dim args, app, pres, i, keep, t
Set args = WScript.Arguments
keep = CInt(args(1))
Set app = CreateObject("PowerPoint.Application")
Set pres = app.Presentations.Open(args(0), False, False, False)
For i = pres.Slides.Count To 1 Step -1
  If i <> keep Then pres.Slides(i).Delete
Next
pres.Slides(1).SlideShowTransition.AdvanceOnTime = True
pres.Slides(1).SlideShowTransition.AdvanceTime = 3
' CreateVideo(FileName, UseTimingsAndNarrations, DefaultSlideDuration, VertResolution, FramesPerSecond, Quality)
pres.CreateVideo args(2), False, 2, 540, 10, 60
t = 0
Do While pres.CreateVideoStatus = 1 Or pres.CreateVideoStatus = 2
  WScript.Sleep 1000
  t = t + 1
  If t > 600 Then Exit Do
Loop
WScript.Echo "status " & pres.CreateVideoStatus & " after " & t & " s"
pres.Close
app.Quit
