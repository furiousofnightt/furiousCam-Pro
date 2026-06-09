
# FuriousCam Pro — Planejamento Arquitetural Completo

## Sistema Premium de Webcam para Android via USB/Wi‑Fi para OBS Studio e Streamlabs

### Arquitetura orientada para orquestração AI-assisted development

---

# 1. Visão Geral do Projeto

## Objetivo

Criar um sistema avançado de transmissão de câmera Android para Windows capaz de:

- funcionar via USB e Wi‑Fi;
- operar em baixa latência;
- ser reconhecido no OBS Studio como fonte de vídeo;
- permitir uso em OBS Studio, Streamlabs, Discord, Zoom e Meet;
- não exigir instalação permanente de aplicativo Android;
- possuir arquitetura moderna, modular e escalável.

---

# 2. Stack Recomendada

## Backend
- Python 3.12+

## UI
- PySide6 (Qt)

## Streaming
- FFmpeg
- PyAV
- NumPy

## Comunicação
- ADB
- TCP/IP
- WebSocket

## Codec
- H264

---

# 3. Arquitetura Geral

```txt
ANDROID
   ↓
ADB / Wi‑Fi
   ↓
Server Temporário
   ↓
Encoder H264
   ↓
Python Receiver
   ↓
FFmpeg Decode
   ↓
OBS Source
   ↓
OBS Virtual Camera
```

---

# 4. Recursos Premium

## Conectividade
- USB ultra estável
- Wi‑Fi inteligente
- Auto reconnect
- Descoberta automática LAN

## Vídeo
- 30/60 FPS
- baixa latência
- aceleração GPU

## Áudio
- captura Android 11+
- sincronização AV
- redução de ruído
- permitir escolha de captura de audio ou não
- permitir captura de áudio em tempo real

## OBS
- integração direta
- auto scene source
- overlay support

---

# 5. Estratégia Android

## Modelo estilo scrcpy
- server temporário enviado via ADB
- sem app permanente
- inicialização automática

## APIs Android
- Camera2 API
- MediaCodec
- MediaProjection

---

# 6. Módulos do Sistema

## Device Manager
- detectar dispositivos
- USB/Wi‑Fi
- status

## Transport Engine
- compressão
- transmissão
- retry

## Decode Engine
- FFmpeg (PyAV)
- GPU decode (Vídeo)
- Opus decode nativo (Áudio)
- Spectral Subtraction (Redução de ruído O(n log n) em NumPy)
- QAudioSink Dual-Stream (Via principal → VB-Cable/OBS sempre ativa | Via monitor → Auto-detecção de alto-falante real, ativada só pelo botão "Me Ouvir")
- Auto-Mute Inteligente (Se dispositivo for fone real, muta automaticamente a via principal até "Me Ouvir" ser ativado)
- Anti-VB-Cable no Monitor (Detecta se dispositivo padrão do Windows é cabo virtual e varre por um fone real automaticamente)
- Persistência de Preferência (Salva dispositivo de saída de áudio em config.ini entre reinicializações)

## OBS Layer
- integração OBS
- Virtual Camera

## UI Engine
- dashboard
- preview
- estatísticas

---

# 7. UI/UX

## Inspirações
- OBS Studio
- Elgato
- Discord
- MSI Afterburner

## Visual
- dark mode
- blur
- glow suave
- animações fluidas

---

# 8. Pipeline de Performance

## Prioridades
- estabilidade
- baixa latência
- frame pacing

## Técnicas
- multithreading
- async IO
- queues isoladas

---

# 9. Estrutura Recomendada

```txt
furiouscam-mobile-win/
├── core/
├── decoder/
├── obs/
├── transport/
├── ui/
├── portables/
├── dist/           # saída de build
├── main.py
├── furiousCam.spec
├── README.md
└── requirements.txt
```

---

# 10. Ferramentas Gratuitas

## Multimídia
- FFmpeg
- GStreamer

## UI
- Qt Designer

## OBS
- OBS WebSocket

## Android
- ADB
- Android Platform Tools

---

# 11. Roadmap

## FASE 1 ✅ COMPLETA
- ✅ USB — Funcional com ADB
- ✅ Preview — VideoWidget com renderização em tempo real
- ✅ OBS source — Integração com OBS Virtual Camera (pyvirtualcam)

