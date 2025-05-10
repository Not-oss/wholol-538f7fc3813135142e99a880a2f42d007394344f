import os
from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash, Response
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import json
import logging
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import socket

from models import db, User, Game, GamePlayer, Video, Round, Vote
from tiktok_extractor import TikTokExtractor, logger
from config import Config

# Variable globale pour l'extracteur TikTok
current_extractor = None

# Initialisation de l'application
app = Flask(__name__)
app.config.from_object(Config)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tiktok_game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
db.init_app(app)

# Configuration de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuration de Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Création des tables de la base de données
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes pour l'authentification
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/qr_login')
def qr_login():
    # Initialiser l'extracteur TikTok en mode non-headless (navigateur visible)
    extractor = TikTokExtractor(headless=False, output_dir="temp_data")
    
    # Stocker l'instance dans la session
    session['extractor_active'] = True
    
    # Lancer le navigateur et capturer le QR code
    extractor.setup_driver()
    extractor.driver.get("https://www.tiktok.com/login/qrcode?redirect_url=https://www.tiktok.com/")
    
    # Attendre que la page charge
    import time
    time.sleep(2)
    
    # Capturer le QR code
    qr_code = extractor.capture_qr_code()
    
    # Stocker l'extracteur dans une variable globale (à améliorer dans une version de production)
    global current_extractor
    current_extractor = extractor
    
    # Copier le QR code dans le dossier static pour qu'il soit accessible au client
    import shutil
    import os
    
    # S'assurer que le dossier static/uploads existe
    os.makedirs('static/uploads', exist_ok=True)
    
    # Copier le QR code depuis temp_data vers static/uploads
    qr_source_path = os.path.join("temp_data", "tiktok_qr.png")
    qr_destination_path = os.path.join("static", "uploads", "tiktok_qr.png")
    shutil.copy2(qr_source_path, qr_destination_path)
    
    # URL du QR code accessible au client
    qr_code_url = url_for('static', filename='uploads/tiktok_qr.png')
    
    return render_template('qr_login.html', qr_code_url=qr_code_url, mode="visible")


