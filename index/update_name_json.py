#!/usr/bin/env python3
"""
Script de renommage des fichiers JSON de notices selon leur champ "id".

Parcourt les dossiers entry_artwork, entry_building, entry_ensemble
contenus dans le dossier data, et renomme chaque fichier .json pour
que son nom corresponde à la valeur du champ "id" contenu dans le JSON.

Produit un fichier CSV récapitulatif avec :
- le dossier concerné
- l'ancien nom de fichier
- le nouveau nom de fichier (basé sur l'id)
- le statut de l'opération (renommé / inchangé / erreur)
- un message éventuel (erreur, collision, etc.)
"""

import json
import csv
from pathlib import Path

# ============================================================
# CONFIGURATION - à adapter selon votre environnement
# ============================================================
DATA_DIR = "../../index_oeuvres/data"                       # dossier contenant entry_artwork, entry_building, entry_ensemble
OUTPUT_CSV = "rename_objectname.csv"     # fichier CSV de sortie
SUBFOLDERS = ["entry_artwork", "entry_building", "entry_ensemble"]
ID_FIELD = "id"          # nom du champ JSON contenant l'identifiant
DRY_RUN = False          # True = simulation sans renommer réellement les fichiers
# ============================================================


def process_folder(folder_path: Path, rows: list):
    if not folder_path.exists():
        print(f"⚠️  Dossier introuvable : {folder_path}")
        return

    json_files = sorted(folder_path.glob("*.json"))
    print(f"📁 {folder_path.name} : {len(json_files)} fichier(s) JSON trouvé(s)")

    for json_file in json_files:
        old_name = json_file.name
        status = ""
        new_name = ""
        message = ""

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            status = "erreur"
            message = f"Impossible de lire/parser le JSON : {e}"
            rows.append([folder_path.name, old_name, new_name, status, message])
            print(f"  ❌ {old_name} : {message}")
            continue

        entry_id = data.get(ID_FIELD)

        if entry_id is None or str(entry_id).strip() == "":
            status = "erreur"
            message = f"Champ '{ID_FIELD}' absent ou vide"
            rows.append([folder_path.name, old_name, new_name, status, message])
            print(f"  ❌ {old_name} : {message}")
            continue

        expected_name = f"{entry_id}.json"
        new_name = expected_name

        if old_name == expected_name:
            status = "inchangé"
            rows.append([folder_path.name, old_name, new_name, status, message])
            continue

        target_path = json_file.with_name(expected_name)

        if target_path.exists():
            status = "erreur"
            message = "Un fichier avec ce nom existe déjà (collision)"
            rows.append([folder_path.name, old_name, new_name, status, message])
            print(f"  ⚠️  {old_name} -> {expected_name} : {message}")
            continue

        if DRY_RUN:
            status = "simulé (dry-run)"
            message = "Aucune modification réelle (DRY_RUN=True)"
        else:
            try:
                json_file.rename(target_path)
                status = "renommé"
            except Exception as e:
                status = "erreur"
                message = f"Échec du renommage : {e}"

        rows.append([folder_path.name, old_name, new_name, status, message])
        icon = "✅" if status == "renommé" else "🔎" if "simulé" in status else "❌"
        print(f"  {icon} {old_name} -> {expected_name} ({status})")


def main():
    data_dir = Path(DATA_DIR)
    rows = []

    for subfolder in SUBFOLDERS:
        process_folder(data_dir / subfolder, rows)

    output_path = Path(OUTPUT_CSV)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["dossier", "ancien_nom", "nouveau_nom", "statut", "message"])
        writer.writerows(rows)

    total = len(rows)
    renamed = sum(1 for r in rows if r[3] == "renommé")
    unchanged = sum(1 for r in rows if r[3] == "inchangé")
    errors = sum(1 for r in rows if r[3] == "erreur")

    print("\n=== Résumé ===")
    print(f"Total de fichiers traités : {total}")
    print(f"Renommés                  : {renamed}")
    print(f"Inchangés                 : {unchanged}")
    print(f"Erreurs                   : {errors}")
    print(f"Rapport CSV               : {output_path}")


if __name__ == "__main__":
    main()