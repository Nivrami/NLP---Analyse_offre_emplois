

# Image de base : Python 3.11 (version légère)
FROM python:3.11-slim

# Métadonnées
LABEL maintainer="Projet NLP - Master Data Science"
LABEL description="Application d'analyse des offres d'emploi Data/IA en France"

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Répertoire de travail dans le container
WORKDIR /app

# Copier le fichier des dépendances d'abord (pour le cache Docker)
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier tout le code de l'application
COPY app.py .
COPY data/ ./data/

# Exposer le port de Streamlit
EXPOSE 8501

# Configuration Streamlit pour Docker
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Commande pour lancer l'application
CMD ["streamlit", "run", "app.py"]
