# 📝 Changelog — FuriousCam Pro

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

---

## [2.1.0] — 2026-06-15

### ✨ Adicionado & Otimizado

#### Estabilidade Absoluta de Conexão USB (Anti-Zumbi)
- **Comportamento:** O aplicativo agora elimina sumariamente qualquer processo `adb.exe` que fique "pendurado" no Windows (zumbi), resolvendo o problema de ter que trocar de porta USB fisicamente quando o cabo dava mau contato.
- **Arquivos:** `core/adb_manager.py`
- **Detalhes:** 
  - Adicionado o comando nativo `taskkill /F /IM adb.exe /T` na rotina de parada do servidor ADB.
  - O sistema de Smart Reconnect agora usa essa limpeza profunda a cada tentativa, garantindo que o socket USB seja sempre liberado para uma reconexão limpa.

#### Responsividade da Interface (Sem Travamentos ao Fechar/Parar)
- **Comportamento:** A janela principal do aplicativo não engasga, não pisca e não mostra a "bolinha de carregamento" do Windows ao clicar em Parar ou ao tentar fechar o app.
- **Arquivos:** `core/app_core.py`, `ui/main_window.py`
- **Detalhes:**
  - O processamento lento de limpeza e comunicação com o celular no botão **Parar** foi movido para uma *background thread* (segundo plano).
  - Bloqueio inteligente da interface: o botão "Iniciar" fica desativado automaticamente até que a thread de limpeza confirme que o ADB e o celular foram 100% desligados, evitando *race conditions*.
  - O fechamento da janela (botão X) agora executa um `taskkill` de forma 100% assíncrona, resultando num encerramento instantâneo do aplicativo.

---

## [0.4.0] — 2026-06-06

### ✨ Adicionado & Otimizado

#### Smart Reconnect Automático (Retry com Backoff Exponencial)
- **Comportamento:** O aplicativo agora detecta automaticamente quedas inesperadas de conexão (seja USB desconectado ou Wi-Fi oscilando) e tenta restabelecer a conexão de forma transparente sem interromper a Câmera Virtual no OBS (evitando tela preta).
- **Arquivos:** `core/app_core.py`
- **Detalhes:**
  - Criação de uma rotina de reconexão inteligente em thread secundária, aplicando backoff exponencial com teto de 10 segundos.
  - Limpeza automática de conexões residuais e sockets antigos no dispositivo Android antes de cada nova tentativa.
  - A Virtual Camera do OBS é mantida ativa durante o processo, congelando no último frame com sucesso para que o feed no OBS não caia/desapareça.
  - Cancelamento instantâneo da rotina de reconexão caso o usuário decida clicar manualmente no botão "Parar".


#### Otimização do Filtro de Redução de Ruído (DSP de Dupla Velocidade)
- **Comportamento:** O filtro de redução de ruído espectral foi otimizado para eliminar pequenos assobios/apitos transitórios (chirps/clicks) no ataque da voz.
- **Arquivos:** `decoder/audio_receiver.py`
- **Detalhes:**
  - **Attack Rápido & Release Suave:** Implementação de suavização temporal diferenciada usando `np.where`. Quando a voz inicia (ganho subindo), a comporta de ruído abre instantaneamente (20ms/1 frame) para não criar chiado de início de frase. Quando a voz silencia (ganho descendo), a comporta fecha lentamente para manter a cauda de reverberação das palavras de forma natural.
  - **Recaptura Dinâmica no Botão:** Ao ligar a Redução de Ruído na UI, o app limpa perfis antigos e inicia uma captura fresh nos próximos 0.5s de silêncio, garantindo fidelidade perfeita com o ruído atual do ambiente.

#### Correção de Rotação de Câmera (Grau Zero)
- **Comportamento:** A câmera não fica mais de ponta cabeça ou espelhada erroneamente na orientação "Em pé" (0°).
- **Arquivos:** `core/app_core.py`, `ui/main_window.py`
- **Detalhes:**
  - Implementado compensador dinâmico `effective_rotation` para corrigir a diferença de ângulo base entre câmeras traseiras (offset 90°) e frontais (offset 270°).

#### Conexão Wi-Fi Mais Robusta e Persistente
- **Comportamento:** O modo Wi-Fi (manual IP e Híbrido) não reseta mais acidentalmente para o USB ao clicar em "Parar", e os bugs de "conexão recusada" no fluxo IP manual foram resolvidos.
- **Arquivos:** `transport/wifi_manager.py`, `core/app_core.py`, `ui/main_window.py`
- **Detalhes:**
  - O fluxo manual de IP agora emite `adb tcpip 5555` proativamente quando o celular está via USB (igual ao fluxo híbrido), evitando erros de porta inativa.
  - A variável `wifi_fallback_ip` agora persiste após um `stop_connection`, garantindo que cliques sucessivos em "Iniciar" reconectem ao Wi-Fi sem reiniciar a busca USB.
  - Correção na interface do usuário para limpar o último frame renderizado e evitar "vídeo fantasma" ao interromper a transmissão.

