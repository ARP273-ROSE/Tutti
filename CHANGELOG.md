# Changelog / Historique

## English

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
