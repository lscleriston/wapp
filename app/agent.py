import json
import logging
import asyncio
import httpx
from typing import Dict, List, Optional
from app.config import settings
from app.database import SCHEMA_DOCUMENTATION, execute_safe_query

logger = logging.getLogger("wapp_agent")

user_conversations: Dict[str, List[Dict[str, str]]] = {}
MAX_HISTORY_TURNS = 5

def get_history(user_id: str) -> str:
    history = user_conversations.get(user_id, [])
    if not history:
        return "Nenhum histórico anterior."
    lines = []
    for item in history[-MAX_HISTORY_TURNS:]:
        role = "Usuário" if item["role"] == "user" else "Agente"
        lines.append(f"{role}: {item['content']}")
    return "\n".join(lines)

def add_to_history(user_id: str, user_text: str, agent_text: str):
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    user_conversations[user_id].append({"role": "user", "content": user_text})
    user_conversations[user_id].append({"role": "agent", "content": agent_text})
    if len(user_conversations[user_id]) > (MAX_HISTORY_TURNS * 2):
        user_conversations[user_id] = user_conversations[user_id][-(MAX_HISTORY_TURNS * 2):]

async def call_gemini(prompt: str, model_name: str, temperature: float = 0.2) -> Optional[str]:
    """Chama a API do Google Gemini com retentativa rápida para picos de demanda (503/timeout)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 2048
        }
    }
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=18.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        for p in parts:
                            if "text" in p and p["text"].strip():
                                return p["text"].strip()
                elif response.status_code in (429, 503):
                    wait_time = 2.0 * (attempt + 1)
                    logger.warning(f"Gemini {model_name} tentativa {attempt+1} retornou status {response.status_code}. Aguardando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"Gemini {model_name} retornou status {response.status_code}: {response.text[:150]}")
                    break
        except Exception as e:
            logger.warning(f"Erro chamando Gemini {model_name} (tentativa {attempt+1}): {type(e).__name__} - {e}")
            if attempt == 0:
                await asyncio.sleep(1.0)
    return None

async def call_ollama(prompt: str) -> Optional[str]:
    """Fallback local para Ollama na VPS (modelo ágil de 3b em CPU)."""
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "stream": False
    }
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                return data.get("response", "").strip()
    except Exception as e:
        logger.warning(f"Ollama local falhou: {e}")
    return None

from app.utils.dates import build_date_context

async def call_llm(prompt: str, temperature: float = 0.2) -> str:
    """Orquestrador de IA com fallback resiliente: Gemini 3.6 Flash -> Gemini Flash Latest -> Gemini Flash Lite -> Ollama."""
    models_to_try = [
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
        "gemini-3.6-flash",
        settings.GEMINI_MODEL
    ]
    seen = set()
    for m in models_to_try:
        if not m or m in seen:
            continue
        seen.add(m)
        logger.info(f"Consultando Gemini com modelo {m}...")
        res = await call_gemini(prompt, m, temperature)
        if res:
            return res
        
    # Fallback para Ollama local
    logger.info("Acionando fallback Ollama local...")
    res = await call_ollama(prompt)
    if res:
        return res

    raise RuntimeError("Nenhum modelo de IA disponível no momento.")

from app.retriever import (
    detect_scope_from_question,
    check_deterministic_kpi,
    retrieve_golden_queries_for_question,
    get_pruned_schema_prompt
)

async def process_user_message(user_id: str, message_text: str, detected_scope: Optional[str] = None) -> str:
    """Fluxo principal do agente: Contexto Temporal -> Roteador KPI -> Retriever Semântico -> SQL -> Execução Segura -> Auto-Correção -> Resposta Transparente."""
    history_str = get_history(user_id)
    scope = detected_scope if (detected_scope and detected_scope != "all") else detect_scope_from_question(message_text)
    
    # 1. Gerar contexto temporal exato no fuso de Brasília
    date_context = build_date_context()
    
    # 2. Roteador Determinístico para Top KPIs (100% exato e instantâneo)
    deterministic = check_deterministic_kpi(message_text, scope)
    if deterministic:
        sql_or_reply, kpi_label = deterministic
        logger.info(f"KPI Determinístico acionado para {user_id} ({kpi_label}): {sql_or_reply}")
    else:
        # 3. Recuperar exemplos e schema podado para a LLM
        golden_examples = retrieve_golden_queries_for_question(message_text, scope, limit=2)
        pruned_schema = get_pruned_schema_prompt(scope)
        
        examples_str = ""
        if golden_examples:
            examples_str = "EXEMPLOS DE CONSULTAS APROVADAS (FEW-SHOT):\n"
            for g in golden_examples:
                examples_str += f"- Pergunta: \"{g['question']}\"\n  SQL: {g['sql']}\n"
                
        sql_prompt = f"""Você é o Agente Analista de Dados da Datavizbi / Positivo Tecnologia.
