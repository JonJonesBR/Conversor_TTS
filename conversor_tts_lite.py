#!/usr/bin/env python3
import os
import sys
import subprocess
import asyncio
import re
import signal
from pathlib import Path

# =============================================================================
# CONFIGURAÇÃO E CONSTANTES
# =============================================================================
# Vozes disponíveis para conversão
VOZES_PT_BR = [
    "pt-BR-ThalitaMultilingualNeural",  # Voz padrão
    "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural"
]

# Diretórios e configurações de encoding e buffer
ENCODINGS_TENTATIVAS = ['utf-8', 'utf-16', 'iso-8859-1', 'cp1252']
BUFFER_IO = 32768

# Global para interrupção via sinal (Ctrl+C)
interrupcao_requisitada = False

# =============================================================================
# FUNÇÕES DE VERIFICAÇÃO DE AMBIENTE E DEPENDÊNCIAS
# =============================================================================
def verificar_sistema() -> bool:
    """
    Verifica se o script está sendo executado no ambiente Termux.
    Retorna True se estiver no Termux, False caso contrário.
    """
    print("\n🔍 Verificando ambiente de execução...")
    if 'TERMUX_VERSION' in os.environ:
        print("✅ Executando no Termux")
        return True
    else:
        print("ℹ️ Executando em ambiente não-Termux")
        return False

def instalar_dependencia_termux(pkg: str) -> None:
    """
    Verifica e instala um pacote do Termux, se necessário.
    """
    try:
        subprocess.run(['pkg', 'list-installed', pkg], check=True, capture_output=True)
        print(f"✅ Pacote Termux {pkg} já está instalado")
    except subprocess.CalledProcessError:
        print(f"⚠️ Instalando pacote Termux {pkg}...")
        try:
            subprocess.run(['pkg', 'install', '-y', pkg], check=True)
            print(f"✅ Pacote Termux {pkg} instalado com sucesso!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao instalar pacote Termux {pkg}: {e}")
            sys.exit(1)

def instalar_dependencia_python(nome_pkg: str, pip_nome: str) -> None:
    """
    Tenta importar o pacote Python e, se não estiver instalado, realiza a instalação.
    """
    try:
        __import__(nome_pkg)
        print(f"✅ {nome_pkg} já está instalado")
    except ImportError:
        print(f"\n⚠️ Instalando {nome_pkg}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", pip_nome])
            print(f"✅ {nome_pkg} instalado com sucesso!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao instalar {nome_pkg}: {e}")
            print(f"💡 Tente instalar manualmente com: pip install --user {pip_nome}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Erro inesperado ao instalar {nome_pkg}: {e}")
            sys.exit(1)

def verificar_dependencias() -> None:
    """
    Verifica e instala as dependências necessárias tanto para Termux quanto para Python.
    """
    is_termux = verificar_sistema()
    if is_termux:
        for pkg in ['python', 'python-pip', 'git']:
            instalar_dependencia_termux(pkg)
    
    dependencias_python = {
        'edge-tts': 'edge-tts',
        'langdetect': 'langdetect',
        'unidecode': 'unidecode',
        'num2words': 'num2words'
    }
    for nome_pkg, pip_nome in dependencias_python.items():
        instalar_dependencia_python(nome_pkg, pip_nome)

# Executa a verificação de dependências antes de importar módulos de terceiros
verificar_dependencias()

# =============================================================================
# IMPORTAÇÃO DE MÓDULOS TERCEIRIZADOS
# =============================================================================
import asyncio
import edge_tts
from unidecode import unidecode
import chardet

try:
    from num2words import num2words
    print("✅ num2words importado com sucesso!")
except ImportError:
    print("\n❌ Erro ao importar num2words. Tente instalar manualmente:")
    print("pip install --user num2words")
    sys.exit(1)

try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    LANG_DETECT_AVAILABLE = True
except ImportError:
    print("\n⚠️ O módulo langdetect não está instalado.")
    print("Para instalar, execute: pip install langdetect")
    LANG_DETECT_AVAILABLE = False

# =============================================================================
# FUNÇÕES UTILITÁRIAS
# =============================================================================
def limpar_tela() -> None:
    """Limpa a tela do terminal."""
    os.system("clear" if os.name == "posix" else "cls")

