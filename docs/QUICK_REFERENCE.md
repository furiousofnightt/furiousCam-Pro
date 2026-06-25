# FuriousCam Pro — Quick Reference para Desenvolvedores

**Guia rápido para entender, modificar e estender o projeto**

---

## 📊 Visão Rápida do Projeto

```
Objetivo: Celular Android → Webcam Windows para OBS Studio
Linguagem: Python 3.10+
UI Framework: PySide6 (Qt)
Versão: 2.0 Final (100% completo)
```

---

## 🚀 Startup Rápido

### 1. Instalar
```powershell
cd furiousCam-mobile-win
pip install -r requirements.txt
python main.py
```

### 2. Conectar Celular
```
1. USB Debug ON no Android
2. Autorizar conexão no popup
3. Clique "Conectar Câmera" na app
4. Aguarde 2-3 segundos
```

### 3. OBS
```
1. Ativar "Câmera Virtual" na app
2. No OBS: Add Source → Video Capture Device → OBS Virtual Camera
3. Pronto!
```

### 4. Build para Distribuição
```powershell
# Automático (RECOMENDADO):
build.bat

# Resultado:
# dist/FuriousCam/FuriousCam.exe  (122 MB)
# Distribua: dist/FuriousCam/ (inteira como ZIP)
```

---

## 🧹 Limpeza & Rebuild

```powershell
# Se tiver build antigo ou erros:
clean_build.bat       # Remove build/ dist/ .egg-info/
build.bat             # Compila novo
```

---

## 📁 Estrutura Essencial

```
core/
├── app_core.py          # Controlador central (AppCore class)
└── adb_manager.py       # Interface Android (AdbManager class)

decoder/
└── video_receiver.py    # H.264 decode (VideoReceiver class)

obs/
└── virtual_cam.py       # OBS output (VirtualCamOutput class)

transport/
└── wifi_manager.py      # Wi-Fi Manager (WifiManager class)

ui/
├── main_window.py       # UI principal (MainWindow class)
├── camera_window.py     # Janela flutuante (CameraOnlyWindow class)
├── icons.py             # SVG icons
└── install_dialog.py    # OBS setup guide

main.py                 # Entry point
config.ini              # Configurações salvas
requirements.txt        # pip dependencies
```

---

## 🔑 Classes Principais

### AppCore (Orquestração)
```python
from core.app_core import AppCore

core = AppCore(base_path)

# Settings
core.set_camera(0)              # 0=back, 1=front
core.set_fps(30)
core.set_bitrate(8_000_000)
core.set_resolution(1920, 1080)
core.set_rotation(90)
core.set_mirrored(True)

# Lifecycle
core.start_connection()          # Inicia em thread
core.stop_connection()           # Para tudo

# OBS
core.enable_virtual_cam()
core.disable_virtual_cam()

# Signals
core.connection_status.connect(slot)   # str: status message
core.stats_updated.connect(slot)       # dict: {fps, resolution, ...}
core.camera_swapped.connect(slot)      # bool: hot-swap completo
core.stream_info_ui.connect(slot)      # width, height (stream metadata)

# Wi-Fi Detection
core.is_connection_wireless()         # bool: True se Wi-Fi, False se USB
```

### MainWindow (UI)
```python
from ui.main_window import MainWindow

window = MainWindow(core)
window.show()

# Slots (automaticamente chamadas)
def on_start_clicked(self):         # "Conectar" clicado
def on_stop_clicked(self):          # "Parar" clicado
def update_status(self, text):      # Status do core
def update_stats(self, stats_dict): # Stats atualizadas
def on_camera_swapped(self):        # Hot-swap completo
```

### VideoReceiver (Decoder)
```python
from decoder.video_receiver import VideoReceiver

receiver = VideoReceiver(host="127.0.0.1", port=27183)
receiver.start()
receiver.stop()

# Propriedades
frame = receiver.latest_frame    # numpy array RGB (H, W, 3)
count = receiver.frame_count     # Frame counter

# Signals
receiver.error_occurred.connect(slot)   # str: error message
receiver.stream_info.connect(slot)      # dict: {codec, width, height, source}
```

