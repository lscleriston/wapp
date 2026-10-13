import re
import time
import logging
import psycopg2
import psycopg2.extras
from typing import List, Dict, Any, Tuple, Optional
from app.config import settings

logger = logging.getLogger("wapp_database")

# Metadados e Documentação Semântica das Views Curadas para o LLM Text-to-SQL
SCHEMA_DOCUMENTATION = """
Você tem acesso ao banco de dados PostgreSQL 'dw_positivo' com VIEWS CURADAS otimizadas no schema 'dw_positivo'.
SEMPRE prefira consultar as VIEWS CURADAS (prefixo vw_bi_), pois elas já possuem datas tratadas como TIMESTAMP nativo, nomes em snake_case e soft deletes filtrados:

1. dw_positivo.vw_bi_chamados_incra (Chamados do INCRA via sistema Cervello):
   * chamado_id (text): Identificador do chamado.
   * codigo_real (text): Código numérico do chamado.
   * data_abertura (timestamp): Data e hora de abertura (já tratada como timestamp).
   * data_fechamento (timestamp): Data de encerramento (null se aberto).
   * data_primeiro_atendimento (timestamp): Data do primeiro atendimento.
   * favorecido, departamento, localidade (text): Dados do solicitante.
   * categoria, subcategoria, tipo (text): Classificação do chamado.
   * prioridade (text): Ex: '4 - Baixa', '3 - Média', '1 - Crítica'.
   * status (text): Estado do chamado ('FECHADO', 'ABERTO', 'EM ATENDIMENTO', 'CANCELADO').
   * fl_encerrado (boolean): true se FECHADO/ENCERRADO/CANCELADO, false se em aberto.
   * situacao_sla (text): 'Dentro SLA' ou 'Fora SLA'.
   * fl_dentro_sla (boolean): true se cumpriu o SLA, false se estourou.
   * analista, grupo_analista (text): Responsável pelo atendimento.

2. dw_positivo.vw_bi_tickets_prf (Chamados de TI da PRF - Polícia Rodoviária Federal):
   * ticket_id (bigint): ID do ticket GLPI.
   * titulo (text): Assunto / resumo do chamado.
   * data_abertura (timestamp): Data de abertura.
   * data_fechamento, data_solucao (timestamp): Datas de resolução/encerramento.
   * status (text): 'FECHADO', 'SOLUCIONADO', 'NOVO', 'ATRIBUIDO', 'PENDENTE'.
   * fl_encerrado (boolean): true se fechado/solucionado.
   * prioridade (bigint): Nível de prioridade (1 a 5).
   * categoria, grupo, solicitante, analista, localidade (text): Dados contextuais.
   * tempo_atendimento_segundos (bigint): Tempo de atendimento em segundos.
   (OBS: is_deleted = false já filtrado na view automaticamente).

3. dw_positivo.vw_bi_tickets_caesb (Chamados de TI da CAESB - Saneamento Ambiental):
   * Mesma estrutura da view da PRF (ticket_id, titulo, data_abertura, data_fechamento, status, fl_encerrado, categoria, analista, etc.).

4. dw_positivo.vw_bi_tickets_dnit (Chamados de TI do DNIT - Departamento Nacional de Infraestrutura de Transportes):
   * ticket_id (bigint): ID do ticket GLPI.
   * titulo (text): Assunto / resumo do chamado.
   * data_abertura (timestamp): Data e hora de abertura.
   * data_fechamento (timestamp): Data de fechamento.
   * data_solucao (timestamp): Data de solução pelo analista.
   * data_encerramento (timestamp): COALESCE(data_fechamento, data_solucao).
   * status (text): 'FECHADO', 'SOLUCIONADO', 'EM ATENDIMENTO (ATRIBUIDO)', 'PENDENTE'.
   * fl_encerrado (boolean): true se finalizado ('FECHADO' ou 'SOLUCIONADO'), false se em aberto.
   * prioridade (bigint): Prioridade de 1 a 5.
   * categoria, grupo, solicitante, analista, localidade (text): Dados contextuais.
   * tempo_atendimento_segundos (bigint): Tempo de atendimento em segundos.
   (OBS: Para chamados fechados/resolvidos hoje: fl_encerrado = true AND (data_fechamento >= CURRENT_DATE OR data_solucao >= CURRENT_DATE)).

5. dw_positivo.vw_bi_tickets_dpu, dw_positivo.vw_bi_tickets_fnde, dw_positivo.vw_bi_tickets_ufba, dw_positivo.vw_bi_tickets_antaq, dw_positivo.vw_bi_tickets_mj:
   * Mesma estrutura da view do DNIT e PRF (ticket_id, titulo, data_abertura, data_fechamento, data_solucao, data_encerramento, status, fl_encerrado, prioridade, categoria, grupo, solicitante, analista, localidade).

6. dw_positivo.vw_bi_glpi_tickets (Tickets GLPI de Outras Operações / Geral):
   * ticket_id (bigint): ID do ticket.
   * contrato (text): Operação vinculada (ex: 'UFBA', 'DNIT', 'DPU', 'ANTAQ', etc.).
   * titulo (text): Assunto do ticket.
   * data_abertura, data_fechamento, data_solucao (timestamp).
   * status (text): Estado do ticket.
   * fl_encerrado (boolean): true se fechado.
   * prioridade, urgencia, impacto (bigint).
   (OBS: is_deleted = false já filtrado na view automaticamente).

7. dw_positivo.vw_bi_telefonia_resumo (Resumo Diário de Ligações do Suporte):
   * data (date): Dia de referência.
   * operacao (text): Contrato / Central (ex: 'INCRA', 'DPU', 'PRF').
   * total_atendidas (bigint): Quantidade de chamadas atendidas.
   * total_perdidas (bigint): Quantidade de chamadas abandonadas/perdidas.
   * total_chamadas (bigint): Total geral de ligações.
   * taxa_perda_percentual (numeric): Porcentagem de perda (ex: 5.25 para 5,25%).

DICAS ESSENCIAIS DE SQL:
- Utilize sempre o prefixo do schema: dw_positivo.nome_da_view
- Para agrupar por mês: DATE_TRUNC('month', data_abertura)
- Para o mês atual: data_abertura >= DATE_TRUNC('month', CURRENT_DATE)
- Para chamados fechados hoje: fl_encerrado = true AND (data_fechamento >= CURRENT_DATE OR data_solucao >= CURRENT_DATE)
- Para agrupar por analista: GROUP BY analista (ou COALESCE(analista, 'Não atribuído'))
- Sempre gere apenas consultas SELECT puras e seguras.
"""

