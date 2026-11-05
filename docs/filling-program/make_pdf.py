"""Make a PDF of a Markdown document of the repository, with its pictures, for printing or reading.

    python docs/filling-program/make_pdf.py docs/filling-program.md filling-program.pdf

pandoc makes one HTML page of it (GitHub's Markdown, so the links in the contents find their
headings, with the pictures in it and the look of pdf.css), and a browser, headless (Chrome, else
Edge), prints that to the PDF: A4, each numbered section on a new page, page numbers, the headings as
bookmarks. The pictures stay drawings, sharp at any zoom. Links within the document work; links to
other files become plain text, since a PDF cannot follow them.
"""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
# Keep links within the document (#...) and to the web; a link to another file keeps only its text.
FILTER = """
function Link(link)
  if link.target:match("^#") or link.target:match("^%a%a+:") then return link end
  return link.content
end
"""


def make_pdf(source: Path, pdf: Path) -> None:
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if browser is None:
        raise SystemExit("Neither Chrome nor Edge found")
    title = next((line[2:].strip() for line in source.read_text(encoding="utf-8").splitlines()
                  if line.startswith("# ")), source.stem)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:
        scratch = Path(scratch)
        (scratch / "links.lua").write_text(FILTER, encoding="utf-8")
        html = scratch / "page.html"
        subprocess.run(["pandoc", str(source), "-f", "gfm", "-t", "html5", "--standalone", "--embed-resources",
                        "--resource-path", str(source.parent), "--css", str(HERE / "pdf.css"),
                        "--lua-filter", str(scratch / "links.lua"), "--metadata", f"pagetitle={title}",
                        "-o", str(html)], check=True)
        out = scratch / "page.pdf"
        subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        "--generate-pdf-document-outline", f"--user-data-dir={scratch / 'profile'}",
                        f"--print-to-pdf={out}", html.as_uri()], check=True, capture_output=True)
        # The browser returns before it has written the PDF: wait until its size stays the same.
        size, start = -1, time.monotonic()
        while not out.exists() or out.stat().st_size != size or out.stat().st_size == 0:
            if time.monotonic() - start > 180:
                raise SystemExit(f"{Path(browser).name} made no PDF")
            size = out.stat().st_size if out.exists() else -1
            time.sleep(2)
        pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(out, pdf)


if __name__ == "__main__":
    make_pdf(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
    print(sys.argv[2])
