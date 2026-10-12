"""Conversion en PDF des images et des documents bureautiques.

* **Images** (JPEG, PNG, TIFF, BMP, GIF, WebP) : img2pdf. Un JPEG est inséré
  tel quel dans le PDF, sans être recompressé — aucune perte de qualité. Les
  autres formats sont recodés sans perte. La page prend le format A4, dans
  l'orientation de l'image, et l'image y est centrée sans être déformée.
* **Documents** (Word, Excel, PowerPoint, OpenDocument, RTF) : il faut un
  logiciel de bureautique pour les mettre en page. Sous Windows, Tutti pilote
  **Microsoft Office** s'il est installé ; sinon, ou sur macOS et Linux, il
  utilise **LibreOffice** (gratuit). Les macros sont désactivées pendant la
  conversion, les documents sont ouverts en lecture seule.

Sécurité : aucune commande n'est passée par un interpréteur (pas de shell),
LibreOffice reçoit un profil jetable, et chaque conversion a une durée limite.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .i18n import tr

EXT_PDF = {".pdf"}
EXT_IMAGES = {".jpg", ".jpeg", ".jpe", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
EXT_WORD = {".doc", ".docx", ".docm", ".odt", ".rtf"}
EXT_EXCEL = {".xls", ".xlsx", ".xlsm", ".ods"}
EXT_POWERPOINT = {".ppt", ".pptx", ".pptm", ".pps", ".ppsx", ".odp"}
EXT_OFFICE = EXT_WORD | EXT_EXCEL | EXT_POWERPOINT
EXT_ACCEPTEES = EXT_PDF | EXT_IMAGES | EXT_OFFICE

DUREE_MAX = 180          # secondes par document bureautique

# Office et LibreOffice n'aiment pas convertir deux documents à la fois :
# les conversions bureautiques passent une par une.
_verrou_office = threading.Lock()


class ErreurConversion(Exception):
    """Message déjà traduit, présentable tel quel."""


def type_fichier(chemin: Path) -> str | None:
    ext = Path(chemin).suffix.lower()
    if ext in EXT_PDF:
        return "pdf"
    if ext in EXT_IMAGES:
        return "image"
    if ext in EXT_OFFICE:
        return "office"
    return None


def convertir(source: Path, dossier: Path) -> Path:
    """Convertit `source` en PDF dans `dossier` et renvoie le chemin produit."""
    source = Path(source)
    genre = type_fichier(source)
    dossier.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="conv-", suffix=".pdf", dir=dossier)
    os.close(fd)
    dest = Path(tmp)
    try:
        if genre == "image":
            image_vers_pdf(source, dest)
        elif genre == "office":
            office_vers_pdf(source, dest)
        else:
            raise ErreurConversion(tr("conv.format", ext=source.suffix or "?"))
        if not dest.exists() or dest.stat().st_size == 0:
            raise ErreurConversion(tr("conv.vide"))
        return dest
    except Exception:
        try:
            dest.unlink()
        except OSError:
            pass
        raise


# ----------------------------------------------------------------- images

A4 = (595.2756, 841.8898)          # points


def image_vers_pdf(source: Path, dest: Path) -> None:
    import img2pdf
    from PIL import Image, ImageOps

    def mise_en_page(largeur_img, hauteur_img, ndpi):
        portrait = hauteur_img >= largeur_img
        page = A4 if portrait else (A4[1], A4[0])
        return img2pdf.get_layout_fun(
            pagesize=page, fit=img2pdf.FitMode.into, auto_orient=False)(
                largeur_img, hauteur_img, ndpi)

    try:
        with open(source, "rb") as f:
            donnees = f.read()
        try:
            pdf = img2pdf.convert(donnees, layout_fun=mise_en_page,
                                  rotation=img2pdf.Rotation.ifvalid)
        except (img2pdf.AlphaChannelError, img2pdf.ImageOpenError, ValueError, Exception):
            # Transparence (PNG), palette exotique, WebP… : on recode l'image
            # en RVB sans perte (PNG) puis on recommence.
            with Image.open(source) as im:
                im = ImageOps.exif_transpose(im)
                pages = []
                for i in range(getattr(im, "n_frames", 1)):
                    im.seek(i)
                    fond = Image.new("RGB", im.size, "white")
                    rgba = im.convert("RGBA")
                    fond.paste(rgba, mask=rgba.split()[3])
                    tmp = tempfile.SpooledTemporaryFile()
                    fond.save(tmp, format="PNG")
                    tmp.seek(0)
                    pages.append(tmp.read())
            pdf = img2pdf.convert(pages, layout_fun=mise_en_page)
        dest.write_bytes(pdf)
    except ErreurConversion:
        raise
    except Exception as e:
        raise ErreurConversion(tr("conv.image", detail=type(e).__name__))


# ----------------------------------------------------------------- bureautique

def office_vers_pdf(source: Path, dest: Path) -> None:
    with _verrou_office:
        erreurs = []
        if sys.platform == "win32":
            try:
                _par_microsoft_office(source, dest)
                return
            except ErreurConversion:
                raise
            except Exception as e:           # Office absent ou refus : on tente LibreOffice
                erreurs.append(type(e).__name__)
        soffice = trouver_libreoffice()
        if soffice:
            _par_libreoffice(soffice, source, dest)
            return
        raise ErreurConversion(tr("conv.pas_de_suite"))


def trouver_libreoffice() -> str | None:
    """Chemin de soffice, ou None. On ne cherche qu'aux emplacements connus."""
    candidats = []
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            candidats.append(Path(base) / "LibreOffice" / "program" / "soffice.exe")
    elif sys.platform == "darwin":
        candidats += [Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
                      Path.home() / "Applications/LibreOffice.app/Contents/MacOS/soffice"]
    for c in candidats:
        if c.is_file():
            return str(c)
    for nom in ("soffice", "libreoffice"):
        trouve = shutil.which(nom)
        if trouve:
            return trouve
    return None


