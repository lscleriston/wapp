import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("PG_HOST", "127.0.0.1"),
    port=int(os.getenv("PG_PORT", "5432")),
    dbname=os.getenv("PG_DB", "dw_positivo"),
    user=os.getenv("PG_USER", "bi_agent_user"),
    password=os.getenv("PG_PASSWORD", "")
)
cur = conn.cursor()

tests = [
    ("PRF Total", "SELECT COUNT(*) FROM dw_positivo.vw_bi_tickets_prf;"),
    ("PRF Abertos", "SELECT COUNT(*) FROM dw_positivo.vw_bi_tickets_prf WHERE fl_encerrado = false;"),
    ("INCRA Total", "SELECT COUNT(*) FROM dw_positivo.vw_bi_chamados_incra;"),
    ("INCRA Abertos", "SELECT COUNT(*) FROM dw_positivo.vw_bi_chamados_incra WHERE fl_encerrado = false;"),
    ("CAESB Total", "SELECT COUNT(*) FROM dw_positivo.vw_bi_tickets_caesb;"),
    ("CAESB Abertos", "SELECT COUNT(*) FROM dw_positivo.vw_bi_tickets_caesb WHERE fl_encerrado = false;"),
    ("GLPI Total", "SELECT COUNT(*) FROM dw_positivo.vw_bi_glpi_tickets;"),
    ("Telefonia Total Atendidas", "SELECT SUM(total_atendidas) FROM dw_positivo.vw_bi_telefonia_resumo;")
]

for label, sql in tests:
    cur.execute(sql)
    val = cur.fetchone()[0]
    print(f"{label}: {val}")
