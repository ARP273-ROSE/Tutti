"""Onglet « Pages » : voir les pages d'un document en vignettes, les pivoter,
les retirer, les déplacer, puis enregistrer le résultat.

Les vignettes sont dessinées dans un fil de fond par QtPdf (le moteur de
rendu PDF de Qt, livré avec PyQt6) ; la fenêtre reste fluide même sur une
partition de 200 pages. Rien n'est écrit tant qu'on n'a pas cliqué sur
« Enregistrer » ; le document d'origine n'est jamais modifié.
"""
from __future__ import annotations

import threading
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from . import conversion, moteur, pages
from .i18n import tr
from .moteur import ErreurTutti

ROLE_PAGE = Qt.ItemDataRole.UserRole           # numéro de la page d'origine (dès 0)
ROLE_QUART = Qt.ItemDataRole.UserRole + 1      # rotation ajoutée, en degrés

BOITE = 132          # côté de la case d'une vignette, en pixels logiques
RENDU = 240          # hauteur de rendu (assez pour rester nette en 150 %)


def sur_blanc(image: QtGui.QImage) -> QtGui.QImage:
    """QtPdf rend la page sur fond transparent : sans papier blanc dessous, la
    vignette prendrait la couleur de ce qui est derrière (ombre, sélection)."""
    fond = QtGui.QImage(image.size(), QtGui.QImage.Format.Format_RGB32)
    fond.fill(QtGui.QColor("white"))
    p = QtGui.QPainter(fond)
    p.drawImage(0, 0, image)
    p.end()
    return fond


class _Signaux(QtCore.QObject):
    pret = QtCore.pyqtSignal(int, object, object, int)   # (génération, chemin lu, erreur, nb pages)
    vignette = QtCore.pyqtSignal(int, int, object)       # (génération, page, QImage)
    ecrit = QtCore.pyqtSignal(object, object)            # (nb pages | None, erreur | None)


class GrillePages(QtWidgets.QListWidget):
    """Vignettes en lignes qui se replient, réordonnables à la souris, et qui
    acceptent un document glissé depuis l'Explorateur."""
    deposes = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QtWidgets.QListView.ViewMode.ListMode)
        self.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.setMovement(QtWidgets.QListView.Movement.Snap)
        self.setIconSize(QtCore.QSize(BOITE, BOITE))
        self.setGridSize(QtCore.QSize(BOITE + 14, BOITE + 14))
        self.setUniformItemSizes(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(True)

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
            zone = self.viewport().rect().adjusted(20, 12, -20, -12)
            options = int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap)
            f = p.font()
            taille = f.pointSizeF() * 1.3
            texte = tr("pages.vide")
            while taille > 7:
                f.setPointSizeF(taille)
                boite = QtGui.QFontMetrics(f).boundingRect(zone, options, texte)
                if boite.width() <= zone.width() and boite.height() <= zone.height():
                    break
                taille -= 0.5
            p.setFont(f)
            p.drawText(zone, options, texte)
            p.end()


