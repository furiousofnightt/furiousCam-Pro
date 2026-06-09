# 📦 Build FuriousCam Pro - Guia Completo

## ✅ Pré-requisitos

1. **Python 3.10+** instalado (verifique com `python --version`)
2. **Dependências do requirements.txt** instaladas:
   ```bash
   pip install -r requirements.txt
   ```
3. **PyInstaller** (será instalado automaticamente pelo build.bat, ou instale manualmente):
   ```bash
   pip install pyinstaller
   ```

---

## 🚀 Opção 1: Build Automático (Recomendado)

### Windows:
1. Abra a pasta do projeto
2. Clique com **duplo clique** em `build.bat`
3. Aguarde (leva ~2-3 minutos na primeira vez)
4. Executável gerado em: `dist\FuriousCam\FuriousCam.exe`

### macOS / Linux:
```bash
bash build.sh
```

---

## 🛠️ Opção 2: Build Manual via Terminal

### Windows (PowerShell ou CMD):
```bash
python -m PyInstaller furiousCam.spec --clean
```

### macOS / Linux:
```bash
python -m PyInstaller furiousCam.spec --clean
```

---

## 🧹 Limpeza de Builds Antigos

### Windows:
Execute `clean_build.bat` antes de um novo build para remover:
- `build/` (artefatos de compilação)
- `dist/` (builds antigos)
- `*.egg-info/` (cache pip)

```bash
clean_build.bat
```

### macOS / Linux:
```bash
rm -rf build dist *.egg-info
```

---

## 📍 Estrutura Final Correta

```
dist/
└── FuriousCam/             ← Distribua esta pasta inteira
    ├── FuriousCam.exe      ← User executa isto
    ├── _internal/          ← Todas as dependências
    │   ├── PySide6/
    │   ├── av/
    │   ├── numpy/
    │   ├── pyvirtualcam/
    │   └── portables/
    │       └── adb/
    │           ├── adb.exe
    │           ├── furious-core.jar
    │           └── ... (drivers ADB)
    └── config.ini          ← Criado automaticamente na 1ª execução
```

**IMPORTANTE:** `dist/` deve conter APENAS a pasta `FuriousCam/`. Se existir `dist/FuriousCam.exe` solto, o build.bat o remove automaticamente.

---

## 🎯 Como Usar o Executável

1. **Primeira Vez:**
   ```bash
   FuriousCam/FuriousCam.exe
   ```
   - App cria `config.ini` automaticamente
   - Settings são salvos ali

2. **Distribuir:**
   - Comprima a pasta `FuriousCam/` inteira
   - Redistribua como ZIP
   - Usuários extraem e clicam em `FuriousCam.exe`

---

## 🐛 Troubleshooting

### Erro: "Python não é reconhecido"
```bash
# Reinstale Python, marcando "Add Python to PATH" na instalação
```

### Erro: "PyInstaller não encontrado"
```bash
pip install --upgrade pyinstaller
```

### Executável muito grande (>500MB)
- Normal! PySide6 + FFmpeg = pesado
- `dist/FuriousCam/` tem ~500-600MB com todas as dependências
- Considere comprimir para distribuição (ZIP/7z reduz para ~150-200MB)

### config.ini não persiste
- Verifique permissões de escrita em `dist/FuriousCam/`
- Config.ini deve estar nesse diretório, não em C:\Users\...\AppData

### Arquivo dist/FuriousCam.exe solto após build
- Isto é um erro de versão anterior do spec file
- Execute `build.bat` (já corrigido) que remove automaticamente
- Ou execute `clean_build.bat && build.bat`

### Erro ao executar FuriousCam.exe em outro PC
- Instale "Visual C++ Redistributable" em máquinas sem Python/compilador
- Link: https://support.microsoft.com/pt-br/help/2977003
- Alguns clientes ADB podem precisar de drivers USB

---

## 📦 Empacotar para Distribuição

### Criar ZIP para compartilhar:
```bash
# Windows (com 7-Zip, WinRAR, ou ZIP nativo)
# Clique direito em dist\FuriousCam → "Enviar para" → "Pasta Compactada"
# Ou via terminal:
Compress-Archive -Path "dist/FuriousCam" -DestinationPath "furiouscam-executavel-v2.0.zip"
```

### Estrutura final distribuível:
```
furiouscam-executavel-v2.0.zip
└── FuriousCam/
    ├── FuriousCam.exe
    ├── _internal/
    └── (config.ini criado na 1ª execução)
```

**Tamanho esperado:** ~150-200MB (ZIP comprimido)

---

## ✅ Verificação Final

Antes de distribuir, teste:

1. ✅ Conectar via USB
2. ✅ Conectar via Wi-Fi (Hybrid)
3. ✅ Reconectar com config.ini salvo
4. ✅ OBS Virtual Camera funciona
5. ✅ Latência exibe valor real (não 0ms)
6. ✅ Tray mostra status correto
7. ✅ Settings persistem após fechar e reabrir

---

## 📊 Tamanho Esperado

- **Pasta FuriousCam/**: ~800MB - 1.2GB
- **Executável (FuriousCam.exe)**: ~15-20MB
- **Deps (_internal/)**: ~700-800MB
- **portables/**: ~100-200MB

---

## 🚀 Para Streamers

Configure assim:

1. Extraia para `C:\Stream\FuriousCam\`
2. Execute `FuriousCam.exe`
3. Conecte câmera (prefira W-Fi para menos cabos)
4. Em OBS: Adicione source "Window" → FuriousCam Pro
5. **OU** use a Câmera Virtual (OBS plugin)

---

## ❓ Dúvidas?

- Verifique `log_file.txt` na pasta do app
- Todos os erros são logados lá