#### Hot-Swap Inteligente de Microfone (Headset)
- **Comportamento:** O aplicativo detecta automaticamente quando um fone de ouvido é conectado/desconectado do aparelho e altera o microfone on-the-fly, sem interromper o vídeo.
- **Arquivos:** `core/app_core.py`, `transport/wifi_manager.py`
- **Detalhes:**
  - Adicionada thread leve `_headset_monitor_loop` que verifica o estado `wired_headset` via ADB a cada 3 segundos.
  - Dispara `_restart_audio_for_headset()` que recria o `AudioReceiver` silenciosamente sem derrubar o `VideoReceiver` (garantindo estabilidade de 30 FPS constantes durante o hot-swap).

---

## [0.3.2] — 2026-06-06

### ✨ Adicionado & Otimizado

#### Reconstrução do Motor de Áudio (Alta Performance & Monitoramento)
- **Comportamento:** O sistema de áudio foi inteiramente reescrito para eliminar engasgos de vídeo (fps drops) causados pela redução de ruído pesada, além de trazer feedback em tempo real e roteamento.
- **Arquivos:** `decoder/audio_receiver.py`, `core/app_core.py`, `ui/main_window.py`
- **Detalhes:**
  - **Algoritmo de Subtração Espectral Customizado:** Substituída a biblioteca pesada (`noisereduce`) por uma implementação em NumPy puro. O processamento caiu de ~50ms/frame para ~0.1ms/frame, resgatando a taxa de quadros (30 FPS constante).
  - **VU Meter Ativo:** A UI agora responde de forma precisa (escala logarítmica dB) à entrada do microfone do celular.
  - **Ouvir Retorno (Monitor de Áudio):** Implementado `QAudioSink` (PySide6) em push mode para envio do áudio Float32 direto para a placa de som nativa do Windows, sem delay.
  - **Roteamento Inteligente Anti-VB-Cable:** O motor de monitoramento agora detecta se o Windows está usando um cabo virtual como dispositivo padrão e, de forma inteligente, varre o sistema atrás de um alto-falante real para reproduzir o teste.
  - **Mute Inteligente (Auto-Mute):** O fluxo de áudio foi dividido em vias independentes para transmissões e retornos locais. Se o usuário escolher um fone normal na caixa de seleção, o app se "muta" automaticamente e só reproduz o áudio se o "Me Ouvir" for ativado, enquanto que cabos virtuais tocam o fluxo principal 100% do tempo.
  - **Seletor de Saída de Áudio:** Adicionado QComboBox dinâmico à UI para redirecionamento do output de áudio (Alto-falantes, Fones, Virtual Cables) on-the-fly, salvando automaticamente a preferência do usuário no `config.ini`.

#### Log Viewer Integrado (UI)
- **Comportamento:** Janela secundária (não-modal) para monitoramento de eventos em tempo real, sem precisar abrir terminal.
- **Arquivos:** `ui/log_viewer.py`, `ui/icons.py`, `ui/main_window.py`
- **Detalhes:**
  - Adicionado botão "Ver Logs do Sistema" no menu de configurações da `MainWindow`.
  - Auto-refresh de log a cada 1s otimizado (só recarrega se o filesize mudar).
  - Syntax-highlight inteligente (cores para INFO, ERROR, WARNING, DEBUG).
  - Sistema de busca inline (Ctrl+F) com highlight amarelo, contagem de ocorrências e setas SVG para navegação.
  - Alternância de auto-scroll, botão de limpar view e copiar clipboard.

#### Monitoramento Limpo da Stream (Telemetria Interna)
- **Comportamento:** Adicionados logs estratégicos de saúde da transmissão sem poluir o console.
- **Arquivos:** `core/app_core.py`, `decoder/video_receiver.py`
- **Detalhes:**
  - Emite log de recebimento do "Primeiro frame decodificado" na sessão.
  - Pulso periódico a cada 10 segundos indicando tempo de uptime, FPS real, latência, resolução, Mbps, conexão (USB/Wi-Fi) e status da Virtual Camera.
  - Resumo de final de sessão ao parar, computando a duração total e a contagem total de frames trafegados.

---

## [2.0] — 2026-06-07

### ✨ Adicionado

#### WiFi Fallback Automático
- **Comportamento:** Tenta USB (5s) → Se falhar e IP salvo em config.ini, tenta WiFi automaticamente
- **Arquivo:** `core/app_core.py` (_connection_routine Step 1-6)
- **Detalhes:**
  - USB timeout reduzido de 10s para 5s em `adb_manager.wait_for_device()`
  - Fallback automático se USB falhar e `wifi_fallback_ip` definido
  - Sleep 0.5s para ADB sincronizar após WiFi connect
  - Verificação de device novamente após WiFi