@app.route('/check_login_status')
def check_login_status():
    global current_extractor
    
    if not hasattr(current_extractor, 'driver'):
        return jsonify({'status': 'error', 'message': 'No active session'})
    
    try:
        # Vérifier si l'utilisateur s'est connecté
        is_logged_in = current_extractor.driver.current_url.startswith("https://www.tiktok.com/foryou") or \
                        "@" in current_extractor.driver.current_url
        
        if is_logged_in:
            # Extraire les informations utilisateur
            current_extractor.extract_user_info()
            
            # Créer ou mettre à jour l'utilisateur dans la base de données
            user_data = current_extractor.user_data
            
            if not user_data.get('username'):
                return jsonify({'status': 'error', 'message': 'Failed to get user data'})
            
            user = User.query.filter_by(tiktok_username=user_data.get('username')).first()
            is_first_login = False
            
            if not user:
                user = User(
                    tiktok_username=user_data.get('username'),
                    tiktok_id=user_data.get('user_id', ''),
                    display_name=user_data.get('screen_name', ''),
                    avatar_url=user_data.get('avatar_url', ''),
                    email=user_data.get('email', '')
                )
                db.session.add(user)
                is_first_login = True
            else:
                user.display_name = user_data.get('screen_name', user.display_name)
                user.avatar_url = user_data.get('avatar_url', user.avatar_url)
                user.email = user_data.get('email', user.email)
            
            db.session.commit()
            
            # Connecter l'utilisateur
            login_user(user)
            
            # Toujours rediriger vers la page d'extraction pour première connexion ou non
            # La redirection vers le Dashboard sera faite une fois l'extraction complétée
            logger.info("Connexion réussie, préparation pour l'extraction des vidéos")
            
            return jsonify({
                'status': 'extracting',
                'message': 'Extraction of liked videos in progress...',
                'user': {
                    'username': user.tiktok_username,
                    'display_name': user.display_name,
                    'avatar_url': user.avatar_url
                },
                'first_login': is_first_login
            })
        else:
            logger.info(f"Utilisateur non connecté, URL actuelle: {current_extractor.driver.current_url}")
            return jsonify({'status': 'waiting'})
    except Exception as e:
        logger.exception(f"Erreur lors de la vérification du statut de connexion: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/extract_progress')
@login_required
def extract_progress():
    """
    Endpoint pour extraire les vidéos likées et suivre la progression
    """
    global current_extractor
    
    logger.info(f"Démarrage de l'extraction des vidéos pour {current_user.tiktok_username}")
    
    if not hasattr(current_extractor, 'driver'):
        logger.error("Aucune session active pour l'extracteur")
        return jsonify({'status': 'error', 'message': 'No active session'})
    
    # Vérifier si nous sommes dans un contexte Socket.IO
    has_socket = hasattr(request, 'sid')
    
    # Fonction pour émettre les mises à jour, seulement si un socket est disponible
    def emit_update(update_data):
        if has_socket:
            socketio.emit('extraction_update', update_data, room=request.sid)
    
    try:
        # Accéder au profil de l'utilisateur
        username = current_user.tiktok_username
        current_url = current_extractor.driver.current_url
        
        logger.info(f"URL actuelle avant extraction: {current_url}")
        
        # Mise à jour de l'état: accès au profil
        status_update = {'status': 'in_progress', 'step': 'profile_access', 'progress': 10, 
                         'message': 'Accès au profil TikTok...'}
        emit_update(status_update)
        
        # Préparer la capture pour le captcha sans passer par about:blank
        current_extractor.prepare_captcha_capture()
        
        # Navigation vers le profil avec vérification
        logger.info(f"Navigation vers le profil: @{username}")
        profile_url = f"https://www.tiktok.com/@{username}"
        current_extractor.driver.get(profile_url)
        
        # Mise à jour de l'état: navigation vers le profil
        status_update = {'status': 'in_progress', 'step': 'profile_navigation', 'progress': 20, 
                         'message': 'Navigation vers votre profil...'}
        emit_update(status_update)
        
        # Vérifier que l'URL a bien changé
        new_url = current_extractor.driver.current_url
        logger.info(f"URL après navigation vers le profil: {new_url}")
        
        if "tiktok.com" not in new_url:
            # Tenter une seconde fois avec un délai
            logger.warning("URL non valide, nouvel essai de navigation")
            time.sleep(2)
            current_extractor.driver.get(profile_url)
            
            new_url = current_extractor.driver.current_url
            logger.info(f"URL après seconde navigation: {new_url}")
            
            if "tiktok.com" not in new_url:
                # Si toujours pas sur TikTok, utiliser JavaScript
                logger.warning("Toujours pas sur TikTok, essai avec JavaScript")
                try:
                    current_extractor.driver.execute_script("window.location.href = arguments[0]", profile_url)
                    time.sleep(3)
                except Exception as js_error:
                    logger.error(f"Erreur JS: {str(js_error)}")
        
        # Vérifier si la page est chargée correctement
        try:
            # Attendre que des éléments clés soient présents
            WebDriverWait(current_extractor.driver, 8).until(
                EC.presence_of_element_located((By.XPATH, '//header'))
            )
            logger.info("Page de profil correctement chargée (header trouvé)")
        except Exception as e:
            logger.warning(f"La page du profil ne semble pas être correctement chargée: {str(e)}")
            screenshot_path = os.path.join("temp_data", f"captcha_check_{int(time.time())}.png")
            current_extractor.driver.save_screenshot(screenshot_path)
            logger.info(f"Capture d'écran sauvegardée: {screenshot_path}")
            
            # Mise à jour de l'état: problème de chargement
            status_update = {'status': 'in_progress', 'step': 'page_loading_issue', 'progress': 25, 
                            'message': 'Problème de chargement de la page, tentative de résolution...'}
            emit_update(status_update)
            
            # Si la page n'est pas chargée, on actualise et on attend
            current_extractor.driver.refresh()
            time.sleep(3)
        
        # Mise à jour de l'état: vérification captcha
        status_update = {'status': 'in_progress', 'step': 'captcha_check', 'progress': 30, 
                        'message': 'Vérification et résolution des captchas...'}
        emit_update(status_update)
        
        # Résoudre le captcha si nécessaire
        max_attempts = 3
        captcha_solved = False
        for attempt in range(max_attempts):
            logger.info(f"Tentative {attempt+1}/{max_attempts} de résolution du captcha")
            if current_extractor.solve_captcha():
                captcha_solved = True
                logger.info("Captcha résolu avec succès")
                break
            time.sleep(2)
        
        if not captcha_solved:
            logger.warning("Impossible de résoudre le captcha après plusieurs tentatives")
        
        # Mise à jour de l'état: recherche onglet Liked
        status_update = {'status': 'in_progress', 'step': 'finding_liked_tab', 'progress': 40, 
                        'message': 'Recherche de l\'onglet "Liked"...'}
        emit_update(status_update)
        
        # Tenter de cliquer sur l'onglet "Liked" avec plusieurs méthodes
        liked_tab_found = False
        
        try:
            # Méthode 1: Sélecteur data-e2e
            logger.info("Tentative de trouver l'onglet Liked via sélecteur data-e2e")
            liked_tab = WebDriverWait(current_extractor.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@data-e2e="liked-tab"]'))
            )
            liked_tab.click()
            liked_tab_found = True
            logger.info("Onglet Liked trouvé et cliqué via sélecteur data-e2e")
        except Exception as e:
            logger.warning(f"Échec de la méthode 1 pour l'onglet Liked: {str(e)}")
            try:
                # Méthode 2: Texte de l'onglet
                logger.info("Tentative via texte de l'onglet")
                tab_selectors = [
                    "//div[contains(text(), 'Liked') or contains(text(), 'J'aime')]",
                    "//span[contains(text(), 'Liked') or contains(text(), 'J'aime')]",
                    "//a[contains(text(), 'Liked') or contains(text(), 'J'aime')]"
                ]
                
                for selector in tab_selectors:
                    try:
                        liked_tab = current_extractor.driver.find_element(By.XPATH, selector)
                        liked_tab.click()
                        liked_tab_found = True
                        logger.info(f"Onglet Liked trouvé et cliqué via sélecteur: {selector}")
                        break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"Échec de la méthode 2 pour l'onglet Liked: {str(e)}")
                try:
                    # Méthode 3: JavaScript
                    logger.info("Tentative via JavaScript")
                    tabs_js = """
                    var tabs = document.querySelectorAll('div[role="tab"], a[role="tab"], li[role="tab"]');
                    var likedTab = null;
                    for (var i = 0; i < tabs.length; i++) {
                        if (tabs[i].textContent.includes('Liked') || 
                            tabs[i].textContent.includes('J'aime') || 
                            tabs[i].getAttribute('data-e2e') === 'liked-tab') {
                            tabs[i].click();
                            return true;
                        }
                    }
                    return false;
                    """
                    liked_tab_found = current_extractor.driver.execute_script(tabs_js)
                    if liked_tab_found:
                        logger.info("Onglet Liked trouvé et cliqué via JavaScript")
                except Exception as e:
                    logger.warning(f"Échec de la méthode 3 pour l'onglet Liked: {str(e)}")
                    try:
                        # Méthode 4: Recherche générique
                        logger.info("Tentative via recherche générique")
                        possible_tabs = current_extractor.driver.find_elements(By.XPATH, 
                            "//a | //div[@role='tab'] | //li[@role='tab'] | //span[@role='tab']")
                        
                        for tab in possible_tabs:
                            try:
                                tab_text = tab.text.lower()
                                logger.info(f"Texte de l'onglet: '{tab_text}'")
                                if 'liked' in tab_text or 'j\'aime' in tab_text:
                                    tab.click()
                                    liked_tab_found = True
                                    logger.info("Onglet Liked trouvé et cliqué via recherche générique")
                                    break
                            except:
                                continue
                    except Exception as e:
                        logger.warning(f"Échec de la méthode 4 pour l'onglet Liked: {str(e)}")
        
        if not liked_tab_found:
            # Échec de l'extraction
            logger.error("Impossible de trouver l'onglet Liked")
            screenshot_path = os.path.join("temp_data", f"liked_tab_error_{int(time.time())}.png")
            current_extractor.driver.save_screenshot(screenshot_path)
            logger.info(f"Capture d'écran sauvegardée: {screenshot_path}")
            
            status_update = {'status': 'error', 'step': 'liked_tab_not_found', 'progress': 0, 
                            'message': 'Impossible de trouver l\'onglet "Liked". Vos vidéos likées sont peut-être privées.'}
            emit_update(status_update)
            
            return jsonify({
                'status': 'error', 
                'message': "Could not find the 'Liked' tab. Your liked videos might be private."
            })
        
        # Mise à jour: résolution captcha après clic
        status_update = {'status': 'in_progress', 'step': 'captcha_after_click', 'progress': 50, 
                        'message': 'Vérification des captchas après navigation...'}
        emit_update(status_update)
        
        # Vérifier s'il y a un nouveau captcha après le clic
        if current_extractor.solve_captcha():
            logger.info("Captcha résolu après clic sur l'onglet Liked")
        
        # Mise à jour: début extraction vidéos
        status_update = {'status': 'in_progress', 'step': 'extracting_videos', 'progress': 60, 
                        'message': 'Extraction des vidéos likées...'}
        emit_update(status_update)
        
        # Extraire les vidéos likées
        liked_videos = current_extractor.extract_liked_videos()
        logger.info(f"Nombre de vidéos extraites: {len(liked_videos)}")
        
        # Si aucune vidéo n'est trouvée, faire un scrolling plus agressif
        if not liked_videos:
            logger.warning("Aucune vidéo trouvée, tentative de scrolling agressif")
            status_update = {'status': 'in_progress', 'step': 'aggressive_scrolling', 'progress': 65, 
                            'message': 'Aucune vidéo trouvée, scrolling agressif...'}
            emit_update(status_update)
            
            # Scrolling agressif
            for i in range(5):
                current_extractor.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            
            # Réessayer l'extraction
            liked_videos = current_extractor.extract_liked_videos()
            logger.info(f"Nombre de vidéos après scrolling agressif: {len(liked_videos)}")
        
        # Si toujours aucune vidéo, vérifier si elles sont privées
        if not liked_videos:
            logger.warning("Vérification si les vidéos sont privées")
            private_elements = current_extractor.driver.find_elements(By.XPATH, 
                "//div[contains(text(), 'This user has set liked videos to private') or contains(text(), 'utilisateur a mis les vidéos')]")
            
            if private_elements:
                logger.error("Les vidéos likées sont définies comme privées")
                status_update = {'status': 'error', 'step': 'private_videos', 'progress': 0, 
                                'message': 'Vos vidéos likées sont définies comme privées. Veuillez les rendre publiques.'}
                emit_update(status_update)
                
                return jsonify({
                    'status': 'error',
                    'message': 'Your liked videos are set to private. Please make them public to use this feature.'
                })
            
            logger.warning("Aucune vidéo trouvée et pas de message 'privé' détecté")
            status_update = {'status': 'warning', 'step': 'no_videos', 'progress': 0, 
                            'message': 'Aucune vidéo trouvée. Vous n\'avez peut-être pas de vidéos likées.'}
            emit_update(status_update)
            
            return jsonify({
                'status': 'warning',
                'message': 'No videos found. You might have no liked videos.'
            })
        
        # Mise à jour: traitement des vidéos
        status_update = {'status': 'in_progress', 'step': 'processing_videos', 'progress': 75, 
                        'message': f'Traitement de {len(liked_videos[:100])} vidéos...'}
        emit_update(status_update)
        
        # Stocker les vidéos dans la base de données
        new_videos_count = 0
        from ttdownloader import ttdownloader
        
        for i, video_url in enumerate(liked_videos[:100]):
            # Mise à jour pour chaque vidéo traitée
            progress = 75 + (i * 20 / min(len(liked_videos[:100]), 100))
            status_update = {'status': 'in_progress', 'step': 'processing_video', 'progress': progress, 
                            'message': f'Traitement vidéo {i+1}/{len(liked_videos[:100])}...'}
            emit_update(status_update)
            
            video_id = video_url.split('/video/')[-1].split('?')[0]
            logger.info(f"Traitement de la vidéo {i+1}/{len(liked_videos[:100])}: {video_id}")
            
            # Vérifier si la vidéo existe déjà
            video = Video.query.filter_by(tiktok_id=video_id).first()
            
            if not video:
                try:
                    media_info = ttdownloader(video_url)
                    
                    # S'assurer que nous avons au moins un résultat
                    if media_info and len(media_info) > 0:
                        # Prendre le premier élément (vidéo sans filigrane) - stocker uniquement l'URL
                        video_url_no_watermark = media_info[0].url
                        
                        video = Video(
                            tiktok_id=video_id,
                            url=video_url,
                            download_url=video_url_no_watermark,  # Stocke uniquement l'URL de téléchargement
                            user_id=current_user.id
                        )
                        db.session.add(video)
                        new_videos_count += 1
                    else:
                        logger.warning(f"Aucune URL de téléchargement trouvée pour la vidéo {video_id}")
                except Exception as e:
                    logger.error(f"Error processing video {video_id}: {str(e)}")
                    continue
            else:
                logger.info(f"Vidéo {video_id} déjà existante dans la base de données")
            
            # Associer la vidéo à l'utilisateur si ce n'est pas déjà fait
            if video and video.user_id != current_user.id:
                video.user_id = current_user.id
                logger.info(f"Vidéo {video_id} associée à l'utilisateur {current_user.tiktok_username}")
        
        db.session.commit()
        
        # Mise à jour finale: extraction terminée
        status_update = {'status': 'completed', 'step': 'extraction_complete', 'progress': 100, 
                        'message': f'Extraction terminée: {len(liked_videos)} vidéos (dont {new_videos_count} nouvelles)'}
        emit_update(status_update)
        
        logger.info(f"Extraction terminée pour {current_user.tiktok_username}: {len(liked_videos)} vidéos (dont {new_videos_count} nouvelles)")
        
        # Fermer l'instance Chrome après avoir terminé l'extraction
        if hasattr(current_extractor, 'driver'):
            try:
                logger.info("Fermeture de l'instance Chrome...")
                current_extractor.driver.quit()
                logger.info("Instance Chrome fermée avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de la fermeture de Chrome: {str(e)}")
        
        return jsonify({
            'status': 'success',
            'message': f'Extracted {len(liked_videos)} videos (added {new_videos_count} new videos)',
            'videos_count': len(liked_videos),
            'new_videos_count': new_videos_count,
            'redirect': url_for('dashboard')
        })
        
    except Exception as e:
        logger.exception(f"Erreur lors de l'extraction des vidéos likées: {str(e)}")
        
        status_update = {'status': 'error', 'step': 'extraction_error', 'progress': 0, 
                        'message': f'Erreur d\'extraction: {str(e)}'}
        emit_update(status_update)
        
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/extract_likes')
@login_required
def extract_likes():
    """Méthode traditionnelle pour extraire les vidéos likées (sans suivi détaillé)"""
    global current_extractor
    
    if not hasattr(current_extractor, 'driver'):
        return jsonify({'status': 'error', 'message': 'No active session'})
    
    try:
        # Accès au profil TikTok
        username = current_user.tiktok_username
        profile_url = f"https://www.tiktok.com/@{username}"
        current_extractor.driver.get(profile_url)
        
        # Résoudre captchas
        current_extractor.solve_captcha()
        
        # Cliquer sur l'onglet "Liked"
        liked_tab_found = False
        try:
            liked_tab = WebDriverWait(current_extractor.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@data-e2e="liked-tab"]'))
            )
            liked_tab.click()
            liked_tab_found = True
        except:
            # Utiliser les méthodes alternatives
            try:
                tabs_js = """
                var tabs = document.querySelectorAll('div[role="tab"], a[role="tab"], li[role="tab"]');
                for (var i = 0; i < tabs.length; i++) {
                    if (tabs[i].textContent.includes('Liked') || tabs[i].textContent.includes('J'aime')) {
                        tabs[i].click();
                        return true;
                    }
                }
                return false;
                """
                liked_tab_found = current_extractor.driver.execute_script(tabs_js)
            except:
                pass
        
        if not liked_tab_found:
            return jsonify({'status': 'error', 'message': 'Could not find Liked tab'})
        
        # Extraire les vidéos
        liked_videos = current_extractor.extract_liked_videos()
        
        # Si pas de vidéos, faire un scrolling
        if not liked_videos:
            for i in range(5):
                current_extractor.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            liked_videos = current_extractor.extract_liked_videos()
        
        # Stocker dans la base de données
        new_videos_count = 0
        from ttdownloader import ttdownloader
        
        for video_url in liked_videos[:100]:
            video_id = video_url.split('/video/')[-1].split('?')[0]
            
            # Vérifier si existe déjà
            video = Video.query.filter_by(tiktok_id=video_id).first()
            
            if not video:
                try:
                    media_info = ttdownloader(video_url)
                    
                    # S'assurer que nous avons au moins un résultat
                    if media_info and len(media_info) > 0:
                        # Prendre le premier élément (vidéo sans filigrane)
                        video_url_no_watermark = media_info[0].url
                        
                        video = Video(
                            tiktok_id=video_id,
                            url=video_url,
                            download_url=video_url_no_watermark,
                            user_id=current_user.id
                        )
                        db.session.add(video)
                        new_videos_count += 1
                    else:
                        logger.warning(f"Aucune URL de téléchargement trouvée pour la vidéo {video_id}")
                except Exception as e:
                    logger.error(f"Error processing video {video_id}: {str(e)}")
                    continue
            
            # Associer la vidéo à l'utilisateur
            if video and video.user_id != current_user.id:
                video.user_id = current_user.id
        
        db.session.commit()
        
        # Fermer l'instance Chrome après avoir terminé l'extraction
        if hasattr(current_extractor, 'driver'):
            try:
                logger.info("Fermeture de l'instance Chrome...")
                current_extractor.driver.quit()
                logger.info("Instance Chrome fermée avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de la fermeture de Chrome: {str(e)}")
        
        return jsonify({
            'status': 'success',
            'message': f'Extracted {len(liked_videos)} videos (added {new_videos_count} new videos)',
            'videos_count': len(liked_videos),
            'new_videos_count': new_videos_count
        })
    
    except Exception as e:
        logger.exception(f"Erreur lors de l'extraction des vidéos likées: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/loading')
@login_required
def loading_page():
    """Page affichée durant le chargement et l'extraction des vidéos"""
    return render_template('loading.html', username=current_user.tiktok_username)

# Routes pour le jeu
@app.route('/dashboard')
@login_required
def dashboard():
    # Récupérer les parties actives de l'utilisateur
    active_games = Game.query.filter(
        Game.players.any(user_id=current_user.id),
        Game.status.in_(['waiting', 'playing'])
    ).all()
    
    # Récupérer l'historique des parties
    past_games = Game.query.filter(
        Game.players.any(user_id=current_user.id),
        Game.status == 'finished'
    ).all()
    
    return render_template('dashboard.html', active_games=active_games, past_games=past_games)

@app.route('/create_game', methods=['GET', 'POST'])
@login_required
def create_game():
    if request.method == 'POST':
        # Générer un code unique pour la partie
        game_code = secrets.token_hex(3).upper()
        
        # Créer une nouvelle partie
        game = Game(
            code=game_code,
            creator_id=current_user.id,
            status='waiting',
            max_rounds=5,
            created_at=datetime.utcnow()
        )
        db.session.add(game)
        
        # Ajouter le créateur comme joueur
        player = GamePlayer(
            game=game,
            user_id=current_user.id,
            score=0,
            joker_used=False
        )
        db.session.add(player)
        db.session.commit()
        
        return redirect(url_for('waiting_room', game_code=game_code))
    
    return render_template('create_game.html')

@app.route('/join_game', methods=['GET', 'POST'])
@login_required
def join_game():
    if request.method == 'POST':
        game_code = request.form.get('game_code').upper()
        
        # Rechercher la partie
        game = Game.query.filter_by(code=game_code, status='waiting').first()
        
        if not game:
            flash('Game not found or already started', 'error')
            return redirect(url_for('dashboard'))
        
        # Vérifier si l'utilisateur est déjà dans la partie
        player = GamePlayer.query.filter_by(game_id=game.id, user_id=current_user.id).first()
        player_added = False
        
        if not player:
            # Vérifier le nombre de joueurs
            player_count = GamePlayer.query.filter_by(game_id=game.id).count()
            
            if player_count >= 10:
                flash('Game is full', 'error')
                return redirect(url_for('dashboard'))
            
            # Ajouter l'utilisateur à la partie
            player = GamePlayer(
                game=game,
                user_id=current_user.id,
                score=0,
                joker_used=False
            )
            db.session.add(player)
            db.session.commit()
            player_added = True
            
            # Notifier les autres joueurs via Socket.IO si un nouveau joueur a été ajouté
            if player_added:
                # Récupérer tous les joueurs pour la mise à jour
                all_players = []
                game_players = GamePlayer.query.filter_by(game_id=game.id).all()
                
                for gp in game_players:
                    user = User.query.get(gp.user_id)
                    all_players.append({
                        'user_id': user.id,
                        'display_name': user.display_name,
                        'tiktok_username': user.tiktok_username,
                        'avatar_url': user.avatar_url
                    })
                
                # Informations sur le nouveau joueur
                new_player = {
                    'user_id': current_user.id,
                    'display_name': current_user.display_name,
                    'tiktok_username': current_user.tiktok_username,
                    'avatar_url': current_user.avatar_url
                }
                
                # Émettre l'événement socket
                socketio.emit('player_joined', {
                    'game_code': game_code,
                    'players': all_players,
                    'new_player': new_player
                }, room=game_code)
        
        return redirect(url_for('waiting_room', game_code=game_code))
    
    return render_template('join_game.html')

@app.route('/waiting_room/<game_code>')
@login_required
def waiting_room(game_code):
    # Rechercher la partie
    game = Game.query.filter_by(code=game_code).first_or_404()
    
    # Vérifier que l'utilisateur est dans la partie
    player = GamePlayer.query.filter_by(game_id=game.id, user_id=current_user.id).first()
    
    if not player:
        flash('You are not part of this game', 'error')
        return redirect(url_for('dashboard'))
    
    # Vérifier si la partie a déjà commencé
    if game.status == 'playing':
        return redirect(url_for('play_game', game_code=game_code))
    
    # Récupérer les joueurs
    players = GamePlayer.query.filter_by(game_id=game.id).all()
    
    return render_template('waiting_room.html', game=game, players=players, is_creator=game.creator_id == current_user.id)

@app.route('/start_game/<game_code>')
@login_required
def start_game(game_code):
    # Rechercher la partie
    game = Game.query.filter_by(code=game_code).first_or_404()
    
    # Vérifier que l'utilisateur est le créateur
    if game.creator_id != current_user.id:
        flash('Only the game creator can start the game', 'error')
        return redirect(url_for('waiting_room', game_code=game_code))
    
    # Vérifier qu'il y a au moins 3 joueurs
    player_count = GamePlayer.query.filter_by(game_id=game.id).count()
    
    if player_count < 3:
        flash('At least 3 players are required to start the game', 'error')
        return redirect(url_for('waiting_room', game_code=game_code))
    
    # Démarrer la partie
    game.status = 'playing'
    game.started_at = datetime.utcnow()
    db.session.commit()
    
    # Notifier tous les joueurs via WebSocket
    socketio.emit('game_started', {'game_code': game_code}, room=game_code)
    
    return redirect(url_for('play_game', game_code=game_code))

@app.route('/play_game/<game_code>')
@login_required
def play_game(game_code):
    # Rechercher la partie
    game = Game.query.filter_by(code=game_code).first_or_404()
    
    # Vérifier que l'utilisateur est dans la partie
    player = GamePlayer.query.filter_by(game_id=game.id, user_id=current_user.id).first()
    
    if not player:
        flash('You are not part of this game', 'error')
        return redirect(url_for('dashboard'))
    
    # Vérifier si la partie est en cours
    if game.status != 'playing':
        if game.status == 'waiting':
            return redirect(url_for('waiting_room', game_code=game_code))
        else:
            return redirect(url_for('game_results', game_code=game_code))
    
    # Récupérer le tour actuel
    current_round = Round.query.filter_by(game_id=game.id).order_by(Round.round_number.desc()).first()
    
    # S'il n'y a pas de tour ou si le tour est terminé, en créer un nouveau
    if not current_round or current_round.status == 'finished':
        # Vérifier si la partie est terminée
        if current_round and current_round.round_number >= game.max_rounds:
            game.status = 'finished'
            game.finished_at = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('game_results', game_code=game_code))
        
        # Créer un nouveau tour
        round_number = 1 if not current_round else current_round.round_number + 1
        
        # Sélectionner une vidéo aléatoire parmi les joueurs
        players = GamePlayer.query.filter_by(game_id=game.id).all()
        eligible_players = [p for p in players if not p.joker_used]
        
        if not eligible_players:
            # Si tous les joueurs ont utilisé leur joker, réinitialiser
            for p in players:
                p.joker_used = False
            eligible_players = players
        
        import random
        selected_player = random.choice(eligible_players)
        
        # Récupérer une vidéo aléatoire du joueur sélectionné
        videos = Video.query.filter_by(user_id=selected_player.user_id).all()
        
        if not videos:
            flash('No videos available for selected player', 'error')
            return redirect(url_for('dashboard'))
        
        selected_video = random.choice(videos)
        
        # Créer le nouveau tour
        new_round = Round(
            game_id=game.id,
            round_number=round_number,
            video_id=selected_video.id,
            user_id=selected_player.user_id,
            status='voting',
            created_at=datetime.utcnow()
        )
        db.session.add(new_round)
        db.session.commit()
        
        current_round = new_round
    
    # Récupérer les informations du tour
    video = Video.query.get(current_round.video_id)
    players = GamePlayer.query.filter_by(game_id=game.id).all()
    
    # Vérifier si l'utilisateur a déjà voté
    user_vote = Vote.query.filter_by(round_id=current_round.id, voter_id=current_user.id).first()
    
    # Vérifier si c'est la vidéo de l'utilisateur
    is_user_video = current_round.user_id == current_user.id
    
    return render_template(
        'play_game.html',
        game=game,
        round=current_round,
        video=video,
        players=players,
        user_vote=user_vote,
        is_user_video=is_user_video
    )

