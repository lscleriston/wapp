import asyncio
from app.agent import process_user_message

async def main():
    phone = "556198379503"
    q = "Quantos chamados abertos temos na PRF?"
    print(f"\n======================================")
    print(f"Executando pergunta: {q}")
    r = await process_user_message(phone, q)
    print(f"\nRESPOSTA FINAL:\n{r}")

if __name__ == "__main__":
    asyncio.run(main())
