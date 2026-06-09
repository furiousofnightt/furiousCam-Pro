@echo off
REM FuriousCam Pro — Build Script
REM Gera: dist\FuriousCam\FuriousCam.exe  (one-dir, sem exe solto na raiz do dist)

echo ============================================
echo   FuriousCam Pro - Build Script
echo ============================================
echo.

REM Verificar PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller nao encontrado. Instalando...
    pip install pyinstaller
) else (
    echo PyInstaller encontrado.
)

echo.
echo Limpando builds anteriores...
if exist "dist" (
    rmdir /s /q "dist"
    echo   dist\ removido.
)
if exist "build" (
    rmdir /s /q "build"
    echo   build\ removido.
)

echo.
echo Construindo executavel...
echo.

python -m PyInstaller furiousCam.spec --clean

if errorlevel 1 (
    echo.
    echo ============================================
    echo   ERRO: Build falhou!
    echo ============================================
    pause
    exit /b 1
)

echo.
echo Copiando arquivos externos (portables)...
xcopy /s /e /i "portables" "dist\FuriousCam\portables" >nul

echo.
echo Copiando TODAS as DLLs do Qt para raiz de _internal (resolve dependências)...
powershell -Command "Get-ChildItem 'dist\FuriousCam\_internal\PySide6' -Recurse -Filter '*.dll' | ForEach-Object { Copy-Item $_.FullName 'dist\FuriousCam\_internal\' -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo.
echo Copiando DLLs de dependências (av.libs e numpy.libs)...
powershell -Command "Get-ChildItem 'dist\FuriousCam\_internal' -Recurse -Include 'av.libs','numpy.libs' | Get-ChildItem -Recurse -Filter '*.dll' | ForEach-Object { Copy-Item $_.FullName 'dist\FuriousCam\_internal\' -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo.
if exist "build" (
    rmdir /s /q "build"
    echo   build\ removido.
)

echo.
echo ============================================
echo   Build concluido com sucesso!
echo ============================================
echo.
echo Executavel em: dist\FuriousCam\FuriousCam.exe
echo.
echo Para distribuir: compacte a pasta dist\FuriousCam\ como ZIP
echo.
pause
