import psycopg2
import json

def inspect():
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        dbname="dw_positivo",
        user="db_user",
        password="4mG62ayIVT0KYb0MIBkK"
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'dw_positivo' 
        ORDER BY table_name;
    """)
    tables = [r[0] for r in cur.fetchall()]
    print(f"Total de tabelas no schema 'dw_positivo': {len(tables)}")
    print(json.dumps(tables, indent=2))

if __name__ == "__main__":
    inspect()
