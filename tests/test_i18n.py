"""Garde-fous de traduction (repris de MountMonitor)."""
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutti import i18n, moteur  # noqa: E402


def champs(modele: str) -> set:
    return {nom for _, nom, _, _ in string.Formatter().parse(modele) if nom}


def test_toutes_les_cles_dans_les_deux_langues():
    for cle, textes in i18n.TEXTES.items():
        for lg in i18n.LANGUES:
            assert textes.get(lg, "").strip(), f"{cle} : texte {lg} vide ou absent"


def test_memes_champs_de_format():
    for cle, textes in i18n.TEXTES.items():
        assert champs(textes["fr"]) == champs(textes["en"]), cle


def test_cle_inconnue_ne_casse_rien():
    assert i18n.tr("cle.qui.n.existe.pas") == "cle.qui.n.existe.pas"


def test_detection_par_environnement(monkeypatch):
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    assert i18n.detecter() == "fr"
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert i18n.detecter() == "en"


def test_noms_et_erreurs_dans_la_langue():
    chemins = [Path("Symphony 5 - 01 Flute.pdf"), Path("Symphony 5 - 02 Oboe.pdf")]
    i18n.definir_langue("en")
    assert moteur.proposer_nom(chemins) == "Symphony 5 - complete.pdf"
    info = moteur.InfoPdf(chemin=Path("x.pdf"), code="motdepasse")
    assert info.erreur == "Password protected"
    i18n.definir_langue("fr")
    assert info.erreur == "Protégé par un mot de passe"
    assert moteur.proposer_nom(chemins) == "Symphony 5 - complet.pdf"


def test_option_version():
    import subprocess
    sortie = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "run.py"),
                             "--version"], capture_output=True, text=True, timeout=60)
    assert sortie.returncode == 0 and sortie.stdout.startswith("Tutti ")


def test_paquet_reconnu_sur_les_trois_systemes(tmp_path, monkeypatch):
    """Le paquet installé se reconnaît à son Python embarqué, quel que soit le système."""
    import updater
    for chemin in ("python/python.exe", "python/bin/python3"):
        racine = tmp_path / chemin.replace("/", "_")
        (racine / "app").mkdir(parents=True)
        exe = racine / chemin
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_text("")
        monkeypatch.setattr(updater, "app_dir", lambda r=racine: r / "app")
        assert updater.is_packaged(), chemin
