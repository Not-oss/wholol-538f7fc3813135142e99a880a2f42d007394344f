#!/bin/bash

# Activer l'environnement virtuel
source venv/bin/activate

# Vérifier si les répertoires nécessaires existent
mkdir -p instance
mkdir -p temp_data
mkdir -p static/uploads

# Lancer l'application
echo "Démarrage de l'application TikTok Game..."
python3 app.py 