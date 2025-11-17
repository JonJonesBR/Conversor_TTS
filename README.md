# 🎙️ Conversor TTS Avançado – Texto para Fala

Um script Python completo e profissional para conversão de texto em áudio (TTS) com suporte a **Edge TTS** e **Gemini TTS**, processamento inteligente de texto, manipulação de áudio/vídeo e muito mais.

## 🌟 Destaques

- 🎯 **Dois motores TTS**: Edge TTS (Microsoft) e Gemini TTS (Google AI)
- 🌍 **11 vozes multilíngues testadas e funcionando** (PT-BR, EN-US, DE, FR, IT, KO)
- 📚 **Suporte completo**: TXT, PDF e EPUB
- 🧠 **Processamento inteligente de texto** com formatação avançada
- 🎬 **Manipulação de mídia**: acelerar, converter, dividir e criar vídeos
- 💻 **Multiplataforma**: Windows, Linux e Android (Termux)
- 🔄 **Sistema de retry infinito** para garantir conversão completa
- 💾 **API Key persistente** para Gemini TTS

---

## 📋 Índice

- [Funcionalidades](#-funcionalidades)
- [Instalação](#-instalação)
- [Uso Rápido](#-uso-rápido)
- [Vozes Disponíveis](#-vozes-disponíveis)
- [Processamento de Texto](#-processamento-de-texto)
- [Recursos Avançados](#-recursos-avançados)
- [Requisitos](#-requisitos)
- [Solução de Problemas](#-solução-de-problemas)
- [Contribuindo](#-contribuindo)

---

## ✨ Funcionalidades

### 🎙️ Conversão TTS
- **Edge TTS**: 11 vozes multilíngues gratuitas (sem API Key)
- **Gemini TTS**: 12 vozes premium com qualidade superior (requer API Key)
- Conversão assíncrona com processamento em lotes
- Sistema de retry automático com backoff exponencial
- Progresso em tempo real com barra de carregamento

### 📄 Suporte a Formatos
- **TXT**: Detecção automática de encoding (UTF-8, UTF-16, ISO-8859-1, CP1252)
- **PDF**: Extração de texto com instalação automática do Poppler
- **EPUB**: Extração inteligente com limpeza de HTML e metadados

### 🧠 Processamento Inteligente
- Formatação automática de capítulos (Capítulo I, II, III...)
- Conversão de números para extenso (123 → "cento e vinte e três")
- Conversão de ordinais (1º → "primeiro", 2ª → "segunda")
- Expansão de abreviações (Dr. → "Doutor", Sra. → "Senhora")
- Conversão de valores monetários (R$ 100 → "cem reais")
- Remoção de metadados e números de página
- Normalização de texto em CAIXA ALTA
- Correção de hifenização em quebras de linha

### 🎬 Manipulação de Mídia
- **Acelerar áudio/vídeo**: Ajuste de velocidade (0.5x a 2.0x)
- **Converter formatos**: MP3, WAV, M4A, OGG, OPUS, FLAC, MP4, MKV, AVI, MOV, WEBM
- **Dividir arquivos longos**: Divisão automática para vídeos >12h
- **Criar vídeos**: Converter MP3 para MP4 com tela preta (múltiplas resoluções)

### 🔧 Recursos Técnicos
- Interface assíncrona com `aioconsole`
- Instalação automática de dependências Python
- Instalação automática de Poppler (Windows/Termux)
- Detecção automática de sistema operacional
- Salvamento automático de progresso
- Cancelamento seguro com CTRL+C

---

## 🚀 Instalação

### Windows

#### 1. Instalar Python
Baixe e instale Python 3.8+:  
👉 [python.org/downloads](https://www.python.org/downloads/)

**Importante**: Marque a opção "Add Python to PATH" durante a instalação.

#### 2. Baixar o Script
```bash
git clone https://github.com/JonJonesBR/Conversor_TTS.git
cd Conversor_TTS
```

Ou baixe o ZIP:  
👉 [github.com/JonJonesBR/Conversor_TTS](https://github.com/JonJonesBR/Conversor_TTS)

#### 3. Instalar Dependências
```bash
pip install --user edge-tts beautifulsoup4 html2text tqdm requests aioconsole chardet num2words aiohttp
```

#### 4. Executar
```bash
python TTS.py
```

---

### Linux

```bash
# Instalar dependências do sistema
sudo apt update
sudo apt install -y python3 python3-pip ffmpeg poppler-utils

# Clonar repositório
git clone https://github.com/JonJonesBR/Conversor_TTS.git
cd Conversor_TTS

# Instalar dependências Python
pip3 install --user edge-tts beautifulsoup4 html2text tqdm requests aioconsole chardet num2words aiohttp

# Executar
python3 TTS.py
```

---

### Android (Termux)

```bash
# Atualizar pacotes
pkg update -y && pkg upgrade -y

# Instalar dependências
pkg install -y python git ffmpeg poppler termux-api

# Configurar acesso ao armazenamento
termux-setup-storage

# Clonar repositório
git clone https://github.com/JonJonesBR/Conversor_TTS.git
cd Conversor_TTS

# Instalar dependências Python
pip install --user edge-tts beautifulsoup4 html2text tqdm requests aioconsole chardet num2words aiohttp

# Executar
python TTS.py
```

---

## 🎯 Uso Rápido

### Conversão Básica (Edge TTS - Gratuito)

1. Execute o script: `python TTS.py`
2. Escolha **Opção 1**: Converter Texto para Áudio
3. Selecione seu arquivo (TXT, PDF ou EPUB)
4. Escolha **Edge TTS** (gratuito, sem API Key)
5. Selecione uma voz da lista
6. Aguarde a conversão!

O áudio será salvo em uma pasta com o nome do arquivo na pasta Downloads.

### Conversão com Gemini TTS (Premium)

1. Obtenha sua API Key do Google AI Studio:  
   👉 [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

2. Execute o script e escolha **Opção 8**: Configurar API Key
3. Cole sua API Key (será salva automaticamente)
4. Escolha **Opção 1**: Converter Texto para Áudio
5. Selecione **Gemini TTS**
6. Escolha uma das 12 vozes premium

---

## 🎙️ Vozes Disponíveis

### Edge TTS (11 vozes testadas e funcionando)

#### Português Brasil
- `pt-BR-ThalitaMultilingualNeural` (Feminina) ⭐

#### Inglês Americano
- `en-US-AndrewMultilingualNeural` (Masculina)
- `en-US-AvaMultilingualNeural` (Feminina)
- `en-US-BrianMultilingualNeural` (Masculina)
- `en-US-EmmaMultilingualNeural` (Feminina)

#### Alemão
- `de-DE-SeraphinaMultilingualNeural` (Feminina)
- `de-DE-FlorianMultilingualNeural` (Masculina)

#### Francês
- `fr-FR-VivienneMultilingualNeural` (Feminina)
- `fr-FR-RemyMultilingualNeural` (Masculina)

#### Italiano
- `it-IT-GiuseppeMultilingualNeural` (Masculina)

#### Coreano
- `ko-KR-HyunsuMultilingualNeural` (Masculina)

### Gemini TTS (12 vozes premium)

- **Kore** (Firme)
- **Puck** (Animada)
- **Charon** (Informativa)
- **Zephyr** (Brilhante)
- **Leda** (Jovial)
- **Orus** (Firme)
- **Aoede** (Arejada)
- **Callirrhoe** (Descontraída)
- **Autonoe** (Brilhante)
- **Iapetus** (Clara)
- **Umbriel** (Descontraída)
- **Algenib** (Grave)

---

## 📝 Processamento de Texto

O script aplica formatações inteligentes automaticamente:

### Números
```
Entrada: "Ele tem 25 anos e ganhou R$ 1000"
Saída:   "Ele tem vinte e cinco anos e ganhou mil reais"
```

### Ordinais
```
Entrada: "Ele ficou em 1º lugar"
Saída:   "Ele ficou em primeiro lugar"
```

### Capítulos
```
Entrada: "CAPÍTULO IV - A JORNADA"
Saída:   "CAPÍTULO 4. A Jornada"
```

### Abreviações
```
Entrada: "O Dr. Silva e a Sra. Maria"
Saída:   "O Doutor Silva e a Senhora Maria"
```

### Limpeza Automática
- Remove números de página isolados
- Remove metadados de PDF
- Corrige palavras hifenizadas em quebras de linha
- Normaliza texto em CAIXA ALTA para Title Case
- Remove caracteres especiais e formatação markdown

---

## 🛠️ Recursos Avançados

### 1. Testar Vozes
Opção 2 do menu permite ouvir amostras de todas as vozes antes de converter.

### 2. Melhorar Áudio/Vídeo
- Acelerar ou desacelerar (0.5x a 2.0x)
- Converter entre formatos
- Aplicar múltiplas melhorias em sequência

### 3. Dividir Vídeos Longos
- Divisão automática para vídeos >12h
- Sem recompressão (rápido)
- Ideal para upload no YouTube

### 4. Converter MP3 para MP4
- Cria vídeo com tela preta
- Múltiplas resoluções: 144p, 240p, 360p, 480p, 720p, 1080p
- Ideal para upload em plataformas de vídeo

### 5. Atualização Automática
Opção 6 do menu baixa automaticamente a versão mais recente do GitHub.

---

## 📦 Requisitos

### Python
- Python 3.8 ou superior

### Dependências Python (instaladas automaticamente)
- `edge-tts>=6.1.5` - Motor TTS da Microsoft
- `beautifulsoup4` - Parser HTML para EPUB
- `html2text` - Conversão HTML para texto
- `tqdm` - Barras de progresso
- `requests` - Requisições HTTP
- `aioconsole>=0.6.0` - Console assíncrono
- `chardet>=5.0.0` - Detecção de encoding
- `num2words>=0.5.12` - Conversão de números
- `aiohttp` - Cliente HTTP assíncrono

### Dependências do Sistema
- **FFmpeg** - Manipulação de áudio/vídeo (instalação automática no Termux)
- **Poppler** - Extração de texto de PDF (instalação automática no Windows/Termux)

---

## 🔧 Solução de Problemas

### Erro: "Módulo não encontrado"
```bash
pip install --user edge-tts beautifulsoup4 html2text tqdm requests aioconsole chardet num2words aiohttp
```

### Erro ao converter PDF
O script tentará instalar o Poppler automaticamente. Se falhar:

**Windows**: Baixe manualmente de [github.com/oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) e adicione ao PATH.

**Linux**:
```bash
sudo apt install poppler-utils
```

**Termux**:
```bash
pkg install poppler
```

### Erro: "FFmpeg não encontrado"
**Windows**: Baixe de [ffmpeg.org](https://ffmpeg.org/download.html) e adicione ao PATH.

**Linux**:
```bash
sudo apt install ffmpeg
```

**Termux**:
```bash
pkg install ffmpeg
```

### Conversão interrompida
O progresso é salvo automaticamente. Execute o script novamente para continuar de onde parou.

### Erro de permissão no Android
```bash
termux-setup-storage
```
Permita o acesso ao armazenamento quando solicitado.

### Gemini TTS não funciona
1. Verifique se você configurou a API Key (Opção 8)
2. Verifique se a API Key é válida em [aistudio.google.com](https://aistudio.google.com)
3. Verifique sua conexão com a internet

---

## 📊 Arquivos do Projeto

```
Conversor_TTS/
├── TTS.py                          # Script principal
├── test_vozes.py                   # Script de teste de vozes
├── relatorio_teste_vozes.txt       # Relatório de vozes testadas
└── README.md                       # Este arquivo
```

---

## 🔐 Segurança

- A API Key do Gemini é salva em `~/.conversor_tts_config.json`
- O arquivo é criado com permissões restritas
- Nunca compartilhe sua API Key publicamente
- A API Key não é enviada para nenhum servidor além do Google AI

---

## 🎓 Casos de Uso

- 📚 Converter livros e artigos para audiobooks
- 🎓 Criar material de estudo em áudio
- 🌐 Gerar narrações para vídeos
- ♿ Acessibilidade para pessoas com deficiência visual
- 🎧 Consumir conteúdo em movimento
- 🎬 Criar conteúdo para YouTube/Podcast

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

### Reportar Bugs
Abra uma issue em: [github.com/JonJonesBR/Conversor_TTS/issues](https://github.com/JonJonesBR/Conversor_TTS/issues)

---

## 📄 Licença

Este projeto é distribuído sob a licença MIT. Consulte o arquivo `LICENSE` para mais informações.

---

## 🔗 Links Úteis

- **Repositório**: [github.com/JonJonesBR/Conversor_TTS](https://github.com/JonJonesBR/Conversor_TTS)
- **Python**: [python.org/downloads](https://www.python.org/downloads/)
- **Google AI Studio**: [aistudio.google.com](https://aistudio.google.com)
- **Edge TTS**: [github.com/rany2/edge-tts](https://github.com/rany2/edge-tts)
- **FFmpeg**: [ffmpeg.org](https://ffmpeg.org)
- **Termux (F-Droid)**: [f-droid.org/packages/com.termux](https://f-droid.org/packages/com.termux/)
- **Termux (GitHub)**: [github.com/termux/termux-app/releases](https://github.com/termux/termux-app/releases)

---

## 📈 Estatísticas do Projeto

- ✅ **11 vozes Edge TTS** testadas e funcionando
- ✅ **12 vozes Gemini TTS** disponíveis
- ✅ **3 formatos de entrada** suportados (TXT, PDF, EPUB)
- ✅ **10+ formatos de mídia** suportados
- ✅ **3 plataformas** suportadas (Windows, Linux, Android)

---

## ⭐ Agradecimentos

Se este projeto foi útil para você, considere:
- ⭐ Dar uma estrela no GitHub
- 🐛 Reportar bugs e sugerir melhorias
- 🤝 Contribuir com código
- 📢 Compartilhar com outras pessoas

---

## 📞 Suporte

Para suporte, abra uma issue no GitHub ou entre em contato através do repositório.

---

**Desenvolvido com ❤️ para a comunidade**

*Última atualização: Novembro 2024*
