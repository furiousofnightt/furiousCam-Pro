# 📖 Documentação FuriousCam Pro — Índice Completo

> Projeto pessoal: Usar Android como webcam no OBS Studio via USB/Wi-Fi

---

## 📊 Status Atual

```
Versão: 2.0 Final
Progresso: 100% Completo
Última atualização: 07/06/2026

✅ USB + H.264 Decode + OBS Integration
✅ Wi-Fi Híbrido (Auto-IP)
✅ Áudio integrado
```

---

## 📚 Documentação Disponível

### 1. 📖 **README.md** — Para Todos
**Comece aqui!** Visão geral, como instalar, como usar.

```
Seções:
├── Visão Geral (o que é, objetivo)
├── Status Atual (% completo, fases)
├── Características (o que funciona)
├── Requisitos (Windows, Android, Python)
├── Instalação (passo a passo)
├── Como Usar (fluxo básico)
├── Troubleshooting (resolvendo problemas)
└── Referências (links úteis)
```

**Leia se**: Quer entender rapidamente o projeto, instalar, usar, ou resolver problemas.

---

### 2. 🏗️ **ARCHITECTURE.md** — Para Desenvolvedores
**Documento técnico aprofundado.** Entender como funciona por dentro.

```
Seções:
├── Visão Geral da Arquitetura (layers)
├── Fluxo de Dados (completo, com diagrama ASCII)
├── Camadas do Sistema (Core, Decoder, OBS, UI)
├── Thread Model (múltiplas threads, sincronização)
├── Protocolos de Comunicação (Qt, ADB, Scrcpy, Virtual Camera)
├── Padrões & Best Practices (como codificar)
├── Otimizações de Performance (60fps, threads)
├── Error Handling (estratégia de recuperação)
├── Extensibilidade (como adicionar features)
└── Testing Strategy (testes futuros)
```

**Leia se**: Quer entender fluxo de dados, modificar código, adicionar features, ou debugar problemas técnicos.

---

### 3. ⚡ **QUICK_REFERENCE.md** — Cheat Sheet
**Guia rápido para desenvolvedores.** Referência sem fluff.

```
Seções:
├── Startup Rápido (instalar, rodar)
├── Estrutura Essencial (arquivos principais)
├── Classes Principais (AppCore, MainWindow, etc)
├── Fluxo de Execução (alto nível)
├── Padrões de Código (exemplos)
├── Debugging (logs, logs de Android)
├── Performance Tips (otimizações)
├── Testes Manuais (5 testes básicos)
├── Troubleshooting (tabela rápida)
├── Projeto Finalizado
└── Referência de Métodos (API rápida)
```

**Leia se**: Quer referência rápida, exemplos de código, ou lembrete de como fazer algo.

---

### 4. 📋 **planejamento_furiouscam_pro.md** — Roadmap
**Planejamento original + status atualizado.** O que foi feito, o que falta.

```
Seções (Atualizado):
├── 1-9. Visão geral, stack, arquitetura (original)
├── 11. Roadmap (FASE 1-5, com ✅ ⚠️ ❌)
├── 12. Diferenciais (implementados vs não)
├── 13. Filosofia (princípios mantidos)
├── 14. Status de Implementação Detalhado (por layer)
├── 15. Fila de Desenvolvimento (v0.3 → v1.0)
└── 16. Objetivo Real (complemento para OBS, nada mais)
```

**Leia se**: Quer entender roadmap, o que foi feito vs planejado, ou próximas prioridades.

---

## 🎯 Como Usar Esta Documentação

### Cenário 1: "Preciso instalar e usar"
```
1. Leia: README.md (seção Instalação + Como Usar)
2. Se tiver problema: README.md (seção Troubleshooting)
3. Pronto!
```

### Cenário 2: "Quero entender como funciona"
```
1. Leia: QUICK_REFERENCE.md (Visão Rápida + Estrutura)
2. Aprofunde: ARCHITECTURE.md (Fluxo de Dados)
3. Entender threads: ARCHITECTURE.md (Thread Model)
```

### Cenário 3: "Vou modificar/adicionar código"
```
1. Leia: QUICK_REFERENCE.md (Classes Principais + Padrões)
2. Aprofunde: ARCHITECTURE.md (seção Extensibilidade)
3. Exemplo: QUICK_REFERENCE.md (Adicionando Nova Feature)
4. Code!
```

### Cenário 4: "Estou com bug, preciso debugar"
```
1. Leia: QUICK_REFERENCE.md (Debugging)
2. Aprofunde: ARCHITECTURE.md (Error Handling)
3. Logs: logs/furiouscam.log
4. Procure padrão similar em ARCHITECTURE.md
```

### Cenário 5: "Qual é o roadmap?"
```
1. Leia: planejamento_furiouscam_pro.md (seção 15: Fila de Desenvolvimento)
2. Status: planejamento_furiouscam_pro.md (seção 14: Status Detalhado)
3. Prioridades: QUICK_REFERENCE.md (Próximos Passos)
```

---

## 📊 Estrutura de Arquivos do Projeto

