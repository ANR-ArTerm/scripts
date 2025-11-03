from bs4 import BeautifulSoup, NavigableString
import re
import csv
import os
import sys

def lire_noms_indexPers(fichier_noms): #Définition d'une fonction pour lire les fichiers individuels avec les noms et les identifiants. En créer un dictionnaire avec une clé et une valeur. 
    print("Lecture de l'index des personnes...")
    noms_auteurs = [] #On créer une liste vide qui va contenir le dictionnaire.
    with open(fichier_noms, 'r', encoding='utf-8') as f: #ouvre le fichier qui sera renseigné en tant que fichier_noms
        reader = csv.DictReader(f)  # Utilise DictReader pour lire les noms de colonne
        for row in reader: #Pour chaque ligne dans les colonnes de reader qui est défini au dessus, on execute les manips qui suivent.
            nom = row['Noms'].strip()  # Récupérer la colonne 'Nom'
            id_noms = row['ID'].strip()  # Récupérer la colonne 'Id'
            if nom and id_noms: # Si on a bien un nom et un id on ajoute au dico (avec .append)
                noms = [n.strip() for n in nom.split(',') if n.strip()]
                noms_auteurs.append({'xml:id': id_noms, 'Nom': noms})  # Ajouter au dictionnaire avec 'id' et 'Nom'
    print("Lecture de l'index personnes terminé\n")
    return noms_auteurs

def lire_noms_indexLieux(fichier_lieux):
    print("Lecture de l'index des lieux...")
    noms_lieux = []
    with open(fichier_lieux, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)  # Utilise DictReader pour lire les noms de colonne
        for row in reader:
            lieu = row['Noms'].strip()  # Récupérer la colonne 'Nom'
            id_lieu = row['ID'].strip()  # Récupérer la colonne 'Id'
            if lieu and id_lieu:
                lieux = [n.strip() for n in lieu.split(',') if n.strip()] # permet de récupérer tous les noms d'un lieu qui sont dans une seule case, séparés par une ","
                noms_lieux.append({'id': id_lieu, 'Nom': lieux})  # Ajouter au dictionnaire avec 'id' et 'Noms'
    print("Lecture de l'index lieux terminé\n")
    return noms_lieux

def ajouter_balise(texte, noms_lieux, noms_auteurs): #Définition de la fonction "rechercher" pour les mots qui sont dans les différents dictionnaires qui sont créer au dessus.
    print(f"Ajout des balises dans le fichier {texte}")
    # Remplacer chaque nom d'auteur par une balise <persName>
    for auteur in noms_auteurs: #Pour les auteurs (valeur du dictionnaire noms_auteurs)
        print("Ajout des balises <persName> dans le fichier")
        for pers in auteur['Nom'] :
            texte = re.sub(rf"(?<![#><\w]){pers}(?!<)\b", f'<persName ref="#{auteur["xml:id"]}">{pers}</persName>', texte)
        # re = utilisation des expressions régulières. 
        # .sub permet de remplacer avec les attribut sous cette forme là (valeur recherchée, remplacement, document cible)
        # (?<![#><\w]) Regarde la non présence des caractères entre crochet avant pers. (pour empêcher le balisage des noms dans les ref)
    
    # Remplacer chaque lieu par une balise <placeName>
    for lieu in noms_lieux:
        print("Ajout des balises <placeName> dans le fichier")
        for nom in lieu['Nom']: # test pour toutes les possibilités de Nom dans la variable nom
            texte = re.sub(rf"(?<![#><\w]){nom}(?!<)\b", f'<placeName ref="#{lieu["id"]}">{nom}</placeName>', texte)
    return texte

def lire_date(texte, pattern):
    # Utiliser re.sub avec une fonction de remplacement
    print("Ajout des balises pour les dates")
    def replacer(match):
        year = match.group()  # Extraire la correspondance
        return f'<date when="{year}">{year}</date>'
    
    # Appliquer re.sub pour remplacer toutes les correspondances
    texte = re.sub(pattern, replacer, texte)
    return texte

def ajouter_balises_xml(fichier_xml, fichier_noms, fichier_lieux):
    # Lire les noms d'auteurs à partir du fichier. utilise la fonction que l'on a crée au dessus pour créer les dictionnaires à partir des docs csv. On les appelle dans des variables pour les utiliser.
    noms_auteurs = lire_noms_indexPers(fichier_noms)
    noms_lieux = lire_noms_indexLieux(fichier_lieux)
    pattern = r"\b\d{4}\b" # pattern pour la reconnaissance des dates

    # Lire le fichier XML avec BeautifulSoup
    with open(fichier_xml, 'r', encoding='utf-8') as fichier:
        contenu_xml = fichier.read()

    # Utiliser BeautifulSoup pour parser le fichier XML
    soup = BeautifulSoup(contenu_xml, 'xml')

    # Parcourir les éléments du XML pour ajouter les balises
    for element in soup.find_all(text=True):
        if element.strip():  # Ignorer les éléments vides
            # Ajoute les balises <persName>, <placeName> autour des auteurs et lieux
            nouveau_texte = ajouter_balise(element, noms_lieux, noms_auteurs) #En utilisant la 2ème fonction créée au dessus. Mime la fonction rechercher/remplacer dans le texte.
            
            # Ajoute les balises <date> avec l'attribut @when autour des dates écrites en chiffre arabe
            nouveau_texte = lire_date(nouveau_texte, pattern)
            # Remplacer le texte existant par le nouveau texte avec balises
            element.replace_with(NavigableString(nouveau_texte))

    fichier_modifie = soup.prettify()
    # On remplace les caractères spéciaux en chevron que l'on souhaite avoir dans le doc XML
    fichier_corrige = fichier_modifie.replace("&lt;", "<").replace("&gt;", ">")


    # Création automatique du nom du fichier corrigé
    nom_base = os.path.basename(fichier_xml)  # ex: lettre_12.xml
    nom_sans_ext, _ = os.path.splitext(nom_base)
    fichier_corrige = f"{nom_sans_ext}_corrige.xml"

    with open(fichier_corrige, 'w', encoding='utf-8') as f:
        f.write(fichier_corrige)


    print(f"✅ Le fichier XML a été modifié et sauvegardé sous '{fichier_corrige}'.")

fichier_noms = 'fichiers_noms/auteurs.csv'
fichier_lieux = 'fichiers_noms/lieux.csv'

nom_fichier_xml = input("Entrer le nom du fichier (sans .xml à la fin) :")
if os.path.exists(f"../../corpus/{nom_fichier_xml}.xml"):
    fichier_xml = f"../../corpus/{nom_fichier_xml}.xml"
    print("📂 Fichier trouvé dans le dépôt git corpus !")
elif os.path.exists(f"../../la_muse_voyageuse/textes/{nom_fichier_xml}.xml"):
    fichier_xml = f"../../la_muse_voyageuse/textes/{nom_fichier_xml}.xml"
    print("📂 Fichier trouvé dans le dépôt git la muse voyageuse !")
else:
    print("❌ Fichier non trouvé, vérifier l'emplacement.")
    sys.exit(1)

ajouter_balises_xml(fichier_xml, fichier_noms, fichier_lieux)