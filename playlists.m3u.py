# Importação de bibliotecas necessárias
import os  # Para operações com sistema de arquivos
import shutil  # Para operações avançadas com arquivos (como apagar diretórios)
import requests  # Para fazer requisições HTTP
from hashlib import md5  # Para calcular hash MD5 dos arquivos
import logging  # Para registrar logs do sistema
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)  # Para download paralelo
import time  # Para controlar pausas entre tentativas

# Configuração do sistema de logging (registro de eventos)
logging.basicConfig(
    level=logging.INFO,  # Nível mínimo de mensagens a serem registradas
    format="%(asctime)s - %(levelname)s - %(message)s",  # Formato das mensagens
    handlers=[
        logging.FileHandler("playlists.log"),  # Salva logs em arquivo
        logging.StreamHandler(),  # Mostra logs no console
    ],
)
# Cria um logger específico para este módulo
logger = logging.getLogger(__name__)

# Configurações globais do script
HEADERS = {
    # Cabeçalhos HTTP para simular um navegador Chrome
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "*/*",  # Aceita qualquer tipo de conteúdo
    "Connection": "keep-alive",  # Mantém a conexão ativa
}
# Diretório onde os arquivos serão salvos (dentro da pasta 'playlists' no diretório atual)
OUTPUT_DIR = os.path.join(os.getcwd(), "playlists")
TIMEOUT = 15  # Tempo máximo (em segundos) para esperar por uma resposta do servidor
RETRIES = 3  # Número máximo de tentativas para cada download
DELAY_BETWEEN_TRIES = 2  # Tempo de espera (em segundos) entre tentativas falhas
MAX_WORKERS = 5  # Número máximo de downloads simultâneos


def validate_url(url):
    """
    Valida se uma URL é válida antes de tentar o download.

    Parâmetros:
        url (str): A URL a ser validada

    Retorna:
        bool: True se a URL é válida, False caso contrário
    """
    # Verifica se a URL começa com http:// ou https://
    if not url.startswith(("http://", "https://")):
        logger.error(f"URL inválida: {url}")
        return False
    return True


def download_file(url, save_path, retries=RETRIES):
    """
    Faz o download de um arquivo com tratamento robusto de erros e múltiplas tentativas.

    Parâmetros:
        url (str): URL do arquivo a ser baixado
        save_path (str): Caminho local onde o arquivo será salvo
        retries (int): Número de tentativas (usa o valor padrão RETRIES se não informado)

    Retorna:
        bool: True se o download foi bem-sucedido, False caso contrário
    """
    # Primeiro valida a URL
    if not validate_url(url):
        return False

    # Loop de tentativas
    for attempt in range(retries):
        try:
            logger.info(f"Tentativa {attempt + 1}/{retries}: Baixando {url}")

            # Faz a requisição HTTP com stream=True para baixar em pedaços
            with requests.get(
                url, headers=HEADERS, timeout=TIMEOUT, stream=True
            ) as response:
                # Levanta exceção se o status não for bem-sucedido (ex: 404, 500)
                response.raise_for_status()

                # Cria o diretório se não existir
                os.makedirs(os.path.dirname(save_path), exist_ok=True)

                # Abre o arquivo para escrita em modo binário
                with open(save_path, "wb") as file:
                    # Escreve cada pedaço (chunk) do arquivo
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:  # Filtra chunks keep-alive
                            file.write(chunk)

                # Verifica se o arquivo não está vazio
                if os.path.getsize(save_path) > 0:
                    # Calcula hash MD5 do arquivo
                    with open(save_path, "rb") as file:
                        file_hash = md5(file.read()).hexdigest()
                    # Log de sucesso com informações do arquivo
                    logger.info(
                        f"Sucesso: {save_path} | Tamanho: {os.path.getsize(save_path)} bytes | Hash: {file_hash}"
                    )
                    return True

                # Se o arquivo estiver vazio, remove e loga aviso
                logger.warning(f"Arquivo vazio: {save_path}")
                os.remove(save_path)

        # Tratamento de erros específicos de requisição HTTP
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na tentativa {attempt + 1}: {str(e)}")
            if attempt < retries - 1:  # Se ainda houver tentativas
                time.sleep(DELAY_BETWEEN_TRIES)  # Aguarda antes de tentar novamente
        # Tratamento de outros erros inesperados
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}")
            if attempt < retries - 1:
                time.sleep(DELAY_BETWEEN_TRIES)

    # Se todas as tentativas falharem
    logger.error(f"Falha ao baixar após {retries} tentativas: {url}")
    return False


def main():
    """
    Função principal que coordena todo o processo de download.

    Retorna:
        bool: True se todos os downloads foram bem-sucedidos, False caso contrário
    """
    try:
        logger.info("Iniciando processo de download para playlists...")

        # Limpeza e preparação do diretório de saída
        # Remove o diretório se já existir
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
        # Cria o diretório vazio
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Configuração dos arquivos a serem baixados
        # Dicionário organizado por tipo de arquivo (m3u e xml.gz)
        files_config = {
            "m3u": {
                "epgbrasil.m3u": "http://m3u4u.com/m3u/3wk1y24kx7uzdevxygz7",
                "epgbrasilportugal.m3u": "http://m3u4u.com/m3u/782dyqdrqkh1xegen4zp",
                "epgportugal.m3u": "http://m3u4u.com/m3u/jq2zy9epr3bwxmgwyxr5",
                "PiauiTV.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/PiauiTV.m3u",
                "m3u@proton.me.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/m3u4u_proton.me.m3u",
                "playlist.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/playlist.m3u",
                "playlists.m3u": "https://gitlab.com/josielluz/playlists/-/raw/main/playlists.m3u",
                "pornstars.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/pornstars.m3u",
            },
            "xml.gz": {
                "epgbrasil.xml.gz": "http://m3u4u.com/epg/3wk1y24kx7uzdevxygz7",
                "epgbrasilportugal.xml.gz": "http://m3u4u.com/epg/782dyqdrqkh1xegen4zp",
                "epgportugal.xml.gz": "http://m3u4u.com/epg/jq2zy9epr3bwxmgwyxr5",
            },
        }

        # Processamento paralelo dos downloads
        # Cria um pool de threads para downloads simultâneos
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []  # Lista para armazenar as tarefas futuras

            # Para cada tipo de arquivo e cada arquivo dentro do tipo
            for ext, files in files_config.items():
                for filename, url in files.items():
                    # Monta o caminho completo do arquivo
                    save_path = os.path.join(OUTPUT_DIR, filename)
                    # Submete a tarefa de download ao executor
                    futures.append(executor.submit(download_file, url, save_path))

            # Aguarda a conclusão de todas as tarefas e coleta os resultados
            results = [future.result() for future in as_completed(futures)]

            # Verifica se algum download falhou
            if not all(results):
                logger.error("Alguns downloads falharam. Verifique o log.")
                return False

        # Se tudo ocorreu bem
        logger.info("Todos os downloads foram concluídos com sucesso!")
        return True

    # Tratamento de erros na função principal
    except Exception as e:
        logger.error(f"Erro no processo principal: {str(e)}")
        return False


# Ponto de entrada do script
if __name__ == "__main__":
    # Executa a função main() e encerra com código 0 (sucesso) ou 1 (falha)
    exit(0 if main() else 1)
