"""
Scraper Indeed France
=====================
Utilise Selenium pour gerer le JavaScript et BeautifulSoup pour parser le HTML.

Prérequis:
    pip install selenium beautifulsoup4 webdriver-manager requests

Usage:
    python scraper_indeed.py --test              # Tester sur 1 page
    python scraper_indeed.py --collect           # Collecter toutes les offres data
    python scraper_indeed.py --collect --pages 5 # Limiter a 5 pages
    python scraper_indeed.py --stages            # Collecter uniquement les stages
"""

import sys
import os
import time
import re
import argparse
import json
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, quote, urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db_utils import (
    get_db_connection,
    get_or_create_source,
    inserer_offre,
    DB_PATH,
)

# Packages web scraping
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

DB_PATH = "data/offres_emploi.db"
BASE_URL = "https://fr.indeed.com"

# Mots-cles pour rechercher des offres data/IA
DATA_KEYWORDS = [
    "data scientist",
    "data analyst",
    "data engineer",
    "machine learning",
    "intelligence artificielle",
    "deep learning",
    "MLOps",
    "NLP",
    "big data",
]

# Mots-clés specifiques pour les stages
STAGE_KEYWORDS = [
    "stage data scientist",
    "stage data analyst",
    "stage data engineer",
    "stage machine learning",
    "stage intelligence artificielle",
    "stage data science",
    "stage big data",
]

