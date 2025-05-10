#!/bin/bash

# Script de configuration pour Ubuntu
echo "Configuration de l'environnement pour l'application TikTok Game"

# Mise à jour des paquets
echo "Mise à jour des paquets..."
sudo apt update -y

# Installation des dépendances système
echo "Installation des dépendances système..."
sudo apt install -y python3 python3-pip python3-venv libzbar0 libgl1-mesa-glx

# Installation de Chrome
echo "Installation de Google Chrome..."
if ! command -v google-chrome &> /dev/null; then
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt install -y ./google-chrome-stable_current_amd64.deb
    rm google-chrome-stable_current_amd64.deb
else
    echo "Google Chrome est déjà installé."
fi

# Création d'un environnement virtuel
echo "Création d'un environnement virtuel..."
python3 -m venv venv
source venv/bin/activate

# Installation des dépendances Python
echo "Installation des dépendances Python..."
pip install -r requirements.txt

# Création du répertoire pour ChromeDriver
echo "Création du répertoire pour ChromeDriver..."
mkdir -p ~/.local/share/undetected_chromedriver/

# Vérification des permissions
echo "Configuration des permissions..."
chmod -R 755 instance/
chmod -R 755 temp_data/
chmod -R 755 static/

echo "Configuration terminée! Vous pouvez maintenant exécuter l'application avec:"
echo "source venv/bin/activate && python3 app.py" 