# Tutti — progression

## État au 15/10/2026

**Version publiée : 1.2.0** — Windows, macOS (Apple Silicon et Intel), Linux (x86_64 et ARM64).
Liens permanents : `https://github.com/ARP273-ROSE/Tutti/releases/latest/download/Tutti-Setup.exe`
(et `Tutti-macos-arm64.dmg`, `Tutti-macos-x86_64.dmg`, `Tutti-linux-x86_64.tar.gz`, `Tutti-linux-arm64.tar.gz`).

### Fonctions
- **Assembler** : glisser-déposer de fichiers ou dossiers, réordonnancement par glisser-déposer,
  tri naturel, un signet par fichier, nom de sortie proposé, option recto (page blanche).
- **Convertir** : images (img2pdf, JPEG sans recompression, A4 orienté) ; Word / Excel / PowerPoint
  par Microsoft Office (COM, `comtypes`, macros coupées, lecture seule) ou LibreOffice (headless,
  profil jetable, durée limite).
- **Découper** : une page par fichier ou plages (`1-3, 5, 8-`), tout format accepté (un document
  est converti puis découpé), multiprocessus au-delà de 40 fichiers.
- **Livret** : *A5 prêt à imprimer* (2 pages par feuille A4 paysage) ou *ordre du livret seulement*
  (pour l'option « 2 pages par feuille » de l'imprimante), depuis un ou plusieurs fichiers.
- **Pages** (1.3.0) : vignettes QtPdf rendues dans un fil de fond (`tutti/onglet_pages.py`),
  pivoter / retirer / déplacer / aperçu en grand, écriture par `pages.remanier` (attribut /Rotate,
  aucune réimpression).
- **Finitions** (1.3.0, `tutti/onglet_finitions.py`, moteur `tutti/pages.py`) : numéros (centre ou
  côté extérieur, « n » ou « n / total »), texte en tête, allègement (images > 150 ppp sur la page
  → JPEG 80) ; Helvetica non embarquée + table de chasses WinAnsi ; placement dans le repère de la
  page VUE (rotation 0/90/180/270), contenu d'origine encadré q … Q.
- **Livret A4 sur A3** (1.3.0) : `Options.livret = "a4"`.
- Bilingue FR/EN avec détection de la langue d'affichage ; apparence figée (Fusion, palette,
  polices OFL embarquées) ; mise à jour automatique et rapports d'incident (kit commun).

### Vérifié
- 70 tests (moteur, pages et finitions, conversion, découpage, livret, traductions, fenêtre hors écran) verts sous
  Linux et Windows (CI `tests.yml`).
- Paquet Linux construit et exécuté pour de vrai (assemblage PNG + PDF en ligne de commande).
- Conversion LibreOffice vérifiée avec la vraie ligne de commande.
- Release téléchargeable sans compte ; 1re installation Windows réelle réussie (rapport
  d'installation reçu, aucun plantage ni gel signalé).

### Reste à vérifier
- ✅ **Conversion Word par Microsoft Office** : fonctionne sur un poste réel (13/10/2026).
- ⏳ Excel et PowerPoint par Office : pas encore essayés. Une conversion refusée s'affiche en
  rouge dans la liste mais n'envoie pas de rapport.
- ⏳ **Première mise à jour automatique** sur un poste Windows installé (Linux : vérifiée en 1.1.4).
- Paquets macOS jamais ouverts sur un vrai Mac.

### Pièges déjà payés
- 🔴 Le kit élague Qt6Pdf/QtPdf des paquets : kit.json `qt_garder: ["Pdf"]` (option ajoutée au kit le
  15/10/2026) + `qt_attendus` par système pour que la construction échoue s'il manque.
- QtPdf rend la page sur fond TRANSPARENT : composer sur du blanc (`onglet_pages.sur_blanc`), sinon la
  vignette prend la couleur de l'ombre ou de la sélection.
- pikepdf ≥ 10.14 n'a plus de roue macOS x86_64 → borne `<10.14` par marqueur dans `requirements.txt`.
- pip refuse `not (...)` dans un marqueur d'environnement : écrire
  `sys_platform != "darwin" or platform_machine != "x86_64"`.
- `tempfile.mkstemp` crée les fichiers en 600 : rendre au PDF final les droits du umask.
- `pages.extend()` perd liens internes et formulaires : `Pdf.add_pages_from()` (pikepdf ≥ 10).
- 🔴 `updater.is_packaged()` ne cherchait que `python/python.exe` : sous macOS et Linux, le paquet se
  croyait lancé depuis les sources et ne cherchait jamais de mise à jour (corrigé en 1.1.3 ; les
  installations ≤ 1.1.2 hors Windows se réinstallent une fois à la main).
- 🔴 `build_unix.py` n'embarquait pas `kit.json` : dépôt de distribution vide, aucune mise à jour
  trouvée sous macOS/Linux même une fois le paquet reconnu (corrigé en 1.1.4 ; la construction
  vérifie désormais `updater.REPO` et `is_packaged()`). Mise à jour Linux testée de bout en bout.
- Le détail d'erreur de qpdf contient le chemin complet du fichier : ne jamais l'afficher ni
  l'envoyer dans un rapport.
- Lancer un installeur ou une opération système depuis un processus confiné (application
  empaquetée, sandbox) peut échouer sans cause apparente : l'utilisateur lance lui-même.

### Fabrication
- Tests : `QT_QPA_PLATFORM=offscreen python -m pytest -q tests`
- Captures fictives des manuels : `python docs/captures.py` ; manuels : `sh docs/src/compiler.sh`
- Publication : mettre `VERSION` à jour, compléter `CHANGELOG.md` (sections English / Francais),
  pousser le tag `vX.Y.Z` → `release.yml` construit les 5 paquets et publie la Release.

### Décision en attente
- Licence du dépôt (aucun fichier LICENSE pour l'instant).
