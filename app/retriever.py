import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("wapp_retriever")

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
CATALOG_PATH = KNOWLEDGE_DIR / "data_catalog.yaml"
GOLDEN_QUERIES_PATH = KNOWLEDGE_DIR / "golden_queries.json"

_golden_queries_cache: List[Dict[str, Any]] = []

def get_golden_queries() -> List[Dict[str, Any]]:
    global _golden_queries_cache
    if not _golden_queries_cache and GOLDEN_QUERIES_PATH.exists():
        try:
            with open(GOLDEN_QUERIES_PATH, "r", encoding="utf-8") as f:
                _golden_queries_cache = json.load(f)
        except Exception as e:
            logger.error(f"Erro carregando golden queries: {e}")
    return _golden_queries_cache

def detect_scope_from_question(question: str) -> str:
    """Identifica o escopo/órgão a partir de sinônimos conhecidos."""
    q_lower = question.lower()
    
    if any(k in q_lower for k in ["prf", "policia rodoviaria", "polícia rodoviária", "dprf", "patrulha"]):
        return "prf"
    if any(k in q_lower for k in ["dnit", "transporte", "rodovias"]):
        return "dnit"
    if any(k in q_lower for k in ["dpu", "defensoria"]):
        return "dpu"
    if any(k in q_lower for k in ["fnde", "educacao"]):
        return "fnde"
    if any(k in q_lower for k in ["mj", "ministerio da justica", "ministério da justiça", "justica"]):
        return "mj"
    if any(k in q_lower for k in ["incra", "cervello", "reforma agraria"]):
        return "incra"
    if any(k in q_lower for k in ["caesb", "saneamento", "agua", "esgoto"]):
        return "caesb"
    if any(k in q_lower for k in ["telefonia", "ligacoes", "ligações", "chamadas", "atendidas", "perdidas", "abandono"]):
        return "telefonia"
    if any(k in q_lower for k in ["glpi", "tickets ti", "chamados ti"]):
        return "glpi"
        
    return "geral"

def check_deterministic_kpi(question: str, scope: str) -> Optional[Tuple[str, str]]:
    """
    Roteador determinístico para os KPIs mais frequentes.
    Retorna (sql_query, label_descritivo) se houver correspondência exata, ou None.
    """
    q_clean = re.sub(r"[^\w\s]", "", question.lower()).strip()
    
    # 1. Total de chamados PRF
    if scope == "prf" and (
        q_clean in ["quantos chamados temos na prf", "total de chamados prf", "quantos chamados na prf", "total chamados prf"]
    ):
        return (
            "SELECT COUNT(*) AS total_chamados FROM dw_positivo.vw_bi_tickets_prf;",
            "Total Geral de Chamados da PRF"
        )
        
    # 2. Total de chamados abertos PRF
    if scope == "prf" and (
        q_clean in ["quantos chamados abertos na prf", "total de chamados abertos na prf", "chamados abertos prf"]
    ):
        return (
            "SELECT COUNT(*) AS total_abertos FROM dw_positivo.vw_bi_tickets_prf WHERE fl_encerrado = false;",
            "Chamados Atualmente em Aberto na PRF"
        )
        
    # 3. Total de chamados INCRA / Cervello
    if scope == "incra" and (
        q_clean in ["quantos chamados temos no incra", "total de chamados incra", "quantos chamados na base do cervello", "total chamados cervello"]
    ):
        return (
            "SELECT COUNT(*) AS total_chamados FROM dw_positivo.vw_bi_chamados_incra;",
            "Total Geral de Chamados do INCRA (Cervello)"
        )
        
    # 4. Total de chamados abertos INCRA
    if scope == "incra" and (
        q_clean in ["quantos chamados abertos no incra", "chamados abertos incra", "quantos chamados em aberto no incra"]
    ):
        return (
            "SELECT COUNT(*) AS total_abertos FROM dw_positivo.vw_bi_chamados_incra WHERE fl_encerrado = false;",
            "Chamados em Aberto no INCRA"
        )
        
    # 5. Total de chamados CAESB
    if scope == "caesb" and (
        q_clean in ["quantos chamados temos na caesb", "total chamados caesb", "quantos chamados na caesb"]
    ):
        return (
            "SELECT COUNT(*) AS total_chamados FROM dw_positivo.vw_bi_tickets_caesb;",
            "Total Geral de Chamados da CAESB"
        )

    # 6. Total de chamados DNIT
    if scope == "dnit" and (
        q_clean in ["quantos chamados temos no dnit", "total de chamados dnit", "quantos chamados no dnit", "total chamados dnit"]
    ):
        return (
            "SELECT COUNT(*) AS total_chamados FROM dw_positivo.vw_bi_tickets_dnit;",
            "Total Geral de Chamados do DNIT"
        )
    if scope == "dnit" and (
        q_clean in ["quantos chamados abertos no dnit", "total de chamados abertos no dnit", "chamados abertos dnit"]
    ):
        return (
            "SELECT COUNT(*) AS total_abertos FROM dw_positivo.vw_bi_tickets_dnit WHERE fl_encerrado = false;",
            "Chamados em Aberto no DNIT"
        )

    # 7. Resumo de telefonia hoje
    if scope == "telefonia" and (
        "hoje" in q_clean or "como esta a telefonia" in q_clean or "resumo telefonia" in q_clean
    ):
        return (
            "SELECT operacao, total_atendidas, total_perdidas, taxa_perda_percentual FROM dw_positivo.vw_bi_telefonia_resumo WHERE data = CURRENT_DATE;",
            "Desempenho da Telefonia no Dia de Hoje"
        )

    return None

