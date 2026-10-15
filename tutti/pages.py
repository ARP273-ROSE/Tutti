"""Travail page par page sur un PDF : remanier (pivoter, retirer, déplacer)
et finitions (numéros de page, texte en tête, allègement pour l'e-mail).

Comme `moteur`, ce module ne connaît pas Qt : la fenêtre l'appelle depuis un
fil de fond. Le document d'origine n'est jamais modifié ; le résultat est
écrit à part, d'un seul coup (`moteur._ecrire_atomique`).

Choix techniques
----------------
* **Pivoter** ne touche pas au contenu : on change l'attribut /Rotate de la
  page, comme le fait un lecteur PDF. Aucune perte, aucun recalcul.
* **Numéros et texte** sont ajoutés par-dessus la page dans la police
  Helvetica, que tout lecteur PDF fournit (aucune police embarquée : le
  fichier ne grossit que de quelques octets par page). La position tient
  compte de la rotation de la page : un numéro « en bas » est en bas de la
  page telle qu'on la voit, même sur une page tournée.
* **Alléger** ne réduit que les images plus fines que nécessaire à l'écran ou
  à l'impression de bureau (150 points par pouce sur la page entière) et les
  ré-enregistre en JPEG. Le texte, les portées et les vecteurs ne bougent
  pas ; une image noir et blanc (partition scannée en 1 bit) est déjà
  compacte et reste intacte.
"""
from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from . import conversion
from .conversion import ErreurConversion, type_fichier
from .i18n import tr
from .moteur import AssemblageAnnule, ErreurTutti, _ecrire_atomique, _meme_fichier

# ----------------------------------------------------------------- ouverture


def ouvrir(source: Path, dossier_conversions: Path | None = None):
    """Ouvre `source` avec pikepdf, après conversion si ce n'est pas un PDF.

    Renvoie (pdf, chemin réellement lu). Lève ErreurTutti avec un message
    sans chemin complet (celui de qpdf en contient un)."""
    import pikepdf

    source = Path(source)
    lire = source
    if type_fichier(source) not in (None, "pdf"):
        try:
            lire = conversion.convertir(
                source, Path(dossier_conversions or tempfile.mkdtemp(prefix="tutti-conv-")))
        except ErreurConversion as e:
            raise ErreurTutti(tr("err.conversion_nom", nom=source.name, detail=e))
    try:
        return pikepdf.open(lire), lire
    except pikepdf.PasswordError:
        raise ErreurTutti(tr("err.lecture_mdp", nom=source.name))
    except pikepdf.PdfError:
        raise ErreurTutti(tr("err.lecture_illisible", nom=source.name))
    except OSError as e:
        raise ErreurTutti(tr("err.lecture_acces", nom=source.name,
                             detail=e.strerror or type(e).__name__))


def _verifier_sortie(sortie: Path, *sources: Path) -> None:
    if sortie.suffix.lower() != ".pdf":
        raise ErreurTutti(tr("err.extension"))
    for s in sources:
        if s is not None and _meme_fichier(sortie, Path(s)):
            raise ErreurTutti(tr("err.ecrase_source", nom=Path(s).name))
    if not sortie.parent.is_dir():
        raise ErreurTutti(tr("err.dossier_absent", dossier=sortie.parent))


def _herite(page_obj, cle: str):
    """Attribut de page éventuellement hérité d'un nœud parent (/Rotate,
    /MediaBox, /CropBox peuvent n'être écrits qu'une fois pour tout l'arbre)."""
    noeud, garde = page_obj, 0
    while noeud is not None and garde < 64:
        if cle in noeud:
            return noeud[cle]
        noeud = noeud.get("/Parent")
        garde += 1
    return None


def rotation(page) -> int:
    """Rotation affichée de la page : 0, 90, 180 ou 270."""
    valeur = _herite(page.obj, "/Rotate")
    try:
        return int(valeur) % 360 if valeur is not None else 0
    except (TypeError, ValueError):
        return 0


def _boite(page) -> tuple[float, float, float, float]:
    """Zone visible de la page (CropBox, à défaut MediaBox), normalisée."""
    b = _herite(page.obj, "/CropBox") or _herite(page.obj, "/MediaBox")
    x0, y0, x1, y1 = (float(v) for v in b) if b is not None else (0, 0, 595.2756, 841.8898)
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


# ----------------------------------------------------------------- remanier

