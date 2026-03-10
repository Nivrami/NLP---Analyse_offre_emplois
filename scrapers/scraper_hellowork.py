"""
Scraper HelloWork 
=================

Prérequis:
    pip install selenium beautifulsoup4 webdriver-manager requests

Usage:
    python scraper_hellowork.py --test              # Tester sur 1 page
    python scraper_hellowork.py --collect           # Collecter toutes les offres data
    python scraper_hellowork.py --stages            # Collecter uniquement les stages
"""

import sys
import os
import time
import re
import argparse
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db_utils import (
    get_db_connection,
    get_or_create_source,
    inserer_offre,
    DB_PATH,
)

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

import requests

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_PATH = "data/offres_emploi.db"
BASE_URL = "https://www.hellowork.com"

# Mots-cles pour rechercher des offres data/IA
DATA_KEYWORDS = [
    "data scientist",
    "data analyst",
    "data engineer",
    "machine learning",
    "intelligence artificielle",
    "big data",
]

# Mots-clés spécifiques pour les stages
# Le filtre "Stage" est appliqué via le paramètre c=Stage dans l'URL
STAGE_KEYWORDS = DATA_KEYWORDS  # Réutiliser les mêmes mots-clés

# Mapping des villes vers codes régions

REGION_MAPPING = {
    "paris": ("11", "Ile-de-France"),
    "lyon": ("84", "Auvergne-Rhone-Alpes"),
    "marseille": ("93", "Provence-Alpes-Cote d'Azur"),
    "toulouse": ("76", "Occitanie"),
    "bordeaux": ("75", "Nouvelle-Aquitaine"),
    "nantes": ("52", "Pays de la Loire"),
    "lille": ("32", "Hauts-de-France"),
    "rennes": ("53", "Bretagne"),
    "strasbourg": ("44", "Grand Est"),
    "nice": ("93", "Provence-Alpes-Cote d'Azur"),
    "montpellier": ("76", "Occitanie"),
    "grenoble": ("84", "Auvergne-Rhone-Alpes"),
}

# Mapping types de contrat

CONTRACT_MAPPING = {
    "cdi": "CDI",
    "contrat a duree indeterminee": "CDI",
    "cdd": "CDD",
    "contrat a duree determinee": "CDD",
    "stage": "Stage",
    "alternance": "Alternance",
    "apprentissage": "Alternance",
    "contrat pro": "Alternance",
    "interim": "Interim",
    "freelance": "Freelance",
}


def check_dependencies():
    """Verifie que toutes les dépendances sont installees."""
    missing = []
    if not BS4_AVAILABLE:
        missing.append("beautifulsoup4")
    if not SELENIUM_AVAILABLE:
        missing.append("selenium")
    if not WEBDRIVER_MANAGER_AVAILABLE:
        missing.append("webdriver-manager")

    if missing:
        print("Dépendances manquantes:")
        print(f"   pip install {' '.join(missing)}")
        return False
    return True


# ============================================================================
# CLASSE SCRAPER
# ============================================================================


