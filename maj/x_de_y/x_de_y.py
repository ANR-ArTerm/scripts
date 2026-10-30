import re

def search_xml():
    #pour entrer le chemin du fichier XML à scanner dans le terminal
    file_path = input("Chemin du fichier XML : ").strip()
    
    #re.compile = intègre des regex
    #incorpore les caractères spéciaux comme a é etc.

    #pattern pour trouver des correspondances dans les balises
    pattern = re.compile(
            r"[a-zA-ZàâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]+\s+"
            r"(?:de la|de|du|di|del|dello|della|d['’])\s*"
            r"(?:<persName\b[^>]*>|<placeName\b[^>]*>)"
            r"\s*[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ][a-zA-ZàâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]*\s*"
            r"(?:</persName>|</placeName>)"
       ) 

    #pattern pour trouver des correspondances hors balises
    pattern1 = re.compile(
        r"[a-zA-ZàâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]+\s+"
        r"(?:de la|de|du|di|del|dello|della|d['’])"
        r"[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ][a-zA-ZàâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]*"
    )

    #correspondances dans des balises
    try:
        print("-" * 50)
        print(f"CORRESPONDANCES DANS DES BALISES : ")
        print("-" * 50)

        with open(file_path, 'r', encoding='utf-8') as file:
            found = False
            for line_num, line in enumerate(file, 1):
                matches = pattern.findall(line)
                if matches:
                    print(f"Ligne / Riga {line_num}:")
                    for match in matches:
                        print(match)
                    print("-" * 50)
                    found = True
                    
            if not found:
                print("Aucune formulation 'x de y' n'a été trouvée dans les balises.")
                
    except FileNotFoundError:
        print(f"Erreur : Le fichier '{file_path}' n'a pas été trouvé.")
    except Exception as e:
        print(f"Erreur : {e}")


    #correspondances hors des balises
    try:
            print("-" * 50)
            print(f"CORRESPONDANCES HORS BALISES : ")
            print("-" * 50)
            
    
            with open(file_path, 'r', encoding='utf-8') as file:
                found = False
                for line_num, line in enumerate(file, 1):
                    matches = pattern1.findall(line)
                    if matches:
                        print(f"Ligne / Riga {line_num}:")
                        for match in matches:
                            print(match)
                        print("-" * 50)
                        found = True
                        
                if not found:
                    print("Aucune formulation 'x de y' n'a été trouvée hors des balises.")
                    
    except FileNotFoundError:
            print(f"Erreur : Le fichier '{file_path}' n'a pas été trouvé.")
    except Exception as e:
            print(f"Erreur : {e}")    

if __name__ == "__main__":
    search_xml()