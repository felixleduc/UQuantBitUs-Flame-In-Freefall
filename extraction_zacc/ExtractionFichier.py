import csv
import glob
import os
import re

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency for CSV export
    pd = None

from pydantic import BaseModel, Field
from pypdf import PdfReader


class TestNasa(BaseModel):
    nom_test: str = Field(description="Nom du test")
    gravite_g: float | None = Field(
        description="Le niveau de gravité de l'environnement où se situe la combustion"
    )
    oxygene_pct: float | None = Field(
        description="Le pourcentage d'oxygène de l'environnement où se situe la combustion"
    )
    pression_psi: float | None = Field(description="Pression de l'expérience")
    flux_cm_s: float | None = Field(description="Flux de ventilation ou de chaleur")
    forme_flamme: str | None = Field(description="La morphologie (forme, couleur, etc)")
    v_propagation_m_s: float | None = Field(description="Vitesse de propagation")
    alertes: str | None = Field(description="Alertes ou commentaires de sécurité")


def lecture_pdf(chemin_fichier: str) -> str:
    lecteur = PdfReader(chemin_fichier)
    texte_pages: list[str] = []
    for page in lecteur.pages:
        contenu = page.extract_text()
        if contenu:
            texte_pages.append(contenu)
    return "\n".join(texte_pages)


def extraire_valeur(motif_regex: str, texte: str) -> float | None:
    recherche = re.search(motif_regex, texte, re.IGNORECASE)
    if recherche:
        try:
            return float(recherche.group(1))
        except ValueError:
            return None
    return None


def analyser_rapport(texte: str, nom_fichier: str) -> dict:
    experience = "Expérience Nasa"
    for prog in ["Bass-II", "BASS", "SoFIE", "Saffire", "FLEX", "BRE"]:
        if re.search(prog, texte, re.IGNORECASE):
            experience = prog
            break

    materiau = "Non-Spécifié"
    for mat in ["cotton", "PMMA", "Nomex", "heptane", "Kapton", "acrylic", "cellulose"]:
        if re.search(mat, texte, re.IGNORECASE):
            materiau = mat.capitalize()
            break

    oxygene = extraire_valeur(r"(\d+(?:\.\d+)?)\s*%\s*(?:O2|oxygen)", texte)
    ventilation = extraire_valeur(r"(\d+(?:\.\d+)?)\s*cm/s", texte)
    pression = extraire_valeur(r"(\d+(?:\.\d+)?)\s*kPa", texte)
    flux_thermique = extraire_valeur(r"(\d+(?:\.\d+)?)\s*kW/m", texte)
    epaisseur = extraire_valeur(r"(\d+(?:\.\d+)?)\s*mm\s*(?:thick|thickness)", texte)
    vitesse = extraire_valeur(r"(\d+(?:\.\d+)?)\s*mm/s", texte)
    gravite = 0.0 if re.search(r"microgravity|zero-g|0\s*g|ISS", texte, re.IGNORECASE) else 1.0

    if oxygene is not None and oxygene > 25.0:
        risque = "Critique"
    elif ventilation is not None and ventilation > 5.0:
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
        "fichier_source": nom_fichier,
    }


def main() -> None:
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
        texte = lecture_pdf(fichier)
        donnees = analyser_rapport(texte, nom)
        resultats.append(donnees)

    chemin_csv = os.path.join(dossier_sortie, "experiences_nasa.csv")
    if pd is not None:
        df = pd.DataFrame(resultats)
        df.to_csv(chemin_csv, index=False, encoding="utf-8")
        print(f"\nTerminé ! Tableau sauvegardé dans '{chemin_csv}'.")
        print(df.head())
    else:
        fieldnames = list(resultats[0].keys()) if resultats else []
        with open(chemin_csv, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(resultats)
        print(f"\nTerminé ! Tableau sauvegardé dans '{chemin_csv}'.")
        print(resultats[:5])


if __name__ == "__main__":
    main()