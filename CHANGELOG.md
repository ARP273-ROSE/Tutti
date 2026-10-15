# Changelog / Historique

## English

### 1.3.0

- New **Pages** tab: open one document (PDF, Word, image…) and see all its pages as thumbnails.
  Rotate pages a quarter turn (Ctrl+L / Ctrl+R), remove pages (Del), drag them to a new place,
  double-click to see a page full size, *Undo all*, then *Save…* a new PDF. Rotation only changes
  the page orientation: no loss of quality. Unsaved changes are never lost without a question.
- New **Finishing** tab, on one or several PDF files at once (each gives `<name> - finished.pdf`):
  - page numbers: bottom centre, or outer edge (right on odd pages, left on even pages) at the bottom
    or the top; “3” or “3 / 12”; start number; no number on the title page;
  - text at the top of every page, or of page 1 only (title, part name);
  - smaller file for e-mail: photos and colour or grey scans reduced to 150 dpi (JPEG); text, vector
    music and black-and-white scans are left untouched. Size before and after is shown.
  Numbers and text are placed on the page as it is seen, even on a rotated page.
- New booklet layout: **A4 booklet on A3 sheets** (two A4 pages per A3 sheet, not reduced), the usual
  size for bound scores, next to the A5 booklet on A4.
- User guide reorganised: an “I want to… → which tab” table first, two new chapters (Pages,
  Finishing), combined recipes, shortcuts by tab.
- Packages keep Qt's PDF module (QtPdf), used for the thumbnails; the build checks it is present.

### 1.2.0

- Linux: opening and saving files now always use Qt's complete file dialog
  (sidebar with home, Documents, Downloads and mounted drives, folder tree,
  new folder), in the application's look; the desktop portal's dialog was
  sometimes reduced to a plain list. Windows and macOS keep their own dialog.
- One logo, drawn once as a vector image (`logo.svg`) and used for the icon,
  the About box (which now shows it) and the manual.
- The look stays the same everywhere, including greyed-out items, whatever
  the system theme.
- Installer packages built by the common kit: the Linux and macOS launchers
  follow symbolic links, a `--check` start test runs on every system before
  publishing, and a native crash of the previous session is no longer lost
  before it is reported.

### 1.1.5

- The hint text in the empty list no longer runs past the edges: it wraps and shrinks to fit
  (narrow window, 125–150 % display scaling).

### 1.1.4

- macOS and Linux: the package now ships the file that tells the updater where to look for new
  versions. 1.1.3 recognised the installed package but still found no update. The build now fails if
  the update check would not work. Reinstall once by hand from 1.1.3 or earlier.

### 1.1.3

- macOS and Linux: automatic updates now work. The installed package was not recognised (only the
  Windows interpreter was looked for), so no update was ever searched for at startup.
  **Versions up to 1.1.2 on macOS/Linux must be reinstalled once by hand**; later updates are automatic.
- macOS and Linux: settings are kept outside the program folder (`~/Library/Application Support/Tutti`,
  `~/.local/state/Tutti`) and survive updates.

### 1.1.2

- Linux: file and folder dialogs are now those of the desktop (KDE, GNOME…) through the XDG portal,
  instead of Qt's reduced built-in dialog.

### 1.1.1

- Linux: the launcher now follows symbolic links (a link from `~/.local/bin/tutti` works).
- Linux: menu entry filed under Office instead of Science.
- `--version` option on the command line.

### 1.1.0

