#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comparer_ner.py
===============
Compare la qualité des annotations NER (persName, placeName…) de plusieurs
systèmes par rapport à un gold standard TEI-XML.

SYSTÈMES CONFIGURÉS
───────────────────
  • Vbalise  — annotation automatique avec @ref
  • Vspacy   — annotation spaCy, sans @ref
  • Vstanza  — annotation Stanza, sans @ref
  (configurable dans la section CONFIGURATION)

PRINCIPE : ALIGNEMENT PAR LCS (Plus Longue Sous-Séquence Commune)
──────────────────────────────────────────────────────────────────
Les versions annotent le MÊME texte source. On aligne les entités des
deux fichiers via un algorithme LCS (comme `diff`), qui tolère les
insertions et suppressions sans décaler les entités suivantes.

Contrairement à un alignement positionnel naïf (i↔i), si une entité
est absente d'un système, elle devient simplement un FN et les entités
suivantes restent correctement appariées.

Deux entités sont candidates à l'alignement si :
  - leur similarité textuelle (token_sort_ratio) est ≥ seuil
  - OU leurs @ref sont identiques (même entité, graphie différente)

Pour chaque paire alignée on diagnostique :
  Correct          — texte identique ET ref correcte (ou absente des deux)
  @ref manquant    — texte OK mais le système n'a pas produit de @ref
  Erreur @ref      — texte OK mais @ref différente
  Erreur texte     — textes différents mais assez proches (LCS les a alignés)

Entités hors de la LCS :
  Faux négatif     — entité gold sans correspondance système (oubli)
  Faux positif     — entité système sans correspondance gold (invention)

SORTIES CSV
───────────
  rapport_comparaison.csv              — une ligne par entité comparée
  rapport_comparaison_erreurs.csv      — uniquement les lignes non-correctes
  rapport_comparaison_statistiques.csv — précision / rappel / F1 par version×type
  rapport_comparaison_comptage.csv     — nombre d'entités par fichier et version

DÉPENDANCES
───────────
  pip install lxml rapidfuzz

Usage :
    python comparer_ner.py [--seuil 0.80] [--output rapport_comparaison.csv]
                           [--tags persName placeName] [--encoding utf-8]