## FASE 2 ✅ COMPLETA
- ✅ Wi‑Fi — Implementado via conexão híbrida (IP) com ADB over TCP e detecção inteligente
- ✅ Wi-Fi Manager — Sistema tray com modo híbrido automático, IP manual e return to USB
- ✅ Reconnect — Hot-swap de câmera ao vivo sem desligar stream OBS
- ✅ Adaptive bitrate — Limitação segura dinâmica (máx 8 Mbps em Wi-Fi)
- ✅ Persistência IP — Salva último IP Wi-Fi em config.ini para reconexão rápida

## FASE 3 ✅ COMPLETA (100%)
- ✅ Áudio — **IMPLEMENTADO** (Motor próprio com Opus nativo e VU Meter visual)
- ✅ Filtros — **IMPLEMENTADO** (Subtração Espectral de Ruído O(n log n) em NumPy)
- ✅ Roteamento de Áudio — **IMPLEMENTADO** (Sistema Dual-Routing inteligente com Mute automático e anti-looping para Cabos Virtuais e Fones)

## FASE 4 ✅ COMPLETA (100%)
- ✅ UX premium — UI moderna com dark mode, gradientes, bordas verdes (#00e676)
- ✅ Animações — Transições QTimer (60fps), fade suave, hover effects
- ✅ Settings Menu — Gear icon com menu dropdown nativo e Wi-Fi submenu
- ✅ FPS Sparkline — Histograma de FPS (últimos 30 segundos)
- ✅ Latência Badge — Mostra latência em ms (calculada per-cycle)
- ✅ Auto-Rotate — Detecta orientação do stream automaticamente
- ✅ Wheel Blocker — Impede scroll em ComboBox/Slider no sidebar
- ✅ Persistência Config — Carrega/salva configurações via config.ini
- ✅ Log Viewer — Sistema de log integrado na UI para debug da stream e eventos

---

# 12. Diferenciais Implementados

- ✅ **Arquitetura moderna** — Modular (core, transport, decoder, obs, ui), signals/slots Qt, threads isoladas
- ✅ **Baixa latência** — H.264 hardware decode, TCP_NODELAY, sem sleep bloqueador
- ✅ **UI premium** — Dark mode, gradientes, transições fluidas 60fps, bordas verdes (#00e676)
- ✅ **Integração OBS superior** — Virtual Camera automática, janela flutuante borderless, fullscreen
- ✅ **Pipeline limpa** — Cada função em módulo separado, facil manutenção
- ✅ **Compatibilidade híbrida** — USB e Wi-Fi totalmente operacionais e selecionáveis

---

# 13. Filosofia (100% Mantida)

```txt
✅ Estabilidade > marketing
✅ Latência > efeitos desnecessários  
✅ Pipeline limpa > hacks
✅ Experiência premium > excesso visual
```

---

# 14. Status de Implementação Detalhado

## 📊 Progresso Geral: **100% Completo**

### Core Layer (100% ✅ — PRONTO)
- ✅ `AppCore`: Orquestração central com signals Qt
- ✅ `AdbManager`: Detecção dispositivos, port-forward, envio JAR scrcpy
- ✅ Lifecycle management (start_connection, stop_connection)
- ✅ Virtual Camera integration pyvirtualcam
- ✅ Hot-swap de câmera ao vivo (sem desligar OBS)
- ✅ Settings dinâmicos (FPS, resolução, bitrate, rotação, espelhar)

### Decoder Layer (100% ✅ — PRONTO)
- ✅ `VideoReceiver`: Socket TCP, protocolo scrcpy completo
- ✅ PyAV + FFmpeg (H.264 com detecção Codec dinâmico)
- ✅ Conversão NumPy RGB thread-safe
- ✅ Frame metadata (PTS, resolução detecção)
- ✅ Timeout detection (10s) e tratamento Socket EOF

### OBS Layer (100% ✅ — PRONTO)
- ✅ `VirtualCamOutput`: pyvirtualcam multi-backend (obs → unitycapture)
- ✅ Resize automático de frames
- ✅ Suporte OBS, Streamlabs, Discord, Zoom, Meet

### UI Layer (100% ✅ — PRONTO)
- ✅ `MainWindow`: Dashboard completo sidebar + preview + stats
- ✅ `VideoWidget`: Renderização QImage 60fps, overlay status
- ✅ `CameraOnlyWindow`: Janela flutuante borderless com auto-resize proporcional e modo fundo
- ✅ `LogViewerDialog`: Janela utilitária não-modal com syntax-highlight, busca SVG inline e auto-scroll
- ✅ Detecção ativa de roubo de câmera (native app) e QDialog popup
- ✅ Bloqueio Scroll Event via WheelBlocker
- ✅ **Persistência de Configurações** (FPS, Res, Câmera, Rotação, Espelhamento e IP via `config.ini`)
- ✅ Settings Menu: Gear icon com menu dropdown nativo e Wi-Fi submenu
- ✅ FPS Sparkline: Histograma de FPS (últimos 30 segundos)
- ✅ Latência Badge: Mostra latência em ms (calculada per-cycle)
- ✅ Auto-Rotate: Detecta orientação do stream automaticamente
- ✅ Controles: Câmera dupla, FPS, resolução, bitrate, rotação, espelhar
- ✅ Stats badges: FPS, resolução, fonte, dispositivo, bitrate, latência
- ✅ Sistema ícones SVG coloridos customizáveis
- ✅ `install_dialog`: Guia instalação OBS Virtual Camera

### Transport Layer (100% ✅ — PRONTO)
- ✅ ADB USB port-forward TCP
- ✅ `WifiManager`: Sistema tray com modo híbrido automático, IP manual e return to USB
- ✅ Wi-Fi híbrido manual inteligente com detecção automática de IP via ADB
- ✅ Otimização max_fps mitigando gargalos 60fps rede sem-fio (sem force_fps em Wi-Fi)
- ✅ Latência per-cycle: cálculo reset baseline para medição precisa
- ✅ Virtual cam timing: controlado externamente (sem sleep_until_next_frame)

### Extras (100% ✅ — PRONTO)
- ✅ Logging estruturado (timestamps, níveis, arquivos)
- ✅ Thread-safety (numpy contiguous arrays)
- ✅ Múltiplas câmeras (traseira/frontal)
- ✅ Frame rate detector automático — Implementado nativamente. O App mede passivamente a quantia exata de decodes por segundo, mitigando oscilações de Wi-Fi e travas físicas de hardware/API (como bloqueios do fabricante a 30fps).

---

# 15. Fila de Desenvolvimento

✅ **TODAS AS FASES CONCLUÍDAS (v2.0 Final)**
O projeto alcançou estabilidade total. Os itens marcados anteriormente como "NICE-TO-HAVE" (Smart Reconnect, Latency/FPS Badge, Roteamento, Múltiplas Câmeras e Persistência) foram totalmente finalizados!

---

# 16. Objetivo Real do Projeto

**FuriousCam Pro é um COMPLEMENTO para o OBS Studio**

Seu único objetivo é:
- 📱 Permitir que um streamer use seu celular como webcam
- 🔌 Via USB (v0.2) ou Wi-Fi (v0.3)
- 🎥 Captura áudio + vídeo em baixa latência
- 🔄 Integração automática no OBS sem configuração manual
- ✨ Simples, estável, robusto

**NÃO é**:
- ❌ Editor de vídeo
- ❌ Plataforma de streaming
- ❌ Aplicativo de analytics
- ❌ Suite de IA/super-resolução

---

# 17. Conclusão

Projeto focado em:
- 🎬 Streamers com apenas **1 celular** disponível
- 📱 Uso como **webcam rápido e confiável**
- 🎥 **Integração plug-and-play** com OBS camera virtual

A arquitetura foi desenhada para:
- 🎯 **Propósito único** (webcam, nada mais)
- 🔧 Fácil manutenção e debug
- 📈 Escalável apenas em estabilidade + novas conexões (Wi-Fi)
- 🚀 Deploy simples (app Windows standalone)

**Status atual**: Stable v2.0 — USB + Wi-Fi Híbrido + Áudio Opus Native + Filtros de Ruído + Roteamento Inteligente + Smart Reconnect.

OBS: Projeto **100% modular**, cada função em seu próprio arquivo/módulo para facilitar manutenção, debug e adição de novos recursos sem efeitos colaterais.