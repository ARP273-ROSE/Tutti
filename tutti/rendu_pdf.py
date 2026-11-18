"""Rendu des pages d'un PDF en images, pour les vignettes et l'aperçu.

Moteur : pdfium (celui de Chrome) par pypdfium2, licence Apache/BSD, roues
pour Windows, macOS et Linux. Il remplace QtPdf : PyQt6 6.12 (novembre 2026)
ne fournit plus ce module, et en dépendre bloquait Tutti sur une vieille
version de Qt. Si pypdfium2 manque, QtPdf sert encore quand il est là.

pdfium n'est pas fait pour être appelé depuis deux fils à la fois : les
vignettes sont dessinées dans un fil de fond pendant que l'aperçu (double
clic) est dessiné dans la fenêtre. Un verrou unique sérialise tout appel.
"""
from __future__ import annotations

import threading
from pathlib import Path

from PyQt6 import QtGui

_VERROU = threading.RLock()

try:
    import pypdfium2 as _pdfium
except Exception:          # paquet absent ou cassé : repli sur QtPdf
    _pdfium = None


class ErreurRendu(Exception):
    pass


def moteur() -> str:
    """« pdfium », « qtpdf » ou « aucun » : ce qui dessinera les pages."""
    if _pdfium is not None:
        return "pdfium"
    try:
        from PyQt6.QtPdf import QPdfDocument  # noqa: F401
        return "qtpdf"
    except Exception:
        return "aucun"


class DocumentPdf:
    """Un PDF ouvert pour le rendu. À fermer (ou `with`)."""

    def __init__(self, chemin):
        self._chemin = str(Path(chemin))
        self._doc = None
        self._qt = None
        with _VERROU:
            if _pdfium is not None:
                try:
                    self._doc = _pdfium.PdfDocument(self._chemin)
                except Exception as e:
                    raise ErreurRendu(str(e)) from e
            else:
                try:
                    from PyQt6.QtPdf import QPdfDocument
                except Exception as e:
                    raise ErreurRendu("aucun moteur de rendu PDF") from e
                self._qt = QPdfDocument(None)
                if self._qt.load(self._chemin) != QPdfDocument.Error.None_:
                    raise ErreurRendu(self._chemin)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def close(self):
        with _VERROU:
            if self._doc is not None:
                self._doc.close()
                self._doc = None
            if self._qt is not None:
                self._qt.close()
                self._qt = None

    def __len__(self) -> int:
        with _VERROU:
            if self._doc is not None:
                return len(self._doc)
            return self._qt.pageCount() if self._qt is not None else 0

    def taille(self, i: int) -> tuple[float, float]:
        """Largeur et hauteur de la page telle qu'elle s'affiche (rotation de
        la page comprise), en points."""
        with _VERROU:
            if self._doc is not None:
                page = self._doc[i]
                try:
                    # get_size() tient deja compte de /Rotate (verifie sur une
                    # page pivotee de 90 degres).
                    w, h = page.get_size()
                    return float(w), float(h)
                finally:
                    page.close()
            t = self._qt.pagePointSize(i)
            return float(t.width()), float(t.height())

    def rendre(self, i: int, largeur: int, hauteur: int) -> QtGui.QImage:
        """La page `i` sur papier blanc, dans un cadre largeur x hauteur pixels."""
        largeur, hauteur = max(1, int(largeur)), max(1, int(hauteur))
        with _VERROU:
            if self._doc is not None:
                page = self._doc[i]
                try:
                    w, h = page.get_size()
                    echelle = min(largeur / max(w, 1e-6), hauteur / max(h, 1e-6))
                    bitmap = page.render(scale=echelle, fill_color=(255, 255, 255, 255))
                    try:
                        pil = bitmap.to_pil().convert("RGB")
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                donnees = pil.tobytes("raw", "RGB")
                image = QtGui.QImage(donnees, pil.width, pil.height, 3 * pil.width,
                                     QtGui.QImage.Format.Format_RGB888)
                return image.copy()          # détache des octets Python
            from PyQt6 import QtCore
            image = self._qt.render(i, QtCore.QSize(largeur, hauteur))
        return sur_blanc(image)


def sur_blanc(image: QtGui.QImage) -> QtGui.QImage:
    """QtPdf rend la page sur fond transparent : sans papier blanc dessous, la
    vignette prendrait la couleur de ce qui est derrière (ombre, sélection)."""
    fond = QtGui.QImage(image.size(), QtGui.QImage.Format.Format_RGB32)
    fond.fill(QtGui.QColor("white"))
    p = QtGui.QPainter(fond)
    p.drawImage(0, 0, image)
    p.end()
    return fond
