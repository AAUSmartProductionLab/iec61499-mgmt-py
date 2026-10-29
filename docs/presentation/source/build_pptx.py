"""Adds the layered, animated figures to the user's deck: new slides in its own style (title, section label,
click timeline with captions), each figure a stack of layer pictures with PowerPoint animations.

    build_pptx.py <repo> <out.pptx>
"""
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
SRC = REPO / "docs/presentation/modular-production.pptx"
FIGS = REPO / "docs/presentation/figures/deck"
HERE = Path(__file__).parent
WORK = HERE / "work"
SKILL = Path(r"C:\Users\marti\.claude-account2\skills\synced\5c9a5e14-fad1-48b1-9a09-6d75966edaeb_b70593fb-1829-42bc-994f-26c5917e2dec\pptx")
PY = sys.executable

SW, SH = 12192000, 6858000
EMU_PX = 1.5                        # the exports are the page × 1.5
TEAL, TEAL_D, GREY_T, INK_T, LINE_T = "2A918B", "0F726C", "5C6166", "2D3134", "BEC2CA"

# ---- the package --------------------------------------------------------------------------------------
shutil.rmtree(WORK, ignore_errors=True)
zipfile.ZipFile(SRC).extractall(WORK)


def add_slide_after(source, after):
    r = subprocess.run([PY, str(SKILL / "scripts/add_slide.py"), str(WORK), source, "--after", after],
                       capture_output=True, text=True, check=True)
    return re.search(r"ppt/slides/(slide\d+\.xml)", r.stdout).group(1)


media_n = [0]


def add_media(img: Image.Image) -> str:
    media_n[0] += 1
    name = f"figlayer{media_n[0]}.png"
    img.save(WORK / "ppt/media" / name)
    return name


# ---- layers ------------------------------------------------------------------------------------------
def layers_of(page):
    folder = FIGS / page
    out = []
    for f in sorted(folder.glob("[0-9][0-9]-*.png")):
        slug = f.stem[3:]
        out.append((slug, f))
    return out


def find(page, prefix):
    hits = [f for s, f in layers_of(page) if s.startswith(prefix)]
    assert len(hits) == 1, (page, prefix, hits)
    return hits[0]


def alpha_box(path):
    im = Image.open(path).convert("RGBA")
    return im, im.getchannel("A").getbbox()


# ---- shapes ------------------------------------------------------------------------------------------
def run(text, size, bold, color):
    return (f'<a:r><a:rPr lang="en-GB" sz="{int(size * 100)}" b="{1 if bold else 0}" i="0" dirty="0">'
            f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="Arial"/></a:rPr>'
            f'<a:t>{escape(text)}</a:t></a:r>')


def para(runs, align="l"):
    return (f'<a:p><a:pPr algn="{align}"><a:lnSpc><a:spcPct val="100000"/></a:lnSpc><a:spcBef><a:spcPts val="0"/>'
            f'</a:spcBef><a:spcAft><a:spcPts val="0"/></a:spcAft></a:pPr>{"".join(runs)}</a:p>')


