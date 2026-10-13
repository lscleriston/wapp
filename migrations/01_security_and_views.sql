-- ==============================================================================
-- Migração 01: Segurança, RBAC, Auditoria e Views Curadas (bi_agent)
-- Banco de Dados: dw_positivo (PostgreSQL 15)
-- ==============================================================================

-- 1. Usuário Dedicado de Execução do Agente
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bi_agent_user') THEN
        CREATE ROLE bi_agent_user WITH LOGIN PASSWORD 'DEFINA_SUA_SENHA_AQUI';
    ELSE
        ALTER ROLE bi_agent_user WITH PASSWORD 'DEFINA_SUA_SENHA_AQUI';
    END IF;
END
$$;

ALTER ROLE bi_agent_user SET statement_timeout = '3000ms';
ALTER ROLE bi_agent_user SET search_path = dw_positivo, public;

-- 2. Tabela de Auditoria e Conformidade LGPD
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

-- 3. View Curada: Cervello INCRA (Datas em Timestamp nativo e snake_case)
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

-- 4. View Curada: GLPI Geral (Filtro is_deleted=false embutido)
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

-- 5. View Curada: PRF (Polícia Rodoviária Federal)
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

-- 6. View Curada: CAESB
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

-- 7. View Curada: Telefonia Resumo Diário
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

-- 8. Concessão de Privilégios ao Usuário Restrito
GRANT CONNECT ON DATABASE dw_positivo TO bi_agent_user;
GRANT USAGE ON SCHEMA dw_positivo TO bi_agent_user;
REVOKE ALL ON ALL TABLES IN SCHEMA dw_positivo FROM bi_agent_user;

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

GRANT SELECT, INSERT ON dw_positivo.bi_agent_audit_log TO bi_agent_user;
GRANT USAGE, SELECT ON SEQUENCE dw_positivo.bi_agent_audit_log_id_seq TO bi_agent_user;
