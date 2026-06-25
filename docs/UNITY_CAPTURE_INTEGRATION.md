# Unity Capture — Documentação Técnica de Integração

> **FuriousCam Pro** | Versão 2.0 | Atualizado em: Junho/2026

---

## 1. Por que o Unity Capture foi adicionado?

### Contexto Histórico

Até recentemente, o FuriousCam Pro funcionava com dois drivers de câmera virtual:

- **OBS Studio (`OBS Virtual Camera`):** Funcionava via a biblioteca `pyvirtualcam`.
- **Streamlabs Desktop:** Funcionava porque o Streamlabs era baseado no OBS e registrava o driver com o mesmo nome `"OBS Virtual Camera"`. A nossa biblioteca encontrava esse nome e conectava normalmente.

### O Problema

A empresa Streamlabs, em decorrência de conflitos de direitos com o projeto OBS, foi obrigada a remover a marca "OBS" de seus produtos. Com isso, o driver que antes se chamava `"OBS Virtual Camera"` passou a se chamar `"Streamlabs Desktop Virtual Webcam"`.

A biblioteca `pyvirtualcam` — que utiliza um módulo compilado em C++ (`_native_windows_obs.pyd`) — tem o nome `"OBS Virtual Camera"` **fixo em código binário**, tornando impossível para o nosso aplicativo Python reconhecer o novo nome do driver do Streamlabs sem recompilar a biblioteca.

Além disso: o Streamlabs **nunca criou um driver de captura de entrada próprio**. O `"Streamlabs Desktop Virtual Webcam"` é um driver de **saída** (serve para enviar a live do Streamlabs para o Discord/Zoom). Para receber vídeo *de fora* (como do celular via FuriousCam), o Streamlabs depende de um **driver de câmera de entrada** separado — que era o `OBS Virtual Camera`.

### A Solução: Unity Capture

