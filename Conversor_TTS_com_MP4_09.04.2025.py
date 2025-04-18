import html2text
from bs4 import BeautifulSoup

# === Início da integração do módulo de formatação ===
import re

def padronizar_capitulos(texto):
    conversao_manual = {
        'UM': 1, 'UMI': 2, 'UMII': 3, 'UMIII': 4, 'UMIV': 5, 'UMV': 6, 'UMVI': 7,
        'CINCO': 5, 'CINCOI': 6, 'CINCOII': 7, 'CINCOIII': 8, 'CINCOIV': 9, 'CINCOV': 10,
        'UMX': 9, 'DEZ': 10, 'DEZI': 11, 'ONZE': 11, 'DOZE': 12
    }

    def substituidor(match):
        capitulo = match.group(1).strip().upper()
        titulo = match.group(2).strip()
        numero = conversao_manual.get(capitulo, capitulo)
        return f"CAPÍTULO {numero}: {titulo.title()}"

    padrao = re.compile(r'CAP[IÍ]TULO\s+([A-Z0-9]+)\s*[:\-]?\s*(.+)', re.IGNORECASE)
    texto_formatado = padrao.sub(substituidor, texto)
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
    """
    Ajusta a marcação dos capítulos para:
    'CAPÍTULO 1.' (com ponto final e duas quebras de linha antes e depois).
    """
    # Padrão para encontrar "Capítulo" ou "CAPÍTULO" seguido de número (com ou sem :)
    padrao = re.compile(
        r'(CAP[IÍ]TULO\s+\d+)\s*:?\s*',
        flags=re.IGNORECASE
    )
    
    # Substitui por "\n\nCAPÍTULO X.\n\n" (mantendo maiúsculas e adicionando ponto)
    texto_formatado = padrao.sub(
        lambda m: f"\n\n{m.group(1).upper()}.\n\n",
        texto
    )
    
    return texto_formatado

def remover_numeracao_avulsa(texto):
    """
    Remove numerações isoladas no início de linhas (como números de página ou listas não desejadas).
    """
    linhas = texto.splitlines()
    novas_linhas = []
    for linha in linhas:
        if re.match(r'^\s*\d+\s*$', linha):  # Linha contém apenas números (possivelmente página)
            continue
        novas_linhas.append(linha)
    return '\n'.join(novas_linhas)

def aplicar_formatacao(texto):
    texto = remover_numeracao_avulsa(texto)
    texto = padronizar_capitulos(texto)
    texto = normalizar_caixa(texto)
    
    # Remover quebras de linha excessivas (exceto após pontos finais)
    texto = re.sub(r'(?<!\n)\n(?!\n|\.\s*)', ' ', texto)  # Remove quebras de linha únicas
    texto = re.sub(r'\n{3,}', '\n\n', texto)  # Limita múltiplas quebras para no máximo duas
    
    # Garantir que haja quebras de linha apenas após pontos finais
    texto = re.sub(r'\.\s+', '.\n\n', texto)  # Quebra após pontos finais
    
    texto = separar_capitulos(texto)
    return texto


# === Fim da integração ===

#!/usr/bin/env python3
import os
import sys
import subprocess
import asyncio
import re
import signal
from pathlib import Path
import select
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
        site.addsitedir(site.getusersitepackages())
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
        with open(caminho_pdf, 'rb') as _:
            pass
    except PermissionError:
        print(f"❌ Sem permissão para acessar o arquivo: {caminho_pdf}")
        return False
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
        __import__(nome_pkg)
        print(f"✅ Módulo Python {nome_pkg} já está instalado")
    except ImportError:
        print(f"⚠️ Instalando módulo Python {nome_pkg}...")
        sistema = detectar_sistema()
        pip_cmd = [sys.executable, "-m", "pip", "install", pip_nome]
        if not sistema['termux']:
            pip_cmd.append("--user")
        try:
            subprocess.run(pip_cmd, check=True)
            print(f"✅ Módulo Python {nome_pkg} instalado com sucesso!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao instalar módulo Python {nome_pkg}: {e}")
            sys.exit(1)

