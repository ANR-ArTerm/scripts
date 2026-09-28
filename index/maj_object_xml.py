#!/usr/bin/env python3
"""
Script de mise à jour des identifiants dans les balises <objectName> des
fichiers XML du corpus, à partir de la table de correspondance produite
par le script "renommer_json_par_id.py" (ancien_nom / nouveau_nom).

Parcourt les dossiers Peinture, Architecture, Perspective contenus dans
le dossier corpus, et pour chaque fichier .xml, cherche les balises du
type :

    <objectName ref="#AncienIdentifiant">...</objectName>

et remplace l'identifiant par le nouveau, si celui-ci figure dans le CSV
de correspondance fourni.

Produit un fichier CSV récapitulatif des remplacements effectués.
"""

import csv
import re
from pathlib import Path

# ============================================================
# CONFIGURATION - à adapter selon votre environnement
# ============================================================
CORPUS_DIR = "../../cahier_des_charges/corpus"                         # dossier contenant Peinture, Architecture, Perspective
MAPPING_CSV = "rename_objectname.csv"          # CSV produit par le 1er script (ancien_nom -> nouveau_nom)
OUTPUT_CSV = "rapport_maj_objectname.csv"      # CSV de rapport de ce script
SUBFOLDERS = ["Peinture", "Architecture", "Perspective"]
DRY_RUN = False          # True = simulation sans modifier réellement les fichiers XML
# ============================================================

# Regex qui capture : tout ce qui précède "ref=" à l'intérieur de la balise
# <objectName ...>, puis la valeur de l'attribut ref elle-même.
# re.DOTALL permet de gérer les balises réparties sur plusieurs lignes.
OBJECTNAME_REF_PATTERN = re.compile(
    r'(<objectName\b(?:(?!ref\s*=)[\s\S])*?ref\s*=\s*")([^"]*)(")',
    re.IGNORECASE
)


def load_mapping(mapping_csv_path: Path) -> dict:
    """
    Charge le CSV de correspondance produit par le script de renommage JSON
    et retourne un dict {ancien_id: nouveau_id}, en retirant l'extension .json.
    Ignore les lignes sans nouveau_nom (erreurs) ou sans changement réel.
    """
    mapping = {}
    with open(mapping_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ancien_nom = (row.get("ancien_nom") or "").strip()
            nouveau_nom = (row.get("nouveau_nom") or "").strip()

            if not ancien_nom or not nouveau_nom:
                continue

            ancien_id = ancien_nom[:-5] if ancien_nom.lower().endswith(".json") else ancien_nom
            nouveau_id = nouveau_nom[:-5] if nouveau_nom.lower().endswith(".json") else nouveau_nom

            if ancien_id != nouveau_id:
                mapping[ancien_id] = nouveau_id

    return mapping


def process_xml_file(xml_path: Path, mapping: dict, folder_name: str, rows: list) -> bool:
    """
    Traite un fichier XML : remplace les identifiants dans les ref des
    balises <objectName>. Retourne True si le fichier a été modifié.
    """
    try:
        content = xml_path.read_text(encoding="utf-8")
    except Exception as e:
        rows.append([folder_name, xml_path.name, "", "", "erreur", f"Lecture impossible : {e}"])
        print(f"  ❌ {xml_path.name} : lecture impossible ({e})")
        return False

    file_changed = False

    def replacer(match: re.Match) -> str:
        nonlocal file_changed
        prefix, ref_value, suffix = match.group(1), match.group(2), match.group(3)

        has_hash = ref_value.startswith("#")
        ancien_id = ref_value[1:] if has_hash else ref_value

        if ancien_id in mapping:
            nouveau_id = mapping[ancien_id]
            nouveau_ref = f"#{nouveau_id}" if has_hash else nouveau_id
            rows.append([folder_name, xml_path.name, ancien_id, nouveau_id, "remplacé", ""])
            print(f"  ✅ {xml_path.name} : {ancien_id} -> {nouveau_id}")
            file_changed = True
            return f"{prefix}{nouveau_ref}{suffix}"

        return match.group(0)

    new_content = OBJECTNAME_REF_PATTERN.sub(replacer, content)

    if file_changed and not DRY_RUN:
        try:
            xml_path.write_text(new_content, encoding="utf-8")
        except Exception as e:
            rows.append([folder_name, xml_path.name, "", "", "erreur", f"Écriture impossible : {e}"])
            print(f"  ❌ {xml_path.name} : écriture impossible ({e})")
            return False

    return file_changed


def process_folder(folder_path: Path, mapping: dict, rows: list):
    if not folder_path.exists():
        print(f"⚠️  Dossier introuvable : {folder_path}")
        return

    xml_files = sorted(folder_path.glob("*.xml"))
    print(f"📁 {folder_path.name} : {len(xml_files)} fichier(s) XML trouvé(s)")

    for xml_file in xml_files:
        process_xml_file(xml_file, mapping, folder_path.name, rows)


def main():
    corpus_dir = Path(CORPUS_DIR)
    mapping_csv_path = Path(MAPPING_CSV)

    if not mapping_csv_path.exists():
        print(f"❌ Fichier de correspondance introuvable : {mapping_csv_path}")
        return

    mapping = load_mapping(mapping_csv_path)
    print(f"🔗 {len(mapping)} correspondance(s) ancien_id -> nouveau_id chargée(s)\n")

    rows = []
    for subfolder in SUBFOLDERS:
        process_folder(corpus_dir / subfolder, mapping, rows)

    output_path = Path(OUTPUT_CSV)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["dossier", "fichier_xml", "ancien_id", "nouveau_id", "statut", "message"])
        writer.writerows(rows)

    total = len(rows)
    remplaces = sum(1 for r in rows if r[4] == "remplacé")
    erreurs = sum(1 for r in rows if r[4] == "erreur")

    print("\n=== Résumé ===")
    print(f"Total de remplacements/entrées : {total}")
    print(f"Remplacés                      : {remplaces}")
    print(f"Erreurs                         : {erreurs}")
    print(f"Rapport CSV                     : {output_path}")
    if DRY_RUN:
        print("⚠️  DRY_RUN activé : aucun fichier XML n'a été modifié réellement.")


if __name__ == "__main__":
    main()