#!/usr/-bin/env python3
# -*- coding: utf-8 -*-

"""
Script completo para conversão de Texto-para-Fala (TTS) e manipulação de áudio/vídeo.

Funcionalidades:
- Extrai texto de .txt, .pdf, .epub.
- Formata texto complexo (capítulos, números, abreviações) para TTS.
- Converte texto para MP3 usando:
    - Edge TTS (edge-tts)
    - Gemini TTS (gemini-2.5-flash-preview-tts) - REQUER API KEY
- Permite acelerar áudio/vídeo.
- Converte áudio (MP3) para vídeo (MP4 com tela preta).
- Divide arquivos de mídia longos.
- Instala dependências Python necessárias automaticamente.
- Tenta instalar Poppler (para PDF) no Windows/Termux.
- Interface de console assínclrônica com opção de inserir e SALVAR API Key.

*** MODIFICAÇÃO (Gemini-User): ***
- Lógica de retry alterada para 'while True' (loop infinito)
- Limite MAX_TTS_TENTATIVAS removido
- Backoff exponencial mantido para evitar sobrecarga da API
"""

import os
import sys
import subprocess
import asyncio
import re
import signal
from pathlib import Path
import platform
import zipfile
import shutil
import time
import unicodedata
from math import ceil
import importlib # Usado para importação dinâmica
import base64 # Necessário para o Gemini
import json # Necessário para salvar a API Key
import random # Necessário para o backoff exponencial de fallback

# ================== IMPORTAÇÃO E INSTALAÇÃO DE DEPENDÊNCIAS ==================

def _importar_ou_instalar(package_name, import_name, attribute_name=None):
    """
    Tenta importar um módulo. Se falhar, tenta instalá-lo via pip
    e depois importá-lo novamente.
    Retorna o módulo ou atributo importado, ou None em caso de falha.
    """
    try:
        module = importlib.import_module(import_name)
        if attribute_name:
            return getattr(module, attribute_name)
        return module
    except (ModuleNotFoundError, ImportError):
        print(f"⚠️ Módulo '{package_name}' não encontrado. Instalando...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", package_name])
            import site
            user_site_packages = site.getusersitepackages()
            if user_site_packages not in sys.path:
                sys.path.append(user_site_packages)
            module = importlib.import_module(import_name)
            if attribute_name:
                return getattr(module, attribute_name)
            return module
        except Exception as e:
            print(f"❌ Falha ao instalar/importar '{package_name}': {e}")
            print(f"   Por favor, instale manually: pip install {package_name}")
            return None

# Importar dependências essenciais
edge_tts = _importar_ou_instalar("edge-tts>=6.1.5", "edge_tts")
BeautifulSoup = _importar_ou_instalar("beautifulsoup4", "bs4", "BeautifulSoup")
html2text = _importar_ou_instalar("html2text", "html2text")
tqdm = _importar_ou_instalar("tqdm", "tqdm", "tqdm")
requests = _importar_ou_instalar("requests", "requests")
aioconsole = _importar_ou_instalar("aioconsole>=0.6.0", "aioconsole")
chardet = _importar_ou_instalar("chardet>=5.0.0", "chardet")
num2words = _importar_ou_instalar("num2words>=0.5.12", "num2words", "num2words")
aiohttp = _importar_ou_instalar("aiohttp", "aiohttp")

if not all([edge_tts, BeautifulSoup, html2text, tqdm, requests, aioconsole, chardet, num2words, aiohttp]):
    print("❌ Dependências essenciais não puderam ser instaladas. Saindo.")
    sys.exit(1)

# ================== CONFIGURAÇÕES GLOBAIS ==================

# --- Lógica de Carregamento da API Key ---
CONFIG_FILE_PATH = Path.home() / ".conversor_tts_config.json"

def load_api_key_from_config():
    """Tenta carregar a API Key do arquivo .json na home do usuário."""
    if not CONFIG_FILE_PATH.exists():
        return None
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get("GEMINI_API_KEY")
    except Exception as e:
        print(f"⚠️ Erro ao ler arquivo de configuração de API Key: {e}")
        return None

def save_api_key_to_config(api_key: str):
    """Salva a API Key no arquivo .json na home do usuário."""
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump({"GEMINI_API_KEY": api_key}, f, indent=2)
        print(f"✅ API Key salva com segurança em: {CONFIG_FILE_PATH}")
    except Exception as e:
        print(f"❌ Erro ao salvar API Key: {e}")

# Tenta carregar do arquivo, senão, tenta do ambiente
GEMINI_API_KEY_ATUAL = load_api_key_from_config() or os.environ.get("GEMINI_API_KEY")

VOZES_PT_BR = [
    "pt-BR-ThalitaMultilingualNeural",
    "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural",
    "pt-BR-BrendaNeural",
    "pt-BR-DonatoNeural",
    "pt-BR-GiovannaNeural",
    "pt-BR-HumbertoNeural",
    "pt-BR-JulioNeural",
    "pt-BR-LeilaNeural",
    "pt-BR-NicolauNeural",
    "pt-BR-ValerioNeural",
    "pt-BR-YaraNeural",
]

VOZES_GEMINI_PT_BR = {
    "Kore (Firme)": "Kore",
    "Puck (Animada)": "Puck",
    "Charon (Informativa)": "Charon",
    "Zephyr (Brilhante)": "Zephyr",
    "Leda (Jovial)": "Leda",
    "Orus (Firme)": "Orus",
    "Aoede (Arejada)": "Aoede",
    "Callirrhoe (Descontraída)": "Callirrhoe",
    "Autonoe (Brilhante)": "Autonoe",
    "Iapetus (Clara)": "Iapetus",
    "Umbriel (Descontraída)": "Umbriel",
    "Algenib (Grave)": "Algenib",
}

ENCODINGS_TENTATIVAS = ['utf-8', 'utf-16', 'iso-8859-1', 'cp1252']
# --- MODIFICAÇÃO (Gemini-User): Limite de tentativas removido ---
# MAX_TTS_TENTATIVAS = 5
CANCELAR_PROCESSAMENTO = False
FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"
LIMITE_SEGUNDOS_DIVISAO = 43200

RESOLUCOES_VIDEO = {
    '1': ('640x360', '360p'),
    '2': ('854x480', '480p'),
    '3': ('1280x720', '720p (HD)')
}
SISTEMA_OPERACIONAL_INFO = {}

# --- LIMITES DE CHUNK E CONCORRÊNCIA (ATUALIZADOS) ---
LIMITE_CARACTERES_CHUNK_TTS_EDGE = 10000
LIMITE_CARACTERES_CHUNK_TTS_GEMINI = 1000

LOTE_MAXIMO_TAREFAS_EDGE = 10
# ==================================================================
# ATUALIZAÇÃO: Reduzido de 100 para 10 para evitar erros 429
LOTE_MAXIMO_TAREFAS_GEMINI = 10
# ==================================================================
# --- FIM DAS ATUALIZAÇÕES ---

# ================== FUNÇÕES DE TEXTO (Inalteradas) ==================

ABREVIACOES_MAP = {
    'dr': 'Doutor', 'd': 'Dona', 'dra': 'Doutora',
    'sr': 'Senhor', 'sra': 'Senhora', 'srta': 'Senhorita',
    'prof': 'Professor', 'profa': 'Professora',
    'eng': 'Engenheiro', 'engª': 'Engenheira',
    'adm': 'Administrador', 'adv': 'Advogado',
    'exmo': 'Excelentíssimo', 'exma': 'Excelentíssima',
    'v.exa': 'Vossa Excelência', 'v.sa': 'Vossa Senhoria',
    'av': 'Avenida', 'r': 'Rua', 'km': 'Quilômetro',
    'etc': 'etcétera', 'ref': 'Referência',
    'pag': 'Página', 'pags': 'Páginas',
    'fl': 'Folha', 'fls': 'Folhas',
    'pe': 'Padre',
    'dept': 'Departamento', 'depto': 'Departamento',
    'univ': 'Universidade', 'inst': 'Instituição',
    'est': 'Estado', 'tel': 'Telefone',
    'eua': 'Estados Unidos da América',
    'ed': 'Edição', 'ltda': 'Limitada'
}
ABREVIACOES_MAP_LOWER = {k.lower(): v for k, v in ABREVIACOES_MAP.items()}

CASOS_ESPECIAIS_RE = {
     r'\bV\.Exa\.(?=\s)': 'Vossa Excelência',
     r'\bV\.Sa\.(?=\s)': 'Vossa Senhoria',
     r'\bEngª\.(?=\s)': 'Engenheira'
}

CONVERSAO_CAPITULOS_EXTENSO_PARA_NUM = {
    'UM': '1', 'DOIS': '2', 'TRÊS': '3', 'QUATRO': '4', 'CINCO': '5',
    'SEIS': '6', 'SETE': '7', 'OITO': '8', 'NOVE': '9', 'DEZ': '10',
    'ONZE': '11', 'DOZE': '12', 'TREZE': '13', 'CATORZE': '14', 'QUINZE': '15',
    'DEZESSEIS': '16', 'DEZESSETE': '17', 'DEZOITO': '18', 'DEZENOVE': '19', 'VINTE': '20'
}

ABREVIACOES_QUE_NAO_TERMINAM_FRASE = set([
    'sr.', 'sra.', 'srta.', 'dr.', 'dra.', 'prof.', 'profa.', 'eng.', 'exmo.', 'exma.',
    'pe.', 'rev.', 'ilmo.', 'ilma.', 'gen.', 'cel.', 'maj.', 'cap.', 'ten.', 'sgt.',
    'cb.', 'sd.', 'me.', 'ms.', 'msc.', 'esp.', 'av.', 'r.', 'pç.', 'esq.', 'trav.',
    'jd.', 'pq.', 'rod.', 'km.', 'apt.', 'ap.', 'bl.', 'cj.', 'cs.', 'ed.', 'nº',
    'no.', 'uf.', 'cep.', 'est.', 'mun.', 'dist.', 'zon.', 'reg.', 'kg.', 'cm.',
    'mm.', 'lt.', 'ml.', 'mg.', 'seg.', 'min.', 'hr.', 'ltda.', 's.a.', 's/a',
    'cnpj.', 'cpf.', 'rg.', 'proc.', 'ref.', 'cod.', 'tel.', 'etc.', 'p.ex.', 'ex.',
    'i.e.', 'e.g.', 'vs.', 'cf.', 'op.cit.', 'loc.cit.', 'fl.', 'fls.', 'pag.',
    'p.', 'pp.', 'u.s.', 'e.u.a.', 'o.n.u.', 'i.b.m.', 'h.p.', 'obs.', 'att.',
    'resp.', 'publ.', 'ed.',
    'doutora', 'senhora', 'senhor', 'doutor', 'professor', 'professora', 'general'
])
SIGLA_COM_PONTOS_RE = re.compile(r'\b([A-Z]\.\s*)+$')


def _formatar_numeracao_capitulos(texto):
    """Localiza e padroniza títulos de capítulo."""
    def substituir_cap(match):
        tipo_cap = match.group(1).upper()
        numero_rom_arab = match.group(2)
        numero_extenso = match.group(3)
        titulo_opcional = match.group(4).strip() if match.group(4) else ""

        numero_final = ""
        if numero_rom_arab:
            numero_final = numero_rom_arab.upper()
        elif numero_extenso:
            num_ext_upper = numero_extenso.strip().upper()
            numero_final = CONVERSAO_CAPITULOS_EXTENSO_PARA_NUM.get(num_ext_upper, num_ext_upper)

        cabecalho = f"{tipo_cap} {numero_final}."
        
        if titulo_opcional:
            palavras_titulo = []
            for p in titulo_opcional.split():
                if p.isupper() and len(p) > 1:
                    palavras_titulo.append(p)
                else:
                    palavras_titulo.append(p.capitalize())
            titulo_formatado = " ".join(palavras_titulo)
            return f"\n\n{cabecalho}\n\n{titulo_formatado}"
        
        return f"\n\n{cabecalho}\n\n"

    padrao = re.compile(
        r'(?i)(cap[íi]tulo|cap\.?)\s+'
        r'(?:(\d+|[IVXLCDM]+)|([A-ZÇÉÊÓÃÕa-zçéêóãõ]+))'
        r'\s*[:\-.]?\s*'
        r'(?=\S)([^\n]*)?',
        re.IGNORECASE
    )
    texto = padrao.sub(substituir_cap, texto)

    def substituir_extenso_com_titulo(match):
        num_ext = match.group(1).strip().upper()
        titulo = match.group(2).strip().title()
        numero = CONVERSAO_CAPITULOS_EXTENSO_PARA_NUM.get(num_ext, num_ext)
        return f"CAPÍTULO {numero}: {titulo}"

    padrao_extenso_titulo = re.compile(r'CAP[IÍ]TULO\s+([A-ZÇÉÊÓÃÕ]+)\s*[:\-]\s*(.+)', re.IGNORECASE)
    texto = padrao_extenso_titulo.sub(substituir_extenso_com_titulo, texto)
    return texto

def _remover_numeros_pagina_isolados(texto):
    """Remove linhas que contêm apenas números."""
    linhas = texto.splitlines()
    novas_linhas = []
    for linha in linhas:
        if re.match(r'^\s*\d+\s*$', linha):
            continue
        linha = re.sub(r'\s{3,}\d+\s*$', '', linha)
        novas_linhas.append(linha)
    return '\n'.join(novas_linhas)