def _par_libreoffice(soffice: str, source: Path, dest: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="tutti-lo-") as tmp:
        profil = Path(tmp) / "profil"
        sortie = Path(tmp) / "sortie"
        sortie.mkdir()
        commande = [soffice, f"-env:UserInstallation={profil.as_uri()}",
                    "--headless", "--norestore", "--nolockcheck", "--nodefault",
                    "--convert-to", "pdf", "--outdir", str(sortie), str(source)]
        options = {}
        if sys.platform == "win32":
            options["creationflags"] = 0x08000000      # CREATE_NO_WINDOW
        try:
            subprocess.run(commande, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=DUREE_MAX, check=False, **options)
        except subprocess.TimeoutExpired:
            raise ErreurConversion(tr("conv.trop_long", s=DUREE_MAX))
        produit = sortie / (source.stem + ".pdf")
        if not produit.exists():
            raise ErreurConversion(tr("conv.echec", logiciel="LibreOffice"))
        shutil.move(str(produit), str(dest))


def _par_microsoft_office(source: Path, dest: Path) -> None:
    """Conversion par Word, Excel ou PowerPoint, invisibles, macros coupées."""
    import comtypes
    import comtypes.client

    ext = source.suffix.lower()
    src, out = str(source.resolve()), str(dest.resolve())
    comtypes.CoInitialize()
    try:
        if ext in EXT_WORD:
            app = comtypes.client.CreateObject("Word.Application")
            try:
                app.Visible = False
                app.DisplayAlerts = 0
                app.AutomationSecurity = 3              # msoAutomationSecurityForceDisable
                doc = app.Documents.Open(src, False, True, False)  # ConfirmConversions, ReadOnly, AddToRecentFiles
                try:
                    doc.ExportAsFixedFormat(out, 17)    # wdExportFormatPDF
                finally:
                    doc.Close(0)                        # wdDoNotSaveChanges
            finally:
                app.Quit()
        elif ext in EXT_EXCEL:
            app = comtypes.client.CreateObject("Excel.Application")
            try:
                app.Visible = False
                app.DisplayAlerts = False
                app.AutomationSecurity = 3
                classeur = app.Workbooks.Open(src, 0, True)   # UpdateLinks, ReadOnly
                try:
                    classeur.ExportAsFixedFormat(0, out)       # xlTypePDF
                finally:
                    classeur.Close(False)
            finally:
                app.Quit()
        elif ext in EXT_POWERPOINT:
            app = comtypes.client.CreateObject("PowerPoint.Application")
            try:
                app.AutomationSecurity = 3
                pres = app.Presentations.Open(src, True, False, False)  # ReadOnly, Untitled, WithWindow
                try:
                    pres.SaveAs(out, 32)                # ppSaveAsPDF
                finally:
                    pres.Close()
            finally:
                app.Quit()
        else:
            raise ErreurConversion(tr("conv.format", ext=ext))
    finally:
        comtypes.CoUninitialize()
    if not dest.exists() or dest.stat().st_size == 0:
        raise ErreurConversion(tr("conv.echec", logiciel="Microsoft Office"))
