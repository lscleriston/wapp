import asyncio
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import psycopg2
from app.config import settings
from app.agent import process_user_message

def get_ground_truth(query: str) -> Any:
    """Executes a query directly against the Postgres DB as postgres/admin user to obtain true expected value."""
    try:
        conn = psycopg2.connect(
            host=settings.PG_HOST,
            port=settings.PG_PORT,
            dbname=settings.PG_DB,
            user=settings.PG_USER,
            password=settings.PG_PASSWORD,
            connect_timeout=10,
            options="-c timezone=America/Sao_Paulo"
        )
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            val = row[0] if row else None
        conn.close()
        return val
    except Exception as e:
        return f"ERR_DB: {e}"

def extract_numbers_and_dates(text: str) -> List[str]:
    """Extracts numbers (handling Brazilian thousand dots) and ISO/BR dates from agent text."""
    # Normalize dots in thousands like 1.234 -> 1234
    normalized = re.sub(r"(\d+)\.(\d{3})", r"\1\2", text)
    # Find all sequences of digits
    numbers = re.findall(r"\b\d+\b", normalized)
    # Find dates like YYYY-MM-DD or DD/MM/YYYY
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b", text)
    return numbers + dates

async def run_evaluation():
    suite_path = Path(__file__).parent / "eval_suite.json"
    if not suite_path.exists():
        print(f"Arquivo {suite_path} não encontrado!")
        return

    with open(suite_path, "r", encoding="utf-8") as f:
        cases: List[Dict[str, Any]] = json.load(f)

    print("=" * 110)
    print("🚀 SUÍTE DE AVALIAÇÃO DE PRECISÃO TEMPORAL E SCHEMA - AGENTE BI WHATSAPP")
    print("=" * 110)

    results = []
    total_time = 0.0
    passed = 0

    for c in cases:
        case_id = c["id"]
        q = c["question"]
        scope = c.get("scope")
        seed = c.get("seed_expected")
        gt_query = c.get("ground_truth_query")

        # Live ground truth from DB
        live_gt = get_ground_truth(gt_query) if gt_query else None

        # Execute agent
        t0 = time.time()
        try:
            agent_reply = await process_user_message(
                user_id=f"EVAL_{case_id}",
                message_text=q,
                detected_scope=scope
            )
            elapsed = time.time() - t0
        except Exception as e:
            agent_reply = f"EXCEÇÃO: {e}"
            elapsed = time.time() - t0

        total_time += elapsed

        # Check match against either live_gt or seed
        normalized_reply = re.sub(r"(\d+)\.(\d{3})", r"\1\2", agent_reply)
        
        target_val = live_gt if live_gt is not None else seed
        is_match = False
        if target_val is not None:
            str_target = str(target_val)
            # Match directly or date format variation
            if str_target in normalized_reply:
                is_match = True
            elif "-" in str_target: # e.g. 2026-10-09 vs 09/10/2026
                parts = str_target.split("-")
                if len(parts) == 3:
                    br_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
                    if br_date in normalized_reply:
                        is_match = True
        
        if is_match:
            passed += 1
            status_icon = "✅ PASSOU"
        else:
            status_icon = "❌ FALHOU"

        results.append({
            "id": case_id,
            "pergunta": q,
            "esperado_db": live_gt,
            "seed": seed,
            "status": status_icon,
            "tempo": f"{elapsed:.2f}s",
            "resposta_resumo": agent_reply.replace("\n", " ")[:60]
        })

    print(f"\n{'ID':<3} | {'PERGUNTA':<42} | {'BD REAL':<9} | {'SEED':<6} | {'STATUS':<9} | {'TEMPO':<6} | {'RESPOSTA AGENTE'}")
    print("-" * 110)
    for r in results:
        seed_str = str(r['seed']) if r['seed'] is not None else "N/A"
        db_str = str(r['esperado_db']) if r['esperado_db'] is not None else "N/A"
        print(f"{r['id']:<3} | {r['pergunta']:<42} | {db_str:<9} | {seed_str:<6} | {r['status']:<9} | {r['tempo']:<6} | {r['resposta_resumo']}")

    print("-" * 110)
    print(f"📊 TAXA DE ACERTO: {passed}/{len(cases)} ({(passed/len(cases))*100:.1f}%) | TEMPO MÉDIO: {total_time/len(cases):.2f}s")
    print("=" * 110)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