class OngletPages(QtWidgets.QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.fenetre = fenetre
        self.source: Path | None = None        # document choisi par l'utilisateur
        self.lu: Path | None = None            # PDF réellement lu (conversion éventuelle)
        self.nb_origine = 0
        self.images: dict[int, QtGui.QImage] = {}
        self.generation = 0
        self.en_cours = False
        self.signaux = _Signaux()
        self.signaux.pret.connect(self._document_pret)
        self.signaux.vignette.connect(self._vignette_recue)
        self.signaux.ecrit.connect(self._fin_ecriture)
        self._construire()
        self._majeur()

    # ------------------------------------------------------------ interface
    def _construire(self):
        g = QtWidgets.QVBoxLayout(self)
        g.setContentsMargins(8, 10, 8, 8)

        haut = QtWidgets.QHBoxLayout()
        self.l_document = QtWidgets.QLabel(tr("pages.aucun_document"))
        self.l_document.setObjectName("resume")
        self.l_document.setTextFormat(Qt.TextFormat.PlainText)
        haut.addWidget(self.l_document, 1)
        g.addLayout(haut)

        ligne = QtWidgets.QHBoxLayout()
        self.grille = GrillePages()
        self.grille.deposes.connect(lambda chemins: self.ouvrir(chemins[0]))
        self.grille.itemSelectionChanged.connect(self._majeur)
        self.grille.model().rowsMoved.connect(lambda *a: self._majeur())
        self.grille.itemDoubleClicked.connect(self._apercu)
        ligne.addWidget(self.grille, 1)

        boutons = QtWidgets.QVBoxLayout()

        def bouton(cle, action, raccourci=None, astuce=None):
            b = QtWidgets.QPushButton(tr(cle))
            b.clicked.connect(action)
            if raccourci:
                b.setShortcut(QtGui.QKeySequence(raccourci))
            if astuce:
                b.setToolTip(tr(astuce))
            boutons.addWidget(b)
            return b

        self.b_ouvrir = bouton("pages.ouvrir", self._choisir)
        boutons.addSpacing(12)
        self.b_gauche = bouton("pages.pivoter_gauche", lambda: self.pivoter(-90), "Ctrl+L",
                               "pages.pivoter_gauche.astuce")
        self.b_droite = bouton("pages.pivoter_droite", lambda: self.pivoter(90), "Ctrl+R",
                               "pages.pivoter_droite.astuce")
        self.b_retirer = bouton("bouton.retirer", self.retirer, "Del", "pages.retirer.astuce")
        boutons.addSpacing(12)
        self.b_tout = bouton("pages.tout", self.grille.selectAll, None, "pages.tout.astuce")
        self.b_revenir = bouton("pages.revenir", self.revenir, None, "pages.revenir.astuce")
        boutons.addStretch(1)
        ligne.addLayout(boutons)
        g.addLayout(ligne, 1)

        self.l_resume = QtWidgets.QLabel("")
        self.l_resume.setObjectName("resume")
        self.l_resume.setWordWrap(True)
        g.addWidget(self.l_resume)

        bas = QtWidgets.QHBoxLayout()
        self.barre = QtWidgets.QProgressBar()
        self.barre.hide()
        bas.addWidget(self.barre, 1)
        bas.addStretch(1)
        self.b_enregistrer = QtWidgets.QPushButton(tr("pages.enregistrer"))
        self.b_enregistrer.setObjectName("principal")
        self.b_enregistrer.setMinimumHeight(46)
        self.b_enregistrer.setMinimumWidth(210)
        f = self.b_enregistrer.font()
        f.setWeight(QtGui.QFont.Weight.DemiBold)
        f.setPointSizeF(f.pointSizeF() * 1.25)
        self.b_enregistrer.setFont(f)
        self.b_enregistrer.clicked.connect(self.enregistrer)
        bas.addWidget(self.b_enregistrer)
        g.addLayout(bas)

    # ------------------------------------------------------------ état
    def etat(self) -> list[tuple[int, int]]:
        """Ce qui sera écrit : (page d'origine, rotation ajoutée), dans l'ordre."""
        return [(self.grille.item(i).data(ROLE_PAGE), self.grille.item(i).data(ROLE_QUART) or 0)
                for i in range(self.grille.count())]

    def modifie(self) -> bool:
        return self.source is not None and self.etat() != [(i, 0) for i in range(self.nb_origine)]

    def _majeur(self):
        libre = not self.en_cours
        charge = self.grille.count() > 0
        sel = bool(self.grille.selectedItems())
        for b in (self.b_gauche, self.b_droite, self.b_retirer):
            b.setEnabled(libre and sel)
        self.b_tout.setEnabled(libre and charge)
        self.b_revenir.setEnabled(libre and self.modifie())
        self.b_ouvrir.setEnabled(libre)
        self.b_enregistrer.setEnabled(libre and charge)
        self.grille.setEnabled(libre)
        if self.source is None or not self.nb_origine:
            self.l_resume.setText("")
            return
        etat = self.etat()
        retirees = self.nb_origine - len({i for i, _ in etat})
        tournees = sum(1 for _, q in etat if q % 360)
        deplacees = [i for i, _ in etat] != sorted(i for i, _ in etat)
        morceaux = [tr("liste.page" if len(etat) == 1 else "liste.pages", n=len(etat))]
        if retirees:
            morceaux.append(tr("pages.resume_retirees", n=retirees))
        if tournees:
            morceaux.append(tr("pages.resume_tournees", n=tournees))
        if deplacees:
            morceaux.append(tr("pages.resume_deplacees"))
        if not (retirees or tournees or deplacees):
            morceaux.append(tr("pages.resume_intact"))
        self.l_resume.setText(" — ".join(morceaux))

    # ------------------------------------------------------------ ouverture
    def _choisir(self):
        fichier, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, tr("pages.ouvrir_titre"), self.fenetre._dernier_dossier(),
            self.fenetre._filtre_entrees())
        if fichier:
            self.fenetre._memoriser_dossier(Path(fichier).parent)
            self.ouvrir(fichier)

    def confirmer_abandon(self) -> bool:
        """Les changements non enregistrés seront perdus : on demande."""
        if not self.modifications_perdues():
            return True
        r = QtWidgets.QMessageBox.question(
            self, "Tutti", tr("pages.abandon", nom=self.source.name),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No)
        return r == QtWidgets.QMessageBox.StandardButton.Yes

    def ouvrir(self, chemin):
        p = Path(chemin)
        if p.is_dir() or conversion.type_fichier(p) is None:
            QtWidgets.QMessageBox.warning(self, "Tutti", tr("pages.format", nom=p.name))
            return
        if not self.confirmer_abandon():
            return
        self.generation += 1
        gen = self.generation
        self.source, self.lu, self.nb_origine = p, None, 0
        self._sauve = None
        self.images.clear()
        self.grille.clear()
        self.l_document.setText(tr("pages.chargement", nom=p.name))
        self._majeur()
        dossier = Path(self.fenetre._dossier_conv)
        threading.Thread(target=self._charger, args=(gen, p, dossier), daemon=True,
                         name="tutti-vignettes").start()

    def _charger(self, gen: int, source: Path, dossier: Path):
        """Fil de fond : conversion éventuelle, puis rendu des vignettes une à une."""
        from PyQt6.QtPdf import QPdfDocument

        try:
            pdf, lu = pages.ouvrir(source, dossier)
            nb = len(pdf.pages)
            pdf.close()
        except ErreurTutti as e:
            self.signaux.pret.emit(gen, None, str(e), 0)
            return
        except Exception as e:
            self.signaux.pret.emit(gen, None, tr("err.inattendue_assemblage", detail=type(e).__name__), 0)
            return
        doc = QPdfDocument(None)
        if doc.load(str(lu)) != QPdfDocument.Error.None_:
            self.signaux.pret.emit(gen, None, tr("err.lecture_illisible", nom=source.name), 0)
            return
        self.signaux.pret.emit(gen, lu, None, nb)
        try:
            for i in range(min(nb, doc.pageCount())):
                if gen != self.generation:          # un autre document a été ouvert
                    return
                taille = doc.pagePointSize(i)
                if taille.height() <= 0 or taille.width() <= 0:
                    continue
                h = RENDU
                w = max(1, round(RENDU * taille.width() / taille.height()))
                if w > RENDU:                        # page couchée : on borne la largeur
                    w, h = RENDU, max(1, round(RENDU * taille.height() / taille.width()))
                image = doc.render(i, QtCore.QSize(w, h))
                if not image.isNull():
                    self.signaux.vignette.emit(gen, i, sur_blanc(image))
        finally:
            doc.close()

    def _document_pret(self, gen, lu, erreur, nb):
        if gen != self.generation:
            return
        if erreur:
            self.source = None
            self.l_document.setText(tr("pages.aucun_document"))
            self._majeur()
            QtWidgets.QMessageBox.warning(self, "Tutti", erreur)
            return
        self.lu, self.nb_origine = Path(lu), nb
        self.l_document.setText(tr("pages.document", nom=self.source.name, n=nb))
        self.l_document.setToolTip(str(self.source))
        for i in range(nb):
            it = QtWidgets.QListWidgetItem()
            it.setData(ROLE_PAGE, i)
            it.setData(ROLE_QUART, 0)
            it.setToolTip(tr("pages.astuce_vignette", n=i + 1))
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
            it.setSizeHint(QtCore.QSize(BOITE + 10, BOITE + 10))
            self._dessiner(it)
            self.grille.addItem(it)
        self._majeur()

    def _vignette_recue(self, gen, i, image):
        if gen != self.generation:
            return
        self.images[i] = image
        for r in range(self.grille.count()):
            it = self.grille.item(r)
            if it.data(ROLE_PAGE) == i:
                self._dessiner(it)

    def _dessiner(self, it):
        """Vignette tournée, centrée dans sa case, numéro d'origine en pastille."""
        ratio = self.devicePixelRatioF() or 1.0
        cote = round(BOITE * ratio)
        toile = QtGui.QPixmap(cote, cote)
        toile.fill(Qt.GlobalColor.transparent)
        p = QtGui.QPainter(toile)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        i, quart = it.data(ROLE_PAGE), it.data(ROLE_QUART) or 0
        image = self.images.get(i)
        utile = cote - round(22 * ratio)            # place laissée au numéro en dessous
        if image is not None:
            if quart % 360:
                image = image.transformed(QtGui.QTransform().rotate(quart))
            image = image.scaled(utile, utile, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            x, y = (cote - image.width()) // 2, (utile - image.height()) // 2 + round(2 * ratio)
            p.fillRect(x + 2, y + 2, image.width(), image.height(), QtGui.QColor(0, 0, 0, 40))
            p.drawImage(x, y, image)
            p.setPen(QtGui.QPen(QtGui.QColor("#9A9081"), 1))
            p.drawRect(x, y, image.width() - 1, image.height() - 1)
        else:                                        # rendu pas encore arrivé
            w, h = round(utile * 0.7), utile
            x, y = (cote - w) // 2, round(2 * ratio)
            p.fillRect(x, y, w, h, QtGui.QColor("#FFFFFF"))
            p.setPen(QtGui.QPen(QtGui.QColor("#C9C0B2"), 1))
            p.drawRect(x, y, w - 1, h - 1)
        f = QtGui.QFont(self.font())
        f.setPixelSize(round(13 * ratio))
        f.setWeight(QtGui.QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(self.palette().color(QtGui.QPalette.ColorRole.Text))
        texte = str(i + 1) + ("  ↻" if quart % 360 else "")
        p.drawText(QtCore.QRect(0, utile + round(2 * ratio), cote, round(20 * ratio)),
                   int(Qt.AlignmentFlag.AlignCenter), texte)
        p.end()
        toile.setDevicePixelRatio(ratio)
        icone = QtGui.QIcon(toile)
        # Sans cela Qt teinte la vignette choisie : on ne lirait plus la page.
        icone.addPixmap(toile, QtGui.QIcon.Mode.Selected)
        it.setIcon(icone)

    # ------------------------------------------------------------ actions
    def pivoter(self, quart: int):
        for it in self.grille.selectedItems():
            it.setData(ROLE_QUART, ((it.data(ROLE_QUART) or 0) + quart) % 360)
            self._dessiner(it)
        self._majeur()

    def retirer(self):
        lignes = sorted((self.grille.row(it) for it in self.grille.selectedItems()), reverse=True)
        if lignes and len(lignes) == self.grille.count():
            QtWidgets.QMessageBox.information(self, "Tutti", tr("pages.pas_tout_retirer"))
            return
        for r in lignes:
            self.grille.takeItem(r)
        if lignes:
            self.grille.setCurrentRow(min(lignes[-1], self.grille.count() - 1))
        self._majeur()

    def revenir(self):
        """Annule tous les changements : pages d'origine, dans l'ordre d'origine."""
        if self.source is None:
            return
        self.grille.clear()
        for i in range(self.nb_origine):
            it = QtWidgets.QListWidgetItem()
            it.setData(ROLE_PAGE, i)
            it.setData(ROLE_QUART, 0)
            it.setToolTip(tr("pages.astuce_vignette", n=i + 1))
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
            it.setSizeHint(QtCore.QSize(BOITE + 10, BOITE + 10))
            self._dessiner(it)
            self.grille.addItem(it)
        self._majeur()

    def _apercu(self, it):
        """Double-clic : la page en grand, pour la lire avant de décider."""
        from PyQt6.QtPdf import QPdfDocument

        if self.lu is None:
            return
        doc = QPdfDocument(self)
        if doc.load(str(self.lu)) != QPdfDocument.Error.None_:
            return
        i, quart = it.data(ROLE_PAGE), it.data(ROLE_QUART) or 0
        ecran = self.screen().availableGeometry()
        taille = doc.pagePointSize(i)
        ratio = self.devicePixelRatioF() or 1.0
        h = int(ecran.height() * 0.8)
        w = max(1, round(h * taille.width() / max(1.0, taille.height())))
        if w > ecran.width() * 0.8:
            w = int(ecran.width() * 0.8)
            h = max(1, round(w * taille.height() / max(1.0, taille.width())))
        image = doc.render(i, QtCore.QSize(round(w * ratio), round(h * ratio)))
        doc.close()
        image = sur_blanc(image)
        if quart % 360:
            image = image.transformed(QtGui.QTransform().rotate(quart))
        pix = QtGui.QPixmap.fromImage(image)
        pix.setDevicePixelRatio(ratio)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(tr("pages.apercu_titre", n=i + 1))
        lo = QtWidgets.QVBoxLayout(dlg)
        lo.setContentsMargins(6, 6, 6, 6)
        vue = QtWidgets.QLabel()
        vue.setPixmap(pix)
        vue.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(vue)
        dlg.exec()

    # ------------------------------------------------------------ écriture
    def enregistrer(self):
        if self.source is None or self.lu is None or not self.grille.count():
            return
        depart = str(self.source.parent / pages.nom_remanie(self.source))
        chemin, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, tr("pages.enregistrer_titre"), depart, tr("dlg.filtre"))
        if not chemin:
            return
        sortie = Path(chemin)
        if sortie.suffix.lower() != ".pdf":
            sortie = sortie.with_name(sortie.name + ".pdf")
        if moteur._meme_fichier(sortie, self.source):
            QtWidgets.QMessageBox.warning(self, "Tutti", tr("err.ecrase_source", nom=self.source.name))
            return
        self._sortie = sortie
        etat = self.etat()
        self.en_cours = True
        self.barre.setRange(0, 0)
        self.barre.show()
        self._majeur()
        lu, source = self.lu, self.source

        def travail():
            try:
                self.signaux.ecrit.emit(pages.remanier(lu, sortie, etat, original=source), None)
            except ErreurTutti as e:
                self.signaux.ecrit.emit(None, str(e))
            except Exception as e:
                self.signaux.ecrit.emit(None, tr("err.inattendue_assemblage", detail=type(e).__name__))
                raise

        threading.Thread(target=travail, daemon=True, name="tutti-pages").start()

    def _fin_ecriture(self, nb, erreur):
        self.en_cours = False
        self.barre.hide()
        self._majeur()
        if erreur:
            QtWidgets.QMessageBox.warning(self, "Tutti", erreur)
            return
        sortie = self._sortie
        # Le travail est sauvé : le document affiché devient « sans changement
        # en attente », pour ne pas reposer la question en fermant.
        self.fenetre.statusBar().showMessage(tr("statut.cree", nom=sortie.name, p=nb), 10000)
        self.fenetre.proposer_ouverture(sortie, nb)
        self._sauve = self.etat()

    def modifications_perdues(self) -> bool:
        """Vrai si l'état affiché diffère du dernier enregistrement (ou de l'original)."""
        return self.modifie() and getattr(self, "_sauve", None) != self.etat()
