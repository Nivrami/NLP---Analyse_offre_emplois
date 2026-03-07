@echo off
REM =============================================================================
REM Script d'aide Docker - Application Offres Data/IA
REM =============================================================================

echo.
echo ============================================================
echo    DOCKER - Application Offres Data/IA
echo ============================================================
echo.

if "%1"=="build" goto build
if "%1"=="run" goto run
if "%1"=="stop" goto stop
if "%1"=="clean" goto clean
if "%1"=="logs" goto logs
goto help

:build
echo [BUILD] Construction de l'image Docker...
docker build -t offres-data-ia .
echo.
echo Image construite avec succes !
goto end

:run
echo [RUN] Lancement du container...
docker run -d -p 8501:8501 --name offres-app offres-data-ia
echo.
echo Application lancee !
echo Ouvre ton navigateur : http://localhost:8501
goto end

:stop
echo [STOP] Arret du container...
docker stop offres-app
docker rm offres-app
echo Container arrete.
goto end

:clean
echo [CLEAN] Nettoyage des images et containers...
docker stop offres-app 2>nul
docker rm offres-app 2>nul
docker rmi offres-data-ia 2>nul
echo Nettoyage termine.
goto end

:logs
echo [LOGS] Affichage des logs...
docker logs -f offres-app
goto end

:help
echo Utilisation : docker-helper.bat [commande]
echo.
echo Commandes disponibles :
echo   build   - Construit l'image Docker
echo   run     - Lance le container
echo   stop    - Arrete le container
echo   clean   - Supprime l'image et le container
echo   logs    - Affiche les logs du container
echo.
echo Exemple :
echo   docker-helper.bat build
echo   docker-helper.bat run
echo.
goto end

:end
