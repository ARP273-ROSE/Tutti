"""Moteur de Tutti : analyse et assemblage de PDF, sans aucune interface.

Tout ce qui touche aux fichiers vit ici, pour être testé sans écran. La
fenêtre ne fait qu'appeler ces fonctions depuis un fil de fond.

Choix techniques
----------------
* **pikepdf / qpdf** plutôt qu'un assembleur en Python pur : qpdf est écrit en
  C++, recopie les pages telles quelles (polices, images et vecteurs intacts,
  aucune « réimpression ») et sait relire un fichier légèrement abîmé. Aucune
  dépendance à Ghostscript.
* **Parallélisme là où il sert** : l'analyse (ouvrir chaque fichier, compter
  ses pages, détecter un mot de passe) est indépendante d'un fichier à l'autre
  et se répartit sur les cœurs, en processus séparés, dès que le lot est assez
  gros pour amortir leur démarrage. L'écriture du fichier final, elle, est un
  flux unique : la paralléliser n'aurait pas de sens.
* **Sécurité** : on n'écrit jamais dans un fichier source ; le résultat est
  d'abord écrit dans un fichier temporaire du même dossier, puis mis en place
  d'un seul coup (os.replace) — une coupure de courant ne laisse jamais un PDF
  à moitié écrit sous le nom final. Aucun accès réseau, aucune commande
  système, aucun JavaScript exécuté.
"""
from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

from . import conversion
from .conversion import ErreurConversion, type_fichier
from .i18n import tr

# En dessous de ces seuils, démarrer des processus coûte plus cher (≈ 0,2 s
# chacun sous Windows, le temps d'importer pikepdf) que l'analyse elle-même.
SEUIL_FICHIERS_PARALLELE = 12
SEUIL_OCTETS_PARALLELE = 64 * 1024 * 1024

# umask lu une fois au chargement : le relire plus tard (os.umask) le
# modifierait un instant pour tout le processus, fils de travail compris.
_UMASK = os.umask(0o022)
os.umask(_UMASK)

EXTENSIONS = conversion.EXT_ACCEPTEES   # PDF, images, Word, Excel, PowerPoint…


class ErreurTutti(Exception):
    """Erreur présentable telle quelle à l'utilisateur (message déjà traduit)."""


class AssemblageAnnule(ErreurTutti):
    """L'utilisateur a interrompu l'assemblage : rien n'a été écrit."""


@dataclass
class InfoPdf:
    """Ce qu'on sait d'un fichier source après analyse."""
    chemin: Path
    pages: int = 0
    taille: int = 0
    code: str = ""              # vide = fichier utilisable ; sinon clé « err.<code> »
    detail: str = ""
    chiffre: bool = False       # chiffré sans mot de passe (droits seulement)
    largeur: float = 0.0        # format de la dernière page, en points
    hauteur: float = 0.0
    genre: str = "pdf"          # pdf, image ou office
    pdf: Path | None = None     # PDF à assembler : le fichier lui-même, ou sa conversion

    @property
    def erreur(self) -> str:
        """Message dans la langue de l'interface — traduit à la lecture, pas à
        l'analyse : celle-ci tourne parfois dans un autre processus."""
        return tr(f"err.{self.code}", detail=self.detail) if self.code else ""

    @property
    def utilisable(self) -> bool:
        return not self.code and self.pages > 0


@dataclass
class Options:
    signets: bool = True            # un signet par fichier source
    recto: bool = False             # chaque fichier commence sur une page impaire
    livret: bool = False            # imposition en livret A5 à plier et agrafer
    titres_signets: dict = field(default_factory=dict)  # chemin -> titre imposé


# ----------------------------------------------------------------- noms

def cle_naturelle(texte: str):
    """Clé de tri « naturel » : 2 < 10, accents et casse ignorés.

    « Partie 2 » passe avant « Partie 10 », comme on l'attend, alors qu'un tri
    alphabétique brut les inverserait.
    """
    sans_accents = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    morceaux = re.split(r"(\d+)", sans_accents.casefold())
    return [(0, int(m), "") if m.isdigit() else (1, 0, m) for m in morceaux if m != ""]


