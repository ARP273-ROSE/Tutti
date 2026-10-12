#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construit le paquet macOS ou Linux.

La structure est LA MEME que celle du paquet Windows produit par
`build_package.py` :

    <NomApp>/
        python/     un CPython autonome
        app/        le code de l'application
        <NomApp>.sh (ou le bundle .app sous macOS)

C'est ce qui permet a `updater.py` de fonctionner a l'identique sur les trois
systemes : il ne remplace que le contenu de `app/`, du Python pur, et ne touche
jamais a l'interpreteur ni aux dependances compilees.

L'interpreteur vient de python-build-standalone, l'equivalent pour Unix du
Python « embeddable » de Windows. Dependre du Python du systeme serait plus
simple et plus fragile : sur macOS il peut ne pas etre installe, et sur Linux
sa version varie d'une distribution a l'autre.

Usage :
    python3 build_unix.py [--version X.Y.Z]
"""

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KIT = json.loads((ROOT / 'kit.json').read_text(encoding='utf-8'))
NOM = KIT['nom_fichier']
NOM_TECHNIQUE = KIT['nom_technique']
NOM_AFFICHE = KIT.get('nom_affiche', NOM)
POINT_ENTREE = KIT['point_entree']

PY_VERSION = '3.12.14'
PY_BUILD = '20260901'
DIST = ROOT / 'dist'
PKG = DIST / NOM
CACHE = ROOT / '.build_cache'


def _version_courante():
    return (ROOT / KIT.get('fichier_version', 'VERSION')).read_text().strip()


def log(msg):
    print(f'  {msg}', flush=True)


def cible_python():
    """Le triplet python-build-standalone de la machine courante."""
    machine = platform.machine().lower()
    if sys.platform == 'darwin':
        return 'aarch64-apple-darwin' if machine in ('arm64', 'aarch64') else 'x86_64-apple-darwin'
    if machine in ('aarch64', 'arm64'):
        return 'aarch64-unknown-linux-gnu'
    return 'x86_64-unknown-linux-gnu'


def plateforme():
    return 'macos' if sys.platform == 'darwin' else 'linux'


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        log(f'deja en cache : {dest.name}')
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f'telechargement : {url}')
    with urllib.request.urlopen(url, timeout=180) as r, open(dest, 'wb') as f:
        shutil.copyfileobj(r, f)
    return dest


def step_python():
    """Pose un CPython autonome dans <PKG>/python."""
    cible = cible_python()
    nom = f'cpython-{PY_VERSION}+{PY_BUILD}-{cible}-install_only.tar.gz'
    url = (f'https://github.com/astral-sh/python-build-standalone/releases/'
           f'download/{PY_BUILD}/{nom}')
    archive = fetch(url, CACHE / nom)

    cible_dir = PKG / 'python'
    if cible_dir.exists():
        shutil.rmtree(cible_dir)
    tmp = DIST / '_py'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    log('extraction de l\'interpreteur')
    with tarfile.open(archive) as t:
        # L'archive contient un unique dossier « python/ ».
        for membre in t.getmembers():
            if os.path.isabs(membre.name) or '..' in Path(membre.name).parts:
                raise RuntimeError(f'Archive suspecte : {membre.name}')
        t.extractall(tmp)
    shutil.move(str(tmp / 'python'), str(cible_dir))
    shutil.rmtree(tmp, ignore_errors=True)

    exe = cible_dir / 'bin' / 'python3'
    if not exe.exists():
        raise RuntimeError(f'Interpreteur introuvable : {exe}')
    sortie = subprocess.run([str(exe), '-V'], capture_output=True, text=True)
    log(f'interpreteur : {sortie.stdout.strip() or sortie.stderr.strip()}')
    return exe


def step_deps(exe):
    reqs = ROOT / (KIT.get('requirements') or 'requirements.txt')
    if not reqs.exists():
        log('aucun requirements.txt')
        return
    log(f'installation depuis {reqs.name}')
    subprocess.run([str(exe), '-m', 'pip', 'install', '-q',
                    '--no-warn-script-location', '-r', str(reqs)], check=True)


def step_app():
    """Copie le code dans <PKG>/app."""
    app = PKG / 'app'
    if app.exists():
        shutil.rmtree(app)
    app.mkdir(parents=True)
    for module in KIT.get('modules', []):
        src = ROOT / module
        if src.exists():
            shutil.copy2(src, app / src.name)
    for paquet in KIT.get('paquets', []):
        src = ROOT / paquet
        if src.exists():
            shutil.copytree(src, app / src.name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for actif in KIT.get('assets', []):
        src = ROOT / actif
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, app / src.name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copy2(src, app / src.name)
    log(f'application copiee ({sum(1 for _ in app.rglob("*"))} entrees)')


def step_lanceur():
    """Un script shell, et sous macOS le bundle .app qui va autour."""
    sh = PKG / f'{NOM}.sh'
    sh.write_text(
        '#!/bin/sh\n'
        '# Lanceur : tout est relatif au dossier du paquet, rien n\'est\n'
        '# installe dans le systeme.\n'
        'ICI=$(cd "$(dirname "$0")" && pwd)\n'
        f'exec "$ICI/python/bin/python3" "$ICI/app/{POINT_ENTREE}" "$@"\n',
        encoding='utf-8')
    sh.chmod(sh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    log(f'lanceur : {sh.name}')

    if plateforme() == 'macos':
        # Un bundle .app : c'est ce qu'un utilisateur macOS attend de pouvoir
        # glisser dans Applications. Il enveloppe le paquet tel quel, ce qui
        # laisse `app/` a la meme place relative et l'updater inchange.
        bundle = DIST / f'{NOM}.app'
        if bundle.exists():
            shutil.rmtree(bundle)
        macos = bundle / 'Contents' / 'MacOS'
        resources = bundle / 'Contents' / 'Resources'
        macos.mkdir(parents=True)
        resources.mkdir(parents=True)
        (bundle / 'Contents' / 'Info.plist').write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0"><dict>\n'
            f'  <key>CFBundleName</key><string>{NOM_AFFICHE}</string>\n'
            f'  <key>CFBundleDisplayName</key><string>{NOM_AFFICHE}</string>\n'
            f'  <key>CFBundleIdentifier</key><string>info.{NOM_TECHNIQUE}.app</string>\n'
            f'  <key>CFBundleExecutable</key><string>{NOM}</string>\n'
            f'  <key>CFBundleVersion</key><string>{_version_courante()}</string>\n'
            f'  <key>CFBundleShortVersionString</key><string>{_version_courante()}</string>\n'
            '  <key>CFBundlePackageType</key><string>APPL</string>\n'
            '  <key>NSHighResolutionCapable</key><true/>\n'
            '  <key>LSMinimumSystemVersion</key><string>11.0</string>\n'
            '</dict></plist>\n', encoding='utf-8')
        lanceur = macos / NOM
        lanceur.write_text(
            '#!/bin/sh\n'
            'ICI=$(cd "$(dirname "$0")/../Resources" && pwd)\n'
            f'exec "$ICI/python/bin/python3" "$ICI/app/{POINT_ENTREE}" "$@"\n',
            encoding='utf-8')
        lanceur.chmod(0o755)
        for entree in ('python', 'app'):
            shutil.move(str(PKG / entree), str(resources / entree))
        shutil.rmtree(PKG, ignore_errors=True)
        log(f'bundle : {bundle.name}')

    if plateforme() == 'linux':
        # Fichier .desktop, pose par l'installeur dans ~/.local/share/applications
        (PKG / f'{NOM_TECHNIQUE}.desktop').write_text(
            '[Desktop Entry]\n'
            'Type=Application\n'
            f'Name={NOM_AFFICHE}\n'
            'Comment=Merge PDF files / Assembler des PDF\n'
            f'Exec=__ICI__/{NOM}.sh\n'
            '__ICONE__'
            'Terminal=false\n'
            'Categories=Science;Astronomy;\n',
            encoding='utf-8')


def racine_paquet() -> Path:
    """Ou vivent `python/` et `app/` : le paquet, ou les Resources du bundle."""
    bundle = DIST / f'{NOM}.app' / 'Contents' / 'Resources'
    return bundle if bundle.exists() else PKG


def step_elaguer():
    """Retire ce qui ne sert pas a l'execution."""
    base = racine_paquet()
    avant = sum(f.stat().st_size for f in base.rglob('*') if f.is_file())
    for motif in ('__pycache__', 'test', 'tests', 'idlelib', 'tkinter',
                  'turtledemo', 'lib2to3', 'ensurepip'):
        for chemin in list(base.rglob(motif)):
            if chemin.is_dir():
                shutil.rmtree(chemin, ignore_errors=True)
    for chemin in list(base.rglob('*.pyc')):
        chemin.unlink(missing_ok=True)
    apres = sum(f.stat().st_size for f in base.rglob('*') if f.is_file())
    log(f'elagage : {avant/1e6:.0f} Mo -> {apres/1e6:.0f} Mo')