def _normalizar_caixa_alta_linhas(texto):
    """Converte linhas em CAIXA ALTA para "Title Case", preservando siglas."""
    linhas = texto.splitlines()
    texto_final = []
    for linha in linhas:
        if re.match(r'^\s*CAP[ÍI]TULO\s+[\w\d]+\.?\s*$', linha, re.IGNORECASE):
            texto_final.append(linha)
            continue
            
        if (linha.isupper() and 
            len(linha.strip()) > 3 and
            any(c.isalpha() for c in linha)):
            
            palavras = []
            for p in linha.split():
                if len(p) > 1 and p.isupper() and p.isalpha() and p not in ['I', 'A', 'E', 'O', 'U']:
                    if not (sum(1 for char in p if char in "AEIOU") > 0 and \
                            sum(1 for char in p if char not in "AEIOU") > 0 and len(p) <= 4) :
                        palavras.append(p)
                        continue
                palavras.append(p.capitalize())
            texto_final.append(" ".join(palavras))
        else:
            texto_final.append(linha)
    return "\n".join(texto_final)

def _corrigir_hifenizacao_quebras(texto):
    """Junta palavras quebradas por hífen no final da linha."""
    return re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', texto)

def _remover_metadados_pdf(texto):
    """Remove linhas que parecem ser metadados de impressão/design."""
    texto = re.sub(
        r'^\s*[\w\d_-]+\.(indd|pdf)\s+\d+\s+\d{2}/\d{2}/\d{2,4}\s+\d{1,2}:\d{2}(:\d{2})?\s*([AP]M)?\s*$',
        '', texto, flags=re.MULTILINE | re.IGNORECASE
    )
    return texto

def _expandir_abreviacoes_numeros(texto: str) -> str:
    """Expande abreviações (Dr., Sr.) e converte números (10, R$10) para extenso."""
    for abrev_re, expansao in CASOS_ESPECIAIS_RE.items():
         texto = re.sub(abrev_re, expansao, texto, flags=re.IGNORECASE)

    def replace_abrev_com_ponto(match):
        abrev_encontrada = match.group(1)
        expansao = ABREVIACOES_MAP_LOWER.get(abrev_encontrada.lower())
        return expansao if expansao else match.group(0)

    chaves_simples = [re.escape(k) for k in ABREVIACOES_MAP_LOWER.keys() if '.' not in k and 'ª' not in k]
    if chaves_simples:
        padrao_abrev_simples = r'\b(' + '|'.join(chaves_simples) + r')\.'
        texto = re.sub(padrao_abrev_simples, replace_abrev_com_ponto, texto, flags=re.IGNORECASE)

    def _converter_numero_match(match):
        num_str = match.group(0)
        try:
            if re.match(r'^\d{4}$', num_str) and (1900 <= int(num_str) <= 2100):
                return num_str
            if len(num_str) > 7 : return num_str
            return num2words(int(num_str), lang='pt_BR')
        except Exception: return num_str
    texto = re.sub(r'\b\d+\b', _converter_numero_match, texto)

    def _converter_valor_monetario_match(match):
        valor_inteiro = match.group(1).replace('.', '')
        try: return f"{num2words(int(valor_inteiro), lang='pt_BR')} reais"
        except Exception: return match.group(0)
    texto = re.sub(r'R\$\s*(\d{1,3}(?:\.\d{3})*),(\d{2})', _converter_valor_monetario_match, texto)
    texto = re.sub(r'R\$\s*(\d+)(?:,00)?', lambda m: f"{num2words(int(m.group(1)), lang='pt_BR')} reais" if m.group(1) else m.group(0) , texto)
    
    texto = re.sub(r'\b(\d+)\s*-\s*(\d+)\b', lambda m: f"{num2words(int(m.group(1)), lang='pt_BR')} a {num2words(int(m.group(2)), lang='pt_BR')}", texto)
    
    return texto

def _converter_ordinais_para_extenso(texto: str) -> str:
    """Converte números ordinais como 1º, 2a, 3ª para extenso."""
    def substituir_ordinal(match):
        numero = match.group(1)
        terminacao = match.group(2).lower()
        try:
            num_int = int(numero)
            ordinal_masc = num2words(num_int, lang='pt_BR', to='ordinal')
            
            if terminacao in ('a', 'ª'):
                if ordinal_masc.endswith('o'):
                    return ordinal_masc[:-1] + 'a'
            return ordinal_masc
        except ValueError:
            return match.group(0)

    padrao_ordinal = re.compile(r'\b(\d+)\s*([oaºª])(?!\w)', re.IGNORECASE)
    texto = padrao_ordinal.sub(substituir_ordinal, texto)
    return texto

def formatar_texto_para_tts(texto_bruto: str) -> str:
    """Orquestra todas as etapas de limpeza e formatação do texto."""
    print("⚙️ Aplicando formatações avançadas ao texto...")
    texto = texto_bruto

    texto = unicodedata.normalize('NFKC', texto)
    texto = texto.replace('\f', '\n\n')
    texto = re.sub(r'[\*_#@\[\](){}\\]', ' ', texto)

    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = "\n".join([linha.strip() for linha in texto.splitlines() if linha.strip()])

    paragrafos_originais = texto.split('\n\n')
    paragrafos_processados = []
    for paragrafo_bruto in paragrafos_originais:
        paragrafo_bruto = paragrafo_bruto.strip()
        if not paragrafo_bruto: continue
        
        linhas_do_paragrafo = paragrafo_bruto.split('\n')
        buffer_linha_atual = ""
        
        for i, linha in enumerate(linhas_do_paragrafo):
            linha_strip = linha.strip()
            if not linha_strip: continue
            
            juntar_com_anterior = False
            if buffer_linha_atual:
                ultima_palavra_buffer = buffer_linha_atual.split()[-1].lower() if buffer_linha_atual else ""
                termina_abreviacao = ultima_palavra_buffer in ABREVIACOES_QUE_NAO_TERMINAM_FRASE
                termina_sigla_ponto = re.search(r'\b[A-Z]\.$', buffer_linha_atual) is not None
                termina_pontuacao_forte = re.search(r'[.!?…]$', buffer_linha_atual)
                
                nao_juntar = False
                if termina_pontuacao_forte and not termina_abreviacao and not termina_sigla_ponto:
                     if linha_strip and linha_strip[0].isupper(): nao_juntar = True
                
                if termina_abreviacao or termina_sigla_ponto: juntar_com_anterior = True
                elif not nao_juntar and not termina_pontuacao_forte: juntar_com_anterior = True
                elif buffer_linha_atual.lower() in ['doutora', 'senhora', 'senhor', 'doutor']: juntar_com_anterior = True

            if juntar_com_anterior:
                buffer_linha_atual += " " + linha_strip
            else:
                if buffer_linha_atual: paragrafos_processados.append(buffer_linha_atual)
                buffer_linha_atual = linha_strip
        
        if buffer_linha_atual: paragrafos_processados.append(buffer_linha_atual)

    texto = '\n\n'.join(paragrafos_processados)
    
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto)

    texto = _remover_metadados_pdf(texto)
    texto = _remover_numeros_pagina_isolados(texto)
    texto = _corrigir_hifenizacao_quebras(texto)
    texto = _formatar_numeracao_capitulos(texto)

    segmentos = re.split(r'([.!?…])\s*', texto)
    texto_reconstruido = ""; buffer_segmento = ""
    
    for i in range(0, len(segmentos), 2):
        parte_texto = segmentos[i]; pontuacao = segmentos[i+1] if i + 1 < len(segmentos) else ""
        segmento_completo = (parte_texto + pontuacao).strip()
        if not segmento_completo: continue
        
        ultima_palavra = segmento_completo.split()[-1].lower() if segmento_completo else ""
        ultima_palavra_sem_ponto = ultima_palavra.rstrip('.!?…') if pontuacao else ultima_palavra
        
        termina_abreviacao_conhecida = ultima_palavra in ABREVIACOES_QUE_NAO_TERMINAM_FRASE or \
                                        ultima_palavra_sem_ponto in ABREVIACOES_QUE_NAO_TERMINAM_FRASE
        termina_sigla_padrao = SIGLA_COM_PONTOS_RE.search(segmento_completo) is not None
        
        nao_quebrar = False
        if pontuacao == '.':
             if termina_abreviacao_conhecida or termina_sigla_padrao: nao_quebrar = True
        
        if buffer_segmento: buffer_segmento += " " + segmento_completo
        else: buffer_segmento = segmento_completo
        
        if not nao_quebrar:
            texto_reconstruido += buffer_segmento + "\n\n"; buffer_segmento = ""
            
    if buffer_segmento:
         texto_reconstruido += buffer_segmento
         if not re.search(r'[.!?…)]$', buffer_segmento): texto_reconstruido += "."
         texto_reconstruido += "\n\n"
         
    texto = texto_reconstruido.strip()

    texto = _normalizar_caixa_alta_linhas(texto)
    texto = _converter_ordinais_para_extenso(texto)
    texto = _expandir_abreviacoes_numeros(texto)

    formas_expandidas_tratamento = ['Senhor', 'Senhora', 'Doutor', 'Doutora', 'Professor', 'Professora', 'Excelentíssimo', 'Excelentíssima']
    for forma in formas_expandidas_tratamento:
        padrao_limpeza = r'\b' + re.escape(forma) + r'\.\s+([A-Z])'
        texto = re.sub(padrao_limpeza, rf'{forma} \1', texto)
        padrao_limpeza_sem_espaco = r'\b' + re.escape(forma) + r'\.([A-Z])'
        texto = re.sub(padrao_limpeza_sem_espaco, rf'{forma} \1', texto)

    paragrafos_finais = texto.split('\n\n')
    paragrafos_formatados_final = []
    for p in paragrafos_finais:
        p_strip = p.strip()
        if not p_strip: continue
        
        e_titulo_capitulo = re.match(r'^\s*CAP[ÍI]TULO\s+[\w\d]+\.?\s*$', p_strip.split('\n')[0].strip(), re.IGNORECASE)
        if not re.search(r'[.!?…)]$', p_strip) and not e_titulo_capitulo:
            p_strip += '.'
        paragrafos_formatados_final.append(p_strip)
        
    texto = '\n\n'.join(paragrafos_formatados_final)
    texto = re.sub(r'[ \t]+', ' ', texto).strip()
    texto = re.sub(r'\n{2,}', '\n\n', texto)

    print("✅ Formatação de texto concluída.")
    return texto.strip()

# ================== FUNÇÕES DE SISTEMA E DEPENDÊNCIAS (Inalteradas) ==================

def handler_sinal(signum, frame):
    """Manipulador para CTRL+C."""
    global CANCELAR_PROCESSAMENTO
    CANCELAR_PROCESSAMENTO = True
    print("\n\n🚫 Operação cancelada pelo usuário. Aguarde a finalização da tarefa atual...")
    signal.signal(signal.SIGINT, signal.SIG_DFL)

signal.signal(signal.SIGINT, handler_sinal)

def detectar_sistema():
    """Detecta o sistema operacional e armazena em cache."""
    global SISTEMA_OPERACIONAL_INFO
    if SISTEMA_OPERACIONAL_INFO:
        return SISTEMA_OPERACIONAL_INFO
        
    sistema = {
        'nome': platform.system().lower(), 'termux': False, 'android': False,
        'windows': False, 'linux': False, 'macos': False,
    }
    sistema['windows'] = (sistema['nome'] == 'windows')
    sistema['macos'] = (sistema['nome'] == 'darwin')
    sistema['linux'] = (sistema['nome'] == 'linux')

    if sistema['linux']:
        if 'ANDROID_ROOT' in os.environ or os.path.exists('/system/bin/app_process'):
            sistema['android'] = True
            if 'TERMUX_VERSION' in os.environ or os.path.exists('/data/data/com.termux'):
                sistema['termux'] = True
                termux_bin = '/data/data/com.termux/files/usr/bin'
                if termux_bin not in os.environ.get('PATH', ''):
                    os.environ['PATH'] = f"{os.environ.get('PATH', '')}:{termux_bin}"
                    
    SISTEMA_OPERACIONAL_INFO = sistema
    return sistema

def _verificar_comando(comando_args, mensagem_sucesso, mensagem_falha, install_commands=None):
    """Verifica se um comando externo (ex: ffmpeg) está disponível."""
    try:
        subprocess.run(comando_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"✅ {mensagem_sucesso}")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"⚠️ {mensagem_falha}")
        current_os_name = SISTEMA_OPERACIONAL_INFO.get('nome', '')
        if install_commands and current_os_name:
            cmd_list = None
            if SISTEMA_OPERACIONAL_INFO.get('termux') and 'termux' in install_commands:
                cmd_list = install_commands.get('termux')
            else:
                cmd_list = install_commands.get(current_os_name)

            if cmd_list:
                print(f"   Sugestão de instalação: {' OU '.join(cmd_list)}")
                if SISTEMA_OPERACIONAL_INFO.get('termux') and 'poppler' in mensagem_falha.lower():
                    if _instalar_dependencia_termux_auto('poppler'): return True
            else:
                print("   Comando de instalação não especificado para este SO.")
        elif not install_commands:
             print("   Comando de instalação não especificado.")
        return False

def _instalar_dependencia_termux_auto(pkg: str) -> bool:
    """Tenta instalar um pacote (ex: poppler, ffmpeg) via 'pkg' no Termux."""
    print(f"📦 Tentando instalar '{pkg}' no Termux automaticamente...")
    try:
        subprocess.run(['pkg', 'update', '-y'], check=True, capture_output=True)
        subprocess.run(['pkg', 'install', '-y', pkg], check=True, capture_output=True)
        print(f"✅ Pacote Termux '{pkg}' instalado com sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao instalar pacote Termux '{pkg}': {e.stderr.decode(errors='ignore') if e.stderr else e}")
    except Exception as e:
        print(f"❌ Erro inesperado ao instalar '{pkg}' em Termux: {e}")
    return False