def retrieve_golden_queries_for_question(question: str, scope: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Recupera os melhores exemplos de Golden Queries baseados no escopo e palavras-chave."""
    queries = get_golden_queries()
    if not queries:
        return []
        
    # 1. Filtrar pelo escopo se identificado
    matching = [q for q in queries if q.get("scope") == scope]
    if not matching:
        matching = queries
        
    # 2. Ranking simples por sobreposição de palavras-chave
    q_words = set(re.findall(r"\w+", question.lower()))
    scored = []
    for item in matching:
        item_words = set(re.findall(r"\w+", item["question"].lower()))
        overlap = len(q_words.intersection(item_words))
        scored.append((overlap, item))
        
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]

_db_columns_cache: Dict[str, List[Tuple[str, str]]] = {}

COLUMN_SEMANTIC_NOTES = {
    "data_abertura": "momento de abertura do chamado. (ATENÇÃO: a coluna chama-se data_abertura, NUNCA 'dt_abertura').",
    "data_solucao": "momento em que o técnico registrou a solução aplicada. (Para chamados solucionados em uma data D, use: data_solucao >= 'D' AND data_solucao < ('D'::date + 1)).",
    "data_fechamento": "momento do encerramento administrativo do chamado.",
    "data_encerramento": "COALESCE(data_fechamento, data_solucao).",
    "status": "texto do status do chamado (ex: 'FECHADO', 'SOLUCIONADO', 'EM ATENDIMENTO (ATRIBUIDO)', 'PENDENTE').",
    "fl_encerrado": "booleano: true se fechado ou solucionado, false se em aberto. (ATENÇÃO: NUNCA invente 'fl_solucionado'!).",
    "analista": "nome do técnico/analista que atendeu o chamado.",
    "categoria": "classificação/categoria de atendimento.",
    "tempo_atendimento_segundos": "tempo total de atendimento em segundos."
}

def load_db_columns_cache(force_refresh: bool = False) -> Dict[str, List[Tuple[str, str]]]:
    """Carrega as colunas e tipos reais das views dw_positivo.vw_bi_* a partir do catálogo do PostgreSQL com cache em memória."""
    global _db_columns_cache
    if _db_columns_cache and not force_refresh:
        return _db_columns_cache
        
    try:
        from app.database import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name, column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = 'dw_positivo' AND table_name LIKE 'vw_bi_%'
                    ORDER BY table_name, ordinal_position;
                """)
                for table_name, col_name, data_type in cur.fetchall():
                    if table_name not in _db_columns_cache:
                        _db_columns_cache[table_name] = []
                    _db_columns_cache[table_name].append((col_name, data_type))
        logger.info(f"Catálogo do banco carregado com sucesso para {len(_db_columns_cache)} views.")
    except Exception as e:
        logger.warning(f"Não foi possível carregar catálogo ao vivo do banco ({e}). Utilizando snapshot padrão.")
        # Snapshot de contingência caso o banco esteja inacessível no momento do import
        default_glpi_cols = [
            ("ticket_id", "bigint"), ("titulo", "text"), ("data_abertura", "timestamp without time zone"),
            ("data_fechamento", "timestamp without time zone"), ("data_solucao", "timestamp without time zone"),
            ("data_encerramento", "timestamp without time zone"), ("status", "text"), ("fl_encerrado", "boolean"),
            ("prioridade", "bigint"), ("categoria", "text"), ("grupo", "text"), ("solicitante", "text"),
            ("analista", "text"), ("localidade", "text"), ("tempo_atendimento_segundos", "bigint")
        ]
        for v in ["vw_bi_glpi_tickets", "vw_bi_tickets_dnit", "vw_bi_tickets_prf", "vw_bi_tickets_caesb", "vw_bi_tickets_dpu", "vw_bi_tickets_fnde", "vw_bi_tickets_ufba", "vw_bi_tickets_antaq", "vw_bi_tickets_mj"]:
            _db_columns_cache[v] = default_glpi_cols
            
    return _db_columns_cache

