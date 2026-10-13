import asyncio
from app.agent import process_user_message

async def main():
    phone = "556198379503"
    
    # Teste 1: PRF
    q1 = "Quantos chamados temos registrados na PRF?"
    print(f"\n======================================")
    print(f"Pergunta 1: {q1}")
    r1 = await process_user_message(phone, q1, detected_scope="prf")
    print("\nResposta do Agente:\n", r1)

    # Teste 2: INCRA
    q2 = "Quantos chamados com status fechado temos no Cervello do Incra?"
    print(f"\n======================================")
    print(f"Pergunta 2: {q2}")
    r2 = await process_user_message(phone, q2, detected_scope="incra")
    print("\nResposta do Agente:\n", r2)

if __name__ == "__main__":
    asyncio.run(main())