def instalar_poppler_windows():
    """Tenta baixar e "instalar" o Poppler no Windows (adicionando ao PATH do usuário)."""
    if shutil.which("pdftotext.exe"):
        print("✅ Poppler (pdftotext.exe) já encontrado no PATH.")
        return True
        
    print("📦 Poppler (pdftotext.exe) não encontrado no PATH. Tentando instalação automática...")
    try:
        poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.11.0-0/Release-23.11.0-0.zip"
        install_dir_base = os.environ.get('LOCALAPPDATA', os.path.join(os.path.expanduser("~"), "AppData", "Local"))
        if not install_dir_base:
             install_dir_base = os.path.join(os.path.expanduser("~"), "Poppler")
        install_dir = os.path.join(install_dir_base, 'Poppler')
        os.makedirs(install_dir, exist_ok=True)
        
        print("📥 Baixando Poppler...")
        response = requests.get(poppler_url, stream=True, timeout=60)
        response.raise_for_status()
        zip_path = os.path.join(install_dir, "poppler.zip")
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
            
        print("📦 Extraindo arquivos...")
        archive_root_dir_name = ""
        with zipfile.ZipFile(zip_path, 'r') as zip_ref_check:
            common_paths = list(set([item.split('/')[0] for item in zip_ref_check.namelist() if '/' in item]))
            if len(common_paths) == 1: archive_root_dir_name = common_paths[0]
            
        with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(install_dir)
        os.remove(zip_path)
        
        bin_path = None
        if archive_root_dir_name:
            potential_bin_path = os.path.join(install_dir, archive_root_dir_name, 'Library', 'bin')
            if not os.path.exists(potential_bin_path):
                 potential_bin_path = os.path.join(install_dir, archive_root_dir_name, 'bin')
            if os.path.exists(potential_bin_path): bin_path = potential_bin_path
        
        if not bin_path:
            for root, dirs, files in os.walk(install_dir):
                if 'pdftotext.exe' in files and ('bin' in root.lower()):
                    bin_path = root
                    break
                    
        if not bin_path or not os.path.exists(os.path.join(bin_path, 'pdftotext.exe')):
            print(f"❌ Erro: Diretório 'bin' com 'pdftotext.exe' não encontrado em {install_dir} após extração.")
            shutil.rmtree(install_dir); return False
            
        print(f"✅ Diretório bin do Poppler encontrado: {bin_path}")
        
        try:
            import winreg
            key_path = r"Environment"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                current_path, _ = winreg.QueryValueEx(key, "PATH")
                if bin_path not in current_path:
                    new_path = f"{current_path};{bin_path}" if current_path else bin_path
                    winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
                    os.environ['PATH'] = f"{bin_path};{os.environ['PATH']}"
                    print("✅ Poppler adicionado ao PATH do usuário. Pode ser necessário reiniciar o terminal/IDE.")
                else:
                    print("✅ Poppler já está no PATH do usuário.")
                    
            if shutil.which("pdftotext.exe"):
                 print("✅ Poppler (pdftotext.exe) agora está acessível."); return True
            else:
                 print(f"⚠️ Poppler instalado, mas pdftotext.exe ainda não está no PATH da sessão atual. Adicione manualmente ou reinicie: {bin_path}"); return False
        except Exception as e_winreg:
            print(f"❌ Erro ao tentar modificar o PATH do usuário via registro: {e_winreg}")
            print(f"   Por favor, adicione manually o diretório '{bin_path}' ao seu PATH.")
            os.environ['PATH'] = f"{bin_path};{os.environ['PATH']}"
            return shutil.which("pdftotext.exe") is not None

    except requests.exceptions.RequestException as e_req:
        print(f"❌ Erro ao baixar Poppler: {str(e_req)}"); return False
    except zipfile.BadZipFile:
        print("❌ Erro: O arquivo baixado do Poppler não é um ZIP válido ou está corrompido.")
        if 'zip_path' in locals() and os.path.exists(zip_path): os.remove(zip_path); return False
    except Exception as e:
        print(f"❌ Erro inesperado ao instalar Poppler: {str(e)}")
        if 'install_dir' in locals() and os.path.exists(install_dir): pass; return False

def verificar_dependencias_essenciais():
    """Verifica se FFmpeg e Poppler estão instalados."""
    print("\n🔍 Verificando dependências essenciais...")
    detectar_sistema()
    
    if not _verificar_comando(
        [FFMPEG_BIN, '-version'],
        "FFmpeg encontrado.",
        "FFmpeg não encontrado. Necessário para manipulação de áudio/vídeo.",
        install_commands={
            'termux': ['pkg install ffmpeg'],
            'linux': ['sudo apt install ffmpeg', 'sudo yum install ffmpeg', 'sudo dnf install ffmpeg'],
            'macos': ['brew install ffmpeg'],
            'windows': ['Baixe em https://ffmpeg.org/download.html e adicione ao PATH']
        }
    ):
        print("    Algumas funcionalidades do script podem não funcionar sem FFmpeg.")
        
    pdftotext_cmd = "pdftotext.exe" if SISTEMA_OPERACIONAL_INFO.get('windows') else "pdftotext"
    if not _verificar_comando(
        [pdftotext_cmd, '-v'],
        "Poppler (pdftotext) encontrado.",
        "Poppler (pdftotext) não encontrado. Necessário para converter PDF para TXT.",
        install_commands={
            'termux': ['pkg install poppler'],
            'linux': ['sudo apt install poppler-utils', 'sudo yum install poppler-utils'],
            'macos': ['brew install poppler'],
            'windows': ['Tentativa de instalação automática será feita se necessário.']
        }
    ):
        print("    A conversão de PDF para TXT não funcionará sem Poppler.")
        
    print("✅ Verificação de dependências essenciais concluída.")

def converter_pdf_para_txt(caminho_pdf: str, caminho_txt: str) -> bool:
    """Converte um arquivo PDF para TXT usando pdftotext."""
    sistema = detectar_sistema()
    pdftotext_executable = "pdftotext"
    
    if sistema['windows']:
        pdftotext_executable = shutil.which("pdftotext.exe")
        if not pdftotext_executable:
            if not instalar_poppler_windows():
                print("❌ Falha ao instalar Poppler. Não é possível converter PDF."); return False
            pdftotext_executable = shutil.which("pdftotext.exe")
            if not pdftotext_executable:
                print("❌ pdftotext.exe não encontrado mesmo após tentativa de instalação."); return False
    elif sistema['termux'] and not shutil.which("pdftotext"):
        if not _instalar_dependencia_termux_auto("poppler"):
            print("❌ Falha ao instalar poppler no Termux. Não é possível converter PDF."); return False
        pdftotext_executable = "pdftotext"
        
    if not os.path.isfile(caminho_pdf):
        print(f"❌ Arquivo PDF não encontrado: {caminho_pdf}"); return False
        
    try:
        comando = [pdftotext_executable or "pdftotext", "-layout", "-enc", "UTF-8", caminho_pdf, caminho_txt]
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=300)
        print(f"✅ PDF convertido para TXT: {caminho_txt}"); return True
    except subprocess.CalledProcessError:
        try:
            print("⚠️ Conversão UTF-8 falhou, tentando encoding padrão...")
            comando = [pdftotext_executable or "pdftotext", "-layout", caminho_pdf, caminho_txt]
            resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=300)
            print(f"✅ PDF convertido para TXT: {caminho_txt}"); return True
        except subprocess.CalledProcessError as e2:
             print(f"❌ Erro ao converter PDF (tentativa 2): {e2.stderr.decode(errors='ignore')}"); return False
    except FileNotFoundError:
        print(f"❌ Comando '{pdftotext_executable or 'pdftotext'}' não encontrado...")
    except Exception as e:
        print(f"❌ Erro inesperado ao converter PDF: {str(e)}"); return False

# ================== FUNÇÕES DE UI E FLUXO (Inalteradas) ==================

def limpar_tela() -> None:
    """Limpa o console."""
    os.system('cls' if detectar_sistema()['windows'] else 'clear')

async def obter_opcao_numerica(prompt: str, num_max: int, permitir_zero=False) -> int:
    """Solicita ao usuário um número dentro de um intervalo válido."""
    min_val = 0 if permitir_zero else 1
    while True:
        try:
            escolha_str = await aioconsole.ainput(f"{prompt} [{min_val}-{num_max}]: ")
            if CANCELAR_PROCESSAMENTO: raise asyncio.CancelledError
            escolha = int(escolha_str)
            if min_val <= escolha <= num_max: return escolha
            else: print(f"⚠️ Opção inválida. Escolha um número entre {min_val} e {num_max}.")
        except ValueError: print("⚠️ Entrada inválida. Por favor, digite um número.")
        except asyncio.CancelledError: print("\n🚫 Entrada cancelada."); raise

async def obter_confirmacao(prompt: str, default_yes=True) -> bool:
    """Solicita ao usuário uma confirmação (S/n ou s/N)."""
    opcoes_prompt = "(S/n)" if default_yes else "(s/N)"
    while True:
        try:
            resposta = await aioconsole.ainput(f"{prompt} {opcoes_prompt}: ")
            if CANCELAR_PROCESSAMENTO: raise asyncio.CancelledError
            resposta = resposta.strip().lower()
            if not resposta: return default_yes
            if resposta in ['s', 'sim']: return True
            if resposta in ['n', 'nao', 'não']: return False
            print("⚠️ Resposta inválida. Digite 's' ou 'n'.")
        except asyncio.CancelledError: print("\n🚫 Entrada cancelada."); raise

async def exibir_banner_e_menu(titulo_menu: str, opcoes_menu: dict):
    """Exibe o banner e um menu de opções, retornando a escolha do usuário."""
    limpar_tela()
    print("╔════════════════════════════════════════════╗")
    print("║         CONVERSOR TTS COMPLETO             ║")
    print("║ Text-to-Speech + Melhoria de Áudio em PT-BR║")
    print("╚════════════════════════════════════════════╝")
    print(f"\n--- {titulo_menu.upper()} ---")
    for num, desc in opcoes_menu.items(): print(f"{num}. {desc}")
    
    max_key = 0
    try:
        max_key = max(int(k) for k in opcoes_menu.keys() if k.isdigit())
    except ValueError:
        max_key = len(opcoes_menu) - 1
        
    return await obter_opcao_numerica("Opção", max_key, permitir_zero=('0' in opcoes_menu))

# ================== FUNÇÕES DE MANIPULAÇÃO DE ARQUIVOS (Inalteradas) ==================

def detectar_encoding_arquivo(caminho_arquivo: str) -> str:
    """Tenta detectar o encoding de um arquivo de texto."""
    try:
        with open(caminho_arquivo, 'rb') as f: raw_data = f.read(50000)
        resultado = chardet.detect(raw_data)
        encoding = resultado['encoding']
        confidence = resultado['confidence']
        
        if encoding and confidence > 0.7:
            return encoding
            
        for enc_try in ENCODINGS_TENTATIVAS:
            try:
                with open(caminho_arquivo, 'r', encoding=enc_try) as f_test: f_test.read(1024)
                return enc_try
            except (UnicodeDecodeError, TypeError): continue
            
        return 'utf-8'
    except Exception as e:
        print(f"⚠️ Erro ao detectar encoding: {str(e)}... Usando 'utf-8'.")
        return 'utf-8'

def ler_arquivo_texto(caminho_arquivo: str) -> str:
    """Lê um arquivo de texto usando o encoding detectado."""
    encoding = detectar_encoding_arquivo(caminho_arquivo)
    try:
        with open(caminho_arquivo, 'r', encoding=encoding, errors='replace') as f:
            return f.read()
    except Exception as e:
        print(f"❌ Erro ao ler arquivo '{caminho_arquivo}' com encoding '{encoding}': {str(e)}")
        return ""

def salvar_arquivo_texto(caminho_arquivo: str, conteudo: str):
    """Salva uma string em um arquivo de texto (sempre em UTF-8)."""
    try:
        os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
        with open(caminho_arquivo, 'w', encoding='utf-8') as f: f.write(conteudo)
        print(f"✅ Arquivo salvo: {caminho_arquivo}")
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo '{caminho_arquivo}': {str(e)}")

def limpar_nome_arquivo(nome: str) -> str:
    """Limpa e normaliza um nome de arquivo, removendo caracteres especiais."""
    nome_sem_ext, ext = os.path.splitext(nome)
    nome_normalizado = unicodedata.normalize('NFKD', nome_sem_ext).encode('ascii', 'ignore').decode('ascii')
    nome_limpo = re.sub(r'[^\w\s-]', '', nome_normalizado).strip()
    nome_limpo = re.sub(r'[-\s]+', '_', nome_limpo)
    return nome_limpo + ext if ext else nome_limpo

