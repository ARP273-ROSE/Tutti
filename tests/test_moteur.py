"""Tests du moteur, sans écran : python -m pytest -q tests/"""
import os
import sys
from pathlib import Path

import pikepdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutti import moteur  # noqa: E402
from tutti.i18n import definir_langue  # noqa: E402

definir_langue("fr")           # les attendus de ces tests sont en français
from tutti.moteur import ErreurTutti, Options  # noqa: E402


def fabriquer(chemin: Path, pages: int, largeur: float = 595, hauteur: float = 842) -> Path:
    """PDF de test dont chaque page porte sa largeur comme signature."""
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(largeur, hauteur))
    pdf.save(chemin)
    return chemin


def largeurs(chemin: Path) -> list[int]:
    with pikepdf.open(chemin) as pdf:
        return [int(p.mediabox[2]) for p in pdf.pages]


# --- noms -------------------------------------------------------------------

def test_tri_naturel():
    noms = ["Partie 10.pdf", "partie 2.pdf", "Partie 1.pdf", "Écho.pdf", "echo 3.pdf"]
    tries = [p.name for p in moteur.trier(Path(n) for n in noms)]
    assert tries == ["echo 3.pdf", "Écho.pdf", "Partie 1.pdf", "partie 2.pdf", "Partie 10.pdf"]


def test_nom_propose_et_signets():
    chemins = [Path(f"Symphonie 5 - {n}.pdf") for n in
               ("32 Violon 1 Solo", "33 Violon I tutti", "37 Contrebasse")]
    assert moteur.proposer_nom(chemins) == "Symphonie 5 - complet.pdf"
    assert moteur.titre_signet(chemins[1], chemins) == "33 Violon I tutti"
    assert moteur.proposer_nom([Path("Seul.pdf")]) == "Seul - complet.pdf"
    assert moteur.proposer_nom([Path("a.pdf"), Path("b.pdf")]) == "Assemblage - complet.pdf"


def test_lister_pdf_dossier_et_doublons(tmp_path):
    for n in ("b 10.pdf", "b 2.pdf", "note.txt"):
        (tmp_path / n).write_bytes(b"x")
    (tmp_path / "sous").mkdir()
    (tmp_path / "sous" / "cache.pdf").write_bytes(b"x")
    res = moteur.lister_pdf([tmp_path, tmp_path / "b 2.pdf"])
    assert [p.name for p in res] == ["b 2.pdf", "b 10.pdf"]


# --- analyse ----------------------------------------------------------------

def test_analyse_et_erreurs(tmp_path):
    bon = fabriquer(tmp_path / "bon.pdf", 3, 400, 500)
    faux = tmp_path / "faux.pdf"
    faux.write_bytes(b"ceci n'est pas un PDF")
    secret = tmp_path / "secret.pdf"
    p = pikepdf.new()
    p.add_blank_page()
    p.save(secret, encryption=pikepdf.Encryption(user="motdepasse", owner="x"))

    i = moteur.analyser(bon)
    assert i.utilisable and i.pages == 3 and int(i.largeur) == 400
    assert not moteur.analyser(faux).utilisable
    assert "mot de passe" in moteur.analyser(secret).erreur
    assert "inaccessible" in moteur.analyser(tmp_path / "absent.pdf").erreur


def test_analyse_parallele_meme_resultat(tmp_path):
    chemins = [fabriquer(tmp_path / f"f{i:02d}.pdf", i % 4 + 1, 300 + i) for i in range(20)]
    vus = []
    infos = moteur.analyser_tous(chemins, rappel=vus.append)
    assert [i.chemin for i in infos] == chemins          # ordre conservé
    assert [i.pages for i in infos] == [i % 4 + 1 for i in range(20)]
    assert len(vus) == 20


# --- assemblage ---------------------------------------------------------------

def test_assemblage_ordre_signets(tmp_path):
    a = fabriquer(tmp_path / "Suite - 1 Prelude.pdf", 2, 101)
    b = fabriquer(tmp_path / "Suite - 2 Allemande.pdf", 1, 102)
    c = fabriquer(tmp_path / "Suite - 3 Courante.pdf", 3, 103)
    sortie = tmp_path / "Suite - complet.pdf"
    etapes = []
    n = moteur.assembler([c, a, b], sortie, Options(),
                         progression=lambda f, t, nom: etapes.append((f, t)))
    assert n == 6
    assert largeurs(sortie) == [103, 103, 103, 101, 101, 102]
    assert etapes[-1] == (4, 4)
    with pikepdf.open(sortie) as pdf:
        with pdf.open_outline() as plan:
            titres = [o.title for o in plan.root]
        assert titres == ["3 Courante", "1 Prelude", "2 Allemande"]
        assert str(pdf.docinfo["/Title"]) == "Suite - complet"
    assert not list(tmp_path.glob(".tutti-*"))          # aucun temporaire oublié


def test_recto_ajoute_pages_blanches(tmp_path):
    a = fabriquer(tmp_path / "a.pdf", 3, 201)
    b = fabriquer(tmp_path / "b.pdf", 2, 202)
    c = fabriquer(tmp_path / "c.pdf", 1, 203)
    sortie = tmp_path / "r.pdf"
    n = moteur.assembler([a, b, c], sortie, Options(recto=True))
    # a: p1-3, blanche p4, b: p5-6, c: p7 — chaque partie commence sur une impaire
    assert n == 7
    assert largeurs(sortie) == [201, 201, 201, 201, 202, 202, 203]


def test_refuse_d_ecraser_une_source(tmp_path):
    a = fabriquer(tmp_path / "a.pdf", 1)
    with pytest.raises(ErreurTutti, match="aussi l'un des fichiers"):
        moteur.assembler([a], tmp_path / "A.pdf" if os.name == "nt" else a)
    assert largeurs(a) == [595]                              # source intacte