def remanier(source: Path, sortie: Path, pages: Sequence[tuple[int, int]], *,
             original: Path | None = None) -> int:
    """Écrit `sortie` avec les pages de `source` dans l'ordre donné.

    `pages` : liste de (numéro de page dès 0, quart de tour ajouté en degrés,
    multiple de 90, positif dans le sens des aiguilles d'une montre). Une page
    absente de la liste est retirée. `original` est le document dont `source`
    est la conversion : on refuse aussi de l'écraser. Renvoie le nombre de pages.
    """
    import pikepdf

    from .moteur import _copier_pages

    source, sortie = Path(source), Path(sortie)
    _verifier_sortie(sortie, source, original)
    if not pages:
        raise ErreurTutti(tr("pages.aucune"))
    pdf, _ = ouvrir(source)
    resultat = pikepdf.new()
    try:
        nb = len(pdf.pages)
        for i, _quart in pages:
            if not 0 <= i < nb:
                raise ErreurTutti(tr("decoupe.hors_limites", plage=str(i + 1), n=nb))
        # Recopie en un seul passage (liens internes et formulaires gardés),
        # dans l'ordre voulu ; une page demandée deux fois est copiée deux fois.
        _copier_pages(resultat, pdf, [i for i, _ in pages])
        for page, (_i, quart) in zip(resultat.pages, pages):
            if quart % 360:
                page.obj.Rotate = (rotation(page) + quart) % 360
        resultat.docinfo["/Title"] = sortie.stem
        resultat.docinfo["/Producer"] = "Tutti (pikepdf/qpdf)"
        n = len(resultat.pages)
        _ecrire_atomique(resultat, sortie)
        return n
    finally:
        resultat.close()
        pdf.close()


# ----------------------------------------------------------------- finitions

#: Positions des numéros. « Extérieur » : à droite sur les pages impaires, à
#: gauche sur les paires — le bord libre d'un recto-verso relié.
POSITIONS = ("bas_centre", "bas_exterieur", "haut_exterieur")
FORMATS = ("n", "n_sur_total")


@dataclass
class Finitions:
    numeros: str = ""              # "" (aucun) ou l'une des POSITIONS
    format_numero: str = "n"       # "n" → « 3 » ; "n_sur_total" → « 3 / 12 »
    premier: int = 1               # numéro de la première page
    sauter_premiere: bool = False  # pas de numéro sur la page de titre (elle compte)
    texte: str = ""                # texte en haut au centre
    texte_partout: bool = True     # sur toutes les pages, sinon la première seule
    alleger: bool = False          # images réduites pour l'e-mail

    @property
    def rien(self) -> bool:
        return not self.numeros and not self.texte.strip() and not self.alleger


MARGE = 20.0            # points (≈ 7 mm) entre le texte et le bord : au-delà des marges
                        # non imprimables (4 à 5 mm), en deçà de la première portée
TAILLE_NUMERO = 10.0
TAILLE_TEXTE = 10.0

# Chasses de la police Helvetica (Adobe, en millièmes de corps) pour les octets
# 32 à 255 de l'encodage WinAnsi : de quoi centrer un texte sans embarquer de
# police. 0 = case vide de l'encodage.
_CHASSES = [int(v) for v in (
    "278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,"
    "556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,"
    "556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,"
    "556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,"
    "500,500,500,334,260,334,584,556,556,0,222,556,333,1000,556,556,333,1000,667,333,1000,0,"
    "611,0,0,222,222,333,333,350,556,1000,333,1000,500,333,944,0,500,667,278,333,556,556,556,"
    "556,260,556,333,737,370,556,584,333,737,333,400,584,333,333,333,556,537,278,333,333,365,"
    "556,834,834,834,611,667,667,667,667,667,667,1000,722,667,667,667,667,278,278,278,278,722,"
    "722,778,778,778,778,778,584,778,722,722,722,722,667,667,611,556,556,556,556,556,556,889,"
    "500,556,556,556,556,278,278,278,278,556,556,556,556,556,556,556,584,611,556,556,556,556,"
    "500,556,500").split(",")]


def encoder(texte: str) -> bytes:
    """Texte → octets WinAnsi ; un caractère hors de l'encodage devient « ? »."""
    texte = " ".join(texte.split())               # pas de saut de ligne dans un en-tête
    return texte.encode("cp1252", errors="replace")


def largeur_texte(octets: bytes, taille: float) -> float:
    return sum(_CHASSES[b - 32] if b >= 32 else 0 for b in octets) * taille / 1000.0


def texte_numero(n: int, total: int, fmt: str) -> str:
    return f"{n} / {total}" if fmt == "n_sur_total" else str(n)