### AdbManager (Android Bridge)
```python
from core.adb_manager import AdbManager

mgr = AdbManager(adb_path, jar_path)

# Lifecycle
mgr.start_server()
mgr.wait_for_device()               # Polling 5x 1s (USB), retorna bool
mgr.push_server()                   # adb push .jar
mgr.setup_port_forward()            # adb forward
mgr.launch_android_server(...)      # Lança scrcpy server
mgr.cleanup()                       # Limpeza

# Wi-Fi Methods
mgr.get_device_ip()                 # Detecta IP do dispositivo
mgr.enable_tcpip()                  # Ativa TCP/IP na porta 5555
mgr.connect_direct_ip(ip:port)      # Conecta via IP direto
mgr.disconnect_ip(ip:port)          # Desconecta IP

# Propriedades
device_serial = mgr.device_serial   # "abc123xyz" ou "192.168.1.15:5555"
local_port = mgr.local_port         # 27183
```

### WifiManager (Wi-Fi Manager)
```python
from transport.wifi_manager import WifiManager

wifi_mgr = WifiManager(app_core, main_window)

# Actions
wifi_mgr.action_hybrid_mode()       # Modo Híbrido Automático
wifi_mgr.action_connect_ip_manual() # Conexão IP Manual
wifi_mgr.action_return_to_usb()     # Voltar para USB

# Signals
wifi_mgr.hybrid_finished.connect(slot)      # bool, ip_with_port
wifi_mgr.manual_ip_finished.connect(slot)    # bool, ip_with_port
wifi_mgr.usb_return_finished.connect(slot)  # return to USB completo

# State
wifi_mgr.is_wireless                # bool: True se Wi-Fi ativo
wifi_mgr.connected_ip                # str: IP atual ou None
```

---

## 🔄 Fluxo de Execução

```
main.py
  ↓
QApplication.exec()
  ↓
MainWindow.__init__()
  └→ AppCore.__init__()
     └→ AdbManager + VideoReceiver + WifiManager inicializados
  └→ Conectar signals do Core à MainWindow
  └── WifiManager signals conectados
  └── Carregar configurações do config.ini
  └── Renderização 60fps QTimer
  ↓
User clica "Conectar Câmera"
  ↓
MainWindow.on_start_clicked()
  ↓
AppCore.start_connection()
  └→ Thread worker: AppCore._connection_routine()
     ├→ AdbManager.start_server()
     ├→ Step 1: AdbManager.wait_for_device()  [USB, 5s timeout]
     ├─→ If USB fails and WiFi_IP saved:
     │  ├→ Step 3: AdbManager.connect_direct_ip(wifi_ip)
     │  ├→ Step 5: Sleep 0.5s para sincronização
     │  └→ Step 6: AdbManager.wait_for_device()  [WiFi verify]
     ├→ Step 7: AdbManager.push_server()  [Retry 2x para Xiaomi EOF]
     ├→ Step 8: AdbManager.setup_port_forward()
     ├→ AdbManager.launch_android_server()  [Camera or Fallback Screen]
     │  └→ If camera fails on Android < 12: auto-fallback screen + popup
     └→ VideoReceiver.start()
        └→ Thread decoder: VideoReceiver._receive_loop()
           ├→ Socket connect
           ├→ H.264 decode FFmpeg
           └→ latest_frame = numpy array
  └→ Thread stats: AppCore._stats_loop()
     └→ 1x/sec: stats_updated.emit()
  └── (Optional) AppCore.enable_virtual_cam()
     └→ Thread virt_cam: AppCore._virtual_cam_loop()
        └→ Envia latest_frame → OBS
  ↓
MainWindow.pull_frame() [QTimer 60fps]
  ├→ Pega latest_frame
  └→ QImage → VideoWidget.paintEvent()
  ↓
User clica "Parar"
  ↓
MainWindow.on_stop_clicked()
  ↓
AppCore.stop_connection()
  ├→ running = False
  ├→ VideoReceiver.stop()
  ├→ AdbManager.cleanup()
  ├→ VirtualCam.stop()
  └→ Todas threads encerram

Wi-Fi Flow (Modo Híbrido):
User clica "Ativar Wi-Fi (Modo Híbrido)"
  ↓
WifiManager.action_hybrid_mode()
  └→ Thread: WifiManager._hybrid_task()
     ├→ Para conexão atual se existente
     ├→ AdbManager.get_device_ip()
     ├→ AdbManager.enable_tcpip()
     ├→ AdbManager.connect_direct_ip(ip:5555)
     └→ Salva IP em config.ini
  ↓
MainWindow.on_start_clicked() (reconecta via Wi-Fi)
```

