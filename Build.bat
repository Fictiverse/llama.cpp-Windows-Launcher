@echo off
title Creation de l'EXE - Llama Launcher

echo ==========================================
echo  ACTIVATION DE L'ENVIRONNEMENT
echo ==========================================
if not exist "env\Scripts\activate.bat" (
    echo [ERREUR] Dossier env introuvable ! Lancez d'abord launcher.bat.
    pause
    exit
)
call env\Scripts\activate

echo.
echo ==========================================
echo  VERIFICATION DE PYINSTALLER
echo ==========================================
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Installation de PyInstaller...
    pip install pyinstaller --disable-pip-version-check
) else (
    echo [OK] PyInstaller est deja installe dans l'environnement virtuel.
)

echo.
echo ==========================================
echo  PREPARATION DE L'ICONE
echo ==========================================
set "ICON_ARG="
if exist "logo.ico" (
    echo [OK] "logo.ico" detecte a la racine. Il sera utilise comme icone de l'EXE.
    set "ICON_ARG=--icon=logo.ico"
) else (
    echo [ATTENTION] Aucun fichier "logo.ico" trouve a la racine.
    echo L'executable sera genere avec l'icone systeme Windows par defaut.
)

echo.
echo ==========================================
echo  COMPILATION EN COURS...
echo ==========================================
REM --clean : nettoie les caches precedents
REM --noconsole : supprime l'affichage de la console noire en arriere-plan
REM --onefile : package l'application dans un unique fichier .exe
REM --collect-data PyQt6 : securise l'inclusion des dependances de PyQt6
pyinstaller --noconsole --onefile --clean --collect-data PyQt6 %ICON_ARG% --name "LlamaLauncher" run.py

echo.
echo ==========================================
echo  NETTOYAGE ET FINALISATION
echo ==========================================
if exist "build" rmdir /s /q build
if exist "LlamaLauncher.spec" del /q LlamaLauncher.spec

echo.
echo ========================================================
echo  TERMINE !
echo ========================================================
echo.
echo Votre executable "LlamaLauncher.exe" est disponible dans le dossier "dist".
echo.
pause