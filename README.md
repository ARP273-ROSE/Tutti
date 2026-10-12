<p align="center"><img src="logo.png" width="128" alt="Tutti"></p>

# Tutti

**Merge, convert and split PDF files — on your own computer.**
**Assembler, convertir et découper des PDF — sur votre ordinateur.**

*Tutti*: “all together”, in music. Windows · macOS · Linux · English / Français.

➡️ **[Download / Télécharger](../../releases/latest)** ·
[User guide (PDF)](docs/manuel-en.pdf) · [Manuel (PDF)](docs/manuel-fr.pdf) ·
[Changes / Historique](CHANGELOG.md)

---

## English

Tutti does what online PDF tools do, without uploading anything:

- **Merge** PDF files by drag and drop, reorder them by dragging inside the list, one **bookmark
  per file**. The output name is suggested from what the file names have in common
  (`Symphony No. 5 - 01 Flute.pdf` … → `Symphony No. 5 - complete.pdf`).
- **Convert** images (JPEG, PNG, TIFF, BMP, GIF, WebP) and **Word, Excel, PowerPoint** documents
  to PDF. Images are embedded losslessly (a JPEG is inserted as is). Documents are laid out by
  Microsoft Office when installed (Windows), otherwise by LibreOffice — read-only, macros disabled.
- **Split** a PDF — or a Word, Excel, PowerPoint document or image — into one file per page, or by
  page ranges (`1-8, 9-16, 17-`). Everything combines: a 6-page Word file becomes six one-page PDFs.
- Option for double-sided printing: every part starts on a right-hand page.

**Safe**: originals are never modified; Tutti refuses to overwrite a source file; output is written
to a temporary file then moved into place in one step, so a power cut never leaves a half-written
PDF. Damaged or password-protected files are flagged before merging.

**Fast**: file analysis and large splits are spread over all CPU cores; writing is done by qpdf (C++).
The window never freezes: no file work runs on the GUI thread.

**Looks the same everywhere**: fixed ivory, burgundy and gold theme with bundled fonts, independent of
the system theme (light/dark, accent colour).

**Language**: follows the system language (French or English), can be forced from the *Language* menu.

**Updates and error reports**: Tutti offers new versions at startup and installs them itself, on all
three systems. With your consent, crashes and freezes are reported automatically; file names and user
name are hidden.

Installation: no administrator rights needed. Windows may show “Windows protected your PC” the first
time (unsigned installer): *More info* → *Run anyway*. macOS: right-click → *Open* the first time.
Linux: unpack and run `installer.sh`.

## Français

Tutti fait ce que font les sites de PDF en ligne, sans rien envoyer sur Internet :

- **Assembler** des PDF par glisser-déposer, les ranger en les faisant glisser dans la liste, un
  **signet par fichier**. Le nom du fichier final est proposé à partir de la partie commune des noms
  (`Symphonie n°5 - 01 Flûte.pdf` … → `Symphonie n°5 - complet.pdf`).
- **Convertir en PDF** les images (JPEG, PNG, TIFF, BMP, GIF, WebP) et les documents **Word, Excel,
  PowerPoint**. Les images sont insérées sans perte (un JPEG tel quel). Les documents sont mis en page
  par Microsoft Office s'il est installé (Windows), sinon par LibreOffice — en lecture seule, macros
  coupées.
- **Découper** un PDF — ou un document Word, Excel, PowerPoint, ou une image — en un fichier par page,
  ou par plages de pages (`1-8, 9-16, 17-`). Tout se combine : un Word de 6 pages donne six PDF d'une page.
- Option recto-verso : chaque partie commence sur une page de droite.

**Sûr** : les originaux ne sont jamais modifiés ; Tutti refuse d'écraser un fichier source ; le
résultat est écrit dans un fichier temporaire puis mis en place d'un coup, si bien qu'une coupure de
courant ne laisse jamais de PDF à moitié écrit. Les fichiers abîmés ou protégés par mot de passe sont
signalés avant l'assemblage.

**Rapide** : l'analyse des fichiers et les gros découpages se répartissent sur tous les cœurs ;
l'écriture est confiée à qpdf (C++). La fenêtre ne se fige jamais.

**Même apparence partout** : thème ivoire, bordeaux et or, polices embarquées, indépendant du thème du
système (clair/sombre, couleur d'accentuation).

**Langue** : celle du système (français ou anglais), modifiable dans le menu *Langue*.

**Mises à jour et rapports d'incident** : Tutti propose les nouvelles versions au démarrage et les
installe lui-même, sur les trois systèmes. Avec votre accord, plantages et gels sont signalés
automatiquement ; noms de fichiers et nom d'utilisateur sont masqués.

Installation : aucun droit administrateur. Windows peut afficher « Windows a protégé votre ordinateur »
la première fois (installeur non signé) : *Informations complémentaires* → *Exécuter quand même*.
macOS : clic droit → *Ouvrir* la première fois. Linux : décompresser et lancer `installer.sh`.

---

## Development / Développement

```
pip install -r requirements.txt
python run.py                                   # interface
python run.py --merge out.pdf a.pdf photo.jpg folder/
QT_QPA_PLATFORM=offscreen python -m pytest -q tests
python docs/captures.py && sh docs/src/compiler.sh   # screenshots + user guides
```

Fonts in `tutti/polices/`: Source Sans 3 and EB Garamond, SIL Open Font License 1.1.
