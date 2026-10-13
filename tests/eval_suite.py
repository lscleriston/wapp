import asyncio
import time
import re
from typing import List, Dict, Any
from app.agent import process_user_message

EVAL_CASES = [
    {
        "id": 1,
        "question": "Quantos chamados temos na PRF?",
        "expected_value": 97177,
        "scope": "prf"
    },
    {
        "id": 2,
        "question": "Quantos chamados abertos temos na PRF?",
        "expected_value": 1766,
        "scope": "prf"
    },
    {
        "id": 3,
        "question": "Quantos chamados temos na base do Cervello do Incra?",
        "expected_value": 28321,
        "scope": "incra"
    },
    {
        "id": 4,
        "question": "Quantos chamados abertos temos no Incra?",
        "expected_value": 324,
        "scope": "incra"
    },
    {
        "id": 5,
        "question": "Quantos chamados temos na CAESB?",
        "expected_value": 9300,
        "scope": "caesb"
    },
    {
        "id": 6,
        "question": "Quantos chamados abertos temos na CAESB?",
        "expected_value": 1082,
        "scope": "caesb"
    },
    {
        "id": 7,
        "question": "Quantos chamados temos no DNIT?",
        "expected_value": 32214,
        "scope": "dnit"
    },
    {
        "id": 8,
        "question": "Quantos chamados abertos temos no DNIT?",
        "expected_value": 225,
        "scope": "dnit"
    }
]

async def run_evaluation():
    print("================================================================")
    print("🚀 INICIANDO SUÍTE DE AVALIAÇÃO DE PRECISÃO NUMÉRICA (EVAL SUITE)")
    print("================================================================")
    
    passed = 0
    total = len(EVAL_CASES)
    total_time = 0.0

    for test in EVAL_CASES:
        t0 = time.time()
        q = test["question"]
        expected = test["expected_value"]
        scope = test["scope"]
        
        print(f"\n[Caso #{test['id']}] Pergunta: '{q}' (Esperado: {expected:,})")
        try:
            reply = await process_user_message("EVAL_USER_556198379503", q, detected_scope=scope)
            elapsed = time.time() - t0
            total_time += elapsed
            
            # Normalizar números na resposta (remover pontos de milhar para comparação)
            # Buscar o número na resposta
            # Ex: 97.177 ou 97177 ou 1.766 ou 1766
            normalized_reply = re.sub(r"(\d+)\.(\d{3})", r"\1\2", reply)
            
            is_match = str(expected) in normalized_reply
            status = "✅ PASSOU" if is_match else "❌ FALHOU"
            if is_match:
                passed += 1
                
            print(f"Resultado: {status} em {elapsed:.2f}s")
            print(f"Trecho da Resposta: {reply[:120].strip()}...")
        except Exception as e:
            print(f"Resultado: ❌ ERRO ({e})")
            
    print("\n================================================================")
    print(f"📊 RESULTADO FINAL DA AVALIAÇÃO:")
    print(f"   Taxa de Acerto: {passed}/{total} ({(passed/total)*100:.1f}%)")
    print(f"   Tempo Médio de Resposta: {total_time/total:.2f}s")
    print("================================================================")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
