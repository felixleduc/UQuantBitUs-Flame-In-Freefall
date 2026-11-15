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
    nom_test: str = Field(description="Nom du test ou fichier source")
    fuel_type: str | None = Field(description="Type de combustible (solid, gas, droplet)")
    material_family: str | None = Field(description="Famille du matériau ou combustible")
    geometry: str | None = Field(description="Géométrie du matériau")
    gravite_g: float | None = Field(description="Le niveau de gravité de l'environnement")
    o2_percent: float | None = Field(description="Le pourcentage d'oxygène")
    pressure_atm: float | None = Field(description="Pression de l'expérience en atmosphères")
    flow_cm_s: float | None = Field(description="Flux de ventilation ou de chaleur en cm/s")
    thickness_mm: float | None = Field(description="Épaisseur en mm")
    diameter_mm: float | None = Field(description="Diamètre en mm")
    ignited: str | None = Field(description="Indique si le matériau s'est enflammé (yes/no)")
    outcome: str | None = Field(description="Issue de l'expérience")
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
    # 1. Identification du type de combustible
    fuel_type = "solid"
    if re.search(r"gas|burner|jet", texte, re.IGNORECASE):
        fuel_type = "gas jet"
    elif re.search(r"droplet|gouttelette", texte, re.IGNORECASE):
        fuel_type = "droplet"

    # 2. Identification de la famille du matériau
    material_family = "Non-Spécifié"
    for mat in ["cotton", "PMMA", "Nomex", "heptane", "Kapton", "acrylic", "cellulose"]:
        if re.search(mat, texte, re.IGNORECASE):
            material_family = mat.capitalize()
            break

    # 3. Extraction des métriques clés alignées sur tests.csv
    o2_percent = extraire_valeur(r"(\d+(?:\.\d+)?)\s*%\s*(?:O2|oxygen)", texte)
    flow_cm_s = extraire_valeur(r"(\d+(?:\.\d+)?)\s*cm/s", texte)
    
    # Conversion de kPa en atm (1 atm ≈ 101.3 kPa) si trouvé, sinon valeur par défaut
    pression_kpa = extraire_valeur(r"(\d+(?:\.\d+)?)\s*kPa", texte)
    pressure_atm = pression_kpa / 101.3 if pression_kpa else 1.0

    thickness_mm = extraire_valeur(r"(\d+(?:\.\d+)?)\s*mm\s*(?:thick|thickness)", texte)
    diameter_mm = extraire_valeur(r"(\d+(?:\.\d+)?)\s*mm\s*(?:diam|diameter)", texte)
    
    gravite = 0.0 if re.search(r"microgravity|zero-g|0\s*g|ISS", texte, re.IGNORECASE) else 1.0

    # 4. Détermination de l'inflammation (yes/no) et de l'issue
    ignited = "yes" if re.search(r"ignite|flame sustained|burning", texte, re.IGNORECASE) else "no"
    outcome = "success" if ignited == "yes" else "extinguished"

    vitesse = extraire_valeur(r"(\d+(?:\.\d+)?)\s*mm/s", texte)
    v_propagation = vitesse / 1000.0 if vitesse else None  # conversion en m/s si besoin

    return {
        "nom_test": nom_fichier,
        "fuel_type": fuel_type,
        "material_family": material_family,
        "geometry": "sheet" if thickness_mm else "rod",
        "gravite_g": gravite,
        "o2_percent": o2_percent,
        "pressure_atm": pressure_atm,
        "flow_cm_s": flow_cm_s,
        "thickness_mm": thickness_mm,
        "diameter_mm": diameter_mm,
        "ignited": ignited,
        "outcome": outcome,
        "v_propagation_m_s": v_propagation,
        "alertes": "Alerte critique O2" if o2_percent and o2_percent > 25.0 else "Normal",
    }


def main() -> None:
    dossier_entree = "donnees_brutes"
    dossier_sortie = "data/processed"  # Aligné sur le dossier attendu par le ML
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

    chemin_csv = os.path.join(dossier_sortie, "tests.csv")
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


if __name__ == "__main__":
    main()