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

from tutti import pages as moteur_pages  # noqa: E402

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


def partition(chemin: Path, titre: str, nb: int, couchee: int | None = None) -> Path:
    """PDF fictif qui ressemble à une partition : titre, portées, barres de
    mesure et quelques « notes » — de quoi rendre les vignettes parlantes."""
    import random
    random.seed(nb)
    pdf = pikepdf.new()
    police = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
        BaseFont=pikepdf.Name("/Times-Bold"), Encoding=pikepdf.Name.WinAnsiEncoding))
    for n in range(nb):
        pdf.add_blank_page(page_size=(595, 842))
        page = pdf.pages[-1]
        flux = ["0.1 g 0.6 w"]
        haut = 760 if n == 0 else 800
        if n == 0:
            t = moteur_pages.encoder(titre)
            larg = len(t) * 11
            flux.append(f"BT /F1 22 Tf {(595 - larg) / 2:.0f} 790 Td <{t.hex()}> Tj ET")
        y = haut
        while y > 70:
            for k in range(5):
                flux.append(f"50 {y - 7 * k} m 545 {y - 7 * k} l S")
            for x in (50, 174, 298, 422, 545):
                flux.append(f"{x} {y} m {x} {y - 28} l S")
            for x in range(70, 540, 26):
                if random.random() < 0.55:
                    yy = y - random.randrange(0, 9) * 3.5
                    flux.append(f"{x} {yy} m {x + 6} {yy + 3} {x + 6} {yy - 3} {x} {yy} c f")
                    flux.append(f"{x + 6} {yy} m {x + 6} {yy + 17} l S")
            y -= 78
        page.obj.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=police))
        page.obj.Contents = pdf.make_stream("\n".join(flux).encode())
        if couchee is not None and n == couchee:
            page.obj.Rotate = 90
    pdf.save(chemin)
    return chemin


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

        w.onglets.setCurrentIndex(w.onglets.count() - 1)
        w.ajouter_a_decouper([str(base / f"{titre} - {parties[0][0]}.pdf")])
        attendre(app, lambda: all(i is not None for i in w._infos_d()))
        w.r_plages.setChecked(True)
        w.e_plages.setText("1-8, 9-16, 17-")
        app.processEvents()
        w.grab().save(str(ICI / f"capture_decoupe-{lg}.png"))

        # Onglet Pages : une partition de 9 pages dont la 4e a été scannée couchée
        conducteur = partition(base / f"{titre} - {parties[0][0]}.pdf", titre, 9, couchee=3)
        o = w.onglet_pages
        w.onglets.setCurrentWidget(o)
        o.ouvrir(str(conducteur))
        attendre(app, lambda: o.grille.count() == 9 and len(o.images) == 9)
        o.grille.item(3).setSelected(True)
        o.pivoter(-90)
        o.grille.clearSelection()
        o.grille.item(7).setSelected(True)
        o._majeur()
        app.processEvents()
        w.grab().save(str(ICI / f"capture_pages-{lg}.png"))
        o._sauve = o.etat()            # pas de question « abandonner ? » à la fermeture

        # Onglet Finitions : toutes les parties, numérotées et titrées
        f = w.onglet_finitions
        w.onglets.setCurrentWidget(f)
        f.ajouter([str(base / f"{titre} - {n}.pdf") for n, _ in parties[1:6]])
        f.c_numeros.setChecked(True)
        f.cb_position.setCurrentIndex(f.cb_position.findData("bas_exterieur"))
        f.cb_format.setCurrentIndex(f.cb_format.findData("n_sur_total"))
        f.s_premier.setValue(1)
        f.c_sauter.setChecked(False)
        f.e_texte.setText(titre)
        f.c_alleger.setChecked(True)
        f.liste.setCurrentRow(0)
        app.processEvents()
        w.grab().save(str(ICI / f"capture_finitions-{lg}.png"))

        # Le résultat d'une finition, vu dans un lecteur : page 2 d'un conducteur
        exemple = base / "exemple.pdf"
        moteur_pages.finir(conducteur, exemple, moteur_pages.Finitions(
            numeros="bas_exterieur", format_numero="n_sur_total", texte=titre))
        rendu = ICI / f"exemple_finitions-{lg}.png"
        from PyQt6.QtPdf import QPdfDocument
        doc = QPdfDocument(None)
        doc.load(str(exemple))
        doc.render(1, QtCore.QSize(595, 842)).save(str(rendu))
        doc.close()

        w.onglets.setCurrentIndex(0)
        w.close()
    print("captures écrites dans", ICI)


if __name__ == "__main__":
    main()
