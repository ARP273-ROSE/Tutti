"""Textes de Tutti en français et en anglais, langue détectée automatiquement.

Règles (les mêmes que MountMonitor) :
* chaque clé existe dans les deux langues — un test l'exige ;
* les champs de format ({n}, {nom}…) sont les mêmes d'une langue à l'autre,
  sinon le texte lèverait une erreur à l'exécution, chez l'utilisateur ;
* une clé manquante retombe sur l'anglais, puis sur la clé elle-même :
  un texte non traduit est un défaut cosmétique, un bouton vide est une panne.

Ce module ne dépend pas de Qt : le moteur l'utilise aussi.
"""
from __future__ import annotations

import os
import sys

LANGUES = ("fr", "en")
_langue = None


def detecter() -> str:
    """Langue d'AFFICHAGE du système (pas celle des formats de date).

    Windows : GetUserDefaultUILanguage (la locale de format peut être
    britannique chez un francophone, et inversement). macOS : la liste
    AppleLanguages des préférences globales, lue sans lancer de commande.
    Linux : variables d'environnement.
    """
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val and val not in ("C", "POSIX") and not val.startswith("C."):
            return "fr" if val.lower().startswith("fr") else "en"
    if sys.platform == "win32":
        try:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "fr" if (langid & 0x3FF) == 0x0C else "en"
        except Exception:
            pass
    if sys.platform == "darwin":
        try:
            import plistlib
            from pathlib import Path
            chemin = Path.home() / "Library" / "Preferences" / ".GlobalPreferences.plist"
            with open(chemin, "rb") as f:
                langues = plistlib.load(f).get("AppleLanguages") or []
            if langues:
                return "fr" if str(langues[0]).lower().startswith("fr") else "en"
        except Exception:
            pass
    return "en"


def definir_langue(code: str | None) -> str:
    """Fixe la langue ('fr', 'en', ou None/'auto' pour la détection)."""
    global _langue
    _langue = code if code in LANGUES else detecter()
    return _langue


def langue() -> str:
    return _langue or definir_langue(None)


def tr(cle: str, **champs) -> str:
    textes = TEXTES.get(cle)
    if not textes:
        return cle
    modele = textes.get(langue()) or textes.get("en") or cle
    try:
        return modele.format(**champs) if champs else modele
    except (KeyError, IndexError, ValueError):
        return modele


def pluriel(n: int, cle_un: str, cle_plusieurs: str, **champs) -> str:
    return tr(cle_un if n == 1 else cle_plusieurs, n=n, **champs)


