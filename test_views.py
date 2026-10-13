import psycopg2

def test_queries():
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        dbname="dw_positivo",
        user="db_user",
        password="4mG62ayIVT0KYb0MIBkK"
    )
    cur = conn.cursor()
    
    # Test 1: Cervello date casting
    print("Testing Cervello date format...")
    cur.execute("""
        SELECT 
            "Chamado", 
            "Data_de_Abertura_Sem_Formato", 
            NULLIF("Data_de_Abertura_Sem_Formato", '')::timestamp as dt
        FROM dw_positivo.tb_cervello_chamados_incra 
        WHERE "Data_de_Abertura_Sem_Formato" IS NOT NULL AND "Data_de_Abertura_Sem_Formato" != ''
        LIMIT 5;
    """)
    for r in cur.fetchall():
        print("  Cervello sample:", r)

    # Test 2: PRF view
    print("\nTesting PRF view...")
    cur.execute("""
        SELECT ticket, "Resumo", "Data de Abertura", status, is_deleted 
        FROM dw_positivo.vw_glpi_ticket_dprf 
        WHERE is_deleted = false
        LIMIT 3;
    """)
    for r in cur.fetchall():
        print("  PRF sample:", r)

    # Test 3: Telefonia union
    print("\nTesting Telefonia summary...")
    cur.execute("""
        SELECT 
            data, 
            operacao, 
            COUNT(*) FILTER (WHERE tipo = 'atendida') AS atendidas,
            COUNT(*) FILTER (WHERE tipo = 'perdida') AS perdidas
        FROM (
            SELECT data, operacao, 'atendida' AS tipo FROM dw_positivo.tb_telefonia_atendidas
            UNION ALL
            SELECT data, operacao, 'perdida' AS tipo FROM dw_positivo.tb_telefonia_perdidas
        ) t
        GROUP BY data, operacao
        LIMIT 3;
    """)
    for r in cur.fetchall():
        print("  Telefonia sample:", r)

    print("\nALL PRE-CHECKS PASSED!")

if __name__ == "__main__":
    test_queries()
