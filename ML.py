import os
import panda as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib


def entrainer_modele():
    chemin_csv = "donnees_propres/experiences_nasa.csv"
    if not os.path.exists(chemin_csv):
        print(f"Erreur : Le fichier {chemin_csv} est introuvable. Lancez d'abord votre extracteur PDF.")
        return

    # 1. Chargement des données
    df = pd.read_csv(chemin_csv)
    
    # Nettoyage minimal des lignes où la variable cible (vitesse) est manquante
    df = df.dropna(subset=["vitesse_mm_s"])

    if len(df) < 5:
        print("Attention : Pas assez de données pour entraîner un modèle solide. Ajoutez plus de PDF !")
        return

    # 2. Définition des caractéristiques (Features) et de la cible (Target)
    # On choisit ce qui influence la combustion : le matériau, l'oxygène, la ventilation, la pression, etc.
    features = ["materiau", "oxygene_pct", "ventilation_cms", "pression_kpa", "flux_thermique_kwm2"]
    target = "vitesse_mm_s"

    X = df[features].fillna(0) # Remplacement simple des valeurs manquantes pour le hackathon
    y = df[target]

    # 3. Gestion des variables textuelles (ex: "PMMA", "Cotton") via un Encoder
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["materiau"])
        ],
        remainder="passthrough" # Laisse passer les colonnes numériques inchangées
    )

    # 4. Construction du Pipeline (Préprocesseur + Modèle de Régression)
    model = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("regressor", RandomForestRegressor(n_estimators=100, random_state=42))
    ])

    # 5. Séparation train/test et entraînement
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model.fit(X_train, y_train)

    # 6. Sauvegarde du modèle pour l'interface web
    os.makedirs("modele_sauvegarde", exist_ok=True)
    joblib.dump(model, "modele_sauvegarde/simulateur_combustion.pkl")
    print("Modèle prédictif entraîné et sauvegardé avec succès dans 'modele_sauvegarde/' !")

if __name__ == "__main__":
    entrainer_modele()