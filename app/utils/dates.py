from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Dict

DIAS_SEMANA_PT = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo"
]

def get_sp_now(ref_datetime: Optional[datetime] = None) -> datetime:
    """Retorna datetime no fuso de São Paulo ou converte/usa ref_datetime fornecido."""
    tz = ZoneInfo("America/Sao_Paulo")
    if ref_datetime is not None:
        if ref_datetime.tzinfo is None:
            return ref_datetime.replace(tzinfo=tz)
        return ref_datetime.astimezone(tz)
    return datetime.now(tz)

def build_date_context_dict(ref_datetime: Optional[datetime] = None) -> Dict[str, any]:
    """Calcula todas as referências temporais sem depender de LLM ou locale do SO."""
    now_sp = get_sp_now(ref_datetime)
    hoje = now_sp.date()
    ontem = hoje - timedelta(days=1)
    anteontem = hoje - timedelta(days=2)
    
    weekday_idx = hoje.weekday()  # 0 = Segunda, 6 = Domingo
    dia_semana_nome = DIAS_SEMANA_PT[weekday_idx]
    ano_corrente = hoje.year

    # Última ocorrência estritamente anterior a hoje para cada dia da semana (0 a 6)
    ultimos_dias = {}
    for target_weekday in range(7):
        target_nome = DIAS_SEMANA_PT[target_weekday]
        diff = (weekday_idx - target_weekday) % 7
        if diff == 0:
            diff = 7  # Se hoje for o mesmo dia, a última ocorrência foi há 7 dias
        last_date = hoje - timedelta(days=diff)
        ultimos_dias[target_nome] = last_date.isoformat()

    # Esta semana: segunda-feira até hoje
    segunda_esta_semana = hoje - timedelta(days=weekday_idx)
    
    # Semana passada: segunda a domingo
    segunda_semana_passada = segunda_esta_semana - timedelta(days=7)
    domingo_semana_passada = segunda_semana_passada + timedelta(days=6)

    # Este mês: dia 1 até hoje
    primeiro_dia_mes = date(hoje.year, hoje.month, 1)

    # Mês passado: dia 1 até último dia
    primeiro_dia_mes_passado = (primeiro_dia_mes - timedelta(days=1)).replace(day=1)
    ultimo_dia_mes_passado = primeiro_dia_mes - timedelta(days=1)

    return {
        "now_iso": now_sp.strftime("%Y-%m-%d %H:%M:%S"),
        "hoje_iso": hoje.isoformat(),
        "ontem_iso": ontem.isoformat(),
        "anteontem_iso": anteontem.isoformat(),
        "dia_semana": dia_semana_nome,
        "ano_corrente": ano_corrente,
        "ultimos_dias": ultimos_dias,
        "esta_semana_inicio": segunda_esta_semana.isoformat(),
        "esta_semana_fim": hoje.isoformat(),
        "semana_passada_inicio": segunda_semana_passada.isoformat(),
        "semana_passada_fim": domingo_semana_passada.isoformat(),
        "este_mes_inicio": primeiro_dia_mes.isoformat(),
        "este_mes_fim": hoje.isoformat(),
        "mes_passado_inicio": primeiro_dia_mes_passado.isoformat(),
        "mes_passado_fim": ultimo_dia_mes_passado.isoformat(),
    }

def build_date_context(ref_datetime: Optional[datetime] = None) -> str:
    """Gera o bloco de texto formatado para injeção no topo do sql_prompt."""
    ctx = build_date_context_dict(ref_datetime)
    
    dias_linhas = []
    for nome, data_iso in ctx["ultimos_dias"].items():
        dias_linhas.append(f"  * Última {nome}: {data_iso}")

    ultimos_dias_str = "\n".join(dias_linhas)

    return f"""--- CONTEXTO TEMPORAL (use estes valores literalmente, não calcule datas com interval) ---
- Data e Hora Atual (Brasília): {ctx['now_iso']}
- Hoje: {ctx['hoje_iso']} ({ctx['dia_semana']})
- Ontem: {ctx['ontem_iso']}
- Anteontem: {ctx['anteontem_iso']}
- Ano Corrente: {ctx['ano_corrente']}

ÚLTIMA OCORRÊNCIA DE CADA DIA DA SEMANA (estritamente anterior a hoje):
{ultimos_dias_str}

PERÍODOS E INTERVALOS RECENTES:
- Esta Semana (segunda até hoje): {ctx['esta_semana_inicio']} até {ctx['esta_semana_fim']}
- Semana Passada (segunda a domingo): {ctx['semana_passada_inicio']} até {ctx['semana_passada_fim']}
- Este Mês (dia 1 até hoje): {ctx['este_mes_inicio']} até {ctx['este_mes_fim']}
- Mês Passado (completo): {ctx['mes_passado_inicio']} até {ctx['mes_passado_fim']}
---------------------------------------------------------------------------------------------"""