@app.route('/vote/<game_code>', methods=['POST'])
@login_required
def vote(game_code):
    # Rechercher la partie
    game = Game.query.filter_by(code=game_code).first_or_404()
    
    # Vérifier que l'utilisateur est dans la partie
    player = GamePlayer.query.filter_by(game_id=game.id, user_id=current_user.id).first()
    
    if not player:
        return jsonify({'status': 'error', 'message': 'You are not part of this game'})
    
    # Récupérer le tour actuel
    current_round = Round.query.filter_by(game_id=game.id, status='voting').first()
    
    if not current_round:
        return jsonify({'status': 'error', 'message': 'No active round found'})
    
    # Vérifier si l'utilisateur a déjà voté
    existing_vote = Vote.query.filter_by(round_id=current_round.id, voter_id=current_user.id).first()
    
    if existing_vote:
        return jsonify({'status': 'error', 'message': 'You have already voted'})
    
    # Récupérer le joueur voté
    voted_player_id = request.form.get('player_id')
    
    if not voted_player_id:
        return jsonify({'status': 'error', 'message': 'No player selected'})
    
    # Créer le vote
    vote = Vote(
        round_id=current_round.id,
        voter_id=current_user.id,
        voted_user_id=voted_player_id,
        created_at=datetime.utcnow()
    )
    db.session.add(vote)
    db.session.commit()
    
    # Vérifier si tous les joueurs ont voté
    players_count = GamePlayer.query.filter_by(game_id=game.id).count()
    votes_count = Vote.query.filter_by(round_id=current_round.id).count()
    
    # Le joueur dont c'est la vidéo ne vote pas
    if votes_count >= players_count - 1:
        # Terminer le tour
        current_round.status = 'finished'
        current_round.finished_at = datetime.utcnow()
        
        # Attribuer les points
        correct_votes = Vote.query.filter_by(round_id=current_round.id, voted_user_id=current_round.user_id).all()
        
        for correct_vote in correct_votes:
            voter = GamePlayer.query.filter_by(game_id=game.id, user_id=correct_vote.voter_id).first()
            voter.score += 1
        
        db.session.commit()
        
        # Notifier tous les joueurs via WebSocket
        socketio.emit('round_finished', {
            'game_code': game_code,
            'round_id': current_round.id
        }, room=game_code)
    
    return jsonify({'status': 'success', 'message': 'Vote recorded'})

