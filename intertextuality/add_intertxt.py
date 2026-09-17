#!/usr/bin/env python3
"""
enrich_intertextuality.py
─────────────────────────
Lit un CSV de paires d'intertextualité (colonnes : ID_1, Paragraphe_1,
ID_2, Paragraphe_2, Similarite) et enrichit les fichiers XML/TEI du
dossier corpus/Peinture en :

  1. Insérant des <ptr type="intertextuality" target="#…"/> dans chaque
     <p> concerné (déduplication : un seul ptr par cible unique).
  2. Insérant un <linkGrp type="intertextuality"> par fichier source
     juste après l'ouverture de <text>, avec un <link> par paire de
     paragraphes (dédupliqué) portant @n = valeur brute de similarité.

Les fichiers enrichis sont écrits dans output/ (copie, pas modification
en place).

Usage :
    python enrich_intertextuality.py \
        --csv  resultats_intertextualite.csv \
        --corpus corpus/Peinture \
        --output output
"""

import argparse
import csv
import shutil
from collections import defaultdict
from pathlib import Path

from lxml import etree

# ── Namespaces TEI ────────────────────────────────────────────────────────────
TEI_NS  = "http://www.tei-c.org/ns/1.0"
XML_NS  = "http://www.w3.org/XML/1998/namespace"
NS_MAP  = {"tei": TEI_NS, "xml": XML_NS}

TAG_P   = f"{{{TEI_NS}}}p"
TAG_PTR = f"{{{TEI_NS}}}ptr"
TAG_LG  = f"{{{TEI_NS}}}linkGrp"
TAG_LNK = f"{{{TEI_NS}}}link"
TAG_TXT = f"{{{TEI_NS}}}text"

ATTR_ID = f"{{{XML_NS}}}id"


# ── Utilitaires sur les identifiants ──────────────────────────────────────────

def sentence_to_para_id(sentence_id: str) -> str:
    """
    'FEL_E1_L1_E2_C75_P1_s04'  →  'FEL_E1_L1_E2_C75_P1'
    Supprime les 2 derniers segments (_Pn et _sXX déjà séparés).
    Règle : les 2 derniers segments séparés par '_' sont toujours
    le numéro de paragraphe et le numéro de phrase.
    On retire uniquement le dernier (_sXX) car les <p> ont leur
    @xml:id jusqu'au paragraphe (dernier segment _Pn inclus).
    """
    parts = sentence_id.rsplit("_", 1)
    return parts[0]  # retire le _sXX


def file_key(para_id: str) -> str:
    """
    Retourne la clé 'Auteur_Titre' (2 premiers segments) identifiant
    le fichier source.
    'FEL_E1_L1_E2_C75_P1'  →  'FEL_E1'
    """
    parts = para_id.split("_")
    return "_".join(parts[:2])


# ── Lecture du CSV ─────────────────────────────────────────────────────────────

