import os
import panda as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib


def entrainer_modele():
    chemin_csv = "data/processed"
    if not os.path.exists(chemin_csv):
        print(f"Erreur : Le fichier {chemin_csv} est introuvable. Lancez d'abord votre extracteur PDF.")
        return

    
    df = pd.read_csv(chemin_csv)
    
    
    df = df.dropna(subset=["vitesse_mm_s"])

    if len(df) < 5: #Une recommendation en ligne et de l'IA, je sais vraiment pas si c'est nécessaire à ajouter...
        print("Attention : Pas assez de données pour entraîner un modèle solide. Ajoutez plus de PDF.")
        return

    
    features = ["materiau", "oxygene_pct", "ventilation_cms", "pression_kpa", "flux_thermique_kwm2"]
    target = "vitesse_mm_s"

    X = df[features].fillna(0) # Remplacement simple des valeurs manquantes pour le hackathon
    y = df[target]

    
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["materiau"])
        ],
        remainder="passthrough" 
    )

   
    model = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("regressor", RandomForestRegressor(n_estimators=100, random_state=42))
    ])

    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model.fit(X_train, y_train)

   
    os.makedirs("modele_sauvegarde", exist_ok=True)
    joblib.dump(model, "modele_sauvegarde/simulateur_combustion.pkl")
    print("Modèle prédictif entraîné et sauvegardé avec succès dans 'modele_sauvegarde/' !")

if __name__ == "__main__":
    entrainer_modele()