#### Cleanup Inteligente
- **Comportamento:** ADB mata completamente APENAS ao fechar app, não durante operações
- **Arquivo:** `core/app_core.py`, `ui/main_window.py`
- **Detalhes:**
  - `stop_connection()` — Para stream + remove port forward, mantém ADB
  - `cleanup_on_exit()` — Para tudo + mata ADB server (chamado em closeEvent)
  - Benefício: WiFi fallback não interrompe por kill-server

#### Retry no Push Server
- **Problema:** Xiaomi Note 7 retornava EOF mesmo com arquivo enviado
- **Solução:** Push com retry 2x + detecta sucesso independente de erro EOF
- **Arquivo:** `core/adb_manager.py` (push_server)
- **Detalhes:**
  - Tenta 2x com 1s delay entre tentativas
  - Considera sucesso se "pushed" em stdout mesmo com "EOF" em stderr
  - Sleep 0.5s após sucesso para filesystem sync

#### Aviso de Câmera Não Suportada
- **Comportamento:** Popup dialog quando câmera cai (Android < 12 ou aparelho sem suporte)
- **Arquivo:** `core/app_core.py`, `ui/main_window.py`
- **Detalhes:**
  - Signal `show_warning(title, msg)` emite de AppCore
  - Slot `show_warning_dialog()` em MainWindow mostra QMessageBox
  - Mensagem educativa sobre suporte varia por modelo/fabricante
  - Fallback para screen mirror automático

### 🔧 Modificado

- **core/adb_manager.py**
  - `wait_for_device()` — 10 → 5 iterações (5s timeout)
  - `launch_android_server()` — Reseta `fallback_used` flag
  - `_launch_screen_fallback()` — Seta `fallback_used = True`
  - Adicionado `__init__: fallback_used = False`

- **core/app_core.py**
  - `launch_android_server()` — Checa `fallback_used` e emite aviso
  - Novo signal: `show_warning(str, str)` para diálogos
  - `stop_connection()` — Sem `stop_adb_server()` (apenas para operações)
  - Novo método: `cleanup_on_exit()` (com `stop_adb_server()`)

- **ui/main_window.py**
  - `closeEvent()` — Chamada `cleanup_on_exit()` em vez de `stop_connection()`
  - Novo slot: `show_warning_dialog(title, msg)` para QMessageBox
  - Conecta signal `core.show_warning` em `__init__`
  - `update_status()` — Detecção de erro mais específica (evita falsos positivos)

- **furiousCam.spec**
  - Ícone mudado: `furiouscam.ico` → `furiouscam_safe.ico`

- **ui/main_window.py** (ícone)
  - Referências `furiouscam.ico` → `furiouscam_safe.ico` (melhor qualidade)

### 🐛 Corrigido

- **WiFi Fallback não funcionava** → Removido kill-server no retry de WiFi
- **App levava 10s para conectar USB** → Reduzido para 5s
- **Xiaomi dava erro EOF em push** → Retry com sucesso mesmo com EOF
- **Mensagem de erro interrompia WiFi fallback** → Detecção mais específica em update_status
- **Diálogo de câmera não aparecia** → Novo signal/slot system

### 📊 Versão

- **Arquivo:** `README.md`, `RELEASE_NOTES.md`
- **De:** v0.3.0 (90% completo)
- **Para:** v2.0 (100% completo)
- **Fases Completadas:** Fase 3 (WiFi Fallback + Cleanup)

---

## [0.3.0] — 2026-05-XX

### ✨ Adicionado

#### Bugs Corrigidos em v0.3.0
- Tray mostrava status errado ao reconectar via WiFi
- Latência mostrava 0ms após 50 segundos (PTS não reset)
- Config.ini não sincronizava ao reconectar

#### Build & Distribuição
- PyInstaller spec otimizado (122.7 MB exe)
- Scripts automáticos: build.bat, clean_build.bat
- Estrutura one-dir para distribuição fácil

#### Logging & Error Handling
- Logging estruturado com timestamps
- Exception handling em pontos críticos
- Error signals com QDialog integrado

---

## Padrão de Versionamento

**MAJOR.MINOR.PATCH**
- **MAJOR:** Quebra compatibilidade ou feature grande
- **MINOR:** Feature nova (backwards compatible)
- **PATCH:** Bug fix

Exemplo: `0.3.1`
- 0 = Foundation phase (alpha/beta)
- 3 = 3 minor features completadas
- 1 = 1 patch aplicado

---

## Roadmap Futuro

Este projeto está concluído como versão `2.0` e não possui roadmap de desenvolvimento adicional.

---

**Última atualização:** 2026-05-30
