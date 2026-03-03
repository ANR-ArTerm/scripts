#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supprimer les attributs xml:id des éléments <tei:p> dans le corpus
Usage:
  python strip_paragraph_ids.py [--dry-run] [--corpus PATH]

Par défaut, parcourt les sous-dossiers Architecture, Peinture, Perspective
du dossier '../../corpus-ArTerm'. Exclut explicitement
'Martin_ArchitectureSerlio.xml' dans 'Architecture'.
"""
from pathlib import Path
import argparse
import re


def process_file(path: Path, dry_run=True):
    try:
        text = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"   ❌ Erreur lecture {path.name}: {e}")
        return False

    # pattern: match start tag of <p ...> or <tei:p ...> and remove xml:id attributes (single or double quoted)
    pattern = re.compile(r'(<(?:tei:)?p\b[^>]*?)\s+xml:id=(?:"[^"]*"|\'[^\']*\')(.*?>)', re.IGNORECASE | re.DOTALL)

    # count removals
    new_text, nsubs = pattern.subn(lambda m: m.group(1) + m.group(2), text)

    # also handle cases where xml:id may be the first attribute without leading space
    if nsubs == 0:
        pattern2 = re.compile(r'(<(?:tei:)?p\b)\s*xml:id=(?:"[^"]*"|\'[^\']*\')(\s|>)', re.IGNORECASE | re.DOTALL)
        new_text, nsubs2 = pattern2.subn(lambda m: m.group(1) + m.group(2), new_text)
        nsubs += nsubs2

    # Report dry-run
    if dry_run:
        print(f"   {path.name}: occurrences xml:id supprimables dans <p>: {nsubs} (dry-run)")
        return True

    try:
        path.write_text(new_text, encoding='utf-8')
        print(f"   {path.name}: xml:id supprimés dans {nsubs} occurrences.")
        return True
    except Exception as e:
        print(f"   ❌ Erreur écriture {path.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Ne pas écrire, afficher seulement')
    parser.add_argument('--corpus', default='../../corpus-ArTerm', help='Chemin vers corpus-ArTerm')
    args = parser.parse_args()

    corpus = Path(args.corpus)
    if not corpus.exists():
        print(f"❌ Dossier corpus introuvable: {corpus}")
        return

    subdirs = ['Architecture', 'Peinture', 'Perspective']
    exclusions = {'Architecture': ['Martin_ArchitectureSerlio.xml']}

    total = 0
    success = 0

    for sd in subdirs:
        sdpath = corpus / sd
        if not sdpath.exists():
            print(f"⚠️  Sous-dossier manquant: {sd}")
            continue
        files = sorted(sdpath.glob('*.xml'))
        print(f"\n📁 {sd} : {len(files)} fichiers")
        for f in files:
            if sd in exclusions and f.name.lower() in [e.lower() for e in exclusions[sd]]:
                print(f"   ⏭️  Ignoré (exception): {f.name}")
                continue
            total += 1
            ok = process_file(f, dry_run=args.dry_run)
            if ok:
                success += 1

    print(f"\n✅ Terminé: {success}/{total} fichiers traités (dry-run={args.dry_run})")


if __name__ == '__main__':
    main()