- Booklet layout is now a choice: *A5 booklet ready to print* (2 pages per A4 sheet) or
  *booklet order only* (same pages, reordered for the printer's “2 pages per sheet”).
- Works from one multi-page file or from several one-page files, in list order.
- Permanent download links (files without a version number).

### 1.0.0

First version.

- Merge PDF files by drag and drop; reorder by dragging inside the list; one bookmark per file;
  output name suggested automatically.
- Convert images and Word, Excel, PowerPoint documents to PDF (Microsoft Office or LibreOffice).
- Split a PDF, or any supported document or image, into one file per page or by page ranges.
- A5 booklet imposition for folding and stapling.
- Double-sided printing option (each part starts on a right-hand page).
- Parallel analysis and splitting, atomic writes, sources never modified.
- Fixed look independent of the system theme; English and French, detected automatically.
- Windows, macOS and Linux packages with automatic updates and error reports.

## Francais

### 1.3.0

- Nouvel onglet **Pages** : ouvrir un document (PDF, Word, image…) et voir toutes ses pages en
  vignettes. Pivoter d'un quart de tour (Ctrl+L / Ctrl+R), retirer (Suppr), faire glisser une page
  à sa nouvelle place, double-clic pour la voir en grand, *Tout annuler*, puis *Enregistrer…* un
  nouveau PDF. Pivoter ne change que l'orientation : aucune perte de qualité. Des changements non
  enregistrés ne sont jamais perdus sans question.
- Nouvel onglet **Finitions**, sur un ou plusieurs PDF à la fois (chacun donne `<nom> - finitions.pdf`) :
  - numéros de page : en bas au centre, ou côté extérieur (à droite sur les impaires, à gauche sur les
    paires) en bas ou en haut ; « 3 » ou « 3 / 12 » ; numéro de départ ; pas de numéro sur la page de titre ;
  - texte en haut de toutes les pages, ou de la première seulement (titre, nom de la partie) ;
  - allègement pour l'e-mail : photos et scans couleur ou gris réduits à 150 ppp (JPEG) ; le texte, la
    musique vectorielle et les scans noir et blanc restent intacts. Poids avant et après affiché.
  Numéros et texte sont placés sur la page telle qu'on la voit, même tournée.
- Nouvelle mise en page : **livret A4 sur feuilles A3** (deux pages A4 par feuille A3, sans réduction),
  le format des partitions reliées, à côté du livret A5 sur A4.
- Manuel réorganisé : un tableau « Je veux… → quel onglet » en tête, deux nouveaux chapitres (Pages,
  Finitions), des recettes combinées, les raccourcis par onglet.
- Les paquets gardent le module PDF de Qt (QtPdf), qui dessine les vignettes ; la construction vérifie
  sa présence.

### 1.2.0

- Linux : ouvrir et enregistrer passent toujours par la boîte de fichiers
  complète de Qt (barre latérale avec dossier personnel, Documents,
  Téléchargements et disques branchés, arborescence, nouveau dossier), aux
  couleurs de l'application ; celle du portail du bureau se réduisait parfois
  à une simple liste. Windows et macOS gardent leur boîte habituelle.
- Un seul logo, dessiné une fois en image vectorielle (`logo.svg`), pour
  l'icône, la fenêtre « À propos » (qui l'affiche désormais) et le manuel.
- L'apparence reste la même partout, éléments grisés compris, quel que soit
  le thème du système.
- Paquets construits par le kit commun : les lanceurs Linux et macOS suivent
  les liens symboliques, un essai de démarrage `--check` tourne sur chaque
  système avant publication, et le crash natif d'une session précédente n'est
  plus perdu avant d'être signalé.

### 1.1.5

- Le texte d'accueil de la liste vide ne dépasse plus du cadre : il passe à la ligne et se réduit
  pour tenir (fenêtre étroite, mise à l'échelle 125–150 %).

### 1.1.4

- macOS et Linux : le paquet contient désormais le fichier qui indique au module de mise à jour où
  chercher les nouvelles versions. La 1.1.3 reconnaissait le paquet installé mais ne trouvait toujours
  aucune mise à jour. La construction échoue maintenant si la mise à jour ne pourrait pas fonctionner.
  Réinstaller une fois à la main depuis la 1.1.3 ou avant.

### 1.1.3

- macOS et Linux : la mise à jour automatique fonctionne. Le paquet installé n'était pas reconnu (seul
  l'interpréteur Windows était cherché), si bien qu'aucune mise à jour n'était jamais recherchée.
  **Les versions jusqu'à 1.1.2 sous macOS/Linux doivent être réinstallées une fois à la main** ;
  les suivantes se mettront à jour seules.
- macOS et Linux : les réglages sont rangés hors du dossier du programme
  (`~/Library/Application Support/Tutti`, `~/.local/state/Tutti`) et survivent aux mises à jour.

### 1.1.2

- Linux : les fenêtres de choix de fichiers et de dossiers sont celles du bureau (KDE, GNOME…), via
  le portail XDG, au lieu de la fenêtre réduite de Qt.

### 1.1.1

- Linux : le lanceur suit les liens symboliques (un lien depuis `~/.local/bin/tutti` fonctionne).
- Linux : entrée de menu rangée dans Bureautique au lieu de Sciences.
- Option `--version` en ligne de commande.

### 1.1.0

- La mise en page livret devient un choix : *livret A5 prêt à imprimer* (2 pages par feuille A4) ou
  *ordre du livret seulement* (mêmes pages, remises dans l'ordre pour l'option « 2 pages par feuille »
  de l'imprimante).
- Fonctionne avec un fichier de plusieurs pages comme avec plusieurs fichiers d'une page, dans
  l'ordre de la liste.
- Liens de téléchargement permanents (fichiers sans numéro de version).

### 1.0.0

Première version.

- Assemblage de PDF par glisser-déposer ; rangement par glisser-déposer dans la liste ; un signet
  par fichier ; nom du fichier final proposé automatiquement.
- Conversion en PDF des images et des documents Word, Excel, PowerPoint (Microsoft Office ou LibreOffice).
- Découpage d'un PDF, ou de tout document ou image accepté, en un fichier par page ou par plages.
- Imposition en livret A5 à plier et agrafer.
- Option recto-verso (chaque partie commence sur une page de droite).
- Analyse et découpage en parallèle, écriture atomique, sources jamais modifiées.
- Apparence figée, indépendante du thème du système ; français et anglais, détectés automatiquement.
- Paquets Windows, macOS et Linux avec mise à jour automatique et rapports d'incident.
