import os 
import pandas as pd 
import pypdf import PdfReader 
import pydantic import BaseModel 



class TestNasa(BaseModel):
    nom_test: str = Field(
        description="Nom du test"       
    )                   #Entrées 
    gravite_g: float | None= Field(
        description="Le niveau de gravité de l'environnement où se situe la combustion"
    )
    oxygene_pct: float | None=Field(
        description="Le pourcentage d'oxygène de l'environnement où se situe la combustion"
    )
    pression_psi: float | None=Field(   
        description=""
    )
    flux_cm/s: float |None=Field(  
        description="wsew"
    ) #Sorties 
    forme_flamme: str | None=Field(
        description="La morphologie (forme, couleur, etc)" 
    )
    v_propagation_m/s: float | None=Field(  
        description=""
    )
    Alertes: str | None= Field(
        description=""
    )





def lecture_pdf(chemin_fichier:str) -> str:
    lecteur = PdfReader(chemin_fichier)
    texte = []
        for page in lecteur.pages 
             contenu = page.extract_text()
             if contenu:
                texte.append(contenu)
return"\n" .join(texte)

def extraire_valeur(motif_regex:str, texte:str) -> float| None = Field(
    recherche = re.search(motif_regex, texte, re.IGNORECASE)
    if recherhe:
        try:
            return float(recherhe.group(1))
        except ValueError
            return None
    return None 
)

def analyser_rapport(texte: str, nom_fichier: str) -> dict:
    experience = "Expérience Nasa"
    for prog in ["Bass-II", "BASS", "SoFIE", "Saffire", "FLEX", "BRE"]:
        if re.search(mat, texte, re.IGNORECASE):
            experience = prog 
            break

materiau = "Non-Spécifié"
for mat in ["cotton", "PMMA", "Nomex", "heptane", "Kapton", "acrylic", "cellulose"]:
     if re.search(mat, texte, re.IGNORECASE):
        materiau= mat.capitalize()
        break

oxygene = extraire_valeur(r"(\d+(?:\.\d+)?)\s*%\s*(?:O2|oxygen)", texte)
ventilation = extraire_valeur(r"(\d+(?:\.\d+)?)\s*cm/s", texte)
pression = extraire_valeur(r"(\d+(?:\.\d+)?)\s*kPa", texte)
flux_thermique = extraire_valeur(r"(\d+(?:\.\d+)?)\s*kW/m", texte)
epaisseur = extraire_valeur(r"(\d+(?:\.\d+)?)\s*mm\s*(?:thick|thickness)", texte)
vitesse = extraire_valeur(r"(\d+(?:\.\d+)?)\s*mm/s", texte)
gravite = 0.0 if re.search(r"microgravity|zero-g|0\s*g|ISS", texte, re.IGNORECASE) else 1.0

if oxygene is not None and oxygene > 25.0:
    risque ="Critique"
elif ventilation is not None and  ventilation > 5.0: 
    risque = "Modéré"
else:
    risque = "Faible"

 return {
        "nom_experience": experience,
        "materiau": materiau,
        "gravite_g": gravite,
        "oxygene_pct": oxygene,
        "ventilation_cms": ventilation,
        "pression_kpa": pression,
        "flux_thermique_kwm2": flux_thermique,
        "epaisseur_mm": epaisseur,
        "vitesse_mm_s": vitesse,
        "niveau_risque": risque,
        "fichier_source": nom_fichier
    }

def main():
    dossier_entree = "donnees_brutes"
    dossier_sortie = "donnees_propres"
    os.makedirs(dossier_entree, exist_ok=True)
    os.makedirs(dossier_sortie, exist_ok=True)

    fichiers_pdf = glob.glob(os.path.join(dossier_entree, "*.pdf"))
    if not fichiers_pdf:
        print(f"Ajoutez vos fichiers PDF dans '{dossier_entree}/' puis relancez.")
        return

    resultats = []
    for fichier in fichiers_pdf:
        nom = os.path.basename(fichier)
        print(f"Lecture de {nom}...")
        texte = lire_pdf(fichier)
        donnees = analyser_rapport(texte, nom)
        resultats.append(donnees)

    df = pd.DataFrame(resultats)
    chemin_csv = os.path.join(dossier_sortie, "experiences_nasa.csv")
    df.to_csv(chemin_csv, index=False, encoding="utf-8")
    print(f"\nTerminé ! Tableau sauvegardé dans '{chemin_csv}'.")
    print(df.head())

if __name__ == "__main__":
    main()
