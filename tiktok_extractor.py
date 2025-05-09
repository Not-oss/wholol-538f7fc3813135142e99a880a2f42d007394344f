import os
import io
import time
import json
import base64
import logging
import re
import requests
import random
import cv2
from urllib.request import urlretrieve
from datetime import datetime
from selenium.webdriver.common.action_chains import ActionChains

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
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
    
    def __init__(self, headless=True, output_dir="output", rapid_api_key=None):
        """Initialisation"""
        self.headless = headless
        self.output_dir = output_dir
        self.driver = None
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
        """Configure le driver Chrome"""
        options = uc.ChromeOptions()
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        # Forcer l'affichage du navigateur (ne pas utiliser headless)
        options.headless = False
        
        # Ajouter le mode incognito
        options.add_argument('--incognito')
        
        # Configuration standard
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-notifications')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36')
        
        logger.info("Initialisation du navigateur Chrome en mode incognito...")
        
        # Utiliser directement le chemin Ubuntu sans détection d'OS
        driver_path = "/home/ubuntu/.local/share/undetected_chromedriver/undetected_adem"
        logger.info(f"Utilisation du chemin chromedriver: {driver_path}")
        self.driver = uc.Chrome(options=options, driver_executable_path=driver_path, port=7777)
        
        self.driver.maximize_window()
    
    def extract_user_info(self):
        """Récupère les informations utilisateur via l'API ou la page"""
        try:
            # Méthode 1: Utiliser l'API d'infos du compte
            self.driver.get("https://www.tiktok.com/passport/web/account/info/")
            time.sleep(2)
            
            # Capturer la réponse de l'API
            logs = self.driver.get_log('performance')
            for entry in logs:
                try:
                    log = json.loads(entry['message'])['message']
                    if ('Network.responseReceived' in log['method'] and 
                        'response' in log['params'] and 
                        'url' in log['params']['response'] and 
                        'passport/web/account/info' in log['params']['response']['url']):
                        
                        request_id = log['params']['requestId']
                        response = self.driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                        if 'body' in response:
                            data = json.loads(response['body'])
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
                except Exception:
                    pass
            
            # Méthode 2: Extraire depuis la page de profil
            self.driver.get("https://www.tiktok.com/setting")
            time.sleep(2)
            
            current_url = self.driver.current_url
            if '@' in current_url:
                username = current_url.split('@')[-1].split('?')[0]
                self.user_data['username'] = username
                
                try:
                    name_element = self.driver.find_element(By.CSS_SELECTOR, 'h1.tiktok-qpyus6-H1ShareTitle')
                    self.user_data['screen_name'] = name_element.text
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
            canvas = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'canvas'))
            )
            
            canvas_base64 = self.driver.execute_script(
                "return document.querySelector('canvas').toDataURL('image/png').split(',')[1];"
            )
            
            image_data = base64.b64decode(canvas_base64)
            image = Image.open(io.BytesIO(image_data))
            
            qr_path = os.path.join(self.output_dir, "tiktok_qr.png")
            image.save(qr_path)
            logger.info(f"QR code sauvegardé: {qr_path}")
            
            # Décodage du QR code
            decoded = decode(image)
            return decoded[0].data.decode('utf-8') if decoded else None
            
        except Exception as e:
            logger.error(f"Erreur lors de la capture du QR code: {e}")
            return None
    
    def wait_for_login(self, timeout=120):
        """Attend la connexion via QR code"""
        logger.info(f"En attente de connexion... Scannez le QR code avec l'application TikTok (timeout: {timeout}s)")
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: "tiktok.com/@" in d.current_url or 
                         EC.presence_of_element_located((By.CSS_SELECTOR, '[data-e2e="profile-icon"]'))(d)
            )
            logger.info("Connexion réussie!")
            return True
        except TimeoutException:
            logger.error(f"Timeout: l'utilisateur ne s'est pas connecté dans les {timeout} secondes")
            return False
    
    def solve_captcha(self):
        """Résout le captcha TikTok s'il est présent"""
        try:
            logger.info("Vérification de la présence d'un captcha...")
            
            # Attendre que la page soit bien chargée
            time.sleep(3)
            
            # Vérifier si la page a bien chargé
            if "tiktok.com" not in self.driver.current_url:
                logger.warning("La page TikTok n'est pas correctement chargée")
                # Forcer le rechargement de la page
                current_url = self.driver.current_url
                self.driver.refresh()
                time.sleep(3)
                logger.info(f"Page rechargée: {current_url}")
            
            # Vérifier différents types de captcha
            
            # Type 1: Captcha whirl standard
            captcha_img1 = self.driver.find_elements(By.XPATH, "//img[@id='captcha-verify-image']")
            
            # Type 2: Captcha whirl/puzzle avec différentes classes
            captcha_img2 = self.driver.find_elements(By.XPATH, "//img[contains(@alt, 'captcha_whirl_title')]")
            
            # Type 3: Nouveau format de captcha puzzle (mais toujours whirl)
            captcha_img3 = self.driver.find_elements(By.XPATH, 
                "//div[contains(@class,'cap-flex')]/img[contains(@class,'cap-h-[170px]')]")
                
            # Type 4: Divers conteneurs de captcha
            captcha_containers = self.driver.find_elements(By.XPATH, 
                "//div[contains(@class, 'captcha_verify_container') or contains(@class, 'verify-container')]")
                
            # Type 5: Iframe captcha
            captcha_iframe = self.driver.find_elements(By.XPATH, "//iframe[contains(@src, 'captcha')]")
            
            if captcha_img1 or captcha_img2 or captcha_img3 or captcha_containers or captcha_iframe:
                logger.info("Captcha détecté, tentative de résolution avec l'API...")
                return self._solve_whirl_captcha()
            else:
                # Vérifier si la page a un contenu typique de TikTok
                profile_elements = self.driver.find_elements(By.XPATH, "//h1[contains(@class, 'title') or contains(@class, 'nickname')]")
                if not profile_elements:
                    logger.warning("La page du profil ne semble pas être correctement chargée, possibilité de captcha non détecté")
                    refresh_button = self.driver.find_element(By.ID, "captcha_refresh_button")
                    refresh_button.click()
                    logger.info("Captcha rafraîchi")
                    # Prendre une capture d'écran pour diagnostic
                    screenshot_path = os.path.join(self.output_dir, f"captcha_check_{int(time.time())}.png")
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"Capture d'écran sauvegardée: {screenshot_path}")
                    
                    # Recharger la page comme solution de dernier recours
                    refresh_button = self.driver.find_element(By.ID, "captcha_refresh_button")
                    refresh_button.click()
                    time.sleep(3)
                    return False
                
                logger.info("Aucun captcha détecté, page profil correctement chargée")
                return True
                
        except Exception as e:
            logger.error(f"Erreur lors de la détection du captcha: {e}")
            return False

    def _solve_whirl_captcha(self):
        """Résout le captcha whirl (rotation)"""
        logger.info("Tentative de résolution du captcha whirl avec l'API...")
        
        max_attempts = 15  # Nombre maximum de tentatives
        tried_keys = set()  # Pour suivre les clés API déjà essayées
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Tentative {attempt}/{max_attempts} de résolution du captcha")
                
                # 1. Récupérer les URLs des images à chaque tentative
                logger.info("Analyse des requêtes réseau pour le captcha...")
                
                # Vider le buffer des logs existants avant chaque tentative
                self.driver.get_log('performance')
                
                # Si ce n'est pas la première tentative, rafraîchir le captcha
                if attempt > 1:
                    try:
                        refresh_button = self.driver.find_element(By.ID, "captcha_refresh_button")
                        refresh_button.click()
                        logger.info("Captcha rafraîchi")
                        time.sleep(2)
                    except Exception as e:
                        logger.warning(f"Impossible de rafraîchir le captcha: {e}")
                
                # Récupérer les logs avec timeout
                start_time = time.time()
                captcha_urls = []
                
                while time.time() - start_time < 10:  # Timeout de 10s
                    logs = self.driver.get_log('performance')
                    
                    for entry in logs:
                        try:
                            log = json.loads(entry['message'])['message']
                            if (log.get('method') == 'Network.responseReceived' and
                                'response' in log.get('params', {}) and
                                'url' in log['params']['response']):
                                
                                url = log['params']['response']['url']
                                if ('rc-captcha' in url and 
                                    any(url.endswith(ext) for ext in ['.webp', '.png', '.jpg'])):
                                    
                                    if url not in captcha_urls:
                                        captcha_urls.append(url)
                                        
                                        if len(captcha_urls) >= 2:
                                            break
                        except Exception:
                            continue
                    
                    if len(captcha_urls) >= 2:
                        break
                        
                    time.sleep(0.5)
                
                if len(captcha_urls) < 2:
                    logger.warning(f"Images captcha insuffisantes (trouvées: {len(captcha_urls)})")
                    continue  # Passer à la tentative suivante
                
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
                    # Essayer avec toutes les clés API disponibles
                    for _ in range(len(self.API_KEYS) - 1):  # -1 car on a déjà essayé la clé actuelle
                        if len(tried_keys) >= len(self.API_KEYS):
                            break  # Toutes les clés ont été essayées
                        
                        # Passer à la clé suivante
                        self.rotate_api_key()
                        
                        # Vérifier si on n'a pas déjà essayé cette clé
                        if self.rapid_api_key in tried_keys:
                            continue
                        
                        tried_keys.add(self.rapid_api_key)
                        logger.info(f"Essai avec une autre clé API: ...{self.rapid_api_key[-8:]}")
                        
                        # Essayer avec les deux ordres d'URLs
                        solution = self._call_captcha_api(url1, url2)
                        if not solution:
                            solution = self._call_captcha_api(url2, url1)
                        
                        if solution:
                            break  # Solution trouvée avec cette clé
                
                if not solution:
                    logger.warning(f"Aucune solution trouvée avec {len(tried_keys)} clés API différentes, nouvel essai...")
                    continue  # Passer à la tentative suivante
                
                # 3. Appliquer la solution
                success = self._apply_captcha_solution(solution)
                
                # 4. Vérifier si le captcha a disparu
                captcha_elements = (
                    self.driver.find_elements(By.XPATH, "//img[@id='captcha-verify-image']") or
                    self.driver.find_elements(By.XPATH, "//img[contains(@alt, 'captcha_whirl_title')]") or
                    self.driver.find_elements(By.XPATH, "//div[contains(@class,'cap-flex')]/img[contains(@class,'cap-h-[170px]')]")
                )
                
                if not captcha_elements or success:
                    logger.info(f"Captcha résolu avec succès à la tentative {attempt} avec la clé ...{self.rapid_api_key[-8:]}")
                    # Enregistrer cette clé comme fonctionnelle
                    self.set_last_working_key()
                    return True
                
                logger.warning(f"Échec de la tentative {attempt}, nouvel essai...")
                time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Erreur à la tentative {attempt}: {e}")
                if attempt < max_attempts:
                    logger.info("Tentative suivante...")
                    time.sleep(2)  # Attendre avant la prochaine tentative
        
        logger.error(f"Échec après {max_attempts} tentatives de résolution avec toutes les clés API disponibles")
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
                # Ajout de 8 pixels à la solution pour compenser l'erreur systématique
                x += 8
            else:
                logger.error("Format de solution non reconnu")
                return False
            
            logger.info(f"Solution obtenue: x={x} (valeur API + 8)")

            # Trouver le slider - plusieurs possibilités
            try:
                # Option 1: Div draggable
                slider = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH,
                    '//div[contains(@class,"cap-flex")]/div[@draggable="true"]'))
                )
            except Exception:
                try:
                    # Option 2: Bouton du slider 
                    slider = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.ID, "captcha_slide_button"))
                    )
                except Exception:
                    # Option 3: Icône SVG du slider
                    slider = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH,
                        '//div[contains(@class,"secsdk-captcha-drag-icon")]//*[name()="svg"]'))
                    )

            # Mouvement humain amélioré
            actions = ActionChains(self.driver)
            
            # 1. Attendre un petit moment avant de commencer (comme un humain)
            time.sleep(random.uniform(0.3, 0.7))
            
            # 2. Cliquer et maintenir avec une légère pause
            actions.click_and_hold(slider)
            time.sleep(random.uniform(0.1, 0.3))
            
            # 3. Déplacement progressif avec courbe d'accélération et décélération
            total_move = x
            
            # Nombre d'étapes variable en fonction de la distance mais pas trop élevé
            steps = min(15, max(8, int(total_move / 15)))
            
            # Créer un mouvement avec accélération et décélération
            for i in range(steps):
                # Courbe en forme de S (accélération progressive puis décélération)
                # Au début, petit mouvement, puis plus rapide au milieu, puis ralentissement
                progress = i / (steps - 1)
                
                # Équation pour créer une courbe en S (sigmoïde)
                # Quand progress = 0 -> environ 0, quand progress = 0.5 -> environ 0.5, quand progress = 1 -> environ 1
                easing = 1 / (1 + 2.7**(-10 * (progress - 0.5)))
                
                # Position actuelle sur la trajectoire totale
                current_position = easing * total_move
                
                # Calculer le mouvement pour cette étape
                if i == 0:
                    distance = current_position
                else:
                    prev_position = (1 / (1 + 2.7**(-10 * ((i-1) / (steps - 1) - 0.5)))) * total_move
                    distance = current_position - prev_position
                
                # Ajouter un peu d'aléatoire au mouvement pour simuler une main qui tremble légèrement
                jitter_x = random.uniform(-1, 1) if i > 0 and i < steps - 1 else 0
                jitter_y = random.uniform(-1, 1) if i > 0 and i < steps - 1 else 0
                
                # Mouvement horizontal principal + léger mouvement vertical aléatoire
                actions.move_by_offset(distance + jitter_x, jitter_y)
                
                # Pause variable entre chaque mouvement (plus lent au début et à la fin)
                pause_time = random.uniform(0.05, 0.15)
                if i < 2 or i > steps - 3:
                    pause_time *= 1.5  # Plus lent au début et à la fin
                actions.pause(pause_time)
            
            # 4. Petit ajustement final (comme un humain qui ajuste sa position)
            overshoot = random.uniform(-3, 3)
            if abs(overshoot) > 1:
                actions.move_by_offset(overshoot, 0).pause(random.uniform(0.1, 0.2))
                actions.move_by_offset(-overshoot, 0).pause(random.uniform(0.05, 0.1))
            
            # 5. Relâcher et attendre
            actions.release().perform()
            time.sleep(random.uniform(1, 2))
            
            # Vérifier bouton confirmer
            try:
                confirm_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[text()='Confirm']"))
                )
                
                # Ajouter un délai avant de cliquer (comportement humain)
                time.sleep(random.uniform(0.5, 1))
                confirm_button.click()
                time.sleep(random.uniform(1, 2))
            except:
                logger.info("Pas de bouton de confirmation trouvé")
            
            # Vérification - vérifier la disparition du captcha
            captcha_elements = (
                self.driver.find_elements(By.XPATH, "//img[@id='captcha-verify-image']") or
                self.driver.find_elements(By.XPATH, "//img[contains(@alt, 'captcha_whirl_title')]") or
                self.driver.find_elements(By.XPATH, "//div[contains(@class,'cap-flex')]/img[contains(@class,'cap-h-[170px]')]")
            )
            
            if not captcha_elements:
                logger.info("Captcha résolu avec succès")
                return True
                
            logger.warning("Le captcha pourrait ne pas être résolu")
            return False
            
        except Exception as e:
            logger.error(f"Échec application solution: {e}")
            return False

    def prepare_captcha_capture(self):
        """Prépare la capture des requêtes réseau pour le captcha"""
        logger.info("Préparation de la capture réseau pour le captcha...")
        # Au lieu de naviguer vers une page vide, on va simplement vider les logs
        try:
            # Vider le buffer des logs existants
            self.driver.get_log('performance')
            logger.info("Logs de performance vidés avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du vidage des logs: {str(e)}")
        
        # Attendre un court instant pour s'assurer que les logs sont bien vidés
        time.sleep(0.5)

    def extract_liked_videos(self):
        """Extrait les URLs des vidéos likées"""
        logger.info("Extraction des vidéos likées...")
        
        # Liste pour stocker les URLs des vidéos
        liked_videos = []
        
        try:
            # Vérifier d'abord si les vidéos sont privées
            try:
                private_elements = self.driver.find_elements(By.XPATH, 
                    "//div[contains(text(), 'This user has set liked videos to private') or " +
                    "contains(text(), 'utilisateur a mis les vidéos') or " +
                    "contains(text(), 'private')]")
                
                if private_elements:
                    logger.warning("Les vidéos likées sont configurées comme privées")
                    return liked_videos
            except Exception as e:
                logger.error(f"Erreur lors de la vérification de la confidentialité: {str(e)}")
            
            # Attendre un court instant pour que le contenu initial se charge
            time.sleep(1)
            
            # Rechercher les vidéos avec différentes méthodes
            video_selectors = [
                "//div[contains(@class, 'tiktok-x6y88p-DivItemContainerV2')]//a[contains(@href, '/video/')]",
                "//div[@data-e2e='user-liked-item']//a[contains(@href, '/video/')]",
                "//div[contains(@class, 'video-feed')]//a[contains(@href, '/video/')]",
                "//a[contains(@href, '/video/')]"
            ]
            
            # Essayer d'extraire les vidéos immédiatement sans attendre
            for selector in video_selectors:
                try:
                    video_elements = self.driver.find_elements(By.XPATH, selector)
                    
                    if video_elements:
                        logger.info(f"Vidéos trouvées avec le sélecteur: {selector}")
                        for element in video_elements:
                            try:
                                video_url = element.get_attribute('href')
                                if video_url and '/video/' in video_url and video_url not in liked_videos:
                                    liked_videos.append(video_url)
                            except Exception as e:
                                continue
                        
                        if liked_videos:
                            break
                except Exception as e:
                    logger.warning(f"Échec avec le sélecteur {selector}: {str(e)}")
            
            # Si on a besoin de plus de vidéos, faire défiler la page
            max_scroll_attempts = 30  # Augmenté pour permettre plus de défilements
            scroll_attempt = 0
            last_height = 0
            
            while len(liked_videos) < 100 and scroll_attempt < max_scroll_attempts:
                # Faire défiler vers le bas
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)  # Délai réduit pour être plus rapide
                
                # Obtenir la nouvelle hauteur
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                
                # Vérifier si on a atteint le bas de la page
                if new_height == last_height:
                    # Faire une dernière tentative avec un délai plus long
                    if scroll_attempt == max_scroll_attempts - 1:
                        time.sleep(2)
                        
                        # Essayer une dernière fois avec tous les sélecteurs
                        for selector in video_selectors:
                            try:
                                for element in self.driver.find_elements(By.XPATH, selector):
                                    video_url = element.get_attribute('href')
                                    if video_url and '/video/' in video_url and video_url not in liked_videos:
                                        liked_videos.append(video_url)
                            except:
                                continue
                    scroll_attempt += 1
                else:
                    # Hauteur différente, on continue à chercher des vidéos
                    last_height = new_height
                    scroll_attempt = 0
                    
                    # Rechercher les vidéos après chaque défilement
                    for selector in video_selectors:
                        try:
                            for element in self.driver.find_elements(By.XPATH, selector):
                                video_url = element.get_attribute('href')
                                if video_url and '/video/' in video_url and video_url not in liked_videos:
                                    liked_videos.append(video_url)
                                    # Afficher le nombre de vidéos trouvées tous les 10
                                    if len(liked_videos) % 10 == 0:
                                        logger.info(f"Nombre de vidéos trouvées: {len(liked_videos)}")
                        except:
                            continue
                            
                    # Limiter à 100 vidéos maximum
                    if len(liked_videos) >= 100:
                        break
            
            # Si toujours aucune vidéo trouvée, utiliser JavaScript pour extraire tous les liens possible
            if not liked_videos:
                logger.warning("Aucune vidéo trouvée avec les sélecteurs XPath, tentative avec JavaScript...")
                try:
                    videos_js = """
                    var links = document.getElementsByTagName('a');
                    var videoLinks = [];
                    for (var i = 0; i < links.length; i++) {
                        var href = links[i].getAttribute('href');
                        if (href && href.includes('/video/')) {
                            videoLinks.push(href);
                        }
                    }
                    return videoLinks;
                    """
                    js_video_links = self.driver.execute_script(videos_js)
                    
                    for link in js_video_links:
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
    
    def _scroll_page(self, scroll_count=5):
        """Fait défiler la page pour charger plus de contenu"""
        logger.info(f"Défilement de la page ({scroll_count} fois)...")
        
        try:
            import time
            
            for i in range(scroll_count):
                # Faire défiler vers le bas
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # Attendre que le contenu se charge
                time.sleep(2)
                
                logger.info(f"Défilement {i+1}/{scroll_count} effectué")
                
        except Exception as e:
            logger.error(f"Erreur lors du défilement: {str(e)}")
    
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
            self.driver.get("https://www.tiktok.com/login/qrcode?redirect_url=https://www.tiktok.com/")
            time.sleep(2)
            
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