def obter_opcao(prompt: str, opcoes: list) -> str:
    """
    Solicita ao usuário uma entrada que esteja dentre as opções válidas.
    """
    while True:
        escolha = input(prompt).strip()
        if escolha in opcoes:
            return escolha
        print("⚠️ Opção inválida! Tente novamente.")

def gravar_progresso(arquivo_progresso: str, indice: int) -> None:
    """Grava o índice da última parte processada em arquivo."""
    with open(arquivo_progresso, 'w') as f:
        f.write(str(indice))

def ler_progresso(arquivo_progresso: str) -> int:
    """Lê o índice da última parte processada a partir do arquivo de progresso."""
    try:
        with open(arquivo_progresso, 'r') as f:
            return int(f.read().strip())
    except Exception:
        return 0

def limpar_nome_arquivo(nome: str) -> str:
    """
    Remove ou substitui caracteres inválidos em sistemas de arquivos,
    como : /  * ? " < > | etc. 
    """
    caracteres_invalidos = r'/:*?"<>|'
    for c in caracteres_invalidos:
        nome = nome.replace(c, '-')
    return nome.strip()

# =============================================================================
# PROCESSAMENTO DE TEXTO
# =============================================================================
def romano_para_decimal(romano: str) -> int:
    """
    Converte números romanos para decimal.
    """
    valores = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    decimal = 0
    prev_value = 0
    for char in reversed(romano.upper()):
        curr_value = valores.get(char, 0)
        decimal = decimal + curr_value if curr_value >= prev_value else decimal - curr_value
        prev_value = curr_value
    return decimal

def converter_ordinal(match: re.Match) -> str:
    """
    Converte números ordinais para texto, utilizando num2words.
    """
    numero = int(match.group(1))
    sufixo = match.group(2)
    if sufixo.lower() in ['º', 'ª']:
        try:
            return num2words(numero, lang='pt_BR', ordinal=True)
        except Exception:
            return match.group(0)
    return match.group(0)

def validar_texto_pt_br(texto: str) -> bool:
    """
    Valida se o texto está em português e trata casos de texto vazio.
    Caso a detecção esteja indisponível ou o idioma não seja pt,
    solicita confirmação ao usuário.
    """
    if not texto.strip():
        print("\n⚠️ Aviso: O texto está vazio!")
        return False

    if LANG_DETECT_AVAILABLE:
        try:
            idioma = detect(texto)
            if idioma != 'pt':
                print(f"\n⚠️ Aviso: O texto pode não estar em português (idioma detectado: {idioma})")
                print("Deseja continuar mesmo assim?")
                opcao = obter_opcao("\n🔹 Sua escolha ([1] Sim / [2] Não): ", ['1', '2'])
                return opcao == '1'
        except Exception as e:
            print(f"\n⚠️ Aviso: Não foi possível detectar o idioma automaticamente: {e}")
    else:
        print("\n⚠️ Aviso: A detecção de idioma não está disponível.")
        print("Deseja continuar mesmo assim?")
        opcao = obter_opcao("\n🔹 Sua escolha ([1] Sim / [2] Não): ", ['1', '2'])
        return opcao == '1'
    return True