def trier(chemins: Iterable[Path]) -> list[Path]:
    return sorted(chemins, key=lambda p: cle_naturelle(p.name))


def _prefixe_commun(noms: Sequence[str]) -> str:
    if not noms:
        return ""
    return os.path.commonprefix(list(noms))


def _nettoyer_fin(texte: str) -> str:
    """Retire les chiffres et séparateurs pendants d'un préfixe commun.

    « Symphonie 5 - 3 » (préfixe de « … - 32 » et « … - 37 ») devient
    « Symphonie 5 » : un numéro coupé en deux n'a aucun sens.
    """
    texte = re.sub(r"\d+$", "", texte)
    return texte.rstrip(" -_.,;:–—(").strip()


def proposer_nom(chemins: Sequence[Path], livret: bool = False) -> str:
    """Nom de fichier proposé pour le résultat, sans le dossier."""
    if livret and chemins:
        base = proposer_nom(chemins)[:-4]
        for fin in (f" - {tr('nom.complet')}",):
            if base.endswith(fin):
                base = base[: -len(fin)]
        return f"{base} - {tr('nom.livret')}.pdf"
    if not chemins:
        return f"{tr('nom.defaut')}.pdf"
    if len(chemins) == 1 and type_fichier(chemins[0]) != "pdf":
        return f"{chemins[0].stem}.pdf"            # simple conversion : même nom, en PDF
    noms = [p.stem for p in chemins]
    base = _nettoyer_fin(_prefixe_commun(noms)) if len(noms) > 1 else noms[0]
    if len(base) < 3:
        base = tr("nom.defaut")
    return f"{base} - {tr('nom.complet')}.pdf"


def titre_signet(chemin: Path, tous: Sequence[Path]) -> str:
    """Titre du signet : le nom du fichier sans la partie commune à tous.

    « Symphonie 5 - 34 Violon II » devient « 34 Violon II ».
    """
    nom = chemin.stem
    if len(tous) > 1:
        prefixe = _nettoyer_fin(_prefixe_commun([p.stem for p in tous]))
        if prefixe and nom.startswith(prefixe):
            reste = nom[len(prefixe):].lstrip(" -_.,;:–—").strip()
            if reste:
                return reste
    return nom


def lister_pdf(elements: Iterable[str | Path], extensions=None) -> list[Path]:
    """Fichiers acceptés (PDF, images, documents) parmi des fichiers et dossiers.

    Un dossier apporte ses PDF directs (pas ses sous-dossiers : glisser un
    dossier de projet ne doit pas aspirer des années d'archives), triés
    naturellement. Les doublons sont écartés, l'ordre d'arrivée conservé.
    """
    vus: set[str] = set()
    sortie: list[Path] = []

    def ajouter(p: Path) -> None:
        cle = os.path.normcase(str(p.resolve()))
        if cle not in vus:
            vus.add(cle)
            sortie.append(p)

    for e in elements:
        p = Path(e)
        if p.is_dir():
            for f in trier(x for x in p.iterdir()
                           if x.is_file() and x.suffix.lower() in (extensions or EXTENSIONS)):
                ajouter(f)
        elif p.is_file() and p.suffix.lower() in (extensions or EXTENSIONS):
            ajouter(p)
    return sortie


# ----------------------------------------------------------------- analyse

