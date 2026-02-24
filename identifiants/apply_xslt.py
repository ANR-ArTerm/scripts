#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour appliquer la transformation XSLT aux fichiers XML du corpus
Usage: python apply_xslt.py [--dry-run]
"""

import os
import sys
from pathlib import Path
from lxml import etree

def apply_xslt_to_file(xml_file, xslt_file, dry_run=False):
    """
    Applique la transformation XSLT à un fichier XML.
    
    Args:
        xml_file: Chemin du fichier XML source
        xslt_file: Chemin du fichier XSLT
        dry_run: Si True, affiche le résultat sans sauvegarder
    
    Returns:
        True si succès, False sinon
    """
    try:
        print(f"\n📄 Traitement de: {xml_file.name}")
        
        # Charger le fichier XML
        xml_doc = etree.parse(str(xml_file))
        
        # Charger la transformation XSLT
        xslt_doc = etree.parse(str(xslt_file))
        try:
            transform = etree.XSLT(xslt_doc)
        except etree.XSLTParseError as e:
            print(f"   ❌ Erreur XSLT (parse): {str(e)}")
            try:
                print("   ℹ️ Détails du parse XSLT:")
                print(e.error_log)
            except Exception:
                pass
            return False
        
        # Appliquer la transformation avec le nom du fichier comme paramètre
        try:
            result = transform(xml_doc, filename=etree.XSLT.strparam(xml_file.name))
        except etree.XSLTApplyError as e:
            print(f"   ❌ Erreur XSLT (apply): {str(e)}")
            try:
                print("   ℹ️ Détails XSLT error_log:")
                print(transform.error_log)
            except Exception:
                pass
            # Tentative de repli avec Saxon (XSLT 2.0/3.0) si disponible
            try:
                from saxonche import PySaxonProcessor
                print("   🔁 Tentative de repli : utilisation de SaxonC (saxonche)")
                with PySaxonProcessor(license=False) as proc:
                    compiler = proc.new_xslt_compiler()
                    xslt_exec = compiler.compile_stylesheet(stylesheet_file=str(xslt_file))
                    result_str = xslt_exec.transform_to_string(source_file=str(xml_file), stylesheet_params={"filename": xml_file.name})
                    # Convertir en ElementTree
                    result = etree.fromstring(result_str.encode('utf-8'))
                    result = etree.XSLTResultTree(result)
            except ImportError:
                print("   ⚠️ saxonche non installé — installez par `pip install saxonche` pour le support XSLT 2.0/3.0")
                return False
            except Exception as e2:
                print(f"   ❌ Échec du repli Saxon: {e2}")
                return False
        
        # Compter les modifications (paragraphes avec xml:id)
        result_tree = etree.ElementTree(result.getroot())
        namespaces = {'tei': 'http://www.tei-c.org/ns/1.0'}
        paragraphs_with_id = result_tree.xpath('.//tei:p[@xml:id]', namespaces=namespaces)
        
        print(f"   ✓ {len(paragraphs_with_id)} paragraphe(s) avec xml:id")
        
        # Afficher quelques exemples
        for i, p in enumerate(paragraphs_with_id[:3]):
            xml_id = p.get('{http://www.w3.org/XML/1998/namespace}id')
            print(f"   ✓ xml:id=\"{xml_id}\"")
        
        if len(paragraphs_with_id) > 3:
            print(f"   ... et {len(paragraphs_with_id) - 3} autres")
        
        if not dry_run:
            # Sauvegarder le résultat
            with open(xml_file, 'wb') as f:
                f.write(etree.tostring(result, 
                                      encoding='UTF-8', 
                                      xml_declaration=True, 
                                      pretty_print=True))
            print(f"   💾 Fichier sauvegardé")
        else:
            print(f"   🔍 Mode test: fichier non modifié")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur: {str(e)}")
        return False


def process_corpus(corpus_path='../../corpus', xslt_file='add_xml_ids.xsl', dry_run=False):
    """
    Traite tous les fichiers XML dans le corpus.
    
    Args:
        corpus_path: Chemin vers le dossier corpus
        xslt_file: Chemin vers le fichier XSLT
        dry_run: Si True, simule sans modifier les fichiers
    """
    corpus_dir = Path(corpus_path)
    xslt_path = Path(xslt_file)
    
    # Vérifications
    if not corpus_dir.exists():
        print(f"❌ Le dossier '{corpus_path}' n'existe pas!")
        print(f"   Chemin actuel: {Path.cwd()}")
        return
    
    if not xslt_path.exists():
        print(f"❌ Le fichier XSLT '{xslt_file}' n'existe pas!")
        return
    
    print("=" * 60)
    print("🚀 DÉBUT DU TRAITEMENT XSLT")
    if dry_run:
        print("⚠️  MODE TEST: Aucun fichier ne sera modifié")
    print("=" * 60)
    
    # Traiter les sous-dossiers FRA et ITA
    subdirs = ['Architecture', 'Peinture', 'Perspective']
    total_files = 0
    total_success = 0
    
    for subdir in subdirs:
        subdir_path = corpus_dir / subdir
        
        if not subdir_path.exists():
            print(f"\n⚠️  Le sous-dossier '{subdir}' n'existe pas")
            continue
        
        print(f"\n{'=' * 60}")
        print(f"📁 Traitement du dossier: {subdir}")
        print(f"{'=' * 60}")
        
        # Trouver tous les fichiers XML
        xml_files = list(subdir_path.glob('*.xml'))
        
        if not xml_files:
            print(f"   Aucun fichier XML trouvé")
            continue
        
        print(f"   {len(xml_files)} fichier(s) XML trouvé(s)")
        
        for xml_file in sorted(xml_files):
            total_files += 1
            if apply_xslt_to_file(xml_file, xslt_path, dry_run):
                total_success += 1
    
    # Résumé
    print("\n" + "=" * 60)
    print("✅ TRAITEMENT TERMINÉ")
    print("=" * 60)
    print(f"📊 Statistiques:")
    print(f"   - Fichiers traités: {total_files}")
    print(f"   - Succès: {total_success}")
    print(f"   - Échecs: {total_files - total_success}")
    if dry_run:
        print(f"\n⚠️  Mode test - Pour appliquer les modifications:")
        print(f"   python {sys.argv[0]}")
    print("=" * 60)


if __name__ == "__main__":
    # Vérifier si mode dry-run
    dry_run = '--dry-run' in sys.argv or '-d' in sys.argv
    
    # Lancer le traitement
    process_corpus(dry_run=dry_run)
