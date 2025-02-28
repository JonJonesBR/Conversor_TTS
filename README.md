# Conversor TTS (Text-to-Speech)

Um conversor de texto para áudio em português brasileiro, utilizando a tecnologia Edge TTS. Este script oferece uma interface amigável e recursos avançados para converter textos em arquivos de áudio com qualidade profissional.

## ✨ Características

- 🎯 **Interface intuitiva e interativa**
- 🎙️ **Três vozes diferentes em português brasileiro**
- 📜 **Suporte a textos longos com divisão automática**
- 🔍 **Detecção automática de idioma e aviso se não for PT-BR**
- 🔢 **Conversão automática de números, ordinais e romanos para texto**
- 🎭 **Correção de pronúncia e substituição de abreviações**
- 🛠️ **Processamento otimizado para melhor entonação e pausas**
- ⏸️ **Pausa e retomada da conversão em caso de interrupção**
- 📦 **Opção de unificar ou manter arquivos de áudio separados**
- 🚀 **Execução eficiente usando o Termux no Android e no Linux**

---

## 📋 Pré-requisitos

Para utilizar este conversor de texto para fala no Android, você precisará instalar o **Termux** e conceder as permissões necessárias. No Linux, basta instalar o Python.

### 🟢 Android (com Termux)

1. **Baixe e instale o Termux** (não use a versão da Play Store, pois está desatualizada):
   - **[Baixar Termux (F-Droid)](https://f-droid.org/packages/com.termux/)**
   - **[Baixar Termux (GitHub)](https://github.com/termux/termux-app/releases)**

2. **Após instalar o Termux, execute os seguintes comandos:**
```bash
   termux-setup-storage  # Concede acesso ao armazenamento
   
   apt update && apt upgrade -y  # Atualiza os pacotes do Termux
   
   apt install python git -y  # Instala Python e Git
```
### Caso durante a instalação pergunte algo, basta digitar y.

### 🔵 Linux

Apenas certifique-se de que o Python 3.6 ou superior está instalado:

```bash
   sudo apt update && sudo apt install python3 python3-pip git -y
```

## 🚀 Instalação do Conversor TTS

### 1.	Baixe o script no seu Termux:
```bash
   curl -o conversor_tts_lite.py https://raw.githubusercontent.com/JonJonesBR/Conversor_TTS/main/conversor_tts_lite.py
```
   OU
```bash
   wget -O conversor_tts_lite.py https://raw.githubusercontent.com/JonJonesBR/Conversor_TTS/main/conversor_tts_lite.py 
```
### 2. Confirme se o script foi baixado com sucesso:
```bash
   ls
```
   #### ✅ Se aparecer a mensagem conversor_tts_lite.py o aquivo foi baixado!
   #### ❌ Se o nome conversor_tts_lite.py não aparecer, refaça o passo 1!

### 3. Instale as dependências necessárias: 

	pip install edge-tts langdetect unidecode num2words chardet && python -m pip install --user requests

## 💻 Como Usar

### 1. Execute o script: 

	python conversor_tts_lite.py

### 2.	No menu principal, você terá as seguintes opções:

   •	🚀 INICIAR: Começa o processo de conversão
   
   •	🎙️ VOZES: Testa as vozes disponíveis
	
   •	❓ AJUDA: Exibe o guia de uso
	
   •	🚪 SAIR: Encerra o programa

### 3.	Para converter um texto:

   •	Salve seu texto em um arquivo .txt
	
   •	Coloque o arquivo na pasta Downloads
	
   •	Escolha a opção INICIAR
	
   •	Selecione o arquivo de texto
	
   •	Escolha a voz desejada
	
   •	Aguarde a conversão

## 🎙️ Vozes Disponíveis

   •	Thalita (padrão) - Otimizada para múltiplos idiomas
	
   •	Francisca - Voz feminina alternativa
	
   •	Antonio - Voz masculina

## 🛠️ Recursos Avançados

### 📜 Processamento Inteligente

   •	🔢 Números para texto (ex.: “1234” → “mil duzentos e trinta e quatro”)
	
   •	🏆 Números ordinais (ex.: “1º” → “primeiro”)
	
   •	🏛️ Números romanos (ex.: “Capítulo IV” → “Capítulo 4”)
	
   •	📝 Abreviações expandidas (ex.: “Dr.” → “Doutor”, “Sr.” → “Senhor”)
	
   •	🔣 Substituições especiais (ex.: “% → porcento”, “& → e”)

## 🔄 Controle de Conversão

   •	⏸️ Pausar e retomar: Se interrompido, o progresso é salvo
	
   •	📦 Escolha do formato de saída: Unificar áudio ou manter arquivos separados
	
   •	🛑 Interrupção segura: Pressione Ctrl+C para interromper e decidir o que fazer com os arquivos gerados

## 🚀 Recursos e Funcionalidades

### 📂 Processamento de Arquivos
   • Leitura automática de arquivos com detecção inteligente de encoding
   • Suporte para conversão de PDF para texto
   • Detecção automática do ambiente (Termux/Desktop)

### 🔍 Otimização de Texto
   • Verificação automática de idioma português
   • Conversão inteligente de números e símbolos
   • Ajuste dinâmico de pausas para melhor entonação
   • Tratamento especial para abreviações e caracteres especiais

### 💾 Gerenciamento de Progresso
   • Salvamento automático do progresso de conversão
   • Capacidade de retomar conversões interrompidas
   • Opção de manter arquivos parciais ou unificados

### 🎛️ Controle e Personalização
   • Múltiplas vozes disponíveis em português
   • Estrutura modular para fácil personalização
   • Interrupção segura da conversão (Ctrl+C ou 'q')
   • Opções flexíveis para gerenciamento de arquivos

## 🔗 Links Úteis

   •	📥 Baixar Termux (F-Droid): [Clique aqui](https://f-droid.org/packages/com.termux/)
	
   •	📥 Baixar Termux (GitHub): [Clique aqui](https://github.com/termux/termux-app/releases)
	
   •	📚 Guia oficial do Termux: [Leia aqui](https://wiki.termux.com/wiki/Main_Page) - Traduza a página com o google tradutor no Chrome 😁
	
   •	🎤 Baixar o repositório deste Conversor TTS: [Clique aqui](https://github.com/JonJonesBR/Conversor_TTS/archive/refs/heads/main.zip)

   •	🐍 Baixar o arquivo Python do Conversor TTS: [Clique aqui]()

### •	🛠️ Comandos úteis do Termux:
```bash 
   termux-setup-storage  # Concede acesso ao armazenamento
	
   apt update && apt upgrade -y  # Atualiza os pacotes do Termux 
	
   apt install python git -y  # Instala Python e Git 
	
   pip install edge-tts langdetect unidecode num2words chardet  # Instala dependências 
```
## ⚠️ Observações

   •	O arquivo de áudio será salvo na pasta de Downloads
	
   •	O nome do arquivo de áudio será baseado na primeira linha do texto
	
   •	A conversão requer conexão com a internet
	
   •	Para melhor compatibilidade no Termux, conceda permissões com:

	termux-setup-storage  # Concede acesso ao armazenamento
	
## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir uma issue ou enviar um pull request.

## ⭐ Se este projeto foi útil para você, considere dar uma estrela no GitHub