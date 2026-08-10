"""
Integracao com Supabase para registro de acoes (audit trail).

Este modulo esta PREPARADO mas DESATIVADO por padrao.
Para ativar:
  1. Crie uma conta no Supabase (https://supabase.com)
  2. Crie um projeto
  3. Crie a tabela 'etl_logs' no SQL Editor (schema abaixo)
  4. Preencha as credenciais em config_supabase()
  5. Chame SupabaseClient.ativar()

SCHEMA SQL para criar no Supabase:
─────────────────────────────────
CREATE TABLE etl_logs (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  sessao_id TEXT NOT NULL,
  arquivo_entrada TEXT,
  arquivo_saida TEXT,
  linhas_entrada INTEGER,
  linhas_saida INTEGER,
  etapas_executadas JSONB,
  duracao_segundos FLOAT,
  status TEXT,
  observacoes TEXT
);

CREATE INDEX idx_etl_logs_sessao ON etl_logs(sessao_id);
CREATE INDEX idx_etl_logs_created ON etl_logs(created_at DESC);
"""

import json
from datetime import datetime


class SupabaseClient:
    """
    Cliente Supabase para registro de acoes.
    Funciona em modo OFFLINE por padrao (grava em memoria/log).
    """

    _instancia = None
    _ativo = False
    _client = None
    _buffer = []

    @classmethod
    def ativar(cls, url: str, chave: str):
        """
        Ativa a integracao com Supabase.
        url: URL do projeto (ex: https://xxxxx.supabase.co)
        chave: anon key do projeto
        """
        try:
            from supabase import create_client
            cls._client = create_client(url, chave)
            cls._ativo = True
            cls._log_console("Integracao Supabase ATIVADA.")
        except ImportError:
            cls._ativo = False
            cls._log_console(
                "AVISO: pacote 'supabase' nao instalado. "
                "Instale com: pip install supabase"
            )
        except Exception as e:
            cls._ativo = False
            cls._log_console(f"AVISO: erro ao conectar Supabase: {e}")

    @classmethod
    def desativar(cls):
        cls._ativo = False
        cls._client = None
        cls._log_console("Integracao Supabase DESATIVADA.")

    @classmethod
    def registrar_execucao(cls, sessao_id: str, dados: dict):
        """
        Registra uma execucao de ETL.
        dados deve conter: arquivo_entrada, arquivo_saida, linhas_entrada,
        linhas_saida, etapas_executadas, duracao_segundos, status, observacoes
        """
        registro = {
            "sessao_id": sessao_id,
            "created_at": datetime.now().isoformat(),
            **dados,
        }

        # Sempre salva no buffer local
        cls._buffer.append(registro)

        # Se ativo, envia ao Supabase
        if cls._ativo and cls._client:
            try:
                cls._client.table("etl_logs").insert(registro).execute()
                cls._log_console(f"Registro enviado ao Supabase: sessao={sessao_id}")
            except Exception as e:
                cls._log_console(f"AVISO: falha ao enviar ao Supabase: {e}")
        else:
            cls._log_console(f"Registro salvo localmente: sessao={sessao_id} (Supabase offline)")

    @classmethod
    def obter_historico(cls, limite: int = 50) -> list:
        """Retorna historico de execucoes (do Supabase se ativo, senao do buffer local)."""
        if cls._ativo and cls._client:
            try:
                resp = (
                    cls._client.table("etl_logs")
                    .select("*")
                    .order("created_at", desc=True)
                    .limit(limite)
                    .execute()
                )
                return resp.data
            except Exception as e:
                cls._log_console(f"AVISO: erro ao consultar Supabase: {e}")

        return list(reversed(cls._buffer[-limite:]))

    @classmethod
    def esta_ativo(cls) -> bool:
        return cls._ativo

    @classmethod
    def _log_console(cls, msg: str):
        print(f"[SUPABASE] {msg}")


class AuditLogger:
    """
    Logger de auditoria que salva localmente e opcionalmente no Supabase.
    Usado pelo pipeline para registrar cada etapa executada.
    """

    def __init__(self, sessao_id: str = None):
        self.sessao_id = sessao_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.etapas = []
        self._timestamp_inicio = datetime.now()

    def registrar_etapa(self, nome: str, params: dict, resultado: str,
                        linhas_afetadas: int = 0):
        self.etapas.append({
            "etapa": nome,
            "params": params,
            "resultado": resultado,
            "linhas_afetadas": linhas_afetadas,
            "momento": datetime.now().isoformat(),
        })

    def finalizar(self, arquivo_entrada: str = "", arquivo_saida: str = "",
                  linhas_entrada: int = 0, linhas_saida: int = 0,
                  status: str = "sucesso", observacoes: str = ""):
        duracao = (datetime.now() - self._timestamp_inicio).total_seconds()

        dados = {
            "arquivo_entrada": arquivo_entrada,
            "arquivo_saida": arquivo_saida,
            "linhas_entrada": linhas_entrada,
            "linhas_saida": linhas_saida,
            "etapas_executadas": json.dumps(self.etapas, ensure_ascii=False),
            "duracao_segundos": round(duracao, 2),
            "status": status,
            "observacoes": observacoes,
        }

        SupabaseClient.registrar_execucao(self.sessao_id, dados)
