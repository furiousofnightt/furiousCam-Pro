<div align="center">
  <img src="portables/images/furiouscam.png" alt="FuriousCam Pro" width="120" height="120" />
  
  # 🔥 FuriousCam Pro
  
  ### Transforme seu Android em Webcam para OBS Studio
  
  **Use seu celular como câmera profissional via USB ou Wi-Fi — sem aplicativo permanente instalado**
  
  [![Download App](https://img.shields.io/badge/📲%20DOWNLOAD%20APP-005CED?style=for-the-badge&logoColor=white)](https://furiouscam.pythonanywhere.com/)
  [![Python](https://img.shields.io/badge/Python-3.9+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
  [![Windows](https://img.shields.io/badge/Windows-10%2B-0078d4?style=flat-square&logo=windows&logoColor=white)](https://www.microsoft.com/windows/)
  [![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=flat-square)](.)
  
</div>

---

## 🎯 O que é FuriousCam Pro?

**FuriousCam Pro** é uma solução poderosa e leve que transforma seu smartphone Android em uma webcam profissional para Windows. Integre-se perfeitamente ao OBS Studio e comece a transmitir com qualidade broadcast.

### ✨ Principais Características

<table>
<tr>
<td>

**📱 Conectividade**
- ✅ USB com ADB (baixa latência)
- ✅ Wi-Fi (mobilidade)
- ✅ Reconexão automática
- ✅ Fallback inteligente

</td>
<td>

**🎥 Qualidade**
- ✅ Até 1080p@60fps
- ✅ H.264 hardware decode
- ✅ Latência ultra-baixa
- ✅ Codificação eficiente

</td>
<td>

**⚡ Performance**
- ✅ Consumo mínimo de CPU
- ✅ Sem lag perceptível
- ✅ Estável e confiável
- ✅ Pronto para produção

</td>
</tr>
</table>

### 🎬 Integração OBS

- Plugin virtual camera ready
- Plug-and-play integration
- Múltiplas resoluções
- Controle em tempo real

---

## 📊 Status do Projeto

| Versão | Status | Progresso |
|--------|--------|-----------|
| **2.0 Final** | ✅ **Production Ready** | 100% |
| USB + Preview + OBS | ✅ Completo | 100% |
| Wi-Fi + Reconnect | ✅ Completo | 100% |
| WiFi Fallback + Cleanup | ✅ Completo | 100% |

---

## 📋 Documentação

1. [Requisitos](#requisitos)
2. [Instalação Rápida](#instalação-rápida)
3. [Como Usar](#como-usar)
4. [Características Detalhadas](#características-detalhadas)
5. [Arquitetura](#arquitetura)
6. [Desenvolvimento](#desenvolvimento)
7. [FAQ](#faq)

---

## 🎯 Visão Geral

**FuriousCam Pro** é um complemento simples para o OBS Studio que permite usar um celular Android como webcam sem aplicativo permanente instalado.

### Objetivo Principal
- 📱 Celular como **webcam para OBS**
- 🔌 Via **USB ou Wi-Fi**
- 🎥 **Sem app permanente** no Android
- ⚡ **Baixa latência** (H.264 hardware decode)
- 🎬 **Pronto para streaming** (plug-and-play OBS)

### O que NÃO é
- ❌ Plataforma de streaming
- ❌ Editor de vídeo
- ❌ Suite de analytics/IA
- ❌ Aplicativo Android permanente

---

## 📊 Status Atual

### Versão: **2.0 Final**
### Progresso: **100% Completo**

| Fase | Status | Progresso |
|------|--------|-----------|
| **Fase 1** — USB + Preview + OBS | ✅ COMPLETA | 100% |
| **Fase 2** — Wi-Fi + Reconnect | ✅ COMPLETA | 100% |
| **Fase 3** — WiFi Fallback + Cleanup | ✅ COMPLETA | 100% |
| **Fase 4** — UX Premium + Animações | ✅ COMPLETA | 95% |
| **Fase 5** — Features Avançadas | ❌ NÃO INICIADA | 0% |

### Resumo Rápido
```
✅ USB Device Detection
✅ H.264 Decode (FFmpeg/PyAV)
✅ OBS Virtual Camera Integration
✅ Multi-camera (Traseira + Frontal)
✅ Hot-swap Câmera ao vivo
✅ Dark Mode UI (Premium)
✅ Live Stats (FPS, Resolution, Bitrate)
✅ Janela Flutuante com Fullscreen

✅ WiFi Fallback Automático
✅ Cleanup Inteligente ao Fechar
✅ Push Server com Retry (Xiaomi)
✅ Aviso de Câmera Não Suportada
✅ Bitrate Manual (sem adaptativo)
✅ Wi-Fi Híbrido
✅ Áudio integrado (Opus + Monitor)
✅ Config Persistência (config.ini)
```

---

## ✨ Características

### Novas em v2.0

#### WiFi Fallback Automático
- ✅ **USB Timeout 5s** — Se não encontrar cabo, tenta WiFi automaticamente
- ✅ **IP Persistência** — Salva último IP WiFi em config.ini
- ✅ **Retry Automático** — Tentativas 2x com delay se push_server falhar (Xiaomi EOF)
- ✅ **Sem Interrupção** — ADB fica ativo durante operações (não mata durante fallback)

#### Cleanup Inteligente
- ✅ **Separado** — `stop_connection()` para operações vs `cleanup_on_exit()` para fechar app
- ✅ **Rápido** — App fecha em < 1s mesmo se conectado
- ✅ **Completo** — ADB mata completamente apenas ao fechar app

#### Aviso de Câmera Não Suportada
- ✅ **Diálogo Popup** — Aparece se aparelho não suporta câmera nativa
- ✅ **Educativo** — Explica que suporte varia por modelo/fabricante em Android 11+
- ✅ **Fallback** — Continua com screen mirror automaticamente

### Implementadas (v2.0)

#### Conectividade
- ✅ **ADB USB** — Detecção automática de dispositivos Android
- ✅ **Wi-Fi Híbrido** — Sistema tray com modo híbrido automático (detecta IP via ADB)
- ✅ **Wi-Fi IP Manual** — Conexão direta por endereço IP
- ✅ **Port-Forward** — Redirecionamento TCP automático
- ✅ **Protocolo Scrcpy** — Compatível com servidor scrcpy-core.jar
- ✅ **Hot-Swap** — Alternar câmera e conexão sem desligar stream OBS
- ✅ **Return to USB** — Voltar para cabo USB com reconexão automática

#### Câmera
- ✅ **Dual Câmera** — Traseira (principal) + Frontal
- ✅ **Resolução** — 480p até 4K (dropdown)
- ✅ **FPS** — 24, 30, 60 FPS selecionável
- ✅ **Bitrate** — 2-20 Mbps (slider)
- ✅ **Rotação** — 0°/90°/180°/270° + Auto-rotate
- ✅ **Espelhamento** — Mirror/flip imagem

#### Vídeo & Decode
- ✅ **H.264 Decode** — Hardware via FFmpeg
- ✅ **Thread-Safe** — NumPy arrays isoladas
- ✅ **PTS Tracking** — Timestamps mantidos
- ✅ **Timeout Detection** — 10s auto-disconnect

#### OBS Integration
- ✅ **Virtual Camera** — Compatível OBS/Streamlabs/Discord/Zoom/Meet
- ✅ **Multi-Backend** — obs → unitycapture fallback
- ✅ **Auto-Resize** — Frames redimensionados automaticamente
- ✅ **Permanente** — Continua ativo após janela fechar

#### Interface
- ✅ **Dark Mode** — Design premium com gradientes
- ✅ **Dashboard** — Sidebar + Preview + Stats
- ✅ **Stats Badges** — FPS, Resolução, Fonte, Device, Bitrate, Latência
- ✅ **FPS Sparkline** — Histograma de FPS (últimos 30 segundos)
- ✅ **Menu Settings** — Gear icon com submenu nativo
- ✅ **Wi-Fi Submenu** — Controles de conexão sem fio integrados
- ✅ **Janela Flutuante** — Borderless, draggable, fullscreen, resizable
- ✅ **Auto-Resize** — Redimensionamento proporcional ao mudar orientação
- ✅ **Modo Fundo** — Joga janela para trás (OBS continua gravando)
- ✅ **Render Timer** — 60fps (QTimer)
- ✅ **Icons SVG** — Coloridos e customizáveis

#### Logging & Debug
- ✅ **Logging Estruturado** — Timestamps, níveis, thread-safe
- ✅ **Exception Handling** — Try-catch em pontos críticos
- ✅ **Error Signals** — Status updates em tempo real com QDialog (ex: Câmera roubada)

#### Persistência & Configurações
- ✅ **Config.ini** — Salva FPS, resolução, câmera, rotação, espelhamento
- ✅ **Último IP Wi-Fi** — Salva automaticamente para reconexão rápida
- ✅ **Auto-Rotate** — Detecta orientação do stream e ajusta automaticamente

---

## 📦 Requisitos

### Windows
- Windows 10/11 (64-bit)
- Python 3.10+
- ADB drivers (Google USB)

### Android
- Android 5.0+ (API 21+)
- Modo USB Debug ativado
- Permissão de câmera

### Dependências Python
```
PySide6           >= 6.0    (UI)
PyAV              >= 10.0   (FFmpeg decode)
numpy             >= 1.20   (Arrays)
pyvirtualcam      >= 0.0.11 (OBS integration)
```

---

## 🚀 Instalação

### 1. Preparar Windows

#### a) Instalar Python 3.10+
```powershell
# Verificar versão
python --version  # Deve ser 3.10+
```

#### b) Instalar ADB
```powershell
# Opção 1: Android SDK Platform Tools (recomendado)
# Download: https://developer.android.com/studio/releases/platform-tools

# Opção 2: FuriousCam já inclui ADB portátil em portables/adb/
```

#### c) Instalar OBS Virtual Camera (CRÍTICO!)
```
1. Instalar OBS Studio >= 27 (obsproject.com)
2. Ferramentas > Start Virtual Camera
3. Fechar OBS
```

### 2. Preparar Celular

```
1. Conectar Android via USB
2. Ativar Modo USB Debug: Configurações > Sobre > Versão do Build (7x) > Dev Options > USB Debug
3. Autorizar conexão no popup
```

### 3. Instalar Dependências

```powershell
cd furiousCam-mobile-win
pip install -r requirements.txt
```

### 4. Executar

```powershell
python main.py
```

---

## 📖 Como Usar

### Fluxo Básico

#### 1. Conectar Celular
```
1. Abrir FuriousCam Pro
2. Celular aparecerá automaticamente em "DISPOSITIVO"
3. Clique em "Conectar Câmera"
4. Aguarde 2-3 segundos
```

#### 2. Visualizar Preview
```
A câmera do celular aparecerá na área principal com:
- Borda verde = stream ativo
- Stats ao fundo = FPS, resolução, etc
```

#### 3. Ativar OBS Virtual Camera
```
1. Clique "Ativar Câmera Virtual"
2. No OBS: Adicionar Fonte > Video Capture Device > OBS Virtual Camera
3. Preview aparece automáticamente no OBS
```

#### 4. Ajustar Configurações
```
CÂMERA:
  - Dropdown: Traseira ou Frontal
  - Botão "Alternar": Hot-swap ao vivo

ROTAÇÃO:
  - Botões 0°/90°/180°/270°
  - "Auto": Detecta orientação automática
  - "Desespelhar": Mirror/flip a imagem

QUALIDADE:
  - Dropdown: 4K / 2K / Full HD / HD / 480p
  - FPS: 60 / 30 / 24
  - Bitrate: Slider 2-20 Mbps

OBS OUTPUT:
  - "Ativar Câmera Virtual": Ativa/desativa output
```

#### 5. Janela Flutuante (para Streamers)
```
1. Clique "Janela de Câmera"
2. Nova janela abre (borderless, sempre no topo)
3. Clique duplo = Fullscreen
4. Drag/resize = Redimensiona
5. Botões: Fullscreen, Background, Close, Rotate
```

#### 6. Conexão Wi-Fi (Sistema Tray)
```
MODO HÍBRIDO AUTOMÁTICO:
1. Clique no ícone de engrenagem (⚙️) no sidebar
2. Vá em "📡 Conexão Wi-Fi"
3. Clique "Ativar Wi-Fi (Modo Híbrido Automático)"
4. O app detecta o IP automaticamente via ADB
5. Após conectar, remova o cabo USB

IP MANUAL:
1. Clique no ícone de engrenagem (⚙️) no sidebar
2. Vá em "📡 Conexão Wi-Fi"
3. Clique "Conectar por Endereço IP Manual"
4. Digite o IP (ex: 192.168.1.15)
5. Conecte-se

VOLTAR PARA USB:
1. Clique no ícone de engrenagem (⚙️) no sidebar
2. Vá em "📡 Conexão Wi-Fi"
3. Clique "Voltar para Cabo USB"
4. Reconexão automática via USB
```

### Atalhos Teclado
- (Nenhum por enquanto)

---

## 🏗️ Arquitetura

### Visão Geral

```
┌─────────────────────────────────────────────────────┐
│                  FuriousCam Pro                      │
│                   (Windows App)                      │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐         │
│  │   Core   │   │ Decoder  │   │   OBS    │         │
│  │          │   │          │   │          │         │
│  │ AppCore  │──→│ Video    │──→│ Virtual  │         │
│  │ AdbMgr   │   │ Receiver │   │ Camera   │         │
│  └──────────┘   └──────────┘   └──────────┘         │
│        │              │              │               │
│        │              │              └─→ OBS Studio  │
│        │              │                  Zoom, etc   │
│        │              └─→ FFmpeg/PyAV                │
│        │                  (H.264 decode)             │
│        └─→ ADB (Android Device Bridge)               │
│            Port-Forward TCP                          │
│                                                       │
│  ┌────────────────────────────────────────┐          │
│  │           UI (PySide6)                 │          │
│  │  MainWindow | CameraOnlyWindow | Icons│          │
│  └────────────────────────────────────────┘          │
│                                                       │
└─────────────────────────────────────────────────────┘
         │                          │
         │                          │
         ▼                          ▼
    ┌─────────┐            ┌──────────────┐
    │ Celular │            │ OBS Virtual  │
    │ Android │◄──USB───→  │ Camera       │
    │         │            │              │
    │ Camera  │            │ Input Source │
    │ +       │            │ for Streaming│
    │ Scrcpy  │            │              │
    │ Server  │            │              │
    └─────────┘            └──────────────┘
```

### Layers

#### 1. **Core Layer** (100% ✅)
- `AppCore` — Orquestração central com Qt signals
- `AdbManager` — Gerencia ADB, device detection, port-forward
- Thread management e lifecycle

#### 2. **Decoder Layer** (100% ✅)
- `VideoReceiver` — Socket TCP, protocolo scrcpy
- PyAV/FFmpeg — H.264 hardware decode
- NumPy array conversion (thread-safe)

#### 3. **OBS Layer** (95% ✅)
- `VirtualCamOutput` — pyvirtualcam wrapper
- Multi-backend support (obs, unitycapture)
- Frame resize e timing

#### 4. **UI Layer** (90% ✅)
- `MainWindow` — Dashboard principal
- `CameraOnlyWindow` — Janela flutuante
- `VideoWidget` — Renderização 60fps QImage
- `icons.py` — Sistema SVG
- `install_dialog.py` — OBS setup guide

---

## 📁 Estrutura de Arquivos

```
furiousCam-mobile-win/
│
├── main.py                          # Entry point
├── requirements.txt                 # Dependências pip
├── planejamento_furiouscam_pro.md   # Planejamento + Status
├── README.md                        # Este arquivo
├── ARCHITECTURE.md                  # Detalhes técnicos
│
├── core/
│   ├── app_core.py                 # Orquestração central (330 linhas)
│   └── adb_manager.py              # ADB control (340 linhas)
│
├── decoder/
│   └── video_receiver.py           # H.264 decode (166 linhas)
│
├── obs/
│   ├── virtual_cam.py              # Virtual Camera (157 linhas)
│   └── __init__.py
│
├── transport/
│   └── wifi_manager.py             # Wi-Fi Manager (227 linhas)
│
├── ui/
│   ├── main_window.py              # Dashboard (1100+ linhas)
│   ├── camera_window.py            # Janela flutuante (400+ linhas)
│   ├── icons.py                    # SVG system (50 linhas)
│   ├── install_dialog.py           # OBS guide (200+ linhas)
│   └── __pycache__/
│
├── portables/
│   └── adb/
│       ├── adb.exe                 # ADB executable
│       ├── AdbWinApi.dll           # ADB library
│       ├── AdbWinUsbApi.dll        # ADB USB support
│       └── furious-core.jar        # Scrcpy server Android
│
└── logs/                           # (criado em runtime)
    └── furiouscam.log
```

**Total de código**: ~2.000 linhas de Python pronto para produção

---

## 🗺️ Roadmap

### ✅ v2.0 (ATUAL — USB + Wi-Fi + OBS + Áudio)
- [x] USB via ADB
- [x] H.264 decode
- [x] OBS Virtual Camera
- [x] Multi-câmera
- [x] Hot-swap
- [x] Dark mode UI
- [x] Live stats
- [x] Áudio integrado

### ✅ Status Final
FuriousCam Pro está concluído como versão `2.0` e já entrega o que foi prometido. Não há planejamento de versões futuras nem roadmap adicional para este projeto.

---

## 🔧 Desenvolvimento

### Ambiente de Desenvolvimento

#### 1. Setup
```powershell
# Clone/abra a pasta no VS Code
cd furiousCam-mobile-win

# Crie virtual env (opcional)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instale dependências
pip install -r requirements.txt

# Se vai desenvolver, instale dev tools:
pip install black flake8 pytest
```

#### 2. Executar em Debug
```powershell
# Com logging verbose
python main.py  # Logs aparecem no console + arquivo

# Arquivo de log:
# logs/furiouscam.log
```

#### 3. Estrutura de Código

**Padrões usados:**
- Qt Signals/Slots para thread-safe communication
- NumPy arrays para video frames (efficient)
- Context managers para resource cleanup
- Docstrings em português (main functions)
- Logging em todos os pontos críticos

**Convenções:**
```python
# Nomes: snake_case para funções/variáveis, PascalCase para classes
class AppCore(QObject):
    def start_connection(self):
        pass

# Signals: Nome descritivo, não usar "on_" prefix
status_changed = Signal(str)

# Thread safety: Sempre converter av.VideoFrame→numpy antes de cross-thread
arr = frame.to_ndarray(format='rgb24')
```

### Modificando o Código

#### Adicionar Nova Feature
```python
# 1. Adicionar ao AppCore se for lógica
class AppCore:
    def new_feature(self):
        pass

# 2. Adicionar sinal se precisa avisar UI
new_signal = Signal(dict)

# 3. Conectar na MainWindow.__init__
self.core.new_signal.connect(self.update_ui)

# 4. Implement UI slot
@Slot()
def update_ui(self, data):
    pass
```

#### Adicionar Logging
```python
import logging
logger = logging.getLogger(__name__)

# Em pontos críticos:
logger.info("Evento importante aconteceu")
logger.error(f"Erro: {exception}")
logger.warning("Algo suspeito detectado")
```

### Testando

#### Sem Celular (Simulação)
```python
# Em adb_manager.py, comentar parte de wait_for_device
# e forçar device_serial = "mock_device"
```

#### Com Celular Real
```
1. Conectar via USB
2. Autorizar USB Debug no popup
3. python main.py
4. Deve detectar automaticamente
```

---

## 📝 Decisões de Design

### Por que PySide6 e não PyQt5?
- PySide6 é oficial da Qt Company
- Melhor suporte moderno
- Tipo hints melhores
- Não precisa compilar C++

### Por que Scrcpy?
- Baixa latência (pensado para gaming)
- H.264 hardware encoding Android
- Sem app permanente
- Open-source e confiável

### Por que pyvirtualcam?
- Funciona com OBS/Zoom/Discord
- Multi-backend (obs, unitycapture)
- Pure Python (sem compilação)
- Ativo e mantido

### Por que H.264 e não VP9/H.265?
- H.264 compatível com qualquer celular (API 21+)
- Menos CPU
- Latência menor
- H.265 seria v1.0+

### Por que USB primeiro, Wi-Fi depois?
- USB é mais estável
- Prototipagem rápida
- Wi-Fi requer MDNS/TCP mais complexo
- Usuários podem esperar

---

## 🐛 Troubleshooting

### "Dispositivo não encontrado"
```
1. Certifique-se USB Debug está ON
2. Autorize o computador no popup do celular
3. Tente outro cabo USB
4. Rode: adb devices (deve listar o device)
```

### "Falha ao enviar servidor"
```
1. Verifique se furious-core.jar existe em portables/adb/
2. Tente: adb shell ls /data/local/tmp/
3. Limpe: adb shell rm /data/local/tmp/furious-core.jar
```

### "OBS Virtual Camera não encontrada"
```
1. Instale OBS Studio >= 27
2. Abra OBS, vá em Ferramentas > Start Virtual Camera
3. Feche OBS
4. Execute novamente FuriousCam
```

### "Camera está congelada / Latência alta"
```
1. Aumente bitrate (slider)
2. Reduza resolução
3. Reduz FPS para 30
4. Tente câmera traseira (mais estável)
```

### "Apenas câmera traseira funciona"
```
1. Verifique se o celular tem câmera frontal
2. Teste direto com: adb shell camera-facing=front
```

---

## 📚 Referências

### Documentação Externa
- [Scrcpy Project](https://github.com/Genymobile/scrcpy) — Protocolo e server
- [PySide6 Docs](https://doc.qt.io/qtforpython-6/) — Framework UI
- [PyAV Docs](https://pyav.org/) — FFmpeg binding
- [pyvirtualcam](https://github.com/letmaik/pyvirtualcam) — Virtual Camera
- [OBS Studio](https://obsproject.com/) — Virtual Camera driver

### Padrões & Best Practices
- Thread-safety: Always convert video frames to NumPy before cross-thread access
- Error handling: Log everything, avisar user via signals
- Performance: Reuse buffers, avoid copies, use C_CONTIGUOUS arrays
- UI: Always use QTimer for render loops, nunca sleep na thread principal

---

## 📄 Licença

Projeto pessoal de Diego. Sem licença específica (propriedade privada).

---

## ✉️ Contato / Notas

### Projeto concluído
FuriousCam Pro está finalizado com a versão `2.0` como entrega completa. Não há planos de desenvolvimento adicional para este aplicativo.

### Histórico de Versões

**v2.0** (07/06/2026)
- USB completo
- OBS Virtual Camera
- Wi-Fi híbrido
- Áudio integrado
- Config persistente

**v2.0** (07/06/2026)
- USB completo
- OBS Virtual Camera
- Wi-Fi híbrido
- Áudio integrado
- Config persistente

**v0.3.0** (29/05/2026)
- USB completo
- OBS Virtual Camera
- Dark mode UI
- Live stats

**v0.1.0** (???)
- Protótipo inicial
- Basic ADB connection

---

## 🙏 Agradecimentos

- **Scrcpy team** — Pela tecnologia base
- **PySide6/Qt** — Framework UI moderno
- **FFmpeg** — Decode potente
- **Comunidade open-source** — Inspiração e ferramentas

---

**Última atualização**: 07/06/2026
**Status**: Final v2.0 — Pronto para distribuição final
**Feedback**: Sempre bem-vindo! 🚀
