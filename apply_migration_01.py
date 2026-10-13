import psycopg2
import sys

def apply():
    print("Iniciando aplicação da Migração 01 (Segurança & Views Curadas)...")
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        dbname="dw_positivo",
        user="db_user",
        password="4mG62ayIVT0KYb0MIBkK"
    )
    conn.autocommit = True
    cur = conn.cursor()

    # 1. Usuário de Banco Dedicado Read-Only
    print("1. Configurando usuário 'bi_agent_user'...")
    db_pass = os.getenv("PG_PASSWORD", "")
    if not db_pass:
        raise ValueError("A variável de ambiente PG_PASSWORD é obrigatória.")
    cur.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bi_agent_user') THEN
                CREATE ROLE bi_agent_user WITH LOGIN PASSWORD '{db_pass}';
            ELSE
                ALTER ROLE bi_agent_user WITH PASSWORD '{db_pass}';
            END IF;
        END
        $$;
    """)
    cur.execute("ALTER ROLE bi_agent_user SET statement_timeout = '3000ms';")
    cur.execute("ALTER ROLE bi_agent_user SET search_path = dw_positivo, public;")
    print("   -> Usuário 'bi_agent_user' pronto com statement_timeout = 3000ms.")

    # 2. Tabela de Auditoria e LGPD
    print("2. Criando tabela de auditoria 'bi_agent_audit_log'...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dw_positivo.bi_agent_audit_log (
            id BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            phone_number VARCHAR(30) NOT NULL,
            user_question TEXT NOT NULL,
            resolved_scope VARCHAR(50),
            generated_sql TEXT,
            execution_time_ms INTEGER,
            success BOOLEAN NOT NULL DEFAULT FALSE,
            row_count INTEGER DEFAULT 0,
            error_message TEXT,
            needs_review BOOLEAN DEFAULT FALSE
        );
        CREATE INDEX IF NOT EXISTS idx_bi_audit_phone ON dw_positivo.bi_agent_audit_log(phone_number);
        CREATE INDEX IF NOT EXISTS idx_bi_audit_created ON dw_positivo.bi_agent_audit_log(created_at);
    """)
    print("   -> Tabela de auditoria criada/verificada.")

    # 3. View Curada: Cervello INCRA
    print("3. Criando view curada 'vw_bi_chamados_incra'...")
    cur.execute("""
        CREATE OR REPLACE VIEW dw_positivo.vw_bi_chamados_incra AS
        SELECT 
            "Chamado" AS chamado_id,
            "Chamado_Codigo_Real" AS codigo_real,
            NULLIF("Data_de_Abertura_Sem_Formato", '')::timestamp AS data_abertura,
            NULLIF("Data_de_Fechamento_Sem_Formato", '')::timestamp AS data_fechamento,
            NULLIF("Data_de_1o_Atendimento_Sem_Formato", '')::timestamp AS data_primeiro_atendimento,
            "Nome_do_Favorecido" AS favorecido,
            "Departamento_do_Favorecido" AS departamento,
            "Localidade_do_Favorecido" AS localidade,
            "Categoria" AS categoria,
            "Item_Subcategoria" AS subcategoria,
            "Tipo" AS tipo,
            "Prioridade" AS prioridade,
            "Estado" AS status,
            CASE 
                WHEN UPPER("Estado") IN ('FECHADO', 'ENCERRADO', 'CANCELADO') THEN true 
                ELSE false 
            END AS fl_encerrado,
            "SLA_Solucao_Situacao" AS situacao_sla,
            CASE 
                WHEN UPPER("SLA_Solucao_Situacao") LIKE '%DENTRO%' THEN true 
                ELSE false 
            END AS fl_dentro_sla,
            "Analista_Atual" AS analista,
            "Grupo_Analista_Atual" AS grupo_analista,
            "Descricao_Chamado" AS descricao,
            "Resumo_Chamado" AS resumo
        FROM dw_positivo.tb_cervello_chamados_incra;
    """)
    print("   -> 'vw_bi_chamados_incra' criada com sucesso.")

    # 4. View Curada: GLPI Geral
    print("4. Criando view curada 'vw_bi_glpi_tickets'...")
    cur.execute("""
        CREATE OR REPLACE VIEW dw_positivo.vw_bi_glpi_tickets AS
        SELECT 
            id AS ticket_id,
            operacao AS contrato,
            name AS titulo,
            date AS data_abertura,
            closedate AS data_fechamento,
            solvedate AS data_solucao,
            status,
            CASE 
                WHEN LOWER(status) IN ('fechado', 'solucionado') THEN true 
                ELSE false 
            END AS fl_encerrado,
            priority AS prioridade,
            urgency AS urgencia,
            impact AS impacto
        FROM dw_positivo.tb_glpi_ticket
        WHERE is_deleted = false;
    """)
    print("   -> 'vw_bi_glpi_tickets' criada com sucesso.")

    # 5. View Curada: PRF (Polícia Rodoviária Federal)
    print("5. Criando view curada 'vw_bi_tickets_prf'...")
    cur.execute("""
        CREATE OR REPLACE VIEW dw_positivo.vw_bi_tickets_prf AS
        SELECT 
            ticket AS ticket_id,
            "Resumo" AS titulo,
            "Data de Abertura" AS data_abertura,
            "Data de Fechamento" AS data_fechamento,
            "Data de Solução" AS data_solucao,
            status,
            CASE 
                WHEN UPPER(status) IN ('FECHADO', 'SOLUCIONADO') THEN true 
                ELSE false 
            END AS fl_encerrado,
            priority AS prioridade,
            "Categoria" AS categoria,
            "Groupo" AS grupo,
            "Solicitante" AS solicitante,
            "Analista" AS analista,
            "Localidade" AS localidade,
            "Tempo Atendimento (S)" AS tempo_atendimento_segundos
        FROM dw_positivo.vw_glpi_ticket_dprf
        WHERE is_deleted = false;
    """)
    print("   -> 'vw_bi_tickets_prf' criada com sucesso.")

    # 6. View Curada: CAESB
    print("6. Criando view curada 'vw_bi_tickets_caesb'...")
    cur.execute("""
        CREATE OR REPLACE VIEW dw_positivo.vw_bi_tickets_caesb AS
        SELECT 
            ticket AS ticket_id,
            "Resumo" AS titulo,
            "Data de Abertura" AS data_abertura,
            "Data de Fechamento" AS data_fechamento,
            "Data de Solução" AS data_solucao,
            status,
            CASE 
                WHEN UPPER(status) IN ('FECHADO', 'SOLUCIONADO') THEN true 
                ELSE false 
            END AS fl_encerrado,
            priority AS prioridade,
            "Categoria" AS categoria,
            "Groupo" AS grupo,
            "Solicitante" AS solicitante,
            "Analista" AS analista,
            "Localidade" AS localidade,
            "Tempo Atendimento (S)" AS tempo_atendimento_segundos
        FROM dw_positivo.vw_glpi_ticket_caesb
        WHERE is_deleted = false;
    """)
    print("   -> 'vw_bi_tickets_caesb' criada com sucesso.")

    # 7. View Curada: Telefonia Resumo
    print("7. Criando view curada 'vw_bi_telefonia_resumo'...")
    cur.execute("""
        CREATE OR REPLACE VIEW dw_positivo.vw_bi_telefonia_resumo AS
        SELECT 
            data,
            operacao,
            COUNT(*) FILTER (WHERE tipo = 'atendida') AS total_atendidas,
            COUNT(*) FILTER (WHERE tipo = 'perdida') AS total_perdidas,
            COUNT(*) AS total_chamadas,
            ROUND(COUNT(*) FILTER (WHERE tipo = 'perdida')::numeric / NULLIF(COUNT(*), 0) * 100, 2) AS taxa_perda_percentual
        FROM (
            SELECT data, operacao, 'atendida' AS tipo FROM dw_positivo.tb_telefonia_atendidas
            UNION ALL
            SELECT data, operacao, 'perdida' AS tipo FROM dw_positivo.tb_telefonia_perdidas
        ) t
        GROUP BY data, operacao;
    """)
    print("   -> 'vw_bi_telefonia_resumo' criada com sucesso.")

    # 8. Permissões estritas para bi_agent_user
    print("8. Aplicando permissões de segurança para bi_agent_user...")
    cur.execute("GRANT CONNECT ON DATABASE dw_positivo TO bi_agent_user;")
    cur.execute("GRANT USAGE ON SCHEMA dw_positivo TO bi_agent_user;")
    cur.execute("REVOKE ALL ON ALL TABLES IN SCHEMA dw_positivo FROM bi_agent_user;")
    
    # Permitir SELECT nas views curadas e tabelas de leitura necessárias
    cur.execute("""
        GRANT SELECT ON 
            dw_positivo.vw_bi_chamados_incra,
            dw_positivo.vw_bi_glpi_tickets,
            dw_positivo.vw_bi_tickets_prf,
            dw_positivo.vw_bi_tickets_caesb,
            dw_positivo.vw_bi_telefonia_resumo,
            dw_positivo.tb_cervello_chamados_incra,
            dw_positivo.tb_glpi_ticket,
            dw_positivo.tb_telefonia_atendidas,
            dw_positivo.tb_telefonia_perdidas,
            dw_positivo.vw_glpi_ticket_dprf,
            dw_positivo.vw_glpi_ticket_caesb
        TO bi_agent_user;
    """)
    
    # Permitir SELECT e INSERT na auditoria
    cur.execute("GRANT SELECT, INSERT ON dw_positivo.bi_agent_audit_log TO bi_agent_user;")
    cur.execute("GRANT USAGE, SELECT ON SEQUENCE dw_positivo.bi_agent_audit_log_id_seq TO bi_agent_user;")
    print("   -> Permissões de read-only restrito concedidas com sucesso!")

    # 9. Teste de conexão do usuário restrito
    print("9. Testando conexão com bi_agent_user...")
    conn_restricted = psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        dbname="dw_positivo",
        user="bi_agent_user",
        password=db_pass
    )
    cur_res = conn_restricted.cursor()
    cur_res.execute("SELECT count(*) FROM dw_positivo.vw_bi_chamados_incra;")
    cnt_incra = cur_res.fetchone()[0]
    print(f"   -> Consulta via 'bi_agent_user' em vw_bi_chamados_incra: {cnt_incra} registros.")
    
    cur_res.execute("SELECT count(*) FROM dw_positivo.vw_bi_tickets_prf;")
    cnt_prf = cur_res.fetchone()[0]
    print(f"   -> Consulta via 'bi_agent_user' em vw_bi_tickets_prf: {cnt_prf} registros.")

    cur_res.execute("""
        INSERT INTO dw_positivo.bi_agent_audit_log (
            phone_number, user_question, resolved_scope, generated_sql, execution_time_ms, success, row_count
        ) VALUES (
            'SYSTEM_SETUP', 'Teste de auditoria inicial', 'setup', 'SELECT 1;', 5, true, 1
        ) RETURNING id;
    """)
    audit_id = cur_res.fetchone()[0]
    print(f"   -> Teste de inserção de auditoria via 'bi_agent_user': ID {audit_id} inserido com sucesso!")
    
    conn_restricted.close()
    conn.close()
    print("\n✅ MIGRAÇÃO 01 CONCLUÍDA COM SUCESSO TOTAL!")

if __name__ == "__main__":
    apply()