---

## 📝 Configurações e Persistência

### config.ini
```ini
[video]
fps_index = 1              # 0=60, 1=30, 2=24
res_index = 2              # 0=4K, 1=2K, 2=1080p, 3=720p, 4=480p
cam_index = 0              # 0=back, 1=front
mirror = true
rotation = 0
bitrate = 8

[network]
last_ip = 192.168.1.15:5555  # Último IP Wi-Fi conectado
```

### Carregar Configurações
```python
# ui/main_window.py
settings = QSettings("config.ini", QSettings.IniFormat)

fps_idx = settings.value("video/fps_index", 1, type=int)
res_idx = settings.value("video/res_index", 2, type=int)
cam_idx = settings.value("video/cam_index", 0, type=int)
mirror = settings.value("video/mirror", True, type=bool)
rotation = settings.value("video/rotation", 0, type=int)
bitrate = settings.value("video/bitrate", 8, type=int)
last_ip = settings.value("network/last_ip", "", type=str)
```

### Salvar Configurações
```python
settings.setValue("video/fps_index", combo_fps.currentIndex())
settings.setValue("video/res_index", combo_res.currentIndex())
settings.setValue("video/cam_index", combo_camera.currentIndex())
settings.setValue("video/mirror", btn_mirror.isChecked())
settings.setValue("video/rotation", self._rotation)
settings.setValue("video/bitrate", slider_bitrate.value())
settings.setValue("network/last_ip", ip_with_port)
```

---

## 🎨 UI Components Novos

### FPS Sparkline
```python
# Histograma de FPS (últimos 30 segundos)
class FpsSparkline(QWidget):
    BAR_COUNT = 30
    TARGET_FPS = 60

    def push(self, fps: float):
        self._history.pop(0)
        self._history.append(min(fps, self.TARGET_FPS))
        self.update()

    def paintEvent(self, event):
        # Desenha barras coloridas baseadas no FPS
        # verde >= 50fps, amarelo >= 25fps, vermelho < 25fps
```

### Settings Menu (Gear Icon)
```python
# Menu dropdown nativo com opções
self._settings_menu = QMenu(self)
self._settings_menu.addAction("Ativar Câmera Virtual (OBS)")
self._settings_menu.addAction("Janela Flutuante de Câmera")

# Wi-Fi Submenu
wifi_submenu = QMenu("📡 Conexão Wi-Fi", self._settings_menu)
wifi_submenu.addAction("Ativar Wi-Fi (Modo Híbrido Automático)")
wifi_submenu.addAction("Conectar por Endereço IP Manual")
wifi_submenu.addAction("Voltar para Cabo USB")
```

### Auto-Rotate
```python
# Detecta orientação do stream automaticamente
@Slot(int, int)
def _on_stream_info_auto_rotate(self, stream_w: int, stream_h: int):
    """Auto-rotate quando stream conecta pela primeira vez."""
    if self._rotation == 0 and stream_h > stream_w and stream_w > 0:
        self._set_rotation(90)  # Portrait → Landscape
```

### Wheel Blocker
```python
# Impede scroll em ComboBox/Slider no sidebar
class WheelBlocker(QObject):
    def eventFilter(self, obj, event):
        if event.type() == event.Type.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)

# Instalar nos widgets
widget.installEventFilter(self._wheel_blocker)
```

---

## 💡 Padrões de Código

