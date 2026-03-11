# 💻 Script : enrichissement.py

**Source :** `enrichissement.py`

```python
"""
Script d'enrichissement des donnees
====================================
Trois modules d'enrichissement independants :

1. Regions    : Complete le mapping departement -> region pour les lieux sans region
2. Salaires   : Parse les textes de salaire pour en extraire les valeurs numeriques
3. Competences: Extrait les competences techniques depuis les descriptions d'offres
                via dictionnaire (rapide) ou LLM local Ollama (plus intelligent)

Usage:
    python enrichissement.py --all
    python enrichissement.py --regions
    python enrichissement.py --salaires
    python enrichissement.py --competences --methode dictionnaire
    python enrichissement.py --competences --methode ollama --model mistral
    python enrichissement.py --competences --methode ollama --limit 50
    python enrichissement.py --competences --compare
    python enrichissement.py --competences --reset
    python enrichissement.py --check-ollama
"""

import sqlite3
import re
import argparse
from collections import Counter
from typing import Optional, Tuple, List, Dict, Set

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

DB_PATH = "data/offres_emploi.db"
OLLAMA_URL = "http://localhost:11434/api/generate"


# =============================================================================
# MODULE 1 : MAPPING DEPARTEMENT -> REGION
# =============================================================================

DEPARTEMENT_TO_REGION = {
    # Auvergne-Rhone-Alpes (84)
    "01": ("84", "Auvergne-Rhone-Alpes"),
    "03": ("84", "Auvergne-Rhone-Alpes"),
    "07": ("84", "Auvergne-Rhone-Alpes"),
    "15": ("84", "Auvergne-Rhone-Alpes"),
    "26": ("84", "Auvergne-Rhone-Alpes"),
    "38": ("84", "Auvergne-Rhone-Alpes"),
    "42": ("84", "Auvergne-Rhone-Alpes"),
    "43": ("84", "Auvergne-Rhone-Alpes"),
    "63": ("84", "Auvergne-Rhone-Alpes"),
    "69": ("84", "Auvergne-Rhone-Alpes"),
    "73": ("84", "Auvergne-Rhone-Alpes"),
    "74": ("84", "Auvergne-Rhone-Alpes"),
    # Bourgogne-Franche-Comte (27)
    "21": ("27", "Bourgogne-Franche-Comte"),
    "25": ("27", "Bourgogne-Franche-Comte"),
    "39": ("27", "Bourgogne-Franche-Comte"),
    "58": ("27", "Bourgogne-Franche-Comte"),
    "70": ("27", "Bourgogne-Franche-Comte"),
    "71": ("27", "Bourgogne-Franche-Comte"),
    "89": ("27", "Bourgogne-Franche-Comte"),
    "90": ("27", "Bourgogne-Franche-Comte"),
    # Bretagne (53)
    "22": ("53", "Bretagne"),
    "29": ("53", "Bretagne"),
    "35": ("53", "Bretagne"),
    "56": ("53", "Bretagne"),
    # Centre-Val de Loire (24)
    "18": ("24", "Centre-Val de Loire"),
    "28": ("24", "Centre-Val de Loire"),
    "36": ("24", "Centre-Val de Loire"),
    "37": ("24", "Centre-Val de Loire"),
    "41": ("24", "Centre-Val de Loire"),
    "45": ("24", "Centre-Val de Loire"),
    # Corse (94)
    "2A": ("94", "Corse"),
    "2B": ("94", "Corse"),
    "20": ("94", "Corse"),
    # Grand Est (44)
    "08": ("44", "Grand Est"),
    "10": ("44", "Grand Est"),
    "51": ("44", "Grand Est"),
    "52": ("44", "Grand Est"),
    "54": ("44", "Grand Est"),
    "55": ("44", "Grand Est"),
    "57": ("44", "Grand Est"),
    "67": ("44", "Grand Est"),
    "68": ("44", "Grand Est"),
    "88": ("44", "Grand Est"),
    # Hauts-de-France (32)
    "02": ("32", "Hauts-de-France"),
    "59": ("32", "Hauts-de-France"),
    "60": ("32", "Hauts-de-France"),
    "62": ("32", "Hauts-de-France"),
    "80": ("32", "Hauts-de-France"),
    # Ile-de-France (11)
    "75": ("11", "Ile-de-France"),
    "77": ("11", "Ile-de-France"),
    "78": ("11", "Ile-de-France"),
    "91": ("11", "Ile-de-France"),
    "92": ("11", "Ile-de-France"),
    "93": ("11", "Ile-de-France"),
    "94": ("11", "Ile-de-France"),
    "95": ("11", "Ile-de-France"),
    # Normandie (28)
    "14": ("28", "Normandie"),
    "27": ("28", "Normandie"),
    "50": ("28", "Normandie"),
    "61": ("28", "Normandie"),
    "76": ("28", "Normandie"),
    # Nouvelle-Aquitaine (75)
    "16": ("75", "Nouvelle-Aquitaine"),
    "17": ("75", "Nouvelle-Aquitaine"),
    "19": ("75", "Nouvelle-Aquitaine"),
    "23": ("75", "Nouvelle-Aquitaine"),
    "24": ("75", "Nouvelle-Aquitaine"),
    "33": ("75", "Nouvelle-Aquitaine"),
    "40": ("75", "Nouvelle-Aquitaine"),
    "47": ("75", "Nouvelle-Aquitaine"),
    "64": ("75", "Nouvelle-Aquitaine"),
    "79": ("75", "Nouvelle-Aquitaine"),
    "86": ("75", "Nouvelle-Aquitaine"),
    "87": ("75", "Nouvelle-Aquitaine"),
    # Occitanie (76)
    "09": ("76", "Occitanie"),
    "11": ("76", "Occitanie"),
    "12": ("76", "Occitanie"),
    "30": ("76", "Occitanie"),
    "31": ("76", "Occitanie"),
    "32": ("76", "Occitanie"),
    "34": ("76", "Occitanie"),
    "46": ("76", "Occitanie"),
    "48": ("76", "Occitanie"),
    "65": ("76", "Occitanie"),
    "66": ("76", "Occitanie"),
    "81": ("76", "Occitanie"),
    "82": ("76", "Occitanie"),
    # Pays de la Loire (52)
    "44": ("52", "Pays de la Loire"),
    "49": ("52", "Pays de la Loire"),
    "53": ("52", "Pays de la Loire"),
    "72": ("52", "Pays de la Loire"),
    "85": ("52", "Pays de la Loire"),
    # Provence-Alpes-Cote d'Azur (93)
    "04": ("93", "Provence-Alpes-Cote d'Azur"),
    "05": ("93", "Provence-Alpes-Cote d'Azur"),
    "06": ("93", "Provence-Alpes-Cote d'Azur"),
    "13": ("93", "Provence-Alpes-Cote d'Azur"),
    "83": ("93", "Provence-Alpes-Cote d'Azur"),
    "84": ("93", "Provence-Alpes-Cote d'Azur"),
    # DOM-TOM
    "971": ("01", "Guadeloupe"),
    "972": ("02", "Martinique"),
    "973": ("03", "Guyane"),
    "974": ("04", "La Reunion"),
    "976": ("06", "Mayotte"),
}


def enrichir_regions(conn: sqlite3.Connection) -> int:
    """Complete les regions manquantes dans dim_lieu a partir du code departement."""
    print("\n" + "=" * 60)
    print("ENRICHISSEMENT DES REGIONS")
    print("=" * 60)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_lieu, code_departement, commune
        FROM dim_lieu
        WHERE (region IS NULL OR region = '')
        AND code_departement IS NOT NULL
    """)
    lieux_sans_region = cursor.fetchall()
    print(f"\n{len(lieux_sans_region)} lieux sans region a traiter")

    updated = 0
    not_found = []

    for id_lieu, code_dept, commune in lieux_sans_region:
        region_info = (
            DEPARTEMENT_TO_REGION.get(code_dept)
            or DEPARTEMENT_TO_REGION.get(code_dept.lstrip("0") if code_dept else "")
            or DEPARTEMENT_TO_REGION.get(code_dept.zfill(2) if code_dept else "")
        )
        if region_info:
            code_region, nom_region = region_info
            cursor.execute(
                "UPDATE dim_lieu SET code_region = ?, region = ? WHERE id_lieu = ?",
                (code_region, nom_region, id_lieu),
            )
            updated += 1
        else:
            not_found.append((code_dept, commune))

    conn.commit()
    print(f"OK : {updated} lieux mis a jour")

    if not_found:
        dept_counts = Counter(d[0] for d in not_found)
        print(f"\nAttention : {len(not_found)} departements non trouves dans le mapping :")
        for dept, count in dept_counts.most_common(10):
            print(f"   - Departement '{dept}' : {count} lieux")

    cursor.execute("""
        SELECT COUNT(*) FROM fait_offres f
        LEFT JOIN dim_lieu l ON f.id_lieu = l.id_lieu
        WHERE l.region IS NULL OR f.id_lieu IS NULL
    """)
    print(f"\nOffres encore sans region : {cursor.fetchone()[0]}")
    return updated


# =============================================================================
# MODULE 2 : PARSING DES SALAIRES
# =============================================================================

def _parse_salaire(texte: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Parse un texte de salaire et retourne (min, max, periode).
    periode : 'annuel' | 'mensuel' | 'horaire' | None
    """
    if not texte:
        return None, None, None

    texte_lower = texte.lower()

    if any(k in texte_lower for k in ("annuel", "/an", " an")):
        periode = "annuel"
    elif any(k in texte_lower for k in ("mensuel", "/mois", "mois")):
        periode = "mensuel"
    elif any(k in texte_lower for k in ("horaire", "/h", "heure")):
        periode = "horaire"
    else:
        periode = None

    nombres = re.findall(r"(\d[\d\s]*[\.,]?\d*)", texte_lower)
    valeurs = []
    for n in nombres:
        try:
            val = float(n.replace(" ", "").replace(",", "."))
            if 5 < val < 500_000:
                valeurs.append(val)
        except ValueError:
            continue

    if not valeurs:
        return None, None, periode
    if len(valeurs) == 1:
        return valeurs[0], valeurs[0], periode
    return min(valeurs), max(valeurs), periode


def enrichir_salaires(conn: sqlite3.Connection) -> int:
    """Parse les salaires textuels et met a jour les colonnes salaire_min / salaire_max."""
    print("\n" + "=" * 60)
    print("PARSING DES SALAIRES")
    print("=" * 60)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_offre, salaire_commentaire
        FROM fait_offres
        WHERE salaire_commentaire IS NOT NULL AND salaire_commentaire != ''
    """)
    offres = cursor.fetchall()
    print(f"\n{len(offres)} offres avec information salaire")

    updated = 0
    stats: Dict[str, int] = {"annuel": 0, "mensuel": 0, "horaire": 0, "inconnu": 0}

    for id_offre, texte in offres:
        sal_min, sal_max, periode = _parse_salaire(texte)
        if sal_min is None:
            continue

        # Ramener tout en annuel brut
        if periode == "mensuel":
            sal_min *= 12
            sal_max = sal_max * 12 if sal_max else None
        elif periode == "horaire":
            sal_min *= 35 * 52
            sal_max = sal_max * 35 * 52 if sal_max else None

        cursor.execute(
            "UPDATE fait_offres SET salaire_min = ?, salaire_max = ? WHERE id_offre = ?",
            (sal_min, sal_max, id_offre),
        )
        updated += 1
        stats[periode or "inconnu"] += 1

    conn.commit()
    print(f"OK : {updated} salaires convertis en annuel")
    for periode, count in stats.items():
        if count:
            print(f"   - {periode} : {count}")

    cursor.execute("""
        SELECT COUNT(*), AVG(salaire_min), AVG(salaire_max), MIN(salaire_min), MAX(salaire_max)
        FROM fait_offres WHERE salaire_min IS NOT NULL
    """)
    row = cursor.fetchone()
    if row and row[0]:
        print(f"\nStatistiques salaires (annuel brut) :")
        print(f"   Offres avec salaire : {row[0]}")
        print(f"   Moyenne min / max   : {row[1]:,.0f} / {row[2]:,.0f} EUR")
        print(f"   Etendue             : {row[3]:,.0f} - {row[4]:,.0f} EUR")

    return updated


# =============================================================================
# MODULE 3 : EXTRACTION DE COMPETENCES
# =============================================================================

# Dictionnaire de competences techniques (patterns -> libelle normalise).
# Les patterns sont appliques en minuscules sur titre + description.
# Ordre des categories : langages, frameworks ML/DL, big data, bases de donnees,
# cloud, devops/mlops, visualisation, outils, concepts, methodologies, architecture.
COMPETENCES_TECHNIQUES = {
    # --- Langages ---
    "python": "Python",
    "pandas": "Python",
    "numpy": "Python",
    "matplotlib": "Python",
    "seaborn": "Python",
    "fastapi": "Python",
    "flask": "Python",
    "django": "Python",
    # R : patterns stricts pour eviter les faux positifs (ex: "travailleR")
    "rstudio": "R",
    "r studio": "R",
    "tidyverse": "R",
    "ggplot": "R",
    "dplyr": "R",
    "shiny": "R (Shiny)",
    "cran": "R",
    "langage r": "R",
    "programmation r": "R",
    "logiciel r": "R",
    "environnement r": "R",
    " r et python": "R",
    "python et r": "R",
    "r/python": "R",
    "python/r": "R",
    # SQL
    "sql": "SQL",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "plsql": "PL/SQL",
    "pl/sql": "PL/SQL",
    "t-sql": "T-SQL",
    "tsql": "T-SQL",
    # Autres langages
    "java ": "Java", "java,": "Java", "java.": "Java",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "scala": "Scala",
    "c++": "C++",
    "c#": "C#",
    "golang": "Go",
    "rust": "Rust",
    "julia": "Julia",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "perl": "Perl",
    "ruby": "Ruby",
    "php": "PHP",
    "bash": "Bash/Shell",
    "shell": "Bash/Shell",
    "powershell": "PowerShell",
    # --- Frameworks ML/DL ---
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "keras": "Keras",
    "scikit-learn": "Scikit-learn",
    "scikit learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
    "prophet": "Prophet",
    "statsmodels": "Statsmodels",
    "spacy": "spaCy",
    "nltk": "NLTK",
    "gensim": "Gensim",
    "opencv": "OpenCV",
    "hugging face": "Hugging Face",
    "huggingface": "Hugging Face",
    "transformers": "Transformers",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    # --- Big Data ---
    "spark": "Apache Spark",
    "pyspark": "PySpark",
    "hadoop": "Hadoop",
    "hive": "Hive",
    "presto": "Presto",
    "trino": "Trino",
    "kafka": "Kafka",
    "airflow": "Apache Airflow",
    "luigi": "Luigi",
    "prefect": "Prefect",
    "dagster": "Dagster",
    "dbt": "dbt",
    "databricks": "Databricks",
    "snowflake": "Snowflake",
    "redshift": "AWS Redshift",
    "bigquery": "BigQuery",
    "synapse": "Azure Synapse",
    "fivetran": "Fivetran",
    "airbyte": "Airbyte",
    "apache nifi": "Apache NiFi",
    " nifi ": "Apache NiFi", " nifi,": "Apache NiFi",
    "flink": "Apache Flink",
    # --- Bases de donnees ---
    "mongodb": "MongoDB",
    "cassandra": "Cassandra",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "opensearch": "OpenSearch",
    "neo4j": "Neo4j",
    "dynamodb": "DynamoDB",
    "cosmos db": "Cosmos DB",
    "cosmosdb": "Cosmos DB",
    "oracle": "Oracle DB",
    "sql server": "SQL Server",
    "sqlite": "SQLite",
    "mariadb": "MariaDB",
    "clickhouse": "ClickHouse",
    "timescaledb": "TimescaleDB",
    "influxdb": "InfluxDB",
    # --- Cloud ---
    "aws": "AWS",
    "amazon web services": "AWS",
    "s3": "AWS S3",
    "ec2": "AWS EC2",
    "lambda": "AWS Lambda",
    "sagemaker": "AWS SageMaker",
    "glue": "AWS Glue",
    "emr": "AWS EMR",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "azure ml": "Azure ML",
    "gcp": "Google Cloud",
    "google cloud": "Google Cloud",
    "vertex ai": "Vertex AI",
    "cloud functions": "Cloud Functions",
    "dataflow": "Dataflow",
    "dataproc": "Dataproc",
    # --- DevOps / MLOps ---
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "helm": "Helm",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "gitlab ci": "GitLab CI/CD",
    "github actions": "GitHub Actions",
    "circleci": "CircleCI",
    "mlflow": "MLflow",
    "kubeflow": "Kubeflow",
    "mlops": "MLOps",
    "feast": "Feast",
    "seldon": "Seldon",
    "bentoml": "BentoML",
    "weights & biases": "Weights & Biases",
    "wandb": "Weights & Biases",
    "neptune": "Neptune.ai",
    "dvc": "DVC",
    # --- Visualisation / BI ---
    "tableau": "Tableau",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "looker": "Looker",
    "qlik": "Qlik",
    "qliksense": "Qlik Sense",
    "metabase": "Metabase",
    "superset": "Apache Superset",
    "grafana": "Grafana",
    "kibana": "Kibana",
    "plotly": "Plotly",
    "dash": "Dash",
    "streamlit": "Streamlit",
    "bokeh": "Bokeh",
    "d3.js": "D3.js",
    "d3js": "D3.js",
    # --- Outils ---
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "bitbucket": "Bitbucket",
    "jira": "Jira",
    "confluence": "Confluence",
    "notion": "Notion",
    "jupyter": "Jupyter",
    "notebook": "Jupyter Notebook",
    "vscode": "VS Code",
    "pycharm": "PyCharm",
    "excel": "Excel",
    "vba": "VBA",
    "sas": "SAS",
    "spss": "SPSS",
    "stata": "Stata",
    "matlab": "MATLAB",
    "alteryx": "Alteryx",
    "talend": "Talend",
    "informatica": "Informatica",
    " ssis": "SSIS", "ssis ": "SSIS", "(ssis)": "SSIS",
    "sql server integration": "SSIS",
    # --- Concepts ML/NLP/IA ---
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "reinforcement learning": "Reinforcement Learning",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "traitement du langage": "NLP",
    "computer vision": "Computer Vision",
    "vision par ordinateur": "Computer Vision",
    "time series": "Series temporelles",
    "series temporelles": "Series temporelles",
    "forecasting": "Prevision/Forecasting",
    "prevision": "Prevision/Forecasting",
    "regression": "Regression",
    "classification": "Classification",
    "clustering": "Clustering",
    "segmentation": "Segmentation",
    "recommendation": "Systemes de recommandation",
    "recommandation": "Systemes de recommandation",
    "neural network": "Reseaux de neurones",
    "reseau de neurones": "Reseaux de neurones",
    "cnn": "CNN",
    "rnn": "RNN",
    "lstm": "LSTM",
    "transformer": "Transformers",
    "attention mechanism": "Mecanisme d'attention",
    "generative ai": "IA Generative",
    "ia generative": "IA Generative",
    "llm": "LLM",
    "large language model": "LLM",
    "gpt": "GPT/LLM",
    "chatgpt": "ChatGPT/LLM",
    "bert": "BERT",
    " rag ": "RAG", "(rag)": "RAG", "rag/": "RAG", "/rag": "RAG",
    "retrieval augmented": "RAG",
    "retrieval-augmented": "RAG",
    "fine-tuning": "Fine-tuning",
    "prompt engineering": "Prompt Engineering",
    "data mining": "Data Mining",
    "text mining": "Text Mining",
    "web scraping": "Web Scraping",
    "scraping": "Web Scraping",
    "etl": "ETL",
    "elt": "ELT",
    "data pipeline": "Data Pipeline",
    "data warehouse": "Data Warehouse",
    "data lake": "Data Lake",
    "data mesh": "Data Mesh",
    "feature engineering": "Feature Engineering",
    "feature store": "Feature Store",
    "a/b test": "A/B Testing",
    "ab test": "A/B Testing",
    "test a/b": "A/B Testing",
    "statistiques": "Statistiques",
    "statistics": "Statistiques",
    "probabilites": "Probabilites",
    "probability": "Probabilites",
    "bayesian": "Statistiques bayesiennes",
    "bayesien": "Statistiques bayesiennes",
    # --- Methodologies ---
    "agile": "Methodologie Agile",
    "scrum": "Scrum",
    "kanban": "Kanban",
    "devops": "DevOps",
    "ci/cd": "CI/CD",
    "ci cd": "CI/CD",
    "continuous integration": "CI/CD",
    "integration continue": "CI/CD",
    "tdd": "TDD",
    "test driven": "TDD",
    # --- Architecture ---
    "api rest": "API REST",
    "restful": "API REST",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "microservices": "Microservices",
    "micro-services": "Microservices",
    "serverless": "Serverless",
    "event-driven": "Event-Driven",
    "message queue": "Message Queue",
    "rabbitmq": "RabbitMQ",
    "celery": "Celery",
}


def _extraire_par_dictionnaire(texte: str) -> Set[str]:
    """Extrait les competences par matching de patterns dans le dictionnaire."""
    if not texte:
        return set()
    texte_lower = texte.lower()
    return {libelle for pattern, libelle in COMPETENCES_TECHNIQUES.items() if pattern in texte_lower}


# --- Ollama ---

_OLLAMA_PROMPT = """Tu es un expert en recrutement IT et Data Science.
Analyse cette offre d'emploi et extrais UNIQUEMENT les competences techniques mentionnees.

TITRE: {titre}

DESCRIPTION:
{description}

REGLES IMPORTANTES:
- Liste uniquement les competences EXPLICITEMENT mentionnees
- Distingue bien le langage "R" de la simple lettre R
- Normalise les noms (ex: "Py" -> "Python")
- Ignore les soft skills
- Une competence par ligne, sans tirets ni numerotation

COMPETENCES TECHNIQUES TROUVEES:"""


def verifier_ollama() -> bool:
    """Retourne True si Ollama est accessible."""
    if not REQUESTS_AVAILABLE:
        return False
    try:
        return requests.get("http://localhost:11434/api/tags", timeout=5).status_code == 200
    except Exception:
        return False


def lister_modeles_ollama() -> List[str]:
    """Retourne la liste des modeles installes dans Ollama."""
    try:
        data = requests.get("http://localhost:11434/api/tags", timeout=5).json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _extraire_par_ollama(titre: str, description: str, model: str = "mistral") -> Set[str]:
    """Extrait les competences via un LLM local Ollama."""
    if not titre and not description:
        return set()

    prompt = _OLLAMA_PROMPT.format(
        titre=titre or "Non specifie",
        description=(description or "")[:3000],
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.1, "num_predict": 500}},
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"      Erreur Ollama : {resp.status_code}")
            return set()

        competences = set()
        for line in resp.json().get("response", "").strip().split("\n"):
            line = re.sub(r"^[-*\d.)\s]+", "", line).strip()
            if 1 < len(line) < 50:
                competences.add(line)
        return competences

    except requests.exceptions.Timeout:
        print("      Timeout Ollama")
        return set()
    except Exception as e:
        print(f"      Erreur : {e}")
        return set()


# --- Persistence ---

def _reset_competences_nlp(conn: sqlite3.Connection):
    """Supprime toutes les competences inserees par NLP/LLM."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM offre_competence WHERE exigence LIKE 'NLP%' OR exigence LIKE 'LLM%'")
    nb_assoc = cursor.rowcount
    cursor.execute(
        "DELETE FROM dim_competence WHERE code_competence LIKE 'NLP_%' OR code_competence LIKE 'LLM_%'"
    )
    conn.commit()
    print(f"OK : {nb_assoc} associations et {cursor.rowcount} competences supprimees")


def _sauvegarder_competences(
    conn: sqlite3.Connection, id_offre: int, competences: Set[str], source: str
) -> int:
    """Insere les competences et leurs liens offre <-> competence."""
    cursor = conn.cursor()
    count = 0
    for comp in competences:
        cursor.execute(
            "SELECT id_competence FROM dim_competence WHERE libelle_competence = ?", (comp,)
        )
        row = cursor.fetchone()
        if row:
            id_comp = row[0]
        else:
            code = f"{source}_{comp.replace(' ', '_').upper()[:20]}"
            cursor.execute(
                "INSERT INTO dim_competence (code_competence, libelle_competence, type_competence) VALUES (?, ?, ?)",
                (code, comp, "technique"),
            )
            id_comp = cursor.lastrowid

        try:
            cursor.execute(
                "INSERT OR IGNORE INTO offre_competence (id_offre, id_competence, exigence) VALUES (?, ?, ?)",
                (id_offre, id_comp, source),
            )
            count += cursor.rowcount
        except sqlite3.IntegrityError:
            pass
    return count


# --- Enrichissement competences ---

def enrichir_competences(
    conn: sqlite3.Connection,
    methode: str = "dictionnaire",
    model: str = "mistral",
    limit: Optional[int] = None,
    reset: bool = False,
) -> int:
    """
    Extrait et sauvegarde les competences techniques des offres.

    Args:
        methode  : 'dictionnaire' ou 'ollama'
        model    : modele Ollama (ex: 'mistral', 'llama3')
        limit    : nombre max d'offres a traiter (None = toutes)
        reset    : si True, supprime d'abord les competences NLP existantes
    """
    if methode == "ollama":
        if not verifier_ollama():
            print("\nOllama n'est pas disponible.")
            print("  1. Installe Ollama : https://ollama.ai")
            print("  2. Lance : ollama serve")
            print(f"  3. Telecharge un modele : ollama pull {model}")
            return 0
        modeles = lister_modeles_ollama()
        print(f"Modeles disponibles : {', '.join(modeles) or 'aucun'}")
        if model not in [m.split(":")[0] for m in modeles]:
            print(f"Le modele '{model}' n'est pas installe. Lance : ollama pull {model}")
            return 0

    print("\n" + "=" * 60)
    label = "DICTIONNAIRE" if methode == "dictionnaire" else f"LLM OLLAMA ({model})"
    print(f"EXTRACTION DE COMPETENCES - {label}")
    print("=" * 60)

    if reset:
        print("\nReinitialisation des competences NLP existantes...")
        _reset_competences_nlp(conn)

    cursor = conn.cursor()
    query = "SELECT id_offre, titre, description FROM fait_offres WHERE description IS NOT NULL"
    if limit:
        query += f" LIMIT {limit}"
    cursor.execute(query)
    offres = cursor.fetchall()
    print(f"\nAnalyse de {len(offres)} offres...")

    total = 0
    competences_count: Counter = Counter()
    source_tag = "NLP_DICT" if methode == "dictionnaire" else "LLM_OLLAMA"

    for i, (id_offre, titre, description) in enumerate(offres):
        if methode == "dictionnaire":
            texte = f"{titre or ''} {description or ''}"
            competences = _extraire_par_dictionnaire(texte)
        else:
            print(f"   [{i+1}/{len(offres)}] {(titre or '')[:50]}", end="  ", flush=True)
            competences = _extraire_par_ollama(titre, description, model)
            print(f"-> {len(competences)} competences")

        if competences:
            nb = _sauvegarder_competences(conn, id_offre, competences, source_tag)
            total += nb
            for c in competences:
                competences_count[c] += 1

        if methode == "ollama":
            conn.commit()  # commit incremental pour Ollama (long a executer)

    conn.commit()

    print(f"\nOK : {total} associations creees")
    print("\nTop 20 competences detectees :")
    for comp, count in competences_count.most_common(20):
        print(f"   - {comp} : {count} offres")

    if methode == "dictionnaire":
        r = competences_count.get("R", 0)
        py = competences_count.get("Python", 0)
        print(f"\nVerification R ({r}) vs Python ({py}) :", end=" ")
        print("ratio OK" if r <= py * 2 else "R semble sur-represente, verifier les patterns")

    return total


def comparer_approches(conn: sqlite3.Connection, model: str = "mistral", limit: int = 10):
    """Compare l'approche dictionnaire et Ollama sur un echantillon d'offres."""
    if not verifier_ollama():
        print("Ollama n'est pas disponible pour la comparaison.")
        return

    print("\n" + "=" * 60)
    print("COMPARAISON : DICTIONNAIRE vs OLLAMA")
    print("=" * 60)

    cursor = conn.cursor()
    cursor.execute(
        f"SELECT id_offre, titre, description FROM fait_offres WHERE description IS NOT NULL LIMIT {limit}"
    )
    offres = cursor.fetchall()
    print(f"\nComparaison sur {len(offres)} offres...\n")

    for _, titre, description in offres:
        texte = f"{titre or ''} {description or ''}"
        comp_dict = _extraire_par_dictionnaire(texte)
        comp_ollama = _extraire_par_ollama(titre, description, model)

        print(f"  {(titre or '')[:60]}")
        print(f"   Dictionnaire ({len(comp_dict)}) : {', '.join(sorted(comp_dict)[:8])}")
        print(f"   Ollama       ({len(comp_ollama)}) : {', '.join(sorted(comp_ollama)[:8])}")
        only_dict = comp_dict - comp_ollama
        only_ollama = comp_ollama - comp_dict
        if only_dict:
            print(f"   Uniquement dico  : {', '.join(list(only_dict)[:5])}")
        if only_ollama:
            print(f"   Uniquement Ollama: {', '.join(list(only_ollama)[:5])}")
        print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Enrichissement des donnees : regions, salaires, competences"
    )

    parser.add_argument("--all", action="store_true",
                        help="Executer regions + salaires + competences (dictionnaire)")
    parser.add_argument("--regions", action="store_true",
                        help="Completer le mapping departement -> region")
    parser.add_argument("--salaires", action="store_true",
                        help="Parser les salaires en valeurs numeriques")
    parser.add_argument("--competences", action="store_true",
                        help="Extraire les competences depuis les descriptions")
    parser.add_argument("--methode", choices=["dictionnaire", "ollama"], default="dictionnaire",
                        help="Methode d'extraction des competences (defaut: dictionnaire)")
    parser.add_argument("--model", default="mistral",
                        help="Modele Ollama a utiliser (defaut: mistral)")
    parser.add_argument("--limit", type=int,
                        help="Nombre max d'offres a traiter pour les competences")
    parser.add_argument("--reset", action="store_true",
                        help="Reinitialiser les competences NLP avant extraction")
    parser.add_argument("--compare", action="store_true",
                        help="Comparer dictionnaire et Ollama sur un echantillon")
    parser.add_argument("--check-ollama", action="store_true",
                        help="Verifier si Ollama est disponible")

    args = parser.parse_args()

    # Verification Ollama standalone
    if args.check_ollama:
        if verifier_ollama():
            modeles = lister_modeles_ollama()
            print(f"Ollama est disponible. Modeles installes : {', '.join(modeles) or 'aucun'}")
            if not modeles:
                print("Installe un modele avec : ollama pull mistral")
        else:
            print("Ollama n'est pas disponible.")
            print("  1. Telecharge depuis https://ollama.ai")
            print("  2. Lance : ollama serve")
            print("  3. Installe un modele : ollama pull mistral")
        return

    if not any([args.all, args.regions, args.salaires, args.competences, args.compare, args.reset]):
        parser.print_help()
        return

    conn = sqlite3.connect(DB_PATH)

    if args.all or args.regions:
        enrichir_regions(conn)

    if args.all or args.salaires:
        enrichir_salaires(conn)

    if args.all:
        enrichir_competences(conn, methode="dictionnaire", reset=args.reset)
    elif args.competences:
        enrichir_competences(
            conn,
            methode=args.methode,
            model=args.model,
            limit=args.limit,
            reset=args.reset,
        )

    if args.compare:
        comparer_approches(conn, model=args.model)

    if args.reset and not (args.competences or args.all):
        print("\nReinitialisation des competences NLP...")
        _reset_competences_nlp(conn)

    conn.close()
    print("\n" + "=" * 60)
    print("ENRICHISSEMENT TERMINE")
    print("=" * 60)


if __name__ == "__main__":
    main()

```