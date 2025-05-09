import os
import requests
from httpx import AsyncClient


class Download:
    """Classe pour télécharger des fichiers depuis une URL"""
    
    def __init__(self, url: str, session: requests.Session, type: str, watermark: bool = False) -> None:
        self.url = url
        self.session = session
        self.type = type
        self.watermark = watermark
    
    def download(self, filename: str = None, path: str = None) -> str:
        """Télécharge le fichier et retourne le chemin"""
        if not filename:
            # Générer un nom de fichier basé sur l'URL
            import hashlib
            hash_name = hashlib.md5(self.url.encode()).hexdigest()[:10]
            filename = f"{hash_name}.mp4" if self.type == 'video' else f"{hash_name}.mp3"
        
        # Créer le dossier de destination si nécessaire
        if path:
            os.makedirs(path, exist_ok=True)
            filepath = os.path.join(path, filename)
        else:
            filepath = filename
        
        # Télécharger le fichier
        response = self.session.get(self.url, stream=True)
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return filepath


class DownloadAsync:
    """Classe pour télécharger des fichiers depuis une URL de manière asynchrone"""
    
    def __init__(self, url: str, client: AsyncClient, type: str, watermark: bool = False) -> None:
        self.url = url
        self.client = client
        self.type = type
        self.watermark = watermark
    
    async def download(self, filename: str = None, path: str = None) -> str:
        """Télécharge le fichier de manière asynchrone et retourne le chemin"""
        if not filename:
            # Générer un nom de fichier basé sur l'URL
            import hashlib
            hash_name = hashlib.md5(self.url.encode()).hexdigest()[:10]
            filename = f"{hash_name}.mp4" if self.type == 'video' else f"{hash_name}.mp3"
        
        # Créer le dossier de destination si nécessaire
        if path:
            os.makedirs(path, exist_ok=True)
            filepath = os.path.join(path, filename)
        else:
            filepath = filename
        
        # Télécharger le fichier
        response = await self.client.get(self.url)
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        return filepath 