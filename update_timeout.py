import psycopg2

conn = psycopg2.connect(
    host="127.0.0.1",
    port=5432,
    dbname="dw_positivo",
    user="db_user",
    password="4mG62ayIVT0KYb0MIBkK"
)
conn.autocommit = True
cur = conn.cursor()
cur.execute("ALTER ROLE bi_agent_user SET statement_timeout = '8000ms';")
print("Role bi_agent_user statement_timeout atualizado para 8000ms!")
