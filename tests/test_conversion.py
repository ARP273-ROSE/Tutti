"""Conversion d'images et découpage (sans écran)."""
import sys
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutti import conversion, moteur  # noqa: E402
from tutti.i18n import definir_langue  # noqa: E402
from tutti.moteur import ErreurTutti  # noqa: E402

definir_langue("fr")


def fabriquer_pdf(chemin: Path, pages: int, largeur: int = 595) -> Path:
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(largeur, 842))
    pdf.save(chemin)
    return chemin


def test_types():
    assert conversion.type_fichier(Path("a.PDF")) == "pdf"
    assert conversion.type_fichier(Path("photo.JPG")) == "image"
    assert conversion.type_fichier(Path("lettre.docx")) == "office"
    assert conversion.type_fichier(Path("tableau.xlsx")) == "office"
    assert conversion.type_fichier(Path("diapos.pptx")) == "office"
    assert conversion.type_fichier(Path("notes.txt")) is None


def test_jpeg_insere_sans_recompression(tmp_path):
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (1200, 800), (200, 30, 40)).save(src, quality=90)
    dest = conversion.convertir(src, tmp_path / "conv")
    with pikepdf.open(dest) as pdf:
        assert len(pdf.pages) == 1
        page = pdf.pages[0]
        assert float(page.mediabox[2]) > float(page.mediabox[3])      # paysage, comme l'image
        image = next(iter(page.Resources.XObject.values()))
        assert image.Filter == pikepdf.Name.DCTDecode                    # le JPEG tel quel
        assert bytes(image.read_raw_bytes()) == src.read_bytes()


def test_png_transparent_et_tiff_multipage(tmp_path):
    png = tmp_path / "logo.png"
    Image.new("RGBA", (300, 500), (0, 0, 0, 0)).save(png)
    tif = tmp_path / "scan.tif"
    images = [Image.new("L", (600, 800), v) for v in (40, 120, 220)]
    images[0].save(tif, save_all=True, append_images=images[1:])
    with pikepdf.open(conversion.convertir(png, tmp_path / "c")) as pdf:
        assert len(pdf.pages) == 1
    with pikepdf.open(conversion.convertir(tif, tmp_path / "c")) as pdf:
        assert len(pdf.pages) == 3


def test_image_abimee(tmp_path):
    faux = tmp_path / "faux.jpg"
    faux.write_bytes(b"pas une image")
    with pytest.raises(conversion.ErreurConversion):
        conversion.convertir(faux, tmp_path / "c")
    assert not list((tmp_path / "c").glob("*"))           # rien laissé derrière


def test_assemblage_melange_pdf_et_images(tmp_path):
    a = fabriquer_pdf(tmp_path / "01 Conducteur.pdf", 2)
    img = tmp_path / "02 Photo.jpg"
    Image.new("RGB", (800, 1200), "white").save(img)
    infos = moteur.analyser_tous([a, img], dossier_conversions=tmp_path / "conv")
    assert [i.pages for i in infos] == [2, 1]
    assert infos[1].genre == "image" and infos[1].pdf.exists()
    sortie = tmp_path / "Tout.pdf"
    n = moteur.assembler([a, img], sortie, converties={str(img): infos[1].pdf})
    assert n == 3
    # sans analyse préalable : conversion à la volée
    assert moteur.assembler([img, a], tmp_path / "Tout2.pdf") == 3


def test_nom_propose_pour_une_conversion_seule():
    assert moteur.proposer_nom([Path("Lettre au chef.docx")]) == "Lettre au chef.pdf"


def test_office_sans_logiciel(tmp_path, monkeypatch):
    if sys.platform == "win32":
        pytest.skip("Office peut être présent sur le poste de test")
    monkeypatch.setattr(conversion, "trouver_libreoffice", lambda: None)
    doc = tmp_path / "lettre.docx"
    doc.write_bytes(b"PK")
    info = moteur.analyser(doc, tmp_path / "c")
    assert not info.utilisable and "LibreOffice" in info.erreur


@pytest.mark.skipif(conversion.trouver_libreoffice() is None, reason="LibreOffice absent")
def test_office_par_libreoffice(tmp_path):
    doc = tmp_path / "lettre.rtf"
    doc.write_text(r"{\rtf1\ansi Bonjour\par}", encoding="ascii")
    with pikepdf.open(conversion.convertir(doc, tmp_path / "c")) as pdf:
        assert len(pdf.pages) == 1


# --- découpage ------------------------------------------------------------------

def test_lire_plages():
    assert moteur.lire_plages("1-3, 5; 8-", 10) == [(1, 3), (5, 5), (8, 10)]
    assert moteur.lire_plages("-2", 10) == [(1, 2)]
    for faux in ("", "a", "3-1", "0", "11", "1-12", "-"):
        with pytest.raises(ErreurTutti):
            moteur.lire_plages(faux, 10)


def test_decouper_une_page_par_fichier(tmp_path):
    src = fabriquer_pdf(tmp_path / "Partition.pdf", 12)
    with pikepdf.open(src, allow_overwriting_input=True) as pdf:        # pages reconnaissables
        for i, p in enumerate(pdf.pages):
            p.mediabox = [0, 0, 300 + i, 842]
        pdf.save(src)
    fichiers = moteur.decouper(src, tmp_path / "pages")
    assert [f.name for f in fichiers][:2] == ["Partition - page 01.pdf", "Partition - page 02.pdf"]
    assert len(fichiers) == 12
    for i, f in enumerate(fichiers):
        with pikepdf.open(f) as pdf:
            assert len(pdf.pages) == 1 and int(pdf.pages[0].mediabox[2]) == 300 + i
    with pikepdf.open(src) as pdf:
        assert len(pdf.pages) == 12                                     # source intacte


def test_decouper_par_plages_en_parallele(tmp_path):
    src = fabriquer_pdf(tmp_path / "Gros.pdf", 90)
    fichiers = moteur.decouper(src, tmp_path / "out")                   # 90 fichiers : multi-cœur
    assert len(fichiers) == 90 and all(f.exists() for f in fichiers)
    plages = moteur.lire_plages("1-30, 31-60, 61-", 90)
    f2 = moteur.decouper(src, tmp_path / "out2", plages)
    assert [p.name for p in f2] == ["Gros - pages 01-30.pdf", "Gros - pages 31-60.pdf",
                                    "Gros - pages 61-90.pdf"]
    with pikepdf.open(f2[2]) as pdf:
        assert len(pdf.pages) == 30
