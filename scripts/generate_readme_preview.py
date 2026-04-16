"""Generate docs/readme-preview.html — self-contained README viewer with Mermaid + SVG mockups."""
import base64, json, pathlib, re

ROOT = pathlib.Path(__file__).parent.parent

readme = (ROOT / "README.md").read_text()
hero_b64  = base64.b64encode((ROOT / "docs/hero.svg").read_bytes()).decode()
tabs_b64  = base64.b64encode((ROOT / "docs/card-tabs.svg").read_bytes()).decode()
sheet_b64 = base64.b64encode((ROOT / "docs/score-sheet.svg").read_bytes()).decode()

# Swap image paths for inline base64 data URIs
readme = readme.replace("docs/hero.svg",        f"data:image/svg+xml;base64,{hero_b64}")
readme = readme.replace("docs/card-tabs.svg",   f"data:image/svg+xml;base64,{tabs_b64}")
readme = readme.replace("docs/score-sheet.svg", f"data:image/svg+xml;base64,{sheet_b64}")

# Pre-process mermaid blocks in Python so marked.js needs zero custom renderer.
# ```mermaid\n...``` → <div class="mermaid">...</div>
readme = re.sub(
    r"```mermaid\n(.*?)```",
    lambda m: f'<div class="mermaid">{m.group(1)}</div>',
    readme,
    flags=re.DOTALL
)

readme_js = json.dumps(readme)

html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>News That Matters — README</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-light.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/11.1.1/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  * { box-sizing: border-box }
  body { background: #f6f8fa; margin: 0; padding: 32px 16px 80px;
         font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif }
  .banner { background: #7c3aed; color: white; text-align: center; padding: 12px 16px;
            font-size: 13px; font-weight: 700; border-radius: 10px;
            max-width: 980px; margin: 0 auto 24px; letter-spacing: .02em }
  .banner span { opacity: .75; font-weight: 400 }
  .markdown-body { background: white; border: 1px solid #d0d7de; border-radius: 10px;
                   padding: 48px 52px; max-width: 980px; margin: 0 auto;
                   box-shadow: 0 1px 3px rgba(0,0,0,.06) }
  .markdown-body img { max-width: 100%; border-radius: 10px; display: block; margin: 0 auto }
  details { border: 1px solid #d0d7de; border-radius: 8px; padding: 10px 18px;
            margin: 10px 0; background: #f6f8fa }
  details[open] { background: white }
  summary { cursor: pointer; padding: 5px 0; font-size: 14px; font-weight: 600 }
  summary:hover { color: #7c3aed }
  .markdown-body pre { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px }
  .mermaid { text-align: center; margin: 24px 0 }
  .mermaid svg { max-width: 100%; border-radius: 8px }
  @media(max-width: 700px) { .markdown-body { padding: 24px 18px } }
</style>
</head>
<body>
<div class="banner">
  📡 News That Matters &nbsp;·&nbsp;
  <span>README preview — Mermaid pipeline diagram · SVG card mockups · AI PM decisions</span>
</div>
<article class="markdown-body" id="top"><div id="content">Loading…</div></article>
<script>
mermaid.initialize({ startOnLoad: false, theme: 'neutral', flowchart: { curve: 'basis' } });

// No custom renderer needed — mermaid blocks are pre-processed to
// <div class="mermaid"> by the Python generator before JSON encoding.
marked.use({ gfm: true, breaks: false });

const raw = README_JS_PLACEHOLDER;
document.getElementById('content').innerHTML = marked.parse(raw);
document.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
mermaid.run({ querySelector: '.mermaid' });
</script>
</body>
</html>"""

html = html.replace("README_JS_PLACEHOLDER", readme_js)

out = ROOT / "docs/readme-preview.html"
out.write_text(html)
print(f"Written {len(html):,} chars → {out}")