class Slide:
    def __init__(self, title, label=None, timeline=None, caption0=None, captions=None):
        self.shapes, self.rels, self.next_id, self.media = [], [], 2, []
        self.title, self.label = title, label
        self.sp_ids = set()
        self.timeline = timeline
        self.clicks = []
        self.shape(self._title(title))
        if label:
            self.shape(self._label(label))
        self.circ, self.ring, self.caps = [], [], []
        if timeline:
            self._timeline(timeline, caption0, captions)

    def nid(self):
        self.next_id += 1
        return self.next_id - 1

    def shape(self, xml, sp=False):
        self.shapes.append(xml)

    def _title(self, text):
        i = self.nid()
        return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Title {i - 1}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
                f'<p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x="647700" y="609600"/>'
                f'<a:ext cx="10896600" cy="426641"/></a:xfrm></p:spPr><p:txBody><a:bodyPr lIns="0" tIns="0" rIns="0" '
                f'bIns="0" wrap="square" anchor="ctr"><a:noAutofit/></a:bodyPr><a:lstStyle/>'
                + para([run(text, 28, True, TEAL)]) + '</p:txBody></p:sp>')

    def textbox(self, x, y, cx, cy, paras, name="TextBox", anchor="ctr"):
        i = self.nid()
        self.sp_ids.add(i)
        self.shape(f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{name} {i - 1}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
                   f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect">'
                   f'<a:avLst/></a:prstGeom><a:noFill/></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" '
                   f'rIns="0" bIns="0" anchor="{anchor}"><a:noAutofit/></a:bodyPr><a:lstStyle/>{"".join(paras)}'
                   f'</p:txBody></p:sp>')
        return i

    def _label(self, text):
        i = self.nid()
        return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="TextBox {i - 1}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
                f'<p:spPr><a:xfrm><a:off x="647700" y="330200"/><a:ext cx="5715000" cy="182860"/></a:xfrm>'
                f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr><p:txBody><a:bodyPr wrap="square" '
                f'lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"><a:noAutofit/></a:bodyPr><a:lstStyle/>'
                + para([run(text, 12, True, TEAL_D).replace('dirty="0"', 'spc="100" dirty="0"')]) + '</p:txBody></p:sp>')

    def roundrect(self, x, y, d, fill, line, lw, text="", tcolor=None, size=12):
        i = self.nid()
        self.sp_ids.add(i)
        fill_x = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else '<a:noFill/>'
        body = (f'<p:txBody><a:bodyPr rtlCol="0" anchor="ctr" lIns="6350" tIns="6350" rIns="6350" bIns="6350" '
                f'wrap="square"><a:noAutofit/></a:bodyPr><a:lstStyle/>'
                + (para([run(text, size, True, tcolor)], "ctr") if text else '<a:p><a:pPr algn="ctr"/></a:p>')
                + '</p:txBody>')
        self.shape(f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Rounded Rectangle {i - 1}"/><p:cNvSpPr/><p:nvPr/>'
                   f'</p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{d}" cy="{d}"/></a:xfrm>'
                   f'<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 50000"/></a:avLst></a:prstGeom>'
                   f'{fill_x}<a:ln w="{lw}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln></p:spPr>'
                   f'{body}</p:sp>')
        return i

    def _timeline(self, labels, caption0, captions):
        n = len(labels)
        x0, x1, ly = 787400, 11404600, 5676900
        i = self.nid()
        self.shape(f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Rectangle {i - 1}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
                   f'<p:spPr><a:xfrm><a:off x="{x0}" y="{ly}"/><a:ext cx="{x1 - x0}" cy="25400"/></a:xfrm>'
                   f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="D9DCDF"/></a:solidFill>'
                   f'<a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr rtlCol="0" anchor="ctr"/><a:lstStyle/>'
                   f'<a:p><a:pPr algn="ctr"/></a:p></p:txBody></p:sp>')
        step = (x1 - x0) / (n - 1)
        cx = [round(x0 + k * step) for k in range(n)]
        size = 12 if n <= 8 else 10.5
        lw = min(1270000, int(step))
        for k, (c, lab) in enumerate(zip(cx, labels)):
            self.roundrect(c - 133350, 5556250, 266700, "FFFFFF", LINE_T, 12700, str(k + 1), GREY_T)
            self.textbox(c - lw // 2, 5880100, lw, 182860, [para([run(lab, size, False, GREY_T)], "ctr")])
        for k, c in enumerate(cx):
            self.circ.append(self.roundrect(c - 133350, 5556250, 266700, TEAL, TEAL, 12700, str(k + 1), "FFFFFF"))
            self.ring.append(self.roundrect(c - 168275, 5521325, 336550, None, TEAL_D, 19050))
        self.cap0 = self.textbox(647700, 6197600, 10896600, 222250, [para([run(caption0, 14, False, GREY_T)])])
        for lead, rest in captions:
            self.caps.append(self.textbox(647700, 6197600, 10896600, 222250,
                                          [para([run(lead, 14, True, TEAL_D), run(" " + rest, 14, False, INK_T)])]))

    def figure(self, page, prefixes, area=None):
        """Stack the page's layers (by slug prefix, in file order) into the figure area; returns slug -> spid."""
        if area is None:
            area = (647700, 1206500, 10896600, (5420000 if self.timeline else 6600000) - 1206500)
        files = [find(page, p) for p in prefixes]
        files = sorted(set(files), key=lambda f: f.name)
        boxes = {f: alpha_box(f) for f in files}
        ux0 = min(b[0] for _, b in boxes.values()); uy0 = min(b[1] for _, b in boxes.values())
        ux1 = max(b[2] for _, b in boxes.values()); uy1 = max(b[3] for _, b in boxes.values())
        ax, ay, aw, ah = area
        s = min(aw / (ux1 - ux0), ah / (uy1 - uy0))           # EMU per exported pixel
        ox = ax + (aw - (ux1 - ux0) * s) / 2
        oy = ay + (ah - (uy1 - uy0) * s) / 2
        self.emu_per_page_px = s * EMU_PX
        self.at = lambda px, py: (round(ox + (px * EMU_PX - ux0) * s), round(oy + (py * EMU_PX - uy0) * s))
        out = {}
        for f in files:
            im, b = boxes[f]
            name = add_media(im.crop(b))
            rid = f"rId{len(self.rels) + 2}"
            self.rels.append((rid, name))
            i = self.nid()
            x, y = round(ox + (b[0] - ux0) * s), round(oy + (b[1] - uy0) * s)
            cx, cy = round((b[2] - b[0]) * s), round((b[3] - b[1]) * s)
            label = f.stem[3:].replace("-", " ")
            self.shape(f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="Layer {escape(label)}" descr="{escape(label)}"/>'
                       f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
                       f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
                       f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
                       f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')
            for p in prefixes:
                if f.stem[3:].startswith(p):
                    out[p] = i
        return out

    # ---- clicks: each a list of groups, each group a list of effects ("in"/"out"/... , spid, args) ---------
    def click(self, k, *groups):
        """Step k of the timeline (1-based): its circle, ring and caption, plus the groups of effects."""
        first = [("out", self.cap0 if k == 1 else self.caps[k - 2]),
                 ("in", self.circ[k - 1]), ("in", self.ring[k - 1]), ("in", self.caps[k - 1])]
        if k > 1:
            first.append(("out", self.ring[k - 2]))
        gs = list(groups) or [[]]
        self.clicks.append([first + list(gs[0])] + list(gs[1:]))

    def plain_click(self, *groups):
        self.clicks.append(list(groups))

    def timing(self):
        cid = [2]
        grp = {}

        def n():
            cid[0] += 1
            return cid[0]

        def tgt(s):
            return f'<p:tgtEl><p:spTgt spid="{s}"/></p:tgtEl>'

        def vis(s, val, delay=0):
            return (f'<p:set><p:cBhvr><p:cTn id="{n()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="{delay}"/>'
                    f'</p:stCondLst></p:cTn>{tgt(s)}<p:attrNameLst><p:attrName>style.visibility</p:attrName>'
                    f'</p:attrNameLst></p:cBhvr><p:to><p:strVal val="{val}"/></p:to></p:set>')

        def effect(kind, s, node, args):
            g = grp.get(s, 0)
            grp[s] = g + 1
            head = lambda pid, cls, sub, extra="": (f'<p:par><p:cTn id="{n()}" presetID="{pid}" presetClass="{cls}" '
                                                    f'presetSubtype="{sub}" {extra}fill="hold" grpId="{g}" '
                                                    f'nodeType="{node}"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
                                                    f'<p:childTnLst>')
            tail = '</p:childTnLst></p:cTn></p:par>'
            if kind == "in":
                d = args.get("dur", 300)
                return head(10, "entr", 0) + vis(s, "visible") + (
                    f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{n()}" dur="{d}"/>{tgt(s)}'
                    f'</p:cBhvr></p:animEffect>') + tail, d
            if kind == "out":
                d = args.get("dur", 300)
                return head(10, "exit", 0) + (
                    f'<p:animEffect transition="out" filter="fade"><p:cBhvr><p:cTn id="{n()}" dur="{d}"/>{tgt(s)}'
                    f'</p:cBhvr></p:animEffect>') + vis(s, "hidden", d - 1) + tail, d
            if kind == "wipe":                                  # direction: "left" (from the left) or "bottom"
                d = args.get("dur", 600)
                sub, filt = {"left": (8, "wipe(right)"), "bottom": (4, "wipe(up)")}[args.get("dir", "left")]
                return head(22, "entr", sub) + vis(s, "visible") + (
                    f'<p:animEffect transition="in" filter="{filt}"><p:cBhvr><p:cTn id="{n()}" dur="{d}"/>{tgt(s)}'
                    f'</p:cBhvr></p:animEffect>') + tail, d
            if kind == "flyin":                                 # from the left
                d = args.get("dur", 800)
                anims = "".join(
                    f'<p:anim calcmode="lin" valueType="num"><p:cBhvr additive="base"><p:cTn id="{n()}" dur="{d}" '
                    f'fill="hold"/>{tgt(s)}<p:attrNameLst><p:attrName>{a}</p:attrName></p:attrNameLst></p:cBhvr>'
                    f'<p:tavLst><p:tav tm="0"><p:val><p:strVal val="{v0}"/></p:val></p:tav><p:tav tm="100000">'
                    f'<p:val><p:strVal val="{v1}"/></p:val></p:tav></p:tavLst></p:anim>'
                    for a, v0, v1 in [("ppt_x", "0-#ppt_w/2", "#ppt_x"), ("ppt_y", "#ppt_y", "#ppt_y")])
                return head(2, "entr", 8, 'decel="100000" ') + vis(s, "visible") + anims + tail, d
            if kind == "path":
                # From (x0, y0) to (x1, y1), fractions of the slide, both measured from where the shape is laid out:
                # PowerPoint starts every motion path there, not where the last one ended.
                d = args.get("dur", 1500)
                x0, y0 = args.get("x0", 0), args.get("y0", 0)
                x1, y1 = args.get("x1", 0), args.get("y1", 0)
                return head(0, "path", 0, 'accel="30000" decel="30000" ') + (
                    f'<p:animMotion origin="layout" path="M {x0:.5f} {y0:.5f} L {x1:.5f} {y1:.5f} E" '
                    f'pathEditMode="relative" '
                    f'rAng="0" ptsTypes="AA"><p:cBhvr><p:cTn id="{n()}" dur="{d}" fill="hold"/>{tgt(s)}'
                    f'<p:attrNameLst><p:attrName>ppt_x</p:attrName><p:attrName>ppt_y</p:attrName></p:attrNameLst>'
                    f'</p:cBhvr><p:rCtr x="0" y="0"/></p:animMotion>') + tail, d
            raise ValueError(kind)

        clicks_xml = []
        for groups in self.clicks:
            t = 0
            gx = []
            for gi, group in enumerate(groups):
                effs, longest = [], 0
                for ei, e in enumerate(group):
                    kind, s = e[0], e[1]
                    args = e[2] if len(e) > 2 else {}
                    node = "withEffect" if ei else ("clickEffect" if gi == 0 else "afterEffect")
                    xml, d = effect(kind, s, node, args)
                    effs.append(xml)
                    longest = max(longest, d)
                gx.append(f'<p:par><p:cTn id="{n()}" fill="hold"><p:stCondLst><p:cond delay="{t}"/></p:stCondLst>'
                          f'<p:childTnLst>{"".join(effs)}</p:childTnLst></p:cTn></p:par>')
                t += longest
            clicks_xml.append(f'<p:par><p:cTn id="{n()}" fill="hold"><p:stCondLst><p:cond delay="indefinite"/>'
                              f'</p:stCondLst><p:childTnLst>{"".join(gx)}</p:childTnLst></p:cTn></p:par>')
        if not clicks_xml:
            return ""
        bld = "".join(f'<p:bldP spid="{s}" grpId="{g}" animBg="1"/>' for s, c in sorted(grp.items())
                      if s in self.sp_ids for g in range(c))
        return ('<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
                '<p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq">'
                f'<p:childTnLst>{"".join(clicks_xml)}</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" '
                'delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst><p:nextCondLst><p:cond evt="onNext" '
                'delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq></p:childTnLst></p:cTn>'
                f'</p:par></p:tnLst>' + (f'<p:bldLst>{bld}</p:bldLst>' if bld else '') + '</p:timing>')

    def xml(self):
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cSld><p:bg><p:bgPr>'
                '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree>'
                '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
                + "".join(self.shapes) + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>'
                '<p:transition spd="med"><p:fade/></p:transition>' + self.timing() + '</p:sld>')


def write_slide(slide_file, sl: Slide, notes: str):
    """The slide, its rels (layout, pictures, notes) and its notes slide."""
    (WORK / "ppt/slides" / slide_file).write_text(sl.xml(), encoding="utf-8")
    num = re.search(r"\d+", slide_file).group(0)
    notes_file = f"notesSlide{num}.xml"
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'slideLayout" Target="../slideLayouts/slideLayout6.xml"/>']
    rels += [f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
             f'image" Target="../media/{name}"/>' for rid, name in sl.rels]
    rels.append(f'<Relationship Id="rId{len(sl.rels) + 2}" Type="http://schemas.openxmlformats.org/officeDocument/'
                f'2006/relationships/notesSlide" Target="../notesSlides/{notes_file}"/>')
    (WORK / f"ppt/slides/_rels/{slide_file}.rels").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.'
        'openxmlformats.org/package/2006/relationships">' + "".join(rels) + '</Relationships>', encoding="utf-8")
    tpl = (WORK / "ppt/notesSlides/notesSlide6.xml").read_text(encoding="utf-8")
    body = "".join(f'<a:p><a:r><a:rPr lang="en-GB" dirty="0"/><a:t>{escape(p)}</a:t></a:r></a:p>' if p else '<a:p/>'
                   for p in notes.strip().split("\n"))
    tpl = re.sub(r'(<p:ph type="body"[^>]*/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>).*?'
                 r'(</p:txBody>)', lambda m: m.group(1) + body + m.group(2), tpl, flags=re.S)
    (WORK / "ppt/notesSlides" / notes_file).write_text(tpl, encoding="utf-8")
    (WORK / f"ppt/notesSlides/_rels/{notes_file}.rels").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.'
        'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.'
        'org/officeDocument/2006/relationships/notesMaster" Target="../notesMasters/notesMaster1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="../slides/{slide_file}"/></Relationships>', encoding="utf-8")
    ct = WORK / "[Content_Types].xml"
    c = ct.read_text(encoding="utf-8")
    part = f"/ppt/notesSlides/{notes_file}"
    if part not in c:
        c = c.replace("</Types>", f'<Override PartName="{part}" ContentType="application/vnd.openxmlformats-'
                                  'officedocument.presentationml.notesSlide+xml"/></Types>')
        ct.write_text(c, encoding="utf-8")


