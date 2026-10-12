"""Test de la fenêtre sans écran (QT_QPA_PLATFORM=offscreen).

Parcourt le chemin réel d'un utilisateur : déposer des fichiers, attendre
l'analyse, réordonner, assembler — et vérifie que le fil graphique n'a
jamais été bloqué (la boucle d'événements tourne pendant tout le travail).
"""
import os
import sys
import time
from pathlib import Path

import pikepdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from tutti import style  # noqa: E402
from tutti.i18n import definir_langue  # noqa: E402

definir_langue("fr")
from tutti.fenetre import FenetrePrincipale  # noqa: E402


@pytest.fixture(scope="module")
def app():
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    style.appliquer(a)
    return a


def attendre(app, condition, delai=20.0):
    fin = time.time() + delai
    while time.time() < fin:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if condition():
            return True
        time.sleep(0.01)
    return False


def fabriquer(chemin: Path, pages: int, largeur: int) -> Path:
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(largeur, 842))
    pdf.save(chemin)
    return chemin


def test_parcours_complet(app, tmp_path, monkeypatch):
    from PyQt6 import QtGui
    ouverts = []
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda url: ouverts.append(url) or True)
    noms = ["Symphonie - 10 Contrebasse", "Symphonie - 2 Flute", "Symphonie - 1 Conducteur"]
    for i, n in enumerate(noms):
        fabriquer(tmp_path / f"{n}.pdf", i + 1, 500 + i)
    (tmp_path / "notes.txt").write_text("pas un pdf")

    w = FenetrePrincipale()
    w.c_ouvrir.setChecked(True)          # pas de boîte modale : on ouvre le PDF
    w.show()
    w.ajouter([str(tmp_path)])                      # glisser un dossier
    assert w.liste.count() == 3
    assert attendre(app, lambda: all(i is not None for i in w._infos()))
    # tri naturel à l'ajout d'un dossier : 1, 2, 10
    assert [p.name for p in w.chemins()][0] == "Symphonie - 1 Conducteur.pdf"
    assert w.e_nom.text() == "Symphonie - complet.pdf"
    assert w.b_assembler.isEnabled()

    # réordonner : la contrebasse remonte en tête
    w.liste.setCurrentRow(2)
    w._deplacer(-1)
    w._deplacer(-1)
    assert w.chemins()[0].name == "Symphonie - 10 Contrebasse.pdf"

    # un doublon n'est pas ajouté deux fois
    w.ajouter([str(tmp_path / "Symphonie - 2 Flute.pdf")])
    assert w.liste.count() == 3

    w.grab().save(str(tmp_path / "capture.png"))

    w._assembler_ou_annuler()
    assert attendre(app, lambda: not w._en_cours)
    sortie = tmp_path / "Symphonie - complet.pdf"
    assert sortie.exists()
    assert ouverts and ouverts[0].toLocalFile() == str(sortie)
    with pikepdf.open(sortie) as pdf:
        assert [int(p.mediabox[2]) for p in pdf.pages] == [500, 502, 502, 502, 501, 501]
        with pdf.open_outline() as plan:
            assert [o.title for o in plan.root] == ["10 Contrebasse", "1 Conducteur", "2 Flute"]
    w.close()


def test_fichier_illisible_bloque_l_assemblage(app, tmp_path):
    fabriquer(tmp_path / "bon.pdf", 1, 400)
    (tmp_path / "abime.pdf").write_bytes(b"%PDF-1.4 tronque")
    w = FenetrePrincipale()
    w.ajouter([str(tmp_path / "bon.pdf"), str(tmp_path / "abime.pdf")])
    assert attendre(app, lambda: all(i is not None for i in w._infos()))
    assert not w.b_assembler.isEnabled()
    assert "illisible" in w.resume.text()
    w.liste.setCurrentRow(1)
    w._retirer()
    assert w.b_assembler.isEnabled()
    w.close()


def test_images_dans_l_assemblage(app, tmp_path, monkeypatch):
    from PIL import Image
    from PyQt6 import QtGui
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda url: True)
    fabriquer(tmp_path / "Recueil - 1 Texte.pdf", 2, 400)
    Image.new("RGB", (900, 1300), "white").save(tmp_path / "Recueil - 2 Photo.jpg")
    w = FenetrePrincipale()
    w.ajouter([str(tmp_path)])
    assert w.liste.count() == 2
    assert attendre(app, lambda: all(i is not None for i in w._infos()))
    assert "(image)" in w.liste.item(1).text()
    w._assembler_ou_annuler()
    assert attendre(app, lambda: not w._en_cours)
    with pikepdf.open(tmp_path / "Recueil - complet.pdf") as pdf:
        assert len(pdf.pages) == 3
    w.close()


def test_onglet_decouper(app, tmp_path, monkeypatch):
    from PyQt6 import QtGui
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda url: True)
    src = fabriquer(tmp_path / "Partition.pdf", 5, 500)
    w = FenetrePrincipale()
    w.onglets.setCurrentIndex(1)
    assert not w.b_decouper.isEnabled()
    w.ajouter_a_decouper([str(src), str(tmp_path / "ignore.txt")])
    assert w.liste_d.count() == 1 and w.b_decouper.isEnabled()
    w.r_plages.setChecked(True)
    w.e_plages.setText("1-2, 3-")
    w._decouper_ou_annuler()
    assert attendre(app, lambda: not w._decoupe_en_cours)
    dossier = tmp_path / "Partition - pages"
    assert sorted(p.name for p in dossier.iterdir()) == ["Partition - pages 1-2.pdf",
                                                         "Partition - pages 3-5.pdf"]
    w.close()