@app.route('/use_joker/<game_code>', methods=['POST'])
@login_required
def use_joker(game_code):
    # Rechercher la partie
    game = Game.query.filter_by(code=game_code).first_or_404()
    
    # Vérifier que l'utilisateur est dans la partie
    player = GamePlayer.query.filter_by(game_id=game.id, user_id=current_user.id).first()
    
    if not player:
        return jsonify({'status': 'error', 'message': 'You are not part of this game'})
    
    # Récupérer le tour actuel
    current_round = Round.query.filter_by(game_id=game.id, status='voting').first()
    
    if not current_round:
        return jsonify({'status': 'error', 'message': 'No active round found'})
    
    # Vérifier si c'est la vidéo de l'utilisateur
    if current_round.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'This is not your video'})
    
    # Vérifier si le joker a déjà été utilisé
    if player.joker_used:
        return jsonify({'status': 'error', 'message': 'You have already used your joker'})
    
    # Utiliser le joker
    player.joker_used = True
    db.session.commit()
    
    # Notifier tous les joueurs via WebSocket
    socketio.emit('joker_used', {
        'game_code': game_code,
        'user_id': current_user.id
    }, room=game_code)
    
    return jsonify({'status': 'success', 'message': 'Joker used'})

@app.route('/round_results/<game_code>/<int:round_id>')
@login_required
def round_results(game_code, round_id):
    # Rechercher la partie
    game = Game.query.filter_by(code=game_code).first_or_404()
    
    # Vérifier que l'utilisateur est dans la partie
    player = GamePlayer.query.filter_by(game_id=game.id, user_id=current_user.id).first()
    
    if not player:
        flash('You are not part of this game', 'error')
        return redirect(url_for('dashboard'))
    
    # Récupérer le tour
    round = Round.query.filter_by(id=round_id, game_id=game.id).first_or_404()
    
    # Récupérer les votes
    votes = Vote.query.filter_by(round_id=round.id).all()
    
    # Récupérer les joueurs
    players = GamePlayer.query.filter_by(game_id=game.id).all()
    
    # Récupérer la vidéo
    video = Video.query.get(round.video_id)
    
    # Récupérer le propriétaire de la vidéo
    video_owner = User.query.get(round.user_id)
    
    return render_template(
        'round_results.html',
        game=game,
        round=round,
        votes=votes,
        players=players,
        video=video,
        video_owner=video_owner
    )