O **Unity Video Capture** é um driver DirectShow leve e open-source criado por [Hendrik Scheiber (schellingb)](https://github.com/schellingb/UnityCapture). Ele funciona como uma **câmera de entrada oficial do Windows**, independente do OBS ou Streamlabs.

Com ele, o fluxo de vídeo passa a ser:
```
Celular → FuriousCam Pro → Unity Video Capture (driver) → Streamlabs / OBS / Discord / TikTok
```

---

## 2. Arquitetura dos Drivers

| Driver | Tipo | Quem cria | Para que serve |
|---|---|---|---|
| `OBS Virtual Camera` | Entrada (captura) | OBS Studio | Injetar vídeo no OBS/Streamlabs via `pyvirtualcam` |
| `Streamlabs Desktop Virtual Webcam` | **Saída** (transmissão) | Streamlabs | Enviar a live pronta do Streamlabs para o Discord/Zoom |
| `Unity Video Capture` | Entrada (captura) | Unity Capture | Injetar vídeo em qualquer app sem depender do OBS |

> **Regra de ouro:** O FuriousCam Pro é uma **câmera** (entrada), não uma emissora (saída). Ele precisa de um driver de *entrada* para enviar o vídeo do celular para os programas de live.

---

## 3. Estrutura de Arquivos no Projeto

Após a integração, os arquivos necessários foram movidos para:

```
portables/
└── unity/
    ├── UnityCaptureFilter32.dll   ← driver para Windows 32-bit
    └── UnityCaptureFilter64.dll   ← driver para Windows 64-bit (principal)
```

> A pasta original `UnityCapture-master/` pode ser deletada com segurança pois os únicos arquivos necessários são as duas DLLs acima.

---

## 4. Arquivos Modificados/Criados

### `ui/install_dialog.py`

Contém três classes de diálogo:

#### `VirtualCamInstallDialog` (Opção 1 — OBS Studio)
- Informa o usuário que deve instalar o OBS Studio para usar a câmera virtual via `pyvirtualcam`.
- **Texto informativo adicionado:** "Tendo o OBS instalado, o driver dele também aparecerá e poderá ser usado dentro do seu Streamlabs Desktop ou TikTok Live."
- Não possui botão de instalação automática (aponta o usuário para o site oficial do OBS).

#### `UnityCaptureInstallDialog` (Opção 2 — Unity Capture)
- Detecta o estado atual do driver lendo o registro do Windows (chave `HKLM\SOFTWARE\Classes\CLSID\` via `DirectShow`).
- Exibe SVGs visuais (check verde / estrela amarela / alerta laranja) conforme o estado.
- Botão **Instalar Driver:** ativo somente se as DLLs existem e o driver **não** está registrado.
- Botão **Remover Driver:** ativo somente se o driver **está** registrado.
- Ao clicar em Instalar ou Remover, invoca `RegSvr32Worker` (thread separada) que executa `regsvr32` via PowerShell com elevação de administrador (`Start-Process -Wait -Verb RunAs`).
- Ao terminar a operação, chama `_update_state_ui()` que **atualiza a interface dinamicamente** sem precisar fechar e reabrir o diálogo.

#### `RegSvr32Worker`
- Executa `regsvr32 /s` (instalar) ou `regsvr32 /u /s` (remover) nas duas DLLs.
- Usa PowerShell com `-Wait` para garantir que o processo UAC termine antes de verificar o resultado.
- Emite sinal `finished(success: bool, message: str)` ao terminar.

### `ui/main_window.py`

- **Botão Câmera Virtual (Streamlabs / Web):** Toggle que ativa/desativa o backend `unitycapture`.
- **Botão "Gerenciar driver Universal...":** Abre o `UnityCaptureInstallDialog` a qualquer momento (mesmo sem vídeo ativo).
- Todos os diálogos são abertos com `dlg.open()` (não-bloqueante) em vez de `dlg.exec()`, **evitando que a conexão ADB caia** enquanto a janela está aberta.
- Instâncias dos diálogos são salvas em `self._unity_dlg` e `self._obs_dlg` para evitar que o Garbage Collector do Python destrua a janela prematuramente.

### `ui/icons.py`

Novos ícones SVG adicionados:
- `SVG_CHECK` — ícone de check (✓) para estado "instalado".
- `SVG_ALERT` — ícone de triângulo de alerta para estado "DLLs ausentes".
- `SVG_STAR` — ícone de estrela para estado "pronto para instalar".

### `main.py`

- `get_base_path()` atualizado para suportar `sys._MEIPASS` (PyInstaller), garantindo que as DLLs sejam encontradas quando o app roda como `.exe`.

### `furiousCam.spec`

- Adicionada a pasta `portables/unity/` em `datas` para que as DLLs sejam empacotadas automaticamente no build do PyInstaller.

---

## 5. Como Funciona o Registro do Driver

O Unity Capture usa o sistema `DirectShow` do Windows. Após instalar com `regsvr32`, o driver aparece em:
```
HKEY_LOCAL_MACHINE\SOFTWARE\Classes\CLSID\{YOUR-CLSID}\
```

A função `is_unity_capture_installed()` no `install_dialog.py` verifica essa chave do registro para determinar se o driver está ativo, garantindo uma detecção 100% confiável (sem depender de arquivos físicos ou de processos rodando).

---

## 6. Fluxo de Uso em Produção (`.exe`)

1. Usuário baixa e executa `FuriousCam.exe`.
2. PyInstaller extrai os arquivos para `sys._MEIPASS` (pasta temporária).
3. As DLLs em `portables/unity/` ficam disponíveis no caminho temporário.
4. Usuário abre o app, conecta o celular e inicia o stream.
5. Clica em **Câmera Virtual (Streamlabs / Web)**.
6. Se o driver não estiver instalado, o diálogo de instalação abre automaticamente.
7. Usuário clica em **Instalar Driver** → aprova o prompt de Administrador do Windows.
8. Driver fica registrado permanentemente no Windows (não precisa reinstalar a cada uso).
9. No Streamlabs/TikTok/Discord, selecionar `Unity Video Capture` como fonte de vídeo.

---

## 7. Decisões de Design

| Decisão | Motivo |
|---|---|
| `dlg.open()` em vez de `dlg.exec()` | Evita bloquear o loop de eventos Qt e derrubar a conexão ADB |
| Salvar dialog em `self._unity_dlg` | Evita que o Garbage Collector do Python destrua a janela antes dela fechar |
| PowerShell com `-Wait` | Garante sincronização: verifica o resultado só após o UAC terminar |
| Verificação via registro Windows (não por arquivo) | Mais confiável; detecta driver desregistrado mesmo que a DLL exista no disco |
| SVGs em vez de emojis | Emojis dependem da fonte do sistema; SVGs renderizam igual em qualquer Windows |
| `portables/unity/` em vez de `UnityCapture-master/Install/` | Estrutura de projeto mais limpa e semântica |

---

## 8. Compatibilidade

O Unity Video Capture, uma vez instalado, funciona como câmera de entrada em:
- ✔ OBS Studio
- ✔ Streamlabs Desktop
- ✔ TikTok Live Studio
- ✔ Discord
- ✔ Google Meet / Zoom
- ✔ Qualquer software que liste dispositivos de captura DirectShow

---

*Documentação gerada por: Antigravity (Google DeepMind) — FuriousCam Pro v2.0*