def extrair_texto_de_epub(caminho_epub: str) -> str:
    """Extrai e concatena o conteúdo textual de um arquivo EPUB."""
    print(f"\n📖 Extraindo conteúdo de: {caminho_epub}")
    texto_completo = ""
    try:
        with zipfile.ZipFile(caminho_epub, 'r') as epub_zip:
            arquivos_xhtml_ordenados = []
            try:
                container_xml = epub_zip.read('META-INF/container.xml').decode('utf-8')
                opf_path_match = re.search(r'full-path="([^"]+)"', container_xml)
                if not opf_path_match: raise Exception("Caminho do OPF não encontrado.")
                
                opf_path = opf_path_match.group(1)
                opf_content = epub_zip.read(opf_path).decode('utf-8')
                opf_dir = os.path.dirname(opf_path)
                
                spine_items = [m.group(1) for m in re.finditer(r'<itemref\s+idref="([^"]+)"', opf_content)]
                if not spine_items: raise Exception("Nenhum item na 'spine'.")
                
                manifest_hrefs = {
                    m.group(1): m.group(2) for m in re.finditer(
                        r'<item\s+id="([^"]+)"\s+href="([^"]+)"\s+media-type="application/xhtml\+xml"', opf_content
                    )
                }
                
                for idref in spine_items:
                    if idref in manifest_hrefs:
                        xhtml_path_in_zip = os.path.normpath(os.path.join(opf_dir, manifest_hrefs[idref]))
                        arquivos_xhtml_ordenados.append(xhtml_path_in_zip)
                        
            except Exception as e_opf:
                print(f"⚠️ Erro ao processar OPF/Spine: {e_opf}. Tentando todos XHTML/HTML.")
                arquivos_xhtml_ordenados = sorted([
                    f.filename for f in epub_zip.infolist() 
                    if f.filename.lower().endswith(('.html', '.xhtml')) and 
                    not re.search(r'(toc|nav|cover|ncx)', f.filename, re.IGNORECASE)
                ])

            if not arquivos_xhtml_ordenados:
                print("❌ Nenhum arquivo de conteúdo (XHTML/HTML) utilizável encontrado no EPUB."); return ""

            h = html2text.HTML2Text()
            h.ignore_links = True; h.ignore_images = True; h.ignore_emphasis = False; h.body_width = 0
            
            for nome_arquivo in tqdm(arquivos_xhtml_ordenados, desc="Processando arquivos EPUB"):
                try:
                    html_bytes = epub_zip.read(nome_arquivo)
                    detected_encoding = chardet.detect(html_bytes)['encoding'] or 'utf-8'
                    html_texto = html_bytes.decode(detected_encoding, errors='replace')
                    
                    soup = BeautifulSoup(html_texto, 'html.parser')
                    for tag in soup(['nav', 'header', 'footer', 'style', 'script', 'figure', 'figcaption', 'aside', 'link', 'meta']):
                        tag.decompose()
                        
                    content_tag = soup.find('body') or soup
                    if content_tag:
                        texto_completo += h.handle(str(content_tag)) + "\n\n"
                        
                except KeyError: print(f"⚠️ Arquivo não encontrado no ZIP: {nome_arquivo}")
                except Exception as e_file: print(f"❌ Erro ao processar '{nome_arquivo}': {e_file}")
                
        if not texto_completo.strip():
            print("⚠️ Nenhum conteúdo textual extraído do EPUB."); return ""
            
        return texto_completo
        
    except FileNotFoundError: print(f"❌ Arquivo EPUB não encontrado: {caminho_epub}")
    except zipfile.BadZipFile: print(f"❌ Arquivo EPUB inválido: {caminho_epub}")
    except Exception as e: print(f"❌ Erro geral ao processar EPUB: {e}"); return ""

def dividir_texto_para_tts(texto_processado: str, limite_caracteres: int) -> list:
    """Divide o texto em partes (chunks) para a API TTS."""
    partes_iniciais = texto_processado.split('\n\n')
    partes_finais = []

    for p_inicial in partes_iniciais:
        p_strip = p_inicial.strip()
        if not p_strip: continue

        if len(p_strip) <= limite_caracteres:
            partes_finais.append(p_strip)
            continue

        frases_com_delimitadores = re.split(r'([.!?…]+)', p_strip)
        segmento_atual = ""
        idx_frase = 0

        while idx_frase < len(frases_com_delimitadores):
            frase_atual = frases_com_delimitadores[idx_frase].strip()
            delimitador = frases_com_delimitadores[idx_frase + 1].strip() if idx_frase + 1 < len(frases_com_delimitadores) else ""
            
            trecho_completo = (frase_atual + delimitador).strip()
            if not trecho_completo:
                idx_frase += 2 if delimitador else 1
                continue

            if len(segmento_atual) + len(trecho_completo) + 1 <= limite_caracteres:
                segmento_atual += (" " if segmento_atual else "") + trecho_completo
            else:
                if segmento_atual:
                    partes_finais.append(segmento_atual)
                
                if len(trecho_completo) > limite_caracteres:
                    for i in range(0, len(trecho_completo), limite_caracteres):
                        partes_finais.append(trecho_completo[i:i+limite_caracteres])
                    segmento_atual = ""
                else:
                    segmento_atual = trecho_completo

            idx_frase += 2 if delimitador else 1

        if segmento_atual:
            partes_finais.append(segmento_atual)

    return [p for p in partes_finais if p.strip()]

# ================== FUNÇÕES DE FFmpeg (Inalteradas) ==================

