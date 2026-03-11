# 💻 Script : scraper_wttj.py

**Source :** `scraper_wttj.py`

```python
"""
Scraper Welcome to the Jungle
=============================
Récupère les offres d'emploi data/IA depuis Welcome to the Jungle.

Utilise Selenium pour gérer le JavaScript et BeautifulSoup pour parser le HTML.

Prérequis:
    pip install selenium beautifulsoup4 webdriver-manager requests

Usage:
    python scraper_wttj.py --test              # Tester sur 1 page
    python scraper_wttj.py --collect           # Collecter toutes les offres data
    python scraper_wttj.py --collect --pages 5 # Limiter à 5 pages
    python scraper_wttj.py --collect --stages  # Collecter uniquement les stages
    python scraper_wttj.py --collect --stages --pages 5  # Stages sur 5 pages
"""

import sys
import os
import time
import re
import argparse
import json
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote

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
BASE_URL = "https://www.welcometothejungle.com"

# Mots-clés pour rechercher des offres data/IA
DATA_KEYWORDS = [
    "data scientist",
    "data analyst",
    "data engineer",
    "machine learning",
    "intelligence artificielle",
    "deep learning",
    "MLOps",
    "NLP",
]

# Mapping des régions WTTJ vers nos codes régions
REGION_MAPPING = {
    "paris": ("11", "Île-de-France"),
    "ile-de-france": ("11", "Île-de-France"),
    "lyon": ("84", "Auvergne-Rhône-Alpes"),
    "rhone": ("84", "Auvergne-Rhône-Alpes"),
    "auvergne-rhone-alpes": ("84", "Auvergne-Rhône-Alpes"),
    "marseille": ("93", "Provence-Alpes-Côte d'Azur"),
    "provence-alpes-cote-d-azur": ("93", "Provence-Alpes-Côte d'Azur"),
    "toulouse": ("76", "Occitanie"),
    "occitanie": ("76", "Occitanie"),
    "bordeaux": ("75", "Nouvelle-Aquitaine"),
    "nouvelle-aquitaine": ("75", "Nouvelle-Aquitaine"),
    "nantes": ("52", "Pays de la Loire"),
    "pays-de-la-loire": ("52", "Pays de la Loire"),
    "lille": ("32", "Hauts-de-France"),
    "hauts-de-france": ("32", "Hauts-de-France"),
    "rennes": ("53", "Bretagne"),
    "bretagne": ("53", "Bretagne"),
    "strasbourg": ("44", "Grand Est"),
    "grand-est": ("44", "Grand Est"),
    "nice": ("93", "Provence-Alpes-Côte d'Azur"),
    "montpellier": ("76", "Occitanie"),
    "grenoble": ("84", "Auvergne-Rhône-Alpes"),
}

# Mapping types de contrat WTTJ
CONTRACT_MAPPING = {
    "cdi": "CDI",
    "full-time": "CDI",
    "permanent": "CDI",
    "cdd": "CDD",
    "temporary": "CDD",
    "fixed-term": "CDD",
    "stage": "Stage",
    "internship": "Stage",
    "intern": "Stage",
    "alternance": "Alternance",
    "apprenticeship": "Alternance",
    "apprentice": "Alternance",
    "freelance": "Freelance",
    "contractor": "Freelance",
    "vie": "VIE",
    "v.i.e": "VIE",
}


def check_dependencies():
    """Vérifie que toutes les dépendances sont installées."""
    missing = []
    if not BS4_AVAILABLE:
        missing.append("beautifulsoup4")
    if not SELENIUM_AVAILABLE:
        missing.append("selenium")
    if not WEBDRIVER_MANAGER_AVAILABLE:
        missing.append("webdriver-manager")
    
    if missing:
        print("❌ Dépendances manquantes:")
        print(f"   pip install {' '.join(missing)}")
        return False
    return True


class WTTJScraper:
    """Scraper pour Welcome to the Jungle."""
    
    def __init__(self, headless: bool = True):
        """
        Initialise le scraper.
        
        Args:
            headless: Si True, le navigateur s'exécute en arrière-plan
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
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium n'est pas installé")
        
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Désactiver les logs
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        if WEBDRIVER_MANAGER_AVAILABLE:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            self.driver = webdriver.Chrome(options=options)
        
        self.driver.implicitly_wait(10)
    
    def close(self):
        """Ferme le driver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def search_jobs(self, keyword: str, page: int = 1, contract_type: str = None) -> str:
        """
        Recherche des offres sur WTTJ.

        Args:
            keyword: Mot-clé de recherche
            page: Numéro de page
            contract_type: Type de contrat à filtrer (ex: "internship" pour stages)

        Returns:
            HTML de la page de résultats
        """
        # Construire l'URL de recherche
        encoded_keyword = quote(keyword)
        url = f"{BASE_URL}/fr/jobs?query={encoded_keyword}&page={page}&aroundQuery=France&refinementList%5Boffices.country_code%5D%5B%5D=FR"

        # Ajouter le filtre de type de contrat si spécifié
        # WTTJ utilise "internship" pour les stages dans l'URL
        if contract_type:
            # Mapping des types de contrat vers les valeurs WTTJ
            contract_url_mapping = {
                "stage": "internship",
                "stages": "internship",
                "internship": "internship",
                "cdi": "full_time",
                "cdd": "fixed_term",
                "alternance": "apprenticeship",
                "freelance": "freelance",
            }
            wttj_contract = contract_url_mapping.get(contract_type.lower(), contract_type)
            url += f"&refinementList%5Bcontract_type%5D%5B%5D={wttj_contract}"
        
        print(f"   🔍 {url}")
        
        if not self.driver:
            self.init_driver()
        
        self.driver.get(url)
        
        # Attendre que les offres soient chargées
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="search-results-list-item-wrapper"]'))
            )
        except TimeoutException:
            # Essayer un autre sélecteur
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'article, [role="article"], .job-card'))
                )
            except TimeoutException:
                print("      ⚠️ Timeout - pas de résultats trouvés")
        
        # Scroll pour charger plus de contenu
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        return self.driver.page_source
    
    def parse_job_list(self, html: str) -> List[Dict]:
        """
        Parse la liste des offres depuis le HTML.
        
        Args:
            html: HTML de la page de résultats
            
        Returns:
            Liste de dicts avec les infos basiques des offres
        """
        soup = BeautifulSoup(html, 'html.parser')
        jobs = []
        
        # Sélecteurs possibles pour les cartes d'offres
        selectors = [
            '[data-testid="search-results-list-item-wrapper"]',
            'article[data-testid]',
            '.ais-Hits-item',
            '[class*="JobCard"]',
            '[class*="job-card"]',
            'a[href*="/jobs/"]',
        ]
        
        job_cards = []
        for selector in selectors:
            job_cards = soup.select(selector)
            if job_cards:
                print(f"      ✅ Trouvé {len(job_cards)} offres avec sélecteur: {selector}")
                break
        
        if not job_cards:
            # Chercher tous les liens vers des offres
            all_links = soup.find_all('a', href=re.compile(r'/fr/companies/.+/jobs/.+'))
            print(f"      📎 Trouvé {len(all_links)} liens vers des offres")
            
            seen_urls = set()
            for link in all_links:
                href = link.get('href', '')
                if href and href not in seen_urls:
                    seen_urls.add(href)
                    jobs.append({
                        'url': urljoin(BASE_URL, href),
                        'titre': link.get_text(strip=True)[:100] or "Offre WTTJ"
                    })
            return jobs
        
        for card in job_cards:
            try:
                # Trouver le lien vers l'offre
                link = card.find('a', href=re.compile(r'/jobs/|/companies/.+/jobs/'))
                if not link:
                    link = card if card.name == 'a' else None
                
                if not link:
                    continue
                
                href = link.get('href', '')
                if not href:
                    continue
                
                url = urljoin(BASE_URL, href)
                
                # Extraire le titre
                title_elem = card.find(['h3', 'h4', 'h2']) or card.find(class_=re.compile(r'title|Title'))
                titre = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)[:100]
                
                # Extraire l'entreprise
                company_elem = card.find(class_=re.compile(r'company|Company|organization'))
                entreprise = company_elem.get_text(strip=True) if company_elem else None
                
                # Extraire la localisation
                location_elem = card.find(class_=re.compile(r'location|Location|city'))
                location = location_elem.get_text(strip=True) if location_elem else None
                
                # Extraire le type de contrat
                contract_elem = card.find(class_=re.compile(r'contract|Contract|type'))
                contract = contract_elem.get_text(strip=True) if contract_elem else None
                
                jobs.append({
                    'url': url,
                    'titre': titre,
                    'entreprise': entreprise,
                    'location': location,
                    'type_contrat': contract,
                })
                
            except Exception as e:
                print(f"      ⚠️ Erreur parsing carte: {e}")
                continue
        
        return jobs
    
    def get_job_details(self, url: str) -> Optional[Dict]:
        """
        Récupère les détails d'une offre.
        
        Args:
            url: URL de l'offre
            
        Returns:
            Dict avec les détails de l'offre
        """
        try:
            if not self.driver:
                self.init_driver()
            
            self.driver.get(url)
            
            # Attendre le chargement
            time.sleep(2)
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extraire les informations
            details = {
                'url': url,
                'source': 'Welcome to the Jungle',
            }
            
            # Titre
            title_elem = soup.find('h1') or soup.find('h2', class_=re.compile(r'title|Title'))
            details['titre'] = title_elem.get_text(strip=True) if title_elem else "Offre WTTJ"
            
            # Entreprise
            company_selectors = [
                '[data-testid="job-header-organization-name"]',
                'a[href*="/companies/"]',
                '[class*="company"]',
                '[class*="organization"]',
            ]
            for sel in company_selectors:
                elem = soup.select_one(sel)
                if elem:
                    details['entreprise'] = elem.get_text(strip=True)
                    break
            
            # Description
            desc_selectors = [
                '[data-testid="job-section-description"]',
                '[class*="description"]',
                '[class*="Description"]',
                'section',
            ]
            for sel in desc_selectors:
                elem = soup.select_one(sel)
                if elem and len(elem.get_text(strip=True)) > 100:
                    details['description'] = elem.get_text(separator='\n', strip=True)
                    break
            
            # Localisation
            location_selectors = [
                '[data-testid="job-header-office-name"]',
                '[class*="location"]',
                '[class*="office"]',
            ]
            for sel in location_selectors:
                elem = soup.select_one(sel)
                if elem:
                    details['location'] = elem.get_text(strip=True)
                    break
            
            # Type de contrat
            contract_selectors = [
                '[data-testid="job-header-contract"]',
                '[class*="contract"]',
                '[class*="Contract"]',
            ]
            for sel in contract_selectors:
                elem = soup.select_one(sel)
                if elem:
                    details['type_contrat'] = elem.get_text(strip=True)
                    break
            
            # Salaire
            salary_selectors = [
                '[data-testid="job-header-salary"]',
                '[class*="salary"]',
                '[class*="Salary"]',
            ]
            for sel in salary_selectors:
                elem = soup.select_one(sel)
                if elem:
                    details['salaire'] = elem.get_text(strip=True)
                    break
            
            # Expérience
            exp_selectors = [
                '[data-testid="job-header-experience"]',
                '[class*="experience"]',
                '[class*="Experience"]',
            ]
            for sel in exp_selectors:
                elem = soup.select_one(sel)
                if elem:
                    details['experience'] = elem.get_text(strip=True)
                    break
            
            # Date de publication
            date_selectors = [
                'time[datetime]',
                '[data-testid="job-header-date"]',
                '[class*="date"]',
            ]
            for sel in date_selectors:
                elem = soup.select_one(sel)
                if elem:
                    date_str = elem.get('datetime') or elem.get_text(strip=True)
                    details['date_publication'] = date_str
                    break
            
            return details
            
        except Exception as e:
            print(f"      ⚠️ Erreur détails {url}: {e}")
            return None


# Les fonctions DB (get_or_create_*, inserer_offre, offre_existe) sont
# importées depuis database.db_utils.


# =============================================================================
# FONCTIONS PRINCIPALES
# =============================================================================

def test_scraper():
    """Teste le scraper sur une recherche."""
    print("\n" + "=" * 60)
    print("TEST DU SCRAPER WELCOME TO THE JUNGLE")
    print("=" * 60)
    
    if not check_dependencies():
        return
    
    scraper = WTTJScraper(headless=True)
    
    try:
        print("\n🔍 Recherche 'data scientist'...")
        html = scraper.search_jobs("data scientist", page=1)
        
        print("\n📋 Parsing des résultats...")
        jobs = scraper.parse_job_list(html)
        
        print(f"\n✅ {len(jobs)} offres trouvées")
        
        if jobs:
            print("\n📝 Exemple d'offre:")
            for key, value in jobs[0].items():
                print(f"   {key}: {value}")
            
            # Récupérer les détails de la première offre
            if jobs[0].get('url'):
                print(f"\n🔍 Récupération des détails...")
                details = scraper.get_job_details(jobs[0]['url'])
                if details:
                    print("\n📝 Détails:")
                    for key, value in details.items():
                        if value:
                            val_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                            print(f"   {key}: {val_str}")
        
    finally:
        scraper.close()
    
    print("\n✅ Test terminé !")


def collecter_offres(max_pages: int = 10, keywords: List[str] = None, contract_type: str = None):
    """
    Collecte les offres et les insère en base.

    Args:
        max_pages: Nombre max de pages par mot-clé
        keywords: Liste de mots-clés (défaut: DATA_KEYWORDS)
        contract_type: Type de contrat à filtrer (ex: "stage" pour les stages)
    """
    print("\n" + "=" * 60)
    if contract_type:
        print(f"COLLECTE DES OFFRES WELCOME TO THE JUNGLE - {contract_type.upper()}")
    else:
        print("COLLECTE DES OFFRES WELCOME TO THE JUNGLE")
    print("=" * 60)
    
    if not check_dependencies():
        return
    
    keywords = keywords or DATA_KEYWORDS
    
    conn = get_db_connection(DB_PATH)
    id_source = get_or_create_source(conn, "Welcome to the Jungle",
                                     "https://www.welcometothejungle.com", "scraping")
    
    scraper = WTTJScraper(headless=True)
    
    total_inserees = 0
    total_doublons = 0
    
    try:
        for keyword in keywords:
            print(f"\n📊 Recherche : '{keyword}'")
            
            for page in range(1, max_pages + 1):
                print(f"   Page {page}/{max_pages}...", end=" ")
                
                try:
                    html = scraper.search_jobs(keyword, page=page, contract_type=contract_type)
                    jobs = scraper.parse_job_list(html)
                    
                    if not jobs:
                        print("Aucune offre trouvée")
                        break
                    
                    inserees = 0
                    doublons = 0
                    
                    for job in jobs:
                        # Récupérer les détails si on a une URL
                        if job.get('url'):
                            details = scraper.get_job_details(job['url'])
                            if details:
                                job.update(details)
                            time.sleep(1)  # Rate limiting
                        
                        # Insérer en base
                        if inserer_offre(conn, job, id_source):
                            inserees += 1
                        else:
                            doublons += 1
                    
                    total_inserees += inserees
                    total_doublons += doublons
                    
                    print(f"→ {inserees} nouvelles, {doublons} doublons")
                    
                    # Si moins de résultats attendus, arrêter
                    if len(jobs) < 10:
                        print("      Fin des résultats")
                        break
                    
                    time.sleep(2)  # Pause entre les pages
                    
                except Exception as e:
                    print(f"Erreur: {e}")
                    continue
        
    finally:
        scraper.close()
        conn.close()
    
    print("\n" + "=" * 60)
    print(f"✅ COLLECTE TERMINÉE")
    print(f"   {total_inserees} offres insérées")
    print(f"   {total_doublons} doublons ignorés")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Scraper Welcome to the Jungle")
    parser.add_argument("--test", action="store_true", help="Tester le scraper")
    parser.add_argument("--collect", action="store_true", help="Collecter les offres")
    parser.add_argument("--pages", type=int, default=5, help="Nombre de pages par mot-clé")
    parser.add_argument("--keywords", nargs="+", help="Mots-clés personnalisés")
    parser.add_argument("--stages", action="store_true", help="Collecter uniquement les stages")
    parser.add_argument("--contract", type=str, help="Type de contrat (stage, cdi, cdd, alternance, freelance)")

    args = parser.parse_args()

    # Déterminer le type de contrat
    contract_type = None
    if args.stages:
        contract_type = "stage"
    elif args.contract:
        contract_type = args.contract

    if args.test:
        test_scraper()
    elif args.collect:
        collecter_offres(max_pages=args.pages, keywords=args.keywords, contract_type=contract_type)
    else:
        parser.print_help()
        print("\n💡 Exemples:")
        print("   python scraper_wttj.py --test")
        print("   python scraper_wttj.py --collect --pages 3")
        print("   python scraper_wttj.py --collect --stages           # Collecter les stages")
        print("   python scraper_wttj.py --collect --stages --pages 5 # Stages sur 5 pages")
        print("   python scraper_wttj.py --collect --contract cdi     # Collecter les CDI")


if __name__ == "__main__":
    main()

```