### Adicionando Nova Feature

**Exemplo: Adicionar botão "Reset All Settings"**

#### 1. Lógica (AppCore)
```python
# core/app_core.py

def reset_settings(self):
    """Reset para padrões de fábrica."""
    self.fps = 30
    self.bitrate = 8_000_000
    self.width = 1920
    self.height = 1080
    self.rotation = 0
    self.is_mirrored = True
    self.camera_id = 0
```

#### 2. UI (MainWindow)
```python
# ui/main_window.py

# No _build_ui(), adicionar botão:
self.btn_reset = QPushButton(" Reset", objectName="btnCamFlip")
self.btn_reset.clicked.connect(self.on_reset_clicked)
sb_layout.addWidget(self.btn_reset)

# Handler:
def on_reset_clicked(self):
    """Resetar todas as configurações."""
    self.core.reset_settings()
    # Atualizar UI
    self.combo_res.setCurrentIndex(2)  # Full HD
    self.combo_fps.setCurrentIndex(1)  # 30 FPS
    self.slider_bitrate.setValue(8)
    # etc
```

### Adicionando Novo Signal

**Exemplo: Adicionar sinal para detectar erro crítico**

```python
# core/app_core.py

class AppCore(QObject):
    critical_error = Signal(str)  # Novo signal
    
    def _connection_routine(self):
        try:
            ...
        except Exception as e:
            logger.error(f"Erro crítico: {e}")
            self.critical_error.emit(str(e))

# ui/main_window.py

self.core.critical_error.connect(self.on_critical_error)

@Slot(str)
def on_critical_error(self, error_msg: str):
    """Mostrar diálogo ou aviso crítico."""
    print(f"⚠️ Erro crítico: {error_msg}")
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Em qualquer arquivo:
logger.info("Evento importante")
logger.warning("Algo suspeito")
logger.error("Erro recoverable")
logger.debug("Info detalhada (dev only)")

# Arquivo de log automático:
# logs/furiouscam.log
```

---

## 🔍 Debugging

### Ver Logs em Tempo Real
```powershell
python main.py
# ou
tail -f logs/furiouscam.log
```

### Debugging Celular
```powershell
# Ver streams ativas
adb shell netstat -an | grep scrcpy

# Ver processo scrcpy
adb shell ps | grep scrcpy

# Matar processo (teste recovery)
adb shell pkill -f scrcpy
```

### Debugging OBS
```
1. Abrir OBS
2. Ferramentas → Log Files → Show Log File
3. Procurar por "OBS Virtual Camera" ou "obs-virtualcam"
```

---

## ⚡ Performance Tips

### FPS Baixo?
```
1. Aumentar bitrate (slider)
2. Reduzir resolução (dropdown)
3. Reduzir FPS para 30
4. Verificar CPU (Task Manager)
5. Tentar câmera traseira (mais rápida)
```

### Latência Alta?
```
1. Verificar CPU load
2. Fechar apps pesados
3. Usar USB 3.0 (se disponível)
4. Evitar Wi-Fi próximo (v0.3)
5. Verificar bitrate (não muito baixo)
```

### Memory Leak?
```
1. Monitorar memory no Task Manager
2. Se cresce: procurar por ciclos não-fechados
3. Verificar thread cleanup em stop_connection()
```

---

## 🧪 Testes Manuais

### Teste 1: Conexão USB Básica
```
1. Conectar Android
2. Clique "Conectar"
3. ✅ Preview aparece em 2-3s
4. ✅ Stats mostram FPS > 0
```

### Teste 2: Hot-Swap
```
1. Stream ativo
2. Clique "Alternar Câmera"
3. ✅ Câmera muda sem piscar (OBS não vê preto)
4. ✅ Stats continuam
```

### Teste 3: OBS Integration
```
1. OBS aberto
2. Ativar "Câmera Virtual" na app
3. OBS: Add Source → Video Capture → OBS Virtual Camera
4. ✅ Preview aparece no OBS
5. ✅ Frames fluem continuamente
```