"""

import argparse
import csv
import re
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lxml import etree
from rapidfuzz import fuzz


# ═══════════════════════════════════════════════════════════════════════
# 1. CONFIGURATION  ← adapter selon l'arborescence du projet
# ═══════════════════════════════════════════════════════════════════════

CORPUS_ROOT   = Path("../")
DOSSIER_GOLD  = CORPUS_ROOT / "corpus-ArTerm/Peinture"
FICHIER_LISTE = CORPUS_ROOT / "CORPUS_Index_Anais/corpus_peinture.txt"
DOSSIER_SORTIE = Path("output")

# Versions à évaluer : label → (chemin_dossier, produit_des_ref)
#   produit_des_ref=True  → le système fournit @ref, on l'évalue aussi
#   produit_des_ref=False → comparaison textuelle uniquement
VERSIONS: Dict[str, Tuple[Path, bool]] = {
    "Vbalise": (CORPUS_ROOT / "CORPUS_Index_Anais/output/Vbalise", True),
    "Vspacy":  (CORPUS_ROOT / "CORPUS_Index_Anais/output/Vspacy",  False),
    "Vstanza": (CORPUS_ROOT / "CORPUS_Index_Anais/output/Vstanza", False),
}

TYPES_ENTITES = ["persName", "placeName"]
TEI_NS = "http://www.tei-c.org/ns/1.0"

# Statuts possibles (ordre d'affichage) — doivent correspondre exactement
# aux valeurs retournées par diagnostiquer_paire() et aligner_et_comparer()
STATUTS = [
    "Correct",        # texte + ref identiques
    "@ref manquant",  # texte OK, ref absente côté système
    "Erreur @ref",    # texte OK, ref différente
    "Erreur texte",   # textes proches (LCS alignés), ref OK ou absente
    "Faux negatif",   # entité gold sans correspondance système
    "Faux positif",   # entité système sans correspondance gold
]

# Statuts comptant comme TP dans les métriques (entité trouvée, même imparfaitement)
STATUTS_TP = {"Correct", "@ref manquant", "Erreur @ref", "Erreur texte"}

# Seuil de similarité utilisé aussi dans l'étape d'alignement LCS
SEUIL_ALIGNEMENT_DEFAULT = 0.80

# Seuil textuel MINIMUM quand deux entités ont la même @ref.
# Calibré sur le corpus : cas DISTINCTS à ~21%, cas à ALIGNER à ~56% minimum.
# → 0.40 sépare proprement les deux populations et garantit des métriques fiables.
#
# Exemples de cas couverts :
#   "ANNIBALE Carracci" ↔ "Carracci"     sim=64% ≥ 40% → aligné   (même occurrence)
#   "Gio. Batt. Agucchi" ↔ "Agucchi"    sim=56% ≥ 40% → aligné   (abréviation)
#   "quell'Autore" ↔ "Gratiadio Machati" sim=21% < 40% → NON aligné (occurrences distinctes)
SEUIL_REF_BONUS = 0.40


# ═══════════════════════════════════════════════════════════════════════
# 2. UTILITAIRES XML
# ═══════════════════════════════════════════════════════════════════════

def nom_local(tag) -> Optional[str]:
    """Supprime le namespace ; retourne None pour PI/commentaires (tag non-str)."""
    if not isinstance(tag, str):
        return None
    return re.sub(r"\{[^}]*\}", "", tag)


def ouvrir_racine(chemin: Path) -> etree._Element:
    """Ouvre un fichier XML en binaire (robuste aux déclarations d'encodage)."""
    with open(chemin, "rb") as fh:
        return etree.parse(fh).getroot()


def texte_element(element) -> str:
    """Texte visible d'une balise, espaces normalisés."""
    return "".join(element.itertext()).strip()


def get_ref(element) -> str:
    """Récupère @ref avec ou sans namespace TEI."""
    return (
        element.get("ref")
        or element.get(f"{{{TEI_NS}}}ref")
        or ""
    ).strip()


def get_para_id(element) -> str:
    """Remonte l'arbre pour trouver le xml:id du paragraphe parent."""
    parent = element.getparent()
    while parent is not None:
        xid = (
            parent.get("{http://www.w3.org/XML/1998/namespace}id")
            or parent.get("xml:id")
        )
        if xid:
            return xid
        parent = parent.getparent()
    return ""


# ═══════════════════════════════════════════════════════════════════════
# 3. EXTRACTION — liste ordonnée des entités dans le document
# ═══════════════════════════════════════════════════════════════════════

def extraire_entites_ordonnees(
    chemin: Path,
    tags: List[str],
    avec_ref: bool,
) -> Optional[Dict[str, List[dict]]]:
    """
    Parcourt le XML dans l'ordre du texte et retourne, par type de balise,
    la liste ordonnée des entités.

    Chaque entité :
        {
          "texte"    : str  — texte visible brut
          "ref"      : str  — valeur @ref (vide si absent/avec_ref=False)
          "para"     : str  — xml:id du paragraphe parent (pour le rapport)
        }

    L'ordre est strictement celui du document source : c'est la base
    de tout l'alignement positionnel.
    """
    if not chemin.exists():
        return None

    try:
        racine = ouvrir_racine(chemin)
    except etree.XMLSyntaxError as e:
        print(f"  [AVERT] XML invalide : {chemin.name} — {e}", file=sys.stderr)
        return None

    entites: Dict[str, List[dict]] = {tag: [] for tag in tags}

    for element in racine.iter():
        tag = nom_local(element.tag)
        if tag is None or tag not in tags:
            continue
        texte = texte_element(element)
        if not texte:
            continue
        entites[tag].append({
            "texte": texte,
            "ref":   get_ref(element) if avec_ref else "",
            "para":  get_para_id(element),
        })

    return entites


def texte_complet(chemin: Path) -> str:
    """Texte visible du document entier (pour extraction de contexte)."""
    try:
        return " ".join("".join(ouvrir_racine(chemin).itertext()).split())
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════
# 4. ALIGNEMENT LCS ET DIAGNOSTIC
# ═══════════════════════════════════════════════════════════════════════

def similarite(a: str, b: str) -> float:
    """Similarité textuelle 0–100 (token_sort_ratio, robuste aux permutations)."""
    return fuzz.token_sort_ratio(a, b)


def peuvent_correspondre(g: dict, s: dict, avec_ref: bool, seuil: float) -> bool:
    """
    Décide si deux entités sont candidates à l'alignement LCS.

    Règles (par ordre de priorité) :
      1. Similarité textuelle ≥ seuil               → appariement direct
      2. @ref identiques ET texte partiellement similaire (≥ SEUIL_REF_BONUS)
         → même entité nommée, graphie différente (ex: "ANNIBALE Carracci" ↔ "Carracci")

    Le critère (2) exige un seuil textuel minimum pour éviter d'aligner deux
    occurrences différentes de la même entité qui ont la même ref mais des textes
    totalement distincts (ex: "quell'Autore" ↔ "Gratiadio Machati" → même #Agucchi
    mais occurrences indépendantes → NE PAS aligner).
    """
    sim = similarite(g["texte"], s["texte"])
    if sim >= seuil * 100:
        return True
    if avec_ref and g["ref"] and s["ref"] and g["ref"] == s["ref"]:
        if sim >= SEUIL_REF_BONUS * 100:
            return True
    return False


def aligner_lcs(
    gold_list: List[dict],
    sys_list: List[dict],
    avec_ref: bool,
    seuil: float,
) -> List[Tuple[Optional[int], Optional[int]]]:
    """
    Aligne les deux listes par LCS (Plus Longue Sous-Séquence Commune).

    Contrairement à l'alignement positionnel naïf (i ↔ i), le LCS tolère
    les insertions et suppressions sans décaler toutes les entités suivantes.

    Exemple :
      Gold    : [Grignani, MOSINI, Carracci, Annibale, Sivello]
      Vbalise : [MOSINI, Annibale, Carracci, Annibale, Sivello]

      Naïf    : Grignani↔MOSINI (✗), MOSINI↔Annibale (✗), ...  ← tout décalé
      LCS     : Grignani→FN, MOSINI↔MOSINI, Annibale→FP,
                Carracci↔Carracci, Annibale↔Annibale, Sivello↔Sivello  ← correct

    Retourne une liste de tuples (idx_gold, idx_sys) :
      (i, j)       → paire alignée
      (i, None)    → FN  : entité gold sans correspondance
      (None, j)    → FP  : entité système sans correspondance
    """
    n_g = len(gold_list)
    n_s = len(sys_list)

    # Matrice booléenne : peut_matcher[i][j] = True si gold[i] ↔ sys[j] possible
    peut = [
        [peuvent_correspondre(gold_list[i], sys_list[j], avec_ref, seuil)
         for j in range(n_s)]
        for i in range(n_g)
    ]

    # Programmation dynamique : dp[i][j] = longueur LCS pour gold[:i], sys[:j]
    dp = [[0] * (n_s + 1) for _ in range(n_g + 1)]
    for i in range(1, n_g + 1):
        for j in range(1, n_s + 1):
            if peut[i-1][j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    # Reconstruction du chemin (lecture à rebours)
    alignements: List[Tuple[Optional[int], Optional[int]]] = []
    i, j = n_g, n_s
    while i > 0 or j > 0:
        if i > 0 and j > 0 and peut[i-1][j-1] and dp[i][j] == dp[i-1][j-1] + 1:
            alignements.append((i-1, j-1))   # paire correspondante
            i -= 1; j -= 1
        elif i > 0 and (j == 0 or dp[i-1][j] >= dp[i][j-1]):
            alignements.append((i-1, None))   # FN
            i -= 1
        else:
            alignements.append((None, j-1))   # FP
            j -= 1

    alignements.reverse()
    return alignements


def diagnostiquer_paire(
    gold: dict,
    sys_e: dict,
    avec_ref_sys: bool,
) -> Tuple[str, float]:
    """
    Diagnostique une paire déjà alignée par LCS.

    La similarité est recalculée ici pour le rapport (le LCS ne l'a utilisée
    que comme critère binaire d'appariement potentiel).

    Hiérarchie :
      texte identique → vérifier @ref
        pas de ref attendue / ref identique → Correct
        ref absente côté système            → @ref manquant
        ref différente                      → Erreur @ref
      texte différent (LCS les a quand même alignés car score ≥ seuil ou ref commune)
        → Erreur texte
    """
    score = similarite(gold["texte"], sys_e["texte"])
    textes_egaux = gold["texte"].lower() == sys_e["texte"].lower()

    if textes_egaux:
        if not avec_ref_sys or not gold["ref"]:
            return "Correct", 100.0
        if not sys_e["ref"]:
            return "@ref manquant", 100.0
        if sys_e["ref"] == gold["ref"]:
            return "Correct", 100.0
        return "Erreur @ref", 100.0
    else:
        # Ici le LCS a jugé qu'ils se correspondent (score ≥ seuil ou ref commune)
        return "Erreur texte", score


def aligner_et_comparer(
    gold_list: List[dict],
    sys_list: List[dict],
    avec_ref_sys: bool,
    seuil_flou: float,
    nom_fichier: str,
    type_entite: str,
    version: str,
    texte_doc: str,
) -> List[dict]:
    """
    Aligne gold et système par LCS puis diagnostique chaque paire.

    L'alignement LCS garantit qu'une entité manquante dans le système
    (FN) ne décale pas les suivantes — contrairement à l'alignement i↔i.
    """
    lignes: List[dict] = []

    alignements = aligner_lcs(gold_list, sys_list, avec_ref_sys, seuil_flou)

    for ig, is_ in alignements:
        if ig is not None and is_ is not None:
            # Paire alignée → diagnostic
            statut, score = diagnostiquer_paire(
                gold_list[ig], sys_list[is_], avec_ref_sys
            )
            lignes.append(_ligne(
                nom_fichier, version, type_entite,
                gold_list[ig], sys_list[is_],
                statut, score, texte_doc,
            ))
        elif ig is not None:
            # Entité gold sans correspondance → Faux négatif
            lignes.append(_ligne(
                nom_fichier, version, type_entite,
                gold_list[ig], None,
                "Faux negatif", 0.0, texte_doc,
            ))
        else:
            # Entité système sans correspondance → Faux positif
            lignes.append(_ligne(
                nom_fichier, version, type_entite,
                None, sys_list[is_],
                "Faux positif", 0.0, texte_doc,
            ))

    return lignes


def _ligne(
    nom_fichier: str,
    version: str,
    type_entite: str,
    gold: Optional[dict],
    sys_e: Optional[dict],
    statut: str,
    score: float,
    texte_doc: str,
) -> dict:
    """Construit un dictionnaire de résultat normalisé."""
    texte_g = gold["texte"]  if gold  else ""
    ref_g   = gold["ref"]    if gold  else ""
    texte_s = sys_e["texte"] if sys_e else ""
    ref_s   = sys_e["ref"]   if sys_e else ""
    para    = (gold or sys_e)["para"]

    tp = 1 if statut in STATUTS_TP    else 0
    fp = 1 if statut == "Faux positif" else 0
    fn = 1 if statut == "Faux negatif" else 0

    return {
        "nom_fichier":          nom_fichier,
        "version":              version,
        "type_entite":          type_entite,
        "paragraphe":           para,
        "texte_gold":           texte_g,
        "ref_gold":             ref_g,
        "texte_systeme":        texte_s,
        "ref_systeme":          ref_s,
        "score_similarite_pct": f"{score:.0f}" if score else "",
        "statut":               statut,
        "TP": tp, "FP": fp, "FN": fn,
        "contexte":             _contexte(texte_doc, texte_g or texte_s),
    }


def _contexte(texte_doc: str, entite: str, fenetre: int = 60) -> str:
    """Extrait un extrait du document centré sur l'entité."""
    if not entite or not texte_doc:
        return ""
    pos = texte_doc.lower().find(entite.lower())
    if pos == -1:
        return entite
    debut = max(0, pos - fenetre)
    fin   = min(len(texte_doc), pos + len(entite) + fenetre)
    extrait = texte_doc[debut:fin]
    idx = extrait.lower().find(entite.lower())
    if idx != -1:
        extrait = (
            extrait[:idx]
            + f"[{extrait[idx:idx+len(entite)]}]"
            + extrait[idx + len(entite):]
        )
    return ("…" if debut > 0 else "") + extrait + ("…" if fin < len(texte_doc) else "")


# ═══════════════════════════════════════════════════════════════════════
# 5. MÉTRIQUES
# ═══════════════════════════════════════════════════════════════════════

def calculer_statistiques(lignes: List[dict]) -> Dict[Tuple, dict]:
    """
    Agrège les résultats par (version × type_entite).

    Totaux :
      total_gold    = toutes les entités gold    = TP + FN
      total_systeme = toutes les entités système = TP + FP

    Métriques :
      Précision = TP / (TP + FP)  = TP / total_systeme
      Rappel    = TP / (TP + FN)  = TP / total_gold
      F1        = 2·P·R / (P+R)

    Détail par statut : n_Correct, n_@ref manquant, n_Erreur @ref,
                        n_Erreur texte, n_Faux negatif, n_Faux positif
    Ces comptages sont indépendants des métriques TP/FP/FN et permettent
    de qualifier la nature des erreurs.
    """
    cpteurs = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0})
    details = defaultdict(lambda: defaultdict(int))

    for l in lignes:
        cle = (l["version"], l["type_entite"])
        cpteurs[cle]["TP"] += l["TP"]
        cpteurs[cle]["FP"] += l["FP"]
        cpteurs[cle]["FN"] += l["FN"]
        details[cle][l["statut"]] += 1

    stats = {}
    for cle, c in cpteurs.items():
        tp, fp, fn = c["TP"], c["FP"], c["FN"]
        p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        d  = details[cle]

        # Vérification de cohérence : sum des statuts = total lignes
        assert sum(d.values()) == tp + fp + fn, \
            f"Incohérence comptage pour {cle}: {sum(d.values())} ≠ {tp+fp+fn}"

        stats[cle] = {
            "total_gold":           tp + fn,
            "total_annote_systeme": tp + fp,  # nb d'entités produites par le système
            "vrais_positifs":       tp,
            "faux_positifs":        fp,
            "faux_negatifs":        fn,
            "precision_pct":        round(p  * 100, 2),
            "rappel_pct":           round(r  * 100, 2),
            "f1_pct":               round(f1 * 100, 2),
            # Détail par statut — noms exacts de STATUTS
            **{f"n_{s}": d.get(s, 0) for s in STATUTS},
        }
    return stats