def _vers_page(page) -> tuple[float, float, float, float, float, float, float, float]:
    """Repère de la page TELLE QU'ON LA VOIT → espace de la page.

    Renvoie (a, b, c, d, e, f, largeur visible, hauteur visible) : le point
    (u, v) vu à l'écran (u vers la droite, v vers le haut, depuis le coin bas
    gauche) est en (a·u + c·v + e, b·u + d·v + f) dans la page.
    """
    x0, y0, x1, y1 = _boite(page)
    w, h = x1 - x0, y1 - y0
    r = rotation(page)
    if r == 90:            # affichée tournée d'un quart de tour horaire
        return 0, 1, -1, 0, x1, y0, h, w
    if r == 180:
        return -1, 0, 0, -1, x1, y1, w, h
    if r == 270:
        return 0, -1, 1, 0, x0, y1, h, w
    return 1, 0, 0, 1, x0, y0, w, h


def _ecrire(page, police: str, octets: bytes, taille: float, u: float, v: float) -> bytes:
    a, b, c, d, e, f, _, _ = _vers_page(page)
    tx, ty = a * u + c * v + e, b * u + d * v + f
    return (f"q 0 g BT /{police} {taille:g} Tf {a:g} {b:g} {c:g} {d:g} {tx:.2f} {ty:.2f} Tm "
            f"<{octets.hex()}> Tj ET Q\n").encode("ascii")


def marquer(pdf, finitions: Finitions,
            progression: Callable[[int, int], None] | None = None,
            annule: Callable[[], bool] | None = None) -> None:
    """Ajoute numéros et texte en tête à chaque page de `pdf` (modifié en place)."""
    import pikepdf

    texte = encoder(finitions.texte) if finitions.texte.strip() else b""
    if not finitions.numeros and not texte:
        return
    police_obj = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
        BaseFont=pikepdf.Name.Helvetica, Encoding=pikepdf.Name.WinAnsiEncoding))
    nb = len(pdf.pages)
    total = finitions.premier + nb - 1
    for i, page in enumerate(pdf.pages):
        if annule and annule():
            raise AssemblageAnnule(tr("err.annule"))
        *_m, largeur, hauteur = _vers_page(page)
        ajout = b""
        police = None

        def nom_police():
            nonlocal police
            if police is None:
                police = str(page.add_resource(police_obj, pikepdf.Name.Font,
                                               prefix="TuttiF"))[1:]
            return police

        if finitions.numeros and not (finitions.sauter_premiere and i == 0):
            o = encoder(texte_numero(finitions.premier + i, total, finitions.format_numero))
            lw = largeur_texte(o, TAILLE_NUMERO)
            impaire = (finitions.premier + i) % 2 == 1
            if finitions.numeros == "bas_centre":
                u, v = (largeur - lw) / 2, MARGE
            else:
                u = largeur - MARGE - lw if impaire else MARGE
                v = MARGE if finitions.numeros == "bas_exterieur" else hauteur - MARGE - TAILLE_NUMERO * 0.72
            ajout += _ecrire(page, nom_police(), o, TAILLE_NUMERO, u, v)
        if texte and (finitions.texte_partout or i == 0):
            lw = largeur_texte(texte, TAILLE_TEXTE)
            u = max(MARGE, (largeur - lw) / 2)
            v = hauteur - MARGE - TAILLE_TEXTE * 0.72
            ajout += _ecrire(page, nom_police(), texte, TAILLE_TEXTE, u, v)
        if ajout:
            # Le contenu d'origine est isolé (q … Q) : un état graphique laissé
            # modifié par la page (échelle, couleur) ne déplace pas nos ajouts.
            page.contents_add(pikepdf.Stream(pdf, b"q\n"), prepend=True)
            page.contents_add(pikepdf.Stream(pdf, b"Q\n" + ajout))
        if progression:
            progression(i + 1, nb)


# ----------------------------------------------------------------- alléger

DPI_LEGER = 150
QUALITE_JPEG = 80