class HelloWorkScraper:
    """
    Scraper pour HelloWork.

    ARCHITECTURE:
    - __init__: Configuration initiale (headless, user-agent)
    - init_driver: Initialise le navigateur Chrome via Selenium
    - build_search_url: Construit l'URL de recherche avec les parametres
    - get_page_content: Recupere le HTML d'une page
    - parse_job_cards: Parse toutes les offres d'une page
    - parse_job_card: Parse une offre individuelle
    - search_jobs: Orchestre la recherche sur plusieurs pages
    """

    def __init__(self, headless: bool = True):
        """
        Initialise le scraper.

        Args:
            headless: Si True, le navigateur s'exécute sans interface graphique
        """
        self.driver = None
        self.headless = headless

        # Session requests pour les requetes simples (sans JS)
        self.session = requests.Session()
        self.session.headers.update({
            # IMPORTANT: Le User-Agent simule un vrai navigateur
            # Sans ca, beaucoup de sites bloquent les requetes
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        })

    def init_driver(self):
        """
        Initialise le driver Selenium.

        POURQUOI SELENIUM ?
        - HelloWork utilise du JavaScript pour charger les offres
        - requests seul ne peut pas executer le JS
        - Selenium controle un vrai navigateur Chrome
        """
        if not SELENIUM_AVAILABLE or not WEBDRIVER_MANAGER_AVAILABLE:
            raise RuntimeError("Selenium ou webdriver-manager non disponible")

        options = Options()

        # Mode headless = pas de fenêtre visible
        if self.headless:
            options.add_argument("--headless=new")

        # Options pour éviter les erreurs courantes
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # Désactiver les notifications et popups
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
        }
        options.add_experimental_option("prefs", prefs)

        # ChromeDriverManager telecharge automatiquement le bon driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)

    def close(self):
        """Ferme proprement le driver."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def build_search_url(self, keyword: str, location: str = "",
                         contract_type: str = None, page: int = 1,
                         sort_by: str = "date") -> str:
        """
        Construit l'URL de recherche HelloWork.

        COMMENT TROUVER LA STRUCTURE DES URLs ?
        1. Aller sur le site et faire une recherche
        2. Observer l'URL resultante
        3. Identifier les parametres

        HelloWork URL format (decouvert via l'interface):
        https://www.hellowork.com/fr-fr/emploi/recherche.html?k=data&l=Lyon&c=Stage&st=date

        Paramètres:
        - k = mot-clé de recherche
        - l = lieu (ville)
        - c = type de contrat (Stage, CDI, CDD, Alternance) - EN MAJUSCULES
        - st = tri (date ou relevance)
        - p = page
        """
        # URL de base pour la recherche
        base = f"{BASE_URL}/fr-fr/emploi/recherche.html"

        params = {
            "k": keyword,  # k = keyword
            "st": sort_by,  # st = sort type (date ou relevance)
        }

        if location:
            params["l"] = location  # l = location (lieu)

        # Type de contrat - IMPORTANT: utiliser la bonne casse
        if contract_type:
            # HelloWork utilise des majuscules: Stage, CDI, CDD, Alternance
            contract_mapping = {
                "stage": "Stage",
                "cdi": "CDI",
                "cdd": "CDD",
                "alternance": "Alternance",
                "interim": "Intérim",
            }
            mapped = contract_mapping.get(contract_type.lower(), contract_type)
            params["c"] = mapped

        if page > 1:
            params["p"] = page  # p = page

        return f"{base}?" + urlencode(params)

    def get_page_content(self, url: str) -> Optional[str]:
        """
        Recupere le contenu HTML d'une page via Selenium.

        ETAPES:
        1. Initialiser le driver si nécessaire
        2. Charger la page
        3. Attendre le chargement du JS
        4. Gérer les popups (cookies, etc.)
        5. Retourner le HTML
        """
        if not self.driver:
            self.init_driver()

        try:
            print(f"      Chargement: {url[:60]}...")
            self.driver.get(url)

            # IMPORTANT: Attendre que le JS charge le contenu
            time.sleep(2)

            # Fermer les popups de cookies si présent
            try:
                cookie_selectors = [
                    "#didomi-notice-agree-button",
                    "button[id*='accept']",
                    "button[class*='accept']",
                    ".didomi-continue-without-agreeing",
                ]
                for selector in cookie_selectors:
                    try:
                        cookie_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                        cookie_btn.click()
                        time.sleep(1)
                        break
                    except NoSuchElementException:
                        continue
            except Exception:
                pass

            # Attendre que les offres soient chargées (chercher un élément spécifique)
            try:
                # Attendre qu'un lien d'offre apparaisse
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/fr-fr/emplois/']"))
                )
                print("      Offres chargees")
            except TimeoutException:
                print("      Timeout: offres non trouvées, tentative avec scroll...")

            # Scroll pour charger plus de contenu (lazy loading)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)

            return self.driver.page_source

        except Exception as e:
            print(f"      Erreur: {e}")
            return None

    def parse_job_cards(self, html: str) -> List[Dict]:
        """
        Parse les cartes d'offres d'emploi depuis le HTML.

        HelloWork charge les offres dynamiquement. On identifie les offres
        par leurs liens qui contiennent '/fr-fr/emplois/'.

        Returns:
            Liste de dictionnaires contenant les infos de base des offres
        """
        soup = BeautifulSoup(html, 'html.parser')
        jobs = []
        seen_urls = set()

        # METHODE 1: Trouver tous les liens vers des offres
        job_links = soup.find_all('a', href=lambda x: x and '/fr-fr/emplois/' in x)
        print(f"      Liens d'offres trouves: {len(job_links)}")

        for link in job_links:
            try:
                href = link.get('href', '')

                # Eviter les doublons (meme URL)
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Remonter au conteneur parent (la carte)
                card = link
                for _ in range(10):  # Remonter max 10 niveaux
                    parent = card.parent
                    if parent and parent.name in ['li', 'article', 'div']:
                        # Verifier si c'est un conteneur significatif
                        if len(parent.get_text(strip=True)) > 50:
                            card = parent
                            break
                    card = parent if parent else card

                job = self.parse_job_card_v2(card, href)
                if job and job.get('titre'):
                    jobs.append(job)

            except Exception as e:
                continue

        # Dédupliquer par titre si nécessaire
        unique_jobs = []
        seen_titles = set()
        for job in jobs:
            title_key = (job.get('titre', ''), job.get('entreprise', ''))
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_jobs.append(job)

        print(f"      Offres uniques: {len(unique_jobs)}")
        return unique_jobs

    def parse_job_card_v2(self, card, href: str) -> Optional[Dict]:
        """
        Parse une carte d'offre en utilisant le texte brut et l'URL.

        STRATEGIE:
        - Extraire l'URL de l'offre
        - Parser le texte de la carte pour trouver les infos
        - Utiliser des heuristiques basees sur le contenu
        """
        job = {'url': urljoin(BASE_URL, href)}

        # Extraire un ID de l'URL
        match = re.search(r'/emplois/([^/]+)-(\d+)\.html', href)
        if match:
            job['id'] = f"hw_{match.group(2)}"

        # Obtenir tout le texte de la carte
        text = card.get_text(separator='\n', strip=True)
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        if not lines:
            return None

        # Le titre est généralement la première ligne significative
        for line in lines[:3]:
            if len(line) > 10 and len(line) < 150:
                job['titre'] = line
                break

        # Chercher l'entreprise (souvent apres le titre)
        for i, line in enumerate(lines[1:6]):
            # L'entreprise est souvent un nom court sans mots-cles de lieu
            if (len(line) > 2 and len(line) < 80 and
                not any(x in line.lower() for x in ['stage', 'cdi', 'cdd', 'paris', 'lyon', 'france', '€', 'jour'])):
                if line != job.get('titre'):
                    job['entreprise'] = line
                    break

        # Chercher le lieu (ville)
        for line in lines:
            line_lower = line.lower()
            # Detecter une ville
            for city in ['paris', 'lyon', 'marseille', 'toulouse', 'bordeaux', 'nantes', 'lille', 'rennes', 'strasbourg', 'nice', 'montpellier', 'grenoble']:
                if city in line_lower:
                    job['lieu'] = line
                    break
            if job.get('lieu'):
                break

        # Chercher le type de contrat
        full_text = ' '.join(lines).lower()
        for key, value in CONTRACT_MAPPING.items():
            if key in full_text:
                job['type_contrat'] = value
                break

        return job if job.get('titre') else None

    def get_job_details(self, url: str) -> Optional[Dict]:
        """
        Récupère les details d'une offre (description, etc.) depuis sa page.

        Args:
            url: URL de l'offre

        Returns:
            Dict avec les details supplementaires (description, salaire, etc.)
        """
        if not self.driver:
            self.init_driver()

        try:
            self.driver.get(url)
            time.sleep(2)

            # Fermer popups si necessaire
            try:
                cookie_btn = self.driver.find_element(By.CSS_SELECTOR, "#didomi-notice-agree-button")
                cookie_btn.click()
                time.sleep(0.5)
            except:
                pass

            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            details = {}

            # Chercher la description
            desc_selectors = [
                'div[class*="description"]',
                'div[class*="job-description"]',
                'div[class*="content"]',
                'section[class*="description"]',
                'article',
            ]

            for selector in desc_selectors:
                desc_elem = soup.select_one(selector)
                if desc_elem and len(desc_elem.get_text(strip=True)) > 100:
                    details['description'] = desc_elem.get_text(separator='\n', strip=True)
                    break

            # Si non trouvé avec sélecteurs, chercher le plus gros bloc de texte
            if not details.get('description'):
                all_divs = soup.find_all('div')
                best_div = None
                best_len = 0
                # Mots a eviter (cookies, menus, etc.)
                blacklist = ['connexion', 'inscription', 'menu', 'recherche',
                            'traceurs', 'cookies', 'accepter', 'refuser',
                            'politique de confidentialite', 'rgpd', 'didomi']
                for div in all_divs:
                    text = div.get_text(strip=True)
                    text_lower = text.lower()[:200]
                    if len(text) > best_len and len(text) < 10000:
                        # Verifier que ce n'est pas du contenu parasite
                        if not any(x in text_lower for x in blacklist):
                            best_len = len(text)
                            best_div = div
                if best_div and best_len > 200:
                    details['description'] = best_div.get_text(separator='\n', strip=True)[:5000]

            # Nettoyer la description des textes de cookies si présent
            if details.get('description'):
                desc = details['description']
                # Supprimer les textes de cookies/RGPD
                cookie_patterns = [
                    'Ces traceurs sont nécessaires',
                    'traceurs sont nécessaires',
                    'cookies nécessaires',
                    'politique de confidentialité',
                ]
                for pattern in cookie_patterns:
                    if pattern.lower() in desc.lower():
                        # Trouver et supprimer cette partie
                        idx = desc.lower().find(pattern.lower())
                        if idx > 0:
                            desc = desc[:idx].strip()
                details['description'] = desc if len(desc) > 50 else None

            return details

        except Exception as e:
            print(f"         Erreur details: {e}")
            return None

    def parse_job_card(self, card) -> Optional[Dict]:
        """
        Parse une carte d'offre individuelle (methode legacy).
        """
        job = {}

        # ====== TITRE ======
        title_selectors = [
            ('h2', {}),
            ('h3', {}),
            ('a', {'class': re.compile(r'title|job-title')}),
            ('span', {'class': re.compile(r'title')}),
        ]

        for tag, attrs in title_selectors:
            title_elem = card.find(tag, attrs) if attrs else card.find(tag)
            if title_elem:
                job['titre'] = title_elem.get_text(strip=True)
                link = title_elem if title_elem.name == 'a' else title_elem.find('a')
                if link and link.get('href'):
                    job['url'] = urljoin(BASE_URL, link['href'])
                break

        # ====== ENTREPRISE ======
        company_selectors = [
            ('span', {'class': re.compile(r'company|entreprise')}),
            ('div', {'class': re.compile(r'company|entreprise')}),
            ('a', {'class': re.compile(r'company')}),
        ]

        for tag, attrs in company_selectors:
            company_elem = card.find(tag, attrs)
            if company_elem:
                job['entreprise'] = company_elem.get_text(strip=True)
                break

        # ====== LIEU ======
        location_selectors = [
            ('span', {'class': re.compile(r'location|lieu|city')}),
            ('div', {'class': re.compile(r'location|lieu')}),
        ]

        for tag, attrs in location_selectors:
            location_elem = card.find(tag, attrs)
            if location_elem:
                job['lieu'] = location_elem.get_text(strip=True)
                break

        # ====== TYPE DE CONTRAT ======
        contract_selectors = [
            ('span', {'class': re.compile(r'contract|contrat|type')}),
            ('div', {'class': re.compile(r'contract|contrat')}),
        ]

        for tag, attrs in contract_selectors:
            contract_elem = card.find(tag, attrs)
            if contract_elem:
                contract_text = contract_elem.get_text(strip=True).lower()
                for key, value in CONTRACT_MAPPING.items():
                    if key in contract_text:
                        job['type_contrat'] = value
                        break
                break

        # ====== SALAIRE ======
        salary_elem = card.find(class_=re.compile(r'salary|salaire'))
        if salary_elem:
            job['salaire'] = salary_elem.get_text(strip=True)

        # ====== ID UNIQUE ======
        # Générer un ID a partir de l'URL ou du titre
        if job.get('url'):
            # Extraire un ID de l'URL si possible
            match = re.search(r'/(\d+)', job['url'])
            if match:
                job['id'] = f"hw_{match.group(1)}"
            else:
                job['id'] = f"hw_{hash(job['url'])}"

        return job if job.get('titre') else None

    def search_jobs(self, keyword: str, location: str = "",
                    contract_type: str = None, max_pages: int = 3,
                    delay: float = 2.0, fetch_details: bool = True) -> List[Dict]:
        """
        Recherche des offres d'emploi sur plusieurs pages.

        Args:
            keyword: Mot-cle de recherche
            location: Ville ou region
            contract_type: Type de contrat (stage, cdi, etc.)
            max_pages: Nombre maximum de pages a scraper
            delay: Delai entre chaque page (politesse + eviter ban)
            fetch_details: Si True, recupere la description de chaque offre

        Returns:
            Liste des offres trouvées
        """
        all_jobs = []
        seen_ids = set()

        print(f"   Recherche: '{keyword}'" +
              (f" | Type: {contract_type}" if contract_type else "") +
              (f" | Lieu: {location}" if location else ""))

        for page in range(1, max_pages + 1):
            print(f"   Page {page}/{max_pages}:")

            url = self.build_search_url(keyword, location, contract_type, page)
            html = self.get_page_content(url)

            if not html:
                print(f"      Impossible de charger la page")
                break

            jobs = self.parse_job_cards(html)

            if not jobs:
                print(f"      Aucune offre trouvee")
                break

            # Filtrer les doublons
            new_jobs = []
            for job in jobs:
                job_id = job.get('id') or job.get('url') or job.get('titre')
                if job_id and job_id not in seen_ids:
                    seen_ids.add(job_id)
                    new_jobs.append(job)

            # Récupérer les détails (description) de chaque offre
            if fetch_details:
                print(f"      Recuperation des descriptions...")
                for i, job in enumerate(new_jobs):
                    if job.get('url'):
                        details = self.get_job_details(job['url'])
                        if details:
                            job.update(details)
                        # Petit delai pour ne pas surcharger le serveur
                        if i < len(new_jobs) - 1:
                            time.sleep(0.5)

            all_jobs.extend(new_jobs)
            print(f"      -> {len(new_jobs)} nouvelles offres (total: {len(all_jobs)})")

            # Arrêter si trop peu de résultats (dernière page)
            if len(new_jobs) < 3:
                break

            # IMPORTANT: Delai entre les requetes
            # - Respecte le serveur (politesse)
            # - Evite d'etre banni
            time.sleep(delay)

        return all_jobs


# ============================================================================
# FONCTIONS BASE DE DONNEES
# ============================================================================
# Fonctions pour stocker les offres dans SQLite

# Les fonctions DB (get_or_create_*, inserer_offre, offre_existe) sont
# importées depuis database.db_utils.


# ============================================================================
# FONCTIONS DE COLLECTE
# ============================================================================

def collecter_offres(keywords: List[str], contract_type: str = None,
                     max_pages: int = 5, db_path: str = DB_PATH) -> Tuple[int, int]:
    """
    Collecte les offres HelloWork et les stocke en base.

    FLUX:
    1. Connexion a la base
    2. Créer/recuperer la source HelloWork
    3. Pour chaque mot-clé:
       - Scraper les pages
       - Insérer chaque offre (si pas doublon)
    4. Retourner les statistiques
    """
    if not check_dependencies():
        return 0, 0

    conn = get_db_connection(db_path)
    id_source = get_or_create_source(conn, "HelloWork", "https://www.hellowork.com")

    scraper = HelloWorkScraper(headless=True)
    total_insere = 0
    total_doublons = 0

    try:
        for keyword in keywords:
            print(f"\n{'='*50}")
            print(f"Mot-cle: '{keyword}'")
            print('='*50)

            jobs = scraper.search_jobs(
                keyword,
                contract_type=contract_type,
                max_pages=max_pages
            )

            for job in jobs:
                result = inserer_offre(conn, job, id_source)
                if result:
                    total_insere += 1
                else:
                    total_doublons += 1

            print(f"   Resume: {len(jobs)} scrapees, "
                  f"{total_insere} inserees, {total_doublons} doublons")

    finally:
        scraper.close()
        conn.close()

    return total_insere, total_doublons


def afficher_stats(db_path: str = DB_PATH):
    """Affiche les statistiques de la collecte HelloWork."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 50)
    print("STATISTIQUES HELLOWORK")
    print("=" * 50)

    cursor.execute("""
        SELECT COUNT(*) FROM fait_offres f
        JOIN dim_source s ON f.id_source = s.id_source
        WHERE s.nom_source = 'HelloWork'
    """)
    print(f"\nTotal offres HelloWork: {cursor.fetchone()[0]}")

    cursor.execute("""
        SELECT c.libelle_contrat, COUNT(*)
        FROM fait_offres f
        JOIN dim_source s ON f.id_source = s.id_source
        JOIN dim_contrat c ON f.id_contrat = c.id_contrat
        WHERE s.nom_source = 'HelloWork'
        GROUP BY c.libelle_contrat
        ORDER BY COUNT(*) DESC
    """)
    print("\nPar type de contrat:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]}")

    conn.close()


# ============================================================================
# MAIN - POINT D'ENTREE
# ============================================================================

def main():
    """
    Point d'entrée du script.

    ARGUMENTS:
    --test     : Mode test (1 page, 1 mot-cle)
    --collect  : Collecte complete
    --stages   : Collecter uniquement les stages
    --pages N  : Nombre de pages par mot-cle
    --stats    : Afficher les statistiques
    """
    parser = argparse.ArgumentParser(description="Scraper HelloWork France")
    parser.add_argument("--test", action="store_true", help="Mode test")
    parser.add_argument("--collect", action="store_true", help="Collecte complete")
    parser.add_argument("--stages", action="store_true", help="Collecter les stages")
    parser.add_argument("--pages", type=int, default=5, help="Pages par mot-cle (defaut: 5)")
    parser.add_argument("--stats", action="store_true", help="Statistiques")

    args = parser.parse_args()

    if args.stats:
        afficher_stats()
        return

    if args.test:
        print("MODE TEST - 1 page, 1 mot-cle")
        print("="*50)
        insere, doublons = collecter_offres(["data scientist"], max_pages=1)
        print(f"\nResultat: {insere} inserees, {doublons} doublons")

    elif args.stages:
        print("COLLECTE DES STAGES")
        print("="*50)
        # Utiliser le parametre c=Stage pour filtrer
        insere, doublons = collecter_offres(
            STAGE_KEYWORDS,
            contract_type="stage",  # Sera converti en c=Stage dans l'URL
            max_pages=args.pages
        )
        print(f"\nTotal: {insere} stages inseres, {doublons} doublons")
        afficher_stats()

    elif args.collect:
        print("COLLECTE COMPLETE")
        print("="*50)
        insere, doublons = collecter_offres(DATA_KEYWORDS, max_pages=args.pages)
        print(f"\nTotal: {insere} inserees, {doublons} doublons")
        afficher_stats()

    else:
        print("SCRAPER HELLOWORK")
        print("="*50)
        print("\nUsage:")
        print("  python scraper_hellowork.py --test       # Mode test")
        print("  python scraper_hellowork.py --collect    # Collecte complete")
        print("  python scraper_hellowork.py --stages     # Collecter les stages")
        print("  python scraper_hellowork.py --stats      # Statistiques")
        print("\nOptions:")
        print("  --pages N  : Nombre de pages par mot-cle (defaut: 3)")


if __name__ == "__main__":
    main()