# ═══════════════════════════════════════════════════════════════════════
# 6. ÉCRITURE CSV
# ═══════════════════════════════════════════════════════════════════════

def ecrire_csv(chemin: Path, colonnes: List[str], lignes: List[dict]):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=colonnes, delimiter=";", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(lignes)
    print(f"  [SORTIE] {chemin}  ({len(lignes)} lignes)")


# ═══════════════════════════════════════════════════════════════════════
# 7. MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Comparaison NER positionnelle — Gold vs systèmes TEI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--seuil",    type=float, default=0.80,
                        help="Seuil similarité floue 0–1 (défaut : 0.80). "
                             "Ex: 'il Carracci' vs 'Carracci' ≈ 84%% → Erreur texte si seuil ≤ 0.84")
    parser.add_argument("--output",   default="rapport_comparaison.csv",
                        help="Nom du CSV de sortie principal")
    parser.add_argument("--tags",     nargs="+", default=TYPES_ENTITES,
                        help="Balises TEI à évaluer")
    parser.add_argument("--encoding", default="utf-8",
                        help="Encodage des fichiers texte")
    args = parser.parse_args()

    DOSSIER_SORTIE.mkdir(exist_ok=True)
    chemin_base = DOSSIER_SORTIE / args.output

    # Ne garder que les versions dont le dossier existe
    versions_actives = {
        v: (Path(d), r)
        for v, (d, r) in VERSIONS.items()
        if Path(d).is_dir()
    }

    print(f"\n{'='*72}")
    print(f"  COMPARAISON NER — alignement positionnel")
    print(f"  Versions actives : {', '.join(versions_actives) or '(aucune)'}")
    print(f"  Seuil flou : {args.seuil*100:.0f}%   |   Entités : {args.tags}")
    print(f"{'='*72}\n")

    if not FICHIER_LISTE.exists():
        sys.exit(f"[ERREUR] Fichier liste introuvable : {FICHIER_LISTE}")

    with open(FICHIER_LISTE, encoding=args.encoding) as f:
        noms_fichiers = [
            l.strip() if l.strip().endswith(".xml") else l.strip() + ".xml"
            for l in f if l.strip()
        ]
    print(f"  {len(noms_fichiers)} fichier(s) dans la liste\n")

    # ── Boucle principale ────────────────────────────────────────────────────
    toutes_lignes: List[dict] = []
    comptage: dict = {}
    manquants: set = set()

    for nom in noms_fichiers:
        chemin_gold = Path(DOSSIER_GOLD) / nom
        gold_entites = extraire_entites_ordonnees(chemin_gold, args.tags, avec_ref=True)

        if gold_entites is None:
            print(f"  [SKIP] {nom} — gold absent ou invalide")
            continue

        texte_doc = texte_complet(chemin_gold)
        comptage[nom] = {}
        print(f"  ── {nom}")

        for tag in args.tags:
            nb = len(gold_entites.get(tag, []))
            comptage[nom][f"gold_{tag}"] = nb
            print(f"     {'Gold':12s} {tag:12s}: {nb:3d}")

        for version, (dossier, avec_ref) in versions_actives.items():
            chemin_sys = dossier / nom
            sys_entites = extraire_entites_ordonnees(chemin_sys, args.tags, avec_ref=avec_ref)

            if sys_entites is None:
                manquants.add((version, nom))
                for tag in args.tags:
                    comptage[nom][f"{version.lower()}_{tag}"] = "N/A"
                print(f"     {version:12s} ✗ ABSENT")
                continue

            for tag in args.tags:
                nb = len(sys_entites.get(tag, []))
                comptage[nom][f"{version.lower()}_{tag}"] = nb
                print(f"     {version:12s} {tag:12s}: {nb:3d}")

            try:
                for tag in args.tags:
                    lignes = aligner_et_comparer(
                        gold_list    = gold_entites.get(tag, []),
                        sys_list     = sys_entites.get(tag, []),
                        avec_ref_sys = avec_ref,
                        seuil_flou   = args.seuil,
                        nom_fichier  = nom,
                        type_entite  = tag,
                        version      = version,
                        texte_doc    = texte_doc,
                    )
                    toutes_lignes.extend(lignes)
            except Exception as e:
                print(f"     [{version}] ERREUR : {e}", file=sys.stderr)
                traceback.print_exc()

        print()

    # ── CSV 1 : rapport détaillé complet ─────────────────────────────────────
    colonnes_detail = [
        "nom_fichier", "version", "type_entite", "paragraphe",
        "texte_gold", "ref_gold",
        "texte_systeme", "ref_systeme",
        "score_similarite_pct", "statut",
        "TP", "FP", "FN",
        "contexte",
    ]
    ecrire_csv(chemin_base, colonnes_detail, toutes_lignes)

    # ── CSV 2 : erreurs uniquement ────────────────────────────────────────────
    lignes_erreurs = [l for l in toutes_lignes if l["statut"] != "Correct"]
    ecrire_csv(
        chemin_base.with_name(chemin_base.stem + "_erreurs.csv"),
        colonnes_detail,
        lignes_erreurs,
    )

    # ── CSV 3 : statistiques globales ─────────────────────────────────────────
    stats = calculer_statistiques(toutes_lignes)
    colonnes_stats = [
        "version", "type_entite",
        "total_gold", "total_annote_systeme",
        "vrais_positifs", "faux_positifs", "faux_negatifs",
        "precision_pct", "rappel_pct", "f1_pct",
    ] + [f"n_{s}" for s in STATUTS]

    lignes_stats = []
    for (version, tag), s in sorted(stats.items()):
        avec_ref = VERSIONS.get(version, (None, False))[1]
        ligne = {"version": version, "type_entite": tag, **s}
        # Colonnes ref sans objet pour les systèmes sans @ref
        if not avec_ref:
            ligne["n_@ref manquant"] = "N/A"
            ligne["n_Erreur @ref"]   = "N/A"
        lignes_stats.append(ligne)
    ecrire_csv(
        chemin_base.with_name(chemin_base.stem + "_statistiques.csv"),
        colonnes_stats,
        lignes_stats,
    )

    # ── CSV 4 : comptage par fichier ──────────────────────────────────────────
    colonnes_comptage = (
        ["nom_fichier"]
        + [f"gold_{t}" for t in args.tags]
        + [f"{v.lower()}_{t}" for v in versions_actives for t in args.tags]
    )
    lignes_comptage = [{"nom_fichier": n, **c} for n, c in sorted(comptage.items())]
    ecrire_csv(
        chemin_base.with_name(chemin_base.stem + "_comptage.csv"),
        colonnes_comptage,
        lignes_comptage,
    )

    # ── Résumé console ────────────────────────────────────────────────────────
    print(f"\n{'='*95}")
    print("  RÉSUMÉ DES MÉTRIQUES")
    print(f"{'='*95}")
    print(
        f"  {'Version':<12} {'Type':<12}"
        f"  {'Gold':>5} {'Annoté':>6}"
        f"  {'Rappel%':>8} {'Précis%':>8} {'F1%':>6}"
        f"  {'Correct':>7} {'@refMq':>6} {'ErrRef':>6} {'ErrTxt':>7}"
        f"  {'FN':>4} {'FP':>4}"
        f"  {'Check':>7}"
    )
    print(f"  {'-'*95}")
    for (version, tag), s in sorted(stats.items()):
        avec_ref = VERSIONS.get(version, (None, False))[1]

        # ErrRef n'a de sens que pour les versions qui produisent des @ref
        err_ref_str = f"{s['n_Erreur @ref']:>6}" if avec_ref else f"{'N/A':>6}"
        ref_mq_str  = f"{s['n_@ref manquant']:>6}" if avec_ref else f"{'N/A':>6}"

        total_lignes = sum(s[f"n_{st}"] for st in STATUTS)
        check = "✓" if total_lignes == s["total_gold"] + s["faux_positifs"] else f"✗{total_lignes}"
        print(
            f"  {version:<12} {tag:<12}"
            f"  {s['total_gold']:>5} {s['total_annote_systeme']:>6}"
            f"  {s['rappel_pct']:>7.1f}% {s['precision_pct']:>7.1f}% {s['f1_pct']:>5.1f}%"
            f"  {s['n_Correct']:>7}"
            f"  {ref_mq_str}"
            f"  {err_ref_str}"
            f"  {s['n_Erreur texte']:>7}"
            f"  {s['n_Faux negatif']:>4}"
            f"  {s['n_Faux positif']:>4}"
            f"  {check:>7}"
        )
    print(f"{'='*95}")
    print(f"  Annoté = nb d'entités produites par le système (= TP + FP)")
    print(f"  N/A    = colonne sans objet (système sans @ref)\n")

    if manquants:
        print("  Fichiers manquants :")
        for version, nom in sorted(manquants):
            print(f"    ✗ {version} / {nom}")
        print()

    print("  Traitement terminé.\n")


if __name__ == "__main__":
    main()