# ---- the user's slides: timelines out, content centred, slides removed, pictures replaced ----------------
from lxml import etree  # noqa: E402

NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
TIMELINE_Y = 5400000                # the timeline, its labels and captions are all below this


def strip_timeline(slide_file):
    """Remove the click timeline and captions, their effects and the clicks left empty; then scale and
    centre what is left in the area the timeline freed."""
    path = WORK / "ppt/slides" / slide_file
    root = etree.fromstring(path.read_bytes())
    tree = root.find(".//p:cSld/p:spTree", NS)
    gone, content = set(), []
    for el in list(tree):
        off = el.find("./*/a:xfrm/a:off", NS)
        if off is None:
            continue
        cid = el.find("./*/p:cNvPr", NS).get("id")
        if int(off.get("y")) >= TIMELINE_Y:
            gone.add(cid)
            tree.remove(el)
        elif el.find(".//p:ph", NS) is None and int(off.get("y")) > 1000000:
            content.append(el)
    for eff in root.findall(".//p:par/p:cTn[@presetClass]/..", NS):
        if {t.get("spid") for t in eff.iter(f"{{{NS['p']}}}spTgt")} <= gone:
            eff.getparent().remove(eff)
    seq = root.find(".//p:cTn[@nodeType='mainSeq']/p:childTnLst", NS)
    for click in list(seq):
        groups = click.find("./p:cTn/p:childTnLst", NS)
        first_gone = False
        for i, grp in enumerate(list(groups)):
            if not len(grp.find("./p:cTn/p:childTnLst", NS)):
                groups.remove(grp)
                first_gone |= i == 0
        if not len(groups):
            seq.remove(click)
        elif first_gone:
            groups[0].find("./p:cTn/p:stCondLst/p:cond", NS).set("delay", "0")
            groups[0].find("./p:cTn/p:childTnLst/p:par/p:cTn", NS).set("nodeType", "clickEffect")
    for b in root.findall(".//p:bldP", NS):
        if b.get("spid") in gone:
            b.getparent().remove(b)
    # scale and centre the rest in the area under the title
    box = [(int(e.find("./*/a:xfrm/a:off", NS).get("x")), int(e.find("./*/a:xfrm/a:off", NS).get("y")),
            int(e.find("./*/a:xfrm/a:ext", NS).get("cx")), int(e.find("./*/a:xfrm/a:ext", NS).get("cy")))
           for e in content]
    x0, y0 = min(b[0] for b in box), min(b[1] for b in box)
    x1, y1 = max(b[0] + b[2] for b in box), max(b[1] + b[3] for b in box)
    ax, ay, aw, ah = 647700, 1206500, 10896600, 6550000 - 1206500
    f = min(aw / (x1 - x0), ah / (y1 - y0), 1.3)
    nx, ny = ax + (aw - (x1 - x0) * f) / 2, ay + (ah - (y1 - y0) * f) / 2
    for e in content:
        off, ext = e.find("./*/a:xfrm/a:off", NS), e.find("./*/a:xfrm/a:ext", NS)
        off.set("x", str(round(nx + (int(off.get("x")) - x0) * f)))
        off.set("y", str(round(ny + (int(off.get("y")) - y0) * f)))
        ext.set("cx", str(round(int(ext.get("cx")) * f))), ext.set("cy", str(round(int(ext.get("cy")) * f)))
        for el in e.iter():
            if el.get("sz") is not None and el.tag.endswith(("rPr", "defRPr", "endParaRPr")):
                el.set("sz", str(int(round(int(el.get("sz")) * f / 50) * 50)))
            if el.tag == f"{{{NS['a']}}}ln" and el.get("w"):
                el.set("w", str(round(int(el.get("w")) * f)))
    path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))
    return f


