import os
import urllib.request
import json
import time

api_key = os.getenv("GEMINI_API_KEY", "")
m = "gemini-3.5-flash"

prompt = "Você é um analista SQL. Escreva APENAS a consulta PostgreSQL para contar quantos chamados existem na tabela dw_positivo.tb_cervello_chamados_incra. Responda apenas com a query SELECT."
payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")

url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode())
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    print(f"MODEL {m}: SUCCESS ({round(time.time() - t0, 2)}s)\n{text}")