def instalar_poppler() -> bool:
    """Instala o pacote poppler (pdftotext) de acordo com o sistema operacional."""
    sistema = detectar_sistema()
    print("⚠️ O pdftotext não está instalado. Tentando instalar automaticamente...")
    try:
        if sistema['termux']:
            subprocess.run(['pkg', 'install', '-y', 'poppler'], check=True)
            print("✅ poppler instalado com sucesso no Termux!")
            return True
        elif sistema['linux']:
            print("⚠️ Instalando poppler-utils no Linux...")
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'poppler-utils'], check=True)
            print("✅ poppler-utils instalado com sucesso no Linux!")
            return True
        elif sistema['macos']:
            print("⚠️ Instalando poppler no macOS via Homebrew...")
            try:
                subprocess.run(['brew', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except FileNotFoundError:
                print("❌ Homebrew não está instalado no macOS. Instale-o e depois execute: brew install poppler")
                return False
            subprocess.run(['brew', 'install', 'poppler'], check=True)
            print("✅ poppler instalado com sucesso no macOS!")
            return True
        elif sistema['windows']:
            print("⚠️ Instalando Poppler no Windows...")
            import tempfile, urllib.request, winreg
            poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.11.0-0/Release-23.11.0-0.zip"
            try:
                temp_dir = tempfile.mkdtemp()
                zip_path = os.path.join(temp_dir, "poppler.zip")
                print("📥 Baixando Poppler...")
                urllib.request.urlretrieve(poppler_url, zip_path)
                program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
                poppler_dir = os.path.join(program_files, "Poppler")
                os.makedirs(poppler_dir, exist_ok=True)
                print("📦 Extraindo arquivos...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    root_dirs = {item.split('/')[0] for item in zip_ref.namelist() if '/' in item}
                    if len(root_dirs) == 1:
                        root_dir = root_dirs.pop()
                        zip_ref.extractall(temp_dir)
                        extracted_dir = os.path.join(temp_dir, root_dir)
                        for item in os.listdir(extracted_dir):
                            src = os.path.join(extracted_dir, item)
                            dst = os.path.join(poppler_dir, item)
                            if os.path.exists(dst):
                                if os.path.isdir(dst):
                                    shutil.rmtree(dst)
                                else:
                                    os.remove(dst)
                            shutil.move(src, dst)
                    else:
                        zip_ref.extractall(poppler_dir)
                print("🔧 Adicionando ao PATH do sistema...")
                bin_dir = os.path.join(poppler_dir, "bin")
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
                    try:
                        path, _ = winreg.QueryValueEx(key, "PATH")
                        if bin_dir.lower() not in path.lower():
                            new_path = path + ";" + bin_dir
                            winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
                            subprocess.run(["setx", "PATH", new_path], check=True, capture_output=True)
                    except FileNotFoundError:
                        winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, bin_dir)
                    finally:
                        winreg.CloseKey(key)
                except Exception as e:
                    print(f"⚠️ Erro ao atualizar o PATH no Windows: {e}")
                os.environ["PATH"] = bin_dir + ";" + os.environ.get("PATH", "")
                shutil.rmtree(temp_dir, ignore_errors=True)
                print("✅ Poppler instalado com sucesso no Windows!")
                print("⚠️ Você pode precisar reiniciar o terminal para que as alterações no PATH tenham efeito.")
                try:
                    subprocess.run([os.path.join(bin_dir, "pdftotext"), "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    print("⚠️ Poppler foi instalado, mas o pdftotext ainda não está disponível.")
                    return False
            except Exception as e:
                print(f"❌ Erro durante a instalação automática do Poppler: {str(e)}")
                return False
        else:
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
        os.system("cls")
    else:
        os.system("clear")

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

async def menu_converter_mp3_para_mp4():
    await exibir_banner()
    print("\n🎬 CONVERTER MP3 PARA MP4")

    dir_download = "/storage/emulated/0/Download"
    arquivos = listar_arquivos(dir_download, ['.mp3'])

    if not arquivos:
        print("\n⚠️ Nenhum arquivo MP3 encontrado na pasta Download.")
        await aioconsole.ainput("\nPressione ENTER para voltar ao menu...")
        return

    print("\nArquivos MP3 encontrados:")
    for i, nome in enumerate(arquivos, 1):
        print(f"{i}. {nome}")

    escolha = await obter_opcao("\nDigite o número do arquivo MP3 para converter: ", [str(i) for i in range(1, len(arquivos) + 1)])
    arquivo_escolhido = arquivos[int(escolha) - 1]
    caminho_mp3 = os.path.join(dir_download, arquivo_escolhido)

    try:
        duracao = obter_duracao_ffprobe(caminho_mp3)
        saida_mp4 = os.path.splitext(caminho_mp3)[0] + ".mp4"
        criar_video_com_audio(caminho_mp3, saida_mp4, duracao)
        print(f"\n✅ Vídeo gerado com sucesso: {saida_mp4}")
    except Exception as e:
        print(f"\n❌ Erro ao gerar vídeo: {e}")

    await aioconsole.ainput("\nPressione ENTER para continuar...")

def unificar_audio(temp_files, arquivo_final) -> bool:
    """Une os arquivos de áudio temporários em um único arquivo final."""
    try:
        if shutil.which(FFMPEG_BIN):
            list_file = os.path.join(os.path.dirname(arquivo_final), "file_list.txt")
            with open(list_file, "w") as f:
                for temp in temp_files:
                    f.write(f"file '{os.path.abspath(temp)}'\n")
            subprocess.run([FFMPEG_BIN, "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", arquivo_final], check=True)
            os.remove(list_file)
        else:
            # Fallback: concatenação binária (pode não funcionar perfeitamente para mp3)
            with open(arquivo_final, "wb") as outfile:
                for temp in temp_files:
                    with open(temp, "rb") as infile:
                        outfile.write(infile.read())
        return True
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
    print("6. 🎬 CONVERTER MP3 PARA MP4")
    print("7. 🚪 SAIR")
    return await obter_opcao("\nOpção: ", ['1', '2', '3', '4', '5', '6', '7'])

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

6. CONVERTER MP3 PARA MP4:
   • Gere vídeos com tela preta a partir de arquivos de áudio MP3
   • Útil para publicar conteúdos de áudio em plataformas como YouTube

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
        download_folder = "/storage/emulated/0/Download"
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
        await asyncio.sleep(1)
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

# ================== FUNÇÕES DE CORREÇÃO DE TEXTO ==================

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
    
    # Primeiro normaliza espaços em branco e quebras existentes
    texto = re.sub(r'\s+', ' ', texto)  # Substitui múltiplos espaços por um único
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)  # Remove quebras de linha isoladas
    
    # Insere quebras de parágrafo apenas após pontos finais
    texto = re.sub(r'\.\s+', '.\n\n', texto)
    
    # Remove possíveis múltiplas quebras criadas
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    
    # Garante que não haja espaços antes de quebras
    texto = re.sub(r' +\n', '\n', texto)
    
    return texto

def formatar_paragrafos_corrigir(texto):
    """Formata os parágrafos garantindo uma linha em branco entre eles."""
    print("[5/5] Formatando parágrafos...")
    paragrafos = [p.strip() for p in texto.split('\n\n') if p.strip()]
    return '\n\n'.join(paragrafos)

def expandir_abreviacoes(texto):
    abreviacoes = {
    r'\bDr\.(?=\s)': 'Doutor',
    r'\bD\.(?=\s)': 'Dona',
    r'\bDra\.(?=\s)': 'Doutora',
    r'\bSr\.(?=\s)': 'Senhor',
    r'\bSra\.(?=\s)': 'Senhora',
    r'\bSrta\.(?=\s)': 'Senhorita',
    r'\bProf\.(?=\s)': 'Professor',
    r'\bProfa\.(?=\s)': 'Professora',
    r'\bEng\.(?=\s)': 'Engenheiro',
    r'\bEngª\.(?=\s)': 'Engenheira',
    r'\bAdm\.(?=\s)': 'Administrador',
    r'\bAdv\.(?=\s)': 'Advogado',
    r'\bExmo\.(?=\s)': 'Excelentíssimo',
    r'\bExma\.(?=\s)': 'Excelentíssima',
    r'\bV\.Exa\.(?=\s)': 'Vossa Excelência',
    r'\bV\.Sa\.(?=\s)': 'Vossa Senhoria',
    r'\bAv\.(?=\s)': 'Avenida',
    r'\bR\.(?=\s)': 'Rua',
    r'\bKm\.(?=\s)': 'Quilômetro',
    r'\betc\.(?=\s)': 'etcétera',
    r'\bRef\.(?=\s)': 'Referência',
    r'\bPag\.(?=\s)': 'Página',
    r'\bPág\.(?=\s)': 'Página',
    r'\bPágs\.(?=\s)': 'Páginas',
    r'\bPags\.(?=\s)': 'Páginas',
    r'\bFl\.(?=\s)': 'Folha',
    r'\bPe\.(?=\s)': 'Padre',
    r'\bFls\.(?=\s)': 'Folhas',
    r'\bDept\.(?=\s)': 'Departamento',
    r'\bDepto\.(?=\s)': 'Departamento',
    r'\bUniv\.(?=\s)': 'Universidade',
    r'\bInst\.(?=\s)': 'Instituição',
    r'\bEst\.(?=\s)': 'Estado',
    r'\bTel\.(?=\s)': 'Telefone',
    r'\bCEP\.(?=\s)': 'Código de Endereçamento Postal',
    r'\bCNPJ\.(?=\s)': 'Cadastro Nacional da Pessoa Jurídica',
    r'\bCPF\.(?=\s)': 'Cadastro de Pessoas Físicas',
    r'\bEUA\.(?=\s)': 'Estados Unidos da América',
    r'\bEd\.(?=\s)': 'Edição',
    r'\bLtda\.(?=\s)': 'Limitada'
}
    for abrev, extensao in abreviacoes.items():
        texto = re.sub(abrev, extensao, texto)
    return texto

def melhorar_texto_corrigido(texto):
    texto = texto.replace('\f', '\n\n')  # Remove form feeds
    texto = remover_numeracao_avulsa(texto)
    
    # Remover quebras de linha excessivas (exceto após pontos finais)
    texto = re.sub(r'(?<!\n)\n(?!\n|\.\s*)', ' ', texto)  # Remove quebras de linha únicas
    texto = re.sub(r'\n{3,}', '\n\n', texto)  # Limita múltiplas quebras para no máximo duas
    
    # Garantir quebras de linha apenas após pontos finais
    texto = re.sub(r'\.\s+', '.\n\n', texto)
    
    # Funções auxiliares mantidas conforme original
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

    # Aplicar as funções auxiliares
    texto = remover_num_paginas_rodapes(texto)
    texto = corrigir_hifenizacao(texto)
    texto = remover_infos_bibliograficas_rodape(texto)
    texto = converter_capitulos_para_extenso_simples(texto)
    
    # Garantir que cada parágrafo termine com pontuação
    paragrafos = texto.split('\n\n')
    paragrafos_corrigidos = []
    for p in paragrafos:
        p = p.strip()
        if p and not re.search(r'[.!?…]$', p):
            p += '.'
        paragrafos_corrigidos.append(p)
    texto = '\n\n'.join(paragrafos_corrigidos)
    
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
    texto = expandir_abreviacoes(texto)
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
    except Exception as e:
        print(f"❌ Erro ao ler o arquivo TXT: {e}")
        return caminho_txt
    conteudo_corrigido = melhorar_texto_corrigido(conteudo)
    novo_caminho = base + "_formatado" + ext
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
    """Divide um arquivo de mídia em partes menores."""
    partes = ceil(duracao_total / duracao_maxima)
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
                await asyncio.sleep(1)
        elif escolha == 'M':
            caminho = (await aioconsole.ainput("\nDigite o caminho completo do arquivo: ")).strip()
            if not os.path.exists(caminho):
                print(f"\n❌ Arquivo não encontrado: {caminho}")
                await asyncio.sleep(1)
                continue
            ext = os.path.splitext(caminho)[1].lower()
            if ext not in ['.mp3', '.wav', '.m4a', '.mp4']:
                print("\n❌ Formato não suportado. Use MP3, WAV, M4A ou MP4.")
                await asyncio.sleep(1)
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
                await asyncio.sleep(1)
        else:
            print("\n❌ Opção inválida")
            await asyncio.sleep(1)

from pathlib import Path

async def processar_melhorar_audio(arquivo):
    """Processa a melhoria de um arquivo de áudio/vídeo."""
    global CANCELAR_PROCESSAMENTO
    CANCELAR_PROCESSAMENTO = False
    
    try:
        nome_base, ext = os.path.splitext(arquivo)
        ext = ext.lower()

        if ext not in ['.mp3', '.wav', '.m4a', '.mp4']:
            print(f"\n❌ Formato não suportado: {ext}")
            await asyncio.sleep(1)
            return

        # Configurações de velocidade
        while True:
            try:
                velocidade = float((await aioconsole.ainput("\nInforme a velocidade de reprodução desejada (ex: 1.25, 1.5, 2.0): ")).strip())
                if not (0.5 <= velocidade <= 2.0):
                    raise ValueError
                break
            except ValueError:
                print("Valor inválido. Digite um número entre 0.5 e 2.0.")

        # Formato de saída
        while True:
            formato = (await aioconsole.ainput("\nEscolha o formato de saída [mp3 para áudio | mp4 para vídeo]: ")).strip().lower()
            if formato in ["mp3", "mp4"]:
                break
            else:
                print("Formato inválido. Digite 'mp3' ou 'mp4'.")

        # Normaliza nome de saída
        nome_saida_base = f"{nome_base}_x{velocidade}".replace(".", "_")
        nome_saida_base = re.sub(r'_+', '_', nome_saida_base)  # Remove underlines duplos

        # Cria diretório de saída, se necessário
        Path(os.path.dirname(nome_saida_base)).mkdir(parents=True, exist_ok=True)

        temp_audio = f"{nome_saida_base}_temp_audio.mp3"

        print(f"\n[+] Processando: {arquivo}")
        print(f"    Aumentando velocidade ({velocidade}x)...")

        acelerar_audio(arquivo, temp_audio, velocidade)
        duracao = obter_duracao_ffprobe(temp_audio)
        print(f"    Duração após aceleração: {duracao / 3600:.2f} horas")

        extensao_final = ".mp4" if formato == "mp4" else ".mp3"

        if duracao <= LIMITE_SEGUNDOS:
            saida_final = f"{nome_saida_base}{extensao_final}"
            if formato == "mp4":
                print("    Gerando vídeo com tela preta...")
                criar_video_com_audio(temp_audio, saida_final, duracao)
                os.remove(temp_audio)
            else:
                os.rename(temp_audio, saida_final)
            print(f"    Arquivo final salvo: {saida_final}")
        else:
            print("    Dividindo em partes de até 12 horas...")
            if formato == "mp4":
                video_completo = f"{nome_saida_base}_video.mp4"
                criar_video_com_audio(temp_audio, video_completo, duracao)
                dividir_em_partes(video_completo, duracao, LIMITE_SEGUNDOS, nome_saida_base, ".mp4")
                os.remove(video_completo)
            else:
                dividir_em_partes(temp_audio, duracao, LIMITE_SEGUNDOS, nome_saida_base, ".mp3")
            os.remove(temp_audio)
            print("    Arquivos divididos com sucesso.")

        await aioconsole.ainput("\nPressione ENTER para continuar...")

    except Exception as e:
        print(f"\n❌ Erro ao processar arquivo: {str(e)}")
        await aioconsole.ainput("\nPressione ENTER para continuar...")
    finally:
        CANCELAR_PROCESSAMENTO = True


def extrair_texto_de_epub(caminho_arquivo: str) -> str:
    """
    Extrai o conteúdo textual de um arquivo EPUB, converte para texto plano,
    aplica formatação e retorna o caminho do arquivo TXT final.
    """
    try:
        print(f"\n📖 Extraindo conteúdo de: {caminho_arquivo}")
        texto_extraido = ""
        with zipfile.ZipFile(caminho_arquivo, 'r') as epub:
            arquivos_html = [
                f for f in epub.namelist()
                if f.endswith(('.html', '.xhtml')) and not re.search(r'(toc|nav|cover)', f, re.IGNORECASE)
            ]
            arquivos_html.sort()

            for nome_arquivo in arquivos_html:
                with epub.open(nome_arquivo) as f:
                    html_bytes = f.read()
                    encoding_detectado = chardet.detect(html_bytes)['encoding'] or 'utf-8'
                    try:
                        html_texto = html_bytes.decode(encoding_detectado, errors='ignore')
                    except Exception as e:
                        print(f"❌ Erro ao decodificar {nome_arquivo}: {e}")
                        continue

                    soup = BeautifulSoup(html_texto, 'html.parser')
                    for tag in soup(['nav', 'header', 'footer', 'style', 'script']):
                        tag.decompose()

                    corpo = soup.get_text(separator=' ', strip=True)
                    if corpo:
                        texto_convertido = html2text.html2text(corpo)
                        texto_extraido += texto_convertido + "\n\n"

        if not texto_extraido.strip():
            print("⚠️ Nenhum conteúdo textual extraído do EPUB.")
            return ""

        nome_base = os.path.splitext(caminho_arquivo)[0]
        caminho_txt_extraido = nome_base + "_extraido.txt"
        with open(caminho_txt_extraido, 'w', encoding='utf-8') as f:
            f.write(texto_extraido)

        caminho_corrigido = verificar_e_corrigir_arquivo(caminho_txt_extraido)
        texto_formatado = aplicar_formatacao(ler_arquivo_texto(caminho_corrigido))
        caminho_formatado = nome_base + "_formatado.txt"
        with open(caminho_formatado, 'w', encoding='utf-8') as f:
            f.write(texto_formatado)

        return caminho_formatado  # retorno do extrair_texto_de_epub
    except Exception as e:
        print(f"❌ Erro ao extrair texto do EPUB: {e}")
        return ""

# ================== FUNÇÕES DE LEITURA E PROCESSAMENTO DE ARQUIVOS ==================

def detectar_encoding(caminho_arquivo: str) -> str:
    """Detecta o encoding de um arquivo de texto."""
    try:
        with open(caminho_arquivo, 'rb') as f:
            resultado = chardet.detect(f.read())
        encoding_detectado = resultado['encoding']
        if not encoding_detectado:
            for enc in ENCODINGS_TENTATIVAS:
                try:
                    with open(caminho_arquivo, 'r', encoding=enc) as f:
                        f.read(100)
                    return enc
                except UnicodeDecodeError:
                    continue
            return 'utf-8'
        return encoding_detectado
    except Exception as e:
        print(f"\n⚠️ Erro ao detectar encoding: {str(e)}")
        return 'utf-8'

def ler_arquivo_texto(caminho_arquivo: str) -> str:
    """Lê o conteúdo de um arquivo de texto com detecção automática de encoding."""
    encoding = detectar_encoding(caminho_arquivo)
    try:
        with open(caminho_arquivo, 'r', encoding=encoding) as f:
            conteudo = f.read()
        return conteudo
    except Exception as e:
        print(f"\n❌ Erro ao ler arquivo: {str(e)}")
        return ""

def processar_texto(texto: str) -> str:
    """Processa o texto para melhorar a qualidade da conversão TTS."""
    # Remover caracteres não imprimíveis
    texto = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', texto)
    texto = texto.encode('utf-8', 'ignore').decode('utf-8')

    texto = re.sub(r'\s+', ' ', texto)
    abreviacoes = {
    r'\bDr\.(?=\s)': 'Doutor',
    r'\bD\.(?=\s)': 'Dona',
    r'\bDra\.(?=\s)': 'Doutora',
    r'\bSr\.(?=\s)': 'Senhor',
    r'\bSra\.(?=\s)': 'Senhora',
    r'\bSrta\.(?=\s)': 'Senhorita',
    r'\bProf\.(?=\s)': 'Professor',
    r'\bProfa\.(?=\s)': 'Professora',
    r'\bEng\.(?=\s)': 'Engenheiro',
    r'\bEngª\.(?=\s)': 'Engenheira',
    r'\bAdm\.(?=\s)': 'Administrador',
    r'\bAdv\.(?=\s)': 'Advogado',
    r'\bExmo\.(?=\s)': 'Excelentíssimo',
    r'\bExma\.(?=\s)': 'Excelentíssima',
    r'\bV\.Exa\.(?=\s)': 'Vossa Excelência',
    r'\bV\.Sa\.(?=\s)': 'Vossa Senhoria',
    r'\bAv\.(?=\s)': 'Avenida',
    r'\bR\.(?=\s)': 'Rua',
    r'\bKm\.(?=\s)': 'Quilômetro',
    r'\betc\.(?=\s)': 'etcétera',
    r'\bRef\.(?=\s)': 'Referência',
    r'\bPag\.(?=\s)': 'Página',
    r'\bPág\.(?=\s)': 'Página',
    r'\bPágs\.(?=\s)': 'Páginas',
    r'\bPags\.(?=\s)': 'Páginas',
    r'\bFl\.(?=\s)': 'Folha',
    r'\bPe\.(?=\s)': 'Padre',
    r'\bFls\.(?=\s)': 'Folhas',
    r'\bDept\.(?=\s)': 'Departamento',
    r'\bDepto\.(?=\s)': 'Departamento',
    r'\bUniv\.(?=\s)': 'Universidade',
    r'\bInst\.(?=\s)': 'Instituição',
    r'\bEst\.(?=\s)': 'Estado',
    r'\bTel\.(?=\s)': 'Telefone',
    r'\bCEP\.(?=\s)': 'Código de Endereçamento Postal',
    r'\bCNPJ\.(?=\s)': 'Cadastro Nacional da Pessoa Jurídica',
    r'\bCPF\.(?=\s)': 'Cadastro de Pessoas Físicas',
    r'\bEUA\.(?=\s)': 'Estados Unidos da América',
    r'\bEd\.(?=\s)': 'Edição',
    r'\bLtda\.(?=\s)': 'Limitada'
}

    for abrev, expansao in abreviacoes.items():
        texto = re.sub(abrev, expansao, texto)

    def converter_numero(match):
        num = match.group(0)
        try:
            return num2words(int(num), lang='pt_BR')
        except:
            return num

    def converter_valor_monetario(match):
        valor = match.group(1)
        try:
            return f"{num2words(int(valor), lang='pt_BR')} reais"
        except:
            return f"{valor} reais"

    texto = re.sub(r'\b\d+\b', converter_numero, texto)
    texto = re.sub(r'R\$\s*(\d+)', converter_valor_monetario, texto)
    texto = re.sub(r'\b(\d+)\s*-\s*(\d+)\b', lambda m: f"{num2words(int(m.group(1)), lang='pt_BR')} a {num2words(int(m.group(2)), lang='pt_BR')}", texto)

    return texto

def dividir_texto(texto: str) -> list:
    """
    Divide o texto em partes menores para processamento, respeitando os pontos finais.
    """
    partes = []
    start = 0
    while start < len(texto):
        next_period = texto.find('.', start)
        if next_period == -1:
            partes.append(texto[start:].strip())
            break
        end = next_period + 1
        partes.append(texto[start:end].strip())
        start = end
    return [p for p in partes if p]

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
        arquivos = listar_arquivos(dir_atual, ['.txt', '.pdf', '.epub'])
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
                await asyncio.sleep(1)
        elif escolha == 'M':
            caminho = (await aioconsole.ainput("\nDigite o caminho completo do arquivo: ")).strip()
            if not os.path.exists(caminho):
                print(f"\n❌ Arquivo não encontrado: {caminho}")
                await asyncio.sleep(1)
                continue
            ext = os.path.splitext(caminho)[1].lower()
            if ext == '.pdf':
                caminho_txt = os.path.splitext(caminho)[0] + '.txt'
                if not converter_pdf(caminho, caminho_txt):
                    print("\n⚠️ Falha na conversão do PDF. Tente outro arquivo.")
                    await asyncio.sleep(1)
                    continue
                # Após converter, verifica se o TXT já foi corrigido
                try:
                    with open(caminho_txt, 'r', encoding='utf-8') as f:
                        texto_original = f.read()
                    texto_formatado = aplicar_formatacao(texto_original)
                    caminho_txt = os.path.splitext(caminho_txt)[0] + '_formatado.txt'
                    with open(caminho_txt, 'w', encoding='utf-8') as f:
                        f.write(texto_formatado)
                    print(f'✅ Formatação aplicada e salva em: {caminho_txt}')
                except Exception as e:
                    print(f'❌ Erro ao aplicar formatação: {e}')
                caminho_txt = verificar_e_corrigir_arquivo(caminho_txt)
                editar = (await aioconsole.ainput("\nDeseja editar o arquivo TXT gerado? (s/n): ")).strip().lower()
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
                # Se o arquivo TXT não contém o sufixo _formatado, corrige-o automaticamente
                if not os.path.basename(caminho).lower().endswith("_formatado.txt"):
                    caminho = verificar_e_corrigir_arquivo(caminho)
                    try:
                        with open(caminho, 'r', encoding='utf-8') as f:
                            texto_original = f.read()
                        texto_formatado = aplicar_formatacao(texto_original)
                        caminho_formatado = os.path.splitext(caminho)[0] + '_formatado.txt'
                        with open(caminho_formatado, 'w', encoding='utf-8') as f:
                            f.write(texto_formatado)
                        print(f'✅ Formatação aplicada ao TXT e salva em: {caminho_formatado}')
                        caminho = caminho_formatado
                    except Exception as e:
                        print(f'❌ Erro ao aplicar formatação ao TXT: {e}')
                return caminho
            else:
                print(f"\n❌ Formato não suportado: {ext}")
                print("💡 Apenas arquivos .txt, .pdf e .epub são suportados")
                await asyncio.sleep(1)
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
                        await asyncio.sleep(1)
                        continue
                    # Corrige o TXT gerado, se necessário
                    caminho_txt = verificar_e_corrigir_arquivo(caminho_txt)
                    editar = (await aioconsole.ainput("\nDeseja editar o arquivo TXT gerado? (s/n): ")).strip().lower()
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
                elif ext == '.epub':
                    caminho_formatado = extrair_texto_de_epub(caminho_completo)
                    try:
                        texto_extraido = ""
                        with zipfile.ZipFile(caminho_completo, 'r') as epub:
                            for nome_arquivo in epub.namelist():
                                if nome_arquivo.endswith('.html') or nome_arquivo.endswith('.xhtml'):
                                    with epub.open(nome_arquivo) as f:
                                        html_bytes = f.read()
                                        try:
                                            html_texto = html_bytes.decode('utf-8')
                                        except UnicodeDecodeError:
                                            html_texto = html_bytes.decode('latin-1')
                                        texto_extraido += html2text.html2text(html_texto) + "\n"
                        nome_base = os.path.splitext(caminho_completo)[0]
                        caminho_txt = nome_base + "_extraido.txt"
                        with open(caminho_txt, 'w', encoding='utf-8') as f:
                            f.write(texto_extraido)

                        caminho_corrigido = verificar_e_corrigir_arquivo(caminho_txt)
                        texto_formatado = aplicar_formatacao(ler_arquivo_texto(caminho_corrigido))
                        caminho_formatado = nome_base + "_formatado.txt"
                        with open(caminho_formatado, 'w', encoding='utf-8') as f:
                            f.write(texto_formatado)

                        editar = (await aioconsole.ainput("\nDeseja editar o arquivo TXT gerado? (s/n): ")).strip().lower()
                        if editar == "s":
                            if sistema["android"]:
                                print("\nO arquivo TXT corrigido foi salvo no diretório padrão (normalmente Download).")
                                print("Após editá-lo, reinicie a conversão selecionando-o novamente.")
                                await aioconsole.ainput("\nPressione ENTER para continuar...")
                                return ""
                            else:
                                if sistema["windows"]:
                                    os.startfile(caminho_formatado)
                                if sistema['windows']:
                                    os.startfile(caminho_formatado)
                                elif sistema['macos']:
                                    subprocess.Popen(["open", caminho_formatado])
                                else:
                                    subprocess.Popen(["xdg-open", caminho_formatado])
                                await aioconsole.ainput("\nPressione ENTER para continuar...")
                                print("Edite o arquivo, salve e pressione ENTER para continuar...")
                        return caminho_formatado  # retorno do extrair_texto_de_epub
                    except Exception as e:
                        print(f"❌ Erro ao processar EPUB (zip/html): {e}")
                        await asyncio.sleep(2)
                        return ''
                    except Exception as e:
                        print(f"\n❌ Erro ao processar EPUB: {str(e)}")
                        await asyncio.sleep(2)
                        return ''

                else:
                    return caminho_completo
            else:
                print("\n❌ Opção inválida")
                await asyncio.sleep(1)
        else:
            print("\n❌ Opção inválida")
            await asyncio.sleep(1)

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
        await asyncio.sleep(1)

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
            await menu_converter_mp3_para_mp4()
        elif opcao == '7':
            print("\n👋 Obrigado por usar o Conversor TTS Completo!")
            sys.exit(0)

asyncio.run(main())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Programa interrompido pelo usuário.")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {str(e)}")


# === Funções para EPUB adicionadas ===
from bs4 import BeautifulSoup

def convert_epub_to_txt(epub_path, output_path=None):
    """
    Converte um arquivo ePub para TXT
    """
    try:
        # Verifica se o arquivo existe
        if not os.path.exists(epub_path):
            print(f"Erro: Arquivo '{epub_path}' não encontrado.")
            return False
        
        # Define o nome do arquivo de saída
        if output_path is None:
            output_path = os.path.splitext(epub_path)[0] + ".txt"
        
        # Extrai o conteúdo do ePub (que é um arquivo zip)
        with zipfile.ZipFile(epub_path, 'r') as epub:
            # Encontra todos os arquivos HTML/XHTML no ePub
            html_files = [f for f in epub.namelist() 
                         if f.lower().endswith(('.html', '.xhtml', '.htm'))]
            
            # Ordena os arquivos para manter a ordem dos capítulos
            html_files.sort()
            
            # Processa cada arquivo HTML
            full_text = ""
            for html_file in html_files:
                with epub.open(html_file) as f:
                    html_content = f.read().decode('utf-8')
                    
                    # Usa BeautifulSoup para limpar o HTML
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Remove scripts e estilos
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Converte HTML para texto usando html2text
                    h = html2text.HTML2Text()
                    h.ignore_links = True
                    h.ignore_images = True
                    h.ignore_emphasis = True
                    text = h.handle(str(soup))
                    
                    full_text += text + "\n\n"
        
        # Salva o texto em um arquivo
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
            
        print(f"Conversão concluída! Arquivo salvo em: {output_path}")
        return True
        
    except Exception as e:
        print(f"Erro durante a conversão: {str(e)}")
        return False
    
    epub_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_epub_to_txt(epub_path, output_path)

if __name__ == "__main__":
    asyncio.run(menu_principal())