### Teste 4: Janela Flutuante
```
1. Clique "Janela de Câmera"
2. ✅ Nova janela (borderless)
3. ✅ Sempre no topo
4. ✅ Drag/resize funciona
5. ✅ Duplo clique = fullscreen
```

### Teste 5: Desconexão
```
1. Desconectar USB do celular
2. ✅ Status: "Conexão perdida"
3. ✅ Preview fica cinza
4. ✅ App não trava
5. ✅ Reconectar funciona
```

---

## 🔧 Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| "Dispositivo não encontrado" | USB Debug ON, autorizar, tentar outro cabo |
| "Falha ao enviar servidor" | Verificar furious-core.jar em portables/adb/ |
| "OBS não vê câmera virtual" | Instalar OBS >= 27, abrir Ferramentas > Start Virtual Camera |
| "Apenas câmera traseira" | Android pode não ter câmera frontal |
| "Congelamento UI" | Nenhuma operação bloqueadora na main thread |
| "Memory leak" | Verificar cleanup em stop_connection() |
| "High latency" | Reduzir resolução ou aumentar bitrate |

---

## 📚 Arquivos Documentação

| Arquivo | Conteúdo |
|---------|----------|
| **README.md** | Visão geral, instalação, uso, status |
| **ARCHITECTURE.md** | Detalhes técnicos, fluxos, padrões |
| **QUICK_REFERENCE.md** | Este arquivo (referência rápida) |
| **planejamento_furiouscam_pro.md** | Roadmap, requisitos, features |

---

## 🚀 Projeto concluído
FuriousCam Pro está finalizado na versão `2.0`. Não há próximos passos planejados neste repositório.

### 1️⃣ Execução Final
```bash
# Execute o aplicativo finalizado
python main.py
```

### 2️⃣ Distribuição
Use `build.bat` para gerar o pacote final e compacte `dist/FuriousCam` como `furiouscam-executavel-v2.0.zip`.

### 3️⃣ Uso
- Execute `FuriousCam.exe`
- Conecte o celular via USB ou Wi-Fi
- Abra OBS e use a câmera virtual

Novo arquivo: audio/audio_receiver.py
MediaProjection API Android 11+
Sincronização com PTS vídeo
```

### 3️⃣ Config Persistência
```
Novo arquivo: config/settings.py
Salvar settings em JSON
Carregar ao iniciar
```

---

## 📞 Referência Rápida de Métodos

### AppCore
```python
start_connection()              # Inicia conexão
stop_connection()               # Para conexão
set_camera(id)                  # 0 ou 1
set_fps(30)                     # 24, 30, 60
set_bitrate(8_000_000)          # 2M - 20M
set_resolution(1920, 1080)      # Qualquer
set_rotation(90)                # 0, 90, 180, 270
set_mirrored(True)              # Mirror/flip
switch_camera_live(id)          # Hot-swap
enable_virtual_cam()            # OBS output
disable_virtual_cam()           # Parar OBS output
```

### VideoReceiver
```python
start()                         # Inicia decode
stop()                          # Para decode
latest_frame                    # numpy array (H, W, 3) RGB
frame_count                     # Contador frames
```

### MainWindow
```python
pull_frame()                    # Renderizar (QTimer 60fps)
update_status(text)             # Atualizar label status
update_stats(dict)              # Atualizar stats badges
on_camera_swapped()             # Hot-swap completo
```

---

## 🎨 UI Quick Style

```python
# Usar estes IDs para styling:
QPushButton#btnStart            # Verde (conectar)
QPushButton#btnStop             # Vermelho (parar)
QPushButton#btnCamFlip          # Azul claro (settings)
QComboBox                       # Dropdown padrão
QSlider                         # Bitrate slider
QLabel#statusLabel              # Status bar
QLabel#recIndicator             # Live indicator
QFrame#sidebar                  # Lado esquerdo
QFrame#topbar                   # Topo
QFrame#statsBar                 # Stats bottom
```

---

**Última atualização**: 29/05/2026  
**Para questões**: Consulte ARCHITECTURE.md para detalhes aprofundados