def analyser(chemin: str | Path, dossier_conversions: str | Path | None = None) -> InfoPdf:
    """Ouvre un fichier et relève ce qu'il faut pour l'afficher et l'assembler.

    Une image ou un document bureautique est d'abord converti en PDF dans
    `dossier_conversions` ; l'assemblage relira cette conversion.
    Ne lève jamais : une erreur devient un message dans `InfoPdf.erreur`, pour
    qu'un fichier défectueux n'empêche pas d'analyser les autres.
    """
    import pikepdf

    p = Path(chemin)
    info = InfoPdf(chemin=p, genre=type_fichier(p) or "pdf")
    try:
        info.taille = p.stat().st_size
    except OSError as e:
        info.code, info.detail = "inaccessible", e.strerror or type(e).__name__
        return info
    lire = p
    if info.genre != "pdf":
        try:
            dossier = Path(dossier_conversions or tempfile.mkdtemp(prefix="tutti-conv-"))
            lire = conversion.convertir(p, dossier)
        except ErreurConversion as e:
            info.code, info.detail = "conversion", str(e)
            return info
        except Exception as e:
            info.code, info.detail = "conversion", type(e).__name__
            return info
    info.pdf = lire
    try:
        with pikepdf.open(lire) as pdf:
            info.pages = len(pdf.pages)
            info.chiffre = bool(pdf.is_encrypted)
            if info.pages:
                boite = pdf.pages[-1].mediabox
                info.largeur = float(abs(boite[2] - boite[0]))
                info.hauteur = float(abs(boite[3] - boite[1]))
            else:
                info.code = "vide"
    except pikepdf.PasswordError:
        info.code = "motdepasse"
    except pikepdf.PdfError:
        # Le détail de qpdf contient le chemin complet du fichier : inutile à
        # l'utilisateur, et indiscret dans un rapport d'incident.
        info.code = "illisible"
    except OSError as e:
        info.code, info.detail = "inaccessible", e.strerror or type(e).__name__
    except Exception as e:                      # filet : jamais d'exception vers l'appelant
        info.code, info.detail = "inattendue", type(e).__name__
    return info


def _court(e: BaseException, n: int = 120) -> str:
    texte = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    return texte if len(texte) <= n else texte[: n - 1] + "…"


def analyser_tous(chemins: Sequence[Path], *, processus: int | None = None,
                  rappel: Callable[[InfoPdf], None] | None = None,
                  dossier_conversions: str | Path | None = None) -> list[InfoPdf]:
    """Analyse un lot, en parallèle sur plusieurs cœurs si le lot le justifie.

    `rappel` est appelé à chaque fichier terminé (dans le fil appelant), pour
    afficher l'avancement. L'ordre du résultat est celui de `chemins`.
    """
    chemins = list(chemins)
    if not chemins:
        return []
    # Images et documents passent par des fils, jamais par des processus :
    # Office se pilote depuis le processus qui l'a lancé, et une conversion
    # écrit dans le dossier de la session.
    autres = [i for i, c in enumerate(chemins) if type_fichier(c) not in (None, "pdf")]
    if autres:
        res_autres: dict[int, InfoPdf] = {}
        dossier = dossier_conversions or tempfile.mkdtemp(prefix="tutti-conv-")
        with ThreadPoolExecutor(max_workers=min(4, len(autres))) as pool:
            futurs = {pool.submit(analyser, chemins[i], dossier): i for i in autres}
            for f in as_completed(futurs):
                info = f.result()
                res_autres[futurs[f]] = info
                if rappel:
                    rappel(info)
        reste = [c for i, c in enumerate(chemins) if i not in res_autres]
        infos_pdf = iter(analyser_tous(reste, processus=processus, rappel=rappel))
        return [res_autres[i] if i in res_autres else next(infos_pdf) for i in range(len(chemins))]
    total = 0
    for c in chemins:
        try:
            total += c.stat().st_size
        except OSError:
            pass
    coeurs = processus or os.cpu_count() or 1
    gros_lot = (len(chemins) >= SEUIL_FICHIERS_PARALLELE
                or total >= SEUIL_OCTETS_PARALLELE)
    resultats: dict[int, InfoPdf] = {}

    if gros_lot and coeurs > 1:
        nb = min(coeurs, len(chemins), 16)
        try:
            with ProcessPoolExecutor(max_workers=nb) as pool:
                for i, info in enumerate(pool.map(analyser, chemins, chunksize=2)):
                    resultats[i] = info
                    if rappel:
                        rappel(info)
            return [resultats[i] for i in range(len(chemins))]
        except Exception:
            # Processus indisponibles (environnement restreint, antivirus…) :
            # on retombe sur des fils, plus lents mais toujours corrects.
            resultats.clear()

    with ThreadPoolExecutor(max_workers=min(4, len(chemins))) as pool:
        for i, info in enumerate(pool.map(analyser, chemins)):
            resultats[i] = info
            if rappel:
                rappel(info)
    return [resultats[i] for i in range(len(chemins))]