DANGEROUS_KEYWORDS = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
    r"\bALTER\b", r"\bTRUNCATE\b", r"\bCREATE\b", r"\bGRANT\b",
    r"\bREVOKE\b", r"\bEXEC\b", r"\bEXECUTE\b", r"\bCOPY\b",
    r"\bPG_SLEEP\b", r"\bPG_READ_FILE\b", r"\bPG_LS_DIR\b",
    r"\bPG_STAT_ACTIVITY\b", r"\bDBLINK\b", r"\bPG_TERMINATE_BACKEND\b",
    r"\bPG_CANCEL_BACKEND\b", r"\bLO_EXPORT\b", r"\bLO_IMPORT\b",
    r"\bPG_SHADOW\b", r"\bPG_AUTHID\b"
]

def get_connection():
    """Conecta ao PostgreSQL utilizando o usuário restrito de BI com timeout curto e timezone America/Sao_Paulo."""
    return psycopg2.connect(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        dbname=settings.PG_DB,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        connect_timeout=4,
        options="-c timezone=America/Sao_Paulo"
    )

def validate_and_clean_sql(query: str) -> Tuple[bool, str]:
    """Valida se a query é estritamente de leitura (SELECT/WITH) sem comandos perigosos ou múltiplos statements."""
    cleaned = query.strip()
    
    # Remover blocos de markdown ```sql ... ```
    cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    
    # Remover comandos SET no início da query se houver
    cleaned = re.sub(r"^SET\s+[^;]+;\s*", "", cleaned, flags=re.IGNORECASE).strip()

    # Remover ponto e vírgula no final se houver
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
        
    # Bloquear múltiplos comandos separados por ponto e vírgula
    if ";" in cleaned:
        return False, "Múltiplos comandos SQL não são permitidos por segurança."
        
    # Verificar se começa exclusivamente com SELECT ou WITH
    first_word = cleaned.split()[0].upper() if cleaned.split() else ""
    if first_word not in ("SELECT", "WITH"):
        return False, f"Apenas consultas SELECT ou WITH são permitidas. Comando recebido: {first_word}"
        
    # Checar palavras perigosas ou funções internas restritas
    for pattern in DANGEROUS_KEYWORDS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return False, f"Palavra-chave ou função restrita detectada na consulta: {pattern}"
            
    # Garantir LIMIT 50 se não houver agregação nem limit explícito
    is_pure_aggregate = bool(re.search(r"^\s*SELECT\s+(COUNT|SUM|AVG|MIN|MAX)\s*\(", cleaned, re.IGNORECASE))
    has_limit = bool(re.search(r"\bLIMIT\b", cleaned, re.IGNORECASE))
    
    if not is_pure_aggregate and not has_limit:
        cleaned += " LIMIT 50"
        
    return True, cleaned

