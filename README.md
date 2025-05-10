# Qui a Liké ? - Le jeu social TikTok

"Qui a Liké ?" est un jeu social basé sur TikTok où les joueurs doivent deviner qui a liké une vidéo TikTok parmi les participants d'une partie. C'est un jeu à jouer entre amis.

## Fonctionnement du jeu

1. Les utilisateurs se connectent à l'application via un QR code TikTok
2. Un joueur crée une partie et génère un code d'invitation
3. Les autres joueurs rejoignent la partie avec ce code (minimum 3 joueurs requis, maximum 10)
4. L'application sélectionne une vidéo likée par l'un des participants
5. Les autres joueurs doivent deviner quel participant a liké cette vidéo
6. Des points sont attribués pour chaque bonne réponse
7. Le jeu se déroule en 5 tours (configurable)
8. À la fin des tours, le joueur avec le score le plus élevé gagne

## Éléments techniques clés

- Application web Flask
- Base de données SQLAlchemy
- Système d'authentification avec Flask-Login
- Téléchargement de vidéos TikTok via une API personnalisée
- Interface utilisateur moderne avec Tailwind CSS et DaisyUI
- Système de joker: si c'est votre vidéo, vous pouvez utiliser un joker pour éviter d'être deviné
- Système de génération de codes de partie uniques
- Statistiques de fin de partie

## Système de QR Code pour se connecter

Le jeu implémente un système d'authentification innovant utilisant des QR codes :
1. L'utilisateur accède à la page de connexion
2. L'application génère un QR code unique temporaire
3. L'utilisateur scanne ce QR code avec son téléphone
4. Le scan ouvre TikTok et authentifie l'utilisateur via un cookie de session
5. L'application récupère les données du profil TikTok et les vidéos likées
6. L'utilisateur est automatiquement connecté à l'application web

Ce système permet d'éviter de stocker les identifiants TikTok et d'accéder facilement aux vidéos likées par l'utilisateur, en utilisant un navigateur automatisé (undetected_chromedriver) qui simule l'authentification TikTok et extrait les cookies de session nécessaires.

## Installation

### Prérequis

- Python 3.8+
- Chrome ou Chromium
- Pip

### Installation des dépendances

```bash
pip install -r requirements.txt
```

### Configuration

Créez un fichier `.env` à la racine du projet avec les variables suivantes :

```
SECRET_KEY=votre_clef_secrete
RAPIDAPI_KEY=votre_clef_api_rapidapi
```

### Installation sur Ubuntu

Pour installer et configurer l'application sur Ubuntu, suivez ces étapes:

1. Clonez le dépôt:
```bash
git clone <url_du_repo>
cd <nom_du_repo>
```

2. Exécutez le script de configuration:
```bash
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

3. Lancez l'application:
```bash
chmod +x run.sh
./run.sh
```

L'application sera disponible à l'adresse http://localhost:5000

### Installation sur Windows

```bash
pip install -r requirements.txt
python app.py
```

L'application sera disponible à l'adresse http://localhost:5000

## Structure du projet

- `app.py` : Point d'entrée de l'application Flask
- `models.py` : Modèles de données SQLAlchemy
- `config.py` : Configuration de l'application
- `tiktok_extractor.py` : Système d'extraction des données TikTok
- `ttdownloader.py` : Module de téléchargement des vidéos TikTok
- `utils.py` : Utilitaires divers
- `templates/` : Templates HTML
- `static/` : Fichiers statiques (CSS, JS, images)
- `temp_data/` : Dossier temporaire pour les QR codes et données extraites

## Captures d'écran

*À venir*

## Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.

## Avertissement

Ce projet n'est pas affilié à TikTok. Il utilise l'API publique de TikTok et des techniques de web scraping pour accéder aux données publiques. Utilisez-le de manière responsable et conformément aux conditions d'utilisation de TikTok. 