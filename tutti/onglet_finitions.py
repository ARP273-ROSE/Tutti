"""Onglet « Finitions » : numéroter les pages, écrire un texte en tête de
page, alléger le fichier pour l'envoyer par e-mail — sur un ou plusieurs
documents à la fois (toutes les parties d'une partition, par exemple).

Chaque document donne un nouveau fichier ; l'original n'est jamais modifié.
"""
from __future__ import annotations

import threading
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from . import moteur, pages
from .i18n import tr
from .moteur import AssemblageAnnule, ErreurTutti

ROLE_CHEMIN = QtCore.Qt.ItemDataRole.UserRole
ROLE_INFO = QtCore.Qt.ItemDataRole.UserRole + 1


class _Signaux(QtCore.QObject):
    progression = QtCore.pyqtSignal(int, int, str)
    fini = QtCore.pyqtSignal(object, object)     # (bilans [(sortie, Bilan)], erreur | None)


def _taille(octets: int) -> str:
    mo = octets / 1_048_576
    return tr("taille.mo", v=f"{mo:.1f}") if mo >= 0.1 else tr("taille.ko", v=octets // 1024 + 1)


class OngletFinitions(QtWidgets.QWidget):
    def __init__(self, fenetre, liste_classe):
        super().__init__()
        self.fenetre = fenetre
        self.reglages = fenetre.reglages
        self.en_cours = False
        self._annuler = threading.Event()
        self.signaux = _Signaux()
        self.signaux.progression.connect(self._progression)
        self.signaux.fini.connect(self._fin)
        self._construire(liste_classe)
        self._majeur()

    # ------------------------------------------------------------ interface
    def _construire(self, liste_classe):
        g = QtWidgets.QVBoxLayout(self)
        g.setContentsMargins(8, 10, 8, 8)

        ligne = QtWidgets.QHBoxLayout()
        self.liste = liste_classe(texte_vide=tr("finir.liste_vide"))
        self.liste.deposes.connect(self.ajouter)
        self.liste.itemSelectionChanged.connect(self._majeur)
        ligne.addWidget(self.liste, 1)
        bd = QtWidgets.QVBoxLayout()
        b = QtWidgets.QPushButton(tr("bouton.ajouter"))
        b.clicked.connect(self._choisir)
        bd.addWidget(b)
        self.b_retirer = QtWidgets.QPushButton(tr("bouton.retirer"))
        self.b_retirer.clicked.connect(self._retirer)
        bd.addWidget(self.b_retirer)
        bv = QtWidgets.QPushButton(tr("bouton.vider"))
        bv.clicked.connect(lambda: (self.liste.clear(), self._majeur()))
        bd.addWidget(bv)
        bd.addStretch(1)
        ligne.addLayout(bd)
        g.addLayout(ligne, 1)

        # Numéros de page
        num = QtWidgets.QGroupBox(tr("finir.numeros"))
        ln = QtWidgets.QGridLayout(num)
        self.c_numeros = QtWidgets.QCheckBox(tr("finir.numeroter"))
        self.cb_position = QtWidgets.QComboBox()
        for code in pages.POSITIONS:
            self.cb_position.addItem(tr(f"finir.position.{code}"), code)
        self.cb_format = QtWidgets.QComboBox()
        for code in pages.FORMATS:
            self.cb_format.addItem(tr(f"finir.format.{code}"), code)
        self.s_premier = QtWidgets.QSpinBox()
        self.s_premier.setRange(1, 9999)
        self.s_premier.setMaximumWidth(110)
        self.c_sauter = QtWidgets.QCheckBox(tr("finir.sauter_premiere"))
        ln.addWidget(self.c_numeros, 0, 0, 1, 4)
        ln.addWidget(QtWidgets.QLabel(tr("finir.ou")), 1, 0)
        ln.addWidget(self.cb_position, 1, 1)
        ln.addWidget(QtWidgets.QLabel(tr("finir.forme")), 1, 2)
        ln.addWidget(self.cb_format, 1, 3)
        ln.addWidget(QtWidgets.QLabel(tr("finir.premier")), 2, 0)
        ln.addWidget(self.s_premier, 2, 1)
        ln.addWidget(self.c_sauter, 2, 2, 1, 2)
        ln.setColumnStretch(1, 1)
        ln.setColumnStretch(3, 1)
        g.addWidget(num)

        # Texte en haut de page
        tete = QtWidgets.QGroupBox(tr("finir.texte_titre"))
        lt = QtWidgets.QHBoxLayout(tete)
        self.e_texte = QtWidgets.QLineEdit()
        self.e_texte.setPlaceholderText(tr("finir.texte_exemple"))
        self.e_texte.setMaxLength(160)
        self.cb_partout = QtWidgets.QComboBox()
        self.cb_partout.addItem(tr("finir.partout"), True)
        self.cb_partout.addItem(tr("finir.premiere_seule"), False)
        lt.addWidget(self.e_texte, 1)
        lt.addWidget(self.cb_partout)
        g.addWidget(tete)

        # Poids et destination
        autre = QtWidgets.QGroupBox(tr("finir.fichier"))
        la = QtWidgets.QGridLayout(autre)
        self.c_alleger = QtWidgets.QCheckBox(tr("finir.alleger"))
        self.c_alleger.setToolTip(tr("finir.alleger.astuce"))
        self.r_dest_auto = QtWidgets.QRadioButton(tr("finir.dest_auto"))
        self.r_dest_choisi = QtWidgets.QRadioButton(tr("decoupe.dest_choisi"))
        self.r_dest_auto.setChecked(True)
        self.e_dest = QtWidgets.QLineEdit()
        self.e_dest.setReadOnly(True)
        b_dest = QtWidgets.QPushButton(tr("bouton.choisir"))
        b_dest.clicked.connect(self._choisir_dest)
        la.addWidget(self.c_alleger, 0, 0, 1, 3)
        la.addWidget(self.r_dest_auto, 1, 0, 1, 3)
        la.addWidget(self.r_dest_choisi, 2, 0)
        la.addWidget(self.e_dest, 2, 1)
        la.addWidget(b_dest, 2, 2)
        la.setColumnStretch(1, 1)
        g.addWidget(autre)

        bas = QtWidgets.QHBoxLayout()
        self.barre = QtWidgets.QProgressBar()
        self.barre.hide()
        bas.addWidget(self.barre, 1)
        bas.addStretch(1)
        self.b_appliquer = QtWidgets.QPushButton(tr("finir.appliquer"))
        self.b_appliquer.setObjectName("principal")
        self.b_appliquer.setMinimumHeight(46)
        self.b_appliquer.setMinimumWidth(210)
        f = self.b_appliquer.font()
        f.setWeight(QtGui.QFont.Weight.DemiBold)
        f.setPointSizeF(f.pointSizeF() * 1.25)
        self.b_appliquer.setFont(f)
        self.b_appliquer.clicked.connect(self._appliquer_ou_annuler)
        bas.addWidget(self.b_appliquer)
        g.addLayout(bas)

        # Réglages retenus d'une fois sur l'autre
        r = self.reglages
        self.c_numeros.setChecked(r.value("finir_numeros", True, type=bool))
        self.cb_position.setCurrentIndex(max(0, self.cb_position.findData(
            r.value("finir_position", "bas_centre", type=str))))
        self.cb_format.setCurrentIndex(max(0, self.cb_format.findData(
            r.value("finir_format", "n", type=str))))
        self.c_sauter.setChecked(r.value("finir_sauter", False, type=bool))
        self.c_alleger.setChecked(r.value("finir_alleger", False, type=bool))
        for w in (self.c_numeros, self.c_alleger, self.r_dest_choisi):
            w.toggled.connect(lambda _: self._majeur())
        self.e_texte.textChanged.connect(lambda _: self._majeur())

    # ------------------------------------------------------------ liste
    def chemins(self) -> list[Path]:
        return [Path(self.liste.item(i).data(ROLE_CHEMIN)) for i in range(self.liste.count())]

    def ajouter(self, elements):
        deja = {str(p) for p in self.chemins()}
        nouveaux = [p for p in moteur.lister_pdf(elements) if str(p) not in deja]
        for p in nouveaux:
            it = QtWidgets.QListWidgetItem(p.name)
            it.setData(ROLE_CHEMIN, str(p))
            it.setToolTip(str(p))
            it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsDropEnabled)
            it.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon))
            self.liste.addItem(it)
        self._majeur()

    def _choisir(self):
        fichiers, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, tr("finir.ouvrir_titre"), self.fenetre._dernier_dossier(),
            self.fenetre._filtre_entrees())
        if fichiers:
            self.fenetre._memoriser_dossier(Path(fichiers[0]).parent)
            self.ajouter(fichiers)

    def _retirer(self):
        for it in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(it))
        self._majeur()

    def _choisir_dest(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, tr("decoupe.dest_choisi"),
                                                       self.fenetre._dernier_dossier())
        if d:
            self.e_dest.setText(d)
            self.r_dest_choisi.setChecked(True)
        self._majeur()

    # ------------------------------------------------------------ état
    def finitions(self) -> pages.Finitions:
        return pages.Finitions(
            numeros=self.cb_position.currentData() if self.c_numeros.isChecked() else "",
            format_numero=self.cb_format.currentData(),
            premier=self.s_premier.value(),
            sauter_premiere=self.c_sauter.isChecked(),
            texte=self.e_texte.text().strip(),
            texte_partout=bool(self.cb_partout.currentData()),
            alleger=self.c_alleger.isChecked())

    def _majeur(self):
        libre = not self.en_cours
        num = self.c_numeros.isChecked()
        for w in (self.cb_position, self.cb_format, self.s_premier, self.c_sauter):
            w.setEnabled(num and libre)
        self.cb_partout.setEnabled(bool(self.e_texte.text().strip()) and libre)
        self.b_retirer.setEnabled(libre and bool(self.liste.selectedItems()))
        pret = (libre and self.liste.count() > 0 and not self.finitions().rien
                and (self.r_dest_auto.isChecked() or self.e_dest.text()))
        self.b_appliquer.setEnabled(bool(pret) or self.en_cours)

    def _sortie(self, source: Path) -> Path:
        dossier = (Path(self.e_dest.text()) if self.r_dest_choisi.isChecked() and self.e_dest.text()
                   else source.parent)
        return dossier / pages.nom_finitions(source)

    # ------------------------------------------------------------ travail
    def _appliquer_ou_annuler(self):
        if self.en_cours:
            self._annuler.set()
            self.b_appliquer.setEnabled(False)
            self.b_appliquer.setText(tr("bouton.annulation"))
            return
        finitions = self.finitions()
        travaux = [(s, self._sortie(s)) for s in self.chemins()]
        existants = [c for _, c in travaux if c.exists()]
        if existants:
            r = QtWidgets.QMessageBox.question(
                self, "Tutti", tr("decoupe.remplacer", n=len(existants)),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        r = self.reglages
        r.setValue("finir_numeros", self.c_numeros.isChecked())
        r.setValue("finir_position", self.cb_position.currentData())
        r.setValue("finir_format", self.cb_format.currentData())
        r.setValue("finir_sauter", self.c_sauter.isChecked())
        r.setValue("finir_alleger", self.c_alleger.isChecked())
        self.en_cours = True
        self._annuler.clear()
        self.barre.setRange(0, len(travaux))
        self.barre.setValue(0)
        self.barre.show()
        self.b_appliquer.setText(tr("bouton.annuler"))
        self.liste.setEnabled(False)
        self._majeur()
        dossier_conv = Path(self.fenetre._dossier_conv)
        total = len(travaux)

        def travail():
            bilans = []
            try:
                for n, (source, sortie) in enumerate(travaux):
                    self.signaux.progression.emit(n, total, source.name)
                    lire = source
                    if moteur.type_fichier(source) not in (None, "pdf"):
                        pdf, lire = pages.ouvrir(source, dossier_conv)
                        pdf.close()
                    bilans.append((sortie, pages.finir(lire, sortie, finitions, original=source,
                                                       annule=self._annuler.is_set)))
                self.signaux.progression.emit(total, total, "")
                self.signaux.fini.emit(bilans, None)
            except AssemblageAnnule:
                self.signaux.fini.emit(bilans, "")
            except ErreurTutti as e:
                self.signaux.fini.emit(bilans, str(e))
            except Exception as e:
                self.signaux.fini.emit(bilans, tr("err.inattendue_assemblage", detail=type(e).__name__))
                raise

        threading.Thread(target=travail, daemon=True, name="tutti-finitions").start()

    def _progression(self, fait, total, nom):
        self.barre.setRange(0, max(1, total))
        self.barre.setValue(fait)
        self.barre.setFormat(f"{nom}  (%p %)" if fait < total else tr("statut.termine"))

    def _fin(self, bilans, erreur):
        self.en_cours = False
        self.barre.hide()
        self.b_appliquer.setText(tr("finir.appliquer"))
        self.liste.setEnabled(True)
        self._majeur()
        if erreur is not None:
            if erreur == "":
                self.fenetre.statusBar().showMessage(tr("finir.annule", n=len(bilans)), 8000)
            else:
                QtWidgets.QMessageBox.warning(self, "Tutti", erreur)
            return
        avant = sum(b.taille_avant for _, b in bilans)
        apres = sum(b.taille_apres for _, b in bilans)
        message = tr("finir.fini", n=len(bilans))
        if self.c_alleger.isChecked():
            message += " " + tr("finir.poids", avant=_taille(avant), apres=_taille(apres))
        self.fenetre.statusBar().showMessage(message, 15000)
        if len(bilans) == 1:
            sortie, b = bilans[0]
            self.fenetre.proposer_ouverture(sortie, b.pages, message)
        elif bilans:
            boite = QtWidgets.QMessageBox(self)
            boite.setWindowTitle("Tutti")
            boite.setIcon(QtWidgets.QMessageBox.Icon.Information)
            boite.setText(message)
            dossier = boite.addButton(tr("dlg.ouvrir_dossier_resultat"),
                                      QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            boite.addButton(tr("dlg.fermer"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            boite.exec()
            if boite.clickedButton() is dossier:
                for d in dict.fromkeys(s.parent for s, _ in bilans):
                    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(d)))

    def confirmer_fermeture(self) -> bool:
        return not self.en_cours
