"""Fabrique les captures du manuel, sans écran : QT_QPA_PLATFORM=offscreen python docs/captures.py

Les fichiers d'exemple sont fictifs et créés dans un dossier temporaire :
le manuel ne montre aucun nom ni chemin réel.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))

import pikepdf  # noqa: E402
from PyQt6 import QtCore, QtWidgets  # noqa: E402

from tutti import style  # noqa: E402
from tutti.i18n import definir_langue  # noqa: E402
from tutti.fenetre import FenetrePrincipale  # noqa: E402

PARTIES = {
    "fr": ("Symphonie n°5", "C:\\Users\\Musicien\\Documents\\Symphonie n°5", "06 Cor (ancienne version)",
           [("01 Conducteur", 24), ("02 Flûte", 3), ("03 Hautbois", 3), ("04 Clarinette en si bémol", 4),
            ("05 Basson", 3), ("10 Violon I", 5), ("11 Violon II", 5), ("12 Alto", 4),
            ("13 Violoncelle", 4), ("14 Contrebasse", 3)]),
    "en": ("Symphony No. 5", "C:\\Users\\Musician\\Documents\\Symphony No. 5", "06 Horn (old version)",
           [("01 Full score", 24), ("02 Flute", 3), ("03 Oboe", 3), ("04 Clarinet in B flat", 4),
            ("05 Bassoon", 3), ("10 Violin I", 5), ("11 Violin II", 5), ("12 Viola", 4),
            ("13 Cello", 4), ("14 Double bass", 3)]),
}


def attendre(app, condition, delai=20):
    fin = time.time() + delai
    while time.time() < fin and not condition():
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        time.sleep(0.01)


def main():
    app = QtWidgets.QApplication([])
    style.appliquer(app)
    for lg, (titre, dossier_affiche, abime, parties) in PARTIES.items():
        definir_langue(lg)
        base = Path(tempfile.mkdtemp()) / titre
        base.mkdir()
        for nom, pages in parties:
            pdf = pikepdf.new()
            for _ in range(pages):
                pdf.add_blank_page(page_size=(595, 842))
            pdf.save(base / f"{titre} - {nom}.pdf")
        (base / f"{titre} - {abime}.pdf").write_bytes(b"%PDF-1.4 abime")

        w = FenetrePrincipale()
        w.resize(860, 660)
        w.show()
        app.processEvents()
        w.grab().save(str(ICI / f"capture_vide-{lg}.png"))

        ordre = [base / f"{titre} - {n}.pdf" for n, _ in parties]
        ordre = [ordre[i] for i in (0, 9, 1, 2, 3, 4, 5, 6, 7, 8)]
        w.ajouter([str(p) for p in ordre] + [str(base / f"{titre} - {abime}.pdf")])
        attendre(app, lambda: all(i is not None for i in w._infos()))
        w.liste.setCurrentRow(10)
        w.e_dossier.setText(dossier_affiche)
        app.processEvents()
        w.grab().save(str(ICI / f"capture_erreur-{lg}.png"))

        w._retirer()
        w.liste.setCurrentRow(1)
        w._majeur_etat()
        app.processEvents()
        w.grab().save(str(ICI / f"capture_liste-{lg}.png"))

        w._trier()
        w.liste.setCurrentRow(0)
        app.processEvents()
        w.grab().save(str(ICI / f"capture_triee-{lg}.png"))

        w.onglets.setCurrentIndex(1)
        w.ajouter_a_decouper([str(base / f"{titre} - {parties[0][0]}.pdf")])
        w.r_plages.setChecked(True)
        w.e_plages.setText("1-8, 9-16, 17-")
        app.processEvents()
        w.grab().save(str(ICI / f"capture_decoupe-{lg}.png"))
        w.close()
    print("captures écrites dans", ICI)


if __name__ == "__main__":
    main()
