"""Apparence figée de Tutti.

L'interface ne doit dépendre ni du thème de Windows (clair, sombre, contraste
élevé), ni de sa couleur d'accentuation, ni de ses polices : un musicien qui
retrouve sa fenêtre transformée après une mise à jour de Windows ne s'y
retrouve plus. On impose donc :

* le style Qt « Fusion », identique sur toutes les plateformes ;
* une palette fixe (papier ivoire, encre, bordeaux et or), appliquée aussi
  aux boîtes de dialogue ;
* des polices embarquées (Source Sans 3 pour le texte, EB Garamond pour les
  titres), chargées depuis le paquet et non depuis Windows.

Seule la mise à l'échelle (125 %, 150 %…) reste celle de Windows : la
neutraliser rendrait le texte minuscule sur un écran 4K.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6 import QtGui, QtWidgets

POLICES = Path(__file__).resolve().parent / "polices"

PAPIER = "#FBF8F1"      # fond général
CARTE = "#FFFFFF"       # zones de saisie, liste
LIGNE = "#F4EFE3"       # lignes alternées
ENCRE = "#2A2420"       # texte
GRIS = "#7D746A"        # texte secondaire, désactivé
BORD = "#D9CFBE"        # traits et contours
BORDEAUX = "#7A1F2B"    # couleur d'action
BORDEAUX_CLAIR = "#94303E"
OR = "#B8860B"          # sélection, accents
SELECTION = "#EAD9B0"

FAMILLE_TEXTE = "Source Sans 3"
FAMILLE_TITRE = "EB Garamond"


def charger_polices() -> tuple[str, str]:
    """Charge les polices du paquet ; repli sur des polices système sûres."""
    texte, titre = "Segoe UI", "Georgia"
    for f in sorted(POLICES.glob("*.otf")):
        ident = QtGui.QFontDatabase.addApplicationFont(str(f))
        if ident < 0:
            continue
        familles = QtGui.QFontDatabase.applicationFontFamilies(ident)
        if FAMILLE_TEXTE in familles:
            texte = FAMILLE_TEXTE
        if FAMILLE_TITRE in familles:
            titre = FAMILLE_TITRE
    return texte, titre


def _palette() -> QtGui.QPalette:
    p = QtGui.QPalette()
    R = QtGui.QPalette.ColorRole
    G = QtGui.QPalette.ColorGroup
    c = QtGui.QColor
    for groupe in (G.Active, G.Inactive):
        p.setColor(groupe, R.Window, c(PAPIER))
        p.setColor(groupe, R.WindowText, c(ENCRE))
        p.setColor(groupe, R.Base, c(CARTE))
        p.setColor(groupe, R.AlternateBase, c(LIGNE))
        p.setColor(groupe, R.Text, c(ENCRE))
        p.setColor(groupe, R.Button, c("#F1EADB"))
        p.setColor(groupe, R.ButtonText, c(ENCRE))
        p.setColor(groupe, R.Highlight, c(SELECTION))
        p.setColor(groupe, R.HighlightedText, c(ENCRE))
        p.setColor(groupe, R.ToolTipBase, c("#FFFDF6"))
        p.setColor(groupe, R.ToolTipText, c(ENCRE))
        p.setColor(groupe, R.PlaceholderText, c(GRIS))
        p.setColor(groupe, R.Link, c(BORDEAUX))
        p.setColor(groupe, R.BrightText, c("#FFFFFF"))
        p.setColor(groupe, R.Light, c("#FFFFFF"))
        p.setColor(groupe, R.Midlight, c("#F6F1E6"))
        p.setColor(groupe, R.Mid, c(BORD))
        p.setColor(groupe, R.Dark, c("#B9AE9C"))
        p.setColor(groupe, R.Shadow, c("#8C8273"))
    for role in (R.WindowText, R.Text, R.ButtonText, R.HighlightedText):
        p.setColor(G.Disabled, role, c(GRIS))
    p.setColor(G.Disabled, R.Window, c(PAPIER))
    p.setColor(G.Disabled, R.Base, c("#F7F3EA"))
    p.setColor(G.Disabled, R.Button, c("#EEE8DB"))
    return p


QSS = f"""
QWidget {{ color: {ENCRE}; }}
QMainWindow, QDialog, QMessageBox {{ background: {PAPIER}; }}
QToolTip {{ background: #FFFDF6; color: {ENCRE}; border: 1px solid {BORD}; padding: 4px; }}

QLabel#titre {{ font-family: "{{TITRE}}"; font-size: 22pt; color: {BORDEAUX}; }}
QLabel#sous_titre {{ color: {GRIS}; }}
QLabel#resume {{ color: {ENCRE}; padding: 2px 4px; }}

QListWidget {{
    background: {CARTE}; alternate-background-color: {LIGNE};
    border: 1px solid {BORD}; border-radius: 6px; padding: 4px; outline: 0;
}}
QListWidget::item {{ padding: 6px 6px; border-radius: 4px; }}
QListWidget::item:selected {{ background: {SELECTION}; color: {ENCRE}; }}
QListWidget::item:hover {{ background: #F3E9CF; }}

QPushButton {{
    background: #F6F1E6; border: 1px solid {BORD}; border-radius: 6px;
    padding: 6px 14px; min-height: 22px;
}}
QPushButton:hover {{ background: #EFE6D2; border-color: #C7B99F; }}
QPushButton:pressed {{ background: #E6DAC0; }}
QPushButton:disabled {{ color: {GRIS}; background: #F2EEE5; border-color: #E4DCCD; }}
QPushButton#principal {{
    background: {BORDEAUX}; color: #FFFFFF; border: 1px solid {BORDEAUX};
    border-radius: 8px; padding: 8px 26px;
}}
QPushButton#principal:hover {{ background: {BORDEAUX_CLAIR}; }}
QPushButton#principal:pressed {{ background: #651823; }}
QPushButton#principal:disabled {{ background: #C9B6B0; border-color: #C9B6B0; color: #FFFFFF; }}

QGroupBox {{
    border: 1px solid {BORD}; border-radius: 8px; margin-top: 14px; padding: 10px 10px 8px 10px;
    background: #FFFDF8;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {BORDEAUX}; font-weight: 600;
}}
QLineEdit {{
    background: {CARTE}; border: 1px solid {BORD}; border-radius: 5px; padding: 5px 7px;
    selection-background-color: {SELECTION}; selection-color: {ENCRE};
}}
QLineEdit:focus {{ border-color: {OR}; }}
QComboBox {{
    background: {CARTE}; border: 1px solid {BORD}; border-radius: 5px; padding: 4px 8px;
}}
QComboBox:hover, QComboBox:focus {{ border-color: {OR}; }}
QComboBox QAbstractItemView {{
    background: {CARTE}; border: 1px solid {BORD}; selection-background-color: {SELECTION};
    selection-color: {ENCRE}; outline: 0;
}}
QLineEdit:read-only {{ background: #F7F3EA; color: #5C544B; }}

QTabWidget::pane {{ border: 1px solid {BORD}; border-radius: 8px; top: -1px; background: {PAPIER}; }}
QTabBar::tab {{
    background: #EFE8DA; border: 1px solid {BORD}; border-bottom: none;
    border-top-left-radius: 7px; border-top-right-radius: 7px;
    padding: 7px 18px; margin-right: 3px; color: #5C544B;
}}
QTabBar::tab:selected {{ background: {PAPIER}; color: {BORDEAUX}; font-weight: 600; }}
QTabBar::tab:hover:!selected {{ background: #F5EFE2; }}
QRadioButton {{ spacing: 8px; padding: 2px 0; }}
QRadioButton::indicator {{
    width: 16px; height: 16px; border: 1px solid #B9AE9C; border-radius: 9px; background: {CARTE};
}}
QRadioButton::indicator:hover {{ border-color: {OR}; }}
QRadioButton::indicator:checked {{ background: {BORDEAUX}; border-color: {BORDEAUX}; image: url("{{POINT}}"); }}
QCheckBox {{ spacing: 8px; padding: 2px 0; }}
QCheckBox::indicator {{
    width: 17px; height: 17px; border: 1px solid #B9AE9C; border-radius: 4px; background: {CARTE};
}}
QCheckBox::indicator:hover {{ border-color: {OR}; }}
QCheckBox::indicator:checked {{ background: {BORDEAUX}; border-color: {BORDEAUX}; image: url("{{COCHE}}"); }}

QProgressBar {{
    border: 1px solid {BORD}; border-radius: 6px; background: {CARTE}; text-align: center;
    min-height: 20px;
}}
QProgressBar::chunk {{ background: {OR}; border-radius: 5px; }}

QMenuBar {{ background: {PAPIER}; border-bottom: 1px solid {BORD}; }}
QMenuBar::item {{ padding: 4px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: #EFE6D2; border-radius: 4px; }}
QMenu {{ background: {CARTE}; border: 1px solid {BORD}; padding: 4px; }}
QMenu::item {{ padding: 5px 24px 5px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background: {SELECTION}; color: {ENCRE}; }}
QMenu::separator {{ height: 1px; background: {BORD}; margin: 4px 8px; }}

QStatusBar {{ background: {PAPIER}; color: {GRIS}; border-top: 1px solid {BORD}; }}
QPlainTextEdit {{ background: {CARTE}; border: 1px solid {BORD}; border-radius: 5px; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #D6CCBA; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #C2B59E; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
"""


def appliquer(app: QtWidgets.QApplication) -> None:
    """Fige l'apparence de toute l'application (fenêtre et dialogues)."""
    app.setStyle("Fusion")
    try:  # Qt ≥ 6.8 : ignorer le mode sombre de Windows
        from PyQt6.QtCore import Qt
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except Exception:
        pass
    texte, titre = charger_polices()
    police = QtGui.QFont(texte)
    police.setPointSizeF(11)
    police.setHintingPreference(QtGui.QFont.HintingPreference.PreferNoHinting)
    app.setFont(police)
    app.setPalette(_palette())
    coche = (Path(__file__).resolve().parent / "icones" / "coche.svg").as_posix()
    point = (Path(__file__).resolve().parent / "icones" / "point.svg").as_posix()
    app.setStyleSheet(QSS.replace("{TITRE}", titre).replace("{COCHE}", coche)
                      .replace("{POINT}", point))
