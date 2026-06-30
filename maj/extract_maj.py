#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extraction des termes tout en majuscules dans des fichiers XML-TEI,
à l'exclusion :
  - des débuts de phrase (après un point/!/? final, ou juste après une balise ouvrante)
  - du contenu des balises <persName>, <placeName>, <objectName>
  - du contenu des balises <hi rend="capitals">
  - des chiffres romains
  - des mots d'une seule lettre

Les résultats sont séparés par langue (français / italien), déterminée
par défaut via teiHeader/fileDesc/titleStmt/title/@xml:lang, et affinée
localement si des attributs xml:lang apparaissent dans le corps du texte
(ex: <div xml:lang="ita">), avec héritage sur les descendants.

Usage:
    python3 extraire_majuscules.py /chemin/vers/corpus --out /chemin/vers/sortie

Le script cherche récursivement tous les *.xml sous le dossier indiqué.
"""

import os
import re
import sys
from pathlib import Path

from lxml import etree

# ============================================================================
# CHEMINS FIGÉS — À ADAPTER À VOTRE ENVIRONNEMENT
# ============================================================================
CORPUS_DIR = Path(r"C:\Users\ebondoer\Desktop\GitHubArTerm\corpus\Perspective")
OUTPUT_DIR = Path(r"C:\Users\ebondoer\Desktop\GitHubArTerm\scripts\maj")
# Fichier texte listant les noms de fichiers à NE PAS traiter (un nom par ligne).
# Le nom doit correspondre au nom du fichier seul (ex: "exemple.xml"),
# sans le chemin complet.
EXCLUDED_FILES_LIST = Path(r"C:\Users\ebondoer\Desktop\GitHubArTerm\scripts\maj\NonTraite.txt")
# ============================================================================

XML_NS = "{http://www.w3.org/XML/1998/namespace}lang"

# Balises dont le contenu textuel est totalement ignoré pour l'extraction
ENTITY_TAGS = {"persName", "placeName", "objectName"}

# Balise à ignorer entièrement (métadonnées), ne contribue pas aux mots
SKIP_TAGS = {"teiHeader"}

# Regex pour repérer un "mot" (lettres latines + accents français/italiens).
# Note : l'apostrophe n'est PAS incluse comme liaison interne, afin de bien
# séparer les élisions ("l'UNESCO" -> "l" + "UNESCO", "d'ACCORD" -> "d" + "ACCORD").
# Conséquence : un mot comme "AUJOURD'HUI" sera scindé en "AUJOURD" et "HUI".
# Le trait d'union, lui, reste joint (ex: "GRECO-ROMAIN").
WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:-[A-Za-zÀ-ÖØ-öø-ÿ]+)*"
)

# Ponctuation considérée comme fin de phrase
SENTENCE_END_RE = re.compile(r"[.!?]")

# Chiffres romains (I, V, X, L, C, D, M) — exclusion stricte
ROMAN_RE = re.compile(
    r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$"
)

LANG_MAP = {
    "fra": "francais",
    "fre": "francais",
    "fr": "francais",
    "ita": "italien",
    "it": "italien",
}


def load_excluded_filenames(path):
    """
    Charge la liste des noms de fichiers à exclure depuis un .txt
    (un nom de fichier par ligne, SANS extension, ex: "exemple").
    Les lignes vides et les espaces superflus sont ignorés.
    Retourne un set() de noms de fichiers sans extension (str).
    """
    if not path.exists():
        print(f"[INFO] Aucun fichier d'exclusion trouvé à {path} "
              f"-> aucun fichier ne sera exclu.", file=sys.stderr)
        return set()

    excluded = set()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            name = line.strip()
            if name:
                # On retire une éventuelle extension fournie par erreur,
                # pour comparer uniquement sur le nom sans extension (stem).
                excluded.add(Path(name).stem)
    print(f"{len(excluded)} fichier(s) à exclure chargé(s) depuis {path}")
    return excluded


def local_name(elem):
    """Nom de balise sans préfixe de namespace."""
    qn = etree.QName(elem)
    return qn.localname


def is_capitals_hi(elem):
    return local_name(elem) == "hi" and elem.get("rend") == "capitals"


def is_roman_numeral(word):
    return bool(ROMAN_RE.fullmatch(word.upper()))


def is_candidate_word(word):
    """
    Le mot est-il un candidat ?
    - commence par une majuscule (le reste du mot peut être minuscule,
      majuscule, mixte... peu importe)
    - au moins 2 lettres
    - n'est pas un chiffre romain (ex: "XIV", "Ier")
    """
    if len(word) < 2:
        return False
    if not word[0].isupper():
        return False
    if is_roman_numeral(word):
        return False
    return True


def detect_document_lang(tree):
    """Détermine la langue par défaut du document via teiHeader/titleStmt/title/@xml:lang."""
    root = tree.getroot()
    titles = root.findall(".//{*}teiHeader//{*}titleStmt/{*}title")
    for t in titles:
        lang = t.get(XML_NS)
        if lang and lang.lower() in LANG_MAP:
            return LANG_MAP[lang.lower()]
    # Repli : chercher n'importe quel xml:lang dans teiHeader
    header = root.find(".//{*}teiHeader")
    if header is not None:
        lang = header.get(XML_NS)
        if lang and lang.lower() in LANG_MAP:
            return LANG_MAP[lang.lower()]
    return None


class Extractor:
    def __init__(self, results):
        # results : dict {"francais": set(), "italien": set()}
        self.results = results

    def collect(self, word, lang):
        if lang in self.results:
            self.results[lang].add(word)
        # Si la langue est inconnue, on l'ignore (ou on pourrait la stocker à part)

    def process_text(self, text, start_flag, lang):
        """
        Traite un segment de texte brut.
        start_flag : True si le tout premier mot de ce segment doit être
                     considéré comme un début de phrase (ex: juste après
                     une balise ouvrante).
        Retourne le nouveau flag (sentence-start) à propager après ce segment.
        """
        if not text:
            return start_flag

        matches = list(WORD_RE.finditer(text))
        if not matches:
            # Pas de mot, on regarde juste si le segment contient une fin de phrase
            return start_flag or bool(SENTENCE_END_RE.search(text))

        pos = 0
        flag = start_flag
        for i, m in enumerate(matches):
            between = text[pos:m.start()]
            if i == 0:
                is_start = start_flag or bool(SENTENCE_END_RE.search(between))
            else:
                is_start = bool(SENTENCE_END_RE.search(between))

            word = m.group()
            if not is_start and is_candidate_word(word) and lang:
                self.collect(word, lang)

            pos = m.end()

        trailing = text[pos:]
        flag = bool(SENTENCE_END_RE.search(trailing))
        return flag

    def walk(self, elem, flag, lang):
        """
        Parcourt récursivement l'élément.
        Retourne le flag (sentence-start) après traitement de elem + sa queue (tail).
        """
        # Ignorer les commentaires, instructions de traitement (PI), etc.
        # dont elem.tag n'est pas une chaîne de caractères normale.
        if not isinstance(elem.tag, str):
            return self.process_text(elem.tail, flag, lang)

        tag = local_name(elem)

        # Langue locale (héritage avec override xml:lang)
        local_lang = elem.get(XML_NS)
        if local_lang and local_lang.lower() in LANG_MAP:
            lang = LANG_MAP[local_lang.lower()]

        if tag in SKIP_TAGS:
            # On ignore complètement (métadonnées), pas d'effet sur le flag
            return self.process_text(elem.tail, False, lang)

        if tag in ENTITY_TAGS or is_capitals_hi(elem):
            # On n'extrait rien du contenu, mais on regarde si ce contenu
            # se termine par une ponctuation de fin de phrase, pour bien
            # gérer le texte qui suit (tail).
            full_text = "".join(elem.itertext())
            ends_sentence = bool(SENTENCE_END_RE.search(full_text[-1:])) if full_text else False
            # Vérification plus robuste : fin de phrase si le dernier caractère
            # non blanc est . ! ou ?
            stripped = full_text.rstrip()
            ends_sentence = bool(stripped) and stripped[-1] in ".!?"
            return self.process_text(elem.tail, ends_sentence, lang)

        # Cas général : on traite elem.text (toujours "après balise ouvrante"
        # donc le 1er mot est exclu), puis les enfants, puis on renvoie le
        # flag courant pour le tail (géré par l'appelant via la queue).
        flag_after_text = self.process_text(elem.text, True, lang)

        child_flag = flag_after_text
        for child in elem:
            child_flag = self.walk(child, child_flag, lang)

        return child_flag


def process_file(path, results):
    try:
        parser = etree.XMLParser(recover=True, huge_tree=True)
        tree = etree.parse(str(path), parser)
    except Exception as e:
        print(f"[AVERTISSEMENT] Impossible de parser {path} : {e}", file=sys.stderr)
        return

    doc_lang = detect_document_lang(tree)
    if doc_lang is None:
        print(f"[AVERTISSEMENT] Langue non détectée pour {path} (titre xml:lang manquant ou inconnu)",
              file=sys.stderr)

    extractor = Extractor(results)
    root = tree.getroot()
    extractor.walk(root, True, doc_lang)


def main():
    corpus_dir = CORPUS_DIR
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    excluded_filenames = load_excluded_filenames(EXCLUDED_FILES_LIST)

    all_xml_files = sorted(corpus_dir.rglob("*.xml"))
    if not all_xml_files:
        print(f"Aucun fichier .xml trouvé sous {corpus_dir}", file=sys.stderr)
        sys.exit(1)

    xml_files = [f for f in all_xml_files if f.stem not in excluded_filenames]
    skipped = [f for f in all_xml_files if f.stem in excluded_filenames]

    print(f"{len(all_xml_files)} fichier(s) XML trouvé(s).")
    if skipped:
        print(f"{len(skipped)} fichier(s) ignoré(s) (présents dans la liste d'exclusion) :")
        for f in skipped:
            print(f"  - {f.name}")
    print(f"{len(xml_files)} fichier(s) seront effectivement traités.")

    results = {"francais": set(), "italien": set()}

    for f in xml_files:
        process_file(f, results)

    for lang, words in results.items():
        out_path = out_dir / f"termes_{lang}.txt"
        with open(out_path, "w", encoding="utf-8") as fh:
            for w in sorted(words, key=lambda s: s.lower()):
                fh.write(w + "\n")
        print(f"-> {len(words)} terme(s) unique(s) écrits dans {out_path}")


if __name__ == "__main__":
    main()