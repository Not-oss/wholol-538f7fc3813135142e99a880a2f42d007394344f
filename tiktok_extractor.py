import os
import io
import time
import json
import base64
import logging
import re
import requests
import random
import platform
from urllib.request import urlretrieve
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, Browser
from PIL import Image
from pyzbar.pyzbar import decode

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

class TikTokExtractor:
    """Extrait des données TikTok via QR code"""
    
    # Liste des clés API disponibles
    API_KEYS = [
        "b5c754ea0bmsha84b1030d2afe01p1b6735jsn40e9e7b67475",  # Clé principale
        "694e7658bamsh43695bc5f6f53f8p1d29c6jsn5365263eaadb",  # Clé de réserve 1
        "df5bd4c068msh7bd2a74b1ef8b60p1f5604jsn56efa16f7b80"   # Clé de réserve 2
    ]
    
    # Variable de classe pour stocker la dernière clé API fonctionnelle
    LAST_WORKING_KEY = None
    
    def __init__(self, output_dir="output", rapid_api_key=None):
        """Initialisation"""
        self.output_dir = output_dir
        self.page = None
        self.browser = None
        self.playwright = None
        self.user_data = {}
        
        # Utiliser la clé API fournie, ou la dernière clé fonctionnelle, ou la première de la liste
        if rapid_api_key:
            self.rapid_api_key = rapid_api_key
            self.current_api_key_index = self.API_KEYS.index(rapid_api_key) if rapid_api_key in self.API_KEYS else 0
        elif TikTokExtractor.LAST_WORKING_KEY:
            self.rapid_api_key = TikTokExtractor.LAST_WORKING_KEY
            self.current_api_key_index = self.API_KEYS.index(TikTokExtractor.LAST_WORKING_KEY)
            logger.info(f"Utilisation de la dernière clé API fonctionnelle: ...{self.rapid_api_key[-8:]}")
        else:
            self.current_api_key_index = 0
            self.rapid_api_key = self.API_KEYS[self.current_api_key_index]
        
        os.makedirs(output_dir, exist_ok=True)
    
    def rotate_api_key(self):
        """Passe à la clé API suivante dans la liste"""
        self.current_api_key_index = (self.current_api_key_index + 1) % len(self.API_KEYS)
        self.rapid_api_key = self.API_KEYS[self.current_api_key_index]
        logger.info(f"Rotation de clé API -> nouvelle clé: ...{self.rapid_api_key[-8:]}")
        return self.rapid_api_key
    
    def set_last_working_key(self):
        """Mémorise la clé API actuelle comme fonctionnelle"""
        TikTokExtractor.LAST_WORKING_KEY = self.rapid_api_key
        logger.info(f"Mémorisation de la clé API fonctionnelle: ...{self.rapid_api_key[-8:]}")
    
    def setup_driver(self):
        """Configure le navigateur Playwright"""
        try:
            self.playwright = sync_playwright().start()
            
            # Configuration du navigateur
            browser_args = [
                '--no-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--window-size=1920,1080',
                '--disable-notifications',
                '--display=:99'
            ]
            
            # Lancer le navigateur en mode non-headless
            self.browser = self.playwright.chromium.launch(
                headless=False,
                args=browser_args
            )
            
            # Créer un nouveau contexte avec des paramètres personnalisés
            context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
            )
            
            # Activer la capture des requêtes réseau
            context.route("**/*", lambda route: route.continue_())
            
            # Créer une nouvelle page
            self.page = context.new_page()
            
            logger.info("Navigateur Playwright initialisé avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du navigateur: {str(e)}")
            raise
    
    def extract_user_info(self):
        """Récupère les informations utilisateur via l'API ou la page"""
        try:
            # Méthode 1: Utiliser l'API d'infos du compte
            self.page.goto("https://www.tiktok.com/passport/web/account/info/")
            self.page.wait_for_timeout(2000)
            
            # Capturer la réponse de l'API
            response = self.page.wait_for_response("**/passport/web/account/info")
            if response:
                data = response.json()
                if 'data' in data:
                    user_data = data['data']
                    self.user_data = {
                        'user_id': user_data.get('user_id_str', ''),
                        'username': user_data.get('username', ''),
                        'screen_name': user_data.get('screen_name', ''),
                        'avatar_url': user_data.get('avatar_url', ''),
                        'email': user_data.get('email', '')
                    }
                    logger.info(f"Infos utilisateur extraites: @{self.user_data['username']}")
                    return True
            
            # Méthode 2: Extraire depuis la page de profil
            self.page.goto("https://www.tiktok.com/setting")
            self.page.wait_for_timeout(2000)
            
            current_url = self.page.url
            if '@' in current_url:
                username = current_url.split('@')[-1].split('?')[0]
                self.user_data['username'] = username
                
                try:
                    name_element = self.page.query_selector('h1.tiktok-qpyus6-H1ShareTitle')
                    if name_element:
                        self.user_data['screen_name'] = name_element.text_content()
                except:
                    pass
            
            return bool(self.user_data)
            
        except Exception as e:
            logger.error(f"Erreur extraction infos utilisateur: {e}")
            return False
    
    def capture_qr_code(self):
        """Capture et sauvegarde le QR code"""
        try:
            logger.info("Recherche du QR code...")
            canvas = self.page.wait_for_selector('canvas', timeout=20000)
            
            if canvas:
                # Capturer le canvas en base64
                canvas_base64 = self.page.evaluate("""
                    () => {
                        const canvas = document.querySelector('canvas');
                        return canvas.toDataURL('image/png').split(',')[1];
                    }
                """)
                
                image_data = base64.b64decode(canvas_base64)
                image = Image.open(io.BytesIO(image_data))
                
                qr_path = os.path.join(self.output_dir, "tiktok_qr.png")
                image.save(qr_path)
                logger.info(f"QR code sauvegardé: {qr_path}")
                
                # Décodage du QR code
                decoded = decode(image)
                return decoded[0].data.decode('utf-8') if decoded else None
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors de la capture du QR code: {e}")
            return None
    
    def wait_for_login(self, timeout=120):
        """Attend la connexion via QR code"""
        logger.info(f"En attente de connexion... Scannez le QR code avec l'application TikTok (timeout: {timeout}s)")
        try:
            # Attendre soit l'URL du profil, soit l'icône de profil
            self.page.wait_for_function("""
                () => {
                    return window.location.href.includes('tiktok.com/@') || 
                           document.querySelector('[data-e2e="profile-icon"]') !== null;
                }
            """, timeout=timeout * 1000)
            
            logger.info("Connexion réussie!")
            return True
        except Exception:
            logger.error(f"Timeout: l'utilisateur ne s'est pas connecté dans les {timeout} secondes")
            return False
    
    def solve_captcha(self):
        """Résout le captcha TikTok s'il est présent"""
        try:
            logger.info("Vérification de la présence d'un captcha...")
            
            # Attendre que la page soit bien chargée
            self.page.wait_for_timeout(3000)
            
            # Vérifier si la page a bien chargé
            if "tiktok.com" not in self.page.url:
                logger.warning("La page TikTok n'est pas correctement chargée")
                self.page.reload()
                self.page.wait_for_timeout(3000)
                logger.info(f"Page rechargée: {self.page.url}")
            
            # Vérifier différents types de captcha
            captcha_selectors = [
                "img#captcha-verify-image",
                "img[alt*='captcha_whirl_title']",
                "div.cap-flex img.cap-h-[170px]",
                "div.captcha_verify_container, div.verify-container",
                "iframe[src*='captcha']"
            ]
            
            for selector in captcha_selectors:
                captcha_element = self.page.query_selector(selector)
                if captcha_element:
                    logger.info("Captcha détecté, tentative de résolution avec l'API...")
                    return self._solve_whirl_captcha()
            
            # Vérifier si la page a un contenu typique de TikTok
            profile_elements = self.page.query_selector("h1[class*='title'], h1[class*='nickname']")
            if not profile_elements:
                logger.warning("La page du profil ne semble pas être correctement chargée")
                refresh_button = self.page.query_selector("#captcha_refresh_button")
                if refresh_button:
                    refresh_button.click()
                    logger.info("Captcha rafraîchi")
                    # Prendre une capture d'écran pour diagnostic
                    screenshot_path = os.path.join(self.output_dir, f"captcha_check_{int(time.time())}.png")
                    self.page.screenshot(path=screenshot_path)
                    logger.info(f"Capture d'écran sauvegardée: {screenshot_path}")
                    
                    # Recharger la page comme solution de dernier recours
                    refresh_button.click()
                    self.page.wait_for_timeout(3000)
                    return False
            
            logger.info("Aucun captcha détecté, page profil correctement chargée")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la détection du captcha: {e}")
            return False
    
    def _solve_whirl_captcha(self):
        """Résout le captcha whirl (rotation)"""
        logger.info("Tentative de résolution du captcha whirl avec l'API...")
        
        max_attempts = 15
        tried_keys = set()
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Tentative {attempt}/{max_attempts} de résolution du captcha")
                
                # 1. Récupérer les URLs des images
                logger.info("Analyse des requêtes réseau pour le captcha...")
                
                # Attendre les requêtes d'images captcha
                captcha_urls = []
                start_time = time.time()
                
                while time.time() - start_time < 10:
                    response = self.page.wait_for_response(
                        lambda response: 'rc-captcha' in response.url and 
                        any(response.url.endswith(ext) for ext in ['.webp', '.png', '.jpg']),
                        timeout=1000
                    )
                    
                    if response and response.url not in captcha_urls:
                        captcha_urls.append(response.url)
                        if len(captcha_urls) >= 2:
                            break
                
                if len(captcha_urls) < 2:
                    logger.warning(f"Images captcha insuffisantes (trouvées: {len(captcha_urls)})")
                    continue
                
                # 2. Trier les URLs et faire appel à l'API
                captcha_urls = sorted(captcha_urls)[:2]
                url1, url2 = captcha_urls
                
                logger.info(f"URLs captcha identifiées:\nImage 1: {url1}\nImage 2: {url2}")
                
                # Essayer d'obtenir une solution avec la clé API actuelle
                solution = self._call_captcha_api(url1, url2)
                tried_keys.add(self.rapid_api_key)
                
                # Si pas de solution, essayer l'ordre inverse
                if not solution:
                    logger.info("Tentative avec l'ordre inversé des URLs")
                    solution = self._call_captcha_api(url2, url1)
                
                # Si toujours pas de solution et qu'il y a des clés non essayées, essayer avec d'autres clés
                if not solution:
                    for _ in range(len(self.API_KEYS) - 1):
                        if len(tried_keys) >= len(self.API_KEYS):
                            break
                        
                        self.rotate_api_key()
                        
                        if self.rapid_api_key in tried_keys:
                            continue
                        
                        tried_keys.add(self.rapid_api_key)
                        logger.info(f"Essai avec une autre clé API: ...{self.rapid_api_key[-8:]}")
                        
                        solution = self._call_captcha_api(url1, url2)
                        if not solution:
                            solution = self._call_captcha_api(url2, url1)
                        
                        if solution:
                            break
                
                if not solution:
                    logger.warning(f"Aucune solution trouvée avec {len(tried_keys)} clés API différentes")
                    continue
                
                # 3. Appliquer la solution
                success = self._apply_captcha_solution(solution)
                
                # 4. Vérifier si le captcha a disparu
                captcha_elements = self.page.query_selector_all(
                    "img#captcha-verify-image, img[alt*='captcha_whirl_title'], div.cap-flex img.cap-h-[170px]"
                )
                
                if not captcha_elements or success:
                    logger.info(f"Captcha résolu avec succès à la tentative {attempt}")
                    self.set_last_working_key()
                    return True
                
                logger.warning(f"Échec de la tentative {attempt}")
                self.page.wait_for_timeout(1000)
                    
            except Exception as e:
                logger.error(f"Erreur à la tentative {attempt}: {e}")
                if attempt < max_attempts:
                    logger.info("Tentative suivante...")
                    self.page.wait_for_timeout(2000)
        
        logger.error(f"Échec après {max_attempts} tentatives de résolution")
        return False
    
    def _call_captcha_api(self, url1, url2):
        """Appelle la nouvelle API de résolution de captcha"""
        try:
            url = "https://tiktok-captcha-solver2.p.rapidapi.com/tiktok/captcha"
            payload = {
                "cap_type": "whirl",
                "url1": url1,
                "url2": url2
            }
            headers = {
                "x-rapidapi-key": self.rapid_api_key,
                "x-rapidapi-host": "tiktok-captcha-solver2.p.rapidapi.com",
                "Content-Type": "application/json"
            }
            
            logger.info("Envoi à l'API de résolution de captcha...")
            response = requests.post(url, json=payload, headers=headers)
            result = response.json()
            logger.info(f"Réponse API: {result}")
            
            # Vérifier si l'erreur est due à un dépassement de la limite mensuelle
            if 'message' in result and ('monthly' in result['message'].lower() or 'limit' in result['message'].lower()):
                logger.warning(f"Limite mensuelle atteinte pour la clé API: {result['message']}")
                
                # Essayer avec une clé de rechange
                old_key = self.rapid_api_key
                self.rotate_api_key()
                
                # Vérifier si nous avons une nouvelle clé différente
                if old_key != self.rapid_api_key:
                    logger.info(f"Nouvel essai avec une autre clé API...")
                    
                    # Mettre à jour les en-têtes avec la nouvelle clé
                    headers["x-rapidapi-key"] = self.rapid_api_key
                    
                    # Réessayer la requête
                    response = requests.post(url, json=payload, headers=headers)
                    result = response.json()
                    logger.info(f"Réponse API (nouvelle clé): {result}")
            
            # Vérifier si la solution est disponible
            if "success" in result and result["success"] and "captcha_solution" in result:
                # Mémoriser cette clé API comme fonctionnelle
                self.set_last_working_key()
                return result
            else:
                logger.error("Solution non trouvée dans la réponse")
                return None
            
        except Exception as e:
            logger.error(f"Échec API: {e}")
            return None
    
    def _apply_captcha_solution(self, solution):
        """Applique la solution du captcha whirl"""
        try:
            # Extraire les coordonnées
            if "captcha_solution" in solution and "x1" in solution["captcha_solution"]:
                x = int(solution["captcha_solution"]["x1"])
                x += 8  # Compensation de l'erreur systématique
            else:
                logger.error("Format de solution non reconnu")
                return False
            
            logger.info(f"Solution obtenue: x={x} (valeur API + 8)")
            
            # Trouver le slider
            slider = self.page.query_selector(
                'div.cap-flex div[draggable="true"], #captcha_slide_button, div.secsdk-captcha-drag-icon svg'
            )
            
            if not slider:
                logger.error("Slider non trouvé")
                return False
            
            # Mouvement humain amélioré
            # 1. Attendre un petit moment
            self.page.wait_for_timeout(random.randint(300, 700))
            
            # 2. Cliquer et maintenir
            slider.hover()
            self.page.mouse.down()
            self.page.wait_for_timeout(random.randint(100, 300))
            
            # 3. Déplacement progressif
            total_move = x
            steps = min(15, max(8, int(total_move / 15)))
            
            for i in range(steps):
                progress = i / (steps - 1)
                easing = 1 / (1 + 2.7**(-10 * (progress - 0.5)))
                current_position = easing * total_move
                
                if i == 0:
                    distance = current_position
                else:
                    prev_position = (1 / (1 + 2.7**(-10 * ((i-1) / (steps - 1) - 0.5)))) * total_move
                    distance = current_position - prev_position
                
                # Ajouter un peu d'aléatoire
                jitter_x = random.uniform(-1, 1) if i > 0 and i < steps - 1 else 0
                jitter_y = random.uniform(-1, 1) if i > 0 and i < steps - 1 else 0
                
                self.page.mouse.move(distance + jitter_x, jitter_y)
                
                # Pause variable
                pause_time = random.uniform(50, 150)
                if i < 2 or i > steps - 3:
                    pause_time *= 1.5
                self.page.wait_for_timeout(pause_time)
            
            # 4. Ajustement final
            overshoot = random.uniform(-3, 3)
            if abs(overshoot) > 1:
                self.page.mouse.move(overshoot, 0)
                self.page.wait_for_timeout(random.randint(100, 200))
                self.page.mouse.move(-overshoot, 0)
                self.page.wait_for_timeout(random.randint(50, 100))
            
            # 5. Relâcher
            self.page.mouse.up()
            self.page.wait_for_timeout(random.randint(1000, 2000))
            
            # Vérifier bouton confirmer
            try:
                confirm_button = self.page.wait_for_selector("div:text('Confirm')", timeout=5000)
                if confirm_button:
                    self.page.wait_for_timeout(random.randint(500, 1000))
                    confirm_button.click()
                    self.page.wait_for_timeout(random.randint(1000, 2000))
            except:
                logger.info("Pas de bouton de confirmation trouvé")
            
            # Vérification finale
            captcha_elements = self.page.query_selector_all(
                "img#captcha-verify-image, img[alt*='captcha_whirl_title'], div.cap-flex img.cap-h-[170px]"
            )
            
            if not captcha_elements:
                logger.info("Captcha résolu avec succès")
                return True
            
            logger.warning("Le captcha pourrait ne pas être résolu")
            return False
            
        except Exception as e:
            logger.error(f"Échec application solution: {e}")
            return False
    
    def extract_liked_videos(self):
        """Extrait les URLs des vidéos likées"""
        logger.info("Extraction des vidéos likées...")
        
        liked_videos = []
        
        try:
            # Vérifier si les vidéos sont privées
            private_text = self.page.query_selector(
                "div:text('This user has set liked videos to private'), " +
                "div:text('utilisateur a mis les vidéos'), " +
                "div:text('private')"
            )
            
            if private_text:
                logger.warning("Les vidéos likées sont configurées comme privées")
                return liked_videos
            
            # Attendre le chargement initial
            self.page.wait_for_timeout(1000)
            
            # Rechercher les vidéos
            video_selectors = [
                "div.tiktok-x6y88p-DivItemContainerV2 a[href*='/video/']",
                "div[data-e2e='user-liked-item'] a[href*='/video/']",
                "div.video-feed a[href*='/video/']",
                "a[href*='/video/']"
            ]
            
            # Extraire les vidéos initiales
            for selector in video_selectors:
                video_elements = self.page.query_selector_all(selector)
                
                if video_elements:
                    logger.info(f"Vidéos trouvées avec le sélecteur: {selector}")
                    for element in video_elements:
                        try:
                            video_url = element.get_attribute('href')
                            if video_url and '/video/' in video_url and video_url not in liked_videos:
                                liked_videos.append(video_url)
                        except:
                            continue
                    
                    if liked_videos:
                        break
            
            # Faire défiler pour plus de vidéos
            max_scroll_attempts = 30
            scroll_attempt = 0
            last_height = 0
            
            while len(liked_videos) < 100 and scroll_attempt < max_scroll_attempts:
                # Défiler
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self.page.wait_for_timeout(1500)
                
                # Vérifier la hauteur
                new_height = self.page.evaluate("document.body.scrollHeight")
                
                if new_height == last_height:
                    if scroll_attempt == max_scroll_attempts - 1:
                        self.page.wait_for_timeout(2000)
                        
                        # Dernière tentative
                        for selector in video_selectors:
                            elements = self.page.query_selector_all(selector)
                            for element in elements:
                                video_url = element.get_attribute('href')
                                if video_url and '/video/' in video_url and video_url not in liked_videos:
                                    liked_videos.append(video_url)
                    scroll_attempt += 1
                else:
                    last_height = new_height
                    scroll_attempt = 0
                    
                    # Rechercher les nouvelles vidéos
                    for selector in video_selectors:
                        elements = self.page.query_selector_all(selector)
                        for element in elements:
                            video_url = element.get_attribute('href')
                            if video_url and '/video/' in video_url and video_url not in liked_videos:
                                liked_videos.append(video_url)
                                if len(liked_videos) % 10 == 0:
                                    logger.info(f"Nombre de vidéos trouvées: {len(liked_videos)}")
                    
                    if len(liked_videos) >= 100:
                        break
            
            # Si toujours aucune vidéo, essayer JavaScript
            if not liked_videos:
                logger.warning("Aucune vidéo trouvée avec les sélecteurs, tentative avec JavaScript...")
                try:
                    video_links = self.page.evaluate("""
                        () => {
                            const links = document.getElementsByTagName('a');
                            const videoLinks = [];
                            for (const link of links) {
                                const href = link.getAttribute('href');
                                if (href && href.includes('/video/')) {
                                    videoLinks.push(href);
                                }
                            }
                            return videoLinks;
                        }
                    """)
                    
                    for link in video_links:
                        if '/video/' in link and link not in liked_videos:
                            if not link.startswith('http'):
                                link = 'https://www.tiktok.com' + link
                            liked_videos.append(link)
                except Exception as e:
                    logger.error(f"Échec de l'extraction JavaScript: {str(e)}")
            
            # Limiter à 100 vidéos
            liked_videos = liked_videos[:100]
            logger.info(f"Extraction terminée: {len(liked_videos)} vidéos trouvées")
            
            return liked_videos
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des vidéos likées: {str(e)}")
            return []
    
    def save_data(self, liked_videos=None):
        """Sauvegarde les données extraites en JSON"""
        if not self.user_data:
            logger.warning("Aucune donnée utilisateur à sauvegarder")
            return False
        
        output_data = {
            "user_info": self.user_data,
            "liked_videos": liked_videos or [],
            "extraction_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        username = self.user_data.get('username', 'unknown')
        filename = os.path.join(self.output_dir, f"tiktok_{username}_{int(time.time())}.json")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Données sauvegardées dans {filename}")
            return filename
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            return False
    
    def run(self):
        """Exécute le processus complet"""
        try:
            # Setup et accès à la page de login
            self.setup_driver()
            self.page.goto("https://www.tiktok.com/login/qrcode?redirect_url=https://www.tiktok.com/")
            self.page.wait_for_timeout(2000)
            
            # Capture du QR code
            qr_content = self.capture_qr_code()
            if not qr_content:
                logger.error("Échec capture QR code")
                return False
            
            # Attente de la connexion
            if not self.wait_for_login():
                return False
            
            # Extraction des données utilisateur
            if not self.extract_user_info():
                logger.warning("Extraction des informations utilisateur limitée")
            
            # Extraction des vidéos likées
            liked_videos = self.extract_liked_videos()
            
            # Sauvegarde des données
            output_file = self.save_data(liked_videos)
            
            # Résumé
            if self.user_data:
                logger.info("\n===== RÉSUMÉ =====")
                logger.info(f"Utilisateur: @{self.user_data.get('username', 'inconnu')}")
                logger.info(f"Vidéos likées: {len(liked_videos)}")
                logger.info(f"Fichier: {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur: {e}")
            return False
        
        finally:
            # Nettoyage
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop() 