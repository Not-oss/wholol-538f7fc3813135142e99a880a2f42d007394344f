from httpx import AsyncClient
from requests import Session
import re
from utils import Download, DownloadAsync


class TTDownloader(Session):
    BASE_URL = 'https://ttdownloader.com/'

    def __init__(self, url: str) -> None:
        super().__init__()
        self.headers: dict[str, str] = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 '
            'Safari/537.36',
            'origin': 'https://ttdownloader.com',
            'referer': 'https://ttdownloader.com/',
            'sec-ch-ua': '"Chromium";v="94",'
            '"Google Chrome";v="94", ";'
            'Not A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': "Linux",
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'x-requested-with': 'XMLHttpRequest'
        }
        self.url = url

    def get_media(self) -> list[Download]:
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Récupérer la page d'accueil
            indexsource = self.get(self.BASE_URL)
            
            # Extraire le token
            token_match = re.findall(r'value=\"([0-9a-z]+)\"', indexsource.text)
            if not token_match:
                logger.warning("Impossible de trouver le token sur ttdownloader.com")
                return [Download(self.url, self, 'video')]
            
            # Faire la requête pour obtenir les liens
            result = self.post(
                self.BASE_URL+'search/',
                data={'url': self.url, 'format': '', 'token': token_match[0]}
            )
            
            # Extraire les liens avec le regex
            media_links = re.findall(r'(https?://.*?.php\?v\=.*?)\"', result.text)
            
            # S'assurer que nous avons au moins un lien
            if not media_links:
                logger.warning("Aucun lien média trouvé")
                return [Download(self.url, self, 'video')]
            
            # Gérer le cas où nous n'avons pas exactement 3 liens
            if len(media_links) == 3:
                # Cas normal: nowm, wm, audio
                return [
                    Download(media_links[0], self, 'video'),
                    Download(media_links[1], self, 'video', True),
                    Download(media_links[2], self, 'music')
                ]
            elif len(media_links) == 2:
                # Cas avec seulement 2 liens, supposer nowm et wm (pas d'audio)
                return [
                    Download(media_links[0], self, 'video'),
                    Download(media_links[1], self, 'video', True)
                ]
            elif len(media_links) == 1:
                # Cas avec un seul lien, supposer nowm
                return [
                    Download(media_links[0], self, 'video')
                ]
            else:
                # Cas inattendu, retourner une liste vide
                logger.warning(f"Format inattendu: {len(media_links)} liens trouvés")
                return [Download(self.url, self, 'video')]
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des médias: {str(e)}")
            # En cas d'erreur, retourner l'URL d'origine 
            return [Download(self.url, self, 'video')]


class TTDownloaderAsync(AsyncClient):
    BASE_URL = 'https://ttdownloader.com/'

    def __init__(self, url: str) -> None:
        super().__init__()
        self.headers: dict[str, str] = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 '
            'Safari/537.36',
            'origin': 'https://ttdownloader.com',
            'referer': 'https://ttdownloader.com/',
            'sec-ch-ua': '"Chromium";v="94",'
            '"Google Chrome";v="94", ";'
            'Not A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': "Linux",
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'x-requested-with': 'XMLHttpRequest'
        }
        self.url = url

    async def get_media(self) -> list[DownloadAsync]:
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Récupérer la page d'accueil
            indexsource = await self.get(self.BASE_URL, follow_redirects=True)
            
            # Extraire le token
            token_match = re.findall(r'value=\"([0-9a-z]+)\"', indexsource.text)
            if not token_match:
                logger.warning("Impossible de trouver le token sur ttdownloader.com")
                return [DownloadAsync(self.url, self, 'video')]
            
            # Faire la requête pour obtenir les liens
            result = await self.post(
                self.BASE_URL+'search/',
                data={'url': self.url, 'format': '', 'token': token_match[0]},
                follow_redirects=True
            )
            
            # Extraire les liens avec le regex
            media_links = re.findall(r'(https?://.*?.php\?v\=.*?)\"', result.text)
            
            # S'assurer que nous avons au moins un lien
            if not media_links:
                logger.warning("Aucun lien média trouvé")
                return [DownloadAsync(self.url, self, 'video')]
            
            # Gérer le cas où nous n'avons pas exactement 3 liens
            if len(media_links) == 3:
                # Cas normal: nowm, wm, audio
                return [
                    DownloadAsync(media_links[0], self, 'video'),
                    DownloadAsync(media_links[1], self, 'video', True),
                    DownloadAsync(media_links[2], self, 'music')
                ]
            elif len(media_links) == 2:
                # Cas avec seulement 2 liens, supposer nowm et wm (pas d'audio)
                return [
                    DownloadAsync(media_links[0], self, 'video'),
                    DownloadAsync(media_links[1], self, 'video', True)
                ]
            elif len(media_links) == 1:
                # Cas avec un seul lien, supposer nowm
                return [
                    DownloadAsync(media_links[0], self, 'video')
                ]
            else:
                # Cas inattendu, retourner une liste vide
                logger.warning(f"Format inattendu: {len(media_links)} liens trouvés")
                return [DownloadAsync(self.url, self, 'video')]
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des médias: {str(e)}")
            # En cas d'erreur, retourner l'URL d'origine
            return [DownloadAsync(self.url, self, 'video')]


def ttdownloader(url: str) -> list[Download]:
    return TTDownloader(url).get_media()


async def ttdownloader_async(url: str):
    return await TTDownloaderAsync(url).get_media() 