@app.route('/game_results/<game_code>')
@login_required
def game_results(game_code):
    # Rechercher la partie
    game = Game.query.filter_by(code=game_code).first_or_404()
    
    # Vérifier que l'utilisateur est dans la partie
    player = GamePlayer.query.filter_by(game_id=game.id, user_id=current_user.id).first()
    
    if not player:
        flash('You are not part of this game', 'error')
        return redirect(url_for('dashboard'))
    
    # Récupérer les joueurs classés par score
    players = GamePlayer.query.filter_by(game_id=game.id).order_by(GamePlayer.score.desc()).all()
    
    # Récupérer les tours
    rounds = Round.query.filter_by(game_id=game.id).order_by(Round.round_number).all()
    
    return render_template(
        'game_results.html',
        game=game,
        players=players,
        rounds=rounds
    )

# WebSocket events
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('join')
def handle_join(data):
    game_code = data.get('game_code')
    if game_code:
        join_room(game_code)
        
        # Récupérer les informations de la partie pour une mise à jour immédiate
        if current_user.is_authenticated:
            game = Game.query.filter_by(code=game_code).first()
            if game:
                # Récupérer tous les joueurs pour la mise à jour
                all_players = []
                game_players = GamePlayer.query.filter_by(game_id=game.id).all()
                
                for gp in game_players:
                    user = User.query.get(gp.user_id)
                    all_players.append({
                        'user_id': user.id,
                        'display_name': user.display_name,
                        'tiktok_username': user.tiktok_username,
                        'avatar_url': user.avatar_url
                    })
                
                # Envoyer une mise à jour des joueurs au client qui vient de se connecter
                socketio.emit('player_list_update', {
                    'game_code': game_code,
                    'players': all_players
                }, room=request.sid)
        
        print(f'Client joined room: {game_code}')

