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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('tiktok_extractor.log')
    ]
)
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
    
    def __init__(self, output_dir="temp_data"):
        """Initialisation"""
        self.output_dir = output_dir
        self.browser = None
        self.page = None
        self.user_data = {}
        
        os.makedirs(output_dir, exist_ok=True)
    
    def setup_driver(self):
        """Initialise le navigateur Playwright avec les options nécessaires"""
        try:
            # Configurer le display pour Xvfb
            os.environ['DISPLAY'] = ':99'
            
            playwright = sync_playwright().start()
            self.browser = playwright.chromium.launch(
                headless=False,  # Mode headed activé
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                    '--display=:99'
                ]
            )
            
            # Créer un nouveau contexte avec un user agent personnalisé
            context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Créer une nouvelle page
            self.page = context.new_page()
            
            # Configurer les timeouts
            self.page.set_default_timeout(30000)
            self.page.set_default_navigation_timeout(30000)
            
            logger.info("Navigateur Playwright initialisé avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du navigateur: {str(e)}")
            return False
    
    def extract_user_info(self):
        """Extrait les informations de l'utilisateur connecté"""
        try:
            # Attendre que la page soit chargée
            self.page.wait_for_load_state('networkidle')
            
            # Vérifier si nous sommes sur la page de profil
            if not self.page.url.startswith("https://www.tiktok.com/@"):
                logger.warning("Pas sur la page de profil, redirection...")
                self.page.goto("https://www.tiktok.com/")
                time.sleep(2)
            
            # Extraire les informations de l'utilisateur
            user_info = self.page.evaluate("""() => {
                const userInfo = {};
                // Extraire le nom d'utilisateur
                const usernameElement = document.querySelector('h1[data-e2e="user-title"]');
                if (usernameElement) userInfo.username = usernameElement.textContent;
                
                // Extraire l'ID utilisateur
                const userIdElement = document.querySelector('strong[data-e2e="user-id"]');
                if (userIdElement) userInfo.user_id = userIdElement.textContent;
                
                // Extraire le nom d'affichage
                const displayNameElement = document.querySelector('h2[data-e2e="user-subtitle"]');
                if (displayNameElement) userInfo.screen_name = displayNameElement.textContent;
                
                // Extraire l'URL de l'avatar
                const avatarElement = document.querySelector('img[data-e2e="user-avatar"]');
                if (avatarElement) userInfo.avatar_url = avatarElement.src;
                
                return userInfo;
            }""")
            
            if user_info:
                self.user_data = user_info
                logger.info(f"Informations utilisateur extraites: {user_info}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des informations utilisateur: {str(e)}")
            return False
    
    def capture_qr_code(self):
        """Capture le QR code de connexion"""
        try:
            # Attendre que le canvas du QR code soit chargé
            self.page.wait_for_selector('canvas[data-e2e="qrcode-canvas"]', timeout=10000)
            
            # Capturer le canvas
            qr_canvas = self.page.query_selector('canvas[data-e2e="qrcode-canvas"]')
            if not qr_canvas:
                logger.error("Canvas QR code non trouvé")
                return False
            
            # Obtenir les données du canvas
            canvas_data = self.page.evaluate("""(canvas) => {
                return canvas.toDataURL('image/png');
            }""", qr_canvas)
            
            # Convertir les données base64 en image
            image_data = canvas_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            
            # Sauvegarder l'image
            qr_path = os.path.join(self.output_dir, "tiktok_qr.png")
            with open(qr_path, 'wb') as f:
                f.write(image_bytes)
            
            logger.info(f"QR code capturé et sauvegardé: {qr_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la capture du QR code: {str(e)}")
            return False
    
    def solve_captcha(self):
        """Tente de résoudre le captcha si présent"""
        try:
            # Vérifier si un captcha est présent
            captcha_frame = self.page.query_selector('iframe[title*="captcha"]')
            if not captcha_frame:
                return True
            
            logger.info("Captcha détecté, tentative de résolution...")
            
            # Attendre que le captcha soit chargé
            self.page.wait_for_timeout(2000)
            
            # Prendre une capture d'écran du captcha
            captcha_path = os.path.join(self.output_dir, f"captcha_{int(time.time())}.png")
            captcha_frame.screenshot(path=captcha_path)
            
            logger.info(f"Capture d'écran du captcha sauvegardée: {captcha_path}")
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du captcha: {str(e)}")
            return False
    
    def extract_liked_videos(self):
        """Extrait les URLs des vidéos likées"""
        try:
            # Attendre que les vidéos soient chargées
            self.page.wait_for_selector('div[data-e2e="user-post-item"]', timeout=10000)
            
            # Extraire les URLs des vidéos
            video_urls = self.page.evaluate("""() => {
                const videos = document.querySelectorAll('div[data-e2e="user-post-item"] a');
                return Array.from(videos).map(video => video.href);
            }""")
            
            # Faire défiler pour charger plus de vidéos
            for _ in range(3):
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                # Extraire les nouvelles URLs
                new_urls = self.page.evaluate("""() => {
                    const videos = document.querySelectorAll('div[data-e2e="user-post-item"] a');
                    return Array.from(videos).map(video => video.href);
                }""")
                
                video_urls.extend(new_urls)
            
            # Supprimer les doublons
            video_urls = list(set(video_urls))
            
            logger.info(f"Nombre de vidéos likées trouvées: {len(video_urls)}")
            return video_urls
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des vidéos likées: {str(e)}")
            return []
    
    def prepare_captcha_capture(self):
        """Prépare la capture pour le captcha"""
        try:
            # Vérifier si nous sommes sur une page TikTok
            if not self.page.url.startswith("https://www.tiktok.com"):
                self.page.goto("https://www.tiktok.com")
                time.sleep(2)
            
            # Attendre que la page soit chargée
            self.page.wait_for_load_state('networkidle')
            
            logger.info("Page préparée pour la capture du captcha")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la préparation de la capture: {str(e)}")
            return False
    
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