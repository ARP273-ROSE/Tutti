"""Fenêtre principale de Tutti.

Règle d'or : le fil graphique ne touche jamais un fichier. Analyse et
assemblage tournent dans un fil de fond qui ne parle à Qt que par signaux ;
la fenêtre ne peut donc pas se figer, même sur un gros lot.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from . import __version__, moteur
from .i18n import langue, tr
from .moteur import AssemblageAnnule, ErreurTutti, InfoPdf, Options
from .onglet_finitions import OngletFinitions
from .onglet_pages import OngletPages

ROLE_CHEMIN = Qt.ItemDataRole.UserRole
ROLE_INFO = Qt.ItemDataRole.UserRole + 1




class Signaux(QtCore.QObject):
    analyse = QtCore.pyqtSignal(object)          # InfoPdf
    analyse_finie = QtCore.pyqtSignal()
    progression = QtCore.pyqtSignal(int, int, str)
    fini = QtCore.pyqtSignal(object, object)     # (nb_pages | None, message d'erreur | None)
    progression_d = QtCore.pyqtSignal(int, int, str)
    fini_d = QtCore.pyqtSignal(object, object)   # (fichiers écrits, message d'erreur | None)


class ListePdf(QtWidgets.QListWidget):
    """Liste réordonnable qui accepte aussi les fichiers venus de l'Explorateur."""
    deposes = QtCore.pyqtSignal(list)

    def __init__(self, parent=None, texte_vide=None):
        super().__init__(parent)
        self._texte_vide = texte_vide
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(True)
        self.setIconSize(QtCore.QSize(20, 20))
        f = self.font()
        f.setPointSizeF(f.pointSizeF() * 1.15)   # lisible sans lunettes
        self.setFont(f)

    def _externe(self, ev) -> bool:
        return ev.mimeData().hasUrls() and ev.source() is not self

    def dragEnterEvent(self, ev):
        if self._externe(ev):
            ev.acceptProposedAction()
        else:
            super().dragEnterEvent(ev)

    def dragMoveEvent(self, ev):
        if self._externe(ev):
            ev.acceptProposedAction()
        else:
            super().dragMoveEvent(ev)

    def dropEvent(self, ev):
        if self._externe(ev):
            chemins = [u.toLocalFile() for u in ev.mimeData().urls() if u.isLocalFile()]
            ev.acceptProposedAction()
            if chemins:
                self.deposes.emit(chemins)
        else:
            super().dropEvent(ev)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if self.count() == 0:
            p = QtGui.QPainter(self.viewport())
            p.setPen(self.palette().color(QtGui.QPalette.ColorRole.PlaceholderText))
            texte = self._texte_vide or tr("liste.vide")
            # Marges, retour à la ligne, et taille réduite jusqu'à ce que le
            # texte tienne : une fenêtre étroite ou une mise à l'échelle 150 %
            # ne doit jamais couper la phrase au bord de la liste.
            zone = self.viewport().rect().adjusted(20, 12, -20, -12)
            options = int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap)
            f = p.font()
            taille = f.pointSizeF() * 1.3
            while taille > 7:
                f.setPointSizeF(taille)
                boite = QtGui.QFontMetrics(f).boundingRect(zone, options, texte)
                if boite.width() <= zone.width() and boite.height() <= zone.height():
                    break
                taille -= 0.5
            p.setFont(f)
            p.drawText(zone, options, texte)
            p.end()