# ----------------------------------------------------------------- assemblage

def _meme_fichier(a: Path, b: Path) -> bool:
    try:
        if a.exists() and b.exists():
            return os.path.samefile(a, b)
    except OSError:
        pass
    return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


def verifier_sortie(sortie: Path, sources: Sequence[Path]) -> None:
    """Refuse une destination dangereuse avant d'avoir rien écrit."""
    if sortie.suffix.lower() != ".pdf":
        raise ErreurTutti(tr("err.extension"))
    for s in sources:
        if _meme_fichier(sortie, s):
            raise ErreurTutti(tr("err.ecrase_source", nom=s.name))
    if not sortie.parent.is_dir():
        raise ErreurTutti(tr("err.dossier_absent", dossier=sortie.parent))


def assembler(sources: Sequence[Path], sortie: Path, options: Options | None = None, *,
              progression: Callable[[int, int, str], None] | None = None,
              annule: Callable[[], bool] | None = None,
              converties: dict | None = None) -> int:
    """Assemble `sources`, dans cet ordre, en un seul PDF `sortie`.

    Renvoie le nombre de pages du résultat. Lève ErreurTutti avec un message
    clair en cas de problème ; dans ce cas aucun fichier n'est laissé derrière.
    `progression(fait, total, nom)` est appelé à chaque étape ; `annule()`
    permet d'interrompre proprement entre deux fichiers. Une image ou un
    document est lu depuis sa conversion (`converties[str(source)]`), ou
    converti à la volée s'il n'a pas été analysé avant.
    """
    import pikepdf

    options = options or Options()
    sources = [Path(s) for s in sources]
    sortie = Path(sortie)
    if not sources:
        raise ErreurTutti(tr("err.aucun"))
    verifier_sortie(sortie, sources)

    etapes = len(sources) + 1           # + l'écriture finale
    ouverts: list = []                  # les sources doivent rester ouvertes jusqu'à l'écriture
    converties = dict(converties or {})
    temporaire = tempfile.TemporaryDirectory(prefix="tutti-conv-")
    resultat = pikepdf.new()
    debuts: list[tuple[str, int]] = []
    try:
        for n, src in enumerate(sources):
            if annule and annule():
                raise AssemblageAnnule(tr("err.annule"))
            if progression:
                progression(n, etapes, src.name)
            lire = src
            if type_fichier(src) not in (None, "pdf"):
                lire = converties.get(str(src))
                if not lire or not Path(lire).exists():
                    try:
                        lire = conversion.convertir(src, Path(temporaire.name))
                    except ErreurConversion as e:
                        raise ErreurTutti(tr("err.conversion_nom", nom=src.name, detail=e))
            try:
                pdf = pikepdf.open(lire)
            except pikepdf.PasswordError:
                raise ErreurTutti(tr("err.lecture_mdp", nom=src.name))
            except pikepdf.PdfError:
                # Le détail de qpdf contient le chemin complet : on ne le montre pas.
                raise ErreurTutti(tr("err.lecture_illisible", nom=src.name))
            except OSError as e:
                raise ErreurTutti(tr("err.lecture_acces", nom=src.name,
                                     detail=e.strerror or type(e).__name__))
            ouverts.append(pdf)
            if not len(pdf.pages):
                continue
            # Recto : une partie doit commencer sur une page de droite, donc à
            # un numéro impair. Si le total courant est impair, on intercale
            # une page blanche au format de la page précédente.
            if options.recto and len(resultat.pages) % 2 == 1:
                derniere = resultat.pages[-1].mediabox
                resultat.add_blank_page(page_size=(
                    float(abs(derniere[2] - derniere[0])),
                    float(abs(derniere[3] - derniere[1]))))
            debuts.append((options.titres_signets.get(str(src))
                           or titre_signet(src, sources), len(resultat.pages)))
            _copier_pages(resultat, pdf)

        if not len(resultat.pages):
            raise ErreurTutti(tr("err.aucune_page"))

        if options.livret:
            # Imposition : le document lu en livret. Les signets n'auraient
            # plus de sens (deux pages par feuille, dans le désordre).
            livret = imposer_livret(resultat)
            ouverts.append(resultat)
            resultat = livret
        elif options.signets and debuts:
            with resultat.open_outline() as plan:
                plan.root.clear()
                for titre, page in debuts:
                    plan.root.append(pikepdf.OutlineItem(titre, page))
            resultat.Root.PageMode = pikepdf.Name.UseOutlines

        resultat.docinfo["/Title"] = sortie.stem
        resultat.docinfo["/Producer"] = "Tutti (pikepdf/qpdf)"

        if annule and annule():
            raise AssemblageAnnule(tr("err.annule"))
        if progression:
            progression(len(sources), etapes, sortie.name)
        nb_pages = len(resultat.pages)
        _ecrire_atomique(resultat, sortie)
        if progression:
            progression(etapes, etapes, sortie.name)
        return nb_pages
    finally:
        resultat.close()
        for pdf in ouverts:
            try:
                pdf.close()
            except Exception:
                pass
        temporaire.cleanup()


