#!/usr/bin/env python3
"""Logo de Tutti : UNE source SVG (logo.svg), tout le reste en est rendu.

    QT_QPA_PLATFORM=offscreen python make_logo.py      (PyQt6 + Pillow)

Le dessin historique — trois partitions assemblées, tenues par une bande d'or,
sur fond bordeaux — redessiné en vectoriel. Sorties : logo.svg (la source),
logo_{16,32,64,128,256,512,1024}.png, logo.png (= 256), logo.ico (installeur
Windows, multi-tailles) et logo.icns (macOS).
"""
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
BORDEAUX, BORDEAUX_SOMBRE, OR, PAPIER, PAPIER_OMBRE, ENCRE = (
    "#7A1F2B", "#5E1620", "#C9A227", "#FBF8F1", "#E9E2D2", "#1E1A17")


def _portee(x, y, l):
    return "\n".join(f'<line x1="{x}" y1="{y + i * 9}" x2="{x + l}" y2="{y + i * 9}" '
                     f'stroke="{ENCRE}" stroke-width="2.6"/>' for i in range(5))


def _croches(x, y):
    """Deux croches liées : têtes, hampes, ligature."""
    t = []
    for dx, dy in ((0, 0), (52, -12)):
        t.append(f'<ellipse cx="{x + dx}" cy="{y + dy}" rx="11" ry="8" '
                 f'transform="rotate(-20 {x + dx} {y + dy})" fill="{ENCRE}"/>')
        t.append(f'<rect x="{x + dx + 8}" y="{y + dy - 58}" width="4" height="58" fill="{ENCRE}"/>')
    t.append(f'<polygon points="{x + 8},{y - 58} {x + 64},{y - 70} {x + 64},{y - 58} '
             f'{x + 8},{y - 46}" fill="{ENCRE}"/>')
    return "\n".join(t)


def construire_svg() -> str:
    n = 512
    feuille = 'rx="16" fill="{f}" stroke="{s}" stroke-width="3"'
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{n}" height="{n}" viewBox="0 0 {n} {n}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="fond" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{BORDEAUX}"/>
      <stop offset="100%" stop-color="{BORDEAUX_SOMBRE}"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="480" height="480" rx="96" fill="url(#fond)"/>
  <rect x="40" y="40" width="432" height="432" rx="76" fill="none" stroke="{OR}" stroke-width="5"/>
  <g transform="rotate(-8 256 270)"><rect x="96" y="108" width="270" height="330" {feuille.format(f=PAPIER_OMBRE, s="#CFC5B2")}/>
    {_portee(122, 170, 110)}</g>
  <g transform="rotate(7 256 270)"><rect x="150" y="104" width="270" height="330" {feuille.format(f=PAPIER_OMBRE, s="#CFC5B2")}/>
    {_portee(300, 170, 100)}</g>
  <rect x="126" y="86" width="260" height="350" {feuille.format(f=PAPIER, s="#D9CFBE")}/>
  {_portee(150, 168, 212)}
  {_croches(214, 196)}
  {_portee(150, 282, 212)}
  {_croches(214, 310)}
  <rect x="112" y="372" width="288" height="30" rx="10" fill="{OR}" stroke="#8C6E12" stroke-width="2"/>
</svg>
'''


def rendre(svg: Path, sortie: Path, taille: int) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    img = QImage(taille, taille, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    QSvgRenderer(str(svg)).render(p, QRectF(0, 0, taille, taille))
    p.end()
    img.save(str(sortie), "PNG")


def main():
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)  # noqa: F841 — requis pour le rendu
    svg = ICI / "logo.svg"
    svg.write_text(construire_svg(), encoding="utf-8")
    for taille in (16, 32, 64, 128, 256, 512, 1024):
        rendre(svg, ICI / f"logo_{taille}.png", taille)
    (ICI / "logo.png").write_bytes((ICI / "logo_256.png").read_bytes())
    from PIL import Image
    img = Image.open(ICI / "logo_1024.png").convert("RGBA")
    img.save(ICI / "logo.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                      (64, 64), (128, 128), (256, 256)])
    img.save(ICI / "logo.icns")
    print("logo.svg -> logo_*.png, logo.png, logo.ico, logo.icns")


if __name__ == "__main__":
    main()
