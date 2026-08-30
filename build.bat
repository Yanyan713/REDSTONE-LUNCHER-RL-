@echo off
chcp 65001 >nul
echo ========================================
echo   Redstone Launcher - Build .exe
echo ========================================
echo.

cd /d "%~dp0"

echo Nettoyage des anciens builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist RedstoneLauncher.spec del /q RedstoneLauncher.spec

echo.
echo Lancement de PyInstaller...
echo.

pyinstaller ^
  --onefile ^
  --name "RedstoneLauncher" ^
  --add-data "web;web" ^
  --add-data "LICENSE;." ^
  --add-data "README.md;." ^
  --hidden-import "launcher" ^
  --hidden-import "launcher.server" ^
  --hidden-import "launcher.paths" ^
  --hidden-import "launcher.state" ^
  --hidden-import "launcher.versions" ^
  --hidden-import "launcher.download" ^
  --hidden-import "launcher.java" ^
  --hidden-import "launcher.launch" ^
  --hidden-import "launcher.auth" ^
  --hidden-import "launcher.fabric" ^
  --hidden-import "launcher.mods" ^
  --hidden-import "launcher.shaders_pack" ^
  --hidden-import "launcher.skins" ^
  --hidden-import "launcher.bedrock" ^
  --collect-submodules "launcher" ^
  run.py

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [ERREUR] Echec du build.
  pause
  exit /b 1
)

echo.
echo ========================================
echo   Build reussi !
echo ========================================
echo.
echo Fichier : dist\RedstoneLauncher.exe
echo.
echo Copie vers la racine...
copy /y "dist\RedstoneLauncher.exe" "RedstoneLauncher.exe" >nul
echo.
echo Termine. Double-clique sur RedstoneLauncher.exe pour lancer le jeu.
echo.
pause
