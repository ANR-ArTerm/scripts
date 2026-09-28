#!/usr/bin/env python3
# ==============================================================================
# # Enrichissement TEI — Liens d'intertextualité
#
# Ce notebook lit un CSV de paires d'intertextualité et enrichit les fichiers XML/TEI du corpus en ajoutant :
#
# 1. **`<linkGrp type="intertextuality">`** juste après l'ouverture de `<text>`, avec un `<link>` par paire de paragraphes reliés (dans les **deux sens** : un bloc par fichier source *et* par fichier cible).
# 2. **`<ptr type="intertextuality" target="#…"/>`** à l'intérieur de chaque `<p>` concerné, pointant vers les paragraphes liés.
#
# Les fichiers enrichis sont écrits dans le dossier `output/` (copie, pas de modification en place).
# ==============================================================================

# ==============================================================================
# ## 1. Chemins à configurer
#
# Modifier uniquement cette cellule pour adapter le notebook à l'environnement.
# ==============================================================================

from pathlib import Path

# ── À adapter ─────────────────────────────────────────────────────────────
CSV_PATH    = Path("C:/Users/ebondoer/Desktop/Allign-bilingual/traitement_IT_propre/LaBSE/output_nettoyage/post_tinder/top_pairs_p_ner_ids_Peinture_Architecture_Perspective_seuil08-085_nettoye_gardes.csv")
CORPUS_DIR  = Path("C:/Users/ebondoer/Desktop/GitHubArTerm/corpus")
CORPUS_SUBDIRS = ("Peinture", "Architecture", "Perspective")
OUTPUT_DIR  = Path("output")
# ──────────────────────────────────────────────────────────────────────────

# Vérifications rapides
assert CSV_PATH.exists(),   f"CSV introuvable : {CSV_PATH}"
assert CORPUS_DIR.exists(), f"Dossier corpus introuvable : {CORPUS_DIR}"
assert all((CORPUS_DIR / name).is_dir() for name in CORPUS_SUBDIRS), \
    f"Un ou plusieurs sous-dossiers corpus sont introuvables : {CORPUS_SUBDIRS}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"CSV     : {CSV_PATH.resolve()}")
print(f"Corpus  : {CORPUS_DIR.resolve()}")
print(f"Output  : {OUTPUT_DIR.resolve()}")



# ==============================================================================
# ## 2. Imports et constantes TEI
#
# Définition des namespaces et des noms de balises utilisés tout au long du notebook.
# ==============================================================================

import csv
import shutil
from collections import defaultdict
from lxml import etree

# Namespaces XML/TEI
TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

# Noms de balises avec namespace (forme Clark)
TAG_P   = f"{{{TEI_NS}}}p"
TAG_PTR = f"{{{TEI_NS}}}ptr"
TAG_LG  = f"{{{TEI_NS}}}linkGrp"
TAG_LNK = f"{{{TEI_NS}}}link"
TAG_TXT = f"{{{TEI_NS}}}text"
ATTR_ID = f"{{{XML_NS}}}id"

print("Imports OK")



# ==============================================================================
# ## 3. Fonctions utilitaires sur les identifiants
#
# Les identifiants ont la forme `Auteur_Titre_…_Pn_sXX` ou sont déjà des IDs de paragraphe `Auteur_Titre_…_Pn` :
#
# - `sentence_to_para_id()` retire uniquement un suffixe de phrase (`_sXX`) ; un ID de paragraphe déjà complet est conservé tel quel.
# - `file_key()` extrait les deux premiers segments (`Auteur_Titre`) pour identifier le fichier XML correspondant.
# ==============================================================================

def sentence_to_para_id(sentence_id: str) -> str:
    """
    'FEL_E1_L1_E2_C75_P1_s04'  →  'FEL_E1_L1_E2_C75_P1'
    'FEL_E4_L4_E8_P254'        →  'FEL_E4_L4_E8_P254'
    Retire le suffixe uniquement s'il s'agit d'un numéro de phrase.
    """
    prefix, separator, suffix = sentence_id.rpartition("_")
    if separator and suffix.startswith("s") and suffix[1:].isdigit():
        return prefix
    return sentence_id


def file_key(para_id: str) -> str:
    """
    'FEL_E1_L1_E2_C75_P1'  →  'FEL_E1'
    Retourne les 2 premiers segments : Auteur_Titre.
    """
    parts = para_id.split("_")
    return "_".join(parts[:2])


# ── Tests unitaires rapides ────────────────────────────────────────────────
assert sentence_to_para_id("FEL_E1_L1_E2_C75_P1_s04") == "FEL_E1_L1_E2_C75_P1"
assert sentence_to_para_id("VIN_TP_C75_P3_s01")        == "VIN_TP_C75_P3"
assert sentence_to_para_id("FEL_E4_L4_E8_P254")        == "FEL_E4_L4_E8_P254"
assert file_key("FEL_E1_L1_E2_C75_P1")                 == "FEL_E1"
assert file_key("VIN_TP_C75_P3")                        == "VIN_TP"
print("Fonctions utilitaires OK")



