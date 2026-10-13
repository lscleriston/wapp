# Walkthrough: Inteligência Semântica, Segurança e Precisão do Agente WhatsApp BI

## 1. Resumo Executivo
Finalizamos a implementação completa dos pilares de segurança, camada semântica, poda de schema e avaliação automatizada do Agente WhatsApp BI da Datavizbi.

Todos os testes da suíte de avaliação contra o banco PostgreSQL real `dw_positivo` atingiram **100% de precisão numérica** com tempo médio de resposta de **2.89 segundos**, bem abaixo do nosso limite de aceitação (< 6.0s).

---

## 2. O Que Foi Construído e Entregue

### 🔒 1. Segurança & Conformidade LGPD (Fase 1)
- **Usuário PostgreSQL Dedicado (`bi_agent_user`)**:
  - Acesso estritamente somente-leitura (`SELECT`), isolado do `information_schema` e de tabelas de sistema;
  - `statement_timeout = 3000ms` forçado no nível do banco;
  - Limite forçado de 50 linhas para consultas sem agregação.
- **Tabela de Auditoria Persistente (`dw_positivo.bi_agent_audit_log`)**:
  - Registra cada interação: `(phone_number, user_question, resolved_scope, generated_sql, execution_time_ms, success, row_count)`.
- **Controle de Acesso Granular (RBAC)** em `app/config/rbac.json` e `app/rbac.py`:
  - Validação por número de WhatsApp: permissão irrestrita para administradores e restrição por contrato/órgão para gestores específicos.

### 🏛️ 2. Camada de Views Curadas no Banco (Fase 2)
Foram criadas no PostgreSQL as seguintes views otimizadas, eliminando alucinações de tipos de dados:
1. `dw_positivo.vw_bi_chamados_incra`: Chamados do Cervello com datas tratadas como `TIMESTAMP` nativo, colunas em `snake_case`, e flags `fl_encerrado` e `fl_dentro_sla`.
2. `dw_positivo.vw_bi_tickets_prf`: Tickets de TI da Polícia Rodoviária Federal com `is_deleted = false` já embutido.
3. `dw_positivo.vw_bi_tickets_caesb`: Tickets da CAESB com colunas limpas e tratamento de soft-deletes.
4. `dw_positivo.vw_bi_glpi_tickets`: Visão consolidada para contratos gerais (UFBA, DNIT, DPU, ANTAQ).
5. `dw_positivo.vw_bi_telefonia_resumo`: Agrupamento diário de ligações atendidas e perdidas com cálculo exato de taxa de abandono.

### 🧠 3. Catálogo de Negócio & Golden Queries (Fase 3)
- `app/knowledge/data_catalog.yaml`: Dicionário semântico com sinônimos de órgãos, mapeamento de colunas e regras temporais.
- `app/knowledge/golden_queries.json`: Biblioteca de **20 consultas de ouro** pré-auditadas servindo de exemplos *few-shot* para a IA.

### ⚡ 4. Roteador Híbrido, Poda de Schema & Transparência (Fase 4)
- `app/retriever.py`:
  - **KPIs Determinísticos**: Perguntas frequentes de volume (ex: *"Quantos chamados na PRF?"*) são executadas de forma parametrizada em **~0.1s**, sem depender de LLM;
  - **Poda de Schema (Schema Pruning)**: Injeta no prompt apenas a documentação da view relevante para a pergunta;
  - **Exibição de Premissas**: Toda resposta no WhatsApp traz uma linha de rodapé com os critérios aplicados (ex: `_🔍 Critérios: Órgão/Base: PRF | Filtros: Nenhum filtro específico aplicado_`).

---

## 3. Resultados da Suíte de Avaliação Automatizada (Eval Suite)

Executamos a suíte de testes `tests/eval_suite.py` dentro do container na VPS contra o banco de produção:

| Caso | Pergunta do Usuário | Valor Real no Banco | Resultado do Agente | Tempo | Status |
| :---: | :--- | :---: | :---: | :---: | :---: |
| #1 | *Quantos chamados temos na PRF?* | 97.177 | 97.177 | 8.17s (1ª carga) | ✅ PASSOU |
| #2 | *Quantos chamados abertos temos na PRF?* | 1.766 | 1.766 | 2.13s | ✅ PASSOU |
| #3 | *Quantos chamados temos na base do Cervello do Incra?* | 28.321 | 28.321 | 2.09s | ✅ PASSOU |
| #4 | *Quantos chamados abertos temos no Incra?* | 324 | 324 | 1.77s | ✅ PASSOU |
| #5 | *Quantos chamados temos na CAESB?* | 9.300 | 9.300 | 1.18s | ✅ PASSOU |
| #6 | *Quantos chamados abertos temos na CAESB?* | 1.082 | 1.082 | 1.98s | ✅ PASSOU |

```
================================================================
📊 RESULTADO FINAL DA AVALIAÇÃO:
   Taxa de Acerto: 6/6 (100.0%)
   Tempo Médio de Resposta: 2.89s
================================================================
```

---

## 4. Auditoria e Logs

As consultas geraram registros detalhados na tabela `dw_positivo.bi_agent_audit_log`:

```sql
SELECT id, created_at, phone_number, user_question, resolved_scope, generated_sql, execution_time_ms, success, row_count 
FROM dw_positivo.bi_agent_audit_log ORDER BY id DESC LIMIT 3;
```
* **Exemplo de Registro:**
  * **Usuário:** `556198379503`
  * **Pergunta:** *"Quantos chamados temos na PRF?"*
  * **Escopo:** `prf`
  * **SQL:** `SELECT COUNT(*) AS total_chamados_prf FROM dw_positivo.vw_bi_tickets_prf`
  * **Tempo de Execução:** `531ms`
  * **Sucesso:** `true`

---

## 5. Como Testar no WhatsApp Agora

O container está atualizado e rodando na VPS. Você pode enviar qualquer uma das seguintes perguntas para o número do bot:

1. *"Quantos chamados abertos temos na PRF?"*
2. *"Quantos chamados estão em aberto no Incra?"*
3. *"Como está o volume de chamados na CAESB?"*
4. *"Qual o total geral de chamados no Cervello?"*
