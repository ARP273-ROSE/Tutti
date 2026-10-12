"""Tutti : assembler plusieurs PDF en un seul.

Le numéro de version n'existe qu'à un seul endroit, le fichier VERSION à la
racine du dépôt (règle du kit Windows) : on le relit ici au lieu de le recopier.
"""
from pathlib import Path


def _lire_version() -> str:
    try:
        return (Path(__file__).resolve().parent.parent / "VERSION").read_text(
            encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


__version__ = _lire_version()