# ==============================================================================
# ## 4. Lecture du CSV
#
# Chargement brut des lignes du fichier de résultats. Les colonnes attendues sont : `ID_1`, `Paragraphe_1`, `ID_2`, `Paragraphe_2`, `Similarite`.
# ==============================================================================

def load_csv(csv_path: Path) -> list[dict]:
    """Retourne la liste des lignes sous forme de dicts (clé = en-tête)."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


rows = load_csv(CSV_PATH)
print(f"{len(rows)} paires lues depuis {CSV_PATH.name}")



# ==============================================================================
# ## 5. Construction des structures de données
#
# Deux structures sont construites à partir des lignes du CSV :
#
# | Structure | Clé | Valeur | Usage |
# |---|---|---|---|
# | `ptr_map` | `para_id` | `{cible, …}` | Insertion des `<ptr>` |
# | `link_map` | `file_key` | `{frozenset(p1,p2) → sim_max}` | Insertion des `<linkGrp>` |
#
# **Règles de déduplication :**
# - Plusieurs phrases reliant les mêmes paragraphes → **un seul lien**,   avec la **similarité maximale** conservée.
# - Auto-liens (même paragraphe des deux côtés) → **ignorés**.
# - `link_map` est alimenté **dans les deux sens** : si la paire `(FEL_P1, VIN_P3)`   est trouvée, elle est enregistrée sous la clé `FEL_E1` *et* sous la clé `VIN_TP`,   de sorte que les deux fichiers recevront un `<linkGrp>`.
# ==============================================================================

def build_data(rows: list[dict]) -> tuple[
    dict[str, set[str]],          # ptr_map  : para_id → {cibles}
    dict[str, dict],              # link_map : file_key → {frozenset(p1,p2) → sim}
]:
    ptr_map: dict[str, set[str]]       = defaultdict(set)
    link_map: dict[str, dict]          = defaultdict(dict)

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

        # ── ptr : A → B et B → A (les deux sens) ─────────────────────────
        ptr_map[p1].add(p2)
        ptr_map[p2].add(p1)

        # ── link : enregistré sous la clé du fichier de p1 ET de p2 ──────
        pair = frozenset((p1, p2))
        for fkey in {file_key(p1), file_key(p2)}:
            if pair not in link_map[fkey] or link_map[fkey][pair] < sim:
                link_map[fkey][pair] = sim

    return ptr_map, link_map


ptr_map, link_map = build_data(rows)

print(f"Paragraphes avec au moins un ptr  : {len(ptr_map)}")
print(f"Fichiers avec au moins un linkGrp : {len(link_map)}")
print(f"Clés de fichiers concernées       : {sorted(link_map.keys())}")



# ==============================================================================
# ## 6. Indexation des fichiers XML du corpus
#
# Le script parcourt récursivement les trois sous-dossiers définis dans `CORPUS_SUBDIRS`, lit le premier `@xml:id` d'un `<p>` dans chaque fichier, et en dérive la clé `Auteur_Titre`. Cela permet d'associer chaque clé du `link_map` au bon fichier, indépendamment du nom de fichier.
# ==============================================================================

def find_xml_files(corpus_dir: Path) -> dict[str, Path]:
    """
    Retourne un dict { file_key → Path } indexé par la clé extraite
    du premier @xml:id d'un <p> dans chaque fichier XML.
    """
    index: dict[str, Path] = {}
    for subdir in CORPUS_SUBDIRS:
        for xml_file in sorted((corpus_dir / subdir).rglob("*.xml")):
            try:
                tree    = etree.parse(str(xml_file))
                first_p = tree.find(f".//{TAG_P}[@{ATTR_ID}]")
                if first_p is not None:
                    pid  = first_p.get(ATTR_ID, "")
                    fkey = file_key(pid)
                    if fkey and fkey not in index:
                        index[fkey] = xml_file
            except etree.XMLSyntaxError:
                print(f"  [AVERT.] XML invalide ignoré : {xml_file}")
    return index


xml_index = find_xml_files(CORPUS_DIR)
print(f"{len(xml_index)} fichiers XML indexés :")
for k, v in sorted(xml_index.items()):
    print(f"  {k:20s} → {v.relative_to(CORPUS_DIR)}")



# ==============================================================================
# ## 7. Enrichissement d'un fichier XML
#
# La fonction `enrich_file()` applique les deux types de modifications à une copie du fichier source :
#
# 1. **`<ptr>`** insérés **au début** de chaque `<p>` concerné (avant le contenu textuel).    Un ptr déjà présent (ré-exécution) n'est pas dupliqué.
# 2. **`<linkGrp>`** inséré comme **premier enfant de `<text>`**.    Un éventuel `<linkGrp>` préexistant est remplacé (idempotence).
# ==============================================================================

def enrich_file(
    src_path : Path,
    dst_path : Path,
    fkey     : str,
    ptr_map  : dict[str, set[str]],
    link_map : dict[str, dict],
) -> int:
    """
    Enrichit une copie du fichier XML.
    Retourne le nombre d'insertions effectuées.
    """
    parser = etree.XMLParser(remove_blank_text=False)
    tree   = etree.parse(str(src_path), parser)
    root   = tree.getroot()
    mods   = 0

    # ── 1. Insertion des <ptr> ─────────────────────────────────────────────
    for p_elem in root.iter(TAG_P):
        para_id = p_elem.get(ATTR_ID)
        if not para_id or para_id not in ptr_map:
            continue

        # Cibles déjà présentes → déduplication sur ré-exécution
        existing: set[str] = {
            e.get("target", "").lstrip("#")
            for e in p_elem.iter(TAG_PTR)
            if e.get("type") == "intertextuality"
        }

        # Insertion en position 0 = avant le contenu textuel du <p>.
        # Dans lxml, le texte du <p> est stocké dans p_elem.text (pas
        # comme nœud enfant). Pour que les <ptr> apparaissent vraiment
        # en premier dans le XML sérialisé, on :
        #   1. crée les <ptr> et les insère à l'index 0 ;
        #   2. déplace p_elem.text sur le .tail du dernier <ptr> inséré.
        nouvelles = sorted(
            [c for c in ptr_map[para_id] if c not in existing],
        )
        if nouvelles:
            # Texte courant du <p> (peut être None)
            original_text = p_elem.text or ""
            # Insère en ordre inverse pour que l'ordre final = alphabétique
            for cible in reversed(nouvelles):
                ptr = etree.Element(TAG_PTR)
                ptr.set("type",   "intertextuality")
                ptr.set("target", f"#{cible}")
                ptr.tail = ""   # sera écrasé ci-dessous pour le dernier
                p_elem.insert(0, ptr)
                existing.add(cible)
                mods += 1
            # Le texte du <p> doit maintenant suivre le dernier <ptr>
            # (index 0 après toutes les insertions)
            p_elem.text = ""          # vide le texte direct du <p>
            p_elem[len(nouvelles) - 1].tail = original_text

    # ── 2. Construction et insertion du <linkGrp> ─────────────────────────
    pairs = link_map.get(fkey, {})
    if pairs:
        lg = etree.Element(TAG_LG)
        lg.set("type", "intertextuality")

        for pair, sim in sorted(pairs.items(), key=lambda x: sorted(x[0])):
            p1, p2 = sorted(pair)
            lnk = etree.SubElement(lg, TAG_LNK)
            lnk.set("target", f"#{p1} #{p2}")
            lnk.set("n",      str(sim))

        text_elem = root.find(f".//{TAG_TXT}")
        if text_elem is not None:
            # Supprime un éventuel linkGrp existant (idempotence)
            old_lg = text_elem.find(f"{TAG_LG}[@type='intertextuality']")
            if old_lg is not None:
                text_elem.remove(old_lg)
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

print("Fonction enrich_file() définie")



# ==============================================================================
# ## 8. Exécution sur l'ensemble du corpus
#
# Parcourt tous les fichiers indexés et applique `enrich_file()`. Les fichiers sans aucun lien sont copiés tels quels dans `output/`.
# ==============================================================================

total_mods = 0
processed  = 0

for fkey, xml_path in sorted(xml_index.items()):
    rel = xml_path.relative_to(CORPUS_DIR)
    dst = OUTPUT_DIR / rel

    mods = enrich_file(xml_path, dst, fkey, ptr_map, link_map)

    if mods:
        print(f"  ✓  {rel}  ({mods} insertions)")
        total_mods += mods
        processed  += 1
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(xml_path, dst)
        print(f"  –  {rel}  (aucun lien, copié tel quel)")

print(f"\nTerminé : {processed} fichier(s) enrichi(s), {total_mods} insertion(s) au total.")



# ==============================================================================
# ## 9. Vérification rapide des fichiers produits
#
# Affiche pour chaque fichier enrichi le nombre de `<linkGrp>`, de `<link>` et de `<ptr>` insérés, pour un contrôle visuel sans ouvrir les XML.
# ==============================================================================

print(f"{'Fichier':<35} {'linkGrp':>7} {'link':>6} {'ptr':>6}")
print("-" * 58)

for xml_file in sorted(OUTPUT_DIR.rglob("*.xml")):
    try:
        tree = etree.parse(str(xml_file))
        root = tree.getroot()
        n_lg  = len(root.findall(f".//{TAG_LG}[@type='intertextuality']"))
        n_lnk = len(root.findall(f".//{TAG_LNK}"))
        n_ptr = len(root.findall(
            f".//{TAG_PTR}[@type='intertextuality']"
        ))
        rel = xml_file.relative_to(OUTPUT_DIR)
        print(f"  {str(rel):<33} {n_lg:>7} {n_lnk:>6} {n_ptr:>6}")
    except etree.XMLSyntaxError:
        print(f"  [ERREUR] {xml_file.name}")