def test_source_illisible_ne_laisse_rien(tmp_path):
    a = fabriquer(tmp_path / "a.pdf", 1)
    faux = tmp_path / "faux.pdf"
    faux.write_bytes(b"pas un pdf du tout")
    sortie = tmp_path / "sortie.pdf"
    with pytest.raises(ErreurTutti, match="faux.pdf"):
        moteur.assembler([a, faux], sortie)
    assert not sortie.exists()
    assert not list(tmp_path.glob(".tutti-*"))


def test_annulation(tmp_path):
    a = fabriquer(tmp_path / "a.pdf", 1)
    sortie = tmp_path / "s.pdf"
    with pytest.raises(ErreurTutti, match="annul"):
        moteur.assembler([a, a], sortie, annule=lambda: True)
    assert not sortie.exists()


def test_remplace_un_ancien_resultat(tmp_path):
    a = fabriquer(tmp_path / "a.pdf", 2, 301)
    sortie = fabriquer(tmp_path / "s.pdf", 5, 999)            # ancien résultat
    moteur.assembler([a], sortie)
    assert largeurs(sortie) == [301, 301]


def test_extension_obligatoire(tmp_path):
    a = fabriquer(tmp_path / "a.pdf", 1)
    with pytest.raises(ErreurTutti, match=".pdf"):
        moteur.assembler([a], tmp_path / "sortie.txt")


def test_liens_internes_et_droits(tmp_path):
    """Un lien interne (destination nommée) survit à l'assemblage ; le PDF
    final a les droits habituels, pas 600."""
    src = tmp_path / "liens.pdf"
    pdf = pikepdf.new()
    for _ in range(2):
        pdf.add_blank_page()
    pdf.Root.Names = pikepdf.Dictionary(Dests=pikepdf.Dictionary(
        Names=pikepdf.Array([pikepdf.String("fin"),
                             pikepdf.Array([pdf.pages[1].obj, pikepdf.Name.Fit])])))
    pdf.pages[0].Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=[0, 0, 100, 100],
        Dest=pikepdf.String("fin")))]))
    pdf.save(src)
    sortie = tmp_path / "s.pdf"
    moteur.assembler([fabriquer(tmp_path / "a.pdf", 1), src], sortie)
    with pikepdf.open(sortie) as res:
        if hasattr(res, "add_pages_from"):
            assert "/Names" in res.Root and "/Dests" in res.Root.Names
    if os.name != "nt":
        assert (sortie.stat().st_mode & 0o044) == 0o044     # lisible par le groupe et les autres


def test_ordre_livret():
    # 8 pages : feuille 1 = (8,1) / (2,7) ; feuille 2 = (6,3) / (4,5)  (numérotées dès 1)
    faces = [(g + 1, d + 1) for g, d in moteur.ordre_livret(8)]
    assert faces == [(8, 1), (2, 7), (6, 3), (4, 5)]
    # 5 pages : complété à 8 par 3 blanches (None), placées à la fin du livret
    assert moteur.ordre_livret(5)[0] == (None, 0)
    assert sum(1 for f in moteur.ordre_livret(5) for p in f if p is None) == 3


def test_assemblage_en_livret(tmp_path):
    a = fabriquer(tmp_path / "a.pdf", 6)
    sortie = tmp_path / "livret.pdf"
    n = moteur.assembler([a], sortie, Options(livret=True))
    assert n == 4                                 # 6 pages → 8 → 2 feuilles, 4 faces
    with pikepdf.open(sortie) as pdf:
        for p in pdf.pages:
            assert int(p.mediabox[2]) == 841 and int(p.mediabox[3]) == 595      # A4 paysage
        def dessins(page):            # nombre de pages posées sur la face
            return sum(1 for _, op in pikepdf.parse_content_stream(page)
                       if str(op) == "Do")
        assert dessins(pdf.pages[0]) == 1        # recto feuille 1 : (blanche ajoutée, page 1)
        assert dessins(pdf.pages[1]) == 1        # verso : (2, blanche)
        assert dessins(pdf.pages[2]) == 2        # feuille 2 recto : (6, 3)
    assert moteur.proposer_nom([Path("Concert - 1.pdf"), Path("Concert - 2.pdf")], livret=True) \
        == "Concert - livret.pdf"


def test_livret_a_partir_de_fichiers_d_une_page(tmp_path):
    """Huit fichiers d'une page chacun (ex. 8 pages de programme scannées
    séparément) : assemblés dans l'ordre de la liste puis mis en livret."""
    fichiers = [fabriquer(tmp_path / f"p{i}.pdf", 1, 400 + i) for i in range(1, 9)]
    # Ordre du livret seulement : 8 pages A4 remises en 8,1,2,7,6,3,4,5
    sortie = tmp_path / "ordre.pdf"
    assert moteur.assembler(fichiers, sortie, Options(livret="ordre")) == 8
    assert largeurs(sortie) == [408, 401, 402, 407, 406, 403, 404, 405]
    # Livret A5 : 2 feuilles, 4 faces A4 paysage
    sortie2 = tmp_path / "livret.pdf"
    assert moteur.assembler(fichiers, sortie2, Options(livret="a5")) == 4


def test_ordre_livret_complete_par_des_blanches(tmp_path):
    fichiers = [fabriquer(tmp_path / f"p{i}.pdf", 1, 500 + i) for i in range(1, 6)]
    sortie = tmp_path / "o.pdf"
    assert moteur.assembler(fichiers, sortie, Options(livret="ordre")) == 8
    # pages 6, 7, 8 blanches (largeur de la 1re page, 501) en fin de livret
    assert largeurs(sortie) == [501, 501, 502, 501, 501, 503, 504, 505]
