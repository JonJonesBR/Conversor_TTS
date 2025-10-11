#!/usr/bin/env python3
import os
import sys
import subprocess
import asyncio
import re
import signal
from pathlib import Path
# import select # Unused, consider removing
import platform
import zipfile
import shutil
import time
import unicodedata
from math import ceil

# Attempt to import necessary modules, install if missing
try:
    import edge_tts
except ModuleNotFoundError:
    print("⚠️ Módulo 'edge-tts' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "edge-tts>=6.1.5"])
    import site
    if site.getusersitepackages() not in sys.path: sys.path.append(site.getusersitepackages())
    import edge_tts

try:
    from bs4 import BeautifulSoup
except ModuleNotFoundError:
    print("⚠️ Módulo 'beautifulsoup4' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "beautifulsoup4"])
    import site
    if site.getusersitepackages() not in sys.path: sys.path.append(site.getusersitepackages())
    from bs4 import BeautifulSoup

try:
    import html2text
except ModuleNotFoundError:
    print("⚠️ Módulo 'html2text' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "html2text"])
    import site
    if site.getusersitepackages() not in sys.path: sys.path.append(site.getusersitepackages())
    import html2text

try:
    from tqdm import tqdm
except ModuleNotFoundError:
    print("⚠️ Módulo 'tqdm' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "tqdm"])
    try: # Add user site packages to path for immediate import
        import site
        if site.getusersitepackages() not in sys.path:
            sys.path.append(site.getusersitepackages())
    except Exception as e:
        print(f"❌ Erro ao adicionar o diretório de pacotes do usuário: {e}")
    from tqdm import tqdm

try:
    import requests
except ModuleNotFoundError:
    print("⚠️ Módulo 'requests' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "requests"])
    import site
    if site.getusersitepackages() not in sys.path: sys.path.append(site.getusersitepackages())
    import requests

try:
    import aioconsole
except ModuleNotFoundError:
    print("⚠️ Módulo 'aioconsole' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "aioconsole>=0.6.0"])
    import site
    if site.getusersitepackages() not in sys.path: sys.path.append(site.getusersitepackages())
    import aioconsole

try:
    import chardet
except ModuleNotFoundError:
    print("⚠️ Módulo 'chardet' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "chardet>=5.0.0"])
    import site
    if site.getusersitepackages() not in sys.path: sys.path.append(site.getusersitepackages())
    import chardet

try:
    from num2words import num2words
except ImportError:
    print("⚠️ Módulo 'num2words' não encontrado. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "num2words>=0.5.12"])
    import site
    if site.getusersitepackages() not in sys.path: sys.path.append(site.getusersitepackages())
    from num2words import num2words

try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0 # for consistent results
    LANG_DETECT_AVAILABLE = True
except ImportError:
    print("\n⚠️ O módulo langdetect não está instalado. Instale com: pip install langdetect")
    LANG_DETECT_AVAILABLE = False


# ================== CONFIGURAÇÕES GLOBAIS ==================
VOZES_PT_BR = [
    "pt-BR-ThalitaMultilingualNeural",  # Voz padrão
    "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural"
]
ENCODINGS_TENTATIVAS = ['utf-8', 'utf-16', 'iso-8859-1', 'cp1252']
# BUFFER_IO = 32768 # Unused
MAX_TTS_TENTATIVAS = 3
CANCELAR_PROCESSAMENTO = False
FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"
LIMITE_SEGUNDOS_DIVISAO = 43200  # 12 horas para divisão de arquivos longos

RESOLUCOES_VIDEO = {
    '1': ('640x360', '360p'),
    '2': ('854x480', '480p'),
    '3': ('1280x720', '720p (HD - maior processamento e arquivo)')
}
SISTEMA_OPERACIONAL_INFO = {} # To store detected OS info globally

# ================== FUNÇÕES DE TEXTO MELHORADAS E CONSOLIDADAS ==================

ABREVIACOES_EXPANSAO = {
    r'\bDr\.(?=\s)': 'Doutor', r'\bD\.(?=\s)': 'Dona', r'\bDra\.(?=\s)': 'Doutora',
    r'\bSr\.(?=\s)': 'Senhor', r'\bSra\.(?=\s)': 'Senhora', r'\bSrta\.(?=\s)': 'Senhorita',
    r'\bProf\.(?=\s)': 'Professor', r'\bProfa\.(?=\s)': 'Professora',
    r'\bEng\.(?=\s)': 'Engenheiro', r'\bEngª\.(?=\s)': 'Engenheira',
    r'\bAdm\.(?=\s)': 'Administrador', r'\bAdv\.(?=\s)': 'Advogado',
    r'\bExmo\.(?=\s)': 'Excelentíssimo', r'\bExma\.(?=\s)': 'Excelentíssima',
    r'\bV\.Exa\.(?=\s)': 'Vossa Excelência', r'\bV\.Sa\.(?=\s)': 'Vossa Senhoria',
    r'\bAv\.(?=\s)': 'Avenida', r'\bR\.(?=\s)': 'Rua', r'\bKm\.(?=\s)': 'Quilômetro',
    r'\betc\.(?=\s|\.)': 'etcétera', # Handle etc. at end of sentence
    r'\bRef\.(?=\s)': 'Referência',
    r'\bP[áa]g\.(?=\s)': 'Página', r'\bP[áa]gs\.(?=\s)': 'Páginas',
    r'\bFl\.(?=\s)': 'Folha', r'\bFls\.(?=\s)': 'Folhas',
    r'\bPe\.(?=\s)': 'Padre',
    r'\bDept[o]?\.(?=\s)': 'Departamento',
    r'\bUniv\.(?=\s)': 'Universidade', r'\bInst\.(?=\s)': 'Instituição',
    r'\bEst\.(?=\s)': 'Estado', r'\bTel\.(?=\s)': 'Telefone',
    r'\bCEP(?=\s|:)': 'Código de Endereçamento Postal', # No dot needed for CEP
    r'\bCNPJ(?=\s|:)': 'Cadastro Nacional da Pessoa Jurídica',
    r'\bCPF(?=\s|:)': 'Cadastro de Pessoas Físicas',
    r'\bEUA\.(?=\s)': 'Estados Unidos da América',
    r'\bEd\.(?=\s)': 'Edição', r'\bLtda\.(?=\s)': 'Limitada'
}

CONVERSAO_CAPITULOS_EXTENSO_PARA_NUM = {
    'UM': '1', 'DOIS': '2', 'TRÊS': '3', 'QUATRO': '4', 'CINCO': '5',
    'SEIS': '6', 'SETE': '7', 'OITO': '8', 'NOVE': '9', 'DEZ': '10',
    'ONZE': '11', 'DOZE': '12', 'TREZE': '13', 'CATORZE': '14', 'QUINZE': '15',
    'DEZESSEIS': '16', 'DEZESSETE': '17', 'DEZOITO': '18', 'DEZENOVE': '19', 'VINTE': '20'
    # Add more if needed
}

def _formatar_numeracao_capitulos(texto):
    """
    Localiza títulos como 'Capítulo 1 Mesmo em pleno verão...' ou 'CAPÍTULO UM ...'
    e converte para: '\n\nCAPÍTULO 1.\n\nMesmo em pleno verão...'
    Também padroniza números por extenso para arábicos.
    """
    def substituir_cap(match):
        tipo_cap = match.group(1).upper() # CAPÍTULO ou CAP.
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
        if titulo_opcional: # Se houver título após o número
             # Capitaliza o título do capítulo, mas preserva siglas
            palavras_titulo = []
            for p in titulo_opcional.split():
                if p.isupper() and len(p) > 1: # sigla
                    palavras_titulo.append(p)
                else:
                    palavras_titulo.append(p.capitalize())
            titulo_formatado = " ".join(palavras_titulo)
            return f"\n\n{cabecalho}\n\n{titulo_formatado}"
        return f"\n\n{cabecalho}\n\n" # Se o título já está na próxima linha

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
    linhas = texto.splitlines()
    novas_linhas = []
    for linha in linhas:
        if re.match(r'^\s*\d+\s*$', linha):
            continue
        linha = re.sub(r'\s{3,}\d+\s*$', '', linha)
        novas_linhas.append(linha)
    return '\n'.join(novas_linhas)

def _normalizar_caixa_alta_linhas(texto):
    linhas = texto.splitlines()
    texto_final = []
    for linha in linhas:
        if not re.match(r'^\s*CAP[ÍI]TULO\s+[\w\d]+\.?\s*$', linha, re.IGNORECASE):
            if linha.isupper() and len(linha.strip()) > 3 and any(c.isalpha() for c in linha):
                palavras = []
                for p in linha.split():
                    if len(p) > 1 and p.isupper() and p.isalpha() and p not in ['I', 'A', 'E', 'O', 'U']:
                        if not (sum(1 for char in p if char in "AEIOU") > 0 and \
                                sum(1 for char in p if char not in "AEIOU") > 0 and len(p) <=4) :
                            palavras.append(p)
                            continue
                    palavras.append(p.capitalize())
                texto_final.append(" ".join(palavras))
            else:
                texto_final.append(linha)
        else:
            texto_final.append(linha)
    return "\n".join(texto_final)

def _corrigir_hifenizacao_quebras(texto):
    return re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', texto)

def _remover_metadados_pdf(texto):
    texto = re.sub(r'^\s*[\w\d_-]+\.indd\s+\d+\s+\d{2}/\d{2}/\d{2,4}\s+\d{1,2}:\d{2}(:\d{2})?\s*([AP]M)?\s*$', '', texto, flags=re.MULTILINE)
    return texto

# Coloque esta definição ANTES da função _expandir_abreviacoes_numeros
# Mapeia a forma base (sem ponto, case-insensitive) para a expansão
ABREVIACOES_MAP = {
    'dr': 'Doutor', 'd': 'Dona', 'dra': 'Doutora',
    'sr': 'Senhor', 'sra': 'Senhora', 'srta': 'Senhorita',
    'prof': 'Professor', 'profa': 'Professora',
    'eng': 'Engenheiro', 'engª': 'Engenheira', # 'engª' é um caso especial
    'adm': 'Administrador', 'adv': 'Advogado',
    'exmo': 'Excelentíssimo', 'exma': 'Excelentíssima',
    'v.exa': 'Vossa Excelência', 'v.sa': 'Vossa Senhoria', # Casos com ponto interno
    'av': 'Avenida', 'r': 'Rua', 'km': 'Quilômetro',
    'etc': 'etcétera', 'ref': 'Referência',
    'pag': 'Página', 'pags': 'Páginas',
    'fl': 'Folha', 'fls': 'Folhas',
    'pe': 'Padre',
    'dept': 'Departamento', 'depto': 'Departamento',
    'univ': 'Universidade', 'inst': 'Instituição',
    'est': 'Estado', 'tel': 'Telefone',
    # CEP, CNPJ, CPF não terminam em ponto geralmente
    'eua': 'Estados Unidos da América', # Sigla comum
    'ed': 'Edição', 'ltda': 'Limitada'
    # Adicione mais conforme necessário
}

# Pré-processar para busca case-insensitive mais rápida
ABREVIACOES_MAP_LOWER = {k.lower(): v for k, v in ABREVIACOES_MAP.items()}

# Casos especiais que precisam de tratamento diferente (ex: ponto interno)
# Estes podem ser deixados nos padrões originais se a nova abordagem não funcionar bem
CASOS_ESPECIAIS_RE = {
     r'\bV\.Exa\.(?=\s)': 'Vossa Excelência', # Mantém o padrão original
     r'\bV\.Sa\.(?=\s)': 'Vossa Senhoria',  # Mantém o padrão original
     r'\bEngª\.(?=\s)': 'Engenheira' # Trata 'ª' separadamente
     # Adicionar outros casos complexos aqui se necessário
}

def _expandir_abreviacoes_numeros(texto: str) -> str:
    """Expande abreviações comuns (removendo o ponto da abrev.) e converte números."""

    # Primeiro, trata casos especiais com regex mais complexas
    for abrev_re, expansao in CASOS_ESPECIAIS_RE.items():
         texto = re.sub(abrev_re, expansao, texto, flags=re.IGNORECASE)

    # Agora, trata as abreviações mais simples terminadas em ponto
    def replace_abrev_com_ponto(match):
        abrev_encontrada = match.group(1) # A parte da abreviação antes do ponto
        # Busca a expansão no dicionário (case-insensitive)
        expansao = ABREVIACOES_MAP_LOWER.get(abrev_encontrada.lower())
        if expansao:
            return expansao # Retorna APENAS a expansão, removendo o ponto original
        else:
            return match.group(0) # Se não encontrar (improvável), retorna o match original

    # Cria um padrão regex que busca por qualquer chave do dicionário seguida por um ponto.
    # Ex: \b(Dr|D|Dra|Sr|Sra|...)\.(?!\.)
    # Usamos lookahead negativo (?!\.) para NÃO remover o ponto se for seguido por outro (ex: fim de frase..)
    # Ou, mais simples: sempre remove o ponto da abreviação e deixa a lógica de pontuação final para depois.
    
    # Padrão: \b(chave1|chave2|...)\.
    # Captura a chave (grupo 1) e o ponto literal.
    chaves_escapadas = [re.escape(k) for k in ABREVIACOES_MAP_LOWER.keys() if '.' not in k and 'ª' not in k] # Ignora chaves já tratadas ou complexas
    if chaves_escapadas: # Só cria o padrão se houver chaves simples
        padrao_abrev_simples = r'\b(' + '|'.join(chaves_escapadas) + r')\.'
        texto = re.sub(padrao_abrev_simples, replace_abrev_com_ponto, texto, flags=re.IGNORECASE)

    # --- Conversão de números cardinais (lógica mantida) ---
    def _converter_numero_match(match):
        num_str = match.group(0)
        try:
            if re.match(r'^\d{4}$', num_str) and (1900 <= int(num_str) <= 2100): return num_str
            if len(num_str) > 7 : return num_str
            return num2words(int(num_str), lang='pt_BR')
        except Exception: return num_str
    texto = re.sub(r'\b\d+\b', _converter_numero_match, texto)

    # --- Conversão de valores monetários (lógica mantida) ---
    def _converter_valor_monetario_match(match):
        valor_inteiro = match.group(1).replace('.', '')
        try: return f"{num2words(int(valor_inteiro), lang='pt_BR')} reais"
        except Exception: return match.group(0)
    texto = re.sub(r'R\$\s*(\d{1,3}(?:\.\d{3})*),(\d{2})', _converter_valor_monetario_match, texto)
    texto = re.sub(r'R\$\s*(\d+)(?:,00)?', lambda m: f"{num2words(int(m.group(1)), lang='pt_BR')} reais" if m.group(1) else m.group(0) , texto)
    
    # --- Conversão de intervalos numéricos (lógica mantida) ---
    texto = re.sub(r'\b(\d+)\s*-\s*(\d+)\b', lambda m: f"{num2words(int(m.group(1)), lang='pt_BR')} a {num2words(int(m.group(2)), lang='pt_BR')}", texto)
    
    return texto

def _converter_ordinais_para_extenso(texto: str) -> str:
    """Converte números ordinais como 1º, 2a, 3ª para extenso."""

    def substituir_ordinal(match):
        numero = match.group(1)
        terminacao = match.group(2).lower() # 'o', 'a', 'os', 'as' (embora 'os'/'as' sejam menos comuns assim)

        try:
            num_int = int(numero)
            if terminacao == 'o' or terminacao == 'º':
                return num2words(num_int, lang='pt_BR', to='ordinal')
            elif terminacao == 'a' or terminacao == 'ª':
                # num2words para ordinal feminino em pt_BR pode precisar de ajuste manual
                # para algumas bibliotecas ou versões.
                # A biblioteca num2words geralmente lida bem com isso se o idioma estiver correto.
                # Ex: num2words(1, lang='pt_BR', to='ordinal_num') -> 1 (mas queremos extenso)
                # Tentativa: converter para ordinal masculino e trocar terminação se necessário
                ordinal_masc = num2words(num_int, lang='pt_BR', to='ordinal')
                if ordinal_masc.endswith('o'):
                    return ordinal_masc[:-1] + 'a'
                else: # Casos como 'terceiro' -> 'terceira' já são cobertos
                    return ordinal_masc # Ou lógica mais específica se necessário
            else: # Caso não previsto, retorna o original
                return match.group(0)
        except ValueError:
            return match.group(0) # Se não for um número válido

    # Padrão para encontrar números seguidos por 'o', 'a', 'º', ou 'ª'
    # \b(\d+)\s*([oaºª])\b -> \b para garantir que é uma palavra/número isolado
    # Adicionamos (?!\w) para evitar pegar em palavras como "para" ou "caso"
    padrao_ordinal = re.compile(r'\b(\d+)\s*([oaºª])(?!\w)', re.IGNORECASE)
    texto = padrao_ordinal.sub(substituir_ordinal, texto)

    return texto

# ================== SET DE ABREVIAÇÕES (Definir ANTES da função) ==================
# (Mantenha a definição de ABREVIACOES_QUE_NAO_TERMINAM_FRASE e SIGLA_COM_PONTOS_RE como na versão anterior)
ABREVIACOES_QUE_NAO_TERMINAM_FRASE = set([
    # ... (lista completa da versão anterior) ...
    'sr.', 'sra.', 'srta.', 'dr.', 'dra.', 'prof.', 'profa.', 'eng.', 'exmo.', 'exma.', 
    'pe.', 'rev.', 'ilmo.', 'ilma.', 'gen.', 'cel.', 'maj.', 'cap.', 'ten.', 'sgt.', 
    'cb.', 'sd.', 'me.', 'ms.', 'msc.', 'esp.', 'av.', 'r.', 'pç.', 'esq.', 'trav.', 
    'jd.', 'pq.', 'rod.', 'km.', 'apt.', 'ap.', 'bl.', 'cj.', 'cs.', 'ed.', 'nº', 
    'no.', 'uf.', 'cep.', 'est.', 'mun.', 'dist.', 'zon.', 'reg.', 'kg.', 'cm.', 
    'mm.', 'lt.', 'ml.', 'mg.', 'seg.', 'min.', 'hr.', 'ltda.', 's.a.', 's/a', 
    'cnpj.', 'cpf.', 'rg.', 'proc.', 'ref.', 'cod.', 'tel.', 'etc.', 'p.ex.', 'ex.', 
    'i.e.', 'e.g.', 'vs.', 'cf.', 'op.cit.', 'loc.cit.', 'fl.', 'fls.', 'pag.', 
    'p.', 'pp.', 'u.s.', 'e.u.a.', 'o.n.u.', 'i.b.m.', 'h.p.', 'obs.', 'att.', 
    'resp.', 'publ.', 'ed.', 'doutora', 'senhora', 'senhor', 'doutor', 'professor', 
    'professora', 'general'
])
SIGLA_COM_PONTOS_RE = re.compile(r'\b([A-Z]\.\s*)+$')
# ==============================================================================

def formatar_texto_para_tts(texto_bruto: str) -> str:
    print("⚙️ Aplicando formatações ao texto...")
    texto = texto_bruto

    # 0. Normalizações e remoções básicas (mantidas)
    # ... (código inalterado) ...
    texto = unicodedata.normalize('NFKC', texto)
    texto = texto.replace('\f', '\n\n'); texto = texto.replace('*', '')
    caracteres_para_espaco = ['_', '#', '@']
    caracteres_para_remover = ['(', ')', '\\', '[', ']'] 
    for char in caracteres_para_espaco: texto = texto.replace(char, ' ')
    for char in caracteres_para_remover: texto = texto.replace(char, '')
    texto = re.sub(r'\{.*?\}', '', texto) 

    # 1. Pré-limpeza de espaços múltiplos e linhas vazias (mantida)
    # ... (código inalterado) ...
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = "\n".join([linha.strip() for linha in texto.splitlines() if linha.strip()]) 

    # 2. JUNTAR LINHAS DENTRO DE PARÁGRAFOS INTENCIONAIS (mantida)
    # ... (código inalterado da versão anterior) ...
    paragrafos_originais = texto.split('\n\n')
    paragrafos_processados = []
    for paragrafo_bruto in paragrafos_originais:
        paragrafo_bruto = paragrafo_bruto.strip()
        if not paragrafo_bruto: continue
        linhas_do_paragrafo = paragrafo_bruto.split('\n')
        paragrafo_corrido_linhas = []
        buffer_linha_atual = ""
        for i, linha in enumerate(linhas_do_paragrafo):
            linha_strip = linha.strip();
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
            if juntar_com_anterior: buffer_linha_atual += " " + linha_strip
            else:
                if buffer_linha_atual: paragrafos_processados.append(buffer_linha_atual)
                buffer_linha_atual = linha_strip
        if buffer_linha_atual: paragrafos_processados.append(buffer_linha_atual)
    texto = '\n\n'.join(paragrafos_processados)
    
    # 3. Limpeza de espaços e quebras (mantido)
    # ... (código inalterado) ...
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto) 
    texto = re.sub(r'\n{3,}', '\n\n', texto) 

    # 4. Formatações que operam melhor no texto mais estruturado (mantidas)
    # ... (código inalterado) ...
    texto = _remover_metadados_pdf(texto)
    texto = _remover_numeros_pagina_isolados(texto) 
    texto = _corrigir_hifenizacao_quebras(texto) 
    texto = _formatar_numeracao_capitulos(texto)

    # 5. REINTRODUZIR QUEBRAS DE PARÁGRAFO (\n\n) INTELIGENTEMENTE (mantida)
    # ... (código inalterado da versão anterior) ...
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
        if not nao_quebrar: texto_reconstruido += buffer_segmento + "\n\n"; buffer_segmento = "" 
    if buffer_segmento:
         texto_reconstruido += buffer_segmento
         if not re.search(r'[.!?…)]$', buffer_segmento): texto_reconstruido += "."
         texto_reconstruido += "\n\n" 
    texto = texto_reconstruido.strip() 

    # 6. Formatações Finais (Caixa, Ordinais, Cardinais, etc.)
    texto = _normalizar_caixa_alta_linhas(texto)
    texto = _converter_ordinais_para_extenso(texto)
    texto = _expandir_abreviacoes_numeros(texto) # <<< Expansão acontece aqui

    # === NOVA ETAPA 6.5: Limpeza Pós-Expansão ===
    # Remove ponto final especificamente após as formas expandidas de tratamentos comuns,
    # SEGUIDO por um espaço e uma letra maiúscula (indicando nome próprio ou início de frase indevido).
    formas_expandidas_tratamento = ['Senhor', 'Senhora', 'Doutor', 'Doutora', 'Professor', 'Professora', 'Excelentíssimo', 'Excelentíssima'] # Adicione mais se necessário
    for forma in formas_expandidas_tratamento:
        # Padrão: \bFormaExpandida\.\s+([A-Z])
        # Substitui por: FormaExpandida \1 (mantém a letra maiúscula seguinte)
        padrao_limpeza = r'\b' + re.escape(forma) + r'\.\s+([A-Z])'
        texto = re.sub(padrao_limpeza, rf'{forma} \1', texto)
        # Caso sem espaço após o ponto (menos comum, mas possível)
        padrao_limpeza_sem_espaco = r'\b' + re.escape(forma) + r'\.([A-Z])'
        texto = re.sub(padrao_limpeza_sem_espaco, rf'{forma} \1', texto)
        
    # Limpa também casos como "U. S. Robôs" -> "U. S. Robôs" (já deve ser tratado antes, mas por garantia)
    # Remove ponto após sigla de letra única se seguido por espaço e letra maiúscula
    texto = re.sub(r'\b([A-Z])\.\s+([A-Z])', r'\1. \2', texto) # Ex: U. S. -> U. S. (garante espaço)
    texto = re.sub(r'\b([A-Z])\.\s+([A-Z][a-z])', r'\1. \2', texto) # Ex: U. S. Robos -> U. S. Robos


    # =============================================

    # 7. Limpeza Final de Parágrafos Vazios e Espaços (mantida)
    # ... (código inalterado) ...
    paragrafos_finais = texto.split('\n\n')
    paragrafos_formatados_final = []
    for p in paragrafos_finais:
        p_strip = p.strip()
        if not p_strip: continue 
        if not re.search(r'[.!?…)]$', p_strip) and \
           not re.match(r'^\s*CAP[ÍI]TULO\s+[\w\d]+\.?\s*$', p_strip.split('\n')[0].strip(), re.IGNORECASE):
            p_strip += '.'
        paragrafos_formatados_final.append(p_strip)
    texto = '\n\n'.join(paragrafos_formatados_final)
    texto = re.sub(r'[ \t]+', ' ', texto).strip()
    texto = re.sub(r'\n{2,}', '\n\n', texto)

    print("✅ Formatação de texto concluída.")
    return texto.strip()

# ================== FUNÇÕES DE SISTEMA E DEPENDÊNCIAS ==================

def handler_sinal(signum, frame):
    global CANCELAR_PROCESSAMENTO
    CANCELAR_PROCESSAMENTO = True
    print("\n🚫 Operação cancelada pelo usuário. Aguarde a finalização da tarefa atual...")

signal.signal(signal.SIGINT, handler_sinal)

def detectar_sistema():
    global SISTEMA_OPERACIONAL_INFO
    if SISTEMA_OPERACIONAL_INFO:
        return SISTEMA_OPERACIONAL_INFO
    sistema = {
        'nome': platform.system().lower(), 'termux': False, 'android': False,
        'windows': False, 'linux': False, 'macos': False,
    }
    if sistema['nome'] == 'windows': sistema['windows'] = True
    elif sistema['nome'] == 'darwin': sistema['macos'] = True
    elif sistema['nome'] == 'linux':
        sistema['linux'] = True
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
    try:
        subprocess.run(comando_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"✅ {mensagem_sucesso}")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"⚠️ {mensagem_falha}")
        current_os_name = SISTEMA_OPERACIONAL_INFO.get('nome', '')
        if install_commands and current_os_name:
            cmd_list = install_commands.get(current_os_name)
            if SISTEMA_OPERACIONAL_INFO.get('termux') and install_commands.get('termux'):
                cmd_list = install_commands.get('termux')

            if cmd_list:
                print(f"   Sugestão de instalação: {' OR '.join(cmd_list)}")
                if SISTEMA_OPERACIONAL_INFO.get('termux') and 'poppler' in mensagem_falha.lower():
                    if _instalar_dependencia_termux_auto('poppler'): return True
                elif SISTEMA_OPERACIONAL_INFO.get('windows') and 'poppler' in mensagem_falha.lower():
                    if instalar_poppler_windows(): return True # instalar_poppler_windows is defined later
            else:
                print("   Comando de instalação não especificado para este SO.")
        elif not install_commands:
             print("   Comando de instalação não especificado.")
        return False

def _instalar_dependencia_termux_auto(pkg: str) -> bool:
    try:
        print(f" пытаюсь установить {pkg} в Termux...")
        subprocess.run(['pkg', 'update', '-y'], check=True, capture_output=True)
        subprocess.run(['pkg', 'install', '-y', pkg], check=True, capture_output=True)
        print(f"✅ Pacote Termux {pkg} instalado com sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao instalar pacote Termux {pkg} automaticamente: {e.stderr.decode() if e.stderr else e}")
    except Exception as e:
        print(f"❌ Erro inesperado ao instalar {pkg} em Termux: {e}")
    return False

def instalar_poppler_windows():
    if shutil.which("pdftotext.exe"):
        print("✅ Poppler (pdftotext.exe) já encontrado no PATH.")
        return True
    print("📦 Poppler (pdftotext.exe) não encontrado no PATH. Tentando instalar...")
    try:
        poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.11.0-0/Release-23.11.0-0.zip"
        install_dir_base = os.environ.get('LOCALAPPDATA', os.path.join(os.path.expanduser("~"), "AppData", "Local"))
        if not install_dir_base:
             install_dir_base = os.path.join(os.path.expanduser("~"), "Poppler")
        install_dir = os.path.join(install_dir_base, 'Poppler')
        os.makedirs(install_dir, exist_ok=True)
        print("📥 Baixando Poppler...")
        response = requests.get(poppler_url, stream=True)
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
            potential_bin_path = os.path.join(install_dir, 'bin')
            if os.path.exists(potential_bin_path): bin_path = potential_bin_path
        if not bin_path or not os.path.exists(os.path.join(bin_path, 'pdftotext.exe')):
            for root, dirs, files in os.walk(install_dir):
                if 'pdftotext.exe' in files and 'bin' in root: bin_path = root; break
            if not bin_path:
                print(f"❌ Erro: Diretório 'bin' com 'pdftotext.exe' não encontrado em {install_dir} após extração.")
                shutil.rmtree(install_dir); return False
        print(f"✅ Diretório bin do Poppler encontrado em: {bin_path}")
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
                 print("⚠️ Poppler instalado, mas pdftotext.exe ainda não está no PATH da sessão atual. Adicione manualmente ou reinicie.")
                 print(f"   Adicione este diretório ao seu PATH: {bin_path}"); return False
        except Exception as e_winreg:
            print(f"❌ Erro ao tentar modificar o PATH do usuário via registro: {e_winreg}")
            print(f"   Por favor, adicione manualmente o diretório '{bin_path}' ao seu PATH.")
            os.environ['PATH'] = f"{bin_path};{os.environ['PATH']}"
            if shutil.which("pdftotext.exe"): return True
            return False
    except requests.exceptions.RequestException as e_req:
        print(f"❌ Erro ao baixar Poppler: {str(e_req)}"); return False
    except zipfile.BadZipFile:
        print("❌ Erro: O arquivo baixado do Poppler não é um ZIP válido ou está corrompido.")
        if 'zip_path' in locals() and os.path.exists(zip_path): os.remove(zip_path); return False
    except Exception as e:
        print(f"❌ Erro inesperado ao instalar Poppler: {str(e)}")
        if 'install_dir' in locals() and os.path.exists(install_dir): pass; return False

def verificar_dependencias_essenciais():
    print("\n🔍 Verificando dependências essenciais...")
    detectar_sistema()
    if not _verificar_comando([FFMPEG_BIN, '-version'], "FFmpeg encontrado.",
        "FFmpeg não encontrado. Necessário para manipulação de áudio/vídeo.",
        install_commands={'termux': ['pkg install ffmpeg'], 'linux': ['sudo apt install ffmpeg', 'sudo yum install ffmpeg', 'sudo dnf install ffmpeg'],
                          'macos': ['brew install ffmpeg'], 'windows': ['Baixe em https://ffmpeg.org/download.html e adicione ao PATH']}):
        print("    Algumas funcionalidades do script podem não funcionar sem FFmpeg.")
    pdftotext_cmd = "pdftotext.exe" if SISTEMA_OPERACIONAL_INFO.get('windows') else "pdftotext"
    if not _verificar_comando([pdftotext_cmd, '-v'], "Poppler (pdftotext) encontrado.",
        "Poppler (pdftotext) não encontrado. Necessário para converter PDF para TXT.",
        install_commands={'termux': ['pkg install poppler'], 'linux': ['sudo apt install poppler-utils', 'sudo yum install poppler-utils'],
                          'macos': ['brew install poppler'], 'windows': ['Tentativa de instalação automática será feita se necessário.']}):
        print("    A conversão de PDF para TXT não funcionará sem Poppler.")
    print("✅ Verificação de dependências essenciais concluída.")

def converter_pdf_para_txt(caminho_pdf: str, caminho_txt: str) -> bool:
    sistema = detectar_sistema()
    pdftotext_executable = "pdftotext"
    if sistema['windows']:
        pdftotext_executable = shutil.which("pdftotext.exe")
        if not pdftotext_executable:
            if not instalar_poppler_windows(): print("❌ Falha ao instalar Poppler..."); return False
            pdftotext_executable = shutil.which("pdftotext.exe")
            if not pdftotext_executable: print("❌ pdftotext.exe não encontrado..."); return False
    elif sistema['termux'] and not shutil.which("pdftotext"):
        if not _instalar_dependencia_termux_auto("poppler"): print("❌ Falha ao instalar poppler no Termux..."); return False
        pdftotext_executable = "pdftotext"
    if not os.path.isfile(caminho_pdf): print(f"❌ Arquivo PDF não encontrado: {caminho_pdf}"); return False
    try:
        comando = [pdftotext_executable or "pdftotext", "-layout", "-enc", "UTF-8", caminho_pdf, caminho_txt]
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if resultado.returncode != 0:
            comando = [pdftotext_executable or "pdftotext", "-layout", caminho_pdf, caminho_txt]
            resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if resultado.returncode != 0: print(f"❌ Erro ao converter PDF: {resultado.stderr.decode(errors='ignore')}"); return False
        print(f"✅ PDF convertido para TXT: {caminho_txt}"); return True
    except FileNotFoundError:
        print(f"❌ Comando '{pdftotext_executable or 'pdftotext'}' não encontrado...")
        if sistema['linux'] and not sistema['termux']: print("   Tente: sudo apt install poppler-utils")
        elif sistema['macos']: print("   Tente: brew install poppler"); return False
    except subprocess.CalledProcessError as e: print(f"❌ Erro ao converter PDF: {e.stderr.decode(errors='ignore')}"); return False
    except Exception as e: print(f"❌ Erro inesperado ao converter PDF: {str(e)}"); return False

# ================== FUNÇÕES DE UI E FLUXO ==================

def limpar_tela() -> None: os.system('cls' if detectar_sistema()['windows'] else 'clear')

async def obter_opcao_numerica(prompt: str, num_max: int, permitir_zero=False) -> int:
    min_val = 0 if permitir_zero else 1
    while True:
        try:
            escolha_str = await aioconsole.ainput(f"{prompt} [{min_val}-{num_max}]: ")
            escolha = int(escolha_str)
            if min_val <= escolha <= num_max: return escolha
            else: print(f"⚠️ Opção inválida. Escolha um número entre {min_val} e {num_max}.")
        except ValueError: print("⚠️ Entrada inválida. Por favor, digite um número.")
        except asyncio.CancelledError: print("\n🚫 Entrada cancelada."); raise

async def obter_confirmacao(prompt: str, default_yes=True) -> bool:
    opcoes_prompt = "(S/n)" if default_yes else "(s/N)"
    while True:
        try:
            resposta = await aioconsole.ainput(f"{prompt} {opcoes_prompt}: ")
            resposta = resposta.strip().lower()
            if not resposta: return default_yes
            if resposta in ['s', 'sim']: return True
            if resposta in ['n', 'nao', 'não']: return False
            print("⚠️ Resposta inválida. Digite 's' ou 'n'.")
        except asyncio.CancelledError: print("\n🚫 Entrada cancelada."); raise

async def exibir_banner_e_menu(titulo_menu: str, opcoes_menu: dict):
    limpar_tela()
    print("╔════════════════════════════════════════════╗")
    print("║         CONVERSOR TTS COMPLETO             ║")
    print("║ Text-to-Speech + Melhoria de Áudio em PT-BR║")
    print("╚════════════════════════════════════════════╝")
    print(f"\n--- {titulo_menu.upper()} ---")
    for num, desc in opcoes_menu.items(): print(f"{num}. {desc}")
    return await obter_opcao_numerica("Opção", len(opcoes_menu), permitir_zero=('0' in opcoes_menu))

# ================== FUNÇÕES DE MANIPULAÇÃO DE ARQUIVOS E CONTEÚDO ==================

def detectar_encoding_arquivo(caminho_arquivo: str) -> str:
    try:
        with open(caminho_arquivo, 'rb') as f: raw_data = f.read(50000)
        resultado = chardet.detect(raw_data)
        encoding = resultado['encoding']
        confidence = resultado['confidence']
        if encoding and confidence > 0.7: return encoding
        for enc_try in ENCODINGS_TENTATIVAS:
            try:
                with open(caminho_arquivo, 'r', encoding=enc_try) as f_test: f_test.read(1024)
                return enc_try
            except (UnicodeDecodeError, TypeError): continue
        return 'utf-8'
    except Exception as e: print(f"⚠️ Erro ao detectar encoding: {str(e)}..."); return 'utf-8'

def ler_arquivo_texto(caminho_arquivo: str) -> str:
    encoding = detectar_encoding_arquivo(caminho_arquivo)
    try:
        with open(caminho_arquivo, 'r', encoding=encoding, errors='replace') as f: return f.read()
    except Exception as e: print(f"❌ Erro ao ler arquivo '{caminho_arquivo}': {str(e)}"); return ""

def salvar_arquivo_texto(caminho_arquivo: str, conteudo: str):
    try:
        os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
        with open(caminho_arquivo, 'w', encoding='utf-8') as f: f.write(conteudo)
        print(f"✅ Arquivo salvo: {caminho_arquivo}")
    except Exception as e: print(f"❌ Erro ao salvar arquivo '{caminho_arquivo}': {str(e)}")

def limpar_nome_arquivo(nome: str) -> str:
    nome_sem_ext, ext = os.path.splitext(nome)
    nome_normalizado = unicodedata.normalize('NFKD', nome_sem_ext).encode('ascii', 'ignore').decode('ascii')
    nome_limpo = re.sub(r'[^\w\s-]', '', nome_normalizado).strip()
    nome_limpo = re.sub(r'[-\s]+', '_', nome_limpo)
    return nome_limpo + ext if ext else nome_limpo

def extrair_texto_de_epub(caminho_epub: str) -> str:
    print(f"\n📖 Extraindo conteúdo de: {caminho_epub}")
    texto_completo = ""
    try:
        with zipfile.ZipFile(caminho_epub, 'r') as epub_zip:
            try:
                container_xml = epub_zip.read('META-INF/container.xml').decode('utf-8')
                opf_path_match = re.search(r'full-path="([^"]+)"', container_xml)
                if not opf_path_match: raise Exception("Caminho do OPF não encontrado...")
                opf_path = opf_path_match.group(1)
                opf_content = epub_zip.read(opf_path).decode('utf-8')
                opf_dir = os.path.dirname(opf_path)
                spine_items = [m.group(1) for m in re.finditer(r'<itemref\s+idref="([^"]+)"', opf_content)]
                if not spine_items: raise Exception("Nenhum item na 'spine'...")
                manifest_hrefs = {m.group(1): m.group(2) for m in re.finditer(r'<item\s+id="([^"]+)"\s+href="([^"]+)"\s+media-type="application/xhtml\+xml"', opf_content)}
                arquivos_xhtml_ordenados = []
                for idref in spine_items:
                    if idref in manifest_hrefs:
                        xhtml_path_in_zip = os.path.normpath(os.path.join(opf_dir, manifest_hrefs[idref]))
                        arquivos_xhtml_ordenados.append(xhtml_path_in_zip)
                    else: print(f"⚠️ Aviso: ID '{idref}' da spine não encontrado...")
                if not arquivos_xhtml_ordenados:
                    print("⚠️ Falha ao ler 'spine'. Tentando todos os XHTML/HTML...")
                    arquivos_xhtml_ordenados = sorted([f.filename for f in epub_zip.infolist() if f.filename.lower().endswith(('.html', '.xhtml')) and not re.search(r'(toc|nav|cover|ncx)', f.filename, re.IGNORECASE)])
            except Exception as e_opf:
                print(f"⚠️ Erro ao processar OPF/Spine: {e_opf}. Tentando todos XHTML/HTML.")
                arquivos_xhtml_ordenados = sorted([f.filename for f in epub_zip.infolist() if f.filename.lower().endswith(('.html', '.xhtml')) and not re.search(r'(toc|nav|cover|ncx)', f.filename, re.IGNORECASE)])
            if not arquivos_xhtml_ordenados: print("❌ Nenhum arquivo de conteúdo utilizável..."); return ""
            h = html2text.HTML2Text(); h.ignore_links = True; h.ignore_images = True; h.ignore_emphasis = False; h.body_width = 0
            for nome_arquivo in tqdm(arquivos_xhtml_ordenados, desc="Processando arquivos EPUB"):
                try:
                    html_bytes = epub_zip.read(nome_arquivo)
                    detected_encoding = chardet.detect(html_bytes)['encoding'] or 'utf-8'
                    html_texto = html_bytes.decode(detected_encoding, errors='replace')
                    soup = BeautifulSoup(html_texto, 'html.parser')
                    for tag in soup(['nav', 'header', 'footer', 'style', 'script', 'figure', 'figcaption', 'aside', 'link', 'meta']): tag.decompose()
                    content_tag = soup.find('body') or soup
                    if content_tag: texto_completo += h.handle(str(content_tag)) + "\n\n"
                except KeyError: print(f"⚠️ Arquivo não encontrado no EPUB: {nome_arquivo}")
                except Exception as e_file: print(f"❌ Erro ao processar '{nome_arquivo}': {e_file}")
        if not texto_completo.strip(): print("⚠️ Nenhum conteúdo textual extraído..."); return ""
        return texto_completo
    except FileNotFoundError: print(f"❌ Arquivo EPUB não encontrado: {caminho_epub}")
    except zipfile.BadZipFile: print(f"❌ Arquivo EPUB inválido: {caminho_epub}")
    except Exception as e: print(f"❌ Erro geral ao processar EPUB: {e}"); return ""

def dividir_texto_para_tts(texto_processado: str) -> list:
    """Divide o texto em partes menores para TTS, respeitando parágrafos e frases,
       buscando um equilíbrio para performance."""
    partes_iniciais = texto_processado.split('\n\n') # Primeiro por parágrafos
    partes_finais = []
    # AJUSTE ESTE VALOR! Valores maiores = menos chunks.
    # Comece com 7000-8000 para Termux, pode ir até 10000-12000 se a API aceitar bem.
    # Se der muitos erros "NoAudioReceived", reduza.
    LIMITE_CARACTERES_CHUNK_TTS = 7500

    for p_inicial in partes_iniciais:
        p_strip = p_inicial.strip()
        if not p_strip:
            continue

        # Se o parágrafo inteiro já é menor que o limite, adiciona-o
        if len(p_strip) < LIMITE_CARACTERES_CHUNK_TTS:
            partes_finais.append(p_strip)
            continue

        # Se o parágrafo é maior, tenta dividir por frases, agrupando-as.
        # Usar regex para dividir por frases, mantendo os delimitadores.
        frases_com_delimitadores = re.split(r'([.!?…]+)', p_strip)
        segmento_atual = ""

        idx_frase = 0
        while idx_frase < len(frases_com_delimitadores):
            frase_atual = frases_com_delimitadores[idx_frase].strip()
            delimitador = ""
            if idx_frase + 1 < len(frases_com_delimitadores):
                delimitador = frases_com_delimitadores[idx_frase + 1].strip()
            
            trecho_completo = frase_atual
            if delimitador: # Adiciona o delimitador se existir
                trecho_completo += delimitador
            trecho_completo = trecho_completo.strip()

            if not trecho_completo: # Pula se a frase/delimitador for vazio
                idx_frase += 2 if delimitador else 1
                continue

            # Se adicionar o trecho atual não excede o limite do chunk
            if len(segmento_atual) + len(trecho_completo) + (1 if segmento_atual else 0) <= LIMITE_CARACTERES_CHUNK_TTS:
                segmento_atual += (" " if segmento_atual else "") + trecho_completo
            else:
                # O trecho atual faria o segmento exceder. Finaliza o segmento atual.
                if segmento_atual: # Adiciona o segmento anterior se não estiver vazio
                    partes_finais.append(segmento_atual)
                
                # O trecho atual se torna o novo segmento.
                # Se o próprio trecho já for maior que o limite, precisa ser quebrado (caso raro para uma frase)
                if len(trecho_completo) > LIMITE_CARACTERES_CHUNK_TTS:
                    # Quebra o trecho grande em pedaços menores que o limite
                    for i in range(0, len(trecho_completo), LIMITE_CARACTERES_CHUNK_TTS):
                        partes_finais.append(trecho_completo[i:i+LIMITE_CARACTERES_CHUNK_TTS])
                    segmento_atual = "" # Reseta, pois o trecho grande foi totalmente processado
                else:
                    segmento_atual = trecho_completo # Inicia novo segmento com o trecho atual

            idx_frase += 2 if delimitador else 1 # Avança para a próxima frase e seu delimitador

        # Adiciona o último segmento que pode ter sobrado
        if segmento_atual:
            partes_finais.append(segmento_atual)

    return [p for p in partes_finais if p.strip()] # Garante que não há chunks vazios

# ================== FUNÇÕES DE FFmpeg (ÁUDIO/VÍDEO) ==================

# Regex para capturar progresso do ffmpeg (simplificado) - Verifique se já existe no topo do seu script
FFMPEG_PROGRESS_RE = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

def _parse_ffmpeg_time(time_str: str) -> float:
    """Converte tempo 'HH:MM:SS.ms' do FFmpeg para segundos."""
    try:
        match = FFMPEG_PROGRESS_RE.search(time_str) # Usa search em vez de match
        if match:
            h, m, s, ms = map(int, match.groups())
            return h * 3600 + m * 60 + s + ms / 100.0
    except Exception:
        pass # Ignora erros de parsing
    return 0.0

import subprocess
import time

def _executar_ffmpeg_comando(comando, descricao="processamento FFmpeg"):
    """
    Executa um comando FFmpeg exibindo progresso em tempo real sem travar.
    Compatível com Termux / Android.
    """
    try:
        print(f"⚙️ Executando: {descricao}...")
        process = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )

        # Mostra progresso sem travar
        while True:
            retcode = process.poll()
            stderr_line = process.stderr.readline()

            # Sai do loop se o processo terminou
            if retcode is not None:
                break

            # Mostra pontinhos ou frames
            if stderr_line:
                if "frame=" in stderr_line or "size=" in stderr_line or "time=" in stderr_line:
                    print(".", end="", flush=True)
            else:
                time.sleep(0.1)

        # Garante que todo o buffer foi lido
        process.wait()

        if process.returncode == 0:
            print(f"\n✅ {descricao} concluído com sucesso.")
            return True
        else:
            print(f"\n❌ {descricao} falhou (código {process.returncode}).")
            return False

    except Exception as e:
        print(f"❌ Erro ao executar FFmpeg: {e}")
        return False

def criar_video_com_audio_ffmpeg(audio_path, video_path, duracao_segundos, resolucao_str="640x360"): # Flag 'usar_progresso_leve' removida
    """Cria um vídeo com tela preta a partir de um áudio, mostrando progresso percentual."""
    if duracao_segundos <= 0:
        print("⚠️ Duração inválida para criar vídeo.")
        return False
    comando = [
        FFMPEG_BIN, '-y',
        '-f', 'lavfi', '-i', f"color=c=black:s={resolucao_str}:r=1:d={duracao_segundos:.3f}",
        '-i', audio_path,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage',
        '-c:a', 'aac', '-b:a', '128k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        # '-progress', '-', '-nostats', # Mantém removido ou comentado, pois lemos o stderr padrão
        video_path
    ]

    # SEMPRE passa a duração total para _executar_ffmpeg_comando para obter progresso percentual
    return _executar_ffmpeg_comando(comando, f"criação de vídeo a partir de {Path(audio_path).name}", total_duration=duracao_segundos)


def acelerar_midia_ffmpeg(input_path: str, output_path: str, velocidade: float = 1.0, is_video: bool = False) -> bool:
    """
    Acelera áudio/vídeo de forma leve e estável, sem travamentos no Termux.
    Para vídeos longos, processa o áudio e o vídeo separadamente e depois junta.
    """
    try:
        if velocidade <= 0:
            print("⚠️ Velocidade inválida. Use um valor acima de 0.")
            return False

        # Gera nome seguro para o áudio temporário
        tmp_audio = str(Path(str(output_path).replace(".mp4", "_audio_temp.m4a")))
        tmp_video = str(Path(str(output_path).replace(".mp4", "_video_temp.mp4")))

        # Corrige limite do filtro atempo (máx. 2.0 por vez)
        atempo_filters = []
        restante = velocidade
        while restante > 2.0:
            atempo_filters.append("atempo=2.0")
            restante /= 2.0
        while restante < 0.5:
            atempo_filters.append("atempo=0.5")
            restante /= 0.5
        atempo_filters.append(f"atempo={restante:.3f}")
        atempo_str = ",".join(atempo_filters)

        # ========================
        # 🔊 1️⃣ Extrair + acelerar áudio
        # ========================
        print(f"🎧 Acelerando áudio em {velocidade}x...")
        comando_audio = [
            FFMPEG_BIN, "-y",
            "-i", input_path,
            "-vn",  # sem vídeo
            "-filter:a", atempo_str,
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            tmp_audio
        ]

        if not _executar_ffmpeg_comando(comando_audio, f"aceleração do áudio ({velocidade}x)"):
            print("❌ Falha ao acelerar áudio.")
            return False

        # ========================
        # 🎞️ 2️⃣ Ajustar vídeo (sem reencodar pesado)
        # ========================
        if is_video:
            print(f"🎬 Ajustando vídeo em {velocidade}x...")
            comando_video = [
                FFMPEG_BIN, "-y",
                "-i", input_path,
                "-an",  # sem áudio
                "-filter:v", f"setpts={1/velocidade}*PTS",
                "-preset", "ultrafast",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                tmp_video
            ]

            if not _executar_ffmpeg_comando(comando_video, f"ajuste do vídeo ({velocidade}x)"):
                print("❌ Falha ao ajustar vídeo.")
                if os.path.exists(tmp_audio): os.remove(tmp_audio)
                return False

            # ========================
            # 🧩 3️⃣ Unir áudio + vídeo
            # ========================
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
            if sucesso:
                print("✅ Arquivo final criado com sucesso!")
            else:
                print("❌ Falha na junção final.")

            # Limpeza
            for temp in [tmp_audio, tmp_video]:
                if os.path.exists(temp):
                    os.remove(temp)
            return sucesso

        else:
            # Apenas áudio
            shutil.move(tmp_audio, output_path)
            print("✅ Áudio acelerado com sucesso!")
            return True

    except Exception as e:
        print(f"❌ Erro ao acelerar mídia: {e}")
        return False

# ================== MENUS PRINCIPAIS E LÓGICA DE OPERAÇÃO ==================

async def _selecionar_arquivo_para_processamento(extensoes_permitidas: list) -> str:
    sistema = detectar_sistema()
    # Define diretório inicial baseado no SO
    if sistema['termux'] or sistema['android']:
        dir_atual = Path.home() / 'storage' / 'shared' / 'Download' # Caminho comum no Termux
        if not dir_atual.exists(): # Fallback para o home do Termux
            dir_atual = Path.home() / 'downloads'
        if not dir_atual.exists(): # Fallback para o storage downloads
             dir_atual = Path("/storage/emulated/0/Download")
    elif sistema['windows']:
        dir_atual = Path.home() / 'Downloads'
        if not dir_atual.exists(): dir_atual = Path.home() / 'Desktop' # Fallback
    else: # Linux, macOS
        dir_atual = Path.home() / 'Downloads'
        if not dir_atual.exists(): dir_atual = Path.home() # Fallback

    if not dir_atual.is_dir(): # Se o caminho não for um diretório válido
        dir_atual = Path.cwd()
        print(f"⚠️ Pasta Downloads padrão não encontrada ou inválida, usando diretório atual: {dir_atual}")


    while True:
        limpar_tela()
        print(f"📂 SELEÇÃO DE ARQUIVO (Extensões: {', '.join(extensoes_permitidas)})")
        print(f"\nDiretório atual: {dir_atual}")
        
        itens_no_diretorio = []
        try:
            # Adiciona ".." para subir um nível
            if dir_atual.parent != dir_atual: # Não mostrar ".." se já estiver na raiz
                itens_no_diretorio.append(("[..] (Voltar)", dir_atual.parent, True)) # (Nome, Path, É Diretório)
            
            # Listar diretórios primeiro, depois arquivos
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
            # Tenta voltar para o diretório pai ou home se der erro de permissão
            if dir_atual.parent != dir_atual: dir_atual = dir_atual.parent
            else: dir_atual = Path.home()
            await asyncio.sleep(2)
            continue
        except Exception as e:
            print(f"❌ Erro ao listar diretório {dir_atual}: {e}")
            dir_atual = Path.home() # Tenta resetar para home
            await asyncio.sleep(2)
            continue


        if not any(not item[2] for item in itens_no_diretorio): # Verifica se há algum arquivo (não diretório) na lista
             # A mensagem só deve aparecer se não houver arquivos, mesmo que haja o [..]
             is_root_and_empty = dir_atual.parent == dir_atual and not any(item_path.is_file() for _, item_path, _ in itens_no_diretorio if item_path.is_file())
             if not itens_no_diretorio or (len(itens_no_diretorio) == 1 and itens_no_diretorio[0][0].startswith("[..]")) or is_root_and_empty:
                 print(f"\n⚠️ Nenhum arquivo com as extensões permitidas ({', '.join(extensoes_permitidas)}) encontrado em {dir_atual}")


        for i, (nome, _, is_dir) in enumerate(itens_no_diretorio):
            print(f"{i+1}. {nome}")
        
        print("\nOpções:")
        print("M. Digitar caminho manualmente")
        print("V. Voltar ao menu anterior")

        try:
            # --- CORREÇÃO APLICADA AQUI ---
            raw_input_str = await aioconsole.ainput("\nEscolha uma opção ou número: ")
            escolha_str = raw_input_str.strip().upper()
            # --- FIM DA CORREÇÃO ---

            if escolha_str == 'V': return ""
            if escolha_str == 'M':
                caminho_manual_raw = await aioconsole.ainput("Digite o caminho completo do arquivo: ")
                caminho_manual_str = caminho_manual_raw.strip() # Strip antes de criar o Path
                if not caminho_manual_str: # Input vazio
                    print("⚠️ Caminho não pode ser vazio.")
                    await asyncio.sleep(1.5)
                    continue

                caminho_manual_path = Path(caminho_manual_str)
                if caminho_manual_path.is_file() and caminho_manual_path.suffix.lower() in extensoes_permitidas:
                    return str(caminho_manual_path)
                else:
                    print(f"❌ Caminho inválido ('{caminho_manual_str}') ou tipo de arquivo não permitido.")
                    await asyncio.sleep(1.5)
                    continue
            
            if escolha_str.isdigit():
                idx_escolha = int(escolha_str) - 1
                if 0 <= idx_escolha < len(itens_no_diretorio):
                    nome_sel, path_sel, is_dir_sel = itens_no_diretorio[idx_escolha]
                    if is_dir_sel:
                        dir_atual = path_sel
                    else: # É arquivo
                        return str(path_sel)
                else:
                    print("❌ Opção numérica inválida.")
            else:
                print("❌ Opção inválida.")
            await asyncio.sleep(1)

        except (ValueError, IndexError):
            print("❌ Seleção inválida.")
            await asyncio.sleep(1)
        except asyncio.CancelledError: # Trata Ctrl+C durante o input
            print("\n🚫 Seleção cancelada.")
            return "" # Ou raise para ser pego mais acima

async def _processar_arquivo_selecionado_para_texto(caminho_arquivo_orig: str) -> str:
    if not caminho_arquivo_orig: return ""
    path_obj = Path(caminho_arquivo_orig); nome_base_limpo = limpar_nome_arquivo(path_obj.stem)
    dir_saida = path_obj.parent; caminho_txt_formatado = dir_saida / f"{nome_base_limpo}_formatado.txt"
    if caminho_txt_formatado.exists() and caminho_txt_formatado.name != path_obj.name :
        if not await obter_confirmacao(f"Arquivo '{caminho_txt_formatado.name}' já existe. Reprocessar?", default_yes=False):
            return str(caminho_txt_formatado)
    texto_bruto = ""; extensao = path_obj.suffix.lower()
    if extensao == '.pdf':
        caminho_txt_temporario = dir_saida / f"{nome_base_limpo}_tempExtraido.txt"
        if not converter_pdf_para_txt(str(path_obj), str(caminho_txt_temporario)):
            print("❌ Falha na conversão PDF.");
            if caminho_txt_temporario.exists(): os.remove(caminho_txt_temporario); return ""
        texto_bruto = ler_arquivo_texto(str(caminho_txt_temporario))
        if caminho_txt_temporario.exists(): os.remove(caminho_txt_temporario)
    elif extensao == '.epub': texto_bruto = extrair_texto_de_epub(str(path_obj))
    elif extensao == '.txt': texto_bruto = ler_arquivo_texto(str(path_obj))
    else: print(f"❌ Formato não suportado: {extensao}"); return ""
    if not texto_bruto.strip(): print("❌ Conteúdo do arquivo vazio."); return ""
    texto_final_formatado = formatar_texto_para_tts(texto_bruto)
    salvar_arquivo_texto(str(caminho_txt_formatado), texto_final_formatado)
    if detectar_sistema()['windows'] or detectar_sistema()['macos'] or \
       (detectar_sistema()['linux'] and not detectar_sistema()['android']):
        if await obter_confirmacao("Abrir TXT formatado para edição?"):
            print(f"📝 Abrindo '{caminho_txt_formatado.name}'...");
            try:
                if detectar_sistema()['windows']: os.startfile(caminho_txt_formatado)
                else: subprocess.run(['xdg-open', str(caminho_txt_formatado)] if detectar_sistema()['linux'] else ['open', str(caminho_txt_formatado)], check=True)
                await aioconsole.ainput("Pressione ENTER após salvar edições...")
            except Exception as e_edit: print(f"❌ Não foi possível abrir editor: {e_edit}")
    elif detectar_sistema()['android']:
        print(f"✅ Arquivo formatado salvo: {caminho_txt_formatado}")
        print("   No Android, edite manualmente se necessário e selecione '_formatado.txt'.")
    return str(caminho_txt_formatado)

async def _converter_chunk_tts(texto_chunk: str, voz: str, caminho_saida_temp: str, indice_chunk: int, total_chunks: int) -> bool:
    """Converte um único chunk de texto para áudio, pulando se já existir e for válido."""
    global CANCELAR_PROCESSAMENTO
    path_saida_obj = Path(caminho_saida_temp)

    # Verificação de arquivo existente (mantida)
    if path_saida_obj.exists() and path_saida_obj.stat().st_size > 200:
        return True 

    tentativas = 0
    while tentativas < MAX_TTS_TENTATIVAS:
        if CANCELAR_PROCESSAMENTO: return False
        
        # Limpa arquivo anterior antes de tentar (se existir e for inválido)
        path_saida_obj.unlink(missing_ok=True) 
        
        try:
            if not texto_chunk or not texto_chunk.strip():
                print(f"⚠️ Chunk {indice_chunk}/{total_chunks} vazio/inválido, pulando.")
                return True 

            communicate = edge_tts.Communicate(texto_chunk, voz)
            await communicate.save(caminho_saida_temp)

            if path_saida_obj.exists() and path_saida_obj.stat().st_size > 200:
                return True # Sucesso
            else:
                # Arquivo criado mas inválido
                tamanho_real = path_saida_obj.stat().st_size if path_saida_obj.exists() else 0
                print(f"⚠️ Arquivo áudio chunk {indice_chunk} inválido (tamanho: {tamanho_real} bytes). Tentativa {tentativas + 1}.")
                path_saida_obj.unlink(missing_ok=True)
                # Continua para próxima tentativa

        except edge_tts.exceptions.NoAudioReceived:
             print(f"❌ Sem áudio recebido chunk {indice_chunk} (tentativa {tentativas + 1}). API pode estar offline ou rejeitou o texto.")
             # path_saida_obj.unlink(missing_ok=True) # Já foi limpo no início do try ou não foi criado
        except asyncio.TimeoutError: # Captura erro de timeout especificamente
            print(f"❌ Timeout na comunicação TTS chunk {indice_chunk} (tentativa {tentativas + 1}). Verifique a conexão.")
        except Exception as e: # Captura outros erros
            print(f"❌ Erro INESPERADO TTS chunk {indice_chunk} (tentativa {tentativas + 1}): {type(e).__name__} - {e}")
            import traceback # Imprime traceback para debug
            traceback.print_exc()
            # path_saida_obj.unlink(missing_ok=True) # Já foi limpo no início do try ou não foi criado

        # Se chegou aqui, a tentativa falhou
        tentativas += 1
        if tentativas < MAX_TTS_TENTATIVAS:
            print(f"   Retentando chunk {indice_chunk} em {2 * tentativas}s...")
            await asyncio.sleep(2 * tentativas)
        else:
            print(f"❌ Falha definitiva chunk {indice_chunk} após {MAX_TTS_TENTATIVAS} tentativas.")
            # path_saida_obj.unlink(missing_ok=True) # Garante limpeza final
            return False
            
    return False

def unificar_arquivos_audio_ffmpeg(lista_arquivos_temp: list, arquivo_final: str) -> bool:
    """Une arquivos de áudio temporários em um único arquivo final usando FFmpeg."""
    if not lista_arquivos_temp:
        print("⚠️ Nenhum arquivo de áudio para unificar.")
        return False
    
    # Cria um arquivo de lista para o FFmpeg concat demuxer
    # Usar caminhos absolutos e sanitizados para o file list
    dir_saida = os.path.dirname(arquivo_final)
    os.makedirs(dir_saida, exist_ok=True) # Garante que o diretório de saída existe
    # Limpa o nome do arquivo de lista para evitar caracteres problemáticos
    nome_lista_limpo = limpar_nome_arquivo(f"_{Path(arquivo_final).stem}_filelist.txt")
    lista_txt_path = Path(dir_saida) / nome_lista_limpo

    try:
        with open(lista_txt_path, "w", encoding='utf-8') as f_list:
            for temp_file in lista_arquivos_temp:
                # FFmpeg concat demuxer precisa de caminhos 'safe'
                # Escapar caracteres especiais para o formato do arquivo de lista
                safe_path = str(Path(temp_file).resolve()).replace("'", r"\'")
                f_list.write(f"file '{safe_path}'\n")
        
        comando = [
            FFMPEG_BIN, '-y', '-f', 'concat', '-safe', '0', # -safe 0 é necessário para caminhos absolutos
            '-i', str(lista_txt_path), 
            '-c', 'copy', # Copia os codecs sem reencodar
            arquivo_final
        ]
        # A unificação com -c copy é rápida e não fornece progresso útil por tempo
        return _executar_ffmpeg_comando(comando, f"unificação de áudio para {os.path.basename(arquivo_final)}")
    except IOError as e:
        print(f"❌ Erro ao criar arquivo de lista para FFmpeg: {e}")
        return False
    finally:
        # Remove o arquivo de lista temporário
        if lista_txt_path.exists():
            try:
                lista_txt_path.unlink()
            except Exception as e_unlink:
                print(f"⚠️ Não foi possível remover o arquivo de lista temporário {lista_txt_path}: {e_unlink}")

async def iniciar_conversao_tts():
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False
    caminho_arquivo_orig = await _selecionar_arquivo_para_processamento(['.txt', '.pdf', '.epub'])
    if not caminho_arquivo_orig or CANCELAR_PROCESSAMENTO: return

    caminho_txt_processado = await _processar_arquivo_selecionado_para_texto(caminho_arquivo_orig)
    if not caminho_txt_processado or CANCELAR_PROCESSAMENTO: return

    opcoes_voz = {str(i+1): voz for i, voz in enumerate(VOZES_PT_BR)}; opcoes_voz[str(len(VOZES_PT_BR)+1)] = "Voltar"
    limpar_tela(); print("\n--- SELECIONAR VOZ ---"); [print(f"{i+1}. {v}") for i,v in enumerate(VOZES_PT_BR)]; print(f"{len(VOZES_PT_BR)+1}. Voltar")
    escolha_voz_idx = await obter_opcao_numerica("Escolha uma voz", len(VOZES_PT_BR)+1)
    if escolha_voz_idx == len(VOZES_PT_BR)+1 or CANCELAR_PROCESSAMENTO: return
    voz_escolhida = VOZES_PT_BR[escolha_voz_idx - 1]

    texto_para_converter = ler_arquivo_texto(caminho_txt_processado)
    if not texto_para_converter.strip() or CANCELAR_PROCESSAMENTO:
        print("❌ Arquivo de texto processado vazio."); return

    print("\n⏳ Dividindo texto para TTS...")
    partes_texto = dividir_texto_para_tts(texto_para_converter) # Use a versão otimizada desta função
    total_partes = len(partes_texto)

    if total_partes == 0:
        print("❌ Nenhuma parte de texto para converter após divisão."); return

    print(f"📊 Texto dividido em {total_partes} parte(s) para TTS.")
    print("   Pressione CTRL+C para tentar cancelar a qualquer momento.")

    path_txt_obj = Path(caminho_txt_processado)
    nome_base_audio = limpar_nome_arquivo(path_txt_obj.stem.replace("_formatado", ""))
    dir_saida_audio = path_txt_obj.parent / f"{nome_base_audio}_AUDIO_TTS"
    dir_saida_audio.mkdir(parents=True, exist_ok=True)

    start_time_total_tts = time.monotonic()
    arquivos_mp3_temporarios_nomes = [str(dir_saida_audio / f"temp_{nome_base_audio}_{i+1:04d}.mp3") for i in range(total_partes)]

    print("\n🎙️ Iniciando conversão TTS das partes...")

    # AJUSTE ESTE VALOR PARA O TERMUX! (Ex: 5, 8, 10)
    LOTE_MAXIMO_TAREFAS_CONCORRENTES = 8

    resultados_conversao = [False] * total_partes # Usaremos para rastrear sucesso/falha
    arquivos_mp3_sucesso = []
    
    semaphore_api_calls = asyncio.Semaphore(LOTE_MAXIMO_TAREFAS_CONCORRENTES)
    tarefas_gerais_tts = []

    # Criar todas as tarefas
    for idx_global_parte in range(total_partes):
        if CANCELAR_PROCESSAMENTO: break
        parte_txt = partes_texto[idx_global_parte]
        caminho_temp_mp3 = arquivos_mp3_temporarios_nomes[idx_global_parte]

        async def converter_com_semaforo(p_txt, voz, c_temp, idx_original_tarefa, total):
            async with semaphore_api_calls:
                if CANCELAR_PROCESSAMENTO: return (idx_original_tarefa, False) # Retorna índice e status
                # Passa o índice original para poder mapear o resultado
                sucesso = await _converter_chunk_tts(p_txt, voz, c_temp, idx_original_tarefa + 1, total)
                return (idx_original_tarefa, sucesso)

        # Guarda o índice original junto com a tarefa para mapeamento posterior
        tarefa = asyncio.create_task(
            converter_com_semaforo(
                parte_txt, voz_escolhida, caminho_temp_mp3, idx_global_parte, total_partes
            )
        )
        tarefas_gerais_tts.append(tarefa)
    
    if CANCELAR_PROCESSAMENTO:
        print("🚫 Criação de tarefas TTS interrompida.")
        for t in tarefas_gerais_tts: t.cancel()
    
    # --- INÍCIO DA LÓGICA DE PROGRESSO LEVE ---
    partes_concluidas = 0
    partes_com_falha = 0
    tempo_ultima_atualizacao_progresso = time.monotonic()

    def imprimir_progresso():
        porcentagem = (partes_concluidas / total_partes) * 100 if total_partes > 0 else 0
        # \r para voltar ao início da linha e sobrescrever
        # sys.stdout.write para evitar nova linha automática do print
        sys.stdout.write(f"\r   Progresso TTS: {partes_concluidas}/{total_partes} ({porcentagem:.1f}%) | Falhas: {partes_com_falha}   ")
        sys.stdout.flush() # Garante que a saída seja exibida imediatamente

    if tarefas_gerais_tts:
        print(f"📦 Processando {len(tarefas_gerais_tts)} tarefas TTS com concorrência de {LOTE_MAXIMO_TAREFAS_CONCORRENTES}...")
        imprimir_progresso() # Imprime o estado inicial (0%)

        for future_task in asyncio.as_completed(tarefas_gerais_tts):
            if CANCELAR_PROCESSAMENTO:
                for t_restante in tarefas_gerais_tts:
                    if not t_restante.done(): t_restante.cancel()
                break
            try:
                idx_original, sucesso_tarefa = await future_task # Agora esperamos tupla (índice, sucesso)
                
                if sucesso_tarefa:
                    resultados_conversao[idx_original] = True
                else:
                    resultados_conversao[idx_original] = False
                    partes_com_falha += 1
                
            except asyncio.CancelledError:
                # Não incrementa falha aqui, pois foi cancelado, não uma falha de conversão
                pass 
            except Exception as e_task:
                print(f"\n   ⚠️ Erro inesperado ao processar tarefa TTS: {e_task}")
                # Se a tarefa lançou uma exceção não tratada, contamos como falha
                # Precisaríamos saber o índice da tarefa que falhou, o que é difícil aqui sem alterar mais
                partes_com_falha +=1 

            partes_concluidas += 1 # Incrementa partes processadas (concluídas ou falhadas)
            
            # Atualiza o progresso no console com menos frequência
            agora = time.monotonic()
            if agora - tempo_ultima_atualizacao_progresso > 0.3 or partes_concluidas == total_partes: # Atualiza a cada 0.3s ou no final
                imprimir_progresso()
                tempo_ultima_atualizacao_progresso = agora
        
        sys.stdout.write("\n") # Nova linha após a conclusão do progresso
    # --- FIM DA LÓGICA DE PROGRESSO LEVE ---

    # Verificação final e coleta de arquivos de sucesso (como antes)
    print("\n🔍 Verificando arquivos gerados...")
    for i in range(total_partes): # Revalida baseado nos arquivos e no array de resultados
        if resultados_conversao[i] and Path(arquivos_mp3_temporarios_nomes[i]).exists() and Path(arquivos_mp3_temporarios_nomes[i]).stat().st_size > 200:
            if arquivos_mp3_temporarios_nomes[i] not in arquivos_mp3_sucesso: # Evita duplicatas
                arquivos_mp3_sucesso.append(arquivos_mp3_temporarios_nomes[i])
        else: # Se não foi sucesso ou o arquivo não é válido, garante que resultado_conversao seja False
            resultados_conversao[i] = False


    if CANCELAR_PROCESSAMENTO:
        print("🚫 Processo de TTS interrompido. Limpando arquivos temporários...")
    elif not arquivos_mp3_sucesso and not any(resultados_conversao):
        print("❌ Nenhuma parte foi convertida com sucesso.")


    if arquivos_mp3_sucesso:
        arquivo_final_mp3 = dir_saida_audio / f"{nome_base_audio}_COMPLETO.mp3"
        print(f"\n🔄 Unificando {len(arquivos_mp3_sucesso)} arquivos de áudio...")
        if unificar_arquivos_audio_ffmpeg(arquivos_mp3_sucesso, str(arquivo_final_mp3)):
            tempo_total_tts = time.monotonic() - start_time_total_tts
            print(f"🎉 Conversão TTS concluída em {tempo_total_tts:.2f}s!")
            print(f"   Áudio final: {arquivo_final_mp3}")
            print("🧹 Limpando temporários TTS unificados...")
            for temp_f_success in arquivos_mp3_sucesso:
                Path(temp_f_success).unlink(missing_ok=True)
            if not CANCELAR_PROCESSAMENTO and await obter_confirmacao("Deseja aplicar melhorias (acelerar, converter para MP4) ao áudio gerado?"):
                await _processar_melhoria_de_audio_video(str(arquivo_final_mp3))
        else:
            print("❌ Falha ao unificar os áudios. Os arquivos parciais permanecem.")
            for f_temp in arquivos_mp3_sucesso: print(f"   - {f_temp}")
    elif not CANCELAR_PROCESSAMENTO :
        print("❌ Nenhum arquivo de áudio foi gerado com sucesso.")

    print("🧹 Limpando arquivos temporários restantes (se houver)...")
    for i in range(total_partes):
        if not resultados_conversao[i] and Path(arquivos_mp3_temporarios_nomes[i]).exists():
            Path(arquivos_mp3_temporarios_nomes[i]).unlink(missing_ok=True)

    if not CANCELAR_PROCESSAMENTO:
        await aioconsole.ainput("\nPressione ENTER para voltar ao menu...")

async def testar_vozes_tts():
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False
    while True:
        if CANCELAR_PROCESSAMENTO: break
        opcoes_teste_voz = {str(i+1): voz for i, voz in enumerate(VOZES_PT_BR)}; opcoes_teste_voz[str(len(VOZES_PT_BR)+1)] = "Voltar"
        escolha_idx = await exibir_banner_e_menu("TESTAR VOZES", opcoes_teste_voz)
        if escolha_idx == len(VOZES_PT_BR)+1 or CANCELAR_PROCESSAMENTO: break
        
        voz_selecionada = VOZES_PT_BR[escolha_idx - 1]; texto_exemplo = "Olá! Esta é uma demonstração da minha voz para você avaliar."
        print(f"\n🎙️ Testando voz: {voz_selecionada}...")
        
        sistema = detectar_sistema(); 
        pasta_testes = Path.home() / "Downloads" / "TTS_Testes_Voz" # Padrão
        if sistema['termux'] or sistema['android']: 
            # Caminho mais comum no Android via Termux
            pasta_testes = Path("/storage/emulated/0/Download/TTS_Testes_Voz")
            # Verifica se a pasta pai (Download) existe, senão tenta o diretório home do Termux
            if not pasta_testes.parent.exists():
                 print(f"⚠️ Pasta {pasta_testes.parent} não encontrada. Tentando no diretório interno do Termux.")
                 pasta_testes = Path.home() / "TTS_Testes_Voz"

        # --- ADICIONADO: Feedback sobre a pasta e permissões ---
        print(f"   Tentando salvar em: {pasta_testes}")
        if sistema['termux'] or sistema['android']:
            print("   Lembre-se: No Termux, execute 'termux-setup-storage' e conceda permissão para acesso ao armazenamento.")
        # --- FIM DA ADIÇÃO ---

        try:
            pasta_testes.mkdir(parents=True, exist_ok=True)
        except OSError as e_mkdir:
             print(f"❌ Erro ao criar/acessar a pasta de testes: {e_mkdir}")
             print(f"   Verifique as permissões para '{pasta_testes}'.")
             await asyncio.sleep(3)
             continue # Pula para a próxima iteração do loop de teste de voz

        nome_arquivo_teste = limpar_nome_arquivo(f"teste_{voz_selecionada}.mp3")
        caminho_arquivo_teste = pasta_testes / nome_arquivo_teste
        
        try:
            # Chama _converter_chunk_tts atualizado
            if await _converter_chunk_tts(texto_exemplo, voz_selecionada, str(caminho_arquivo_teste), 1, 1):
                # Verifica novamente se o arquivo realmente existe após a função retornar True
                if caminho_arquivo_teste.exists() and caminho_arquivo_teste.stat().st_size > 50: # Reduz um pouco o limite mínimo para o teste
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
                     # A função retornou True, mas o arquivo não existe ou é inválido
                     print(f"❌ Erro: Conversão para {voz_selecionada} indicada como sucesso, mas arquivo final é inválido ou não encontrado.")
                     print(f"   Verifique permissões e logs de erro em _converter_chunk_tts.")
                     caminho_arquivo_teste.unlink(missing_ok=True) # Limpa se existir inválido
            else: 
                # A função retornou False
                print(f"❌ Falha ao gerar áudio de teste para {voz_selecionada} (ver logs acima).")
        
        except asyncio.CancelledError: 
            print("\n🚫 Teste de voz cancelado.")
            caminho_arquivo_teste.unlink(missing_ok=True) # Tenta limpar
            break # Sai do loop de teste de vozes
        except Exception as e_test: # Captura outros erros inesperados no teste
             print(f"\n❌ Erro inesperado durante o teste da voz {voz_selecionada}: {e_test}")
             import traceback
             traceback.print_exc()
             caminho_arquivo_teste.unlink(missing_ok=True) # Tenta limpar

        if not await obter_confirmacao("Testar outra voz?", default_yes=True):
            break
        if CANCELAR_PROCESSAMENTO: break

def obter_duracao_midia(caminho_arquivo: str) -> float:
    """Obtém a duração de um arquivo de mídia usando ffprobe."""
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

def dividir_midia_ffmpeg(input_path, duracao_total_seg, duracao_max_parte_seg, nome_base_saida, extensao_saida):
    """Divide um arquivo de mídia em partes menores usando FFmpeg (sem reencodar)."""
    if duracao_total_seg <= duracao_max_parte_seg:
        print(f"    ℹ️ Arquivo tem {duracao_total_seg/3600:.2f}h. Não precisa ser dividido (limite {duracao_max_parte_seg/3600:.1f}h).")
        # Se não precisa dividir, mas o formato de saída é diferente, ou apenas para consistência,
        # podemos copiar para o nome da "parte 1"
        output_single_part_path = f"{nome_base_saida}_parte1{extensao_saida}"
        try:
            # Usa copy2 para preservar metadados se possível
            shutil.copy2(input_path, output_single_part_path)
            print(f"    ✅ Arquivo copiado para: {output_single_part_path}")
            return [output_single_part_path] # Retorna lista com o único arquivo
        except Exception as e:
            print(f"    ❌ Erro ao copiar arquivo original para o nome da parte: {e}")
            return [] # Falhou

    num_partes = ceil(duracao_total_seg / duracao_max_parte_seg)
    print(f"\n    📄 Arquivo tem {duracao_total_seg/3600:.2f}h. Será dividido em {num_partes} partes de até {duracao_max_parte_seg/3600:.1f}h.")
    
    arquivos_gerados = []
    for i in range(num_partes):
        if CANCELAR_PROCESSAMENTO:
            print("    🚫 Divisão cancelada pelo usuário.")
            break
            
        inicio_seg = i * duracao_max_parte_seg
        # A duração da parte é min(duração_max, restante_do_arquivo)
        # Isso é tratado pelo -t do ffmpeg se o tempo final for menor que -t
        # Para garantir que a última parte não exceda o necessário, podemos calcular
        # a duração real desta parte, embora -t lide com isso.
        duracao_segmento_seg = min(duracao_max_parte_seg, duracao_total_seg - inicio_seg)
        if duracao_segmento_seg <= 0: # Evita criar partes vazias se houver erro de cálculo
             continue
             
        output_path_parte = f"{nome_base_saida}_parte{i+1}{extensao_saida}"
        
        print(f"    🎞️ Criando parte {i+1}/{num_partes}...")
        comando = [
            FFMPEG_BIN, '-y', 
            '-ss', str(inicio_seg),      # Ponto inicial
            '-i', input_path,
            '-t', str(duracao_segmento_seg), # Duração MÁXIMA desta parte (FFmpeg corta no fim do arquivo se for menor)
            '-c', 'copy',               # Sem reencodar, muito mais rápido
            output_path_parte
        ]
        # Chamamos _executar_ffmpeg_comando SEM total_duration, pois -c copy não dá progresso percentual
        if _executar_ffmpeg_comando(comando, f"criação da parte {i+1}"):
            arquivos_gerados.append(output_path_parte)
        else:
            print(f"    ❌ Falha ao criar parte {i+1}. A divisão pode estar incompleta.")
            # Decide se continua ou para. Por ora, continua.
    return arquivos_gerados

async def _processar_melhoria_de_audio_video(caminho_arquivo_entrada: str):
    global CANCELAR_PROCESSAMENTO
    CANCELAR_PROCESSAMENTO = False
    
    path_entrada_obj = Path(caminho_arquivo_entrada)
    if not path_entrada_obj.exists():
        print(f"❌ Arquivo de entrada não encontrado: {caminho_arquivo_entrada}")
        return

    print(f"\n⚡ Melhorando arquivo: {path_entrada_obj.name}")

    # Velocidade
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

    # Formato de saída
    is_video_input = path_entrada_obj.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.webm']
    formato_saida = ""
    if is_video_input:
        formato_saida = ".mp4" if await obter_confirmacao("Manter vídeo (MP4)? (S=vídeo, N=áudio MP3)", True) else ".mp3"
    else: 
        formato_saida = ".mp4" if await obter_confirmacao("Gerar vídeo com tela preta (MP4)? (S=vídeo, N=áudio MP3)", False) else ".mp3"
    if CANCELAR_PROCESSAMENTO: return

    # Resolução para vídeo de saída (AGORA FIXA)
    resolucao_video_saida_str = "" 
    if formato_saida == ".mp4":
        resolucao_video_saida_str = RESOLUCOES_VIDEO['1'][0] # Fixa em 360p ("640x360")
        desc_res_fixa = f"{RESOLUCOES_VIDEO['1'][1]} ({RESOLUCOES_VIDEO['1'][0]})" # "360p (640x360)"
        print(f"ℹ️  Gerando MP4 com resolução padrão: {desc_res_fixa}")
        # Não há mais menu de seleção aqui
    
    if CANCELAR_PROCESSAMENTO: return

    # Divisão de arquivo
    duracao_total_seg = obter_duracao_midia(str(path_entrada_obj)) # Garanta que obter_duracao_midia está definida
    if duracao_total_seg == 0 and formato_saida == ".mp4":
        print("❌ Não foi possível obter a duração do arquivo. Não é possível criar vídeo MP4.")
        return

    dividir = False; duracao_max_parte = LIMITE_SEGUNDOS_DIVISAO
    if duracao_total_seg > duracao_max_parte: # Corrigido: usar duracao_max_parte aqui, não LIMITE_SEGUNDOS_DIVISAO diretamente na condição
        if await obter_confirmacao(f"O arquivo tem {duracao_total_seg/3600:.2f}h. Dividir em partes de até {duracao_max_parte/3600:.0f}h?", True): # Usar duracao_max_parte
            dividir = True
            if await obter_confirmacao("Definir tamanho personalizado por parte (em horas)?", False):
                while True:
                    try:
                        # Usar LIMITE_SEGUNDOS_DIVISAO para o prompt do máximo
                        horas_str = await aioconsole.ainput(f"Horas por parte (ex: 2.5, máx {LIMITE_SEGUNDOS_DIVISAO/3600:.0f}): ")
                        horas_parte = float(horas_str)
                        # Validar contra o limite máximo original
                        if 0.5 <= horas_parte <= LIMITE_SEGUNDOS_DIVISAO/3600: 
                            duracao_max_parte = horas_parte * 3600 # Atualiza duracao_max_parte
                            break
                        else: print(f"⚠️ Horas devem estar entre 0.5 e {LIMITE_SEGUNDOS_DIVISAO/3600:.0f}.")
                    except ValueError: print("⚠️ Número inválido.")
                    except asyncio.CancelledError: return
    if CANCELAR_PROCESSAMENTO: return

    # Preparar nome de saída
    nome_proc = limpar_nome_arquivo(f"{path_entrada_obj.stem}_veloc{str(velocidade).replace('.','_')}")
    dir_out = path_entrada_obj.parent / f"{nome_proc}_PROCESSADO"; dir_out.mkdir(parents=True, exist_ok=True)
    tmp_acel = dir_out / f"temp_acel{path_entrada_obj.suffix}"; entrada_prox = ""; dur_acel = 0.0

    # 1. Acelerar
    if velocidade != 1.0:
        if not acelerar_midia_ffmpeg(str(path_entrada_obj), str(tmp_acel), velocidade, is_video_input): # Garanta que acelerar_midia_ffmpeg está definida
            print("❌ Falha acelerar."); tmp_acel.unlink(missing_ok=True); return
        entrada_prox = str(tmp_acel); dur_acel = obter_duracao_midia(entrada_prox)
        if dur_acel == 0 and formato_saida == ".mp4": 
            print("❌ Duração não obtida pós aceleração. Abortando MP4."); tmp_acel.unlink(missing_ok=True); return
    else: 
        entrada_prox = str(path_entrada_obj); dur_acel = duracao_total_seg
    
    if CANCELAR_PROCESSAMENTO: 
        if Path(entrada_prox).resolve() != path_entrada_obj.resolve() and Path(entrada_prox).exists(): # Só remove se for temporário
            Path(entrada_prox).unlink(missing_ok=True)
        return

    # 2. Converter para MP4 (se áudio -> MP4)
    entrada_div = entrada_prox; tmp_vid_gerado = None
    if formato_saida == ".mp4" and not is_video_input:
        tmp_vid_gerado = dir_out / "temp_video_from_audio.mp4"
        if not criar_video_com_audio_ffmpeg(entrada_prox, str(tmp_vid_gerado), dur_acel, resolucao_video_saida_str): # Garanta que criar_video_com_audio_ffmpeg está definida
            print("❌ Falha criar vídeo."); 
            if Path(entrada_prox).resolve() != path_entrada_obj.resolve(): Path(entrada_prox).unlink(missing_ok=True) 
            tmp_vid_gerado.unlink(missing_ok=True); return
        entrada_div = str(tmp_vid_gerado)
        # Remove o arquivo temporário de aceleração se um vídeo foi gerado a partir dele E não era o arquivo original
        if Path(entrada_prox).resolve() != path_entrada_obj.resolve() and Path(entrada_prox).resolve() != Path(tmp_vid_gerado).resolve():
             Path(entrada_prox).unlink(missing_ok=True)

    if CANCELAR_PROCESSAMENTO:
        # Limpa temporários
        if Path(entrada_prox).resolve() != path_entrada_obj.resolve() and Path(entrada_prox).exists() : Path(entrada_prox).unlink(missing_ok=True)
        if tmp_vid_gerado and tmp_vid_gerado.exists(): tmp_vid_gerado.unlink(missing_ok=True)
        return
    
    # 3. Dividir
    nome_base_final = dir_out / nome_proc; arquivos_finais = []
    if dividir:
        arquivos_finais = dividir_midia_ffmpeg(entrada_div, dur_acel, duracao_max_parte, str(nome_base_final), formato_saida) # Garanta que dividir_midia_ffmpeg está definida
    else:
        arq_final_unico = f"{nome_base_final}{formato_saida}"
        try:
            p_entrada_div = Path(entrada_div)
            # Se a entrada para divisão é o arquivo original E o formato de saída é o mesmo, apenas COPIAMOS.
            if p_entrada_div.resolve() == path_entrada_obj.resolve() and path_entrada_obj.suffix.lower() == formato_saida: 
                shutil.copy(entrada_div, arq_final_unico)
            # Se o arquivo de entrada para divisão existe (e não é o caso acima), MOVEMOS
            elif p_entrada_div.exists(): 
                shutil.move(entrada_div, arq_final_unico)
            # Caso especial: Entrada é vídeo, saída é MP3, e nenhuma operação de movimento/cópia ocorreu ainda (pode acontecer se não houver aceleração)
            elif formato_saida == ".mp3" and is_video_input and p_entrada_div.exists(): 
                 if not _executar_ffmpeg_comando([FFMPEG_BIN,'-y','-i',str(p_entrada_div),'-vn','-q:a','2',arq_final_unico], "Extraindo MP3", dur_acel): # Usar _executar_ffmpeg_comando
                      print(f"❌ Falha ao extrair áudio para {arq_final_unico}")
                      # Se a entrada para divisão era um temporário, removemos se a extração falhar
                      if p_entrada_div.resolve() != path_entrada_obj.resolve(): p_entrada_div.unlink(missing_ok=True)
                      return 
            elif not Path(arq_final_unico).exists(): # Se o arquivo final não foi criado por nenhum dos caminhos acima
                 print(f"⚠️ Arquivo de processamento intermediário '{entrada_div}' não encontrado ou não processado para '{arq_final_unico}'.")

            if Path(arq_final_unico).exists(): 
                print(f"✅ Arquivo final salvo: {arq_final_unico}")
                arquivos_finais.append(arq_final_unico)
            # else: # Se ainda não existe, uma mensagem de erro já teria sido impressa ou a lógica acima falhou
                # print(f"DEBUG: Arquivo final '{arq_final_unico}' não foi criado e não se encaixou nos casos de erro.")


        except Exception as e_final: print(f"❌ Erro ao finalizar arquivo único: {e_final}")

    # Limpeza do arquivo que foi entrada para divisão, APENAS se ele foi um temporário e não o arquivo original
    # e também não é o próprio arquivo final (caso não haja divisão e o arquivo só foi renomeado/movido)
    p_entrada_div_obj = Path(entrada_div)
    if p_entrada_div_obj.resolve() != path_entrada_obj.resolve() and \
       (not arquivos_finais or p_entrada_div_obj.resolve() != Path(arquivos_finais[0]).resolve() if arquivos_finais else True) and \
       p_entrada_div_obj.exists():
        p_entrada_div_obj.unlink(missing_ok=True)
    
    if arquivos_finais: 
        print("\n🎉 Processo de melhoria concluído!")
        for f_gerado in arquivos_finais: print(f"   -> {f_gerado}")
    else: 
        print("❌ Nenhum arquivo foi gerado no processo de melhoria.")
    
    await aioconsole.ainput("\nPressione ENTER para voltar ao menu...")

async def menu_melhorar_audio_video():
    while True:
        caminho_arquivo = await _selecionar_arquivo_para_processamento(['.mp3', '.wav', '.m4a', '.ogg', '.opus', '.flac', '.mp4', '.mkv', '.avi', '.mov', '.webm'])
        if not caminho_arquivo or CANCELAR_PROCESSAMENTO: break
        await _processar_melhoria_de_audio_video(caminho_arquivo)
        if CANCELAR_PROCESSAMENTO: break
        if not await obter_confirmacao("Melhorar outro arquivo?", default_yes=False): break

async def menu_converter_mp3_para_mp4():
    """Menu para converter MP3 para MP4 com tela preta, resolução fixa 360p.""" # Descrição atualizada
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False

    resolucao_fixa_str = RESOLUCOES_VIDEO['1'][0]
    resolucao_fixa_desc = RESOLUCOES_VIDEO['1'][1]

    while True:
        caminho_mp3 = await _selecionar_arquivo_para_processamento(['.mp3'])
        if not caminho_mp3 or CANCELAR_PROCESSAMENTO: break

        path_mp3_obj = Path(caminho_mp3)
        duracao_mp3 = obter_duracao_midia(caminho_mp3)
        if duracao_mp3 <= 0:
            print("❌ Não foi possível obter a duração do MP3 ou é inválida.")
            await asyncio.sleep(2); continue

        print(f"\nℹ️  Convertendo MP3 para MP4 com resolução fixa: {resolucao_fixa_desc} ({resolucao_fixa_str}).")

        if CANCELAR_PROCESSAMENTO: break

        nome_video_saida = limpar_nome_arquivo(f"{path_mp3_obj.stem}_VIDEO_{resolucao_fixa_desc}.mp4")
        caminho_video_saida = path_mp3_obj.with_name(nome_video_saida)

        # --- CHAMADA CORRIGIDA: Remover usar_progresso_leve=True ---
        if criar_video_com_audio_ffmpeg(caminho_mp3, str(caminho_video_saida), duracao_mp3, resolucao_fixa_str):
        # --- FIM DA CORREÇÃO ---
            print(f"✅ Vídeo gerado: {caminho_video_saida}")
        else:
            print(f"❌ Falha ao gerar vídeo a partir de {path_mp3_obj.name}")

        if not await obter_confirmacao("Converter outro MP3 para MP4?", default_yes=False):
            break
        if CANCELAR_PROCESSAMENTO: break

    if not CANCELAR_PROCESSAMENTO:
        await aioconsole.ainput("\nPressione ENTER para voltar ao menu...")

async def menu_dividir_video_existente():
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False
    while True:
        caminho_video_entrada = await _selecionar_arquivo_para_processamento(['.mp4', '.mkv', '.avi', '.mov', '.webm'])
        if not caminho_video_entrada or CANCELAR_PROCESSAMENTO: break
        path_video_obj = Path(caminho_video_entrada); duracao_total_seg = obter_duracao_midia(str(path_video_obj))
        if duracao_total_seg <= LIMITE_SEGUNDOS_DIVISAO:
            print(f"ℹ️ Vídeo '{path_video_obj.name}' não precisa ser dividido.");
            if not await obter_confirmacao("Selecionar outro vídeo?", default_yes=False): break; continue
        print(f"Vídeo '{path_video_obj.name}' tem {duracao_total_seg/3600:.2f}h.")
        duracao_max_parte = LIMITE_SEGUNDOS_DIVISAO
        if await obter_confirmacao("Tamanho personalizado por parte (horas)?", default_yes=False):
            while True:
                try:
                    horas_str = await aioconsole.ainput(f"Horas/parte (0.5-{LIMITE_SEGUNDOS_DIVISAO/3600:.0f}): ")
                    horas_parte = float(horas_str)
                    if 0.5 <= horas_parte <= LIMITE_SEGUNDOS_DIVISAO/3600: duracao_max_parte = horas_parte * 3600; break
                    else: print(f"⚠️ Horas entre 0.5 e {LIMITE_SEGUNDOS_DIVISAO/3600:.0f}.")
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
    - Arquivos PDF/EPUB são convertidos para TXT formatado primeiro (_formatado.txt).
    - Se não estiver no Android, você poderá editar o TXT formatado antes do TTS.
    - Escolha uma voz para a conversão.
    - O áudio será salvo em uma subpasta (ex: NOME_LIVRO_AUDIO_TTS).
    - Após a conversão, você pode optar por melhorar o áudio gerado (item 3).

2.  TESTAR VOZES TTS:
    - Ouça amostras das vozes disponíveis para escolher a melhor.
    - Os áudios de teste são salvos na sua pasta de Downloads (subpasta TTS_Testes_Voz).

3.  MELHORAR ÁUDIO/VÍDEO (Velocidade, Formato):
    - Nome antigo: "MUDAR VELOCIDADE MP3 E GERAR MP4"
    - Selecione um arquivo de áudio ou vídeo existente.
    - Ajuste a velocidade de reprodução (ex: 1.5 para 1.5x).
    - Escolha o formato de saída: MP3 (áudio) ou MP4 (vídeo com tela preta/original).
    - MP4 gerado usa resolução padrão 360p automaticamente.
    - Arquivos longos (>12h por padrão) podem ser divididos automaticamente ou com tamanho customizado.
    - O resultado é salvo em uma subpasta (ex: NOME_ARQUIVO_PROCESSADO).

4.  DIVIDIR VÍDEO LONGO:
    - Selecione um arquivo de vídeo (MP4, MKV, etc.).
    - Ideal para vídeos com mais de 12 horas (ou limite customizado).
    - Divide o vídeo em partes menores sem recompressão (processo rápido).
    - As partes são salvas na mesma pasta do original com sufixo _dividido_parteX.

5.  CONVERTER MP3 PARA MP4 (Tela Preta):
    - Selecione um arquivo MP3.
    - Gera um vídeo MP4 com tela preta e o áudio do MP3.
    - Usa resolução padrão 360p automaticamente.
    - Mostra progresso durante a conversão.

6.  ATUALIZAR SCRIPT:
    - Baixa a versão mais recente do script do GitHub (requer conexão com a internet).
    - Cria um backup do script atual antes de atualizar.

7.  AJUDA:
    - Exibe este guia de uso.

0.  SAIR:
    - Encerra o script.

OBSERVAÇÕES IMPORTANTES:
- Pressione CTRL+C para tentar cancelar operações longas (TTS, FFmpeg).
- FFmpeg e Poppler (para PDFs) são dependências externas importantes. O script tenta ajudar na instalação se não encontrados.
- No Android/Termux, pode ser necessário conceder permissão de armazenamento executando `termux-setup-storage` no terminal do Termux antes de usar o script.
- Use `termux-wake-lock` antes de iniciar conversões TTS longas no Termux para evitar que o Android suspenda o processo. Use `termux-wake-unlock` depois.
- Arquivos são geralmente salvos na mesma pasta do arquivo original ou em subpastas criadas pelo script.
    """)
    await aioconsole.ainput("Pressione ENTER para voltar ao menu...")

async def atualizar_script():
    global CANCELAR_PROCESSAMENTO; CANCELAR_PROCESSAMENTO = False
    limpar_tela(); print("🔄 ATUALIZAÇÃO DO SCRIPT")
    if not await obter_confirmacao("Baixar versão mais recente do GitHub?"): print("❌ Cancelado."); await asyncio.sleep(1); return
    print("\n🔄 Baixando..."); script_atual_path = Path(__file__).resolve(); script_backup_path = script_atual_path.with_suffix(script_atual_path.suffix + ".backup")
    try: shutil.copy2(script_atual_path, script_backup_path); print(f"✅ Backup: {script_backup_path.name}")
    except Exception as e_backup:
        print(f"⚠️ Sem backup: {e_backup}");
        if not await obter_confirmacao("Continuar sem backup?", default_yes=False): return
    url_script = "https://raw.githubusercontent.com/JonJonesBR/Conversor_TTS/main/Conversor_TTS_com_MP4_09.04.2025.py" # AJUSTE URL!
    try:
        print(f"Baixando de: {url_script}"); response = requests.get(url_script, timeout=30); response.raise_for_status()
        with open(script_atual_path, 'wb') as f: f.write(response.content)
        print("✅ Script atualizado! Reiniciando..."); await aioconsole.ainput("Pressione ENTER para reiniciar...")
        os.execl(sys.executable, sys.executable, str(script_atual_path), *sys.argv[1:])
    except requests.exceptions.RequestException as e_req: print(f"\n❌ Erro de rede: {e_req}")
    except Exception as e_update: print(f"\n❌ Erro na atualização: {e_update}")
    if script_backup_path.exists():
        print("\n🔄 Restaurando backup...");
        try: shutil.copy2(script_backup_path, script_atual_path); print("✅ Backup restaurado!"); os.remove(script_backup_path)
        except Exception as e_restore: print(f"❌ Erro ao restaurar: {e_restore}. Backup: {script_backup_path}")
    await aioconsole.ainput("\nPressione ENTER para continuar...")

# ================== FUNÇÃO MAIN E LOOP PRINCIPAL ==================

async def main_loop():
    global CANCELAR_PROCESSAMENTO; detectar_sistema(); verificar_dependencias_essenciais()
    if sys.platform == 'win32' and sys.version_info >= (3,8) : pass
    opcoes_principais = {
        '1': "🚀 CONVERTER TEXTO PARA ÁUDIO (TTS)", '2': "🎙️ TESTAR VOZES TTS",
        '3': "⚡ MUDAR VELOCIDADE MP3 E GERAR MP4", '4': "🎞️ DIVIDIR VÍDEO LONGO",
        '5': "🎬 CONVERTER MP3 PARA MP4 (Tela Preta)", '6': "🔄 ATUALIZAR SCRIPT",
        '7': "❓ AJUDA", '0': "🚪 SAIR"
    }
    while True:
        CANCELAR_PROCESSAMENTO = False
        try:
            escolha = await exibir_banner_e_menu("MENU PRINCIPAL", opcoes_principais)
            if escolha == 1: await iniciar_conversao_tts()
            elif escolha == 2: await testar_vozes_tts()
            elif escolha == 3: await menu_melhorar_audio_video()
            elif escolha == 4: await menu_dividir_video_existente()
            elif escolha == 5: await menu_converter_mp3_para_mp4()
            elif escolha == 6: await atualizar_script()
            elif escolha == 7: await exibir_ajuda()
            elif escolha == 0: print("\n👋 Obrigado por usar!"); break
        except asyncio.CancelledError: print("\n🚫 Operação cancelada. Voltando ao menu..."); CANCELAR_PROCESSAMENTO = True; await asyncio.sleep(0.1)
        except Exception as e_main:
            print(f"\n❌ Erro no loop principal: {e_main}"); import traceback; traceback.print_exc()
            await aioconsole.ainput("Pressione ENTER para tentar continuar...")

if __name__ == "__main__":
    # Lembre-se de renomear o arquivo se ele se chamar "code.py"
    if Path(__file__).name == "code.py":
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERRO DE NOME DE ARQUIVO: Por favor, renomeie este script para algo    !!!")
        print("!!! diferente de 'code.py' (ex: 'conversor_tts.py') para evitar conflitos !!!")
        print("!!! com módulos internos do Python.                                        !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1)
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt: print("\n\n⚠️ Programa interrompido (KeyboardInterrupt).")
    except Exception as e_global: print(f"\n❌ Erro global: {str(e_global)}"); import traceback; traceback.print_exc()
    finally: print("🔚 Script finalizado.")
