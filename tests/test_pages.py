"""Tests du travail page par page : remanier, numéroter, texte en tête,
alléger, livret A4 sur A3. Sans écran, sans Qt."""
import io
import re
import sys
from pathlib import Path

import pikepdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tutti import moteur, pages  # noqa: E402
from tutti.i18n import definir_langue  # noqa: E402
from tutti.moteur import ErreurTutti  # noqa: E402

definir_langue("fr")


def fabriquer(chemin: Path, tailles, rotations=None) -> Path:
    pdf = pikepdf.new()
    for i, (w, h) in enumerate(tailles):
        pdf.add_blank_page(page_size=(w, h))
        # chaque page porte son numéro d'origine, pour suivre son trajet
        pdf.pages[-1].obj.TuttiEssai = i
        if rotations and rotations[i]:
            pdf.pages[-1].obj.Rotate = rotations[i]
    pdf.save(chemin)
    return chemin


def ajouts(page) -> list[tuple[str, float, float, list]]:
    """(texte, x, y, matrice) de chaque texte posé par Tutti sur la page."""
    sortie = []
    for operandes, op in pikepdf.parse_content_stream(page):
        if str(op) == "Tm":
            m = [float(v) for v in operandes]
        elif str(op) == "Tj":
            sortie.append((bytes(operandes[0]).decode("cp1252"), m[4], m[5], m))
    return sortie


# ----------------------------------------------------------------- remanier

def test_remanier_ordre_rotation_retrait(tmp_path):
    src = fabriquer(tmp_path / "a.pdf", [(595, 842)] * 4, [0, 0, 90, 0])
    n = pages.remanier(src, tmp_path / "b.pdf", [(3, 0), (0, 90), (2, -90)])
    assert n == 3
    with pikepdf.open(tmp_path / "b.pdf") as pdf:
        assert [int(p.obj.TuttiEssai) for p in pdf.pages] == [3, 0, 2]
        assert [pages.rotation(p) for p in pdf.pages] == [0, 90, 0]


def test_remanier_rotation_heritee(tmp_path):
    """Une rotation écrite une seule fois sur l'arbre des pages est lue."""
    src = fabriquer(tmp_path / "a.pdf", [(595, 842)] * 2)
    with pikepdf.open(src, allow_overwriting_input=True) as pdf:
        pdf.Root.Pages.Rotate = 180
        pdf.save(src)
    with pikepdf.open(src) as pdf:
        assert pages.rotation(pdf.pages[0]) == 180
    pages.remanier(src, tmp_path / "b.pdf", [(0, 90), (1, 0)])
    with pikepdf.open(tmp_path / "b.pdf") as pdf:
        assert [pages.rotation(p) for p in pdf.pages] == [270, 180]


def test_remanier_refuse_d_ecraser_l_original(tmp_path):
    src = fabriquer(tmp_path / "a.pdf", [(595, 842)])
    with pytest.raises(ErreurTutti):
        pages.remanier(src, src, [(0, 0)])
    with pytest.raises(ErreurTutti):
        pages.remanier(src, tmp_path / "b.pdf", [])
    with pytest.raises(ErreurTutti):
        pages.remanier(src, tmp_path / "b.pdf", [(5, 0)])
    assert not (tmp_path / "b.pdf").exists()


# ----------------------------------------------------------------- numéros et texte

def test_numeros_au_centre_et_premiere_page_sautee(tmp_path):
    src = fabriquer(tmp_path / "a.pdf", [(595, 842)] * 3)
    f = pages.Finitions(numeros="bas_centre", format_numero="n_sur_total", sauter_premiere=True)
    b = pages.finir(src, tmp_path / "b.pdf", f)
    assert b.pages == 3
    with pikepdf.open(tmp_path / "b.pdf") as pdf:
        assert ajouts(pdf.pages[0]) == []
        (texte, x, y, _), = ajouts(pdf.pages[1])
        assert texte == "2 / 3"
        largeur = pages.largeur_texte(texte.encode("cp1252"), pages.TAILLE_NUMERO)
        assert x == pytest.approx((595 - largeur) / 2, abs=0.01)
        assert y == pytest.approx(pages.MARGE)


def test_numeros_cote_exterieur_alternent(tmp_path):
    src = fabriquer(tmp_path / "a.pdf", [(595, 842)] * 2)
    pages.finir(src, tmp_path / "b.pdf", pages.Finitions(numeros="bas_exterieur", premier=5))
    with pikepdf.open(tmp_path / "b.pdf") as pdf:
        (t1, x1, _, _), = ajouts(pdf.pages[0])
        (t2, x2, _, _), = ajouts(pdf.pages[1])
    assert (t1, t2) == ("5", "6")
    assert x1 > 500             # 5, impaire : à droite
    assert x2 == pytest.approx(pages.MARGE)   # 6, paire : à gauche


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_texte_en_haut_de_la_page_vue(tmp_path, rotation):
    """Sur une page tournée, « en haut » est le haut de la page telle qu'on la
    voit : on vérifie le point d'écriture dans le repère affiché."""
    src = fabriquer(tmp_path / "a.pdf", [(595, 842)], [rotation])
    pages.finir(src, tmp_path / "b.pdf", pages.Finitions(texte="Violon I"))
    with pikepdf.open(tmp_path / "b.pdf") as pdf:
        page = pdf.pages[0]
        (texte, x, y, m), = ajouts(page)
        a, b, c, d, e, f, largeur, hauteur = pages._vers_page(page)
    assert texte == "Violon I"
    # retour au repère affiché : (u, v) tel que x = a·u + c·v + e, y = b·u + d·v + f
    det = a * d - b * c
    u = (d * (x - e) - c * (y - f)) / det
    v = (-b * (x - e) + a * (y - f)) / det
    assert v > hauteur - pages.MARGE - 12          # tout en haut
    assert abs(u + pages.largeur_texte(b"Violon I", 10) / 2 - largeur / 2) < 1   # centré
    assert m[:4] == [a, b, c, d]                    # écrit dans le sens de lecture


