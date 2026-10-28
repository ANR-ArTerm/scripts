"""
Extraction des lettrines du corpus ArTerm (détection zero-shot, sans entraînement).

Dépendances :
    pip install ultralytics opencv-python requests beautifulsoup4 lxml numpy
    (YOLO-World télécharge les poids et le module CLIP au premier lancement)
"""
import os
import re
from collections import defaultdict

import cv2
import numpy as np
import requests
from bs4 import BeautifulSoup, Tag, Comment
from ultralytics import YOLOWorld

# ----------------------------- CONFIGURATION -----------------------------
DOSSIER_PRINCIPAL = "../../corpus"
DOSSIER_SORTIE = "alphabet_lettrines"
DOSSIER_ECHECS = os.path.join(DOSSIER_SORTIE, "_echecs")       # pages entières si rien trouvé
DOSSIER_DEBUG = os.path.join(DOSSIER_SORTIE, "_debug")         # pages annotées (boîtes détectées)
DEBUG = True                                                   # mettre False une fois les réglages validés

PREFIXES_EXCLUS = ("Index", "certainty", "header", "glossaire")

POIDS = "yolov8l-worldv2.pt"
CLASSES = ["decorated initial letter", "ornamental drop cap", "historiated initial"]
CONF = 0.03            # seuil bas : en zero-shot les scores sont faibles
IMGSZ = 1280           # pages grand format : meilleure résolution d'inférence
RATIO_MIN, RATIO_MAX = 0.6, 1.6          # lettrine à peu près carrée
AIRE_MIN, AIRE_MAX = 0.002, 0.15         # part de la page (écarte bruit et boîtes "page entière")
MARGE = 5              # pixels autour de la boîte
TIMEOUT = 60

for d in (DOSSIER_SORTIE, DOSSIER_ECHECS) + ((DOSSIER_DEBUG,) if DEBUG else ()):
    os.makedirs(d, exist_ok=True)

print("Chargement du modèle YOLO-World...")
modele = YOLOWorld(POIDS)
modele.set_classes(CLASSES)


# ------------------------------- FONCTIONS -------------------------------
def telecharger_image(url):
    """Télécharge une image et la décode en mémoire (pas de fichier temporaire)."""
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    image = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("image illisible")
    return image


def detecter_boites(image, nb_attendu):
    """
    Retourne au plus `nb_attendu` boîtes (x1, y1, x2, y2) plausibles,
    les mieux notées, triées dans l'ordre de lecture (haut -> bas, gauche -> droite).
    """
    h, w = image.shape[:2]
    resultats = modele.predict(image, conf=CONF, imgsz=IMGSZ, verbose=False)

    candidates = []
    for r in resultats:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])
            bw, bh = x2 - x1, y2 - y1
            if bw <= 0 or bh <= 0:
                continue
            ratio = bw / bh
            aire = (bw * bh) / (w * h)
            if RATIO_MIN <= ratio <= RATIO_MAX and AIRE_MIN <= aire <= AIRE_MAX:
                candidates.append((conf, (x1, y1, x2, y2)))

    candidates.sort(key=lambda c: c[0], reverse=True)
    retenues = [b for _, b in candidates[:nb_attendu]]
    retenues.sort(key=lambda b: (b[1], b[0]))
    return retenues, candidates


def decouper(image, box):
    h, w = image.shape[:2]
    x1, y1, x2, y2 = box
    return image[max(0, y1 - MARGE):min(h, y2 + MARGE), max(0, x1 - MARGE):min(w, x2 + MARGE)]


def extraire_lettre(fig):
    """Première lettre du premier texte non vide qui suit la figure."""
    for sib in fig.next_siblings:
        if isinstance(sib, Comment):
            continue
        texte = (sib.get_text() if isinstance(sib, Tag) else str(sib)).strip()
        if texte:
            m = re.search(r"[^\W\d_]", texte)   # lettre Unicode, accents inclus
            return m.group(0).upper() if m else None
    return None


def sauver_debug(image, candidates, retenues, nom):
    img = image.copy()
    epaisseur = max(2, image.shape[1] // 400)
    for conf, (x1, y1, x2, y2) in candidates:
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 165, 255), epaisseur)       # orange : candidates
    for (x1, y1, x2, y2) in retenues:
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), epaisseur * 2)     # vert : retenues
    cv2.imwrite(os.path.join(DOSSIER_DEBUG, f"{nom}.jpg"), img)


def traiter_xml(chemin_xml, nom_xml_court):
    with open(chemin_xml, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "xml")

    # Regroupement des lettrines par page (<pb> précédent)
    pages = defaultdict(list)       # clé : (url facs, n) -> [(index, lettre), ...]
    for index, fig in enumerate(soup.find_all("figure", type="lettrine"), start=1):
        lettre = extraire_lettre(fig)
        if not lettre:
            print(f"    [-] Lettrine n°{index} : aucune lettre trouvée après la figure")
            continue
        pb = fig.find_previous("pb")
        if not pb or not pb.get("facs"):
            print(f"    [-] Lettrine n°{index} [{lettre}] : pas de <pb facs> valide")
            continue
        pages[(pb["facs"], pb.get("n", "?"))].append((index, lettre))

    for (url, n_page), lettrines in pages.items():
        print(f"    [+] Page {n_page} : {len(lettrines)} lettrine(s) attendue(s)")
        try:
            image = telecharger_image(url)
        except (requests.RequestException, ValueError) as e:
            print(f"    [-] Téléchargement impossible ({url}) : {e}")
            continue

        boites, candidates = detecter_boites(image, len(lettrines))
        nom_page = f"{nom_xml_court}_p{n_page}"
        if DEBUG:
            sauver_debug(image, candidates, boites, nom_page)

        # Une seule page => si autant de boîtes que de lettrines, appariement par ordre de lecture.
        # Sinon on ne peut pas savoir quelle boîte correspond à quelle lettre : page entière en échec.
        if len(boites) == len(lettrines):
            for box, (index, lettre) in zip(boites, lettrines):
                nom = f"lettre_{lettre}_{nom_xml_court}_lettrine{index}.jpg"
                cv2.imwrite(os.path.join(DOSSIER_SORTIE, nom), decouper(image, box))
        else:
            print(f"    [!] {len(boites)} boîte(s) pour {len(lettrines)} lettrine(s) : page mise de côté")
            cv2.imwrite(os.path.join(DOSSIER_ECHECS, f"{nom_page}.jpg"), image)


# ------------------------------ BOUCLE PRINCIPALE ------------------------------
print(f"Début de l'analyse du dossier : {DOSSIER_PRINCIPAL}")
compteur = 0

for racine, _, fichiers in os.walk(DOSSIER_PRINCIPAL):
    for fichier in sorted(fichiers):
        if not fichier.endswith(".xml") or fichier.startswith(PREFIXES_EXCLUS):
            continue
        compteur += 1
        chemin = os.path.join(racine, fichier)
        nom_court = os.path.relpath(os.path.splitext(chemin)[0], DOSSIER_PRINCIPAL).replace(os.sep, "_")
        print(f"\n--- [Fichier {compteur}] {fichier}")
        try:
            traiter_xml(chemin, nom_court)
        except Exception as e:
            print(f"    [-] Erreur sur {fichier} : {e}")

print(f"\n[Terminé] {compteur} fichiers XML analysés. Résultats dans '{DOSSIER_SORTIE}'.")