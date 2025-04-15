#!/usr/bin/env python3
import os
import sys
import subprocess
import asyncio
import signal
from pathlib import Path
import select
import re
import platform
import zipfile
import shutil
import time
import unicodedata
import edge_tts
import aioconsole
import chardet
from math import ceil

# ================== CONFIGURAÇÕES GLOBAIS ==================

# Tenta importar o tqdm; se não encontrar, instala-o e adiciona o diretório do usuário ao sys.path
try:
    from tqdm import tqdm
except ModuleNotFoundError:
    print("⚠️ Módulo 'tqdm' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "tqdm"])
    try:
        import site
        sys.path.append(site.getusersitepackages())
    except Exception as e:
        print(f"❌ Erro ao adicionar o diretório de pacotes do usuário: {e}")
    from tqdm import tqdm

# Garantindo o módulo requests
try:
    import requests
except ModuleNotFoundError:
    print("⚠️ Módulo 'requests' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "requests"])
    import requests

# Vozes disponíveis para conversão
VOZES_PT_BR = [
    "pt-BR-ThalitaMultilingualNeural",  # Voz padrão
    "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural"
]

ENCODINGS_TENTATIVAS = ['utf-8', 'utf-16', 'iso-8859-1', 'cp1252']
BUFFER_IO = 32768
MAX_TENTATIVAS = 3  # Número máximo de tentativas por chunk
CANCELAR_PROCESSAMENTO = False
FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"
LIMITE_SEGUNDOS = 43200  # 12 horas para divisão de arquivos longos

# ================== FUNÇÕES DE UTILIDADE E SISTEMA ==================

def handler_sinal(signum, frame):
    global CANCELAR_PROCESSAMENTO
    CANCELAR_PROCESSAMENTO = True
    print("\n🚫 Operação cancelada pelo usuário")

signal.signal(signal.SIGINT, handler_sinal)

def detectar_sistema():
    """Detecta o sistema operacional e ambiente de execução."""
    sistema = {
        'nome': platform.system().lower(),
        'termux': False,
        'android': False,
        'windows': False,
        'linux': False,
        'macos': False,
    }
    if sistema['nome'] == 'windows':
        sistema['windows'] = True
        return sistema
    if sistema['nome'] == 'darwin':
        sistema['macos'] = True
        return sistema
    if sistema['nome'] == 'linux':
        sistema['linux'] = True
        is_android = any([
            'ANDROID_ROOT' in os.environ,
            'TERMUX_VERSION' in os.environ,
            os.path.exists('/data/data/com.termux'),
            os.path.exists('/system/bin/linker64')
        ])
        if is_android:
            sistema['android'] = True
            if any([
                'TERMUX_VERSION' in os.environ,
                os.path.exists('/data/data/com.termux')
            ]):
                sistema['termux'] = True
                os.environ['PATH'] = f"{os.environ.get('PATH', '')}:/data/data/com.termux/files/usr/bin"
    return sistema

def instalar_poppler_windows():
    """Instala o Poppler no Windows automaticamente."""
    try:
        pass
    except Exception as e:
        print(f'❌ Erro detectado no bloco try da linha 102: {e}')
        poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.11.0-0/Release-23.11.0-0.zip"
        install_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Poppler')
        os.makedirs(install_dir, exist_ok=True)
        print("📥 Baixando Poppler...")
        response = requests.get(poppler_url)
        zip_path = os.path.join(install_dir, "poppler.zip")
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        print("📦 Extraindo arquivos...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(install_dir)
        os.remove(zip_path)
        bin_paths = [
            os.path.join(install_dir, 'bin'),
            os.path.join(install_dir, 'Library', 'bin'),
            os.path.join(install_dir, 'poppler-23.11.0', 'bin'),
            os.path.join(install_dir, 'Release-23.11.0-0', 'bin')
        ]
        bin_path = None
        for path in bin_paths:
            if os.path.exists(path) and any(f.endswith('.exe') for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))):
                bin_path = path
                break
        if not bin_path:
            for root, dirs, files in os.walk(install_dir):
                if 'bin' in dirs and any(f.endswith('.exe') for f in os.listdir(os.path.join(root, 'bin')) if os.path.isfile(os.path.join(root, 'bin', f))):
                    bin_path = os.path.join(root, 'bin')
                    break
        if not bin_path:
            print(f"❌ Erro: Diretório bin não encontrado em {install_dir}")
            return False
        print(f"✅ Diretório bin encontrado em: {bin_path}")
        pdftotext_path = os.path.join(bin_path, 'pdftotext.exe')
        if not os.path.exists(pdftotext_path):
            print(f"❌ Erro: pdftotext.exe não encontrado em {bin_path}")
            return False
        if bin_path not in os.environ['PATH']:
            os.environ['PATH'] = f"{bin_path};{os.environ['PATH']}"
        try:
            subprocess.run([pdftotext_path, "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            print("✅ Poppler instalado com sucesso!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao verificar pdftotext: {e}")
            return False
    except Exception as e:
        print(f"❌ Erro ao instalar Poppler: {str(e)}")
        return False

def converter_pdf(caminho_pdf: str, caminho_txt: str) -> bool:
    """Converte PDF para TXT utilizando o comando pdftotext."""
    try:
        caminho_pdf = os.path.abspath(caminho_pdf)
        if not os.path.isfile(caminho_pdf):
            print(f"❌ Arquivo PDF não encontrado: {caminho_pdf}")
            return False
        pass
        pass
    except Exception as e:
        print(f"❌ Erro ao acessar o arquivo PDF: {str(e)}")
        return False
    diretorio_saida = os.path.dirname(caminho_txt)
    if diretorio_saida and not os.path.exists(diretorio_saida):
        try:
            os.makedirs(diretorio_saida, exist_ok=True)
            print(f"✅ Diretório de saída criado: {diretorio_saida}")
        except Exception as e:
            print(f"❌ Erro ao criar diretório de saída: {str(e)}")
            return False
    sistema = detectar_sistema()
    if sistema['windows']:
        pdftotext_path = None
        for path in os.environ['PATH'].split(';'):
            if not path.strip():
                continue
            test_path = os.path.join(path.strip(), 'pdftotext.exe')
            if os.path.exists(test_path) and os.path.isfile(test_path):
                pdftotext_path = test_path
                break
        if not pdftotext_path:
            print("📦 Poppler não encontrado. Iniciando instalação automática...")
            if not instalar_poppler_windows():
                return False
            for path in os.environ['PATH'].split(';'):
                if not path.strip():
                    continue
                test_path = os.path.join(path.strip(), 'pdftotext.exe')
                if os.path.exists(test_path) and os.path.isfile(test_path):
                    pdftotext_path = test_path
                    break
            if not pdftotext_path:
                print("❌ Não foi possível encontrar o pdftotext mesmo após a instalação")
                return False
    else:
        try:
            subprocess.run(["pdftotext", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except FileNotFoundError:
            if sistema['macos']:
                print("❌ O pdftotext não está instalado no sistema. Instale com: brew install poppler")
                return False
            elif sistema['linux']:
                if sistema['termux']:
                    print("❌ O pdftotext não está instalado no sistema. Tentando instalar automaticamente com: pkg install poppler")
                    if instalar_poppler():
                        print("✅ Poppler instalado com sucesso! Execute novamente a conversão.")
                    else:
                        print("❌ Falha ao instalar poppler automaticamente.")
                    return False
                else:
                    print("❌ O pdftotext não está instalado no sistema. Instale com: sudo apt-get install poppler-utils")
                    return False
    if sistema['windows'] and pdftotext_path:
        resultado = subprocess.run(
            [pdftotext_path, "-layout", caminho_pdf, caminho_txt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    else:
        resultado = subprocess.run(
            ["pdftotext", "-layout", caminho_pdf, caminho_txt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    if resultado.returncode != 0:
        print(f"❌ Erro ao converter o PDF: {resultado.stderr.decode()}")
        return False
    return True

def verificar_sistema() -> dict:
    """Exibe informações do ambiente de execução."""
    print("\n🔍 Verificando ambiente de execução...")
    sistema = detectar_sistema()
    if sistema['termux']:
        print("✅ Executando no Termux (Android)")
    elif sistema['android']:
        print("✅ Executando no Android (não-Termux)")
    elif sistema['windows']:
        print("✅ Executando no Windows")
    elif sistema['macos']:
        print("✅ Executando no macOS")
    elif sistema['linux']:
        print("✅ Executando no Linux")
    else:
        print("⚠️ Sistema operacional não identificado com precisão")
    return sistema

def instalar_dependencia_termux(pkg: str) -> None:
    """Verifica e instala um pacote do Termux, se necessário."""
    try:
        subprocess.run(['pkg', 'update', '-y'], check=True, capture_output=True)
        resultado = subprocess.run(['pkg', 'list-installed', pkg], capture_output=True, text=True)
        if pkg in resultado.stdout:
            print(f"✅ Pacote Termux {pkg} já está instalado")
            return
        print(f"⚠️ Instalando pacote Termux {pkg}...")
        subprocess.run(['pkg', 'install', '-y', pkg], check=True)
        print(f"✅ Pacote Termux {pkg} instalado com sucesso!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao instalar pacote Termux {pkg}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro inesperado ao instalar {pkg}: {e}")
        sys.exit(1)

def instalar_dependencia_python(nome_pkg: str, pip_nome: str) -> None:
    """Verifica e instala uma dependência Python, se necessária."""
    try:
        import importlib
        importlib.import_module(nome_pkg)  # importação direta otimizada
        print(f"✅ Módulo Python {nome_pkg} já está instalado")
    except ImportError:
        print(f"⚠️ Instalando módulo Python {nome_pkg}...")
        sistema = detectar_sistema()
        pip_cmd = [sys.executable, "-m", "pip", "install", pip_nome]
        if not sistema['termux']:
            pip_cmd.append("--user")
            subprocess.run(pip_cmd, check=True)
            print(f"✅ Módulo Python {nome_pkg} instalado com sucesso!")
        try:
            subprocess.run(pip_cmd, check=True)
            print(f"✅ Módulo Python {nome_pkg} instalado com sucesso!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao instalar módulo Python {nome_pkg}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"⚠️ Erro ao atualizar o PATH no Windows: {e}")
            print(f"⚠️ Erro ao atualizar o PATH no Windows: {e}")
        os.environ["PATH"] = bin_dir + ";" + os.environ.get("PATH", "")
        shutil.rmtree(temp_dir, ignore_errors=True)
        subprocess.run([os.path.join(bin_dir, "pdftotext"), "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Poppler foi instalado, mas o pdftotext ainda não está disponível.")
            return False
            print("❌ Sistema operacional não suportado para instalação automática.")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao instalar poppler: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado ao instalar poppler: {e}")
        return False

def verificar_dependencias() -> None:
    """Verifica e instala as dependências necessárias para o sistema atual."""
    sistema = verificar_sistema()
    if sistema['termux']:
        pacotes_termux = ['python', 'python-pip', 'git', 'poppler', 'termux-api', 'ffmpeg']
        for pkg in pacotes_termux:
            instalar_dependencia_termux(pkg)
    dependencias_python = {
        'edge_tts': 'edge-tts>=6.1.5',
        'langdetect': 'langdetect>=1.0.9',
        'unidecode': 'unidecode>=1.3.6',
        'num2words': 'num2words>=0.5.12',
        'chardet': 'chardet>=5.0.0',
        'requests': 'requests>=2.31.0',
        'aioconsole': 'aioconsole>=0.6.0'
    }
    for nome_pkg, pip_nome in dependencias_python.items():
        instalar_dependencia_python(nome_pkg, pip_nome)
    try:
        subprocess.run(['pdftotext', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ pdftotext (poppler) está funcionando corretamente")
    except FileNotFoundError:
        sistema = detectar_sistema()
        if sistema['windows']:
            print("📦 Poppler não encontrado. Iniciando instalação automática...")
            if not instalar_poppler_windows():
                print("❌ Não foi possível instalar o pdftotext automaticamente.")
        elif sistema['macos']:
            print("❌ O pdftotext não está instalado no sistema. Instale com: brew install poppler")
        elif sistema['termux']:
            print("❌ O pdftotext não está instalado no sistema. Tente executar: pkg install poppler")
        else:
            print("❌ O pdftotext não está instalado no sistema. Instale com: sudo apt-get install poppler-utils")
    
    # Verificar FFmpeg
    try:
        subprocess.run([FFMPEG_BIN, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print("✅ FFmpeg está instalado e funcionando")
    except FileNotFoundError:
        print("❌ FFmpeg não está instalado. É necessário para processamento de áudio.")
        if sistema['termux']:
            print("Instale com: pkg install ffmpeg")
        elif sistema['linux']:
            print("Instale com: sudo apt-get install ffmpeg")
        elif sistema['macos']:
            print("Instale com: brew install ffmpeg")
        elif sistema['windows']:
            print("Baixe em: https://ffmpeg.org/download.html")

try:
    from num2words import num2words
    print("✅ num2words importado com sucesso!")
except ImportError:
    print("\n❌ Erro ao importar num2words. Tente instalar manualmente: pip install --user num2words")
    sys.exit(1)

try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    LANG_DETECT_AVAILABLE = True
except ImportError:
    print("\n⚠️ O módulo langdetect não está instalado. Para instalar, execute: pip install langdetect")
    LANG_DETECT_AVAILABLE = False

def limpar_tela() -> None:
    """Limpa a tela do terminal de forma compatível com todos os sistemas."""
    sistema = detectar_sistema()
    if sistema['windows']:
        print("c", end="")
    else:
        print("c", end="")

async def obter_opcao(prompt: str, opcoes: list) -> str:
    """Solicita ao usuário uma entrada que esteja dentre as opções válidas."""
    while True:
        escolha = (await aioconsole.ainput(prompt)).strip()
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
    """Remove ou substitui caracteres inválidos em sistemas de arquivos."""
    nome_limpo = re.sub(r'[<>:"/\\|?*]', '', nome)
    nome_limpo = nome_limpo.replace(' ', '_')
    return nome_limpo

def unificar_audio(temp_files, arquivo_final) -> bool:
    try:
        if shutil.which(FFMPEG_BIN):
            list_file = os.path.join(os.path.dirname(arquivo_final), "file_list.txt")
            with open(list_file, "w") as f:
                for temp in temp_files:
                    f.write(f"file '{os.path.abspath(temp)}'\n")
            subprocess.run([FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", arquivo_final], check=True)
            try:
                os.remove(list_file)
            except Exception as e:
                print(f"⚠️ Não foi possível remover o arquivo temporário da lista: {e}")
            return True
        else:
            print("⚠️ FFmpeg ausente. Não é possível unificar os arquivos corretamente.")
            return False
    except Exception as e:
        print(f"❌ Erro na unificação dos arquivos: {e}")
        return False

async def atualizar_script() -> None:
    """Atualiza o script para a versão mais recente do GitHub."""
    await exibir_banner()
    print("\n🔄 ATUALIZAÇÃO DO SCRIPT")
    print("\nIsso irá baixar a versão mais recente do script do GitHub.")
    confirmar = await obter_opcao("Deseja continuar? (s/n): ", ['s', 'n'])
    if confirmar != 's':
        print("\n❌ Atualização cancelada pelo usuário.")
        await aioconsole.ainput("\nPressione ENTER para continuar...")
        return
    print("\n🔄 Baixando a versão mais recente...")
    script_atual = os.path.abspath(__file__)
    script_backup = script_atual + ".backup"
    try:
        shutil.copy2(script_atual, script_backup)
        print(f"✅ Backup criado: {script_backup}")
    except Exception as e:
        print(f"⚠️ Não foi possível criar backup: {str(e)}")
        await aioconsole.ainput("\nPressione ENTER para continuar...")
        return
    sistema = detectar_sistema()
    url = "https://raw.githubusercontent.com/JonJonesBR/Conversor_TTS/main/Conversor_TTS_com_MP4_09.04.2025.py"
    try:
        if sistema['windows']:
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    with open(script_atual, 'wb') as f:
                        f.write(response.content)
                    print("✅ Script atualizado com sucesso!")
                else:
                    raise Exception(f"Erro ao baixar: código {response.status_code}")
            except ImportError:
                resultado = subprocess.run(["curl", "-o", script_atual, url], capture_output=True, text=True)
                if resultado.returncode != 0:
                    raise Exception(f"Erro curl: {resultado.stderr}")
                print("✅ Script atualizado com sucesso!")
        else:
            resultado = subprocess.run(["curl", "-o", script_atual, url], capture_output=True, text=True)
            if resultado.returncode != 0:
                raise Exception(f"Erro curl: {resultado.stderr}")
            print("✅ Script atualizado com sucesso!")
        print("\n🔄 O script será reiniciado para aplicar as atualizações.")
        await aioconsole.ainput("Pressione ENTER para continuar...")
        python_exec = sys.executable
        os.execl(python_exec, python_exec, script_atual)
    except Exception as e:
        print(f"\n❌ Erro durante a atualização: {str(e)}")
        print(f"\n🔄 Restaurando backup...")
        try:
            shutil.copy2(script_backup, script_atual)
            print("✅ Backup restaurado com sucesso!")
        except Exception as e2:
            print(f"❌ Erro ao restaurar backup: {str(e2)}")
            print(f"⚠️ O backup está disponível em: {script_backup}")
        await aioconsole.ainput("\nPressione ENTER para continuar...")

async def exibir_banner() -> None:
    """Exibe o banner do programa."""
    limpar_tela()
    print("""
╔════════════════════════════════════════════╗
║         CONVERSOR TTS COMPLETO             ║
║ Text-to-Speech + Melhoria de Áudio em PT-BR║
╚════════════════════════════════════════════╝
""")

async def menu_principal() -> str:
    """Exibe o menu principal e retorna a opção escolhida."""
    await exibir_banner()
    print("\nEscolha uma opção:")
    print("1. 🚀 CONVERTER TEXTO PARA ÁUDIO")
    print("2. 🎙️ TESTAR VOZES")
    print("3. ⚡ MELHORAR ÁUDIO EXISTENTE")
    print("4. ❓ AJUDA")
    print("5. 🔄 ATUALIZAR")
    print("6. 🚪 SAIR")
    return await obter_opcao("\nOpção: ", ['1', '2', '3', '4', '5', '6'])

async def menu_vozes() -> str:
    """Exibe o menu de seleção de vozes e retorna a voz escolhida."""
    await exibir_banner()
    print("\nVozes disponíveis:")
    for i, voz in enumerate(VOZES_PT_BR, 1):
        print(f"{i}. {voz}")
    print(f"{len(VOZES_PT_BR) + 1}. Voltar")
    opcoes = [str(i) for i in range(1, len(VOZES_PT_BR) + 2)]
    escolha = await obter_opcao("\nEscolha uma voz: ", opcoes)
    if escolha == str(len(VOZES_PT_BR) + 1):
        return None
    return VOZES_PT_BR[int(escolha) - 1]

async def exibir_ajuda() -> None:
    """Exibe o guia de ajuda do programa."""
    await exibir_banner()
    print("""
📖 GUIA DE USO:

1. CONVERSÃO DE TEXTO PARA ÁUDIO:
   • Prepare seu arquivo de texto (.txt) ou PDF (.pdf)
   • Escolha uma voz e aguarde a conversão
   • O áudio resultante pode ser melhorado na opção 3

2. MELHORIA DE ÁUDIO:
   • Acelere arquivos de áudio/vídeo existentes
   • Escolha entre 0.5x e 2.0x de velocidade
   • Converta para MP3 (áudio) ou MP4 (vídeo com tela preta)
   • Arquivos longos são automaticamente divididos

⚠️ OBSERVAÇÕES:
• Para arquivos muito grandes, o processo pode demorar
• Certifique-se de ter espaço em disco suficiente
• No Android/Termux, os arquivos são salvos em /storage/emulated/0/Download
""")
    await aioconsole.ainput("\nPressione ENTER para voltar ao menu principal...")

async def testar_voz(voz: str) -> None:
    """
    Testa uma voz específica com um texto de exemplo e salva a amostra
    em uma pasta na pasta Download do Android. Após a geração, retorna automaticamente.
    """
    texto_teste = "Olá! Esta é uma demonstração da minha voz."
    communicate = edge_tts.Communicate(texto_teste, voz)
    sistema = detectar_sistema()
    if sistema['android'] or sistema['termux']:
        download_folder = str(Path.home() / "storage" / "downloads")
        test_folder = os.path.join(download_folder, "TTS_Teste_Voz")
        os.makedirs(test_folder, exist_ok=True)
        file_path = os.path.join(test_folder, f"teste_voz_{voz}.mp3")
    else:
        file_path = "teste_voz.mp3"
    try:
        await communicate.save(file_path)
        print(f"\n✅ Arquivo de teste gerado: {file_path}")
        if sistema['termux']:
            if shutil.which("termux-media-player"):
                try:
                    subprocess.run(['termux-media-player', 'play', file_path], timeout=10)
                except subprocess.TimeoutExpired:
                    print("Aviso: reprodução de áudio demorou, continuando...")
            else:
                print("termux-media-player não disponível, áudio não reproduzido.")
        elif sistema['windows']:
            os.startfile(file_path)
        else:
            subprocess.Popen(['xdg-open', file_path])
        
    except Exception as e:
        print(f"\n❌ Erro ao testar voz: {str(e)}")

def listar_arquivos(diretorio: str, extensoes: list = None) -> list:
    """Lista arquivos no diretório especificado, filtrando por extensões se fornecido."""
    arquivos = []
    try:
        for item in os.listdir(diretorio):
            caminho_completo = os.path.join(diretorio, item)
            if os.path.isfile(caminho_completo):
                if not extensoes or os.path.splitext(item)[1].lower() in extensoes:
                    arquivos.append(item)
    except Exception as e:
        print(f"\n⚠️ Erro ao listar arquivos: {str(e)}")
    return sorted(arquivos)

#=== Início da integração do módulo de formatação ===
PADRAO_CAPITULO = re.compile(r'CAP[IÍ]TULO\s+([A-Z0-9]+)\s*[:\-]?\s*(.+)', re.IGNORECASE)
def roman_para_inteiro(romano):
    romanos = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = 0
    anterior = 0
    for letra in romano[::-1]:
        valor = romanos.get(letra, 0)
        total += -valor if valor < anterior else valor
        anterior = valor
    return total
import re

def padronizar_capitulos(texto):
    def substituidor(match):
        capitulo_raw = match.group(1).strip().upper()
        titulo = match.group(2).strip()
        try:
            numero = roman_para_inteiro(capitulo_raw)
        except (ValueError, TypeError):
            numero = capitulo_raw
        return f"CAPÍTULO {numero}: {titulo.title()}"
    texto_formatado = PADRAO_CAPITULO.sub(substituidor, texto)
    return texto_formatado

def normalizar_caixa(texto):
    linhas = texto.splitlines()
    texto_final = []
    for linha in linhas:
        if linha.isupper() and len(linha.strip()) > 3:
            texto_final.append(linha.capitalize())
        else:
            texto_final.append(linha)
    return "\n".join(texto_final)

def separar_capitulos(texto):
    return re.sub(r'(CAP[IÍ]TULO\s+\d+:)', r'\n\n\1', texto)

def gerar_indice(texto):
    padrao = re.compile(r'CAP[IÍ]TULO\s+(\d+):\s+(.+)', re.IGNORECASE)
    return "\n".join([
        f"{match.group(1)}. {match.group(2).title()}" for match in padrao.finditer(texto)
    ])


def limpeza_avancada(texto):
    import re
    texto = re.sub(r'^\s*[IVXLCDM]+\.\s*$', '', texto, flags=re.MULTILINE)  # Remove "I.", "II." etc.
    texto = re.sub(r'\n{3,}', '\n\n', texto)  # Remove quebras de linha excessivas
    texto = re.sub(r'^[ \t]+', '', texto, flags=re.MULTILINE)  # Remove espaços no início das linhas
    return texto

def aplicar_formatacao(texto):
    texto = limpeza_avancada(texto)
    texto = padronizar_capitulos(texto)
    texto = normalizar_caixa(texto)
    texto = separar_capitulos(texto)
    indice = gerar_indice(texto)
    return indice + '\n\n' + texto
def normalizar_texto_corrigir(texto):
    """Normaliza o texto preservando acentos."""
    print("\n[1/5] Normalizando texto...")
    return unicodedata.normalize('NFKC', texto)

def corrigir_espacamento_corrigir(texto):
    """Corrige espaçamentos desnecessários e remove espaços no início e fim das linhas."""
    print("[2/5] Corrigindo espaçamento...")
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'^\s+|\s+$', '', texto, flags=re.MULTILINE)
    return texto

def ajustar_titulo_e_capitulos_corrigir(texto):
    """
    Ajusta título, autor e formata capítulos.
    Tenta separar o cabeçalho (título e autor) se estiver em uma única linha.
    """
    print("[3/5] Ajustando título, autor e capítulos...")
    pattern = r"^(?P<titulo>.+?)\s+(?P<autor>[A-Z][a-z]+(?:\s+[A-Z][a-z]+))\s+(?P<body>.*)$"
    match = re.match(pattern, texto, re.DOTALL)
    if match:
        titulo = match.group("titulo").strip()
        autor = match.group("autor").strip()
        body = match.group("body").strip()
        if not titulo.endswith(('.', '!', '?')):
            titulo += '.'
        if not autor.endswith(('.', '!', '?')):
            autor += '.'
        novo_texto = titulo + "\n" + autor + "\n\n" + body
    else:
        linhas = texto.splitlines()
        header = []
        corpo = []
        non_empty_count = 0
        for linha in linhas:
            if linha.strip():
                non_empty_count += 1
                if non_empty_count <= 2:
                    header.append(linha.strip())
                else:
                    corpo.append(linha)
            else:
                if non_empty_count >= 2:
                    corpo.append(linha)
        if len(header) == 1:
            palavras = header[0].split()
            if len(palavras) >= 4 and palavras[-1][0].isupper() and palavras[-2][0].isupper():
                autor = " ".join(palavras[-2:])
                titulo = " ".join(palavras[:-2])
                header = [titulo.strip(), autor.strip()]
        if header:
            if not header[0].endswith(('.', '!', '?')):
                header[0] += '.'
        if len(header) > 1:
            if not header[1].endswith(('.', '!', '?')):
                header[1] += '.'
        novo_texto = "\n".join(header + [""] + corpo)
    novo_texto = re.sub(r'(?i)\b(capítulo\s*\d+)\b', r'\n\n\1.\n\n', novo_texto)
    return novo_texto

def inserir_quebra_apos_ponto_corrigir(texto):
    """Insere uma quebra de parágrafo após cada ponto final."""
    print("[4/5] Inserindo quebra de parágrafo após cada ponto final...")
    texto = re.sub(r'\.\s+', '.\n\n', texto)
    return texto

def formatar_paragrafos_corrigir(texto):
    """Formata os parágrafos garantindo uma linha em branco entre eles."""
    print("[5/5] Formatando parágrafos...")
    paragrafos = [p.strip() for p in texto.split('\n\n') if p.strip()]
    return '\n\n'.join(paragrafos)

def melhorar_texto_corrigido(texto):
    texto = texto.replace('\f', '\n\n')  # Remove form feeds
    import re

    def remover_num_paginas_rodapes(texto):
        return re.sub(r'\n?\s*\d+\s+cda_pr_.*?\.indd\s+\d+\s+\d+/\d+/\d+\s+\d+:\d+\s+[APM]{2}', '', texto)

    def corrigir_hifenizacao(texto):
        return re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', texto)

    def remover_infos_bibliograficas_rodape(texto):
        return re.sub(r'^\s*(cda_pr_.*?\.indd.*?)$', '', texto, flags=re.MULTILINE)

    def converter_capitulos_para_extenso_simples(texto):
        substituicoes = {
            'CAPÍTULO I': 'CAPÍTULO UM',
            'CAPÍTULO II': 'CAPÍTULO DOIS',
            'CAPÍTULO III': 'CAPÍTULO TRÊS',
            'CAPÍTULO IV': 'CAPÍTULO QUATRO',
            'CAPÍTULO V': 'CAPÍTULO CINCO',
            'CAPÍTULO VI': 'CAPÍTULO SEIS',
            'CAPÍTULO VII': 'CAPÍTULO SETE',
            'CAPÍTULO VIII': 'CAPÍTULO OITO',
            'CAPÍTULO IX': 'CAPÍTULO NOVE',
            'CAPÍTULO X': 'CAPÍTULO DEZ',
        }
        for original, novo in substituicoes.items():
            texto = texto.replace(original, novo)
        return texto

    def pontuar_finais_de_paragrafo(texto):
        paragrafos = texto.split('\n\n')
        paragrafos_corrigidos = []
        for p in paragrafos:
            p = p.strip()
            if p and not re.search(r'[.!?…]$', p):
                p += '.'
            paragrafos_corrigidos.append(p)
        return '\n\n'.join(paragrafos_corrigidos)

    texto = remover_num_paginas_rodapes(texto)
    texto = corrigir_hifenizacao(texto)
    texto = remover_infos_bibliograficas_rodape(texto)
    texto = converter_capitulos_para_extenso_simples(texto)
    texto = pontuar_finais_de_paragrafo(texto)
    return texto

def verificar_e_corrigir_arquivo(caminho_txt: str) -> str:
    """
    Verifica se o arquivo TXT já foi processado (contém o sufixo '_formatado').
    Caso não, lê o arquivo, o processa e o salva com o sufixo, retornando o novo caminho.
    """
    base, ext = os.path.splitext(caminho_txt)
    if base.endswith("_formatado"):
        return caminho_txt
    try:
        with open(caminho_txt, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            conteudo_corrigido = aplicar_formatacao(conteudo)
    except Exception as e:
        print(f'❌ Erro ao ler o arquivo TXT: {e}')
        return caminho_txt
    try:
        novo_caminho = base + "_formatado" + ext
        with open(novo_caminho, 'w', encoding='utf-8') as f:
            f.write(conteudo_corrigido)
        print(f"✅ Arquivo corrigido e salvo em: {novo_caminho}")
    except Exception as e:
        print(f"❌ Erro ao salvar o arquivo corrigido: {e}")
        return caminho_txt
    return novo_caminho
    try:
        with open(caminho_txt, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            conteudo = limpeza_avancada(conteudo)
    except Exception as e:
        print(f'❌ Erro ao ler o arquivo TXT: {e}')
        return caminho_txt
    try:
        with open(novo_caminho, 'w', encoding='utf-8') as f:
            f.write(conteudo_corrigido)
        print(f"✅ Arquivo corrigido e salvo em: {novo_caminho}")
    except Exception as e:
        print(f"❌ Erro ao salvar o arquivo corrigido: {e}")
        return caminho_txt
    return novo_caminho

# ================== FUNÇÕES DE MELHORIA DE ÁUDIO ==================

def obter_duracao_ffprobe(caminho_arquivo):
    """Obtém a duração de um arquivo de mídia usando ffprobe."""
    comando = [
        FFPROBE_BIN,
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        caminho_arquivo
    ]
    resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(resultado.stdout.strip())

def acelerar_audio(input_path, output_path, velocidade):
    """Acelera um arquivo de áudio usando o filtro atempo do FFmpeg."""
    comando = [
        FFMPEG_BIN,
        '-y',
        '-i', input_path,
        '-filter:a', f"atempo={velocidade}",
        '-vn',
        output_path
    ]
    subprocess.run(comando, check=True)

def criar_video_com_audio(audio_path, video_path, duracao):
    """Cria um vídeo com tela preta a partir de um arquivo de áudio."""
    comando = [
        FFMPEG_BIN,
        '-y',
        '-f', 'lavfi',
        '-i', f"color=c=black:s=1280x720:d={int(duracao)}",
        '-i', audio_path,
        '-shortest',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        video_path
    ]
    subprocess.run(comando, check=True)

def dividir_em_partes(input_path, duracao_total, duracao_maxima, nome_base_saida, extensao):

        with tqdm(total=partes, desc="Dividindo partes", unit="parte(s)", dynamic_ncols=True) as pbar:
            for i in range(partes):
                inicio = i * duracao_maxima
                duracao = min(duracao_maxima, duracao_total - inicio)
                output_path = f"{nome_base_saida}_parte{i+1}{extensao}"
                comando = [
                    FFMPEG_BIN,
                    '-y',
                    '-i', input_path,
                    '-ss', str(int(inicio)),
                    '-t', str(int(duracao)),
                    '-c', 'copy',
                    output_path
                ]
                subprocess.run(comando, check=True)
                print(f"    Parte {i+1} criada: {output_path}")
                pbar.update(1)

        inicio = i * duracao_maxima
        duracao = min(duracao_maxima, duracao_total - inicio)

        output_path = f"{nome_base_saida}_parte{i+1}{extensao}"

        comando = [
            FFMPEG_BIN,
            '-y',
            '-i', input_path,
            '-ss', str(int(inicio)),
            '-t', str(int(duracao)),
            '-c', 'copy',
            output_path
        ]
        subprocess.run(comando, check=True)
        print(f"    Parte {i+1} criada: {output_path}")

async def menu_melhorar_audio():
    """Menu para melhorar arquivos de áudio/vídeo existentes."""
    await exibir_banner()
    print("\n⚡ MELHORAR ÁUDIO EXISTENTE")
    
    sistema = detectar_sistema()
    if sistema['termux'] or sistema['android']:
        dir_atual = '/storage/emulated/0/Download'
    elif sistema['windows']:
        dir_atual = os.path.join(os.path.expanduser('~'), 'Desktop')
    else:
        dir_atual = os.path.join(os.path.expanduser('~'), 'Desktop')
    
    while True:
        print(f"\nDiretório atual: {dir_atual}")
        print("\nArquivos de áudio/vídeo disponíveis:")
        arquivos = listar_arquivos(dir_atual, ['.mp3', '.wav', '.m4a', '.mp4'])
        
        if not arquivos:
            print("\n⚠️ Nenhum arquivo de áudio/vídeo encontrado neste diretório")
        else:
            for i, arquivo in enumerate(arquivos, 1):
                print(f"{i}. {arquivo}")
        
        print("\nOpções:")
        print("D. Mudar diretório")
        print("M. Digitar caminho manualmente")
        print("V. Voltar ao menu principal")
        
        escolha = (await aioconsole.ainput("\nEscolha uma opção: ")).strip().upper()
        
        if escolha == 'V':
            return
        elif escolha == 'D':
            novo_dir = (await aioconsole.ainput("\nDigite o caminho do novo diretório: ")).strip()
            if os.path.isdir(novo_dir):
                dir_atual = novo_dir
            else:
                print("\n❌ Diretório inválido")
                
        elif escolha == 'M':
            caminho = (await aioconsole.ainput("\nDigite o caminho completo do arquivo: ")).strip()
            if not os.path.exists(caminho):
                print(f"\n❌ Arquivo não encontrado: {caminho}")
                
                continue
            ext = os.path.splitext(caminho)[1].lower()
            if ext not in ['.mp3', '.wav', '.m4a', '.mp4']:
                print("\n❌ Formato não suportado. Use MP3, WAV, M4A ou MP4.")
                
                continue
            await processar_melhorar_audio(caminho)
            return
        elif escolha.isdigit():
            indice = int(escolha) - 1
            if 0 <= indice < len(arquivos):
                arquivo_selecionado = arquivos[indice]
                caminho_completo = os.path.join(dir_atual, arquivo_selecionado)
                await processar_melhorar_audio(caminho_completo)
                return
            else:
                print("\n❌ Opção inválida")
                
        else:
            print("\n❌ Opção inválida")


async def converter_texto_para_audio(texto: str, voz: str, caminho_saida: str) -> bool:
    """Converte texto para áudio usando Edge TTS."""
    tentativas = 0
    while tentativas < MAX_TENTATIVAS:
        try:
            if not texto.strip():
                print("⚠️ Texto vazio detectado")
                return False
                
            communicate = edge_tts.Communicate(texto, voz)
            await communicate.save(caminho_saida)
            
            # Verifica se o arquivo foi criado e tem tamanho mínimo
            if os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 1024:
                return True
            else:
                print("⚠️ Arquivo de áudio vazio ou muito pequeno")
                if os.path.exists(caminho_saida):
                    os.remove(caminho_saida)
                return False
        except Exception as e:
            tentativas += 1
            print(f"\n❌ Erro na conversão (tentativa {tentativas}/{MAX_TENTATIVAS}): {str(e)}")
            if os.path.exists(caminho_saida):
                os.remove(caminho_saida)
            if tentativas < MAX_TENTATIVAS:
                await asyncio.sleep(2)  # Espera antes de tentar novamente
    return False

# ================== FUNÇÕES DE SELEÇÃO E CONVERSÃO DE ARQUIVOS ==================

async def selecionar_arquivo() -> str:
    """
    Interface aprimorada para seleção de arquivo com navegação por diretórios.
    Se o usuário selecionar um PDF, ele é convertido para TXT e o arquivo gerado é corrigido.
    Se for um arquivo TXT e o nome não contiver '_formatado', o arquivo é automaticamente corrigido.
    """
    sistema = detectar_sistema()
    if sistema['termux'] or sistema['android']:
        dir_atual = '/storage/emulated/0/Download'
    elif sistema['windows']:
        dir_atual = os.path.join(os.path.expanduser('~'), 'Desktop')
    else:
        dir_atual = os.path.join(os.path.expanduser('~'), 'Desktop')
    while True:
        await exibir_banner()
        print("\n📂 SELEÇÃO DE ARQUIVO")
        print(f"\nDiretório atual: {dir_atual}")
        print("\nArquivos disponíveis:")
        arquivos = listar_arquivos(dir_atual, ['.txt', '.pdf'])
        if not arquivos:
            print("\n⚠️ Nenhum arquivo TXT ou PDF encontrado neste diretório")
        else:
            for i, arquivo in enumerate(arquivos, 1):
                print(f"{i}. {arquivo}")
        print("\nOpções:")
        print("D. Mudar diretório")
        print("M. Digitar caminho manualmente")
        print("V. Voltar ao menu principal")
        try:
            escolha = (await aioconsole.ainput("\nEscolha uma opção: ")).strip().upper()
        except asyncio.TimeoutError:
            return ''
        
        if escolha == 'V':
            return ''
        elif escolha == 'D':
            novo_dir = (await aioconsole.ainput("\nDigite o caminho do novo diretório: ")).strip()
            if os.path.isdir(novo_dir):
                dir_atual = novo_dir
            else:
                print("\n❌ Diretório inválido")
                
        elif escolha == 'M':
            caminho = (await aioconsole.ainput("\nDigite o caminho completo do arquivo: ")).strip()
            if not os.path.exists(caminho):
                print(f"\n❌ Arquivo não encontrado: {caminho}")
                
                continue
            ext = os.path.splitext(caminho)[1].lower()
            if ext == '.pdf':
                caminho_txt = os.path.splitext(caminho)[0] + '.txt'
                if not converter_pdf(caminho, caminho_txt):
                    print("\n⚠️ Falha na conversão do PDF. Tente outro arquivo.")
                    
                    continue
                # Após converter, verifica se o TXT já foi corrigido
                try:
                    with open(caminho_txt, 'r', encoding='utf-8') as f:
                        texto_original = f.read()
                        texto = limpeza_avancada(texto)
                    texto_formatado = aplicar_formatacao(texto_original)
                    caminho_txt = os.path.splitext(caminho_txt)[0] + '_formatado.txt'
                    with open(caminho_txt, 'w', encoding='utf-8') as f:
                        f.write(texto_formatado)
                    print(f'✅ Formatação aplicada e salva em: {caminho_txt}')
                except Exception as e:
                    print(f'❌ Erro ao aplicar formatação: {e}')
                caminho_txt = verificar_e_corrigir_arquivo(caminho_txt)
                editar = (await aioconsole.ainput("\nDeseja editar o arquivo TXT corrigido? (s/n): ")).strip().lower()
                if editar == 's':
                    if sistema['android']:
                        print("\nO arquivo TXT corrigido foi salvo no diretório padrão (normalmente Download).")
                        print("Após editá-lo, reinicie a conversão selecionando-o neste script pela opção 1 do menu inicial.")
                        await aioconsole.ainput("\nPressione ENTER para retornar ao menu principal...")
                        texto_formatado = aplicar_formatacao(texto_original)
                        caminho_formatado = os.path.splitext(caminho)[0] + '_formatado.txt'
                        with open(caminho_formatado, 'w', encoding='utf-8') as f:
                            f.write(texto_formatado)
                        print(f'✅ Formatação aplicada ao TXT e salva em: {caminho_formatado}')
                        caminho = caminho_formatado
                        print(f'❌ Erro ao aplicar formatação ao TXT: {e}')
                return caminho
            else:
                print(f"\n❌ Formato não suportado: {ext}")
                print("💡 Apenas arquivos .txt e .pdf são suportados")
                
        elif escolha.isdigit():
            indice = int(escolha) - 1
            if 0 <= indice < len(arquivos):
                arquivo_selecionado = arquivos[indice]
                caminho_completo = os.path.join(dir_atual, arquivo_selecionado)
                ext = os.path.splitext(arquivo_selecionado)[1].lower()
                if ext == '.pdf':
                    caminho_txt = os.path.splitext(caminho_completo)[0] + '.txt'
                    if not converter_pdf(caminho_completo, caminho_txt):
                        print("\n⚠️ Falha na conversão do PDF. Tente outro arquivo.")
                        
                        continue
                    # Corrige o TXT gerado, se necessário
                    caminho_txt = verificar_e_corrigir_arquivo(caminho_txt)
                    editar = (await aioconsole.ainput("\nDeseja editar o arquivo TXT corrigido? (s/n): ")).strip().lower()
                    if editar == 's':
                        if sistema['android']:
                            print("\nO arquivo TXT corrigido foi salvo no diretório padrão (normalmente Download).")
                            print("Após editá-lo, reinicie a conversão selecionando-o neste script pela opção 1 do menu inicial.")
                            await aioconsole.ainput("\nPressione ENTER para retornar ao menu principal...")
                            return ''
                        else:
                            if sistema['windows']:
                                os.startfile(caminho_txt)
                            elif sistema['macos']:
                                subprocess.Popen(["open", caminho_txt])
                            else:
                                subprocess.Popen(["xdg-open", caminho_txt])
                            await aioconsole.ainput("\nEdite o arquivo, salve as alterações e pressione ENTER para continuar...")
                    return caminho_txt
                elif ext == '.txt':
                    if not os.path.basename(caminho_completo).lower().endswith("_formatado.txt"):
                        caminho_completo = verificar_e_corrigir_arquivo(caminho_completo)
                    return caminho_completo
                else:
                    return caminho_completo
            else:
                print("\n❌ Opção inválida")
                print(f'❌ Erro detectado no bloco try da linha %d: {e}' % 1404)
                
        else:
            print("\n❌ Opção inválida")
            

            
# ================== FUNÇÕES DE CONVERSÃO TTS ==================

async def iniciar_conversao() -> None:
    """
    Inicia o processo de conversão de texto para áudio de forma concorrente.
    O tamanho dos chunks é calculado dinamicamente.
    """
    global CANCELAR_PROCESSAMENTO
    CANCELAR_PROCESSAMENTO = False
    
    try:
        caminho_arquivo = await selecionar_arquivo()
        if not caminho_arquivo or CANCELAR_PROCESSAMENTO:
            return

        voz_escolhida = await menu_vozes()
        if voz_escolhida is None or CANCELAR_PROCESSAMENTO:
            return

        print("\n📖 Lendo arquivo...")
        texto = ler_arquivo_texto(caminho_arquivo)
        if not texto or CANCELAR_PROCESSAMENTO:
            print("\n❌ Arquivo vazio ou ilegível")
            await asyncio.sleep(2)
            return

        print("🔄 Processando texto...")
        texto_processado = processar_texto(texto)
        
        partes = dividir_texto(texto_processado)
        total_partes = len(partes)
        print(f"\n📊 Texto dividido em {total_partes} parte(s).")
        print("Para interromper a conversão a qualquer momento, pressione CTRL + C.\n")

        nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
        nome_base = limpar_nome_arquivo(nome_base)
        diretorio_saida = os.path.join(os.path.dirname(caminho_arquivo), f"{nome_base}_audio")

        if not os.path.exists(diretorio_saida):
            os.makedirs(diretorio_saida)

        temp_files = []
        start_time = time.time()
        semaphore = asyncio.Semaphore(5)  # Limite de 5 tarefas simultâneas

        async def processar_chunk(i, parte):
            async with semaphore:
                if CANCELAR_PROCESSAMENTO:
                    return None
                
                saida_temp = os.path.join(diretorio_saida, f"{nome_base}_temp_{i:03d}.mp3")
                temp_files.append(saida_temp)
                
                tentativa = 1
                while tentativa <= MAX_TENTATIVAS:
                    if CANCELAR_PROCESSAMENTO:
                        return None
                    
                    inicio_chunk = time.time()
                    sucesso = await converter_texto_para_audio(parte, voz_escolhida, saida_temp)
                    
                    if sucesso:
                        tempo_chunk = time.time() - inicio_chunk
                        print(f"✅ Parte {i}/{total_partes} | Tentativa {tentativa}/{MAX_TENTATIVAS} | Tempo: {tempo_chunk:.1f}s")
                        return True
                    else:
                        print(f"🔄 Tentativa {tentativa}/{MAX_TENTATIVAS} falhou para parte {i}. Reiniciando...")
                        tentativa += 1
                        await asyncio.sleep(2)  # Intervalo entre tentativas
                
                print(f"❌ Falha definitiva na parte {i} após {MAX_TENTATIVAS} tentativas")
                return False

        tasks = [processar_chunk(i+1, p) for i, p in enumerate(partes)]
        results = await asyncio.gather(*tasks)
        
        # Verificar se todas as partes foram convertidas
        if not all(results):
            print("\n⚠️ Algumas partes falharam. Não é possível unificar.")
            return
        
        if not CANCELAR_PROCESSAMENTO and any(results):
            print("\n🔄 Unificando arquivos...")
            arquivo_final = os.path.join(diretorio_saida, f"{nome_base}.mp3")
            
            if unificar_audio(temp_files, arquivo_final):
                for f in temp_files:
                    if os.path.exists(f):
                        os.remove(f)
                overall_time = time.time() - start_time
                print(f"\n🎉 Conversão concluída em {overall_time:.1f} s! Arquivo final: {arquivo_final}")
                
                # Pergunta se deseja melhorar o áudio
                melhorar = (await aioconsole.ainput("\nDeseja melhorar o áudio gerado (ajustar velocidade)? (s/n): ")).strip().lower()
                if melhorar == 's':
                    await processar_melhorar_audio(arquivo_final)
            else:
                print("\n❌ Falha na unificação dos arquivos.")

        await aioconsole.ainput("\nPressione ENTER para continuar...")

    except asyncio.CancelledError:
        print("\n🚫 Operação cancelada pelo usuário")
    finally:
        CANCELAR_PROCESSAMENTO = True
        if 'temp_files' in locals():
            for f in temp_files:
                if os.path.exists(f):
                    os.remove(f)
        

async def main() -> None:
    """Função principal do programa."""
    verificar_dependencias()
    
    # Configura política de event loop para Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    while True:
        opcao = await menu_principal()
        if opcao == '1':
            await iniciar_conversao()
        elif opcao == '2':
            while True:
                voz_escolhida = await menu_vozes()
                if voz_escolhida is None:
                    break
                print(f"\n🎙️ Testando voz: {voz_escolhida}")
                await testar_voz(voz_escolhida)
        elif opcao == '3':
            await menu_melhorar_audio()
        elif opcao == '4':
            await exibir_ajuda()
        elif opcao == '5':
            await atualizar_script()
        elif opcao == '6':
            print("👋 Obrigado por usar o Conversor TTS Completo!")
            break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Programa interrompido pelo usuário.")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {str(e)}")




        print('Sistema operacional não reconhecido.')