class FenetrePrincipale(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("fenetre.titre", version=__version__))
        self.resize(860, 680)
        self.reglages = QtCore.QSettings("ARP273-ROSE", "Tutti")
        self.signaux = Signaux()
        self.signaux.analyse.connect(self._recevoir_analyse)
        self.signaux.analyse_finie.connect(self._analyse_finie)
        self.signaux.progression.connect(self._progression)
        self.signaux.fini.connect(self._fin_assemblage)
        self._en_cours = False
        self._annuler = threading.Event()
        self._nom_auto = True            # le nom suit la liste tant qu'on ne l'a pas retouché
        self._analyses_en_cours = 0
        # Conversions (images, documents) de la session : effacées à la fermeture.
        self._dossier_conv = tempfile.mkdtemp(prefix="tutti-conv-")
        self._construire()
        self._construire_menus()
        self._majeur_etat()

    # ------------------------------------------------------------ interface
    def _construire(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        grille = QtWidgets.QVBoxLayout(central)

        entete = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        chemin_logo = Path(__file__).resolve().parent.parent / "logo_64.png"
        if chemin_logo.exists():
            logo.setPixmap(QtGui.QPixmap(str(chemin_logo)).scaled(
                52, 52, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        entete.addWidget(logo)
        textes = QtWidgets.QVBoxLayout()
        titre = QtWidgets.QLabel("Tutti")
        titre.setObjectName("titre")
        textes.addWidget(titre)
        sous = QtWidgets.QLabel(tr("entete.sous_titre"))
        sous.setObjectName("sous_titre")
        sous.setWordWrap(True)
        textes.addWidget(sous)
        entete.addLayout(textes, 1)
        grille.addLayout(entete)
        self.onglets = QtWidgets.QTabWidget()
        grille.addWidget(self.onglets, 1)
        page_a = QtWidgets.QWidget()
        ga = QtWidgets.QVBoxLayout(page_a)
        ga.setContentsMargins(8, 10, 8, 8)
        self.onglets.addTab(page_a, tr("onglet.assembler"))

        ligne = QtWidgets.QHBoxLayout()
        self.liste = ListePdf()
        self.liste.deposes.connect(self.ajouter)
        self.liste.model().rowsMoved.connect(lambda *a: self._liste_changee())
        self.liste.itemSelectionChanged.connect(self._majeur_etat)
        ligne.addWidget(self.liste, 1)

        boutons = QtWidgets.QVBoxLayout()

        def bouton(texte, action, raccourci=None, astuce=None):
            b = QtWidgets.QPushButton(texte)
            b.clicked.connect(action)
            if raccourci:
                b.setShortcut(QtGui.QKeySequence(raccourci))
            if astuce:
                b.setToolTip(astuce)
            boutons.addWidget(b)
            return b

        self.b_ajouter = bouton(tr("bouton.ajouter"), self._choisir_fichiers, "Ctrl+O")
        self.b_dossier = bouton(tr("bouton.dossier"), self._choisir_dossier)
        boutons.addSpacing(12)
        self.b_monter = bouton(tr("bouton.monter"), lambda: self._deplacer(-1), "Alt+Up")
        self.b_descendre = bouton(tr("bouton.descendre"), lambda: self._deplacer(+1), "Alt+Down")
        self.b_trier = bouton(tr("bouton.trier"), self._trier,
                              astuce=tr("bouton.trier.astuce"))
        boutons.addSpacing(12)
        self.b_retirer = bouton(tr("bouton.retirer"), self._retirer, "Del")
        self.b_vider = bouton(tr("bouton.vider"), self._vider)
        boutons.addStretch(1)
        ligne.addLayout(boutons)
        ga.addLayout(ligne, 1)

        self.resume = QtWidgets.QLabel("")
        self.resume.setObjectName("resume")
        ga.addWidget(self.resume)

        options = QtWidgets.QGroupBox(tr("options.titre"))
        lo = QtWidgets.QVBoxLayout(options)
        self.c_signets = QtWidgets.QCheckBox(tr("options.signets"))
        self.c_signets.setChecked(self.reglages.value("signets", True, type=bool))
        self.c_recto = QtWidgets.QCheckBox(tr("options.recto"))
        self.c_recto.setChecked(self.reglages.value("recto", False, type=bool))
        ligne_livret = QtWidgets.QHBoxLayout()
        ligne_livret.addWidget(QtWidgets.QLabel(tr("options.mise_en_page")))
        self.cb_livret = QtWidgets.QComboBox()
        for code, cle in (("", "livret.non"), ("a5", "livret.a5"), ("a4", "livret.a4"),
                          ("ordre", "livret.ordre")):
            self.cb_livret.addItem(tr(cle), code)
        choix = self.reglages.value("livret_mode", "", type=str)
        self.cb_livret.setCurrentIndex(max(0, self.cb_livret.findData(choix)))
        self.cb_livret.currentIndexChanged.connect(lambda _: self._livret_bascule())
        ligne_livret.addWidget(self.cb_livret, 1)
        self.c_ouvrir = QtWidgets.QCheckBox(tr("options.ouvrir"))
        self.c_ouvrir.setChecked(self.reglages.value("ouvrir", True, type=bool))
        for c in (self.c_signets, self.c_recto):
            lo.addWidget(c)
        lo.addLayout(ligne_livret)
        lo.addWidget(self.c_ouvrir)
        self.c_signets.setEnabled(not self.mode_livret())
        ga.addWidget(options)

        sortie = QtWidgets.QGroupBox(tr("sortie.titre"))
        ls = QtWidgets.QGridLayout(sortie)
        ls.addWidget(QtWidgets.QLabel(tr("sortie.nom")), 0, 0)
        self.e_nom = QtWidgets.QLineEdit()
        self.e_nom.textEdited.connect(self._nom_retouche)
        ls.addWidget(self.e_nom, 0, 1)
        ls.addWidget(QtWidgets.QLabel(tr("sortie.dossier")), 1, 0)
        self.e_dossier = QtWidgets.QLineEdit()
        self.e_dossier.setReadOnly(True)
        ls.addWidget(self.e_dossier, 1, 1)
        b_dest = QtWidgets.QPushButton(tr("bouton.choisir"))
        b_dest.clicked.connect(self._choisir_destination)
        ls.addWidget(b_dest, 0, 2, 2, 1)
        ga.addWidget(sortie)

        bas = QtWidgets.QHBoxLayout()
        self.barre = QtWidgets.QProgressBar()
        self.barre.setTextVisible(True)
        self.barre.hide()
        bas.addWidget(self.barre, 1)
        self.b_assembler = QtWidgets.QPushButton(tr("bouton.assembler"))
        self.b_assembler.setObjectName("principal")
        self.b_assembler.setDefault(True)
        self.b_assembler.setMinimumHeight(46)
        self.b_assembler.setMinimumWidth(210)
        f = self.b_assembler.font()
        f.setWeight(QtGui.QFont.Weight.DemiBold)
        f.setPointSizeF(f.pointSizeF() * 1.25)
        self.b_assembler.setFont(f)
        self.b_assembler.clicked.connect(self._assembler_ou_annuler)
        bas.addStretch(0 if self.barre.isVisible() else 1)
        bas.addWidget(self.b_assembler)
        ga.addLayout(bas)
        # Onglets dans l'ordre d'un travail : assembler, retoucher les pages,
        # finir (numéros, en-tête, poids) ; le découpage est l'opération inverse.
        self.onglet_pages = OngletPages(self)
        self.onglets.addTab(self.onglet_pages, tr("onglet.pages"))
        self.onglet_finitions = OngletFinitions(self, ListePdf)
        self.onglets.addTab(self.onglet_finitions, tr("onglet.finitions"))
        self._construire_decoupe()
        self.statusBar()

    def _filtre_entrees(self) -> str:
        motifs = " ".join(sorted(f"*{e}" for e in moteur.EXTENSIONS))
        return f"{tr('dlg.filtre_tout')} ({motifs});;{tr('dlg.filtre')}"

    # ------------------------------------------------------------ découpage
    def _construire_decoupe(self):
        page = QtWidgets.QWidget()
        gd = QtWidgets.QVBoxLayout(page)
        gd.setContentsMargins(8, 10, 8, 8)
        self.onglets.addTab(page, tr("onglet.decouper"))

        ligne = QtWidgets.QHBoxLayout()
        self.liste_d = ListePdf(texte_vide=tr("decoupe.liste_vide"))
        self.liste_d.deposes.connect(self.ajouter_a_decouper)
        self.liste_d.itemSelectionChanged.connect(self._majeur_decoupe)
        ligne.addWidget(self.liste_d, 1)
        bd = QtWidgets.QVBoxLayout()
        b = QtWidgets.QPushButton(tr("bouton.ajouter"))
        b.clicked.connect(self._choisir_a_decouper)
        bd.addWidget(b)
        self.bd_retirer = QtWidgets.QPushButton(tr("bouton.retirer"))
        self.bd_retirer.clicked.connect(lambda: [self.liste_d.takeItem(self.liste_d.row(i))
                                                 for i in self.liste_d.selectedItems()]
                                        and self._majeur_decoupe())
        bd.addWidget(self.bd_retirer)
        bv = QtWidgets.QPushButton(tr("bouton.vider"))
        bv.clicked.connect(lambda: (self.liste_d.clear(), self._majeur_decoupe()))
        bd.addWidget(bv)
        bd.addStretch(1)
        ligne.addLayout(bd)
        gd.addLayout(ligne, 1)

        mode = QtWidgets.QGroupBox(tr("decoupe.mode"))
        lm = QtWidgets.QGridLayout(mode)
        self.r_pages = QtWidgets.QRadioButton(tr("decoupe.une_page"))
        self.r_plages = QtWidgets.QRadioButton(tr("decoupe.par_plages"))
        self.r_pages.setChecked(True)
        self.e_plages = QtWidgets.QLineEdit()
        self.e_plages.setPlaceholderText(tr("decoupe.exemple"))
        self.e_plages.setEnabled(False)
        self.r_plages.toggled.connect(self.e_plages.setEnabled)
        self.r_plages.toggled.connect(lambda _: self._majeur_decoupe())
        self.e_plages.textChanged.connect(lambda _: self._majeur_decoupe())
        lm.addWidget(self.r_pages, 0, 0, 1, 2)
        lm.addWidget(self.r_plages, 1, 0)
        lm.addWidget(self.e_plages, 1, 1)
        lm.setColumnStretch(1, 1)
        gd.addWidget(mode)

        dest = QtWidgets.QGroupBox(tr("decoupe.destination"))
        ld = QtWidgets.QGridLayout(dest)
        self.r_dest_auto = QtWidgets.QRadioButton(tr("decoupe.dest_auto"))
        self.r_dest_auto.setChecked(True)
        self.r_dest_choisi = QtWidgets.QRadioButton(tr("decoupe.dest_choisi"))
        self.e_dest = QtWidgets.QLineEdit()
        self.e_dest.setReadOnly(True)
        b_dest = QtWidgets.QPushButton(tr("bouton.choisir"))
        b_dest.clicked.connect(self._choisir_dest_decoupe)
        self.c_ouvrir_dossier = QtWidgets.QCheckBox(tr("decoupe.ouvrir_dossier"))
        self.c_ouvrir_dossier.setChecked(self.reglages.value("ouvrir_dossier", True, type=bool))
        ld.addWidget(self.r_dest_auto, 0, 0, 1, 3)
        ld.addWidget(self.r_dest_choisi, 1, 0)
        ld.addWidget(self.e_dest, 1, 1)
        ld.addWidget(b_dest, 1, 2)
        ld.addWidget(self.c_ouvrir_dossier, 2, 0, 1, 3)
        ld.setColumnStretch(1, 1)
        self.r_dest_choisi.toggled.connect(lambda _: self._majeur_decoupe())
        gd.addWidget(dest)

        bas = QtWidgets.QHBoxLayout()
        self.barre_d = QtWidgets.QProgressBar()
        self.barre_d.hide()
        bas.addWidget(self.barre_d, 1)
        self.b_decouper = QtWidgets.QPushButton(tr("bouton.decouper"))
        self.b_decouper.setObjectName("principal")
        self.b_decouper.setMinimumHeight(46)
        self.b_decouper.setMinimumWidth(210)
        f = self.b_decouper.font()
        f.setWeight(QtGui.QFont.Weight.DemiBold)
        f.setPointSizeF(f.pointSizeF() * 1.25)
        self.b_decouper.setFont(f)
        self.b_decouper.clicked.connect(self._decouper_ou_annuler)
        bas.addStretch(1)
        bas.addWidget(self.b_decouper)
        gd.addLayout(bas)
        self.signaux.progression_d.connect(self._progression_d)
        self.signaux.fini_d.connect(self._fin_decoupe)
        self._decoupe_en_cours = False
        self._annuler_d = threading.Event()
        self._majeur_decoupe()

    def ajouter_a_decouper(self, elements):
        """PDF, images ou documents : les non-PDF sont convertis à l'analyse,
        puis découpés comme un PDF (un Word de 6 pages donne 6 PDF)."""
        deja = {self.liste_d.item(i).data(ROLE_CHEMIN) for i in range(self.liste_d.count())}
        nouveaux = [p for p in moteur.lister_pdf(elements) if str(p) not in deja]
        for p in nouveaux:
            it = QtWidgets.QListWidgetItem(f"{p.name}   —   {tr('liste.analyse')}")
            it.setData(ROLE_CHEMIN, str(p))
            it.setToolTip(str(p))
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
            self.liste_d.addItem(it)
        if nouveaux:
            threading.Thread(target=self._analyser_fond, args=(nouveaux,),
                             daemon=True, name="tutti-analyse-d").start()
        self._majeur_decoupe()

    def _infos_d(self):
        return [self.liste_d.item(i).data(ROLE_INFO) for i in range(self.liste_d.count())]

    def _choisir_a_decouper(self):
        fichiers, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, tr("dlg.ouvrir_pdf"), self._dernier_dossier(), self._filtre_entrees())
        if fichiers:
            self._memoriser_dossier(Path(fichiers[0]).parent)
            self.ajouter_a_decouper(fichiers)

    def _choisir_dest_decoupe(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, tr("decoupe.dest_choisi"),
                                                       self._dernier_dossier())
        if d:
            self.e_dest.setText(d)
            self.r_dest_choisi.setChecked(True)
        self._majeur_decoupe()

    def _majeur_decoupe(self):
        libre = not self._decoupe_en_cours
        infos = self._infos_d()
        pret = (libre and self.liste_d.count() > 0
                and all(i is not None and i.utilisable for i in infos)
                and (self.r_pages.isChecked() or self.e_plages.text().strip())
                and (self.r_dest_auto.isChecked() or self.e_dest.text()))
        self.b_decouper.setEnabled(bool(pret) or self._decoupe_en_cours)
        self.bd_retirer.setEnabled(libre and bool(self.liste_d.selectedItems()))

    def _dossier_decoupe(self, source: Path) -> Path:
        if self.r_dest_choisi.isChecked() and self.e_dest.text():
            return Path(self.e_dest.text())
        return source.parent / f"{source.stem} - {tr('decoupe.pages')}"

    def _decouper_ou_annuler(self):
        if self._decoupe_en_cours:
            self._annuler_d.set()
            self.b_decouper.setEnabled(False)
            self.b_decouper.setText(tr("bouton.annulation"))
            return
        travaux = []
        for info in self._infos_d():
            s, nb = info.chemin, info.pages
            try:
                plages = (moteur.lire_plages(self.e_plages.text(), nb)
                          if self.r_plages.isChecked() else moteur.plages_par_page(nb))
            except ErreurTutti as e:
                QtWidgets.QMessageBox.warning(self, "Tutti", f"{s.name} :\n{e}")
                return
            dossier = self._dossier_decoupe(s)
            travaux.append((s, info.pdf or s, dossier, plages,
                            [dossier / n for n in moteur.noms_decoupe(s, plages, nb)]))
        existants = [c for *_, cibles in travaux for c in cibles if c.exists()]
        if existants:
            r = QtWidgets.QMessageBox.question(
                self, "Tutti", tr("decoupe.remplacer", n=len(existants)),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.reglages.setValue("ouvrir_dossier", self.c_ouvrir_dossier.isChecked())
        total = sum(len(t[3]) for t in travaux)
        self._decoupe_en_cours = True
        self._annuler_d.clear()
        self.barre_d.setRange(0, max(1, total))
        self.barre_d.setValue(0)
        self.barre_d.show()
        self.b_decouper.setText(tr("bouton.annuler"))
        self.liste_d.setEnabled(False)
        self._majeur_decoupe()

        def travail():
            ecrits, deja = [], 0
            try:
                for s, lire, dossier, plages, _ in travaux:
                    base = deja
                    fichiers = moteur.decouper(
                        lire, dossier, plages, original=s, annule=self._annuler_d.is_set,
                        progression=lambda f, t, nom, b=base: self.signaux.progression_d.emit(
                            b + f, total, nom))
                    ecrits.extend(fichiers)
                    deja += len(plages)
                self.signaux.fini_d.emit(ecrits, None)
            except AssemblageAnnule:
                self.signaux.fini_d.emit(ecrits, "")
            except ErreurTutti as e:
                self.signaux.fini_d.emit(ecrits, str(e))
            except Exception as e:
                self.signaux.fini_d.emit(ecrits, tr("err.inattendue_assemblage", detail=type(e).__name__))
                raise

        threading.Thread(target=travail, daemon=True, name="tutti-decoupe").start()

    def _progression_d(self, fait, total, nom):
        self.barre_d.setRange(0, total)
        self.barre_d.setValue(fait)
        self.barre_d.setFormat(f"{nom}  (%p %)" if fait < total else tr("statut.termine"))

    def _fin_decoupe(self, ecrits, erreur):
        self._decoupe_en_cours = False
        self.barre_d.hide()
        self.b_decouper.setText(tr("bouton.decouper"))
        self.liste_d.setEnabled(True)
        self._majeur_decoupe()
        if erreur is not None:
            if erreur == "":
                self.statusBar().showMessage(tr("statut.annule_decoupe", n=len(ecrits)), 8000)
            else:
                QtWidgets.QMessageBox.warning(self, "Tutti", erreur)
            return
        self.statusBar().showMessage(tr("decoupe.fini", n=len(ecrits)), 10000)
        if ecrits and self.c_ouvrir_dossier.isChecked():
            for d in dict.fromkeys(p.parent for p in ecrits):
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(d)))

    def _construire_menus(self):
        m = self.menuBar().addMenu(tr("menu.fichier"))
        a = m.addAction(tr("bouton.ajouter"), self._choisir_fichiers)
        a.setShortcut("Ctrl+O")
        m.addAction(tr("bouton.dossier"), self._choisir_dossier)
        m.addSeparator()
        m.addAction(tr("menu.quitter"), self.close).setShortcut("Ctrl+Q")

        lg = self.menuBar().addMenu(tr("menu.langue"))
        groupe = QtGui.QActionGroup(self)
        choisie = self.reglages.value("langue", "auto", type=str)
        for code, libelle in (("auto", tr("menu.langue.auto")), ("fr", "Français"),
                              ("en", "English")):
            act = lg.addAction(libelle)
            act.setCheckable(True)
            act.setChecked(code == choisie)
            act.triggered.connect(lambda _=False, c=code: self._changer_langue(c))
            groupe.addAction(act)

        aide = self.menuBar().addMenu(tr("menu.aide"))
        aide.addAction(tr("menu.manuel"), self._ouvrir_manuel).setShortcut("F1")
        aide.addAction(tr("menu.mode_emploi"), self._afficher_aide)
        aide.addSeparator()
        aide.addAction(tr("menu.maj"), lambda: self._check_update(manual=True))
        aide.addAction(tr("menu.signaler"), self._signaler_probleme)
        self.act_autoreport = aide.addAction(tr("menu.rapports_auto"))
        self.act_autoreport.setCheckable(True)
        try:
            import reporting
            self.act_autoreport.setChecked(reporting.consentement() is True)
        except Exception:
            self.act_autoreport.setEnabled(False)
        self.act_autoreport.toggled.connect(self._basculer_rapports)
        aide.addSeparator()
        aide.addAction(tr("menu.a_propos"), self._a_propos)

    # ------------------------------------------------------------ liste
    def chemins(self) -> list[Path]:
        return [Path(self.liste.item(i).data(ROLE_CHEMIN)) for i in range(self.liste.count())]

    def ajouter(self, elements):
        """Ajoute des fichiers ou des dossiers, puis les analyse en fond."""
        deja = {os.path.normcase(str(p.resolve())) for p in self.chemins()}
        nouveaux = [p for p in moteur.lister_pdf(elements)
                    if os.path.normcase(str(p.resolve())) not in deja]
        ignores = [e for e in elements
                   if not Path(e).is_dir() and Path(e).suffix.lower() not in moteur.EXTENSIONS]
        if ignores:
            self.statusBar().showMessage(
                tr("statut.ignores", n=len(ignores)), 6000)
        if not nouveaux:
            if not ignores:
                self.statusBar().showMessage(tr("statut.rien"), 4000)
            return
        if self.liste.count() == 0:
            self._definir_dossier(nouveaux[0].parent)
        for p in nouveaux:
            it = QtWidgets.QListWidgetItem(f"{p.name}   —   {tr('liste.analyse')}")
            it.setData(ROLE_CHEMIN, str(p))
            it.setToolTip(str(p))
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
            self.liste.addItem(it)
        self._analyses_en_cours += 1
        threading.Thread(target=self._analyser_fond, args=(nouveaux,),
                         daemon=True, name="tutti-analyse").start()
        self._liste_changee()

    def _analyser_fond(self, chemins):
        try:
            moteur.analyser_tous(chemins, rappel=self.signaux.analyse.emit,
                                 dossier_conversions=self._dossier_conv)
        finally:
            self.signaux.analyse_finie.emit()

    def _item_pour(self, chemin: Path):
        """L'élément d'un fichier, dans l'une ou l'autre des deux listes."""
        cle = str(chemin)
        for liste in (self.liste, getattr(self, "liste_d", None)):
            if liste is None:
                continue
            for i in range(liste.count()):
                if liste.item(i).data(ROLE_CHEMIN) == cle and liste.item(i).data(ROLE_INFO) is None:
                    return liste.item(i)
        return None

    def _recevoir_analyse(self, info: InfoPdf):
        it = self._item_pour(info.chemin)
        if it is None:                       # retiré entre-temps
            return
        it.setData(ROLE_INFO, info)
        style = self.style()
        if info.utilisable:
            mo = info.taille / 1_048_576
            taille = (tr("taille.mo", v=f"{mo:.1f}") if mo >= 0.1
                      else tr("taille.ko", v=info.taille // 1024 + 1))
            pages = tr("liste.page" if info.pages == 1 else "liste.pages", n=info.pages)
            genre = "" if info.genre == "pdf" else f" ({tr('genre.' + info.genre)})"
            it.setText(f"{info.chemin.name}   —   {pages}, {taille}{genre}")
            it.setIcon(style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon))
            it.setForeground(self.palette().color(QtGui.QPalette.ColorRole.Text))
        else:
            it.setText(f"{info.chemin.name}   —   {info.erreur}")
            it.setIcon(style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning))
            it.setForeground(QtGui.QColor("#B5382B"))
        self._majeur_etat()
        if hasattr(self, "liste_d"):
            self._majeur_decoupe()

    def _analyse_finie(self):
        self._analyses_en_cours = max(0, self._analyses_en_cours - 1)
        self._majeur_etat()

    def mode_livret(self) -> str:
        return self.cb_livret.currentData() or "" if hasattr(self, "cb_livret") else ""

    def _livret_bascule(self):
        self.c_signets.setEnabled(not self.mode_livret())   # pas de signets dans un livret
        self._liste_changee()

    def _liste_changee(self):
        if self._nom_auto:
            self.e_nom.setText(moteur.proposer_nom(self.chemins(), livret=bool(self.mode_livret()))
                               if self.liste.count() else "")
        self._majeur_etat()

    def _deplacer(self, sens: int):
        lignes = sorted({self.liste.row(i) for i in self.liste.selectedItems()},
                        reverse=sens > 0)
        if not lignes:
            return
        if (sens < 0 and lignes[0] == 0) or (sens > 0 and lignes[0] == self.liste.count() - 1):
            return
        for r in lignes:
            it = self.liste.takeItem(r)
            self.liste.insertItem(r + sens, it)
        for r in lignes:
            self.liste.item(r + sens).setSelected(True)
        self._liste_changee()

    def _trier(self):
        items = [self.liste.takeItem(0) for _ in range(self.liste.count())]
        items.sort(key=lambda it: moteur.cle_naturelle(Path(it.data(ROLE_CHEMIN)).name))
        for it in items:
            self.liste.addItem(it)
        self._liste_changee()

    def _retirer(self):
        for it in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(it))
        self._liste_changee()

    def _vider(self):
        self.liste.clear()
        self._nom_auto = True
        self._liste_changee()

    # ------------------------------------------------------------ sortie
    def _definir_dossier(self, dossier: Path):
        self.e_dossier.setText(str(dossier))

    def _nom_retouche(self, texte):
        self._nom_auto = not texte.strip()

    def _choisir_destination(self):
        depart = str(Path(self.e_dossier.text() or Path.home()) /
                     (self.e_nom.text() or moteur.proposer_nom([])))
        chemin, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, tr("dlg.enregistrer"), depart, tr("dlg.filtre"))
        if chemin:
            p = Path(chemin)
            if p.suffix.lower() != ".pdf":
                p = p.with_name(p.name + ".pdf")
            self.e_dossier.setText(str(p.parent))
            self.e_nom.setText(p.name)
            self._nom_auto = False

    def _chemin_sortie(self) -> Path | None:
        nom = self.e_nom.text().strip()
        if not nom or not self.e_dossier.text():
            return None
        nom = "".join(c for c in nom if c not in '<>:"/\\|?*').strip(" .")
        if not nom:
            return None
        if not nom.lower().endswith(".pdf"):
            nom += ".pdf"
        return Path(self.e_dossier.text()) / nom

    def _choisir_fichiers(self):
        fichiers, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, tr("dlg.ouvrir_pdf"), self._dernier_dossier(), self._filtre_entrees())
        if fichiers:
            self._memoriser_dossier(Path(fichiers[0]).parent)
            self.ajouter(fichiers)

    def _choisir_dossier(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, tr("dlg.ouvrir_dossier"), self._dernier_dossier())
        if d:
            self._memoriser_dossier(Path(d))
            self.ajouter([d])

    def _dernier_dossier(self) -> str:
        d = self.reglages.value("dernier_dossier", "", type=str)
        return d if d and Path(d).is_dir() else str(Path.home() / "Desktop")

    def _memoriser_dossier(self, d: Path):
        self.reglages.setValue("dernier_dossier", str(d))

    # ------------------------------------------------------------ état
    def _infos(self) -> list[InfoPdf | None]:
        return [self.liste.item(i).data(ROLE_INFO) for i in range(self.liste.count())]

    def _majeur_etat(self):
        infos = self._infos()
        n = len(infos)
        prets = [i for i in infos if i is not None and i.utilisable]
        mauvais = [i for i in infos if i is not None and not i.utilisable]
        attente = n - len(prets) - len(mauvais)
        pages = sum(i.pages for i in prets)
        if n == 0:
            self.resume.setText("")
        else:
            txt = tr("resume.fichier" if n == 1 else "resume.fichiers", n=n, p=pages)
            if attente:
                txt += tr("resume.attente", n=attente)
            if mauvais:
                txt += ("<span style='color:#B5382B'>"
                        + tr("resume.mauvais", n=len(mauvais)) + "</span>")
            self.resume.setText(txt)
        sel = bool(self.liste.selectedItems())
        libre = not self._en_cours
        for b in (self.b_monter, self.b_descendre, self.b_retirer):
            b.setEnabled(sel and libre)
        for b in (self.b_ajouter, self.b_dossier, self.b_trier, self.b_vider):
            b.setEnabled(libre)
        self.liste.setEnabled(libre)
        pret = (libre and n > 0 and attente == 0 and not mauvais
                and self._chemin_sortie() is not None)
        self.b_assembler.setEnabled(pret or self._en_cours)

    # ------------------------------------------------------------ assemblage
    def _assembler_ou_annuler(self):
        if self._en_cours:
            self._annuler.set()
            self.b_assembler.setEnabled(False)
            self.b_assembler.setText(tr("bouton.annulation"))
            return
        sortie = self._chemin_sortie()
        sources = self.chemins()
        if sortie is None or not sources:
            return
        try:
            moteur.verifier_sortie(sortie, sources)
        except ErreurTutti as e:
            QtWidgets.QMessageBox.warning(self, "Tutti", str(e))
            return
        if sortie.exists():
            r = QtWidgets.QMessageBox.question(
                self, "Tutti", tr("dlg.remplacer", nom=sortie.name),
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        for cle, case in (("signets", self.c_signets), ("recto", self.c_recto),
                          ("ouvrir", self.c_ouvrir)):
            self.reglages.setValue(cle, case.isChecked())
        options = Options(signets=self.c_signets.isChecked(), recto=self.c_recto.isChecked(),
                          livret=self.mode_livret())
        self.reglages.setValue("livret_mode", self.mode_livret())
        self._livret_en_cours = options.livret
        converties = {str(i.chemin): i.pdf for i in self._infos()
                      if i is not None and i.genre != "pdf" and i.pdf}
        self._en_cours = True
        self._annuler.clear()
        self._sortie = sortie
        self.barre.setRange(0, len(sources) + 1)
        self.barre.setValue(0)
        self.barre.show()
        self.b_assembler.setText(tr("bouton.annuler"))
        self._majeur_etat()

        def travail():
            try:
                n = moteur.assembler(sources, sortie, options,
                                     progression=self.signaux.progression.emit,
                                     annule=self._annuler.is_set, converties=converties)
                self.signaux.fini.emit(n, None)
            except AssemblageAnnule:
                self.signaux.fini.emit(None, "")
            except ErreurTutti as e:
                self.signaux.fini.emit(None, str(e))
            except Exception as e:           # remonté aux rapports par le filet global
                self.signaux.fini.emit(None, tr("err.inattendue_assemblage", detail=type(e).__name__))
                raise

        threading.Thread(target=travail, daemon=True, name="tutti-assemblage").start()

    def _progression(self, fait, total, nom):
        self.barre.setRange(0, total)
        self.barre.setValue(fait)
        self.barre.setFormat(f"{nom}  (%p %)" if fait < total else tr("statut.termine"))

    def _fin_assemblage(self, pages, erreur):
        self._en_cours = False
        self.barre.hide()
        self.b_assembler.setText(tr("bouton.assembler"))
        self._majeur_etat()
        if erreur is not None:
            if erreur == "":
                self.statusBar().showMessage(tr("statut.annule"), 6000)
            else:
                QtWidgets.QMessageBox.warning(self, "Tutti", erreur)
            return
        sortie = self._sortie
        self.statusBar().showMessage(tr("statut.cree", nom=sortie.name, p=pages), 10000)
        livret = getattr(self, "_livret_en_cours", "")
        if livret:
            QtWidgets.QMessageBox.information(
                self, tr("options.titre"),
                tr({"a5": "livret.conseil", "a4": "livret.conseil_a4"}.get(livret,
                                                                           "livret.conseil_ordre")))
        self.proposer_ouverture(sortie, pages)

    def proposer_ouverture(self, sortie: Path, pages: int, message: str | None = None):
        """Fin d'un travail qui a produit un PDF : on l'ouvre directement si la
        case « Ouvrir le PDF une fois terminé » est cochée, sinon on propose."""
        if self.c_ouvrir.isChecked():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(sortie)))
        else:
            boite = QtWidgets.QMessageBox(self)
            boite.setWindowTitle("Tutti")
            boite.setIcon(QtWidgets.QMessageBox.Icon.Information)
            texte = tr("dlg.pret", nom=sortie.name, p=pages)
            boite.setText(texte + ("\n\n" + message if message else ""))
            ouvrir = boite.addButton(tr("dlg.ouvrir"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            dossier = boite.addButton(tr("dlg.ouvrir_dossier_resultat"),
                                      QtWidgets.QMessageBox.ButtonRole.ActionRole)
            boite.addButton(tr("dlg.fermer"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            boite.exec()
            if boite.clickedButton() is ouvrir:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(sortie)))
            elif boite.clickedButton() is dossier:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(sortie.parent)))

    def closeEvent(self, ev):
        if not self.onglet_pages.confirmer_abandon():
            ev.ignore()
            return
        if (self._en_cours or getattr(self, "_decoupe_en_cours", False)
                or self.onglet_pages.en_cours or self.onglet_finitions.en_cours):
            r = QtWidgets.QMessageBox.question(
                self, "Tutti", tr("dlg.quitter_en_cours"))
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                ev.ignore()
                return
            self._annuler.set()
            self.onglet_finitions._annuler.set()
        shutil.rmtree(self._dossier_conv, ignore_errors=True)
        super().closeEvent(ev)

    # ------------------------------------------------------------ aide
    def _afficher_aide(self):
        QtWidgets.QMessageBox.information(self, tr("aide.titre"), tr("aide.texte"))

    def _ouvrir_manuel(self):
        """Manuel PDF dans la langue de l'interface (docs/manuel-fr.pdf, -en.pdf)."""
        docs = Path(__file__).resolve().parent.parent / "docs"
        for nom in (f"manuel-{langue()}.pdf", "manuel-en.pdf", "manuel-fr.pdf"):
            if (docs / nom).exists():
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(docs / nom)))
                return
        QtWidgets.QMessageBox.information(self, "Tutti", tr("manuel.absent"))

    def _changer_langue(self, code: str):
        self.reglages.setValue("langue", code)
        QtWidgets.QMessageBox.information(self, "Tutti", tr("menu.langue.redemarrer"))

    def _a_propos(self):
        # le logo est le même fichier que l'icône (une seule source : logo.svg)
        boite = QtWidgets.QMessageBox(self)
        boite.setWindowTitle(tr("menu.a_propos"))
        logo = Path(__file__).resolve().parent.parent / "logo_128.png"
        if logo.exists():
            boite.setIconPixmap(QtGui.QPixmap(str(logo)))
        boite.setText(tr("a_propos.texte", version=__version__))
        boite.exec()

    def _basculer_rapports(self, coche: bool):
        try:
            import reporting
            reporting.definir_consentement(bool(coche))
        except Exception:
            pass

    # ------------------------------------------------------------ mise à jour
    # Dispositif du kit Windows (identique à MusicOthèque, Anticythere3D…) :
    # archive ZIP déballée par le programme, jamais d'exécutable téléchargé.
    _maj_signal = QtCore.pyqtSignal(object, bool)

    def _check_update(self, manual: bool = False):
        if not hasattr(self, "_maj_branche"):
            self._maj_signal.connect(self._update_result)
            self._maj_branche = True
        if manual:
            self.statusBar().showMessage(tr("maj.recherche"))

        def worker():
            try:
                import updater
                info = updater.check(__version__)
            except Exception:
                info = None
            self._maj_signal.emit(info, manual)

        threading.Thread(target=worker, daemon=True, name="tutti-maj").start()

    def _update_result(self, info, manual: bool):
        self.statusBar().clearMessage()
        if not info:
            if manual:
                QtWidgets.QMessageBox.information(
                    self, tr("maj.titre"), tr("maj.a_jour", version=__version__))
            return
        try:
            import updater
            installe = bool(updater.is_packaged())
            page = f"https://github.com/{updater.REPO}/releases/latest"
        except Exception:
            installe, page = False, ""
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(tr("maj.titre"))
        box.setText(tr("maj.dispo", nouvelle=info["version"], version=__version__))
        notes = (info.get("notes") or "").strip()
        try:
            import updater
            notes = updater.notes_dans_la_langue(notes, langue())
        except Exception:
            pass
        if notes:
            box.setDetailedText(notes[:4000])
        oui = box.addButton(tr("maj.installer") if installe else tr("maj.page"),
                            QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("maj.plus_tard"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not oui:
            return
        if not installe:
            if page:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(page))
            return
        self._telecharger_maj(info)

    def _telecharger_maj(self, info: dict):
        import updater
        dlg = QtWidgets.QProgressDialog(tr("maj.telechargement"), None, 0, 100, self)
        dlg.setWindowTitle(tr("maj.titre"))
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        etat = {"fait": 0, "total": 0, "fini": False, "erreur": None, "pose": False}

        def _prog(done, total):
            etat["fait"], etat["total"] = done, total

        def worker():
            try:
                etat["pose"] = bool(updater.download_and_apply(info, progress=_prog))
            except Exception as exc:
                etat["erreur"] = exc
            finally:
                etat["fini"] = True

        threading.Thread(target=worker, daemon=True, name="tutti-maj-pose").start()
        poll = QtCore.QTimer(self)
        poll.setInterval(100)

        def tick():
            if not etat["fini"]:
                if etat["total"] > 0:
                    dlg.setValue(min(99, etat["fait"] * 100 // etat["total"]))
                return
            poll.stop()
            dlg.close()
            if etat["erreur"] is not None or not etat["pose"]:
                texte = str(etat["erreur"] or "archive invalide")
                verrou = ("WinError 32" in texte or "used by another process" in texte
                          or isinstance(etat["erreur"], PermissionError))
                QtWidgets.QMessageBox.warning(
                    self, tr("maj.titre"),
                    tr("maj.verrou") if verrou else tr("maj.echec", erreur=texte))
                return
            QtWidgets.QMessageBox.information(self, tr("maj.titre"), tr("maj.redemarre"))
            try:
                updater.restart()
            finally:
                QtWidgets.QApplication.quit()

        poll.timeout.connect(tick)
        poll.start()
        self._maj_poll = poll

    # ------------------------------------------------------------ rapports
    def _signaler_probleme(self):
        try:
            import reporting
        except Exception:
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(tr("signal.titre"))
        dlg.resize(560, 360)
        lo = QtWidgets.QVBoxLayout(dlg)
        lo.addWidget(QtWidgets.QLabel(tr("signal.invite")))
        texte = QtWidgets.QPlainTextEdit()
        texte.setPlaceholderText(tr("signal.exemple"))
        lo.addWidget(texte)
        note = QtWidgets.QLabel(tr("signal.note"))
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        lo.addWidget(note)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                          | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btns.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(tr("signal.envoyer"))
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lo.addWidget(btns)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        description = texte.toPlainText().strip()
        if not description:
            return
        accord = reporting.consentement()
        if accord is not True:
            reporting.definir_consentement(True)
        rapport = reporting.envoyer("manuel", description=description, version=__version__,
                                    fichiers=self.liste.count())
        if accord is not True:
            reporting.definir_consentement(bool(accord))
        chemin = None
        try:
            chemin = reporting.paquet_local(rapport, None)
        except Exception:
            pass
        msg = (tr("signal.parti") if rapport.get("transmis", True) and not chemin
               else tr("signal.local", chemin=chemin))
        QtWidgets.QMessageBox.information(self, tr("signal.merci"), msg)
