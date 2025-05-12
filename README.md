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

Ce système permet d'éviter de stocker les identifiants TikTok et d'accéder facilement aux vidéos likées par l'utilisateur, en utilisant un navigateur automatisé (Selenium WebDriver) qui simule l'authentification TikTok et extrait les cookies de session nécessaires.

### Modes de connexion

L'application propose deux modes de connexion via QR code :

- **Mode visible** : Le navigateur Chrome s'ouvre et est visible pendant le processus d'authentification. Ce mode est plus stable mais nécessite plus de ressources.
- **Mode invisible (headless)** : Le navigateur fonctionne en arrière-plan sans interface graphique. Ce mode est plus léger mais peut être moins stable sur certains systèmes.

Choisissez le mode qui convient le mieux à votre environnement et à vos ressources système.

## Installation

### Prérequis

- Python 3.8+
- Chrome ou Chromium
- ChromeDriver (compatible avec votre version de Chrome)
- Pip

### Installation des dépendances

```