A4_PAYSAGE = (841.8898, 595.2756)


def ordre_livret(nb_pages: int) -> list[tuple[int | None, int | None]]:
    """Ordre des pages d'un livret plié et agrafé au milieu (« piqûre à cheval »).

    Renvoie, face après face (recto puis verso de chaque feuille), le couple
    (page de gauche, page de droite), numérotées dès 0 ; None = page blanche
    ajoutée pour atteindre un multiple de 4. Pour 8 pages : feuille 1 recto
    (8, 1), verso (2, 7) ; feuille 2 recto (6, 3), verso (4, 5).
    """
    total = (nb_pages + 3) // 4 * 4

    def page(i):
        return i if i < nb_pages else None

    faces = []
    for f in range(total // 4):
        faces.append((page(total - 1 - 2 * f), page(2 * f)))         # recto
        faces.append((page(2 * f + 1), page(total - 2 - 2 * f)))     # verso
    return faces


def imposer_livret(source, format_feuille=A4_PAYSAGE):
    """Nouveau PDF : deux pages côte à côte par face de feuille, dans l'ordre
    du livret. Chaque page est réduite (A4 → A5) sans être déformée. À
    imprimer en recto-verso, retournement sur le bord COURT."""
    import pikepdf

    largeur, hauteur = format_feuille
    livret = pikepdf.new()
    for gauche, droite in ordre_livret(len(source.pages)):
        livret.add_blank_page(page_size=(largeur, hauteur))
        face = livret.pages[-1]
        if gauche is not None:
            face.add_overlay(source.pages[gauche], pikepdf.Rectangle(0, 0, largeur / 2, hauteur))
        if droite is not None:
            face.add_overlay(source.pages[droite], pikepdf.Rectangle(largeur / 2, 0, largeur, hauteur))
    return livret


def _copier_pages(dest, src, pages=None) -> None:
    """Recopie des pages en gardant liens internes, signets nommés et champs
    de formulaire (pikepdf ≥ 10) ; à défaut, copie simple des pages."""
    if hasattr(dest, "add_pages_from"):
        dest.add_pages_from(src, pages)
    else:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dest.pages.extend(src.pages if pages is None else [src.pages[i] for i in pages])


def _droits_par_defaut(chemin: Path) -> None:
    """mkstemp crée le fichier en 600 (lisible par son seul propriétaire) :
    on rend au PDF final les droits habituels d'un fichier (umask)."""
    if os.name == "nt":
        return
    try:
        os.chmod(chemin, 0o666 & ~_UMASK)
    except OSError:
        pass


def _ecrire_atomique(pdf, sortie: Path) -> None:
    """Écrit dans un temporaire du même dossier, puis le met en place d'un coup."""
    import pikepdf

    fd, tmp = tempfile.mkstemp(prefix=".tutti-", suffix=".pdf.tmp", dir=sortie.parent)
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        pdf.save(tmp_path,
                 compress_streams=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate,
                 fix_metadata_version=True)
        _droits_par_defaut(tmp_path)
        try:
            os.replace(tmp_path, sortie)
        except PermissionError:
            raise ErreurTutti(tr("err.ouvert_ailleurs", nom=sortie.name))
    except OSError as e:
        if isinstance(e, PermissionError):
            raise ErreurTutti(tr("err.ecriture_refusee", dossier=sortie.parent,
                                 detail=e.strerror or type(e).__name__))
        raise ErreurTutti(tr("err.ecriture", detail=e.strerror or type(e).__name__))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


# ----------------------------------------------------------------- découpage

def lire_plages(texte: str, nb_pages: int) -> list[tuple[int, int]]:
    """« 1-3, 5, 8- » → [(1, 3), (5, 5), (8, nb_pages)]. Pages numérotées dès 1.

    Lève ErreurTutti avec un message clair pour toute saisie incorrecte : un
    découpage silencieusement faux est pire qu'un refus.
    """
    plages: list[tuple[int, int]] = []
    morceaux = [m.strip() for m in re.split(r"[,;]", texte or "") if m.strip()]
    if not morceaux:
        raise ErreurTutti(tr("decoupe.plages_vides"))
    for m in morceaux:
        r = re.fullmatch(r"(\d*)\s*[-–—]\s*(\d*)|(\d+)", m)
        if not r:
            raise ErreurTutti(tr("decoupe.plage_invalide", plage=m))
        if r.group(3):
            a = b = int(r.group(3))
        else:
            if not r.group(1) and not r.group(2):
                raise ErreurTutti(tr("decoupe.plage_invalide", plage=m))
            a = int(r.group(1)) if r.group(1) else 1
            b = int(r.group(2)) if r.group(2) else nb_pages
        if a < 1 or b > nb_pages or a > b:
            raise ErreurTutti(tr("decoupe.hors_limites", plage=m, n=nb_pages))
        plages.append((a, b))
    return plages


def plages_par_page(nb_pages: int) -> list[tuple[int, int]]:
    return [(i, i) for i in range(1, nb_pages + 1)]


def noms_decoupe(source: Path, plages: Sequence[tuple[int, int]], nb_pages: int) -> list[str]:
    """« Partition - page 03.pdf », « Partition - pages 04-06.pdf » : les zéros
    gardent l'ordre dans l'Explorateur (« 10 » après « 09 », pas après « 1 »)."""
    largeur = len(str(nb_pages))
    noms = []
    for a, b in plages:
        if a == b:
            noms.append(f"{source.stem} - {tr('decoupe.page')} {a:0{largeur}d}.pdf")
        else:
            noms.append(f"{source.stem} - {tr('decoupe.pages')} {a:0{largeur}d}-{b:0{largeur}d}.pdf")
    return noms


def _ecrire_extraits(source: str, travaux: list[tuple[int, int, str]]) -> int:
    """Écrit une série d'extraits ; tourne dans un processus séparé si besoin.

    Chaque processus ouvre sa propre copie du document : un objet pikepdf ne
    se partage pas entre processus, et l'ouverture coûte peu devant l'écriture.
    """
    import pikepdf

    faits = 0
    with pikepdf.open(source) as pdf:
        for a, b, cible in travaux:
            extrait = pikepdf.new()
            _copier_pages(extrait, pdf, range(a - 1, b))
            extrait.docinfo["/Title"] = Path(cible).stem
            _ecrire_atomique(extrait, Path(cible))
            extrait.close()
            faits += 1
    return faits


SEUIL_PAGES_PARALLELE = 40


def decouper(source: Path, dossier: Path, plages: Sequence[tuple[int, int]] | None = None, *,
             progression: Callable[[int, int, str], None] | None = None,
             annule: Callable[[], bool] | None = None,
             processus: int | None = None,
             original: Path | None = None) -> list[Path]:
    """Découpe `source` en plusieurs PDF dans `dossier` (créé au besoin).

    Sans `plages`, une page par fichier. Au-delà de quelques dizaines de
    fichiers à écrire, le travail est réparti sur les cœurs du processeur.
    Renvoie la liste des fichiers écrits. Le fichier d'origine n'est jamais
    modifié ; un fichier déjà présent portant le même nom est remplacé (la
    fenêtre demande confirmation avant). `original` est le document dont
    `source` est la conversion (Word, image…) : il donne son nom aux fichiers.
    Un document non PDF passé directement en `source` est converti d'abord.
    """
    import pikepdf

    source = Path(source)
    original = Path(original) if original else source
    temporaire = None
    if type_fichier(source) not in (None, "pdf"):
        temporaire = tempfile.TemporaryDirectory(prefix="tutti-conv-")
        try:
            source = conversion.convertir(source, Path(temporaire.name))
        except ErreurConversion as e:
            temporaire.cleanup()
            raise ErreurTutti(tr("err.conversion_nom", nom=original.name, detail=e))
    try:
        return _decouper_pdf(source, original, dossier, plages, progression=progression,
                             annule=annule, processus=processus)
    finally:
        if temporaire:
            temporaire.cleanup()


def _decouper_pdf(source: Path, original: Path, dossier: Path, plages, *,
                  progression, annule, processus) -> list[Path]:
    import pikepdf

    try:
        with pikepdf.open(source) as pdf:
            nb = len(pdf.pages)
    except pikepdf.PasswordError:
        raise ErreurTutti(tr("err.lecture_mdp", nom=source.name))
    except pikepdf.PdfError:
        raise ErreurTutti(tr("err.lecture_illisible", nom=source.name))
    except OSError as e:
        raise ErreurTutti(tr("err.lecture_acces", nom=source.name,
                             detail=e.strerror or type(e).__name__))
    if nb == 0:
        raise ErreurTutti(tr("err.aucune_page"))
    plages = list(plages) if plages else plages_par_page(nb)
    for a, b in plages:
        if a < 1 or b > nb or a > b:
            raise ErreurTutti(tr("decoupe.hors_limites", plage=f"{a}-{b}", n=nb))
    try:
        dossier.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ErreurTutti(tr("err.ecriture", detail=e.strerror or type(e).__name__))
    cibles = [dossier / n for n in noms_decoupe(original, plages, nb)]
    for c in cibles:
        if _meme_fichier(c, source) or _meme_fichier(c, original):
            raise ErreurTutti(tr("err.ecrase_source", nom=original.name))
    travaux = [(a, b, str(c)) for (a, b), c in zip(plages, cibles)]
    total = len(travaux)
    coeurs = processus or os.cpu_count() or 1

    if total >= SEUIL_PAGES_PARALLELE and coeurs > 1:
        nb_proc = min(coeurs, 16)
        paquets = [travaux[i::nb_proc] for i in range(nb_proc) if travaux[i::nb_proc]]
        fait = 0
        try:
            with ProcessPoolExecutor(max_workers=len(paquets)) as pool:
                futurs = [pool.submit(_ecrire_extraits, str(source), p) for p in paquets]
                for f in as_completed(futurs):
                    fait += f.result()
                    if progression:
                        progression(fait, total, source.name)
            return cibles
        except ErreurTutti:
            raise
        except Exception:
            pass                       # repli : écriture dans ce processus

    for i, travail in enumerate(travaux):
        if annule and annule():
            raise AssemblageAnnule(tr("err.annule"))
        if progression:
            progression(i, total, Path(travail[2]).name)
        _ecrire_extraits(str(source), [travail])
    if progression:
        progression(total, total, source.name)
    return cibles