Sua missão é responder perguntas sobre o banco de dados 'dw_positivo' de forma precisa e segura.

{date_context}

{pruned_schema}

{examples_str}

HISTÓRICO DA CONVERSA:
{history_str}

PERGUNTA ATUAL DO USUÁRIO:
"{message_text}"

REGRAS OBRIGATÓRIAS PARA GERAÇÃO DE SQL:
1. Data sem ano ("09/10", "dia 09") = utilize o ano corrente indicado no contexto temporal acima. Se resultar em data futura em relação a hoje, utilize o ano anterior. NUNCA use anos passados como 2023 se a pergunta não pedir expressamente.
2. Para filtrar um dia D: utilize estritamente `coluna >= 'D' AND coluna < ('D'::date + 1)` (ex: `data_solucao >= '2026-10-09' AND data_solucao < '2026-10-10'`).
3. Para termos relativos ("ontem", "última sexta-feira", "semana passada", "este mês"): utilize as datas EXATAS fornecidas no CONTEXTO TEMPORAL acima. NÃO use `current_date - interval`.
4. Não use ano diferente do corrente a menos que o usuário peça explicitamente.
5. Use SOMENTE as colunas e views listadas acima. Se a coluna necessária não existir, não invente: use a mais próxima listada. Nunca use 'fl_solucionado' nem 'dt_abertura'.
6. Chamados SOLUCIONADOS: use `data_solucao`. Chamados ABERTOS: use `data_abertura`. Chamados FECHADOS: use `data_fechamento`.
7. Se a mensagem for apenas uma saudação, apresentação ou agradecimento, responda iniciando com o prefixo 'NO_SQL:' seguido de uma resposta cordial.
8. Se for pergunta de dados, retorne APENAS a instrução SQL PostgreSQL pura (sem crases de markdown, sem explicações, apenas o SELECT puro).
9. Nunca gere comandos que alterem dados (apenas SELECT/WITH).
"""
        
        try:
            sql_or_reply = await call_llm(sql_prompt, temperature=0.1)
        except Exception as e:
            logger.error(f"Erro chamando IA para SQL: {e}")
            return "⚠️ Tive uma instabilidade ao conectar com o serviço de inteligência artificial. Por favor, tente novamente em instantes."

        # Se for uma saudação ou conversa geral
        if sql_or_reply.startswith("NO_SQL:"):
            reply = sql_or_reply.replace("NO_SQL:", "").strip()
            add_to_history(user_id, message_text, reply)
            return reply

    # 4. Executar a consulta no banco de dados com auditoria e usuário restrito
    logger.info(f"Executando SQL para {user_id} (escopo: {detected_scope}): {sql_or_reply}")
    db_result = execute_safe_query(
        sql_or_reply,
        phone_number=user_id,
        user_question=message_text,
        resolved_scope=detected_scope,
        date_context=date_context
    )
    
    if not db_result["success"]:
        logger.warning(f"Erro SQL no primeiro ciclo: {db_result['error']}")
        # Ciclo de Auto-Correção (Self-Healing)
        retry_prompt = f"""A consulta SQL gerada retornou um erro no PostgreSQL:
