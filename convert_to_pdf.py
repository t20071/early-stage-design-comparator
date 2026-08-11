"""
Convert README.md to README.pdf using xhtml2pdf (pure Python, no GTK needed).
Images are embedded as base64 data URIs after HTML conversion so they always appear.

Run: python convert_to_pdf.py
"""

import sys
import re
import base64
from pathlib import Path

HERE = Path(__file__).parent


def embed_images_in_html(html: str, base_dir: Path) -> str:
    """
    Replace every <img src="relative/path.png"> with a base64 data URI.
    Works on the HTML *after* markdown parsing, so nothing gets stripped.
    """
    def replace_src(m):
        src = m.group(1)
        # Skip already-inlined or remote images
        if src.startswith("data:") or src.startswith("http"):
            return m.group(0)
        img_path = base_dir / src
        if img_path.exists():
            ext = img_path.suffix.lstrip(".").lower()
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png",
                    "gif": "gif", "webp": "webp"}.get(ext, "png")
            b64 = base64.b64encode(img_path.read_bytes()).decode()
            print(f"  [embedded] {src}")
            return f'src="data:image/{mime};base64,{b64}"'
        else:
            print(f"  [not found] {src}")
            return m.group(0)

    # Match src="..." inside img tags
    return re.sub(r'src="([^"]+)"', replace_src, html)


def md_to_pdf():
    import markdown
    from xhtml2pdf import pisa

    md_text = (HERE / "README.md").read_text(encoding="utf-8")

    # Step 1: Convert markdown → HTML (images become <img src="path">)
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc", "nl2br"],
    )

    # Step 2: Embed all local images as base64 AFTER parsing
    print("Embedding images...")
    html_body = embed_images_in_html(html_body, HERE)

    css = """
        @page { margin: 2cm 2.2cm; size: A4; }
        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.65;
            color: #1a1a1a;
        }
        h1 {
            font-size: 20pt;
            font-weight: bold;
            color: #111;
            border-bottom: 2px solid #222;
            padding-bottom: 4px;
            margin-top: 0;
        }
        h2 {
            font-size: 14pt;
            font-weight: bold;
            color: #222;
            border-bottom: 1px solid #ccc;
            padding-bottom: 2px;
            margin-top: 22px;
        }
        h3 { font-size: 11pt; font-weight: bold; color: #333; margin-top: 14px; }
        p  { margin: 6px 0; }
        a  { color: #3f51b5; }
        code {
            font-family: Courier, monospace;
            background: #f4f4f4;
            padding: 1px 4px;
            font-size: 8.5pt;
        }
        pre {
            background: #f4f4f4;
            padding: 10px 14px;
            border-left: 4px solid #3f51b5;
            font-family: Courier, monospace;
            font-size: 8pt;
            margin: 10px 0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 12px 0;
            font-size: 9pt;
        }
        th {
            background: #3f51b5;
            color: white;
            padding: 6px 10px;
            text-align: left;
        }
        td { padding: 5px 10px; border-bottom: 1px solid #e0e0e0; }
        tr:nth-child(even) td { background: #f8f9ff; }
        img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            margin: 6px 0;
        }
        hr { border: none; border-top: 1px solid #ddd; margin: 16px 0; }
        ul, ol { margin: 6px 0; padding-left: 20px; }
        li { margin: 2px 0; }
        blockquote {
            border-left: 4px solid #3f51b5;
            margin: 10px 0;
            padding: 4px 12px;
            background: #f8f9ff;
            color: #444;
        }
    """

    full_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>{css}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    out_path = HERE / "README.pdf"
    print(f"Writing PDF...")
    with open(out_path, "wb") as f:
        result = pisa.CreatePDF(full_html, dest=f, encoding="utf-8")

    if result.err:
        print(f"[DONE with {result.err} warnings] {out_path}")
    else:
        print(f"[DONE] PDF written to: {out_path}")


if __name__ == "__main__":
    try:
        md_to_pdf()
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install with: pip install xhtml2pdf markdown")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
