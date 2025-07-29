#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para download e gerenciamento de playlists de IPTV.

Funcionalidades:
- Download paralelo de múltiplas playlists
- Verificação de integridade dos arquivos
- Logging detalhado de operações
- Suporte a formatos M3U e XML.GZ (EPG)
- Tratamento robusto de erros
- Validação de URLs e conteúdos

Uso:
    python playlists.py [--output-dir DIRETÓRIO] [--max-workers THREADS]

Argumentos opcionais:
    --output-dir    Diretório para salvar os arquivos (padrão: diretório atual)
    --max-workers   Número máximo de threads para downloads paralelos (padrão: 5)
"""

import os
import shutil
import requests
from hashlib import md5
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import argparse
from typing import Dict, Tuple
import time
from logging.handlers import RotatingFileHandler

# ==============================================
# Configuração inicial
# ==============================================

# Configuração do sistema de logging (registro de eventos)
logging.basicConfig(
    level=logging.INFO,  # Nível mínimo de mensagens (INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formato das mensagens
    handlers=[
        # Handler para arquivo de log com rotação (1MB por arquivo, mantém 3 backups)
        RotatingFileHandler("playlists.log", maxBytes=1e6, backupCount=3),
        # Handler para exibir logs no console
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)  # Cria uma instância do logger

# Constantes de configuração padrão
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}  # Cabeçalho HTTP para simular navegador
DEFAULT_TIMEOUT = 10  # Tempo limite em segundos para requisições
DEFAULT_RETRIES = 3   # Número de tentativas para cada download
DEFAULT_MAX_WORKERS = 5  # Número máximo de threads paralelas

# ==============================================
# Classes de Exceção Personalizadas
# ==============================================

class DownloadError(Exception):
    """Exceção para erros durante o download"""
    pass

class InvalidURLError(Exception):
    """Exceção para URLs inválidas"""
    pass

class FileValidationError(Exception):
    """Exceção para validação de arquivos"""
    pass

# ==============================================
# Funções auxiliares
# ==============================================

def validate_url(url: str) -> bool:
    """
    Valida se a URL é válida e segura.
    
    Parâmetros:
        url (str): URL a ser validada
        
    Retorna:
        bool: True se a URL é válida, False caso contrário
    """
    return url.startswith(("http://", "https://"))

def validate_file_extension(file_path: str, expected_ext: str) -> bool:
    """
    Valida se o arquivo tem a extensão esperada.
    
    Parâmetros:
        file_path (str): Caminho do arquivo
        expected_ext (str): Extensão esperada (ex: '.m3u')
        
    Retorna:
        bool: True se a extensão é válida, False caso contrário
    """
    return file_path.lower().endswith(expected_ext.lower())

def is_valid_m3u(content: bytes) -> bool:
    """
    Verifica se o conteúdo é um arquivo M3U válido.
    
    Parâmetros:
        content (bytes): Conteúdo do arquivo
        
    Retorna:
        bool: True se for M3U válido, False caso contrário
    """
    return b"#EXTM3U" in content[:100]

def is_valid_xml_gz(content: bytes) -> bool:
    """
    Verifica se o conteúdo é um arquivo GZIP válido.
    
    Parâmetros:
        content (bytes): Conteúdo do arquivo
        
    Retorna:
        bool: True se for GZIP válido, False caso contrário
    """
    return content[:2] == b"\x1f\x8b"  # Assinatura magic number do GZIP

def verify_gzip(file_path: str) -> bool:
    """
    Verifica a integridade de um arquivo .gz.
    
    Parâmetros:
        file_path (str): Caminho do arquivo
        
    Retorna:
        bool: True se o arquivo é válido, False caso contrário
    """
    try:
        with gzip.open(file_path, 'rb') as f:
            f.read(1)  # Tenta ler um byte
        return True
    except Exception as e:
        logger.error(f"Erro ao verificar arquivo GZIP {file_path}: {e}")
        return False

# ==============================================
# Função principal de download
# ==============================================

def download_file(url: str, save_path: str, retries: int = DEFAULT_RETRIES, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Faz o download de um arquivo com tratamento de erros e tentativas.
    
    Parâmetros:
        url (str): Endereço do arquivo a ser baixado
        save_path (str): Caminho local para salvar o arquivo
        retries (int): Número de tentativas em caso de falha
        timeout (int): Tempo limite da requisição em segundos
        
    Retorna:
        bool: True se o download foi bem-sucedido, False caso contrário
        
    Levanta:
        InvalidURLError: Se a URL for inválida
        DownloadError: Se ocorrer erro durante o download
    """
    # Validação inicial da URL
    if not validate_url(url):
        error_msg = f"URL inválida: {url}"
        logger.error(error_msg)
        raise InvalidURLError(error_msg)

    # Tentativas de download
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Tentativa {attempt} de {retries}: Baixando de: {url}")
            
            # Faz a requisição HTTP com timeout
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            
            # Verifica código de status HTTP
            if response.status_code != 200:
                error_msg = f"Falha ao baixar {url}. Código: {response.status_code}"
                logger.error(error_msg)
                raise DownloadError(error_msg)
            
            # Valida o conteúdo baixado conforme a extensão
            content = response.content
            if validate_file_extension(save_path, '.m3u') and not is_valid_m3u(content):
                error_msg = f"Conteúdo M3U inválido em {url}"
                logger.error(error_msg)
                raise FileValidationError(error_msg)
                
            if validate_file_extension(save_path, '.xml.gz') and not is_valid_xml_gz(content):
                error_msg = f"Conteúdo GZIP inválido em {url}"
                logger.error(error_msg)
                raise FileValidationError(error_msg)
            
            # Salva o conteúdo no arquivo local
            with open(save_path, 'wb') as file:
                file.write(content)

            # Verificação pós-download
            if os.path.getsize(save_path) == 0:
                error_msg = f"Arquivo vazio: {save_path}"
                logger.error(error_msg)
                raise DownloadError(error_msg)
                
            # Verificação adicional para arquivos .gz
            if save_path.endswith('.xml.gz') and not verify_gzip(save_path):
                error_msg = f"Arquivo GZIP corrompido: {save_path}"
                logger.error(error_msg)
                raise FileValidationError(error_msg)

            # Log de sucesso
            file_size = os.path.getsize(save_path)
            logger.info(f"Download concluído: {save_path} ({file_size} bytes)")
            
            # Calcula hash MD5 para verificação de integridade
            with open(save_path, 'rb') as file:
                file_hash = md5(file.read()).hexdigest()
            logger.info(f"Hash MD5 do arquivo: {file_hash}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na tentativa {attempt} de {retries}: {str(e)}")
            if attempt < retries:
                wait_time = 2 ** attempt  # Backoff exponencial
                logger.info(f"Aguardando {wait_time} segundos antes de tentar novamente...")
                time.sleep(wait_time)
            else:
                logger.error(f"Falha após {retries} tentativas: {url}")
                return False