@socketio.on('leave')
def handle_leave(data):
    game_code = data.get('game_code')
    if game_code:
        leave_room(game_code)
        print(f'Client left room: {game_code}')

@socketio.on('start_auto_extraction')
def start_auto_extraction(data):
    """Démarre automatiquement l'extraction des vidéos pour un nouvel utilisateur"""
    if not current_user.is_authenticated:
        emit('auto_extraction_error', {'message': 'User not authenticated'})
        return
    
    logger.info(f"Démarrage automatique de l'extraction pour {current_user.tiktok_username}")
    
    try:
        # Créer une session Socket.IO
        join_room(request.sid)
        
        # Émettre un statut initial
        emit('extraction_update', {
            'status': 'in_progress',
            'step': 'initialization',
            'progress': 5,
            'message': 'Initialisation de l\'extraction automatique...'
        })
        
        # Appeler l'extraction des vidéos
        result = extract_progress()
        
        # Récupérer la réponse JSON
        response_data = json.loads(result.get_data(as_text=True))
        
        # Vérifier le statut de la réponse
        if response_data.get('status') == 'success':
            emit('auto_extraction_complete', {
                'redirect': url_for('dashboard')
            })
        else:
            emit('auto_extraction_error', {
                'message': response_data.get('message', 'Unknown error')
            })
    
    except Exception as e:
        logger.exception(f"Erreur lors de l'extraction automatique: {str(e)}")
        emit('auto_extraction_error', {'message': str(e)})
        