def test_texte_premiere_page_seulement_et_caracteres(tmp_path):
    src = fabriquer(tmp_path / "a.pdf", [(595, 842)] * 2)
    pages.finir(src, tmp_path / "b.pdf",
                pages.Finitions(texte="Dvořák – Symphonie\nn° 9", texte_partout=False))
    with pikepdf.open(tmp_path / "b.pdf") as pdf:
        (texte, *_), = ajouts(pdf.pages[0])
        assert ajouts(pdf.pages[1]) == []
    assert texte == "Dvo?ák – Symphonie n° 9"      # ř hors de l'encodage, saut de ligne retiré


def test_finir_sans_rien_refuse(tmp_path):
    src = fabriquer(tmp_path / "a.pdf", [(595, 842)])
    with pytest.raises(ErreurTutti):
        pages.finir(src, tmp_path / "b.pdf", pages.Finitions())


def test_contenu_d_origine_isole(tmp_path):
    """Une page qui laisse l'état graphique modifié (ici une échelle ×10) ne
    déplace pas le numéro : le contenu d'origine est encadré par q … Q."""
    src = tmp_path / "a.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(595, 842))
    pdf.pages[0].contents_add(pikepdf.Stream(pdf, b"10 0 0 10 0 0 cm"))
    pdf.save(src)
    pages.finir(src, tmp_path / "b.pdf", pages.Finitions(numeros="bas_centre"))
    with pikepdf.open(tmp_path / "b.pdf") as pdf:
        ops = [str(op) for _, op in pikepdf.parse_content_stream(pdf.pages[0])]
    assert ops[0] == "q" and ops.index("Q") < ops.index("BT")


# ----------------------------------------------------------------- alléger

def _pdf_image(chemin: Path, image) -> Path:
    import img2pdf
    tampon = io.BytesIO()
    if image.mode == "1":
        image.save(tampon, format="PNG")
    else:
        image.save(tampon, format="JPEG", quality=95)
    chemin.write_bytes(img2pdf.convert(tampon.getvalue(),
                                       layout_fun=img2pdf.get_layout_fun((595.28, 841.89))))
    return chemin


def _images(chemin: Path):
    with pikepdf.open(chemin) as pdf:
        return [(int(o.Width), int(o.Height)) for o in pdf.objects
                if isinstance(o, pikepdf.Stream) and o.get("/Subtype") == pikepdf.Name.Image]


def test_alleger_reduit_une_photo_trop_fine(tmp_path):
    from PIL import Image, ImageDraw
    import random
    random.seed(3)
    im = Image.new("RGB", (3500, 4950), "white")
    d = ImageDraw.Draw(im)
    for _ in range(1500):
        x, y = random.randrange(3500), random.randrange(4950)
        d.ellipse((x, y, x + 30, y + 30), fill=(random.randrange(256),) * 3)
    src = _pdf_image(tmp_path / "photo.pdf", im)
    b = pages.finir(src, tmp_path / "leger.pdf", pages.Finitions(alleger=True))
    assert b.images_reduites == 1
    assert b.taille_apres < b.taille_avant / 3
    (w, h), = _images(tmp_path / "leger.pdf")
    assert max(w, h) == pytest.approx(11.69 * pages.DPI_LEGER, abs=3)   # A4 à 150 ppp


def test_alleger_laisse_les_petites_images_et_le_noir_et_blanc(tmp_path):
    from PIL import Image
    petite = _pdf_image(tmp_path / "petite.pdf", Image.new("RGB", (800, 1100), "gray"))
    nb = _pdf_image(tmp_path / "nb.pdf", Image.new("1", (4960, 7016), 1))
    for src in (petite, nb):
        b = pages.finir(src, tmp_path / f"{src.stem}-leger.pdf", pages.Finitions(alleger=True))
        assert b.images_reduites == 0
        assert _images(src) == _images(tmp_path / f"{src.stem}-leger.pdf")


# ----------------------------------------------------------------- livret A4 sur A3

def test_livret_a4_sur_a3(tmp_path):
    src = fabriquer(tmp_path / "a.pdf", [(595.28, 841.89)] * 8)
    n = moteur.assembler([src], tmp_path / "livret.pdf", moteur.Options(livret="a4"))
    assert n == 2 * 2          # 8 pages → 2 feuilles, recto et verso
    with pikepdf.open(tmp_path / "livret.pdf") as pdf:
        boite = [float(v) for v in pdf.pages[0].mediabox]
        assert boite[2] == pytest.approx(1190.55, abs=0.1)
        assert boite[3] == pytest.approx(841.89, abs=0.1)
        # échelle 1 : une page A4 tient exactement dans une demi-feuille A3
        contenu = pdf.pages[0].Contents.read_bytes() if not isinstance(
            pdf.pages[0].Contents, pikepdf.Array) else b"".join(
                s.read_bytes() for s in pdf.pages[0].Contents)
        echelles = [float(x) for x in re.findall(rb"([\d.]+) 0 0 [\d.]+ [\d.-]+ [\d.-]+ cm", contenu)]
        assert echelles and all(e == pytest.approx(1, abs=0.001) for e in echelles)
