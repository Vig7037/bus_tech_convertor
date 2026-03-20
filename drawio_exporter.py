"""
drawio_exporter.py
──────────────────
Converts Draw.io XML to a PNG image using one of three strategies:

  Strategy 1 (preferred):  draw.io desktop CLI
      drawio --export --format png --output out.png in.drawio

  Strategy 2 (fallback):   drawio-batch npm package
      drawio-batch in.drawio out.png

  Strategy 3 (pure Python): render the XML as an SVG in-memory using
      the drawio.com embed API (no local install required) — encodes the
      XML as a draw.io URL and fetches a PNG thumbnail via the unofficial
      export endpoint.  Works everywhere without any local install.

The caller receives either:
  - (png_bytes: bytes, method: str)  on success
  - raises DrawioExportError         on total failure
"""

import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Tuple


class DrawioExportError(Exception):
    pass


# ── Strategy 1: draw.io Desktop CLI ──────────────────────────────────────────

def _find_drawio_cli() -> str | None:
    """Return the path to the draw.io CLI, or None if not found."""
    # Common install locations across platforms
    candidates = [
        "drawio",                                   # on PATH (Linux/Mac brew)
        "/usr/bin/drawio",
        "/usr/local/bin/drawio",
        "/opt/drawio/drawio",
        # macOS app bundle
        "/Applications/draw.io.app/Contents/MacOS/draw.io",
        # Windows
        r"C:\Program Files\draw.io\draw.io.exe",
        r"C:\Program Files (x86)\draw.io\draw.io.exe",
    ]
    for c in candidates:
        if shutil.which(c) or Path(c).exists():
            return c
    return None