@app.route('/auto_extract')
@login_required
def auto_extract():
    """Page pour l'extraction automatique au premier login"""
    return render_template('auto_extract.html', username=current_user.tiktok_username)

@socketio.on('start_next_round')
def handle_next_round(data):
    game_code = data.get('game_code')
    if game_code:
        # Vérifier que l'utilisateur est bien le créateur du jeu
        game = Game.query.filter_by(code=game_code).first()
        if game and game.creator_id == current_user.id:
            # Émettre l'événement à tous les joueurs dans la salle
            socketio.emit('next_round', {'game_code': game_code}, room=game_code)
            print(f'Starting next round for game: {game_code}')

@socketio.on('end_game')
def handle_end_game(data):
    game_code = data.get('game_code')
    if game_code:
        # Vérifier que l'utilisateur est bien le créateur du jeu
        game = Game.query.filter_by(code=game_code).first()
        if game and game.creator_id == current_user.id:
            # Émettre l'événement à tous les joueurs dans la salle
            socketio.emit('return_to_dashboard', {'game_code': game_code}, room=game_code)
            print(f'Game ended, returning to dashboard: {game_code}')

# Add datetime to Jinja2 global context
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

if __name__ == '__main__':
    # Récupérer l'adresse IP locale
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"Application accessible à l'adresse: http://{local_ip}:5000")
    
    # Lancer l'application sur toutes les interfaces (0.0.0.0)
    socketio.run(app, debug=True, host='0.0.0.0', port=7777) 