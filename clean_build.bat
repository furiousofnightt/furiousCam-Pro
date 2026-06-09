@echo off
REM Clean old builds before running new build

echo Limpando builds anteriores...

if exist "build" (
    echo Deletando: build\
    rmdir /s /q "build"
)

if exist "dist" (
    echo Deletando: dist\
    rmdir /s /q "dist"
)

if exist ".eggs" (
    echo Deletando: .eggs\
    rmdir /s /q ".eggs"
)

if exist "*.egg-info" (
    echo Deletando: *.egg-info\
    for /d %%x in (*.egg-info) do rmdir /s /q "%%x"
)

echo Limpeza concluída!
echo.
pause