def otimizar_texto_tts(texto: str) -> str:
    """
    Realiza otimizações no texto para melhorar a pronúncia na conversão TTS:
      - Remove ou substitui caracteres problemáticos.
      - Converte números romanos, ordinais e algarismos.
      - Substitui palavras e símbolos problemáticos.
      - Ajusta pausas na pontuação.
    """
    caracteres_problematicos = {
        "©": " copyright ",
        "®": " marca registrada ",
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "ufeff": "",
        "…": "..."
    }
    for chave, valor in caracteres_problematicos.items():
        texto = texto.replace(chave, valor)
    texto = re.sub(r'(CAPÍTULO|Capítulo|TÍTULO|Título|Parte|PARTE|Livro|LIVRO)\s+([IVXLCDM]+)',
                   lambda m: f"{m.group(1)} {romano_para_decimal(m.group(2))}",
                   texto)
    texto = re.sub(r'(\d+)([ºª])', converter_ordinal, texto)
    texto = re.sub(r'\b([IVXLCDM]+)\b',
                   lambda m: str(romano_para_decimal(m.group(1))),
                   texto)
    substituicoes = {
        'más': 'mas', 'pôr': 'por', 'têm': 'tem',
        'à': 'a', 'às': 'as', 'é': 'eh',
        'há': 'ha', 'através': 'atraves',
        'após': 'apos', 'até': 'ate',
        '1º': 'primeiro', '2º': 'segundo', '3º': 'terceiro',
        'dr.': 'doutor', 'sr.': 'senhor', 'sra.': 'senhora',
        'prof.': 'professor', 'profa.': 'professora',
        '%': ' porcento', '&': ' e ', '@': ' arroba ', '#': ' hashtag ',
        'pra': 'para', 'pro': 'para o',
        'vc': 'você', 'tb': 'também',
        'q': 'que', 'td': 'tudo'
    }
    texto = texto.lower()
    for original, corrigida in substituicoes.items():
        texto = re.sub(rf'\b{original}\b', corrigida, texto, flags=re.IGNORECASE)
    texto = re.sub(r'\d+', lambda m: num2words(int(m.group()), lang='pt_BR'), texto)
    pontuacoes = {'.': '. ', ',': ', ', ';': '; ', ':': ': ', '!': '! ', '?': '? ', '...': '... '}
    for sinal, substituicao in pontuacoes.items():
        texto = texto.replace(sinal, substituicao)
    texto = re.sub(r'\.{3,}', '... ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

# =============================================================================
# PROCESSAMENTO DE ÁUDIO
# =============================================================================
def tratar_sinal_interrupcao(signum, frame) -> None:
    """
    Manipulador de sinal para Ctrl+C: ativa a flag global de interrupção.
    """
    global interrupcao_requisitada
    interrupcao_requisitada = True
    print("\n\n🛑 Pressione Ctrl+C novamente para interromper a conversão...")

signal.signal(signal.SIGINT, tratar_sinal_interrupcao)

async def tratar_interrupcao(temp_files: list, arquivo_saida: str) -> bool:
    """
    Trata a interrupção da conversão, oferecendo opções para o usuário:
      1. Manter arquivos parciais separados.
      2. Unificar arquivos convertidos.
      3. Excluir arquivos convertidos.
    Também pergunta se o registro de progresso deve ser mantido.
    """
    print("\n\n🛑 Conversão interrompida!")
    print("\nEscolha uma opção:")
    print("[1] Manter arquivos parciais separados")
    print("[2] Unificar arquivos convertidos")
    print("[3] Excluir arquivos convertidos")
    opcao = obter_opcao("\n🔹 Sua escolha ([1/2/3]): ", ['1', '2', '3'])
    if opcao == '1':
        print("\n✅ Arquivos parciais mantidos separadamente.")
    elif opcao == '2':
        print("\n🔄 Unificando arquivos convertidos...")
        try:
            with open(arquivo_saida, 'wb') as outfile:
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        with open(temp_file, 'rb') as infile:
                            while True:
                                chunk = infile.read(BUFFER_IO)
                                if not chunk:
                                    break
                                outfile.write(chunk)
                        os.remove(temp_file)
                        print(f"\n🗑️ Arquivo temporário removido: {temp_file}")
            print("✅ Arquivos unificados com sucesso!")
        except Exception as e:
            print(f"\n⚠️ Erro ao unificar arquivos: {e}")
    else:
        print("\n🗑️ Excluindo arquivos convertidos...")
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"\n⚠️ Erro ao excluir {temp_file}: {e}")
        print("✅ Arquivos excluídos com sucesso!")
    arquivo_progresso = f"{arquivo_saida}.progress"
    if os.path.exists(arquivo_progresso):
        print("\n💾 Deseja manter o registro de progresso para retomar a conversão posteriormente?")
        opcao_prog = obter_opcao("\n🔹 Sua escolha ([1] Sim / [2] Não): ", ['1', '2'])
        if opcao_prog == '2':
            try:
                os.remove(arquivo_progresso)
                print("✅ Registro de progresso apagado com sucesso!")
            except Exception as e:
                print(f"\n⚠️ Erro ao apagar registro de progresso: {e}")
        else:
            print("✅ Registro de progresso mantido para continuação posterior.")
    limpar_tela()
    return False