SQL ANTERIOR: {sql_or_reply}
ERRO DO POSTGRESQL: {db_result['error']}

{date_context}

{pruned_schema}

{SCHEMA_DOCUMENTATION}

INSTRUÇÕES DE CORREÇÃO:
1. Corrija a consulta SQL para PostgreSQL utilizando apenas as views e colunas existentes acima.
2. Certifique-se de usar os nomes de colunas corretos (ex: analista, data_abertura, data_fechamento, data_solucao, fl_encerrado). NUNCA invente fl_solucionado ou dt_abertura.
3. Para filtrar um dia D, use: `coluna >= 'D' AND coluna < ('D'::date + 1)`.
4. NUNCA gere comandos SET, ALTER, nem múltiplos comandos separados por ponto e vírgula.
5. Retorne APENAS um único comando SELECT puro (sem crases de markdown, sem explicações)."""
        try:
            fixed_sql = await call_llm(retry_prompt, temperature=0.0)
            logger.info(f"Tentativa de auto-correção gerada: {fixed_sql}")
            db_result = execute_safe_query(
                fixed_sql,
                phone_number=user_id,
                user_question=message_text,
                resolved_scope=detected_scope,
                date_context=date_context
            )
        except Exception as retry_err:
            logger.error(f"Falha no ciclo de auto-correção: {retry_err}")

    if not db_result["success"]:
        reply = f"❌ Não foi possível extrair esses dados com exatidão no momento.\n_Motivo técnico: {db_result['error']}_"
        add_to_history(user_id, message_text, reply)
        return reply

    # 5. Formatar a resposta final para o WhatsApp com Transparência de Critérios
    data_preview = json.dumps(db_result["rows"][:50], ensure_ascii=False, default=str)
    
    formatting_prompt = f"""Você é o Agente de Inteligência Corporativa da Datavizbi no WhatsApp.
O usuário fez a seguinte pergunta:
"{message_text}"

A consulta SQL executada com sucesso foi:
{db_result['query']}

O banco de dados retornou o seguinte resultado ({db_result['count']} registros):
{data_preview}

INSTRUÇÕES OBRIGATÓRIAS DE FORMATAÇÃO PARA WHATSAPP:
1. Responda em português brasileiro de forma direta, executiva e profissional.
2. NUNCA recalcule ou invente números. Seja 100% fiel aos dados brutos retornados pelo banco.
3. Use a formatação do WhatsApp: asterisco para negrito (*valor*), traço para tópicos.
4. Se houver contagens ou métricas, destaque-as no início da resposta.
5. Se o resultado for 0 registros, informe com clareza que nenhum dado foi encontrado para esse filtro.
6. Ao final da resposta, SEMPRE inclua uma linha em itálico de transparência resumindo os critérios aplicados:
   Exemplo:
   _🔍 Critérios: Órgão/Base: [Nome] | Período: [Período considerado] | Filtros: [Status/Regras aplicadas]_
7. Adicione 1 ou 2 emojis corporativos adequados (📋, 📊, 📈).
"""
    
    try:
        final_reply = await call_llm(formatting_prompt, temperature=0.2)
    except Exception as e:
        logger.error(f"Erro formatando resposta final com LLM: {e}")
        # Fallback seguro determinístico: nunca deixar o usuário sem resposta se o banco já respondeu
        if db_result["count"] == 1 and len(db_result["rows"][0]) == 1:
            k, v = list(db_result["rows"][0].items())[0]
            final_reply = f"📊 O total registrado para sua consulta é *{v}*."
        else:
            final_reply = f"📊 Encontrei *{db_result['count']}* registros para sua consulta no banco de dados."
        final_reply += f"\n\n_🔍 Critérios: Consulta executada com sucesso no banco dw_positivo._"

    add_to_history(user_id, message_text, final_reply)
    return final_reply