def step_verifier(version):
    """L'application doit au moins s'importer avec l'interpreteur embarque."""
    base = racine_paquet()
    exe = base / 'python' / 'bin' / 'python3'
    modules = KIT.get('verification_import', [])
    if not modules:
        return
    code = 'import sys; sys.path.insert(0, "app")\n' + \
           '\n'.join(f'import {m}' for m in modules) + '\nprint("ok")'
    # -B : sans cela la verification recree des .pyc dans app/ — apres
    # l'elagage, qui les avait retires — et ils partent dans le paquet.
    r = subprocess.run([str(exe), '-B', '-c', code], cwd=base,
                       capture_output=True, text=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if r.returncode != 0:
        raise RuntimeError('Le paquet ne s\'importe pas :\n' + r.stderr[-2000:])
    log('verification d\'import : ok')


def step_archive(version):
    """L'archive applicative — le contenu de app/, ce que l'updater telecharge."""
    nom = f'{NOM_TECHNIQUE}-app-{version}.zip'
    sortie = ROOT / nom
    if sortie.exists():
        sortie.unlink()
    app = racine_paquet() / 'app'
    exclus = set(KIT.get('exclus_de_la_maj', []) or [])
    with zipfile.ZipFile(sortie, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(app.rglob('*')):
            rel = f.relative_to(app)
            if rel.parts and rel.parts[0] in exclus:
                continue
            if '__pycache__' in rel.parts:
                continue
            if f.is_file():
                info = zipfile.ZipInfo(str(rel))
                info.external_attr = (f.stat().st_mode & 0xFFFF) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, f.read_bytes())
    log(f'archive applicative : {nom} ({sortie.stat().st_size/1e6:.1f} Mo)')
    return sortie


def step_paquet_complet(version):
    """Le paquet complet, a telecharger la premiere fois."""
    nom = f'{NOM}-{version}-{plateforme()}.tar.gz'
    sortie = ROOT / nom
    if sortie.exists():
        sortie.unlink()
    cible = DIST / f'{NOM}.app' if plateforme() == 'macos' else PKG
    arc = f'{NOM}.app' if plateforme() == 'macos' else NOM
    with tarfile.open(sortie, 'w:gz') as t:
        t.add(cible, arcname=arc)
    log(f'paquet complet : {nom} ({sortie.stat().st_size/1e6:.0f} Mo)')
    return sortie


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default=None)
    args = ap.parse_args()
    version = args.version or (ROOT / KIT.get('fichier_version', 'VERSION')).read_text().strip()

    print(f'== {NOM_AFFICHE} {version} — paquet {plateforme()} ==')
    if PKG.exists():
        shutil.rmtree(PKG)
    PKG.mkdir(parents=True)

    exe = step_python()
    step_deps(exe)
    step_app()
    step_lanceur()
    step_elaguer()
    step_verifier(version)
    step_archive(version)
    step_paquet_complet(version)
    print('== termine ==')


if __name__ == '__main__':
    main()