def _executar_ffmpeg_comando(comando, descricao="processamento FFmpeg", total_duration=None):
    """Executa um comando FFmpeg, exibindo progresso percentual."""
    print(f"⚙️ Executando: {descricao}...")
    
    FFMPEG_PROGRESS_RE = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

    def _parse_ffmpeg_time_to_seconds(time_str: str) -> float:
        match = FFMPEG_PROGRESS_RE.search(time_str)
        if match:
            h, m, s, ms = map(int, match.groups())
            return h * 3600 + m * 60 + s + ms / 100.0
        return 0.0

    try:
        process = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )

        last_percent = -1
        last_time_str = ""
        stderr_output_buffer = []

        for line in iter(process.stderr.readline, ''):
            if CANCELAR_PROCESSAMENTO:
                print("\n🚫 Recebido sinal de cancelamento. Terminando processo FFmpeg...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("   Processo não terminou, forçando... (kill)")
                    process.kill()
                return False

            if "time=" in line:
                current_time_sec = _parse_ffmpeg_time_to_seconds(line)
                if total_duration and total_duration > 0:
                    percent = min(max((current_time_sec / total_duration) * 100, 0), 100)
                    if int(percent) > last_percent:
                        last_percent = int(percent)
                        bar = '█' * (last_percent // 4)
                        sys.stdout.write(f"\r   Progresso: [{bar:<25}] {last_percent:3d}%")
                        sys.stdout.flush()
                else:
                    time_match = FFMPEG_PROGRESS_RE.search(line)
                    if time_match:
                        time_str = time_match.group(0)
                        if time_str != last_time_str:
                            sys.stdout.write(f"\r   Tempo: {time_str}...")
                            sys.stdout.flush()
                            last_time_str = time_str
            elif "error" in line.lower() or "failed" in line.lower():
                 stderr_output_buffer.append(line.strip())
        
        process.wait()
        
        if last_percent != -1 or last_time_str:
            sys.stdout.write("\n")
            sys.stdout.flush()

        if process.returncode == 0:
            print(f"✅ {descricao} concluído com sucesso.")
            return True
        else:
            print(f"\n❌ {descricao} falhou (código {process.returncode}).")
            if stderr_output_buffer:
                 print("   --- Saída de Erro FFmpeg ---")
                 for err_line in stderr_output_buffer[-10:]:
                     print(f"   {err_line}")
                 print("   ------------------------------")
            return False

    except FileNotFoundError:
         print(f"❌ Erro: Comando '{comando[0]}' (FFmpeg/FFprobe) não encontrado.")
         print("   Verifique se o FFmpeg está instalado e no PATH do sistema.")
         return False
    except Exception as e:
        print(f"❌ Erro inesperado ao executar FFmpeg: {e}")
        import traceback
        traceback.print_exc()
        return False

def obter_duracao_midia(caminho_arquivo: str) -> float:
    """Obtém a duração de um arquivo de mídia em segundos usando ffprobe."""
    if not shutil.which(FFPROBE_BIN):
        print(f"⚠️ {FFPROBE_BIN} não encontrado. Não é possível obter duração da mídia.")
        return 0.0
        
    comando = [
        FFPROBE_BIN, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', caminho_arquivo
    ]
    try:
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(resultado.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        print(f"⚠️ Erro ao obter duração de '{os.path.basename(caminho_arquivo)}': {e}")
        return 0.0

def criar_video_com_audio_ffmpeg(audio_path, video_path, duracao_segundos, resolucao_str="640x360"):
    """Cria um vídeo com tela preta a partir de um áudio."""
    if duracao_segundos <= 0:
        print("⚠️ Duração inválida para criar vídeo."); return False
        
    comando = [
        FFMPEG_BIN, '-y',
        '-f', 'lavfi', '-i', f"color=c=black:s={resolucao_str}:r=1:d={duracao_segundos + 1:.3f}",
        '-i', audio_path,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage',
        '-c:a', 'aac', '-b:a', '128k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        video_path
    ]
    return _executar_ffmpeg_comando(comando, 
                                    f"criação de vídeo a partir de {Path(audio_path).name}", 
                                    total_duration=duracao_segundos)

def acelerar_midia_ffmpeg(input_path: str, output_path: str, velocidade: float = 1.0, is_video: bool = False) -> bool:
    """Acelera áudio ou vídeo usando FFmpeg."""
    try:
        if velocidade <= 0:
            print("⚠️ Velocidade inválida. Use um valor acima de 0."); return False
        if velocidade == 1.0:
            print("ℹ️ Velocidade é 1.0x. Copiando arquivo...")
            shutil.copy(input_path, output_path); return True
            
        duracao_entrada = obter_duracao_midia(input_path)
        if duracao_entrada == 0: duracao_entrada = None

        atempo_filters = []
        restante = velocidade
        while restante > 2.0:
            atempo_filters.append("atempo=2.0")
            restante /= 2.0
        while restante < 0.5 and restante > 0:
            atempo_filters.append("atempo=0.5")
            restante /= 0.5
        if restante != 1.0:
             atempo_filters.append(f"atempo={restante:.3f}")
        
        atempo_str = ",".join(atempo_filters) if atempo_filters else "atempo=1.0"
        
        tmp_audio = str(Path(str(output_path).replace(".mp4", "_audio_temp.m4a")))
        tmp_video = str(Path(str(output_path).replace(".mp4", "_video_temp.mp4")))
        
        print(f"🎧 Acelerando áudio em {velocidade}x...")
        comando_audio = [
            FFMPEG_BIN, "-y",
            "-i", input_path,
            "-vn",
            "-filter:a", atempo_str,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            tmp_audio
        ]
        if not _executar_ffmpeg_comando(comando_audio, f"aceleração do áudio ({velocidade}x)", total_duration=duracao_entrada):
            print("❌ Falha ao acelerar áudio."); return False

        if is_video:
            print(f"🎬 Ajustando vídeo em {velocidade}x...")
            comando_video = [
                FFMPEG_BIN, "-y",
                "-i", input_path,
                "-an",
                "-filter:v", f"setpts={1/velocidade:.4f}*PTS",
                "-preset", "ultrafast",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                tmp_video
            ]
            if not _executar_ffmpeg_comando(comando_video, f"ajuste do vídeo ({velocidade}x)", total_duration=duracao_entrada):
                print("❌ Falha ao ajustar vídeo.")
                if os.path.exists(tmp_audio): os.remove(tmp_audio); return False

            print("🔗 Juntando áudio e vídeo...")
            comando_merge = [
                FFMPEG_BIN, "-y",
                "-i", tmp_video,
                "-i", tmp_audio,
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-movflags", "+faststart",
                output_path
            ]
            sucesso = _executar_ffmpeg_comando(comando_merge, f"junção final ({velocidade}x)")
            
            for temp in [tmp_audio, tmp_video]:
                if os.path.exists(temp): os.remove(temp)
            return sucesso
        else:
            shutil.move(tmp_audio, output_path)
            print("✅ Áudio acelerado com sucesso!")
            return True

    except Exception as e:
        print(f"❌ Erro ao acelerar mídia: {e}"); return False

def unificar_arquivos_audio_ffmpeg(lista_arquivos_temp: list, arquivo_final: str) -> bool:
    """Une arquivos de áudio temporários em um único arquivo final usando FFmpeg concat."""
    if not lista_arquivos_temp:
        print("⚠️ Nenhum arquivo de áudio para unificar."); return False
    
    dir_saida = os.path.dirname(arquivo_final)
    os.makedirs(dir_saida, exist_ok=True)
    nome_lista_limpo = limpar_nome_arquivo(f"_{Path(arquivo_final).stem}_filelist.txt")
    lista_txt_path = Path(dir_saida) / nome_lista_limpo

    try:
        with open(lista_txt_path, "w", encoding='utf-8') as f_list:
            for temp_file in lista_arquivos_temp:
                safe_path = str(Path(temp_file).resolve()).replace("'", r"\'")
                f_list.write(f"file '{safe_path}'\n")
        
        comando = [
            FFMPEG_BIN, '-y', 
            '-f', 'concat', 
            '-safe', '0',
            '-i', str(lista_txt_path), 
            '-c', 'copy',
            arquivo_final
        ]
        return _executar_ffmpeg_comando(comando, f"unificação de áudio para {os.path.basename(arquivo_final)}")
        
    except IOError as e:
        print(f"❌ Erro ao criar arquivo de lista para FFmpeg: {e}"); return False
    finally:
        if lista_txt_path.exists():
            lista_txt_path.unlink(missing_ok=True)

def dividir_midia_ffmpeg(input_path, duracao_total_seg, duracao_max_parte_seg, nome_base_saida, extensao_saida):
    """Divide um arquivo de mídia em partes menores usando FFmpeg (-c copy)."""
    if duracao_total_seg <= duracao_max_parte_seg:
        print(f"    ℹ️ Arquivo tem {duracao_total_seg/3600:.2f}h. Não precisa ser dividido (limite {duracao_max_parte_seg/3600:.1f}h).")
        output_single_part_path = f"{nome_base_saida}_parte1{extensao_saida}"
        try:
            shutil.copy2(input_path, output_single_part_path)
            print(f"    ✅ Arquivo copiado para: {output_single_part_path}")
            return [output_single_part_path]
        except Exception as e:
            print(f"    ❌ Erro ao copiar arquivo original para o nome da parte: {e}"); return []

    num_partes = ceil(duracao_total_seg / duracao_max_parte_seg)
    print(f"\n    📄 Arquivo tem {duracao_total_seg/3600:.2f}h. Será dividido em {num_partes} partes de até {duracao_max_parte_seg/3600:.1f}h.")
    
    arquivos_gerados = []
    for i in range(num_partes):
        if CANCELAR_PROCESSAMENTO:
            print("    🚫 Divisão cancelada pelo usuário."); break
            
        inicio_seg = i * duracao_max_parte_seg
        duracao_segmento_seg = min(duracao_max_parte_seg, duracao_total_seg - inicio_seg)
        if duracao_segmento_seg <= 0: continue
             
        output_path_parte = f"{nome_base_saida}_parte{i+1}{extensao_saida}"
        
        print(f"    🎞️ Criando parte {i+1}/{num_partes}...")
        comando = [
            FFMPEG_BIN, '-y', 
            '-ss', str(inicio_seg),
            '-i', input_path,
            '-t', str(duracao_segmento_seg),
            '-c', 'copy',
            output_path_parte
        ]
        if _executar_ffmpeg_comando(comando, f"criação da parte {i+1}"):
            arquivos_gerados.append(output_path_parte)
        else:
            print(f"    ❌ Falha ao criar parte {i+1}. A divisão pode estar incompleta.")
            
    return arquivos_gerados

# ================== MENUS E LÓGICA DE OPERAÇÃO (Atualizados) ==================

async def _selecionar_arquivo_para_processamento(extensoes_permitidas: list) -> str:
    """Navegador de arquivos de console para selecionar um arquivo."""
    sistema = detectar_sistema()
    
    dir_atual = None
    if sistema['termux'] or sistema['android']:
        caminhos_tentativa = [
            Path.home() / 'storage' / 'shared' / 'Download',
            Path("/storage/emulated/0/Download"),
            Path.home() / 'downloads',
        ]
        for p in caminhos_tentativa:
            if p.is_dir(): dir_atual = p; break
        if not dir_atual: dir_atual = Path.home()
    elif sistema['windows']:
        dir_atual = Path.home() / 'Downloads'
        if not dir_atual.is_dir(): dir_atual = Path.home() / 'Desktop'
    else:
        dir_atual = Path.home() / 'Downloads'
        if not dir_atual.is_dir(): dir_atual = Path.home()

    if not dir_atual or not dir_atual.is_dir():
         dir_atual = Path.cwd()
         print(f"⚠️ Pastas padrão não encontradas, usando diretório atual: {dir_atual}")

    while True:
        limpar_tela()
        print(f"📂 SELEÇÃO DE ARQUIVO (Extensões: {', '.join(extensoes_permitidas)})")
        print(f"\nDiretório atual: {dir_atual}")
        
        itens_no_diretorio = []
        try:
            if dir_atual.parent != dir_atual:
                itens_no_diretorio.append(("[..] (Voltar)", dir_atual.parent, True))
            
            diretorios_listados = []
            arquivos_listados = []

            for item in sorted(list(dir_atual.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower())):
                if item.is_dir():
                    diretorios_listados.append((f"[{item.name}]", item, True))
                elif item.suffix.lower() in extensoes_permitidas:
                    arquivos_listados.append((item.name, item, False))
            
            itens_no_diretorio.extend(diretorios_listados)
            itens_no_diretorio.extend(arquivos_listados)

        except PermissionError:
            print(f"❌ Permissão negada para acessar: {dir_atual}")
            dir_atual = dir_atual.parent if dir_atual.parent != dir_atual else Path.home()
            await asyncio.sleep(2); continue
        except Exception as e:
            print(f"❌ Erro ao listar diretório {dir_atual}: {e}")
            dir_atual = Path.home()
            await asyncio.sleep(2); continue
        
        for i, (nome, _, is_dir) in enumerate(itens_no_diretorio):
            print(f"{i+1}. {nome}")

        if not any(not item[2] for item in itens_no_diretorio):
             print(f"\n⚠️ Nenhum arquivo ({', '.join(extensoes_permitidas)}) encontrado em {dir_atual}")

        print("\nOpções:")
        print("M. Digitar caminho manualmente")
        print("V. Voltar ao menu anterior")

        try:
            escolha_str = (await aioconsole.ainput("\nEscolha uma opção ou número: ")).strip().upper()
            if CANCELAR_PROCESSAMENTO: raise asyncio.CancelledError

            if escolha_str == 'V': return ""
            if escolha_str == 'M':
                caminho_manual_raw = await aioconsole.ainput("Digite o caminho completo do arquivo: ")
                caminho_manual_str = caminho_manual_raw.strip().replace('"', '')
                if not caminho_manual_str:
                    print("⚠️ Caminho não pode ser vazio."); await asyncio.sleep(1.5); continue

                caminho_manual_path = Path(caminho_manual_str)
                if caminho_manual_path.is_file() and caminho_manual_path.suffix.lower() in extensoes_permitidas:
                    return str(caminho_manual_path)
                else:
                    print(f"❌ Caminho inválido ('{caminho_manual_str}') ou tipo não permitido."); await asyncio.sleep(1.5); continue
            
            if escolha_str.isdigit():
                idx_escolha = int(escolha_str) - 1
                if 0 <= idx_escolha < len(itens_no_diretorio):
                    nome_sel, path_sel, is_dir_sel = itens_no_diretorio[idx_escolha]
                    if is_dir_sel:
                        dir_atual = path_sel
                    else:
                        return str(path_sel)
                else:
                    print("❌ Opção numérica inválida.")
            else:
                print("❌ Opção inválida.")
            await asyncio.sleep(1)

        except (ValueError, IndexError):
            print("❌ Seleção inválida."); await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("\n🚫 Seleção cancelada."); return ""

async def _processar_arquivo_selecionado_para_texto(caminho_arquivo_orig: str) -> str:
    """Extrai texto, formata e salva como "_formatado.txt"."""
    if not caminho_arquivo_orig: return ""
    
    path_obj = Path(caminho_arquivo_orig)
    nome_base_limpo = limpar_nome_arquivo(path_obj.stem)
    dir_saida = path_obj.parent
    caminho_txt_formatado = dir_saida / f"{nome_base_limpo}_formatado.txt"

    if caminho_txt_formatado.exists() and caminho_txt_formatado.name != path_obj.name :
        if not await obter_confirmacao(f"Arquivo '{caminho_txt_formatado.name}' já existe. Reprocessar?", default_yes=False):
            return str(caminho_txt_formatado)

    texto_bruto = ""; extensao = path_obj.suffix.lower()
    
    if extensao == '.pdf':
        caminho_txt_temporario = dir_saida / f"{nome_base_limpo}_tempExtraido.txt"
        if not converter_pdf_para_txt(str(path_obj), str(caminho_txt_temporario)):
            print("❌ Falha na conversão PDF.");
            caminho_txt_temporario.unlink(missing_ok=True); return ""
        texto_bruto = ler_arquivo_texto(str(caminho_txt_temporario))
        caminho_txt_temporario.unlink(missing_ok=True)
    elif extensao == '.epub':
        texto_bruto = extrair_texto_de_epub(str(path_obj))
    elif extensao == '.txt':
        texto_bruto = ler_arquivo_texto(str(path_obj))
    else:
        print(f"❌ Formato não suportado: {extensao}"); return ""

    if not texto_bruto.strip():
        print("❌ Conteúdo do arquivo extraído está vazio."); return ""

    texto_final_formatado = formatar_texto_para_tts(texto_bruto)
    salvar_arquivo_texto(str(caminho_txt_formatado), texto_final_formatado)
    
    sistema = detectar_sistema()
    if sistema['windows'] or sistema['macos'] or (sistema['linux'] and not sistema['android']):
        if await obter_confirmacao("Abrir TXT formatado para edição manual?"):
            print(f"📝 Abrindo '{caminho_txt_formatado.name}' no editor padrão...")
            try:
                if sistema['windows']: os.startfile(caminho_txt_formatado)
                elif sistema['macos']: subprocess.run(['open', str(caminho_txt_formatado)], check=True)
                else: subprocess.run(['xdg-open', str(caminho_txt_formatado)], check=True)
                await aioconsole.ainput("Pressione ENTER após salvar suas edições...")
            except Exception as e_edit:
                print(f"❌ Não foi possível abrir editor: {e_edit}")
    elif sistema['android']:
        print(f"✅ Arquivo formatado salvo: {caminho_txt_formatado}")
        print("   (No Android, edite o arquivo manualmente se necessário e depois selecione o '_formatado.txt' para conversão)")
        
    return str(caminho_txt_formatado)

# --- MODIFICAÇÃO (Gemini-User): _converter_chunk_tts_edge ---
# - Trocado 'while tentativas < MAX_TTS_TENTATIVAS' por 'while True'
# - Removida a lógica de falha definitiva (else)
# - Mantido backoff exponencial (com teto) para evitar hot-loop
async def _converter_chunk_tts_edge(texto_chunk: str, voz: str, caminho_saida_temp: str, indice_chunk: int, total_chunks: int) -> bool:
    """Converte um chunk de texto para áudio usando Edge-TTS (Loop infinito até sucesso)."""
    global CANCELAR_PROCESSAMENTO
    path_saida_obj = Path(caminho_saida_temp)

    if path_saida_obj.exists() and path_saida_obj.stat().st_size > 200:
        return True

    tentativas = 0
    # Loop infinito até o chunk ser convertido ou o processo ser cancelado
    while True:
        if CANCELAR_PROCESSAMENTO: return False
        
        path_saida_obj.unlink(missing_ok=True)
        
        if not texto_chunk or not texto_chunk.strip():
            print(f"⚠️ [Edge] Chunk {indice_chunk}/{total_chunks} vazio, pulando.")
            return True # Considera sucesso (chunk vazio)

        try:
            communicate = edge_tts.Communicate(texto_chunk, voz)
            await communicate.save(caminho_saida_temp)

            if path_saida_obj.exists() and path_saida_obj.stat().st_size > 200:
                return True # SUCESSO! O loop termina aqui.
            else:
                tamanho_real = path_saida_obj.stat().st_size if path_saida_obj.exists() else 0
                print(f"⚠️ [Edge] Arquivo áudio chunk {indice_chunk} inválido (tamanho: {tamanho_real} bytes). Tentativa {tentativas + 1}.")
                
        except edge_tts.exceptions.NoAudioReceived:
             print(f"❌ [Edge] Sem áudio recebido (NoAudioReceived) chunk {indice_chunk} (tentativa {tentativas + 1}).")
        except asyncio.TimeoutError:
            print(f"❌ [Edge] Timeout na comunicação TTS chunk {indice_chunk} (tentativa {tentativas + 1}).")
        except Exception as e:
            print(f"❌ [Edge] Erro INESPERADO TTS chunk {indice_chunk} (tentativa {tentativas + 1}): {type(e).__name__} - {e}")
            import traceback; traceback.print_exc()

        # Se chegou aqui, a conversão falhou
        tentativas += 1
        
        # Mantém o backoff exponencial para não sobrecarregar a API,
        # mas agora sem limite de tentativas.
        # ==================================================================
        # ATUALIZAÇÃO: Teto de espera reduzido de 60s para 20s
        wait_time = min(2 * tentativas, 20) 
        # ==================================================================
        
        print(f"   Retentando chunk {indice_chunk} em {wait_time}s... (Tentativa {tentativas})")
        await asyncio.sleep(wait_time)
        
    # Esta linha (return False) nunca será alcançada devido ao 'while True'
    # O loop só sai com 'return True' (sucesso) ou 'return False' (cancelamento)
    
# --- MODIFICAÇÃO (Gemini-User): _converter_chunk_tts_gemini ---
# - Removido o 'if tentativas >= MAX_TTS_TENTATIVAS: return False'
# - Lógica 'while True' já estava presente, mas agora não desistirá mais
# - Backoff exponencial mantido e com teto de 60s
async def _converter_chunk_tts_gemini(
    texto_chunk: str, 
    voz_name: str, 
    caminho_saida_temp: str, 
    indice_chunk: int, 
    total_chunks: int, 
    api_key: str, 
    aiohttp_session: aiohttp.ClientSession
) -> bool:
    """Converte um chunk de texto para áudio usando a API Gemini TTS (Loop infinito até sucesso)."""
    global CANCELAR_PROCESSAMENTO
    path_saida_obj = Path(caminho_saida_temp)

    if path_saida_obj.exists() and path_saida_obj.stat().st_size > 200:
        return True

    tentativas = 0
    # Loop de "Brute Force": Tenta para sempre até conseguir, ou falhar por erro fatal
    while True: 
        if CANCELAR_PROCESSAMENTO: return False
        
        path_saida_obj.unlink(missing_ok=True)
        
        if not texto_chunk or not texto_chunk.strip():
            print(f"⚠️ [Gemini] Chunk {indice_chunk}/{total_chunks} vazio, pulando.")
            return True # Considera sucesso (chunk vazio)
            
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": texto_chunk}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz_name}}
                }
            },
            "model": "gemini-2.5-flash-preview-tts"
        }
        
        pcm_data_raw = None
        http_status = 0
        
        try:
            async with aiohttp_session.post(api_url, json=payload, timeout=60) as response:
                http_status = response.status
                
                if http_status == 200:
                    result = await response.json()
                    audio_data_base64 = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('inlineData', {}).get('data')
                    if audio_data_base64:
                        pcm_data_raw = base64.b64decode(audio_data_base64)
                    else:
                        print(f"❌ [Gemini] API retornou sucesso, mas sem dados de áudio (chunk {indice_chunk}). Resposta: {result}")
                        raise Exception("NoAudioDataInResponse")
                
                elif http_status == 429: # Cota Excedida
                    error_json = {}
                    wait_time = 0
                    try:
                        error_json = await response.json()
                        details = error_json.get('error', {}).get('details', [])
                        for detail in details:
                            if detail.get('@type') == "type.googleapis.com/google.rpc.RetryInfo":
                                delay_str = detail.get('retryDelay', '0s')
                                # IMPORTANTE: Esse é o tempo que a API *manda* esperar
                                wait_time = float(delay_str.replace('s', '')) + 0.0 
                                break
                    except Exception as e:
                        print(f"   [Gemini] Não foi possível analisar o JSON do erro 429: {e}")

                    if wait_time == 0:
                        # Fallback se a API não informar o tempo
                        wait_time = (1 ** tentativas) + random.uniform(0, 1)
                    
                    print(f"⚠️ [Gemini] Cota da API excedida (HTTP 429) chunk {indice_chunk}.")
                    print(f"   Aguardando {wait_time:.2f} segundos (conforme API)...")
                    
                    # AQUI ESTÁ O TEMPO DE ESPERA OBRIGATÓRIO (NÃO REMOVER)
                    await asyncio.sleep(wait_time)
                    continue # Tenta novamente (não incrementa 'tentativas' principais)
                
                else: # Outros erros
                    error_text = await response.text()
                    print(f"❌ [Gemini] Erro na API (HTTP {http_status}) chunk {indice_chunk} (tentativa {tentativas + 1}): {error_text[:200]}...")
                    if http_status == 400 or "API key expired" in error_text:
                         print("   ERRO: Chave de API inválida ou expirada. Abortando este chunk.")
                         return False # Erro fatal (não adianta tentar de novo)
                    
        except asyncio.TimeoutError:
            print(f"❌ [Gemini] Timeout na API TTS chunk {indice_chunk} (tentativa {tentativas + 1}).")
        except Exception as e:
            print(f"❌ [Gemini] Erro na chamada da API chunk {indice_chunk} (tentativa {tentativas + 1}): {e}")
        
        if pcm_data_raw:
            try:
                ffmpeg_cmd = [
                    FFMPEG_BIN,
                    '-f', 's16le',
                    '-ar', '24000',
                    '-ac', '1',
                    '-i', 'pipe:0',
                    '-c:a', 'libmp3lame', '-q:a', '2',
                    '-y',
                    str(caminho_saida_temp)
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate(input=pcm_data_raw)
                
                if process.returncode == 0:
                    if path_saida_obj.exists() and path_saida_obj.stat().st_size > 200:
                        return True # SUCESSO! O loop termina aqui.
                    else:
                        print(f"❌ [Gemini] FFmpeg executado, mas MP3 final inválido (chunk {indice_chunk}).")
                else:
                    print(f"❌ [Gemini] FFmpeg falhou ao converter PCM->MP3 (chunk {indice_chunk}): {stderr.decode(errors='ignore')}")

            except Exception as e_ffmpeg:
                print(f"❌ [Gemini] Erro inesperado ao executar FFmpeg (chunk {indice_chunk}): {e_ffmpeg}")
        
        # Se a API ou o FFmpeg falharam (e não foi 429)
        tentativas += 1

        # --- MODIFICAÇÃO (Gemini-User): Bloco 'if tentativas >= MAX_TTS_TENTATIVAS' removido ---
        
        # Se não foi 429, faz o backoff exponencial padrão
        if http_status != 429:
            # ==================================================================
            # ATUALIZAÇÃO: Teto de espera reduzido de 60s para 20s
            wait_time_exp = min((2 ** tentativas) + random.uniform(0, 1), 20)
            # ==================================================================
            print(f"   Retentando chunk {indice_chunk} em {wait_time_exp:.2f}s... (Tentativa {tentativas})")
            await asyncio.sleep(wait_time_exp)
        
        # O loop 'while True' continua


async def iniciar_conversao_tts():
    """Menu e fluxo principal para converter um arquivo (TXT/PDF/EPUB) para áudio."""
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False
    
    caminho_arquivo_orig = await _selecionar_arquivo_para_processamento(['.txt', '.pdf', '.epub'])
    if not caminho_arquivo_orig or CANCELAR_PROCESSAMENTO: return

    caminho_txt_processado = await _processar_arquivo_selecionado_para_texto(caminho_arquivo_orig)
    if not caminho_txt_processado or CANCELAR_PROCESSAMENTO: return

    limpar_tela()
    print("\n--- SELECIONAR MOTOR TTS ---")
    print("1. Edge TTS (Padrão, grátis, sem chave)")
    print("2. Gemini TTS (Requer API Key, vozes diferentes)")
    print("3. Voltar")
    escolha_motor_idx = await obter_opcao_numerica("Escolha o motor", 3)
    
    if escolha_motor_idx == 3: return
    motor_escolhido = "edge" if escolha_motor_idx == 1 else "gemini"
    
    gemini_api_key_local = ""
    if motor_escolhido == "gemini":
        if not GEMINI_API_KEY_ATUAL:
            print("\n" + "!"*60)
            print("❌ A API Key do Gemini não está configurada!")
            print("   Para usar o Gemini TTS, vá ao Menu Principal e")
            print("   use a 'Opção 8: CONFIGURAR API KEY (Gemini)'.")
            print("!"*60)
            await aioconsole.ainput("\nPressione ENTER para voltar ao menu...")
            return
        gemini_api_key_local = GEMINI_API_KEY_ATUAL
        print("✅ API Key do Gemini carregada para a conversão.")
        await asyncio.sleep(1.5)

    opcoes_voz = {}
    lista_vozes_desc = []
    
    if motor_escolhido == "edge":
        lista_vozes_desc = VOZES_PT_BR
        opcoes_voz = {str(i+1): voz for i, voz in enumerate(VOZES_PT_BR)}
    else:
        lista_vozes_desc = list(VOZES_GEMINI_PT_BR.keys())
        opcoes_voz = {str(i+1): desc for i, desc in enumerate(lista_vozes_desc)}
    
    opcoes_voz[str(len(opcoes_voz)+1)] = "Voltar"
    
    limpar_tela(); print("\n--- SELECIONAR VOZ ---")
    for num, desc in opcoes_voz.items(): print(f"{num}. {desc}")
    
    escolha_voz_idx = await obter_opcao_numerica("Escolha uma voz", len(opcoes_voz))
    if escolha_voz_idx == len(opcoes_voz): return
    
    voz_escolhida_name = ""
    if motor_escolhido == "edge":
        voz_escolhida_name = lista_vozes_desc[escolha_voz_idx - 1]
    else:
        desc_escolhida = lista_vozes_desc[escolha_voz_idx - 1]
        voz_escolhida_name = VOZES_GEMINI_PT_BR[desc_escolhida]

    texto_para_converter = ler_arquivo_texto(caminho_txt_processado)
    if not texto_para_converter.strip() or CANCELAR_PROCESSAMENTO:
        print("❌ Arquivo de texto processado vazio."); return

    # --- LÓGICA DE LIMITE E CONCORRÊNCIA (ATUALIZADA) ---
    limite_chunk = 0
    lote_maximo_concorrente = 0
    if motor_escolhido == "edge":
        limite_chunk = LIMITE_CARACTERES_CHUNK_TTS_EDGE
        lote_maximo_concorrente = LOTE_MAXIMO_TAREFAS_EDGE
    else: # gemini
        limite_chunk = LIMITE_CARACTERES_CHUNK_TTS_GEMINI
        lote_maximo_concorrente = LOTE_MAXIMO_TAREFAS_GEMINI
    
    print(f"\n⏳ Dividindo texto para TTS (motor: {motor_escolhido}, limite: {limite_chunk} caracteres)...")
    partes_texto = dividir_texto_para_tts(texto_para_converter, limite_chunk)
    # --- FIM DA ATUALIZAÇÃO ---
    
    total_partes = len(partes_texto)
    if total_partes == 0:
        print("❌ Nenhuma parte de texto para converter após divisão."); return

    print(f"📊 Texto dividido em {total_partes} parte(s) para TTS.")
    print("   Pressione CTRL+C para tentar cancelar a qualquer momento.")

    path_txt_obj = Path(caminho_txt_processado)
    nome_base_audio = limpar_nome_arquivo(path_txt_obj.stem.replace("_formatado", ""))
    dir_saida_audio = path_txt_obj.parent / f"{nome_base_audio}_AUDIO_TTS_{motor_escolhido.upper()}"
    dir_saida_audio.mkdir(parents=True, exist_ok=True)
    arquivos_mp3_temporarios_nomes = [str(dir_saida_audio / f"temp_{nome_base_audio}_{i+1:04d}.mp3") for i in range(total_partes)]

    print("\n🎙️ Iniciando conversão TTS das partes...")

    resultados_conversao = [False] * total_partes
    arquivos_mp3_sucesso = []
    
    semaphore_api_calls = asyncio.Semaphore(lote_maximo_concorrente)
    tarefas_gerais_tts = []

    async with aiohttp.ClientSession() as session:
        async def converter_com_semaforo(p_txt, voz, c_temp, idx_original, total, motor, key, http_session):
            async with semaphore_api_calls:
                if CANCELAR_PROCESSAMENTO: return (idx_original, False)
                
                if motor == "edge":
                    sucesso = await _converter_chunk_tts_edge(
                        p_txt, voz, c_temp, idx_original + 1, total
                    )
                else:
                    sucesso = await _converter_chunk_tts_gemini(
                        p_txt, voz, c_temp, idx_original + 1, total, key, http_session
                    )
                return (idx_original, sucesso)
        
        for idx_global_parte in range(total_partes):
            if CANCELAR_PROCESSAMENTO: break
            
            tarefa = asyncio.create_task(
                converter_com_semaforo(
                    partes_texto[idx_global_parte], 
                    voz_escolhida_name, 
                    arquivos_mp3_temporarios_nomes[idx_global_parte], 
                    idx_global_parte, 
                    total_partes,
                    motor_escolhido,
                    gemini_api_key_local,
                    session
                )
            )
            tarefas_gerais_tts.append(tarefa)
        
        if CANCELAR_PROCESSAMENTO:
            print("🚫 Criação de tarefas TTS interrompida.")
            for t in tarefas_gerais_tts: t.cancel()
        
        partes_concluidas = 0; partes_com_falha = 0
        tempo_ultima_atualizacao_progresso = time.monotonic()

        def imprimir_progresso_tts():
            porcentagem = (partes_concluidas / total_partes) * 100 if total_partes > 0 else 0
            sys.stdout.write(f"\r   Progresso TTS ({motor_escolhido}): {partes_concluidas}/{total_partes} ({porcentagem:.1f}%) | Falhas: {partes_com_falha}   ")
            sys.stdout.flush()

        if tarefas_gerais_tts:
            print(f"📦 Processando {len(tarefas_gerais_tts)} tarefas com concorrência de {lote_maximo_concorrente}...")
            imprimir_progresso_tts()

            for future_task in asyncio.as_completed(tarefas_gerais_tts):
                if CANCELAR_PROCESSAMENTO:
                    for t_restante in tarefas_gerais_tts:
                        if not t_restante.done(): t_restante.cancel()
                    break
                try:
                    idx_original, sucesso_tarefa = await future_task
                    
                    if sucesso_tarefa:
                        resultados_conversao[idx_original] = True
                    else:
                        resultados_conversao[idx_original] = False
                        # --- MODIFICAÇÃO (Gemini-User): 
                        # 'partes_com_falha' agora só incrementa se a tarefa
                        # falhar por um erro fatal (ex: API key errada)
                        # Como agora tentamos para sempre, 'partes_com_falha'
                        # não será incrementado em falhas de rede.
                        # (Nota: A lógica de falha fatal no Gemini já retorna False)
                        if not sucesso_tarefa:
                            partes_com_falha += 1
                    
                except asyncio.CancelledError:
                    pass
                except Exception as e_task:
                    print(f"\n   ⚠️ Erro inesperado ao processar tarefa: {e_task}")
                    partes_com_falha +=1 

                partes_concluidas += 1
                
                agora = time.monotonic()
                if agora - tempo_ultima_atualizacao_progresso > 0.3 or partes_concluidas == total_partes:
                    imprimir_progresso_tts()
                    tempo_ultima_atualizacao_progresso = agora
            
            sys.stdout.write("\n")
    
    print("\n🔍 Verificando arquivos gerados...")
    for i in range(total_partes):
        caminho_temp = arquivos_mp3_temporarios_nomes[i]
        if resultados_conversao[i] and Path(caminho_temp).exists() and Path(caminho_temp).stat().st_size > 200:
            if caminho_temp not in arquivos_mp3_sucesso:
                arquivos_mp3_sucesso.append(caminho_temp)
        else:
            resultados_conversao[i] = False

    if CANCELAR_PROCESSAMENTO:
        print("🚫 Processo de TTS interrompido.")
    
    if arquivos_mp3_sucesso:
        arquivo_final_mp3 = dir_saida_audio / f"{nome_base_audio}_COMPLETO.mp3"
        print(f"\n🔄 Unificando {len(arquivos_mp3_sucesso)} arquivos de áudio...")
        
        if unificar_arquivos_audio_ffmpeg(arquivos_mp3_sucesso, str(arquivo_final_mp3)):
            print(f"🎉 Conversão TTS ({motor_escolhido}) concluída!")
            print(f"   Áudio final: {arquivo_final_mp3}")
            print("🧹 Limpando temporários TTS unificados...")
            for temp_f_success in arquivos_mp3_sucesso:
                Path(temp_f_success).unlink(missing_ok=True)
            
            if not CANCELAR_PROCESSAMENTO and await obter_confirmacao("Deseja aplicar melhorias (acelerar, converter para MP4) ao áudio gerado?"):
                await _processar_melhoria_de_audio_video(str(arquivo_final_mp3))
        else:
            print("❌ Falha ao unificar os áudios. Os arquivos parciais permanecem.")
    elif not CANCELAR_PROCESSAMENTO:
        print("❌ Nenhum arquivo de áudio foi gerado com sucesso.")

    for i in range(total_partes):
        if not resultados_conversao[i]:
            Path(arquivos_mp3_temporarios_nomes[i]).unlink(missing_ok=True)

    if not CANCELAR_PROCESSAMENTO:
        await aioconsole.ainput("\nPressione ENTER para voltar ao menu...")


async def testar_vozes_tts():
    """Permite ao usuário ouvir amostras das vozes (Edge ou Gemini)."""
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False
    
    sistema = detectar_sistema()
    pasta_testes = None
    if sistema['termux'] or sistema['android']:
        pasta_testes = Path("/storage/emulated/0/Download/TTS_Testes_Voz")
        if not pasta_testes.parent.exists():
             pasta_testes = Path.home() / "TTS_Testes_Voz"
    else:
        pasta_testes = Path.home() / "Downloads" / "TTS_Testes_Voz"

    print(f"   Áudios de teste serão salvos em: {pasta_testes}")
    if sistema['termux']:
        print("   Lembre-se: No Termux, execute 'termux-setup-storage' para dar permissão.")
    try:
        pasta_testes.mkdir(parents=True, exist_ok=True)
    except OSError as e_mkdir:
         print(f"❌ Erro ao criar/acessar a pasta de testes: {e_mkdir}"); await asyncio.sleep(3); return

    limpar_tela()
    print("\n--- TESTAR VOZES: SELECIONAR MOTOR ---")
    print("1. Edge TTS")
    print("2. Gemini TTS (Requer API Key)")
    print("3. Voltar")
    escolha_motor_idx = await obter_opcao_numerica("Escolha o motor", 3)
    
    if escolha_motor_idx == 3: return
    motor_escolhido = "edge" if escolha_motor_idx == 1 else "gemini"

    gemini_api_key_local = ""
    if motor_escolhido == "gemini":
        if not GEMINI_API_KEY_ATUAL:
            print("\n❌ API Key do Gemini não está configurada!")
            print("   Use a 'Opção 8' no menu principal para configurar.")
            await aioconsole.ainput("Pressione ENTER para voltar..."); return
        gemini_api_key_local = GEMINI_API_KEY_ATUAL
        print("✅ API Key do Gemini carregada para o teste.")

    while True:
        if CANCELAR_PROCESSAMENTO: break
        
        opcoes_voz = {}
        lista_vozes_desc = []
        
        if motor_escolhido == "edge":
            lista_vozes_desc = VOZES_PT_BR
            opcoes_voz = {str(i+1): voz for i, voz in enumerate(VOZES_PT_BR)}
        else:
            lista_vozes_desc = list(VOZES_GEMINI_PT_BR.keys())
            opcoes_voz = {str(i+1): desc for i, desc in enumerate(lista_vozes_desc)}
        
        opcoes_voz[str(len(opcoes_voz)+1)] = "Voltar"
        
        escolha_idx = await exibir_banner_e_menu(f"TESTAR VOZES ({motor_escolhido.upper()})", opcoes_voz)
        
        if escolha_idx == len(opcoes_voz)+1 or CANCELAR_PROCESSAMENTO: break
        
        voz_selecionada_name = ""
        desc_voz = ""
        if motor_escolhido == "edge":
            voz_selecionada_name = lista_vozes_desc[escolha_idx - 1]
            desc_voz = voz_selecionada_name
        else:
            desc_voz = lista_vozes_desc[escolha_idx - 1]
            voz_selecionada_name = VOZES_GEMINI_PT_BR[desc_voz]

        texto_exemplo = "Olá! Esta é uma demonstração da minha voz para você avaliar."
        print(f"\n🎙️ Testando voz: {desc_voz}...")
        
        nome_arquivo_teste = limpar_nome_arquivo(f"teste_{motor_escolhido}_{voz_selecionada_name}.mp3")
        caminho_arquivo_teste = pasta_testes / nome_arquivo_teste
        
        try:
            sucesso = False
            async with aiohttp.ClientSession() as session:
                if motor_escolhido == "edge":
                    sucesso = await _converter_chunk_tts_edge(
                        texto_exemplo, voz_selecionada_name, str(caminho_arquivo_teste), 1, 1
                    )
                else:
                    sucesso = await _converter_chunk_tts_gemini(
                        texto_exemplo, voz_selecionada_name, str(caminho_arquivo_teste), 1, 1, 
                        gemini_api_key_local, session
                    )
            
            if sucesso:
                if caminho_arquivo_teste.exists() and caminho_arquivo_teste.stat().st_size > 50:
                     print(f"✅ Áudio de teste salvo: {caminho_arquivo_teste}")
                     if await obter_confirmacao("Ouvir áudio de teste?", default_yes=True):
                         try:
                             if sistema['windows']: os.startfile(caminho_arquivo_teste)
                             elif sistema['termux'] and shutil.which("termux-media-player"): subprocess.run(['termux-media-player', 'play', str(caminho_arquivo_teste)], timeout=15)
                             elif sistema['macos']: subprocess.run(['open', str(caminho_arquivo_teste)], check=True)
                             elif sistema['linux']: subprocess.run(['xdg-open', str(caminho_arquivo_teste)], check=True)
                             else: print("   Não foi possível reproduzir automaticamente.")
                         except Exception as e_play: print(f"⚠️ Não reproduziu: {e_play}")
                else:
                     print(f"❌ Erro: Conversão para {desc_voz} falhou (arquivo final inválido).")
                     caminho_arquivo_teste.unlink(missing_ok=True)
            else: 
                print(f"❌ Falha ao gerar áudio de teste para {desc_voz} (ver logs acima).")
        
        except asyncio.CancelledError: 
            print("\n🚫 Teste de voz cancelado.")
            caminho_arquivo_teste.unlink(missing_ok=True); break
        except Exception as e_test:
             print(f"\n❌ Erro inesperado durante o teste da voz: {e_test}")
             caminho_arquivo_teste.unlink(missing_ok=True)

        if not await obter_confirmacao("Testar outra voz?", default_yes=True):
            break

async def _processar_melhoria_de_audio_video(caminho_arquivo_entrada: str):
    """Orquestra o processo de melhoria: acelerar, converter formato e dividir."""
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False
    
    path_entrada_obj = Path(caminho_arquivo_entrada)
    if not path_entrada_obj.exists():
        print(f"❌ Arquivo de entrada não encontrado: {caminho_arquivo_entrada}"); return

    print(f"\n⚡ Melhorando arquivo: {path_entrada_obj.name}")

    velocidade = 1.0 
    while True:
        try:
            velocidade_str = await aioconsole.ainput("Informe a velocidade (ex: 1.5, padrão 1.0): ")
            if not velocidade_str.strip(): break
            velocidade = float(velocidade_str)
            if 0.25 <= velocidade <= 5.0: break
            else: print("⚠️ Velocidade fora do intervalo (0.25x - 5.0x).")
        except ValueError: print("⚠️ Entrada inválida.")
        except asyncio.CancelledError: return
    if CANCELAR_PROCESSAMENTO: return

    is_video_input = path_entrada_obj.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.webm']
    formato_saida = ""
    if is_video_input:
        formato_saida = ".mp4" if await obter_confirmacao("Manter vídeo (MP4)? (S=vídeo, N=áudio MP3)", True) else ".mp3"
    else:
        formato_saida = ".mp4" if await obter_confirmacao("Gerar vídeo com tela preta (MP4)? (S=vídeo, N=áudio MP3)", False) else ".mp3"
    if CANCELAR_PROCESSAMENTO: return

    resolucao_video_saida_str = "" 
    if formato_saida == ".mp4":
        resolucao_video_saida_str = RESOLUCOES_VIDEO['1'][0]
        desc_res_fixa = f"{RESOLUCOES_VIDEO['1'][1]} ({RESOLUCOES_VIDEO['1'][0]})"
        print(f"ℹ️  Gerando MP4 com resolução padrão: {desc_res_fixa}")
    if CANCELAR_PROCESSAMENTO: return

    duracao_total_seg = obter_duracao_midia(str(path_entrada_obj))
    if duracao_total_seg == 0 and formato_saida == ".mp4":
        print("❌ Não foi possível obter a duração do arquivo. Não é possível criar vídeo MP4."); return

    dividir = False; duracao_max_parte = LIMITE_SEGUNDOS_DIVISAO
    if duracao_total_seg > duracao_max_parte:
        if await obter_confirmacao(f"O arquivo tem {duracao_total_seg/3600:.2f}h. Dividir em partes de até {duracao_max_parte/3600:.0f}h?", True):
            dividir = True
            if await obter_confirmacao("Definir tamanho personalizado por parte (em horas)?", False):
                while True:
                    try:
                        horas_str = await aioconsole.ainput(f"Horas por parte (ex: 2.5, máx {LIMITE_SEGUNDOS_DIVISAO/3600:.0f}): ")
                        horas_parte = float(horas_str)
                        if 0.5 <= horas_parte <= LIMITE_SEGUNDOS_DIVISAO/3600: 
                            duracao_max_parte = horas_parte * 3600
                            break
                        else: print(f"⚠️ Horas devem estar entre 0.5 e {LIMITE_SEGUNDOS_DIVISAO/3600:.0f}.")
                    except ValueError: print("⚠️ Número inválido.")
                    except asyncio.CancelledError: return
    if CANCELAR_PROCESSAMENTO: return

    nome_proc = limpar_nome_arquivo(f"{path_entrada_obj.stem}_veloc{str(velocidade).replace('.','_')}")
    dir_out = path_entrada_obj.parent / f"{nome_proc}_PROCESSADO"; dir_out.mkdir(parents=True, exist_ok=True)
    tmp_acel = dir_out / f"temp_acel{path_entrada_obj.suffix}"
    entrada_prox = ""; dur_acel = 0.0

    if velocidade != 1.0:
        if not acelerar_midia_ffmpeg(str(path_entrada_obj), str(tmp_acel), velocidade, is_video_input):
            print("❌ Falha acelerar."); tmp_acel.unlink(missing_ok=True); return
        entrada_prox = str(tmp_acel)
        dur_acel = obter_duracao_midia(entrada_prox)
        if dur_acel == 0 and formato_saida == ".mp4": 
            print("❌ Duração não obtida pós aceleração. Abortando MP4."); tmp_acel.unlink(missing_ok=True); return
    else: 
        entrada_prox = str(path_entrada_obj); dur_acel = duracao_total_seg
    
    if CANCELAR_PROCESSAMENTO: 
        if Path(entrada_prox).resolve() != path_entrada_obj.resolve(): Path(entrada_prox).unlink(missing_ok=True)
        return

    entrada_div = entrada_prox; tmp_vid_gerado = None
    if formato_saida == ".mp4" and not is_video_input:
        tmp_vid_gerado = dir_out / "temp_video_from_audio.mp4"
        if not criar_video_com_audio_ffmpeg(entrada_prox, str(tmp_vid_gerado), dur_acel, resolucao_video_saida_str):
            print("❌ Falha criar vídeo."); 
            if Path(entrada_prox).resolve() != path_entrada_obj.resolve(): Path(entrada_prox).unlink(missing_ok=True) 
            tmp_vid_gerado.unlink(missing_ok=True); return
        
        entrada_div = str(tmp_vid_gerado)
        if Path(entrada_prox).resolve() != path_entrada_obj.resolve():
             Path(entrada_prox).unlink(missing_ok=True)
             
    elif formato_saida == ".mp3" and is_video_input:
        tmp_audio_extraido = dir_out / "temp_audio_from_video.mp3"
        print("Extracting audio from video...")
        if not _executar_ffmpeg_comando(
            [FFMPEG_BIN,'-y','-i', entrada_prox,'-vn','-q:a','2', str(tmp_audio_extraido)], 
            "Extraindo MP3", dur_acel
        ):
            print(f"❌ Falha ao extrair áudio")
            if Path(entrada_prox).resolve() != path_entrada_obj.resolve(): Path(entrada_prox).unlink(missing_ok=True)
            tmp_audio_extraido.unlink(missing_ok=True); return

        if Path(entrada_prox).resolve() != path_entrada_obj.resolve():
             Path(entrada_prox).unlink(missing_ok=True)
        entrada_div = str(tmp_audio_extraido)

    if CANCELAR_PROCESSAMENTO:
        if Path(entrada_div).exists() and Path(entrada_div).resolve() != path_entrada_obj.resolve():
            Path(entrada_div).unlink(missing_ok=True)
        return
    
    nome_base_final = dir_out / nome_proc; arquivos_finais = []
    if dividir:
        arquivos_finais = dividir_midia_ffmpeg(entrada_div, dur_acel, duracao_max_parte, str(nome_base_final), formato_saida)
    else:
        arq_final_unico = f"{nome_base_final}{formato_saida}"
        try:
            p_entrada_div = Path(entrada_div)
            if p_entrada_div.exists(): 
                shutil.move(entrada_div, arq_final_unico)
                print(f"✅ Arquivo final salvo: {arq_final_unico}")
                arquivos_finais.append(arq_final_unico)
            else:
                 print(f"⚠️ Arquivo de processamento '{entrada_div}' não encontrado para finalização.")
        except Exception as e_final:
            print(f"❌ Erro ao finalizar arquivo único: {e_final}")

    p_entrada_div_obj = Path(entrada_div)
    if p_entrada_div_obj.resolve() != path_entrada_obj.resolve() and p_entrada_div_obj.exists():
        p_entrada_div_obj.unlink(missing_ok=True)
    
    if arquivos_finais: 
        print("\n🎉 Processo de melhoria concluído!")
        for f_gerado in arquivos_finais: print(f"   -> {f_gerado}")
    else: 
        print("❌ Nenhum arquivo foi gerado no processo de melhoria.")
    
    await aioconsole.ainput("\nPressione ENTER para voltar ao menu...")

async def menu_melhorar_audio_video():
    """Menu para acessar a função de melhoria."""
    while True:
        caminho_arquivo = await _selecionar_arquivo_para_processamento(['.mp3', '.wav', '.m4a', '.ogg', '.opus', '.flac', '.mp4', '.mkv', '.avi', '.mov', '.webm'])
        if not caminho_arquivo or CANCELAR_PROCESSAMENTO: break
        await _processar_melhoria_de_audio_video(caminho_arquivo)
        if CANCELAR_PROCESSAMENTO: break
        if not await obter_confirmacao("Melhorar outro arquivo?", default_yes=False): break

async def menu_converter_mp3_para_mp4():
    """Menu para converter MP3 para MP4 (tela preta, 360p)."""
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False

    resolucao_fixa_str = RESOLUCOES_VIDEO['1'][0]
    resolucao_fixa_desc = RESOLUCOES_VIDEO['1'][1]

    while True:
        caminho_mp3 = await _selecionar_arquivo_para_processamento(['.mp3'])
        if not caminho_mp3 or CANCELAR_PROCESSAMENTO: break

        path_mp3_obj = Path(caminho_mp3)
        duracao_mp3 = obter_duracao_midia(caminho_mp3)
        if duracao_mp3 <= 0:
            print("❌ Não foi possível obter a duração do MP3 ou é inválida.");
            await asyncio.sleep(2); continue

        print(f"\nℹ️  Convertendo MP3 para MP4 com resolução fixa: {resolucao_fixa_desc} ({resolucao_fixa_str}).")
        if CANCELAR_PROCESSAMENTO: break

        nome_video_saida = limpar_nome_arquivo(f"{path_mp3_obj.stem}_VIDEO_{resolucao_fixa_desc}.mp4")
        caminho_video_saida = path_mp3_obj.with_name(nome_video_saida)

        if criar_video_com_audio_ffmpeg(caminho_mp3, str(caminho_video_saida), duracao_mp3, resolucao_fixa_str):
            print(f"✅ Vídeo gerado: {caminho_video_saida}")
        else:
            print(f"❌ Falha ao gerar vídeo a partir de {path_mp3_obj.name}")

        if not await obter_confirmacao("Converter outro MP3 para MP4?", default_yes=False):
            break
        if CANCELAR_PROCESSAMENTO: break

    if not CANCELAR_PROCESSAMENTO:
        await aioconsole.ainput("\nPressione ENTER para voltar ao menu...")

async def menu_dividir_video_existente():
    """Menu para dividir arquivos de vídeo longos sem reencodar."""
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False
    while True:
        caminho_video_entrada = await _selecionar_arquivo_para_processamento(['.mp4', '.mkv', '.avi', '.mov', '.webm'])
        if not caminho_video_entrada or CANCELAR_PROCESSAMENTO: break
        
        path_video_obj = Path(caminho_video_entrada)
        duracao_total_seg = obter_duracao_midia(str(path_video_obj))
        
        if duracao_total_seg == 0:
            print("❌ Não foi possível obter a duração do vídeo."); await asyncio.sleep(2); continue
            
        if duracao_total_seg <= LIMITE_SEGUNDOS_DIVISAO:
            print(f"ℹ️ Vídeo '{path_video_obj.name}' ({duracao_total_seg/3600:.2f}h) não precisa ser dividido (limite {LIMITE_SEGUNDOS_DIVISAO/3600:.1f}h).");
            if not await obter_confirmacao("Selecionar outro vídeo?", default_yes=False): break
            continue
            
        print(f"Vídeo '{path_video_obj.name}' tem {duracao_total_seg/3600:.2f}h.")
        duracao_max_parte = LIMITE_SEGUNDOS_DIVISAO
        
        if await obter_confirmacao("Tamanho personalizado por parte (horas)?", default_yes=False):
            while True:
                try:
                    horas_str = await aioconsole.ainput(f"Horas/parte (0.5-{LIMITE_SEGUNDOS_DIVISAO/3600:.0f}): ")
                    horas_parte = float(horas_str)
                    if 0.5 <= horas_parte <= LIMITE_SEGUNDOS_DIVISAO/3600:
                        duracao_max_parte = horas_parte * 3600; break
                    else: print(f"⚠️ Horas devem estar entre 0.5 e {LIMITE_SEGUNDOS_DIVISAO/3600:.0f}.")
                except ValueError: print("⚠️ Inválido.")
                except asyncio.CancelledError: return
        if CANCELAR_PROCESSAMENTO: break
        
        nome_base_saida = path_video_obj.parent / limpar_nome_arquivo(f"{path_video_obj.stem}_dividido")
        arquivos_gerados = dividir_midia_ffmpeg(str(path_video_obj), duracao_total_seg, duracao_max_parte, str(nome_base_saida), path_video_obj.suffix)
        
        if arquivos_gerados: print("\n🎉 Divisão concluída!"); [print(f"   -> {f}") for f in arquivos_gerados]
        else: print(f"❌ Falha ao dividir {path_video_obj.name} ou cancelado.")
            
        if not await obter_confirmacao("Dividir outro vídeo?", default_yes=False): break
        if CANCELAR_PROCESSAMENTO: break
        
    await aioconsole.ainput("\nPressione ENTER para voltar...")

# --- FUNÇÃO ATUALIZADA (SALVA EM ARQUIVO) ---
async def menu_configurar_api_key():
    """Permite ao usuário inserir ou atualizar a API Key do Gemini para a sessão E SALVAR."""
    global GEMINI_API_KEY_ATUAL
    limpar_tela()
    print("╔════════════════════════════════════════════╗")
    print("║           CONFIGURAR API KEY (GEMINI)        ║")
    print("╚════════════════════════════════════════════╝")
    
    if GEMINI_API_KEY_ATUAL:
        key_display = f"{GEMINI_API_KEY_ATUAL[:4]}...{GEMINI_API_KEY_ATUAL[-4:]}"
        print(f"\nℹ️ API Key atual (carregada do arquivo ou sessão): {key_display}")
    else:
        print("\n⚠️ Nenhuma API Key do Gemini configurada.")

    print("\nDigite sua nova API Key (ou deixe em branco para manter a atual):")
    
    try:
        nova_key_raw = await aioconsole.ainput("Nova API Key: ")
        nova_key = nova_key_raw.strip()
        
        if nova_key:
            GEMINI_API_KEY_ATUAL = nova_key
            save_api_key_to_config(nova_key) # <<-- SALVA A CHAVE
            print("\n✅ API Key atualizada e salva para futuras sessões!")
        elif not GEMINI_API_KEY_ATUAL:
            print("\n❌ Nenhuma chave inserida. A API Key continua vazia.")
        else:
            print("\nℹ️ Nenhuma chave inserida. A chave anterior foi mantida.")
            
    except asyncio.CancelledError:
        print("\n🚫 Configuração cancelada.")

    await aioconsole.ainput("\nPressione ENTER para voltar ao menu...")


async def exibir_ajuda():
    """Exibe o guia de uso do script."""
    limpar_tela()
    print("""
╔════════════════════════════════════════════╗
║                 GUIA DE USO                ║
╚════════════════════════════════════════════╝

1.  CONVERTER TEXTO PARA ÁUDIO (TTS):
    - Selecione um arquivo .txt, .pdf ou .epub.
    - O script tentará formatar o texto (capítulos, números, etc.).
    - Escolha o motor TTS (Edge ou Gemini).
    - IMPORTANTE (Gemini): Você DEVE configurar sua API Key
      usando a 'Opção 8' no menu principal (ou via variável de ambiente).
    - Escolha uma voz da lista.
    - O áudio será salvo em uma subpasta (ex: NOME_AUDIO_TTS_GEMINI).

2.  TESTAR VOZES TTS (Edge ou Gemini):
    - Escolha qual motor (Edge ou Gemini) você quer testar.
    - Ouça amostras das vozes disponíveis.

3.  MELHORAR ÁUDIO/VÍDEO (Velocidade, Formato):
    - Selecione um arquivo de áudio ou vídeo.
    - Ajuste a velocidade de reprodução (ex: 1.5 para 1.5x).
    - Escolha o formato de saída: MP3 (áudio) ou MP4 (vídeo).

4.  DIVIDIR VÍDEO LONGO:
    - Selecione um arquivo de vídeo (MP4, MKV, etc.).
    - Divide o vídeo em partes menores sem recompressão (rápido).

5.  CONVERTER MP3 PARA MP4 (Tela Preta):
    - Selecione um arquivo MP3.
    - Gera um vídeo MP4 com tela preta e o áudio do MP3 (360p).

6.  ATUALIZAR SCRIPT:
    - Baixa a versão mais recente do script do GitHub.

7.  AJUDA:
    - Exibe este guia de uso.

8.  CONFIGURAR API KEY (Gemini):
    - Permite que você digite sua API Key do Gemini.
    - NOVO: A chave digitada aqui agora é SALVA para futuras sessões.

0.  SAIR:
    - Encerra o script.
    """)
    await aioconsole.ainput("Pressione ENTER para voltar ao menu...")

async def atualizar_script():
    """Baixa a versão mais recente do script do GitHub."""
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False
    limpar_tela(); print("🔄 ATUALIZAÇÃO DO SCRIPT")
    
    url_script = "https://raw.githubusercontent.com/JonJonesBR/Conversor_TTS/main/Conversor_TTS_com_MP4_09.04.2025.py"
    
    if not await obter_confirmacao(f"Baixar versão mais recente de '{url_script}'?"):
        print("❌ Cancelado."); await asyncio.sleep(1); return

    print("\n🔄 Baixando...");
    script_atual_path = Path(__file__).resolve()
    script_backup_path = script_atual_path.with_suffix(script_atual_path.suffix + f".backup_{int(time.time())}")
    
    try:
        shutil.copy2(script_atual_path, script_backup_path)
        print(f"✅ Backup salvo como: {script_backup_path.name}")
    except Exception as e_backup:
        print(f"⚠️ Não foi possível criar backup: {e_backup}");
        if not await obter_confirmacao("Continuar sem backup?", default_yes=False): return
        
    try:
        print(f"Baixando de: {url_script}");
        response = requests.get(url_script, timeout=30)
        response.raise_for_status()
        
        with open(script_atual_path, 'wb') as f:
            f.write(response.content)
            
        print("✅ Script atualizado com sucesso! Reiniciando...");
        await aioconsole.ainput("Pressione ENTER para reiniciar...")
        
        os.execl(sys.executable, sys.executable, str(script_atual_path), *sys.argv[1:])
        
    except requests.exceptions.RequestException as e_req:
        print(f"\n❌ Erro de rede ao baixar atualização: {e_req}")
    except Exception as e_update:
        print(f"\n❌ Erro inesperado ao salvar atualização: {e_update}")
        
    if script_backup_path.exists():
        print("\n🔄 Atualização falhou. Restaurando backup...");
        try:
            shutil.copy2(script_backup_path, script_atual_path)
            print("✅ Backup restaurado!");
            script_backup_path.unlink(missing_ok=True)
        except Exception as e_restore:
            print(f"❌ Erro crítico ao restaurar backup: {e_restore}.")
            print(f"   Seu backup está em: {script_backup_path}")
            
    await aioconsole.ainput("\nPressione ENTER para continuar...")

# ================== FUNÇÃO MAIN E LOOP PRINCIPAL ==================

async def main_loop():
    """Loop principal assíncrono do menu."""
    global CANCELAR_PROCESSAMENTO
    detectar_sistema()
    verificar_dependencias_essenciais()
    
    opcoes_principais = {
        '1': "🚀 CONVERTER TEXTO PARA ÁUDIO (TTS)",
        '2': "🎙️ TESTAR VOZES TTS (Edge ou Gemini)",
        '3': "⚡ MELHORAR ÁUDIO/VÍDEO (Velocidade, Formato)",
        '4': "🎞️ DIVIDIR VÍDEO LONGO",
        '5': "🎬 CONVERTER MP3 PARA MP4 (Tela Preta)",
        '6': "🔄 ATUALIZAR SCRIPT",
        '7': "❓ AJUDA",
        '8': "🔑 CONFIGURAR API KEY (Gemini)",
        '0': "🚪 SAIR"
    }
    
    while True:
        CANCELAR_PROCESSAMENTO = False
        signal.signal(signal.SIGINT, handler_sinal)
        
        try:
            escolha = await exibir_banner_e_menu("MENU PRINCIPAL", opcoes_principais)
            
            if escolha == 1: await iniciar_conversao_tts()
            elif escolha == 2: await testar_vozes_tts()
            elif escolha == 3: await menu_melhorar_audio_video()
            elif escolha == 4: await menu_dividir_video_existente()
            elif escolha == 5: await menu_converter_mp3_para_mp4()
            elif escolha == 6: await atualizar_script()
            elif escolha == 7: await exibir_ajuda()
            elif escolha == 8: await menu_configurar_api_key()
            elif escolha == 0:
                print("\n👋 Obrigado por usar!"); break
                
        except asyncio.CancelledError:
            print("\n🚫 Operação cancelada. Voltando ao menu...")
            CANCELAR_PROCESSAMENTO = True; await asyncio.sleep(0.1)
        except Exception as e_main:
            print(f"\n❌ Erro Inesperado no loop principal: {e_main}")
            import traceback; traceback.print_exc()
            await aioconsole.ainput("Pressione ENTER para tentar continuar...")

if __name__ == "__main__":
    if Path(__file__).name == "code.py":
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERRO DE NOME DE ARQUIVO: Renomeie este script (ex: 'conversor_tts.py') !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1)
        
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n\n⚠️ Programa interrompido (KeyboardInterrupt).")
    except Exception as e_global:
        print(f"\n❌ Erro global não tratado: {str(e_global)}")
        import traceback; traceback.print_exc()
    finally:
        print("🔚 Script finalizado.")