TEXTES: dict[str, dict[str, str]] = {
    # ---- fenêtre
    "fenetre.titre": {"fr": "Tutti {version} — assembler des PDF",
                      "en": "Tutti {version} — merge PDF files"},
    "entete.sous_titre": {
        "fr": "Assembler, convertir et découper des PDF — glissez vos fichiers, rangez-les, c'est prêt.",
        "en": "Merge, convert and split PDF files — drop your files, put them in order, done."},
    "liste.vide": {"fr": "Glissez ici vos PDF, images, documents Word, Excel ou PowerPoint\n"
                         "(ou un dossier entier)",
                   "en": "Drop your PDF files, images, Word, Excel or PowerPoint documents here\n"
                         "(or a whole folder)"},
    "onglet.assembler": {"fr": "Assembler et convertir", "en": "Merge and convert"},
    "onglet.decouper": {"fr": "Découper", "en": "Split"},
    "bouton.ajouter_pdf": {"fr": "Ajouter des PDF…", "en": "Add PDF files…"},
    "bouton.decouper": {"fr": "Découper", "en": "Split"},
    "dlg.filtre_tout": {"fr": "Fichiers acceptés", "en": "Supported files"},
    "decoupe.liste_vide": {"fr": "Glissez ici les fichiers à découper\n(PDF, Word, Excel, PowerPoint, images…)",
                           "en": "Drop the files to split here\n(PDF, Word, Excel, PowerPoint, images…)"},
    "decoupe.mode": {"fr": "Découpage", "en": "How to split"},
    "decoupe.une_page": {"fr": "Une page par fichier", "en": "One page per file"},
    "decoupe.par_plages": {"fr": "Par plages de pages :", "en": "By page ranges:"},
    "decoupe.exemple": {"fr": "par exemple : 1-3, 4-6, 7-", "en": "for example: 1-3, 4-6, 7-"},
    "decoupe.destination": {"fr": "Où ranger les fichiers", "en": "Where to save the files"},
    "decoupe.dest_auto": {"fr": "À côté de chaque PDF, dans un dossier « <nom> - pages »",
                          "en": "Next to each PDF, in a “<name> - pages” folder"},
    "decoupe.dest_choisi": {"fr": "Dans ce dossier :", "en": "In this folder:"},
    "decoupe.ouvrir_dossier": {"fr": "Ouvrir le dossier une fois terminé", "en": "Open the folder when done"},
    "decoupe.remplacer": {"fr": "{n} fichier(s) portant le même nom existent déjà et seront remplacés. Continuer ?",
                          "en": "{n} file(s) with the same name already exist and will be replaced. Continue?"},
    "decoupe.fini": {"fr": "Découpage terminé : {n} fichier(s) créé(s).", "en": "Split done: {n} file(s) created."},
    "statut.annule_decoupe": {"fr": "Découpage interrompu : {n} fichier(s) déjà écrits sont conservés.",
                              "en": "Split stopped: {n} file(s) already written were kept."},
    "liste.analyse": {"fr": "analyse…", "en": "reading…"},
    "liste.page": {"fr": "{n} page", "en": "{n} page"},
    "liste.pages": {"fr": "{n} pages", "en": "{n} pages"},
    "taille.ko": {"fr": "{v} Ko", "en": "{v} KB"},
    "taille.mo": {"fr": "{v} Mo", "en": "{v} MB"},
    "bouton.ajouter": {"fr": "Ajouter des fichiers…", "en": "Add files…"},
    "bouton.dossier": {"fr": "Ajouter un dossier…", "en": "Add a folder…"},
    "bouton.monter": {"fr": "▲  Monter", "en": "▲  Move up"},
    "bouton.descendre": {"fr": "▼  Descendre", "en": "▼  Move down"},
    "bouton.trier": {"fr": "Trier par nom", "en": "Sort by name"},
    "bouton.trier.astuce": {"fr": "Tri « naturel » : 2 passe avant 10",
                            "en": "“Natural” order: 2 comes before 10"},
    "bouton.retirer": {"fr": "Retirer", "en": "Remove"},
    "bouton.vider": {"fr": "Tout effacer", "en": "Clear all"},
    "bouton.assembler": {"fr": "Assembler", "en": "Merge"},
    "bouton.annuler": {"fr": "Annuler", "en": "Cancel"},
    "bouton.annulation": {"fr": "Annulation…", "en": "Cancelling…"},
    "bouton.choisir": {"fr": "Choisir…", "en": "Browse…"},
    "options.titre": {"fr": "Options", "en": "Options"},
    "options.signets": {"fr": "Un signet par fichier (pour sauter d'une partie à l'autre dans le PDF)",
                        "en": "One bookmark per file (to jump from part to part in the PDF)"},
    "options.recto": {"fr": "Chaque partie commence sur une page de droite "
                            "(page blanche ajoutée si besoin, pour l'impression recto-verso)",
                      "en": "Start each part on a right-hand page "
                            "(blank page added when needed, for double-sided printing)"},
    "options.ouvrir": {"fr": "Ouvrir le PDF une fois terminé", "en": "Open the PDF when done"},
    "sortie.titre": {"fr": "Fichier final", "en": "Output file"},
    "sortie.nom": {"fr": "Nom :", "en": "Name:"},
    "sortie.dossier": {"fr": "Dossier :", "en": "Folder:"},
    "resume.fichier": {"fr": "{n} fichier, {p} pages", "en": "{n} file, {p} pages"},
    "resume.fichiers": {"fr": "{n} fichiers, {p} pages", "en": "{n} files, {p} pages"},
    "resume.attente": {"fr": " — analyse en cours ({n})…", "en": " — reading ({n})…"},
    "resume.mauvais": {"fr": " — {n} illisible(s), à retirer avant d'assembler",
                       "en": " — {n} unreadable, remove before merging"},
    "statut.ignores": {"fr": "{n} élément(s) ignoré(s) : seuls les PDF sont acceptés.",
                       "en": "{n} item(s) skipped: only PDF files are accepted."},
    "statut.rien": {"fr": "Aucun nouveau PDF à ajouter.", "en": "No new PDF to add."},
    "statut.annule": {"fr": "Assemblage annulé : rien n'a été écrit.",
                      "en": "Merge cancelled: nothing was written."},
    "statut.cree": {"fr": "« {nom} » créé : {p} pages.", "en": "“{nom}” created: {p} pages."},
    "statut.termine": {"fr": "Terminé", "en": "Done"},
    # ---- dialogues
    "dlg.ouvrir_pdf": {"fr": "Choisir les PDF à assembler", "en": "Choose the PDF files to merge"},
    "dlg.ouvrir_dossier": {"fr": "Choisir un dossier de PDF", "en": "Choose a folder of PDF files"},
    "dlg.enregistrer": {"fr": "Enregistrer le PDF assemblé", "en": "Save the merged PDF"},
    "dlg.filtre": {"fr": "Documents PDF (*.pdf)", "en": "PDF documents (*.pdf)"},
    "dlg.remplacer": {"fr": "« {nom} » existe déjà dans ce dossier.\n\nLe remplacer ?",
                      "en": "“{nom}” already exists in this folder.\n\nReplace it?"},
    "dlg.pret": {"fr": "« {nom} » est prêt ({p} pages).", "en": "“{nom}” is ready ({p} pages)."},
    "dlg.ouvrir": {"fr": "Ouvrir le PDF", "en": "Open the PDF"},
    "dlg.ouvrir_dossier_resultat": {"fr": "Ouvrir le dossier", "en": "Open the folder"},
    "dlg.fermer": {"fr": "Fermer", "en": "Close"},
    "dlg.quitter_en_cours": {"fr": "Un assemblage est en cours. L'interrompre et quitter ?",
                             "en": "A merge is in progress. Stop it and quit?"},
    "dlg.oui": {"fr": "Oui", "en": "Yes"},
    "dlg.non": {"fr": "Non", "en": "No"},
    # ---- menus
    "menu.fichier": {"fr": "&Fichier", "en": "&File"},
    "menu.quitter": {"fr": "Quitter", "en": "Quit"},
    "menu.langue": {"fr": "&Langue", "en": "&Language"},
    "menu.langue.auto": {"fr": "Automatique (langue du système)", "en": "Automatic (system language)"},
    "menu.langue.redemarrer": {"fr": "La nouvelle langue s'appliquera au prochain démarrage de Tutti.",
                               "en": "The new language will apply the next time Tutti starts."},
    "menu.aide": {"fr": "&Aide", "en": "&Help"},
    "menu.manuel": {"fr": "Manuel (PDF)", "en": "User guide (PDF)"},
    "menu.mode_emploi": {"fr": "Mode d'emploi rapide", "en": "Quick help"},
    "menu.maj": {"fr": "Rechercher une mise à jour", "en": "Check for updates"},
    "menu.signaler": {"fr": "Signaler un problème…", "en": "Report a problem…"},
    "menu.rapports_auto": {"fr": "Envoi automatique des rapports d'incident",
                           "en": "Send error reports automatically"},
    "menu.a_propos": {"fr": "À propos", "en": "About"},
    "aide.titre": {"fr": "Mode d'emploi", "en": "Quick help"},
    "aide.texte": {
        "fr": "<h3>Tutti — assembler des PDF</h3><ol>"
              "<li><b>Glissez</b> les PDF (ou un dossier) dans la liste, ou utilisez "
              "<i>Ajouter des PDF…</i></li>"
              "<li><b>Rangez-les</b> : glisser-déposer dans la liste, boutons "
              "<i>Monter / Descendre</i>, ou <i>Trier par nom</i> (« 2 » passe avant « 10 »).</li>"
              "<li>Vérifiez le <b>nom du fichier final</b>, proposé automatiquement.</li>"
              "<li>Cliquez sur <b>Assembler</b>.</li></ol>"
              "<p>Les fichiers d'origine ne sont <b>jamais modifiés</b>. Un signet par fichier "
              "permet de sauter d'une partie à l'autre dans le PDF final.</p>"
              "<p>Le manuel complet est dans le menu <i>Aide</i>.</p>",
        "en": "<h3>Tutti — merge PDF files</h3><ol>"
              "<li><b>Drop</b> the PDF files (or a folder) into the list, or use "
              "<i>Add PDF files…</i></li>"
              "<li><b>Put them in order</b>: drag and drop inside the list, "
              "<i>Move up / Move down</i>, or <i>Sort by name</i> (“2” comes before “10”).</li>"
              "<li>Check the suggested <b>output file name</b>.</li>"
              "<li>Click <b>Merge</b>.</li></ol>"
              "<p>The original files are <b>never modified</b>. One bookmark per file lets "
              "you jump from part to part in the merged PDF.</p>"
              "<p>The full user guide is in the <i>Help</i> menu.</p>"},
    "a_propos.texte": {
        "fr": "<b>Tutti {version}</b><br>Assembler plusieurs PDF en un seul.<br><br>"
              "<i>Tutti</i> : « tous ensemble », en musique.<br><br>"
              "Moteur : qpdf (via pikepdf). Les pages sont recopiées telles quelles, sans perte "
              "de qualité ; les fichiers d'origine ne sont jamais modifiés.<br><br>"
              "Polices : Source Sans 3 et EB Garamond (SIL Open Font License).",
        "en": "<b>Tutti {version}</b><br>Merge several PDF files into one.<br><br>"
              "<i>Tutti</i>: “all together”, in music.<br><br>"
              "Engine: qpdf (through pikepdf). Pages are copied as they are, with no loss of "
              "quality; the original files are never modified.<br><br>"
              "Fonts: Source Sans 3 and EB Garamond (SIL Open Font License)."},
    "manuel.absent": {"fr": "Le manuel est introuvable dans le dossier du programme.",
                      "en": "The user guide could not be found in the program folder."},
    # ---- accord, mises à jour, signalement
    "accord.titre": {"fr": "Envoyer automatiquement un rapport si Tutti rencontre un problème ?",
                     "en": "Send a report automatically if Tutti runs into a problem?"},
    "accord.texte": {
        "fr": "Le rapport contient la version du programme et du système et l'erreur rencontrée. "
              "Les noms de vos fichiers et votre nom d'utilisateur sont masqués. "
              "Vous pourrez changer d'avis dans le menu Aide.",
        "en": "The report contains the program and system versions and the error. "
              "Your file names and user name are hidden. You can change your mind in the Help menu."},
    "maj.titre": {"fr": "Mise à jour", "en": "Update"},
    "maj.recherche": {"fr": "Recherche d'une mise à jour…", "en": "Checking for updates…"},
    "maj.a_jour": {"fr": "Tutti {version} est à jour.", "en": "Tutti {version} is up to date."},
    "maj.dispo": {"fr": "La version {nouvelle} est disponible (vous avez la {version}).",
                  "en": "Version {nouvelle} is available (you have {version})."},
    "maj.installer": {"fr": "Installer maintenant", "en": "Install now"},
    "maj.page": {"fr": "Ouvrir la page", "en": "Open the page"},
    "maj.plus_tard": {"fr": "Plus tard", "en": "Later"},
    "maj.telechargement": {"fr": "Téléchargement de la mise à jour…", "en": "Downloading the update…"},
    "maj.verrou": {"fr": "Un fichier de Tutti est en cours d'utilisation : fermez les autres fenêtres "
                         "de Tutti et réessayez.",
                   "en": "A Tutti file is in use: close the other Tutti windows and try again."},
    "maj.echec": {"fr": "La mise à jour a échoué : {erreur}", "en": "The update failed: {erreur}"},
    "maj.redemarre": {"fr": "Mise à jour installée : Tutti va redémarrer.",
                      "en": "Update installed: Tutti will now restart."},
    "signal.titre": {"fr": "Signaler un problème", "en": "Report a problem"},
    "signal.invite": {"fr": "Décrivez ce qui s'est passé :", "en": "Describe what happened:"},
    "signal.exemple": {"fr": "Par exemple : j'ai glissé 12 PDF, cliqué sur Assembler, et le message "
                             "suivant est apparu…",
                       "en": "For example: I dropped 12 PDF files, clicked Merge, and this message "
                             "appeared…"},
    "signal.note": {"fr": "Le message part avec la version de Tutti et du système. Les noms de vos "
                          "fichiers et votre nom d'utilisateur sont masqués.",
                    "en": "The message is sent with the Tutti and system versions. Your file names "
                          "and user name are hidden."},
    "signal.envoyer": {"fr": "Envoyer", "en": "Send"},
    "signal.merci": {"fr": "Merci", "en": "Thank you"},
    "signal.parti": {"fr": "Merci, le signalement est parti.", "en": "Thank you, the report was sent."},
    "signal.local": {"fr": "Pas de réseau : le signalement a été enregistré ici :\n{chemin}",
                     "en": "No network: the report was saved here:\n{chemin}"},
    "demarrage.echec": {"fr": "Le programme n'a pas pu démarrer.\n\n{erreur}\n\nDétails enregistrés dans :\n{chemin}",
                        "en": "The program could not start.\n\n{erreur}\n\nDetails saved in:\n{chemin}"},
    # ---- moteur : noms et erreurs
    "nom.complet": {"fr": "complet", "en": "complete"},
    "nom.livret": {"fr": "livret", "en": "booklet"},
    "options.mise_en_page": {"fr": "Mise en page :", "en": "Layout:"},
    "livret.non": {"fr": "Pages normales", "en": "Normal pages"},
    "livret.a5": {"fr": "Livret A5 prêt à imprimer (2 pages par feuille A4, pour plier et agrafer)",
                  "en": "A5 booklet ready to print (2 pages per A4 sheet, to fold and staple)"},
    "livret.ordre": {"fr": "Ordre du livret seulement (l'imprimante fait « 2 pages par feuille »)",
                     "en": "Booklet order only (the printer does “2 pages per sheet”)"},
    "livret.conseil_ordre": {"fr": "Les pages sont dans l'ordre du livret. Pour imprimer : option « 2 pages "
                                   "par feuille » (Plusieurs pages / Multiple), A4 paysage, recto-verso avec "
                                   "retournement sur le BORD COURT. Pliez la pile au milieu, emboîtez les "
                                   "feuilles et agrafez au pli.",
                             "en": "The pages are in booklet order. To print: “2 pages per sheet” (Multiple), "
                                   "A4 landscape, double-sided flipping on the SHORT EDGE. Fold the stack in the "
                                   "middle, nest the sheets and staple along the fold."},
    "options.livret": {"fr": "Livret A5 à plier : 2 pages par feuille A4, dans l'ordre pour agrafer au milieu",
                       "en": "A5 booklet to fold: 2 pages per A4 sheet, ordered for stapling in the middle"},
    "livret.conseil": {"fr": "Pour imprimer le livret : format A4, orientation paysage, taille réelle (100 %), "
                             "recto-verso avec retournement sur le BORD COURT. Pliez la pile au milieu, "
                             "emboîtez les feuilles et agrafez au pli.",
                       "en": "To print the booklet: A4 paper, landscape, actual size (100%), double-sided "
                             "flipping on the SHORT EDGE. Fold the stack in the middle, nest the sheets and "
                             "staple along the fold."},
    "nom.defaut": {"fr": "Assemblage", "en": "Merged"},
    "err.inaccessible": {"fr": "Fichier inaccessible ({detail})", "en": "File not accessible ({detail})"},
    "err.vide": {"fr": "Ce PDF ne contient aucune page", "en": "This PDF has no pages"},
    "err.motdepasse": {"fr": "Protégé par un mot de passe", "en": "Password protected"},
    "err.illisible": {"fr": "PDF illisible ou abîmé", "en": "Unreadable or damaged PDF"},
    "err.inattendue": {"fr": "Erreur inattendue ({detail})", "en": "Unexpected error ({detail})"},
    "err.aucun": {"fr": "Aucun fichier à assembler.", "en": "No file to merge."},
    "err.extension": {"fr": "Le fichier de sortie doit se terminer par .pdf",
                      "en": "The output file name must end with .pdf"},
    "err.ecrase_source": {"fr": "Le fichier de sortie est aussi l'un des fichiers à assembler ({nom}) : "
                                "choisissez un autre nom pour ne pas l'écraser.",
                          "en": "The output file is also one of the files to merge ({nom}): "
                                "choose another name so it is not overwritten."},
    "err.dossier_absent": {"fr": "Le dossier de destination n'existe pas :\n{dossier}",
                           "en": "The destination folder does not exist:\n{dossier}"},
    "err.annule": {"fr": "Assemblage annulé.", "en": "Merge cancelled."},
    "err.lecture_mdp": {"fr": "« {nom} » est protégé par un mot de passe.",
                        "en": "“{nom}” is password protected."},
    "err.lecture_illisible": {"fr": "Impossible de lire « {nom} » : PDF illisible ou abîmé.",
                              "en": "Cannot read “{nom}”: unreadable or damaged PDF."},
    "err.lecture_acces": {"fr": "Impossible de lire « {nom} » : {detail}.",
                          "en": "Cannot read “{nom}”: {detail}."},
    "err.aucune_page": {"fr": "Les fichiers choisis ne contiennent aucune page.",
                        "en": "The chosen files contain no pages."},
    "err.ouvert_ailleurs": {"fr": "Impossible d'écrire « {nom} » : le fichier est sans doute ouvert dans "
                                  "un autre programme (lecteur PDF). Fermez-le et recommencez.",
                            "en": "Cannot write “{nom}”: the file is probably open in another program "
                                  "(PDF reader). Close it and try again."},
    "err.ecriture_refusee": {"fr": "Écriture refusée dans {dossier} : {detail}",
                             "en": "Writing refused in {dossier}: {detail}"},
    "err.ecriture": {"fr": "Écriture impossible : {detail}", "en": "Cannot write: {detail}"},
    "err.inattendue_assemblage": {"fr": "Erreur inattendue : {detail}", "en": "Unexpected error: {detail}"},
    "err.conversion": {"fr": "{detail}", "en": "{detail}"},
    "err.conversion_nom": {"fr": "« {nom} » : {detail}", "en": "“{nom}”: {detail}"},
    # ---- conversion
    "conv.format": {"fr": "Format non pris en charge ({ext})", "en": "Unsupported format ({ext})"},
    "conv.vide": {"fr": "La conversion n'a rien produit", "en": "The conversion produced nothing"},
    "conv.image": {"fr": "Image illisible ({detail})", "en": "Unreadable image ({detail})"},
    "conv.pas_de_suite": {"fr": "Conversion impossible : installez Microsoft Office ou LibreOffice (gratuit)",
                          "en": "Cannot convert: install Microsoft Office or LibreOffice (free)"},
    "conv.trop_long": {"fr": "Conversion trop longue (plus de {s} s)", "en": "Conversion took too long (over {s} s)"},
    "conv.echec": {"fr": "{logiciel} n'a pas pu convertir ce document", "en": "{logiciel} could not convert this document"},
    "genre.image": {"fr": "image", "en": "image"},
    "genre.office": {"fr": "document converti", "en": "converted document"},
    # ---- découpage
    "decoupe.page": {"fr": "page", "en": "page"},
    "decoupe.pages": {"fr": "pages", "en": "pages"},
    "decoupe.plages_vides": {"fr": "Indiquez les pages à extraire, par exemple : 1-3, 5, 8-",
                             "en": "Enter the pages to extract, for example: 1-3, 5, 8-"},
    "decoupe.plage_invalide": {"fr": "« {plage} » n'est pas une plage de pages valide (exemple : 1-3, 5, 8-)",
                               "en": "“{plage}” is not a valid page range (example: 1-3, 5, 8-)"},
    "decoupe.hors_limites": {"fr": "La plage « {plage} » sort du document, qui a {n} pages",
                             "en": "The range “{plage}” is outside the document, which has {n} pages"},
    # ---- ligne de commande
    "cli.description": {"fr": "Assembler plusieurs PDF en un seul.", "en": "Merge several PDF files into one."},
    "cli.erreur": {"fr": "Erreur : {detail}", "en": "Error: {detail}"},
}
