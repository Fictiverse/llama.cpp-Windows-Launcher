@echo off
title Llama.cpp Launcher

REM --- 1. CREATION ENVIRONNEMENT ---
if not exist "env" (
    echo [INIT] Creation de l'environnement virtuel...
    python -m venv env
)

REM --- 2. ACTIVATION ---
call env\Scripts\activate

REM --- 3. VERIFICATION SI DEJA INSTALLE ---
if exist "env\Lib\site-packages\PyQt6\QtWidgets.pyi" (
    goto :LANCEMENT_OFFLINE
)

REM =========================================================
REM ZONE INSTALLATION (SEULEMENT LA PREMIERE FOIS)
REM =========================================================
echo.
echo [INSTALL] Premiere fois : Installation de PyQt6...
echo.

python -m pip install --upgrade pip --disable-pip-version-check
pip install PyQt6 --disable-pip-version-check

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR CRITIQUE] L'installation a echoue. 
    echo Verifiez votre connexion internet pour cette premiere installation.
    pause
    exit
)

echo [OK] Installation reussie.
echo.

:LANCEMENT_OFFLINE
set PIP_NO_INDEX=1
set PIP_DISABLE_PIP_VERSION_CHECK=1

echo [INFO] Lancement de l'interface graphique...
python run.py

pause