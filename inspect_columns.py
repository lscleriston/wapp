import psycopg2
import json

conn = psycopg2.connect(
    host="127.0.0.1",
    port=5432,
    dbname="dw_positivo",
    user="db_user",
    password="4mG62ayIVT0KYb0MIBkK"
)
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_schema = 'dw_positivo' AND table_name = 'tb_cervello_chamados_incra'
    ORDER BY ordinal_position;
""")
cols = cur.fetchall()
for col, dt in cols:
    print(f"{col}: {dt}")