def format_view_schema_prompt(view_name: str, friendly_desc: str) -> str:
    """Monta a especificação técnica exata da view com nomes e tipos reais."""
    schema_map = load_db_columns_cache()
    cols = schema_map.get(view_name, [])
    
    col_lines = []
    for col_name, data_type in cols:
        note = COLUMN_SEMANTIC_NOTES.get(col_name)
        if note:
            col_lines.append(f"  * {col_name} ({data_type}) - {note}")
        else:
            col_lines.append(f"  * {col_name} ({data_type})")
            
    columns_str = "\n".join(col_lines)
    return f"""VIEW DISPONÍVEL: dw_positivo.{view_name} ({friendly_desc})
COLUNAS REAIS DA VIEW:
{columns_str}"""

def get_pruned_schema_prompt(scope: str) -> str:
    """Retorna documentação de schema podada (apenas views relevantes para o escopo) com nomes e tipos reais."""
    strict_rule = """REGRAS CRÍTICAS DE SCHEMA:
- Use SOMENTE as colunas e views listadas acima. Se a coluna necessária não existir, não invente: use a mais próxima listada.
- NUNCA invente colunas como 'fl_solucionado' ou 'dt_abertura'. Use sempre 'data_solucao', 'data_fechamento' e 'data_abertura'.
- Chamados SOLUCIONADOS: use data_solucao. Chamados FECHADOS: use data_fechamento. Chamados ABERTOS: fl_encerrado = false."""

    if scope == "prf":
        view_doc = format_view_schema_prompt("vw_bi_tickets_prf", "Chamados de TI da PRF - Polícia Rodoviária Federal")
        return f"{view_doc}\n\n{strict_rule}"

    elif scope == "dnit":
        view_doc = format_view_schema_prompt("vw_bi_tickets_dnit", "Chamados de TI do DNIT - Infraestrutura de Transportes")
        return f"{view_doc}\n\n{strict_rule}"

    elif scope in ("dpu", "fnde", "ufba", "antaq", "mj", "caesb"):
        view_name = f"vw_bi_tickets_{scope}"
        view_doc = format_view_schema_prompt(view_name, f"Chamados de TI do contrato {scope.upper()}")
        return f"{view_doc}\n\n{strict_rule}"

    elif scope == "incra":
        view_doc = format_view_schema_prompt("vw_bi_chamados_incra", "Chamados do INCRA via Cervello")
        return f"{view_doc}\n\n{strict_rule}"

    elif scope == "telefonia":
        view_doc = format_view_schema_prompt("vw_bi_telefonia_resumo", "Resumo Diário de Ligações da Telefonia")
        return f"{view_doc}\n\n{strict_rule}"

    else:
        # Escopo geral: listar a view consolidada geral GLPI e as principais views
        docs = [
            format_view_schema_prompt("vw_bi_glpi_tickets", "Todos os chamados de TI consolidados de todos os órgãos (GLPI)"),
            format_view_schema_prompt("vw_bi_tickets_dnit", "DNIT - GLPI"),
            format_view_schema_prompt("vw_bi_tickets_prf", "PRF - GLPI"),
            format_view_schema_prompt("vw_bi_tickets_ufba", "UFBA - GLPI"),
            format_view_schema_prompt("vw_bi_chamados_incra", "INCRA - Cervello")
        ]
        return "\n\n".join(docs) + f"\n\n{strict_rule}"
