"""
Configuração central de logging.

Regra de negócio: toda execução do sistema gera um arquivo de log em
data/logs/, com timestamp, para que seja possível auditar depois o que
rodou, quando, e se houve problema — sem precisar confiar na memória de
quem executou.
"""

import logging
import os
from datetime import datetime

PASTA_LOGS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "logs")


def configurar_logger(nome: str = "etl_ngr_see") -> logging.Logger:
    os.makedirs(PASTA_LOGS, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_log = os.path.join(PASTA_LOGS, f"execucao_{timestamp}.log")

    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # evita log duplicado se configurar_logger for chamado mais de uma vez

    formato = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    handler_arquivo = logging.FileHandler(caminho_log, encoding="utf-8")
    handler_arquivo.setFormatter(formato)
    logger.addHandler(handler_arquivo)

    handler_console = logging.StreamHandler()
    handler_console.setFormatter(formato)
    logger.addHandler(handler_console)

    logger.info(f"Log desta execução salvo em: {caminho_log}")
    return logger