# Mapping des villes Indeed vers nos codes regions
REGION_MAPPING = {
    "paris": ("11", "Ile-de-France"),
    "ile-de-france": ("11", "Ile-de-France"),
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

# Mapping types de contrat Indeed
CONTRACT_MAPPING = {
    "cdi": "CDI",
    "contrat a duree indeterminee": "CDI",
    "temps plein": "CDI",
    "cdd": "CDD",
    "contrat a duree determinee": "CDD",
    "stage": "Stage",
    "alternance": "Alternance",
    "apprentissage": "Alternance",
    "contrat pro": "Alternance",
    "freelance": "Freelance",
    "interim": "Interim",
    "mission": "Interim",
    "temps partiel": "Temps partiel",
}


def check_dependencies():
    """Vérifie que toutes les dependances sont installées."""
    missing = []
    if not BS4_AVAILABLE:
        missing.append("beautifulsoup4")
    if not SELENIUM_AVAILABLE:
        missing.append("selenium")
    if not WEBDRIVER_MANAGER_AVAILABLE:
        missing.append("webdriver-manager")

    if missing:
        print("Dependances manquantes:")
        print(f"   pip install {' '.join(missing)}")
        return False
    return True


class IndeedScraper:
    """Scraper pour Indeed France."""

    def __init__(self, headless: bool = True):
        """
        Initialise le scraper.

        Args:
            headless: Si True, le navigateur s'execute en arrière-plan
        """
        self.driver = None
        self.headless = headless
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        })

    def init_driver(self):
        """Initialise le driver Selenium."""
        if not SELENIUM_AVAILABLE or not WEBDRIVER_MANAGER_AVAILABLE:
            raise RuntimeError("Selenium ou webdriver-manager non disponible")

        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
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

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)

    def close(self):
        """Ferme le driver."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def build_search_url(self, keyword: str, location: str = "", job_type: str = None, start: int = 0) -> str:
        """
        Construit l'URL de recherche Indeed.

        Args:
            keyword: Mot-cle de recherche
            location: Ville ou region
            job_type: Type de contrat (stage, cdi, cdd, etc.)
            start: Index de debut pour la pagination
        """
        params = {
            "q": keyword,
            "l": location or "France",
            "start": start,
        }

        # Filtrer par type de contrat
        if job_type:
            job_type_mapping = {
                "stage": "internship",
                "cdi": "permanent",
                "cdd": "contract",
                "alternance": "apprenticeship",
            }
            if job_type.lower() in job_type_mapping:
                params["jt"] = job_type_mapping[job_type.lower()]

        return f"{BASE_URL}/emplois?" + urlencode(params)

    def get_page_content(self, url: str) -> Optional[str]:
        """Récupère le contenu HTML d'une page via Selenium."""
        if not self.driver:
            self.init_driver()

        try:
            self.driver.get(url)
            time.sleep(2)  # Attendre le chargement JavaScript

            # Fermer les popups de cookies si présents
            try:
                cookie_btn = self.driver.find_element(By.ID, "onetrust-accept-btn-handler")
                cookie_btn.click()
                time.sleep(1)
            except NoSuchElementException:
                pass

            # Scroll pour charger plus de contenu
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)

            return self.driver.page_source
        except Exception as e:
            print(f"   Erreur lors du chargement: {e}")
            return None

    def parse_job_cards(self, html: str) -> List[Dict]:
        """
        Parse les cartes d'offres d'emploi depuis le HTML.

        Returns:
            Liste de dictionnaires contenant les infos de base des offres
        """
        soup = BeautifulSoup(html, 'html.parser')
        jobs = []

        # Selecteurs Indeed (peuvent changer)
        job_cards = soup.find_all('div', class_=re.compile(r'job_seen_beacon|cardOutline|resultContent'))

        if not job_cards:
            # Essayer d'autres selecteurs
            job_cards = soup.find_all('div', {'data-jk': True})

        for card in job_cards:
            try:
                job = self.parse_job_card(card)
                if job and job.get('titre'):
                    jobs.append(job)
            except Exception as e:
                continue

        return jobs

    def parse_job_card(self, card) -> Optional[Dict]:
        """Parse une carte d'offre individuelle."""
        job = {}

        # Titre du poste
        title_elem = card.find(['h2', 'a'], class_=re.compile(r'jobTitle|jcs-JobTitle'))
        if title_elem:
            job['titre'] = title_elem.get_text(strip=True)
            # Recuperer le lien
            link = title_elem.find('a') if title_elem.name != 'a' else title_elem
            if link and link.get('href'):
                job['url'] = urljoin(BASE_URL, link['href'])
                # Extraire l'ID de l'offre
                job_id_match = re.search(r'jk=([a-f0-9]+)', link['href'])
                if job_id_match:
                    job['id'] = job_id_match.group(1)

        # Entreprise
        company_elem = card.find(['span', 'div'], {'data-testid': 'company-name'})
        if not company_elem:
            company_elem = card.find(class_=re.compile(r'companyName|company'))
        if company_elem:
            job['entreprise'] = company_elem.get_text(strip=True)

        # Lieu
        location_elem = card.find(['div', 'span'], {'data-testid': 'text-location'})
        if not location_elem:
            location_elem = card.find(class_=re.compile(r'companyLocation|location'))
        if location_elem:
            job['lieu'] = location_elem.get_text(strip=True)

        # Salaire (si disponible)
        salary_elem = card.find(class_=re.compile(r'salary|estimated-salary'))
        if salary_elem:
            job['salaire'] = salary_elem.get_text(strip=True)

        # Type de contrat
        metadata = card.find_all(class_=re.compile(r'metadata|attribute'))
        for meta in metadata:
            text = meta.get_text(strip=True).lower()
            for key, value in CONTRACT_MAPPING.items():
                if key in text:
                    job['type_contrat'] = value
                    break

        # Description courte
        snippet_elem = card.find(class_=re.compile(r'job-snippet|underShelfFooter'))
        if snippet_elem:
            job['description_courte'] = snippet_elem.get_text(strip=True)

        # Date de publication
        date_elem = card.find(class_=re.compile(r'date|posted'))
        if date_elem:
            job['date_publication'] = date_elem.get_text(strip=True)

        return job if job.get('titre') else None

    def get_job_details(self, job_url: str) -> Dict:
        """Récupère les détails complets d'une offre."""
        html = self.get_page_content(job_url)
        if not html:
            return {}

        soup = BeautifulSoup(html, 'html.parser')
        details = {}

        # Description complete
        desc_elem = soup.find('div', {'id': 'jobDescriptionText'})
        if desc_elem:
            details['description'] = desc_elem.get_text(separator='\n', strip=True)

        # Infos supplémentaires
        info_section = soup.find('div', class_=re.compile(r'jobsearch-JobInfoHeader'))
        if info_section:
            # Type de contrat, experience, etc.
            metadata = info_section.find_all('div', class_=re.compile(r'jobsearch-JobMetadataHeader'))
            for meta in metadata:
                text = meta.get_text(strip=True).lower()
                for key, value in CONTRACT_MAPPING.items():
                    if key in text:
                        details['type_contrat'] = value
                        break

        return details

    def search_jobs(self, keyword: str, location: str = "", job_type: str = None,
                    max_pages: int = 5, delay: float = 2.0) -> List[Dict]:
        """
        Recherche des offres d'emploi.

        Args:
            keyword: Mot-clé de recherche
            location: Ville ou région
            job_type: Type de contrat (stage, cdi, etc.)
            max_pages: Nombre maximum de pages à scraper
            delay: Délai entre chaque requete (en secondes)

        Returns:
            Liste des offres trouvées
        """
        all_jobs = []
        seen_ids = set()

        for page in range(max_pages):
            start = page * 10  # Indeed affiche 10-15 offres par page

            url = self.build_search_url(keyword, location, job_type, start)
            print(f"   Page {page + 1}/{max_pages}: {url[:80]}...")

            html = self.get_page_content(url)
            if not html:
                print(f"   Impossible de charger la page {page + 1}")
                break

            jobs = self.parse_job_cards(html)

            if not jobs:
                print(f"   Aucune offre trouvée sur la page {page + 1}")
                break

            # Filtrer les doublons
            new_jobs = []
            for job in jobs:
                job_id = job.get('id') or job.get('url')
                if job_id and job_id not in seen_ids:
                    seen_ids.add(job_id)
                    new_jobs.append(job)

            all_jobs.extend(new_jobs)
            print(f"   -> {len(new_jobs)} nouvelles offres (total: {len(all_jobs)})")

            if len(new_jobs) < 5:  # Probablement la dernière page
                break

            time.sleep(delay)

        return all_jobs