def alleger(pdf, dpi: int = DPI_LEGER, qualite: int = QUALITE_JPEG,
            annule: Callable[[], bool] | None = None) -> int:
    """Réduit les images trop fines pour l'usage courant. Renvoie le nombre
    d'images réduites. Une image n'est remplacée que si le résultat est plus
    petit ; en cas de doute (masque, couleurs CMJN, palette…), on n'y touche pas.
    """
    import pikepdf
    from PIL import Image

    if not len(pdf.pages):
        return 0
    # Dimension maximale utile : la plus grande page du document, en pouces,
    # fois la finesse visée. Une image qui couvre la page entière garde donc
    # ses 150 points par pouce ; une petite image n'est jamais agrandie.
    pouces = max(max(_boite(p)[2] - _boite(p)[0], _boite(p)[3] - _boite(p)[1])
                 for p in pdf.pages) / 72.0
    limite = max(300, int(pouces * dpi))
    masques = set()
    for obj in pdf.objects:
        if isinstance(obj, pikepdf.Stream) and obj.get("/SMask") is not None:
            try:
                masques.add(obj.SMask.objgen)
            except Exception:
                pass
    faites = 0
    for obj in list(pdf.objects):
        if annule and annule():
            raise AssemblageAnnule(tr("err.annule"))
        if not isinstance(obj, pikepdf.Stream) or obj.get("/Subtype") != pikepdf.Name.Image:
            continue
        if obj.objgen in masques or obj.get("/ImageMask") or "/Mask" in obj or "/Decode" in obj:
            continue
        if int(obj.get("/BitsPerComponent", 0)) != 8:
            continue
        try:
            largeur, hauteur = int(obj.Width), int(obj.Height)
        except Exception:
            continue
        if max(largeur, hauteur) <= limite * 1.1:
            continue                       # déjà raisonnable : ne pas re-compresser
        filtres = obj.get("/Filter")
        filtres = list(filtres) if isinstance(filtres, pikepdf.Array) else [filtres]
        if any(f not in (None, pikepdf.Name.DCTDecode, pikepdf.Name.FlateDecode,
                         pikepdf.Name.LZWDecode) for f in filtres):
            continue                       # JBIG2, CCITT, JPEG 2000 : on laisse
        try:
            image = pikepdf.PdfImage(obj).as_pil_image()
        except Exception:
            continue
        if image.mode not in ("L", "RGB"):
            continue
        espace = obj.get("/ColorSpace")
        if image.mode == "RGB" and espace not in (pikepdf.Name.DeviceRGB, None) \
                and not (isinstance(espace, pikepdf.Array) and espace[0] == pikepdf.Name.ICCBased):
            continue
        echelle = limite / max(largeur, hauteur)
        taille = (max(1, round(largeur * echelle)), max(1, round(hauteur * echelle)))
        image = image.resize(taille, Image.Resampling.LANCZOS)
        tampon = io.BytesIO()
        image.save(tampon, format="JPEG", quality=qualite, optimize=True)
        donnees = tampon.getvalue()
        if len(donnees) >= len(obj.read_raw_bytes()):
            continue
        obj.write(donnees, filter=pikepdf.Name.DCTDecode)
        obj.Width, obj.Height = taille
        obj.BitsPerComponent = 8
        if "/DecodeParms" in obj:
            del obj["/DecodeParms"]
        faites += 1
    return faites


# ----------------------------------------------------------------- tout ensemble

@dataclass
class Bilan:
    pages: int
    taille_avant: int
    taille_apres: int
    images_reduites: int = 0


def finir(source: Path, sortie: Path, finitions: Finitions, *,
          original: Path | None = None,
          progression: Callable[[int, int, str], None] | None = None,
          annule: Callable[[], bool] | None = None) -> Bilan:
    """Applique les finitions à `source` et écrit `sortie`."""
    source, sortie = Path(source), Path(sortie)
    nom = (original or source).name
    _verifier_sortie(sortie, source, original)
    if finitions.rien:
        raise ErreurTutti(tr("finir.rien"))
    try:
        avant = Path(original or source).stat().st_size
    except OSError:
        avant = 0
    pdf, _ = ouvrir(source)
    try:
        nb = len(pdf.pages)
        if not nb:
            raise ErreurTutti(tr("err.aucune_page"))
        etapes = nb + (1 if finitions.alleger else 0) + 1
        if progression:
            progression(0, etapes, nom)
        marquer(pdf, finitions, annule=annule,
                progression=lambda f, t: progression and progression(f, etapes, nom))
        reduites = 0
        if finitions.alleger:
            reduites = alleger(pdf, annule=annule)
            try:
                pdf.remove_unreferenced_resources()
            except Exception:
                pass
            if progression:
                progression(nb + 1, etapes, nom)
        if annule and annule():
            raise AssemblageAnnule(tr("err.annule"))
        pdf.docinfo["/Producer"] = "Tutti (pikepdf/qpdf)"
        _ecrire_atomique(pdf, sortie)
        if progression:
            progression(etapes, etapes, sortie.name)
        return Bilan(nb, avant, sortie.stat().st_size, reduites)
    finally:
        pdf.close()


def nom_finitions(source: Path) -> str:
    return f"{Path(source).stem} - {tr('nom.finitions')}.pdf"


def nom_remanie(source: Path) -> str:
    return f"{Path(source).stem} - {tr('nom.remanie')}.pdf"