```
furiousCam-mobile-win/
│
├── 📄 DOCUMENTAÇÃO:
│   ├── README.md                    ← COMECE AQUI (visão geral + uso)
│   ├── ARCHITECTURE.md              ← Técnico aprofundado
│   ├── QUICK_REFERENCE.md           ← Cheat sheet rápido
│   ├── INDEX.md                     ← Este arquivo
│   └── planejamento_furiouscam_pro.md ← Roadmap original + status
│
├── 🐍 CÓDIGO:
│   ├── main.py                      ← Entry point
│   ├── requirements.txt              ← Dependências
│   │
│   ├── core/
│   │   ├── app_core.py              ← Orquestração (AppCore)
│   │   └── adb_manager.py           ← Android bridge (AdbManager)
│   │
│   ├── decoder/
│   │   └── video_receiver.py        ← H.264 decode (VideoReceiver)
│   │
│   ├── obs/
│   │   ├── virtual_cam.py           ← OBS output (VirtualCamOutput)
│   │   └── __init__.py
│   │
│   ├── ui/
│   │   ├── main_window.py           ← Dashboard (MainWindow)
│   │   ├── camera_window.py         ← Janela flutuante (CameraOnlyWindow)
│   │   ├── icons.py                 ← SVG icons
│   │   ├── install_dialog.py        ← OBS setup guide
│   │   └── __pycache__/
│   │
│   ├── portables/
│   │   └── adb/
│   │       ├── adb.exe              ← Executável ADB
│   │       ├── *.dll                ← Bibliotecas ADB
│   │       └── furious-core.jar     ← Scrcpy server
│   │
│   └── logs/                         ← Criado em runtime
│       └── furiouscam.log           ← Log arquivo
│
└── 🎯 Projeto finalizado — Nenhum roadmap futuro previsto.
```

---

## 🔄 Fluxo Rápido de Desenvolvimento

```
1. Feature idea
   ↓
2. Consultar planejamento_furiouscam_pro.md (já foi planejada?)
   ↓
3. Ler QUICK_REFERENCE.md (Padrões de Código)
   ↓
4. Ler ARCHITECTURE.md (Fluxo existente, onde se encaixa)
   ↓
5. Consultar classes em QUICK_REFERENCE.md (API)
   ↓
6. Codificar seguindo padrões
   ↓
7. Testar com testes manuais (QUICK_REFERENCE.md)
   ↓
8. Atualizar documentação (este índice, QUICK_REFERENCE.md, etc)
```

---

## ✨ Quick Start (5 minutos)

```powershell
# 1. Instalar
pip install -r requirements.txt

# 2. Conectar Android via USB (USB Debug ON)

# 3. Rodar
python main.py

# 4. No app: Clique "Conectar Câmera"

# 5. No OBS: Add Source → Video Capture → OBS Virtual Camera

# 6. Pronto! Streaming com celular como webcam 🎬
```

---

## 🚀 Roadmap Resumido

| Versão | Status | ETA | O que muda |
|--------|--------|-----|-----------|
| **2.0** | ✅ Final | - | USB + H.264 + OBS + Wi-Fi + Áudio |

---

## 📞 Contato / Dúvidas

Se tiver dúvida:
1. **Usar**: Consulte README.md
2. **Técnica**: Consulte ARCHITECTURE.md
3. **Rápido**: Consulte QUICK_REFERENCE.md
4. **Feature**: Consulte planejamento_furiouscam_pro.md

---

## ✅ Checklist para Novo Dev

- [ ] Li README.md (visão geral)
- [ ] Instalei dependências (`pip install -r requirements.txt`)
- [ ] Conectei celular Android e testei
- [ ] Li QUICK_REFERENCE.md (padrões)
- [ ] Li ARCHITECTURE.md (seção relevante)
- [ ] Consegui rodar `python main.py` com sucesso
- [ ] Pronto para desenvolver!

---

## 📈 Estatísticas do Projeto

| Métrica | Valor |
|---------|-------|
| Linhas de código | ~2.000 |
| Arquivos Python | 8 |
| Threads ativas | 4 |
| Versão atual | 2.0 |
| Progresso | 92% |
| FPS UI | 60 |
| Latência típica | <100ms |
| Suporte Android | API 21+ |

---

## 🎓 Conceitos-Chave

```
ADB             → Android Device Bridge (controla celular via USB)
Scrcpy          → Protocolo de stream H.264 low-latency
H.264           → Codec vídeo (compatível API 21+)
Virtual Camera  → Dispositivo virtual capturado por OBS
Qt Signals      → Thread-safe communication (PySide6)
NumPy           → Array eficiente para vídeo (RGB24)
PyAV            → Binding FFmpeg (decode)
pyvirtualcam    → Wrapper Virtual Camera
```

---

## 🙏 Agradecimentos Internos

- **Scrcpy team** — Tecnologia base (protocolo, servidor)
- **PySide6/Qt** — Framework moderno
- **FFmpeg** — Decode potente e confiável
- **Comunidade open-source** — Inspiração

---

**Documentação completa**  
**Última atualização**: 29/05/2026  
**Versão do projeto**: 2.2 Final