# =============================================================================
# FONCTIONS DE BASE DE DONNEES
# =============================================================================

# Les fonctions DB (get_or_create_*, inserer_offre, offre_existe) sont
# importées depuis database.db_utils.


# =============================================================================
# FONCTIONS DE COLLECTE
# =============================================================================

def collecter_offres(keywords: List[str], job_type: str = None,
                     max_pages: int = 3, db_path: str = DB_PATH) -> Tuple[int, int]:
    """
    Collecte les offres Indeed et les stocke en base.

    Args:
        keywords: Liste de mots-clès à rechercher
        job_type: Type de contrat (stage, cdi, etc.)
        max_pages: Nombre de pages par mot-cle
        db_path: Chemin de la base de données

    Returns:
        Tuple (nombre insere, nombre doublons)
    """
    if not check_dependencies():
        return 0, 0

    conn = get_db_connection(db_path)
    id_source = get_or_create_source(conn, "Indeed", "https://fr.indeed.com")

    scraper = IndeedScraper(headless=True)
    total_insere = 0
    total_doublons = 0

    try:
        for keyword in keywords:
            print(f"\nRecherche: '{keyword}'" + (f" (type: {job_type})" if job_type else ""))

            jobs = scraper.search_jobs(keyword, job_type=job_type, max_pages=max_pages)

            for job in jobs:
                result = inserer_offre(conn, job, id_source)
                if result:
                    total_insere += 1
                else:
                    total_doublons += 1

            print(f"   Total pour '{keyword}': {len(jobs)} offres scrapees")

    finally:
        scraper.close()
        conn.close()

    return total_insere, total_doublons


def afficher_stats(db_path: str = DB_PATH):
    """Affiche les statistiques de la collecte Indeed."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 50)
    print("STATISTIQUES INDEED")
    print("=" * 50)

    # Total offres Indeed
    cursor.execute("""
        SELECT COUNT(*) FROM fait_offres f
        JOIN dim_source s ON f.id_source = s.id_source
        WHERE s.nom_source = 'Indeed'
    """)
    print(f"\nTotal offres Indeed: {cursor.fetchone()[0]}")

    # Par type de contrat
    cursor.execute("""
        SELECT c.libelle_contrat, COUNT(*)
        FROM fait_offres f
        JOIN dim_source s ON f.id_source = s.id_source
        JOIN dim_contrat c ON f.id_contrat = c.id_contrat
        WHERE s.nom_source = 'Indeed'
        GROUP BY c.libelle_contrat
        ORDER BY COUNT(*) DESC
    """)
    print("\nPar type de contrat:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]}")

    conn.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Scraper Indeed France")
    parser.add_argument("--test", action="store_true", help="Mode test (1 page, 1 mot-cle)")
    parser.add_argument("--collect", action="store_true", help="Collecter toutes les offres data")
    parser.add_argument("--stages", action="store_true", help="Collecter uniquement les stages")
    parser.add_argument("--pages", type=int, default=3, help="Nombre de pages par mot-cle")
    parser.add_argument("--stats", action="store_true", help="Afficher les statistiques")

    args = parser.parse_args()

    if args.stats:
        afficher_stats()
        return

    if args.test:
        print("Mode test - 1 page, 1 mot-cle")
        insere, doublons = collecter_offres(["data scientist"], max_pages=1)
        print(f"\nResultat: {insere} inserees, {doublons} doublons")

    elif args.stages:
        print("Collecte des stages data/IA")
        insere, doublons = collecter_offres(STAGE_KEYWORDS, job_type="stage", max_pages=args.pages)
        print(f"\nTotal: {insere} stages inseres, {doublons} doublons")
        afficher_stats()

    elif args.collect:
        print("Collecte complete des offres data/IA")
        insere, doublons = collecter_offres(DATA_KEYWORDS, max_pages=args.pages)
        print(f"\nTotal: {insere} inserees, {doublons} doublons")
        afficher_stats()

    else:
        print("Usage:")
        print("  python scraper_indeed.py --test       # Mode test")
        print("  python scraper_indeed.py --collect    # Collecte complete")
        print("  python scraper_indeed.py --stages     # Collecter les stages")
        print("  python scraper_indeed.py --stats      # Statistiques")


if __name__ == "__main__":
    main()