def export_via_desktop_cli(xml: str, output_path: Path) -> bool:
    """Try to export using the draw.io desktop CLI. Returns True on success."""
    cli = _find_drawio_cli()
    if not cli:
        return False

    with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False, mode="w", encoding="utf-8") as f:
        f.write(xml)
        tmp_in = f.name

    try:
        result = subprocess.run(
            [cli, "--export", "--format", "png", "--output", str(output_path), tmp_in],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0 and output_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    finally:
        os.unlink(tmp_in)


# ── Strategy 2: drawio-batch (npm) ───────────────────────────────────────────

def export_via_drawio_batch(xml: str, output_path: Path) -> bool:
    """Try the drawio-batch npm package. Returns True on success."""
    if not shutil.which("drawio-batch"):
        return False

    with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False, mode="w", encoding="utf-8") as f:
        f.write(xml)
        tmp_in = f.name

    try:
        result = subprocess.run(
            ["drawio-batch", tmp_in, str(output_path)],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0 and output_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    finally:
        os.unlink(tmp_in)


# ── Strategy 3: draw.io viewer URL → PNG via requests ────────────────────────

def _compress_drawio_xml(xml: str) -> str:
    """
    Compress Draw.io XML the same way draw.io does for URL encoding:
    UTF-8 → raw deflate (wbits=-15) → base64 → URL-encode
    """
    xml_bytes = xml.encode("utf-8")
    compressed = zlib.compress(xml_bytes, level=9)[2:-4]  # strip zlib header/trailer → raw deflate
    b64 = base64.b64encode(compressed).decode("ascii")
    return urllib.parse.quote(b64)


def _xml_to_drawio_url(xml: str) -> str:
    """Return a draw.io viewer URL that embeds the given XML."""
    compressed = _compress_drawio_xml(xml)
    return f"https://viewer.diagrams.net/?lightbox=1&highlight=0000ff&edit=_blank&xml={compressed}"


def export_via_url_png(xml: str, output_path: Path) -> bool:
    """
    Fetch a PNG via the draw.io export service.
    Uses the unofficial /export endpoint that many draw.io integrations rely on.
    Returns True on success.
    """
    try:
        # Encode the XML directly (not compressed) for the export endpoint
        encoded = urllib.parse.quote(xml)
        url = f"https://export.diagrams.net/export?format=png&xml={encoded}&scale=1.5&transparent=0"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "BizArchAgent/1.0 (Python)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                data = resp.read()
                if data[:4] == b"\x89PNG":   # valid PNG header
                    output_path.write_bytes(data)
                    return True
        return False
    except Exception:
        return False


# ── Strategy 4: SVG generation (pure Python, always works) ───────────────────

def _generate_svg_fallback(xml: str) -> bytes:
    """
    When no external tool is available, parse the Draw.io XML and generate
    a clean SVG that faithfully represents the diagram structure.
    This is a simplified but readable rendering.
    """
    import re

    # Parse mxCell elements
    cells = {}
    edges = []

    for m in re.finditer(
        r'<mxCell\s+([^/]*?)(?:/?>|>.*?</mxCell>)',
        xml, re.DOTALL
    ):
        attrs_str = m.group(1)

        def get(attr):
            a = re.search(rf'{attr}=["\']([^"\']*)["\']', attrs_str)
            return a.group(1) if a else ""

        cell_id = get("id")
        value = get("value")
        style = get("style")
        vertex = get("vertex")
        edge = get("edge")
        source = get("source")
        target = get("target")

        # geometry
        geo = re.search(
            r'<mxGeometry[^>]*x=["\']([^"\']*)["\'][^>]*y=["\']([^"\']*)["\'][^>]*'
            r'width=["\']([^"\']*)["\'][^>]*height=["\']([^"\']*)["\']',
            m.group(0)
        )
        x, y, w, h = (float(v) for v in geo.groups()) if geo else (0, 0, 120, 60)

        # Clean HTML from value
        clean_val = re.sub(r'<[^>]+>', ' ', value).strip()
        clean_val = clean_val.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&nbsp;', ' ')

        if vertex == "1" and cell_id not in ("0", "1"):
            cells[cell_id] = {"id": cell_id, "label": clean_val, "style": style,
                              "x": x, "y": y, "w": w, "h": h}
        elif edge == "1":
            edge_label = re.sub(r'<[^>]+>', '', value).strip()
            edges.append({"source": source, "target": target, "label": edge_label})

    if not cells:
        # Return a simple "no diagram" SVG
        svg_fallback = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100">'
            '<rect width="400" height="100" fill="#f5f5f5"/>'
            '<text x="200" y="55" text-anchor="middle" font-size="14" fill="#666">'
            "Diagram generated - open .drawio file to view"
            "</text></svg>"
        )
        return svg_fallback.encode("utf-8")

    # Compute bounding box
    all_x = [c["x"] for c in cells.values()] + [c["x"] + c["w"] for c in cells.values()]
    all_y = [c["y"] for c in cells.values()] + [c["y"] + c["h"] for c in cells.values()]
    min_x, max_x = min(all_x) - 40, max(all_x) + 40
    min_y, max_y = min(all_y) - 40, max(all_y) + 40
    vw, vh = max_x - min_x, max_y - min_y

    scale = min(1600 / max(vw, 1), 900 / max(vh, 1), 1.0)
    svg_w = int(vw * scale)
    svg_h = int(vh * scale)

    def tx(x): return (x - min_x) * scale
    def ty(y): return (y - min_y) * scale
    def tw(w): return w * scale
    def th(h): return h * scale

    def cell_color(style):
        if "fillColor=#F3F6FC" in style or "fillColor=#f3f6fc" in style:
            return "#F3F6FC", "#4285F4", 2
        if "fillColor=#fff2cc" in style or "cylinder" in style:
            return "#fff2cc", "#d6b656", 1.5
        if "fillColor=#dae8fc" in style:
            return "#dae8fc", "#6c8ebf", 1.5
        if "fillColor=#d5e8d4" in style:
            return "#d5e8d4", "#82b366", 1.5
        if "fillColor=#E8F0FE" in style or "fillColor=#e8f0fe" in style:
            return "#E8F0FE", "#4285F4", 1
        if "text;" in style and "strokeColor=none" in style:
            return "none", "none", 0
        return "#FFFFFF", "#4285F4", 1.5

    rects = []
    texts = []
    edge_lines = []

    for c in cells.values():
        fill, stroke, sw = cell_color(c["style"])
        x0, y0 = tx(c["x"]), ty(c["y"])
        w0, h0 = tw(c["w"]), th(c["h"])
        is_db = "cylinder" in c["style"]
        is_text = "text;" in c["style"] and "strokeColor=none" in c["style"]

        if not is_text:
            if is_db:
                # Draw cylinder as ellipse + rect
                ew, eh = w0, min(h0 * 0.3, 20)
                rects.append(
                    f'<rect x="{x0:.1f}" y="{y0+eh/2:.1f}" width="{w0:.1f}" height="{h0-eh/2:.1f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="4"/>'
                )
                rects.append(
                    f'<ellipse cx="{x0+w0/2:.1f}" cy="{y0+eh/2:.1f}" rx="{w0/2:.1f}" ry="{eh/2:.1f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
                )
                rects.append(
                    f'<ellipse cx="{x0+w0/2:.1f}" cy="{y0+eh/2:.1f}" rx="{w0/2:.1f}" ry="{eh/2:.1f}" '
                    f'fill="none" stroke="{stroke}" stroke-width="{sw}"/>'
                )
            else:
                rx_val = "8" if "rounded=1" in c["style"] else "4"
                rects.append(
                    f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{w0:.1f}" height="{h0:.1f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="{rx_val}"/>'
                )

        # Label (up to 2 lines)
        label_parts = c["label"].split("\n") if "\n" in c["label"] else [c["label"]]
        label_parts = [p.strip() for p in label_parts[:2] if p.strip()]
        cy = y0 + h0 / 2
        if len(label_parts) == 2:
            fs = max(9, min(13, w0 / 9))
            texts.append(
                f'<text x="{x0+w0/2:.1f}" y="{cy-6:.1f}" text-anchor="middle" '
                f'font-family="Arial,sans-serif" font-size="{fs:.0f}" font-weight="bold" fill="#333">'
                f'{label_parts[0][:22]}</text>'
            )
            texts.append(
                f'<text x="{x0+w0/2:.1f}" y="{cy+10:.1f}" text-anchor="middle" '
                f'font-family="Arial,sans-serif" font-size="{max(8,fs-2):.0f}" fill="#666">'
                f'{label_parts[1][:28]}</text>'
            )
        elif label_parts:
            fs = max(9, min(13, w0 / 9))
            texts.append(
                f'<text x="{x0+w0/2:.1f}" y="{cy+4:.1f}" text-anchor="middle" '
                f'font-family="Arial,sans-serif" font-size="{fs:.0f}" font-weight="bold" fill="#333">'
                f'{label_parts[0][:25]}</text>'
            )

    for e in edges:
        src = cells.get(e["source"])
        tgt = cells.get(e["target"])
        if not src or not tgt:
            continue
        x1 = tx(src["x"] + src["w"])
        y1 = ty(src["y"] + src["h"] / 2)
        x2 = tx(tgt["x"])
        y2 = ty(tgt["y"] + tgt["h"] / 2)
        mx = (x1 + x2) / 2
        edge_lines.append(
            f'<path d="M{x1:.1f},{y1:.1f} C{mx:.1f},{y1:.1f} {mx:.1f},{y2:.1f} {x2:.1f},{y2:.1f}" '
            f'fill="none" stroke="#4285F4" stroke-width="1.5" '
            f'marker-end="url(#arrow)" opacity="0.8"/>'
        )
        if e["label"]:
            texts.append(
                f'<text x="{mx:.1f}" y="{(y1+y2)/2-4:.1f}" text-anchor="middle" '
                f'font-family="Arial,sans-serif" font-size="9" fill="#666">{e["label"][:15]}</text>'
            )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#4285F4"/>
    </marker>
  </defs>
  <rect width="{svg_w}" height="{svg_h}" fill="#f8f9fa"/>
  {''.join(rects)}
  {''.join(edge_lines)}
  {''.join(texts)}
</svg>"""

    return svg.encode("utf-8")


def _svg_to_png_bytes(svg_bytes: bytes) -> bytes:
    """Convert SVG bytes to PNG using cairosvg if available, else return SVG bytes."""
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg_bytes, scale=2.0)
    except ImportError:
        pass
    try:
        from PIL import Image
        import io, struct
        # If cairosvg not available, return SVG bytes wrapped — Streamlit can display SVG
        return svg_bytes
    except Exception:
        return svg_bytes


# ── Public API ────────────────────────────────────────────────────────────────

def drawio_xml_to_image(xml: str, output_dir: Path | None = None) -> Tuple[bytes, str, str]:
    """
    Convert Draw.io XML to an image.

    Returns: (image_bytes, mime_type, method_used)
      mime_type is 'image/png' or 'image/svg+xml'
    """
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir())

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "architecture.png"

    # Strategy 1: draw.io desktop CLI
    if export_via_desktop_cli(xml, png_path):
        return png_path.read_bytes(), "image/png", "draw.io Desktop CLI"

    # Strategy 2: drawio-batch
    if export_via_drawio_batch(xml, png_path):
        return png_path.read_bytes(), "image/png", "drawio-batch (npm)"

    # Strategy 3: draw.io export service
    if export_via_url_png(xml, png_path):
        return png_path.read_bytes(), "image/png", "draw.io Export Service"

    # Strategy 4: Pure Python SVG fallback
    svg_bytes = _generate_svg_fallback(xml)
    png_bytes = _svg_to_png_bytes(svg_bytes)

    if png_bytes[:4] == b"\x89PNG":
        return png_bytes, "image/png", "Python SVG → PNG (cairosvg)"
    else:
        return svg_bytes, "image/svg+xml", "Python SVG renderer (fallback)"


def save_drawio_file(xml: str, output_dir: Path, filename: str = "architecture.drawio") -> Path:
    """Save the raw Draw.io XML as a .drawio file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(xml, encoding="utf-8")
    return path
