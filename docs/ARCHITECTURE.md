# FuriousCam Pro — Arquitetura Técnica Detalhada

**Documento para desenvolvedores — Decisões de design, fluxos de dados, e padrões de código**

---

## 📋 Índice

1. [Visão Geral da Arquitetura](#visão-geral-da-arquitetura)
2. [Fluxo de Dados](#fluxo-de-dados)
3. [Camadas do Sistema](#camadas-do-sistema)
4. [Componentes Principais](#componentes-principais)
5. [Thread Model](#thread-model)
6. [Protocolos de Comunicação](#protocolos-de-comunicação)
7. [Padrões & Best Practices](#padrões--best-practices)
8. [Otimizações de Performance](#otimizações-de-performance)
9. [Error Handling](#error-handling)
10. [Extensibilidade](#extensibilidade)

---

## 🏛️ Visão Geral da Arquitetura

### Princípios de Design

1. **Separação de Responsabilidades** — Cada layer tem função específica
2. **Thread-Safety** — Signals/slots para cross-thread communication
3. **Low Latency** — Mínimas cópias, buffers reutilizáveis
4. **Modularidade** — Fácil adicionar features sem quebrar existentes
5. **Error Resilience** — Falhas não derrubam a aplicação

### Diagrama de Camadas

```
┌──────────────────────────────────────────────────┐
│              UI Layer (PySide6)                   │
│  MainWindow | CameraOnlyWindow | VideoWidget      │
│  WifiManager (System Tray)                        │
├──────────────────────────────────────────────────┤
│           Application Core (Qt Signals)           │
│  AppCore ←→ AdbManager | VideoReceiver | AudioReceiver │
├──────────────────────────────────────────────────┤
│       Transport & Decode Layers                   │
│  ADB TCP ←→ Video: H.264 | Audio: Opus (Float32) │
│  WifiManager (Hybrid/IP Manual)                  │
├──────────────────────────────────────────────────┤
│          OBS Integration (pyvirtualcam)           │
│  VirtualCamOutput → OBS | Zoom | Discord         │
├──────────────────────────────────────────────────┤
│              Hardware & OS                        │
│  Android Device | ADB Driver | Virtual Camera    │
└──────────────────────────────────────────────────┘
```

---

## 📊 Fluxo de Dados

### Fluxo Completo: Conexão até Streaming

```
1. INICIALIZAÇÃO
   User clica "Conectar Câmera"
   ↓
   MainWindow.on_start_clicked()
   ↓
   AppCore.start_connection() [thread]

2. DETECÇÃO DE DEVICE
   AdbManager.start_server()
   ↓
   AdbManager.wait_for_device() [polling 10x 1s]
   ↓
   device_serial = "abc123xyz"

3. PUSH SERVER
   AdbManager.push_server()
   ↓
   adb push furious-core.jar → /data/local/tmp/

4. PORT FORWARD
   AdbManager.setup_port_forward()
   ↓
   adb forward tcp:27183 localabstract:scrcpy_abc123

5. LAUNCH ANDROID SERVER
   AdbManager.launch_android_server()
   ↓
   adb shell CLASSPATH=... app_process ... (scrcpy server)
   ↓
   Servidor inicia, aguarda conexão em localabstract:scrcpy

6. CONEXÃO SOCKET
   VideoReceiver.start() [thread]
   ↓
   socket.connect("127.0.0.1", 27183)
   ↓
   Socket conectado → Android streaming

7. PROTOCOLO SCRCPY
   Dummy byte ← (1 byte para sincronismo)
   ↓
   Codec meta ← (12 bytes: codec_id, w, h)
   ↓
   Frame loop:
   - Header (12 bytes: pts_flags, size)
   - Frame data (N bytes)
   - ...

8. H.264 DECODE
   VideoReceiver._receive_loop()
   ↓
   av.CodecContext.create('h264', 'r')
   ↓
   frame_data → codec_context.decode() → av.VideoFrame
   ↓
   av.VideoFrame → numpy.ndarray (RGB24)
   ↓
   self.latest_frame = numpy_array

9. UI RENDER (60fps QTimer)
   MainWindow.pull_frame() [on render_timer]
   ↓
   frame = AppCore.video_receiver.latest_frame
   ↓
   QImage(numpy_array) → VideoWidget.set_image()
   ↓
   VideoWidget.paintEvent() → QPainter

10. OBS VIRTUAL CAMERA (paralelo)
    AppCore.enable_virtual_cam()
    ↓
    VirtualCamOutput.start() [thread]
    ↓
    Loop extrai AppCore.video_receiver.latest_frame
    ↓
    pyvirtualcam.Camera.send(numpy_array)
    ↓
    OBS recebe frames como "OBS Virtual Camera"

11. UI STATS (1x/segundo)
    AppCore._stats_loop() [thread]
    ↓
    fps = frame_count / elapsed
    ↓
    AppCore.stats_updated.emit({fps, resolution, ...})
    ↓
    MainWindow.update_stats() → UI badges
```

### Fluxo de Hot-Swap (Alternar Câmera)

```
User clica "Alternar Câmera" (estando conectado)
↓
MainWindow._flip_camera()
↓
AppCore.switch_camera_live(camera_id=1) [thread]
↓
AppCore._hot_swap_routine():
  1. self.running = False
  2. VideoReceiver.stop() — Fecha socket
  3. AdbManager.cleanup() — Fecha socket ADB
  4. AdbManager.cleanup_server_on_device() — SIGTERM scrcpy
  5. sleep(1.2) — Aguarda Android liberar câmera
  6. VideoReceiver = novo VideoReceiver()
  7. self.running = True
  8. _connection_routine() — Reconecta como antes
  9. AppCore.camera_swapped.emit()
↓
MainWindow.on_camera_swapped() — Limpa render buffer
↓
User vê câmera mudando sem piscar preto no OBS
```

### Fluxo de Wi-Fi (Modo Híbrido Automático)

```
User clica "Ativar Wi-Fi (Modo Híbrido Automático)"
↓
WifiManager.action_hybrid_mode() [thread]
↓
WifiManager._hybrid_task():
  1. Se conectado: AppCore.stop_connection()
  2. AdbManager.start_server()
  3. AdbManager.wait_for_device() — USB deve estar conectado
  4. AdbManager.get_device_ip() — Detecta IP via ADB
  5. AdbManager.enable_tcpip() — Ativa TCP/IP na porta 5555
  6. sleep(3.0) — Aguarda Android preparar TCP/IP
  7. AdbManager.connect_direct_ip(ip:5555) — Conecta via Wi-Fi
  8. WifiManager.hybrid_finished.emit(True, ip:5555)
↓
WifiManager._on_hybrid_finished():
  1. is_wireless = True
  2. Salva IP em config.ini (network/last_ip)
  3. MainWindow.set_wifi_mode(True)
  4. MainWindow.on_start_clicked() — Reconecta via Wi-Fi
  5. QMessageBox: "Você já pode remover o cabo USB!"
↓
User remove cabo USB e continua streaming via Wi-Fi
```

### Fluxo de Wi-Fi (IP Manual)

```
User clica "Conectar por Endereço IP Manual"
↓
WifiManager.action_connect_ip_manual()
↓
QInputDialog: "Digite o IP (ex: 192.168.1.15)"
↓
WifiManager._manual_ip_task(ip):
  1. Se conectado: AppCore.stop_connection()
  2. AdbManager.start_server()
  3. AdbManager.connect_direct_ip(ip:5555)
  4. WifiManager.manual_ip_finished.emit(True, ip:5555)
↓
WifiManager._on_manual_ip_finished():
  1. is_wireless = True
  2. Salva IP em config.ini (network/last_ip)
  3. MainWindow.set_wifi_mode(True)
  4. MainWindow.on_start_clicked() — Reconecta via Wi-Fi
↓
System Tray: "Conectado via Wi-Fi: {ip}"
```

### Fluxo de WiFi Fallback (Automático)

```
User clica "Conectar Câmera" (sem cabo USB)
↓
MainWindow.on_start_clicked()
  └→ AppCore.start_connection()
     └→ Inicia _connection_routine()
        ├→ Step 1: AdbManager.wait_for_device() [USB, timeout 5s]
        │          If device found → pula para Step 7
        │
        ├→ Step 2: USB timeout/failed
        │          Check se tem wifi_fallback_ip em config.ini
        │
        ├→ Step 3-6: WiFi Fallback
        │  ├→ AdbManager.connect_direct_ip(ip:5555)
        │  ├→ sleep(0.5) para ADB sincronizar
        │  └→ AdbManager.wait_for_device() verify
        │
        ├→ Step 7-8: Continue normal (push_server, port_forward)
        │
        └→ launch_android_server()
           └→ If camera not supported: fallback screen + popup

Status: ✅ IMPLEMENTADO v2.0
```

**Detalhes Técnicos:**

1. **5s USB Timeout:** `wait_for_device()` faz 5 iterações × 1s cada
2. **WiFi IP Storage:** Salvo em config.ini sob `[network]/last_ip`
3. **Retry Logic:** `push_server()` tenta 2x em caso de EOF (Xiaomi)
4. **User Notification:**
   - Se câmera falha em Android < 12: popup avisa fallback para screen mirror
   - Signal `show_warning(title, msg)` emite diálogo

### Fluxo de Return to USB

```
User clica "Voltar para Cabo USB"
↓
WifiManager.action_return_to_usb() [thread]
↓
WifiManager._return_to_usb_task():
  1. Se conectado: AppCore.stop_connection()
  2. AdbManager.disconnect_ip(ip:5555)
  3. WifiManager.usb_return_finished.emit()
↓
WifiManager._on_usb_return_finished():
  1. is_wireless = False
  2. AdbManager.device_serial = None
  3. MainWindow.set_wifi_mode(False)
  4. MainWindow.on_start_clicked() — Reconecta via USB
↓
System Tray: "Voltou para Cabo USB. Reconectando..."
```

---

## 🏗️ Camadas do Sistema

### 1. Core Layer

#### `core/app_core.py` (Orquestração Central)

**Responsabilidades:**
- Gerenciar ciclo de vida (start/stop connection)
- Coordenar AdbManager + VideoReceiver
- Manter settings (FPS, resolução, bitrate, etc)
- Emitir signals para UI
- Gerenciar Virtual Camera thread

**Signals (Qt):**
```python
connection_status = Signal(str)   # Status updates
stats_updated = Signal(dict)      # FPS, resolution, etc
camera_swapped = Signal()         # Hot-swap completo
```

**Key Methods:**
```python
start_connection()           # Inicia thread de conexão + stats
_connection_routine()        # Fluxo: ADB → USB/WiFi → server → socket
stop_connection()            # Para stream, remove forward (MAS mantém ADB)
cleanup_on_exit()            # Para TUDO + mata ADB server (app closing)
enable_virtual_cam()         # Ativa OBS output
disable_virtual_cam()        # Para OBS output
switch_camera_live()         # Hot-swap camera
_virtual_cam_loop()          # Thread que envia frames ao OBS
is_connection_wireless()     # Detecta se está via WiFi (device_serial contém ":")
```

**Thread Model:**
- Main thread: UI + settings
- Worker thread: _connection_routine() (uma por conexão)
- Stats thread: _stats_loop() (FPS counter)
- Virtual cam thread: _virtual_cam_loop() (OBS output)

#### `core/adb_manager.py` (Android Bridge)

**Responsabilidades:**
- Detectar dispositivos Android via ADB
- Redireionar porta TCP via `adb forward`
- Enviar JAR scrcpy para Android
- Lançar servidor scrcpy-core no Android
- Limpeza de recursos (cleanup)

**Key Methods:**
```python
start_server()               # Inicia daemon ADB
wait_for_device()            # Poll até encontrar device (timeout 5s USB)
push_server()                # adb push furious-core.jar (com retry 2x)
setup_port_forward()         # adb forward tcp:LOCAL localabstract:SOCKET
launch_android_server()      # Lança scrcpy (fallback screen se camera falhar)
connect_direct_ip()          # adb connect para WiFi
cleanup()                    # Remove forward, mata process
cleanup_server_on_device()   # SIGTERM servidor Android
```

**Protocolo ADB Shell:**
```bash
# Exemplo: Lançar câmera traseira 1920x1080 30fps 8Mbps
adb shell CLASSPATH=/data/local/tmp/furious-core.jar \
  app_process / com.genymobile.scrcpy.Server \
  3.3.4 \
  video_source=camera \
  camera_facing=back \
  max_size=1920 \
  max_fps=30 \
  video_bit_rate=8000000 \
  ...
```

---

### 2. Decoder Layer

#### `decoder/video_receiver.py` (Socket + H.264 Decode)

**Responsabilidades:**
- Criar socket TCP para scrcpy stream de vídeo
- Ler protocolo scrcpy (dummy byte, meta, frames)
- Decodificar H.264 com FFmpeg via PyAV
- Converter av.VideoFrame → numpy RGB (thread-safe)
- Manter frame count para stats

#### `decoder/audio_receiver.py` (Socket + Opus + Filtros)

**Responsabilidades:**
- Criar socket TCP dedicado para stream de áudio do scrcpy
- Decodificar pacotes de áudio Opus nativo via PyAV para Float32 PCM
- Realizar Redução de Ruído por Subtração Espectral Rápida (Numpy FFT, ~0.1ms/frame)
- Calcular nível do VU meter (RMS dinâmico convertido para percentual Log/dB)
- Emitir buffer PCM Float32 contíguo para API nativa de áudio do SO via `QAudioSink`
- **Roteamento Inteligente (Dual-Routing):**
  - Mantém duas saídas `QAudioSink` independentes processadas na thread do worker.
  - **Saída Principal (`_main_sink`)**: Se o destino for um cabo virtual (ex: VB-Cable), fica ligada constantemente para o OBS. Se for um fone real, só emite som se o botão "Me Ouvir" estiver ativo (funcionando como Mute).
  - **Monitor de Retorno (`_monitor_sink`)**: Se a saída principal for para o OBS, cria uma segunda via independente apontando para o alto-falante real (ignorando cabos virtuais definidos como padrão no Windows), controlada pelo botão "Me Ouvir".

**Protocolo Scrcpy (Custom):**

```
CONEXÃO:
[1 byte] Dummy byte (sync)

HEADER:
[4 bytes] Codec ID (big-endian u32, 0x00000100 = H264)
[4 bytes] Width (big-endian u32)
[4 bytes] Height (big-endian u32)

STREAM:
[8 bytes] pts_flags (big-endian u64)
           - bits [63]: 1=config packet, 0=frame
           - bits [62]: 1=key-frame, 0=inter-frame
           - bits [0:62]: PTS (timestamp)
[4 bytes] Frame size (big-endian u32)
[N bytes] Frame data (H.264 NAL units)
... (repetir para cada frame)
```

**FFmpeg Decode Loop:**
```python
codec_context = av.CodecContext.create('h264', 'r')

while running:
    # Ler header + data
    packet = av.Packet(data)
    packet.pts = pts
    
    # Decodificar
    frames = codec_context.decode(packet)
    
    for frame in frames:
        # CRÍTICO: Converter na thread do decoder
        # NUNCA passar av.VideoFrame entre threads (segfault!)
        arr = frame.to_ndarray(format='rgb24')
        
        # Garantir contiguidade (requerido por NumPy)
        if not arr.flags['C_CONTIGUOUS']:
            arr = np.ascontiguousarray(arr)
        
        self.latest_frame = arr  # Substituir atomic
        self.frame_count += 1
```

**Thread Model:**
- Apenas 1 thread por socket
- `latest_frame` é atomic (Python GIL)
- `frame_count` é contador simples (não precisa lock)

---

### 3. Transport Layer

#### `transport/wifi_manager.py` (Wi-Fi Manager)

**Responsabilidades:**
- Gerenciar conexões Wi-Fi via ADB over TCP
- Sistema tray para controle rápido de conexão
- Modo Híbrido Automático (detecta IP via ADB)
- Conexão IP Manual
- Return to USB com reconexão automática
- Persistência de último IP Wi-Fi

**Signals (Qt):**
```python
hybrid_finished = Signal(bool, str)    # success, ip_with_port
manual_ip_finished = Signal(bool, str)  # success, ip_with_port
usb_return_finished = Signal()          # return to USB completo
```

**Key Methods:**
```python
action_hybrid_mode()           # Inicia modo híbrido automático
action_connect_ip_manual()     # Conexão por IP manual
action_return_to_usb()         # Volta para cabo USB
update_menu()                  # Atualiza menu do system tray
_hybrid_task()                 # Task em background para modo híbrido
_manual_ip_task(ip)            # Task em background para IP manual
_return_to_usb_task()          # Task em background para return USB
```

**Wi-Fi Hybrid Mode Flow:**
1. Para conexão atual se existente
2. Detecta device via USB ADB
3. Obtém IP do dispositivo via `adb shell ip route`
4. Ativa TCP/IP no Android via `adb tcpip 5555`
5. Conecta via IP usando `adb connect ip:5555`
6. Salva IP em config.ini para reconexão rápida
7. Reconecta stream via Wi-Fi

**System Tray Integration:**
- Ícone de cast verde quando Wi-Fi ativo
- Menu contextual com opções de conexão
- Notificações de status (QSystemTrayIcon.showMessage)
- Atualização dinâmica do menu baseado no estado

---

### 4. OBS Layer

#### `obs/virtual_cam.py` (Virtual Camera Output)

**Responsabilidades:**
- Abrir dispositivo virtual camera (pyvirtualcam)
- Tentar múltiplos backends (obs, unitycapture)
- Redimensionar frames se necessário
- Enviar para OBS/Zoom/Discord

**Backend Fallback:**
```python
_BACKENDS_TO_TRY = ["obs", "unitycapture"]

for backend in _BACKENDS_TO_TRY:
    try:
        self._cam = pyvirtualcam.Camera(..., backend=backend)
        return True  # Sucesso
    except Exception:
        continue

# Last resort: sem backend específico
self._cam = pyvirtualcam.Camera(...)
```

**Key Methods:**
```python
start(width, height, fps)    # Abrir virtual camera
send_frame(frame_rgb)        # Enviar numpy array RGB
stop()                       # Fechar
```

**Frame Pipeline:**
```python
def send_frame(self, frame_rgb: np.ndarray):
    # Redimensionar se necessário (avoid cv2 import if not needed)
    if frame_rgb.shape != (height, width, 3):
        frame_rgb = cv2.resize(frame_rgb, (width, height))
    
    # Garantir contiguidade (requerimento pyvirtualcam)
    if not frame_rgb.flags['C_CONTIGUOUS']:
        frame_rgb = np.ascontiguousarray(frame_rgb)
    
    # Enviar
    self._cam.send(frame_rgb)
    # Timing controlado externamente (AppCore._virtual_cam_loop)
```

---

### 5. UI Layer

#### `ui/main_window.py` (Dashboard Principal)

**Componentes:**
- Top bar (logo, status, live indicator)
- Sidebar com gear icon (settings menu)
- Video widget (preview)
- Stats bar (badges + FPS sparkline)

**Architecture:**
```
MainWindow (QMainWindow)
├── Topbar (QFrame)
│   ├── Logo (QLabel)
│   ├── Status (QLabel)
│   └── LIVE indicator (QLabel)
├── Content (QHBoxLayout)
│   ├── Sidebar (QFrame, 270px)
│   │   ├── Header com gear icon (btn_settings)
│   │   │   └── Settings Menu (QMenu)
│   │   │       ├── OBS Virtual Camera (checkable)
│   │   │       ├── Janela Flutuante (checkable)
│   │   │       └── Wi-Fi Submenu
│   │   │           ├── Ativar Wi-Fi (Modo Híbrido)
│   │   │           ├── Conectar por IP Manual
│   │   │           └── Voltar para USB
│   │   ├── Section: CÂMERA
│   │   │   ├── combo_camera (QComboBox)
│   │   │   └── btn_flip (QPushButton)
│   │   ├── Section: ROTAÇÃO
│   │   │   ├── rot_buttons (4x QPushButton)
│   │   │   ├── btn_auto_rotate
│   │   │   └── btn_mirror
│   │   ├── Section: QUALIDADE
│   │   │   ├── combo_res (QComboBox)
│   │   │   ├── combo_fps (QComboBox)
│   │   │   ├── lbl_bitrate (QLabel)
│   │   │   └── slider_bitrate (QSlider)
│   │   ├── Connection buttons
│   │   │   ├── btn_start (QPushButton)
│   │   │   └── btn_stop (QPushButton)
│   │
│   └── VideoWidget (custom, expanding)
│       ├── Imagem renderizada (QImage)
│       ├── Overlay com status
│       └── Borda verde quando live
│
└── Stats bar (QFrame, 58px)
    ├── stat_fps (StatBadge)
    ├── stat_res (StatBadge)
    ├── stat_source (StatBadge)
    ├── stat_device (StatBadge)
    ├── stat_bitrate (StatBadge)
    ├── stat_latency (StatBadge)
    └── fps_sparkline (FpsSparkline)
```

**Novas Features UI:**
- **Settings Menu**: Gear icon com menu dropdown nativo
- **Wi-Fi Submenu**: Controles de conexão sem fio integrados
- **FPS Sparkline**: Histograma de FPS (últimos 30 segundos)
- **Latência Badge**: Mostra latência em ms (calculada per-cycle)
- **Auto-Rotate**: Detecta orientação do stream automaticamente
- **Wheel Blocker**: Impede scroll em ComboBox/Slider no sidebar
- **Persistência**: Carrega configurações do config.ini ao iniciar

**Render Timer:**
```python
self.render_timer = QTimer(self)
self.render_timer.timeout.connect(self.pull_frame)
self.render_timer.start(16)  # ~60fps (1000/60 ≈ 16ms)
```

**Thread Communication:**
```python
# Core emits signal
core.connection_status.emit("Conectando...")
↓
# MainWindow slot recebe
@Slot(str)
def update_status(self, text: str):
    self.lbl_status.setText(text)
    # Qt automaticamente marshala para main thread
```

#### `ui/camera_window.py` (Janela Flutuante)

**Features:**
- Frameless (Qt.FramelessWindowHint)
- Always on top (Qt.WindowStaysOnTopHint)
- Resizable via borders (8px margin)
- Draggable (custom mouse handling)
- Fullscreen mode
- Rotation local (independente da main window)

**Mouse Events:**
```python
def _canvas_mouse_press(event):
    if at_border():
        start_resize()
    else:
        start_drag()

def _canvas_mouse_move(event):
    if resizing:
        update_geometry(border_direction)
    elif dragging:
        move_window(offset)
```

#### `ui/icons.py` (SVG System)

**Approach:**
```python
# SVG inline como string
SVG_CAMERA = '<svg ...>...</svg>'

# Função helper
def get_icon(svg_str: str, color: str = "#e0e0e0", size: int = 24) -> QIcon:
    # Substituir currentColor pelo color desejado
    svg_str = svg_str.replace('currentColor', color)
    
    # Renderizar com QSvgRenderer
    renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    
    return QIcon(pixmap)
```

**Vantagens:**
- Zero dependências externas (sem arquivos PNG)
- Fácil mudar cores dinamicamente
- Escalável (SVG vetorial)
- Leve (strings inline)

---

## 🔄 Thread Model

### Threads Ativas

```
Main Thread (Qt Event Loop)
├── UI rendering (QTimer 60fps)
├── Signal/slot processing
└── User input handling

Worker Thread (AppCore._connection_routine)
├── ADB operations (blocking I/O)
├── Socket connection
└── Device setup

Decoder Thread (VideoReceiver._receive_loop)
├── Socket reading (blocking I/O)
├── H.264 decoding
└── Frame conversion (av.VideoFrame → numpy)

Stats Thread (AppCore._stats_loop)
├── Frame counting
├── FPS calculation
└── Signal emission (1x/sec)

Virtual Cam Thread (AppCore._virtual_cam_loop)
├── Polling latest_frame
├── Sending to pyvirtualcam
└── Timing control
```

### Cross-Thread Data Flow

**Regra Ouro**: NumPy arrays são **thread-safe** porque:
1. Python GIL protege referência
2. Data é immutable (uma thread escreve, outras leem)
3. Evitar: av.VideoFrame nunca passa entre threads (segfault!)

**Exemplo Seguro:**
```python
# Thread 1 (Decoder) escreve:
arr = frame.to_ndarray(format='rgb24')
self.latest_frame = arr  # Substituição atomic (GIL)

# Thread 2 (Render) lê:
frame = self.video_receiver.latest_frame
if frame is not None:
    # Usar frame com segurança
    qimage = QImage(frame.data, ...)
```

**Sincronização:**
- **Signals**: Para avisar eventos (status, stats)
- **frame_count**: Counter simples (não precisa lock)
- **running**: Flag boolean (atomic)
- **Sem locks**: GIL é suficiente para este app

---

## 📡 Protocolos de Comunicação

### 1. Qt Signals (Local)

```python
# Emitir
core.connection_status.emit("Conectando...")

# Receber
window.core.connection_status.connect(window.update_status)

@Slot(str)
def update_status(self, text: str):
    # Executado automaticamente na main thread
    pass
```

### 2. ADB Shell (Android Bridge)

```bash
# Protocolo: texto simples com newlines
adb shell <command>

# Exemplos:
adb devices              # Lista devices
adb forward tcp:X Y      # Redireção de porta
adb push src dst         # Enviar arquivo
adb shell <cmd>          # Executar comando

# Parsing:
output = subprocess.run(..., capture_output=True, text=True)
lines = output.stdout.strip().split('\n')
```

### 3. Scrcpy Protocol (Binário)

Descrito acima em [Decoder Layer](#2-decoder-layer)

### 4. pyvirtualcam (Virtual Camera)

```python
# Inicializar
cam = pyvirtualcam.Camera(
    width=1920, height=1080, fps=30,
    fmt=pyvirtualcam.PixelFormat.RGB,
    backend='obs'
)

# Enviar frame (NumPy RGB24)
cam.send(numpy_array)

# Fechar
cam.close()
```

---

## 🎯 Padrões & Best Practices

### 1. Error Handling

```python
# Pattern: Try-catch com logging + signal
try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"Contexto: {e}")
    self.connection_status.emit(f"Erro: {str(e)}")
    return False
except Exception as e:
    logger.exception("Erro inesperado")  # Inclui traceback
    raise
```

### 2. Resource Cleanup

```python
# Pattern: Context manager (auto cleanup)
try:
    socket = socket.socket(...)
    socket.connect(...)
    # usar socket
finally:
    try:
        socket.close()
    except:
        pass  # Ignorar erro em close
```

### 3. Thread-Safe Queues (Futuro)

Para v0.3 (múltiplos devices):
```python
from queue import Queue

# Cada device tem seu próprio queue
devices_queue = Queue(maxsize=10)

# Producer (decoder thread)
devices_queue.put(frame, block=False)

# Consumer (render thread)
try:
    frame = devices_queue.get(timeout=0.01)
except queue.Empty:
    continue
```

### 4. Logging Pattern

```python
import logging
logger = logging.getLogger(__name__)

# Em entry points
logger.info("Iniciando conexão com device")

# Em loops
logger.debug("Frame decodificado: %dx%d", w, h)

# Em erros
logger.error("Socket timeout", exc_info=True)
```

---

## ⚡ Otimizações de Performance

### 1. Render Loop (60fps)

```python
# ✅ Correto: QTimer (não bloqueia main thread)
self.render_timer = QTimer()
self.render_timer.timeout.connect(self.pull_frame)
self.render_timer.start(16)  # 16ms ≈ 60fps

# ❌ Errado: while loop (congelaria UI)
while True:
    pull_frame()
    time.sleep(0.016)  # Bloqueia!
```

### 2. NumPy Array Contiguity

```python
# ✅ Garantir C-contiguous (necessário pyvirtualcam)
if not arr.flags['C_CONTIGUOUS']:
    arr = np.ascontiguousarray(arr)

# ❌ Evitar: Slicing cria views (não contíguas)
arr_rotated = np.rot90(arr)  # Pode não ser contígua!
```

### 3. Frame Conversion (Decoder)

```python
# ✅ Fast: Converter uma só vez na thread decoder
arr = frame.to_ndarray(format='rgb24')  # PyAV faz conversão C rápida
self.latest_frame = arr  # Store

# ❌ Lento: Converter na thread render (contention)
arr = frame.to_ndarray()  # Slow!
```

### 4. Virtual Camera Loop Timing

```python
# ✅ Timing controlado externamente
while enabled:
    frame = video_receiver.latest_frame
    if frame is not None and count != last_count:
        virt_cam.send(frame)
        last_count = count
    time.sleep(0.01)  # Backoff (evita busy-loop)

# ❌ Evitar: sleep_until_next_frame() causa GIL contention
cam.send(frame)
cam.sleep_until_next_frame()  # Trava GIL!
```

### 5. Socket Timeout

```python
# ✅ Detectar dead stream rapidamente
socket.settimeout(10.0)  # 10s timeout

# ❌ Sem timeout
socket.settimeout(None)  # Bloqueia infinito!
```

---

## 🚨 Error Handling Strategy

### Connection Errors

```python
# 1. Device não encontrado
→ wait_for_device() timeout
→ Avisar user: "Dispositivo não encontrado"
→ Retry automático: não (deixar user reconectar)

# 2. Server não iniciou
→ launch_android_server() retorna False
→ Avisar user: "Versão Android incompatível ou câmera em uso"

# 3. Socket timeout
→ Decoder thread percebe (10s timeout)
→ Emitir signal: "Conexão perdida"
→ AppCore para threads
→ User pode reconectar
```

### Recovery Strategy

```python
# Hot-swap é essencialmente: Stop → Clean → Start
def switch_camera_live(camera_id):
    # 1. Stop (gracioso)
    running = False
    video_receiver.stop()
    
    # 2. Clean (force kill se necessário)
    adb_manager.cleanup()
    adb_manager.cleanup_server_on_device()  # SIGTERM → SIGKILL
    
    # 3. Wait (deixar Android liberar recurso)
    sleep(1.2)
    
    # 4. Start (nova conexão)
    running = True
    _connection_routine()
```

---

## 🔌 Extensibilidade

### Adicionar Suporte Wi-Fi (v0.3)

```python
# 1. Novo módulo: transport/wifi_discovery.py
class WifiDiscovery:
    def discover_devices(self) -> List[Device]:
        # MDNS/Bonjour para encontrar devices
        pass

# 2. Modificar AdbManager
class TransportManager:  # Refatorar de AdbManager
    def __init__(self, transport_type: str):
        if transport_type == 'usb':
            self.transport = AdbManager()
        elif transport_type == 'wifi':
            self.transport = WifiManager()

# 3. AppCore escolhe transporte
core = AppCore(transport_type='wifi')
```

### Adicionar Suporte Áudio (v0.3)

```python
# 1. Novo módulo: audio/audio_receiver.py
class AudioReceiver:
    def start(self):
        # MediaProjection API Android 11+
        pass
    
    def get_audio_frame(self) -> np.ndarray:
        # Retornar samples PCM
        pass

# 2. Novo módulo: audio/audio_output.py
class AudioOutput:
    def send_frame(self, samples: np.ndarray):
        # Enviar para sistema audio Windows
        pass

# 3. AppCore coordena
self.audio_receiver = AudioReceiver()
self.audio_receiver.start()

# 4. Sync com vídeo (usar PTS)
video_pts = frame_timestamp
audio_pts = audio_timestamp
delay = sync_engine.calculate_delay(video_pts, audio_pts)
```

### Adicionar Suporte Múltiplos Devices

```python
# 1. Refatorar AppCore → per-device
class DeviceConnection:
    def __init__(self, device_serial: str):
        self.adb_manager = AdbManager(serial=device_serial)
        self.video_receiver = VideoReceiver()
        self.virtual_cam = VirtualCamOutput()

# 2. AppCore gerencia múltiplas
class AppCore:
    def __init__(self):
        self.connections = {}  # serial → DeviceConnection
    
    def add_device(self, serial: str):
        self.connections[serial] = DeviceConnection(serial)

# 3. UI adaptado para lista
device_list = [DeviceConnection(s) for s in connected_serials]
```

---

## 📈 Métricas & Performance

### Medição de Latência (Futuro)

```python
# Frame timestamps já presentes via PTS
# Adicionar medição completa:

class LatencyMonitor:
    def record_capture_time(self, pts: float):
        self.capture_time = pts
    
    def record_decode_time(self):
        self.decode_time = time.time()
    
    def record_render_time(self):
        self.render_time = time.time()
    
    @property
    def total_latency(self) -> float:
        # Diferença entre capture e render
        return self.render_time - self.capture_time
```

### FPS Calculation (Já implementado)

```python
# Stats loop: 1 frame count por segundo
fps = frame_count / elapsed
self.stats_updated.emit({'fps': fps})

# Frame count resetado a cada 1s (AppCore._stats_loop)
```

---

## 🧪 Testing Strategy (Futuro)

```python
# tests/test_adb_manager.py
def test_device_detection():
    mgr = AdbManager()
    devices = mgr.get_devices()
    assert len(devices) > 0

# tests/test_video_receiver.py
def test_socket_connection():
    # Mock socket para não precisar celular
    receiver = VideoReceiver()
    # ...

# tests/test_virtual_cam.py
def test_frame_send():
    cam = VirtualCamOutput()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cam.send_frame(frame)
    # Assert no erro
```

---

## 📚 Referências Técnicas

### Scrcpy
- [GitHub](https://github.com/Genymobile/scrcpy)
- Protocolo: Binário, H.264 raw
- Low-latency: ~100ms typical

### PyAV/FFmpeg
- [PyAV Docs](https://pyav.org/docs/develop/index.html)
- Context.decode() retorna lista de frames
- Frame.to_ndarray() para conversão NumPy

### PySide6
- [Qt for Python](https://doc.qt.io/qtforpython-6/)
- Signals marshalam threads automaticamente
- QTimer melhor que threading puro

### pyvirtualcam
- [GitHub](https://github.com/letmaik/pyvirtualcam)
- Backends: obs, unitycapture, gstreamer
- Requer array C-contiguous

---

**Documento atualizado**: 07/06/2026  
**Status**: Beta v0.2.0  
**Próximo Review**: Após implementação v2.0 (Wi-Fi + Áudio)