# ==============================================
# Função para limpar arquivos antigos
# ==============================================

def clean_old_files(output_dir: str) -> None:
    """
    Remove arquivos antigos (.m3u e .xml.gz) do diretório de saída.
    
    Parâmetros:
        output_dir (str): Diretório onde os arquivos estão armazenados
    """
    logger.info(f"Limpando arquivos antigos em {output_dir}...")
    for filename in os.listdir(output_dir):
        if filename.endswith(('.m3u', '.xml.gz')):
            file_path = os.path.join(output_dir, filename)
            try:
                os.remove(file_path)
                logger.info(f"Arquivo removido: {filename}")
            except Exception as e:
                logger.error(f"Erro ao remover {filename}: {e}")

# ==============================================
# Função para processar argumentos de linha de comando
# ==============================================

def parse_args() -> argparse.Namespace:
    """
    Processa argumentos de linha de comando.
    
    Retorna:
        argparse.Namespace: Objeto com os argumentos parseados
    """
    parser = argparse.ArgumentParser(description="Download de playlists IPTV")
    parser.add_argument(
        "--output-dir",
        default=os.getcwd(),
        help="Diretório para salvar os arquivos (padrão: diretório atual)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"Número máximo de threads (padrão: {DEFAULT_MAX_WORKERS})"
    )
    return parser.parse_args()

# ==============================================
# Função principal
# ==============================================

def main() -> None:
    """
    Função principal que orquestra o processo de download.
    """
    # Parseia argumentos de linha de comando
    args = parse_args()
    
    # Cria o diretório de saída se não existir
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Remove arquivos antigos
    clean_old_files(args.output_dir)
    
    # Dicionário com os arquivos a serem baixados
    files_to_download = {
        "m3u": {
            "epgbrasil.m3u": "http://m3u4u.com/m3u/3wk1y24kx7uzdevxygz7",
            "epgbrasilportugal.m3u": "http://m3u4u.com/m3u/782dyqdrqkh1xegen4zp",
            "epgportugal.m3u": "http://m3u4u.com/m3u/jq2zy9epr3bwxmgwyxr5",
            "PiauiTV.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/PiauiTV.m3u",
            "m3u@proton.me.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/m3u4u_proton.me.m3u",
            "playlist.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/playlist.m3u",
            "playlists.m3u": "https://gitlab.com/josielluz/playlists/-/raw/main/playlists.m3u",
            "pornstars.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/pornstars.m3u"
        },
        "xml.gz": {
            "epgbrasil.xml.gz": "http://m3u4u.com/epg/3wk1y24kx7uzdevxygz7",
            "epgbrasilportugal.xml.gz": "http://m3u4u.com/epg/782dyqdrqkh1xegen4zp",
            "epgportugal.xml.gz": "http://m3u4u.com/epg/jq2zy9epr3bwxmgwyxr5"
        }
    }

    logger.info("Iniciando downloads...")
    
    # Contadores para estatísticas
    success_count = 0
    failure_count = 0
    
    # Usa ThreadPool para downloads paralelos
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = []
        
        # Prepara todas as tarefas de download
        for ext, files in files_to_download.items():
            for filename, url in files.items():
                save_path = os.path.join(args.output_dir, filename)
                futures.append(executor.submit(download_file, url, save_path))
        
        # Processa os resultados conforme completam
        for future in as_completed(futures):
            try:
                if future.result():
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                logger.error(f"Erro durante o download: {e}")
                failure_count += 1
    
    # Log final com estatísticas
    logger.info(f"Downloads concluídos. Sucessos: {success_count}, Falhas: {failure_count}")
    
    # Verifica se houve falhas
    if failure_count > 0:
        logger.warning(f"Atenção: {failure_count} arquivos falharam no download")

# Ponto de entrada do script
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Script interrompido pelo usuário")
    except Exception as e:
        logger.critical(f"Erro crítico: {str(e)}", exc_info=True)