def remove_slides(*slide_files):
    pres = WORK / "ppt/presentation.xml"
    rels = (WORK / "ppt/_rels/presentation.xml.rels").read_text(encoding="utf-8")
    p = pres.read_text(encoding="utf-8")
    for sf in slide_files:
        rid = re.search(rf'<Relationship [^>]*Id="(rId\d+)"[^>]*Target="slides/{sf}"', rels) or \
            re.search(rf'<Relationship [^>]*Target="slides/{sf}"[^>]*Id="(rId\d+)"', rels)
        p = re.sub(rf'<p:sldId [^>]*r:id="{rid.group(1)}"/>', "", p)
    pres.write_text(p, encoding="utf-8")


def replace_picture(media, png):
    shutil.copy(png, WORK / "ppt/media" / media)


import slides_spec  # noqa: E402  (the slides: what each shows and how it animates)

slides_spec.build(sys.modules[__name__])
subprocess.run([PY, str(SKILL / "scripts/clean.py"), str(WORK)], check=True, capture_output=True)

# ---- pack -----------------------------------------------------------------------------------------------
OUT.unlink(missing_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    ct = WORK / "[Content_Types].xml"
    z.write(ct, "[Content_Types].xml")
    for f in sorted(WORK.rglob("*")):
        if f.is_file() and f != ct:
            z.write(f, f.relative_to(WORK).as_posix())
print("wrote", OUT)