async def processar_audio(texto: str, arquivo_saida: str, voz: str, chunk_size: int = 2000) -> bool:
    """
    Processa o texto em chunks para conversão em áudio via edge-tts.
    Gera arquivos temporários para cada parte e, dependendo da escolha do usuário,
    unifica os arquivos ao final.
    """
    temp_files = []
    primeira_linha = texto.strip().split('\n')[0].strip()
    if primeira_linha:
        linha_limpa = limpar_nome_arquivo(primeira_linha)
        nome_base = Path(arquivo_saida).parent / linha_limpa
        arquivo_saida = f"{nome_base}.mp3"
    print("\n📦 Preferência de arquivos:")
    print("[Enter/N] Unificar arquivos e excluir partes (padrão)")
    print("[S] Manter arquivos separados")
    opcao = input("\n🔹 Sua escolha: ").strip().upper()
    manter_separado = (opcao == 'S')
    if not validar_texto_pt_br(texto):
        print("\n🛑 Conversão cancelada pelo usuário.")
        return False
    texto = otimizar_texto_tts(texto)
    global interrupcao_requisitada
    interrupcao_requisitada = False
    chunk_size = max(2000, min(len(texto) // 10, 5000))
    partes = [texto[i:i + chunk_size] for i in range(0, len(texto), chunk_size)]
    total_partes = len(partes)
    print(f"\n🔄 Processando {total_partes} partes...")
    print("\nPressione Ctrl+C para interromper a conversão a qualquer momento.")
    arquivo_progresso = f"{arquivo_saida}.progress"
    indice_inicial = ler_progresso(arquivo_progresso)
    if indice_inicial > 0:
        print(f"\n📝 Retomando a partir da parte {indice_inicial + 1}")
    for i, parte in enumerate(partes[indice_inicial:], start=indice_inicial + 1):
        if interrupcao_requisitada:
            gravar_progresso(arquivo_progresso, i - 1)
            await tratar_interrupcao(temp_files, arquivo_saida)
            limpar_tela()
            return False
        print(f"\r📊 Progresso: {i}/{total_partes} ({int(i / total_partes * 100)}%) " + "=" * (i * 20 // total_partes) + ">", end="")
        max_tentativas = 5
        for tentativa in range(1, max_tentativas + 1):
            try:
                comunicador = edge_tts.Communicate(parte.strip(), voz)
                arquivo_temp = f"{arquivo_saida}.part{i:03d}.mp3"
                await comunicador.save(arquivo_temp)
                temp_files.append(arquivo_temp)
                gravar_progresso(arquivo_progresso, i)
                break
            except Exception as e:
                if tentativa < max_tentativas:
                    tempo_espera = 2 ** tentativa
                    print(f"\n⚠️ Erro ao processar parte {i}. Tentativa {tentativa}/{max_tentativas}. Aguardando {tempo_espera}s...")
                    await asyncio.sleep(tempo_espera)
                else:
                    print(f"\n⚠️ Erro ao processar parte {i} após {max_tentativas} tentativas: {e}")
                    continue
    if not interrupcao_requisitada:
        if not manter_separado:
            print("\n📦 Combinando arquivos...")
            try:
                with open(arquivo_saida, 'wb') as outfile:
                    for temp_file in temp_files:
                        if os.path.exists(temp_file):
                            with open(temp_file, 'rb') as infile:
                                while True:
                                    chunk = infile.read(BUFFER_IO)
                                    if not chunk:
                                        break
                                    outfile.write(chunk)
                            os.remove(temp_file)
                            print(f"\r🗑️ Arquivo temporário removido: {temp_file}", end="")
                if os.path.exists(arquivo_progresso):
                    os.remove(arquivo_progresso)
                print("\n✅ Conversão concluída! Arquivo unificado criado.")
            except Exception as e:
                print(f"\n⚠️ Erro ao unificar arquivos: {e}")
        else:
            print("\n✅ Conversão concluída! Arquivos mantidos separados.")
        return True
    return False

def ler_arquivo(caminho: str) -> str:
    try:
        with open(caminho, 'rb') as f:
            conteudo_bruto = f.read()
            resultado = chardet.detect(conteudo_bruto)
            encoding_detectado = resultado.get('encoding')
            if encoding_detectado is None and b'x00' in conteudo_bruto:
                encoding_detectado = 'utf-16-le'
            if encoding_detectado:
                return conteudo_bruto.decode(encoding_detectado)
    except Exception as e:
        print(f"❌ Erro ao ler o arquivo: {e}")
    print(f"❌ Não foi possível ler o arquivo {caminho}. Verifique o encoding.")
    return None

# =============================================================================
# FUNÇÕES DE ATUALIZAÇÃO
# =============================================================================
def atualizar_script(finalizar_apos=False):
    """
    Atualiza o script baixando a versão mais recente diretamente do GitHub.
    Sobrescreve o arquivo atual e oferece opção de reiniciar automaticamente ou encerrar.
    """
    import shutil

    url = "https://raw.githubusercontent.com/JonJonesBR/Conversor_TTS/main/conversor_tts_lite.py"
    arquivo_temp = "conversor_tts_lite_temp.py"
    arquivo_atual = sys.argv[0]

    print("\n🔄 Iniciando atualização do Conversor TTS...")

    try:
        subprocess.run(["curl", "-o", arquivo_temp, url], check=True)
        print("✅ Nova versão baixada com sucesso.")
    except subprocess.CalledProcessError:
        print("❌ Erro ao baixar com curl. Tentando com wget...")
        try:
            subprocess.run(["wget", "-O", arquivo_temp, url], check=True)
            print("✅ Nova versão baixada com sucesso.")
        except subprocess.CalledProcessError:
            print("❌ Falha ao baixar a atualização. Verifique sua conexão com a internet.")
            return

    try:
        shutil.move(arquivo_temp, arquivo_atual)
        print("✅ Atualização concluída com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao substituir o arquivo: {e}")
        return

    if finalizar_apos:
        print("\n✅ Script atualizado e encerrado. Execute novamente para carregar a nova versão.")
        sys.exit(0)
    else:
        opcao = input("\n🔄 Deseja reiniciar o script agora? (S/N): ").strip().lower()
        if opcao == 's':
            print("🔄 Reiniciando...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

# =============================================================================
# INTERFACE DO USUÁRIO (CLI)
# =============================================================================
def exibir_menu() -> str:
    print("\n" + "=" * 60)
    print("""\
████████╗████████╗███████╗
╚══██╔══╝╚══██╔══╝██╔════╝
   ██║      ██║   ███████╗
   ██║      ██║   ╚════██║
   ██║      ██║   ███████║
   ╚═╝      ╚═╝   ╚══════╝
""")
    print("=" * 60)
    print("\n[1] 🚀 Iniciar Conversão")
    print("[2] 🎙️ Testar Vozes")
    print("[3] ❓ Ajuda")
    print("[4] 🔄 Atualizar Script")
    print("[5] 🔄 Atualizar e Sair")
    print("[6] 🚪 Sair")
    print("-" * 50)
    return obter_opcao("\nEscolha: ", ['1', '2', '3', '4', '5', '6'])

def exibir_ajuda() -> None:
    print("\n" + "-" * 50)
    print("📚 GUIA DO CONVERSOR TTS")
    print("-" * 50)
    print("\n1️⃣ PREPARAÇÃO")
    print("• Salve seu texto em um arquivo .txt")
    print("• Coloque-o na pasta Downloads")
    print("\n2️⃣ CONVERSÃO")
    print("• Selecione 'Iniciar'")
    print("• Escolha o arquivo desejado")
    print("• Selecione a voz")
    print("\n3️⃣ RECURSOS")
    print("• Conversão de números para texto")
    print("• Otimizações para o português")
    print("• Processamento de textos longos")
    print("• Detecção de idioma (para avisar se não for PT-BR)")
    print("\n4️⃣ DICAS")
    print("• Teste diferentes vozes")
    print("• Use Ctrl+C para interromper a conversão")
    print("• O áudio será salvo na pasta Downloads")
    input("\nPressione Enter para voltar...")
    limpar_tela()

def escolher_voz() -> str:
    print("\n" + "-" * 50)
    print("🎙️ ESCOLHA A VOZ PARA A CONVERSÃO")
    print("\n⭐ A voz padrão é 'Thalita' - otimizada para múltiplos idiomas")
    for indice, voz in enumerate(VOZES_PT_BR, start=1):
        detalhe = " (Voz padrão)" if indice == 1 else ""
        print(f"  [{indice}] {voz}{detalhe}")
    escolha = input("\nDigite o número da voz desejada: ").strip()
    while not (escolha.isdigit() and 1 <= int(escolha) <= len(VOZES_PT_BR)):
        print("⚠️ Opção inválida! Escolha um número da lista.")
        escolha = input("\nDigite o número da voz desejada: ").strip()
    return VOZES_PT_BR[int(escolha) - 1]

async def converter_audio() -> None:
    limpar_tela()
    print("\n📖 Conversor de Texto para Fala - Modo Leve")
    diretorio_padrao = "/storage/emulated/0/Download"
    if not os.path.exists(diretorio_padrao):
        diretorio_padrao = os.path.expanduser("~/storage/downloads")
        if not os.path.exists(diretorio_padrao):
            diretorio_padrao = os.path.expanduser("~")
    if not os.path.exists(diretorio_padrao):
        print(f"⚠️ Diretório não encontrado: {diretorio_padrao}")
        print("ℹ️ Dica: Verifique se o Termux tem permissão de acesso ao armazenamento (termux-setup-storage).")
        return
    arquivos_txt = [f for f in os.listdir(diretorio_padrao) if f.endswith('.txt')]
    if not arquivos_txt:
        print("⚠️ Nenhum arquivo TXT encontrado no diretório de downloads!")
        return
    print("📄 Arquivos TXT disponíveis:")
    for indice, arquivo in enumerate(arquivos_txt, start=1):
        print(f"[{indice}] {arquivo}")
    opcao = input("\nDigite o número do arquivo desejado: ").strip()
    while not (opcao.isdigit() and 1 <= int(opcao) <= len(arquivos_txt)):
        print("⚠️ Opção inválida! Escolha um número da lista.")
        opcao = input("\nDigite o número do arquivo desejado: ").strip()
    arquivo_selecionado = arquivos_txt[int(opcao) - 1]
    caminho_completo = os.path.join(diretorio_padrao, arquivo_selecionado)
    print(f"\n📄 Lendo arquivo: {arquivo_selecionado}")
    texto = ler_arquivo(caminho_completo)
    if not texto:
        return
    voz = escolher_voz()
    nome_base = Path(caminho_completo).stem
    diretorio_saida = os.path.join(diretorio_padrao, f"{nome_base}_audio")
    os.makedirs(diretorio_saida, exist_ok=True)
    arquivo_saida = os.path.join(diretorio_saida, f"{nome_base}.mp3")
    await processar_audio(texto, arquivo_saida, voz)
    print(f"\n📂 Arquivos salvos em: {diretorio_saida}")
    input("\nPressione Enter para voltar ao menu...")
    limpar_tela()

async def testar_vozes() -> None:
    limpar_tela()
    print("\n🔊 Gerando arquivos de teste para cada voz...\n")
    diretorio_testes = "vozes_teste"
    os.makedirs(diretorio_testes, exist_ok=True)
    texto_teste = "Este é um teste da voz para conversão de texto em fala."
    for voz in VOZES_PT_BR:
        print(f"\n🎙️ Testando voz: {voz}")
        arquivo_mp3 = os.path.join(diretorio_testes, f"{voz}.mp3")
        comunicador = edge_tts.Communicate(texto_teste, voz)
        await comunicador.save(arquivo_mp3)
        print(f"✅ Arquivo salvo: {arquivo_mp3}")
    print("\n✅ Testes concluídos!")
    print(f"📂 Arquivos salvos em: {diretorio_testes}")
    input("\nPressione Enter para voltar ao menu...")
    limpar_tela()

async def main():
    while True:
        opcao = exibir_menu()
        if opcao == '1':
            await converter_audio()
        elif opcao == '2':
            await testar_vozes()
        elif opcao == '3':
            exibir_ajuda()
        elif opcao == '4':
            atualizar_script()
        elif opcao == '5':
            atualizar_script(finalizar_apos=True)
        elif opcao == '6':
            print("\n👋 Obrigado por usar o Conversor TTS Lite!")
            break

if __name__ == '__main__':
    asyncio.run(main())