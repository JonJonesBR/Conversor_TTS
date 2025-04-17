# NOVA ATUALIZAÇÃO!!! 🥳🥳

# Conversor TTS – Texto para Fala em Português Brasileiro (PT-BR)

## Um script completo e eficiente para converter textos em arquivos de áudio (MP3), utilizando a tecnologia **Edge TTS** da Microsoft. Compatível com **Windows**, **Linux** e **Android (via Termux)**, este projeto foi desenvolvido para facilitar a conversão de textos longos com alta qualidade, recursos avançados de formatação e melhoria de áudio.

---

## ✨ Funcionalidades

- ✅ **Compatível com Windows, Linux e Termux (Android)**
- 🎙️ **Três vozes diferentes em português brasileiro**
- 📜 **Suporte a textos longos com divisão automática**
- 🔍 **Detecção automática de idioma e aviso se não for PT-BR**
- 🔢 **Conversão automática de números, ordinais e romanos para texto**
- 📄 **Conversão integrada de arquivos PDF e EPUB para texto**
- 📝 **Expansão de abreviações e símbolos especiais**
- 💾 **Salvamento automático na pasta Download**
- ⚡ **Melhoria de áudio (aceleração, conversão, divisão em partes)**
- 🎬 **Conversão de MP3 em vídeos MP4 com tela preta**
- 🔧 **Instalação automática de dependências (pip e sistema)**

---

## 🗂️ Suporte a Arquivos PDF e EPUB

### 🚨 ATENÇÃO:

> Caso na primeira tentativa de conversão de PDF ocorra erro, **aguarde a instalação automática do Poppler** e execute novamente a operação. Após isso, funcionará normalmente.

- O script identifica e converte automaticamente arquivos `.pdf` e `.epub` em `.txt`
- PDFs escaneados (imagem) **não** são suportados
- PDFs textuais e EPUBs são tratados com limpeza e formatação inteligente
- O arquivo `.txt` é salvo automaticamente com sufixo `_formatado.txt`

---

# ⚙️ Passo a Passo de Instalação e Uso

## 🪟 Windows

### 1️⃣ Instalar Python

Baixe e instale a versão mais recente do Python:  
[https://www.python.org/downloads/](https://www.python.org/downloads/)

### 2️⃣ Baixar o Script

Baixe os arquivos do repositório:  
[https://github.com/JonJonesBR/Conversor_TTS](https://github.com/JonJonesBR/Conversor_TTS)

### 3️⃣ Instalar Dependências

Abra o **Prompt de Comando** e execute:

```bash
pip install --user edge-tts langdetect unidecode num2words chardet requests tqdm aioconsole
```

### 4️⃣ Executar o Script

Navegue até a pasta onde salvou o script:

```bash
cd Downloads
python Conversor_TTS_com_MP4_09.04.2025.py
```

---

## 🐧 Linux / 📱 Android (Termux)

### 1️⃣ Preparar Ambiente

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git ffmpeg poppler termux-api unzip
pip install --user edge-tts langdetect unidecode num2words chardet requests tqdm aioconsole
termux-setup-storage
```

### 2️⃣ Baixar e Executar o Script

```bash
curl -L -o Conversor_TTS.zip https://github.com/JonJonesBR/Conversor_TTS/archive/refs/heads/main.zip
unzip -j Conversor_TTS.zip -d ~/
python Conversor_TTS_com_MP4_09.04.2025.py
```

---

## 📂 Como Funciona

1. Coloque seu arquivo `.txt`, `.pdf` ou `.epub` na pasta **Download**
2. Execute o script
3. Selecione a opção desejada no menu
4. Escolha o arquivo e a voz
5. O áudio será salvo automaticamente em uma pasta com o nome dele na pasta Download

---

## 🎙️ Vozes Disponíveis

- **Thalita** – Neural otimizada (padrão)  
- **Francisca** – Voz alternativa suave  
- **Antonio** – Voz clara e objetiva

---

## 🛠️ Recursos Avançados

### 📜 Processamento inteligente de texto

- Conversão de números: `123` → *cento e vinte e três*
- Conversão de ordinais: `1º` → *primeiro*
- Números romanos: `Capítulo IV` → *Capítulo 4*
- Expansão de abreviações: `Dr.` → *Doutor*, `Sra.` → *Senhora*
- Substituição de símbolos: `%` → *porcento*, `&` → *e*

### 🔄 Controle de conversão

- Acelerar ou reduzir velocidade de leitura do áudio ao final da conversão e através do menu inicial 
- Áudios com mais de 12 horas são automaticamente divididos e cada um terá no máximo 12 horas (para upload no YouTube)
- Geração de vídeos MP4 com tela preta a partir de MP3

---

## ❓ Problemas Comuns e Soluções

- **Erro: módulo não encontrado**  
  → Execute novamente o comando `pip install` com as dependências indicadas.

- **Erro: permissão negada no Android**  
  → Execute `termux-setup-storage` e permita acesso aos arquivos.

- **Conversão interrompida**  
  → O progresso é salvo automaticamente. Rode o script novamente para continuar.

- **Erro ao converter PDF**  
  → O script instalará automaticamente o Poppler. Tente novamente após a instalação.

---

## 🔗 Links Úteis

- **Repositório no GitHub:**  
  [https://github.com/JonJonesBR/Conversor_TTS](https://github.com/JonJonesBR/Conversor_TTS)

- **Download do Python:**  
  [https://www.python.org/downloads/](https://www.python.org/downloads/)

- **Termux no F-Droid:**  
  [https://f-droid.org/packages/com.termux/](https://f-droid.org/packages/com.termux/)

- **Termux no GitHub:**  
  [https://github.com/termux/termux-app/releases](https://github.com/termux/termux-app/releases)

---

## 📄 Licença

Este projeto é distribuído sob a licença **MIT**. Consulte o arquivo `LICENSE` para mais informações.

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Se você encontrou um bug, tem sugestões ou deseja ajudar no desenvolvimento, abra uma *issue* ou envie um *pull request*.

---

## ⭐ Se este projeto foi útil para você, deixe uma estrela no GitHub! ⭐