def load_csv(csv_path: Path) -> list[dict]:
    """Retourne la liste des lignes du CSV sous forme de dicts."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── Construction des structures de données ────────────────────────────────────

def build_data(rows: list[dict]) -> tuple[
    dict[str, dict[str, set[str]]],   # ptr_map  : para_id → {cible, …}
    dict[str, dict[frozenset, float]], # link_map : file_key → {frozenset(p1,p2) → sim}
]:
    """
    ptr_map[para_id]  = ensemble des para_id cibles (pour les <ptr>)
    link_map[fkey]    = dict { frozenset(p1, p2) → similarité } pour les <link>

    Règles de déduplication :
    - ptr  : un seul ptr par paire ordonnée (A→B et B→A sont tous deux insérés,
             mais chacun une seule fois).
    - link : une seule entrée par paire {A, B} ; on garde la similarité max
             si plusieurs phrases relient les mêmes paragraphes.
    """
    ptr_map: dict[str, set[str]]          = defaultdict(set)
    link_map: dict[str, dict[frozenset, float]] = defaultdict(dict)

    for row in rows:
        id1_raw = row["ID_1"].strip()
        id2_raw = row["ID_2"].strip()
        sim_raw = row["Similarite"].strip()

        if not id1_raw or not id2_raw:
            continue

        p1 = sentence_to_para_id(id1_raw)
        p2 = sentence_to_para_id(id2_raw)

        if p1 == p2:
            continue  # auto-lien : ignoré

        try:
            sim = float(sim_raw)
        except ValueError:
            sim = 0.0

        # ptr : A pointe vers B et B pointe vers A
        ptr_map[p1].add(p2)
        ptr_map[p2].add(p1)

        # link groupé par fichier source du premier identifiant
        fkey = file_key(p1)
        pair = frozenset((p1, p2))
        # garde la similarité maximale pour la paire
        if pair not in link_map[fkey] or link_map[fkey][pair] < sim:
            link_map[fkey][pair] = sim

    return ptr_map, link_map


# ── Localisation des fichiers XML ─────────────────────────────────────────────

def find_xml_files(corpus_dir: Path) -> dict[str, Path]:
    """
    Retourne un dict { file_key → Path } en analysant le nom des fichiers
    ou, à défaut, les identifiants présents dans le document.
    Stratégie : on cherche d'abord par nom de fichier (stem commence par
    la clé), puis on indexe par clé extraite des @xml:id des <p>.
    """
    index: dict[str, Path] = {}
    for xml_file in sorted(corpus_dir.rglob("*.xml")):
        # Tente de lire le premier @xml:id d'un <p> pour dériver la clé
        try:
            tree = etree.parse(str(xml_file))
            first_p = tree.find(f".//{TAG_P}[@{ATTR_ID}]")
            if first_p is not None:
                pid = first_p.get(ATTR_ID, "")
                fkey = file_key(pid)
                if fkey and fkey not in index:
                    index[fkey] = xml_file
        except etree.XMLSyntaxError:
            print(f"  [AVERTISSEMENT] XML invalide ignoré : {xml_file}")
    return index


# ── Enrichissement d'un fichier ───────────────────────────────────────────────

def enrich_file(
    src_path: Path,
    dst_path: Path,
    fkey: str,
    ptr_map: dict[str, set[str]],
    link_map: dict[str, dict[frozenset, float]],
) -> int:
    """
    Enrichit une copie du fichier XML.
    Retourne le nombre de modifications effectuées.
    """
    parser = etree.XMLParser(remove_blank_text=False)
    tree   = etree.parse(str(src_path), parser)
    root   = tree.getroot()
    mods   = 0

    # ── 1. Insertion des <ptr> dans les <p> ───────────────────────────────
    for p_elem in root.iter(TAG_P):
        para_id = p_elem.get(ATTR_ID)
        if not para_id or para_id not in ptr_map:
            continue

        # Cibles déjà présentes (évite les doublons sur ré-exécution)
        existing_targets: set[str] = {
            ptr.get("target", "").lstrip("#")
            for ptr in p_elem.iter(TAG_PTR)
            if ptr.get("type") == "intertextuality"
        }

        for cible in sorted(ptr_map[para_id]):
            if cible in existing_targets:
                continue
            ptr = etree.SubElement(p_elem, TAG_PTR)
            ptr.set("type", "intertextuality")
            ptr.set("target", f"#{cible}")
            existing_targets.add(cible)
            mods += 1

    # ── 2. Construction du <linkGrp> ─────────────────────────────────────
    pairs = link_map.get(fkey, {})
    if pairs:
        lg = etree.Element(TAG_LG)
        lg.set("type", "intertextuality")

        for pair, sim in sorted(pairs.items(), key=lambda x: sorted(x[0])):
            p1, p2 = sorted(pair)
            lnk = etree.SubElement(lg, TAG_LNK)
            lnk.set("target", f"#{p1} #{p2}")
            lnk.set("n", str(sim))

        # Insertion juste après l'ouverture de <text>
        text_elem = root.find(f".//{TAG_TXT}")
        if text_elem is not None:
            # Vérifie qu'un linkGrp identique n'existe pas déjà
            existing_lg = text_elem.find(
                f"{TAG_LG}[@type='intertextuality']"
            )
            if existing_lg is not None:
                text_elem.remove(existing_lg)
            text_elem.insert(0, lg)
            mods += len(pairs)

    # ── 3. Écriture ───────────────────────────────────────────────────────
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(
        str(dst_path),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )
    return mods


# ── Point d'entrée ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enrichit des fichiers TEI avec des liens d'intertextualité."
    )
    parser.add_argument("--csv",  default="C:/Users/ebondoer/Desktop/Allign-bilingual/scripts_2026/output_visu_sentences/labse_nettoye/top_pairs_Peinture_seuil08_nettoye_gardes_sentences.csv", help="Chemin vers le fichier CSV")
    parser.add_argument("--corpus",  default="C:/Users/ebondoer/Desktop/GitHubArTerm/corpus/Peinture", help="Dossier corpus/Peinture")
    parser.add_argument("--output", default="output", help="Dossier de sortie")
    args = parser.parse_args()

    csv_path    = Path(args.csv)
    corpus_dir  = Path(args.corpus)
    output_dir  = Path(args.output)

    print(f"Lecture du CSV : {csv_path}")
    rows = load_csv(csv_path)
    print(f"  → {len(rows)} paires lues")

    ptr_map, link_map = build_data(rows)
    print(f"  → {len(ptr_map)} paragraphes concernés par des <ptr>")
    print(f"  → {len(link_map)} fichiers sources avec des <link>")

    print(f"\nIndexation des fichiers XML dans : {corpus_dir}")
    xml_index = find_xml_files(corpus_dir)
    print(f"  → {len(xml_index)} fichiers indexés")

    print(f"\nEnrichissement → {output_dir}/")
    total_mods = 0
    processed  = 0

    for fkey, xml_path in sorted(xml_index.items()):
        # Chemin relatif conservé dans output/
        rel = xml_path.relative_to(corpus_dir)
        dst = output_dir / rel

        mods = enrich_file(xml_path, dst, fkey, ptr_map, link_map)
        if mods:
            print(f"  ✓  {rel}  ({mods} modifications)")
            total_mods += mods
            processed  += 1
        else:
            # Copie sans modification (aucun lien pour ce fichier)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(xml_path, dst)
            print(f"  –  {rel}  (aucun lien, copié tel quel)")

    print(f"\nTerminé : {processed} fichier(s) enrichi(s), {total_mods} insertion(s) au total.")


if __name__ == "__main__":
    main()