def log_audit_event(
    phone_number: str,
    user_question: str,
    resolved_scope: Optional[str] = None,
    generated_sql: Optional[str] = None,
    execution_time_ms: int = 0,
    success: bool = False,
    row_count: int = 0,
    error_message: Optional[str] = None,
    needs_review: bool = False,
    date_context: Optional[str] = None
):
    """Grava o evento no log de auditoria persistente dw_positivo.bi_agent_audit_log para LGPD."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO dw_positivo.bi_agent_audit_log (
                        phone_number, user_question, resolved_scope, generated_sql,
                        execution_time_ms, success, row_count, error_message, needs_review,
                        date_context
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    phone_number,
                    user_question,
                    resolved_scope,
                    generated_sql,
                    execution_time_ms,
                    success,
                    row_count,
                    error_message,
                    needs_review,
                    date_context
                ))
                conn.commit()
    except Exception as e:
        logger.error(f"Falha ao registrar auditoria no banco: {e}")

def execute_safe_query(
    sql_query: str,
    phone_number: str = "SYSTEM",
    user_question: str = "",
    resolved_scope: Optional[str] = None,
    date_context: Optional[str] = None
) -> Dict[str, Any]:
    """Executa a query com statement_timeout de 8 segundos, fuso horário America/Sao_Paulo, audita o resultado e trata erros."""
    t0 = time.time()
    is_valid, sanitized_sql = validate_and_clean_sql(sql_query)
    
    if not is_valid:
        exec_ms = int((time.time() - t0) * 1000)
        log_audit_event(
            phone_number=phone_number,
            user_question=user_question,
            resolved_scope=resolved_scope,
            generated_sql=sql_query,
            execution_time_ms=exec_ms,
            success=False,
            row_count=0,
            error_message=sanitized_sql,
            needs_review=True,
            date_context=date_context
        )
        return {
            "success": False,
            "error": sanitized_sql,
            "query": sql_query,
            "rows": [],
            "count": 0,
            "execution_time_ms": exec_ms
        }
        
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Sessão com timezone de Brasília, statement timeout de 8000ms e search_path seguro
            cur.execute("SET TIME ZONE 'America/Sao_Paulo';")
            cur.execute("SET statement_timeout = 8000;")
            cur.execute("SET search_path TO dw_positivo, public;")
            cur.execute(sanitized_sql)
            
            rows = cur.fetchall()
            result_rows = [dict(row) for row in rows]
            exec_ms = int((time.time() - t0) * 1000)
            
            log_audit_event(
                phone_number=phone_number,
                user_question=user_question,
                resolved_scope=resolved_scope,
                generated_sql=sanitized_sql,
                execution_time_ms=exec_ms,
                success=True,
                row_count=len(result_rows),
                error_message=None,
                date_context=date_context
            )
            
            return {
                "success": True,
                "query": sanitized_sql,
                "rows": result_rows,
                "count": len(result_rows),
                "error": None,
                "execution_time_ms": exec_ms
            }
    except Exception as e:
        exec_ms = int((time.time() - t0) * 1000)
        err_msg = str(e)
        log_audit_event(
            phone_number=phone_number,
            user_question=user_question,
            resolved_scope=resolved_scope,
            generated_sql=sanitized_sql,
            execution_time_ms=exec_ms,
            success=False,
            row_count=0,
            error_message=err_msg,
            needs_review=True,
            date_context=date_context
        )
        return {
            "success": False,
            "error": err_msg,
            "query": sanitized_sql,
            "rows": [],
            "count": 0,
            "execution_time_ms": exec_ms
        }
    finally:
        if conn:
            conn.close()
