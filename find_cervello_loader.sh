#!/bin/bash

echo "=== 1. VERIFICAR TABELAS CERVELLO ==="
sudo -u postgres psql -d dw_positivo -c "
SELECT 'tb_cervello_chamados_incra' as tab, count(*) as total, max(\"Data_de_Fechamento_Sem_Formato\") as max_data FROM dw_positivo.tb_cervello_chamados_incra
UNION ALL
SELECT 'tb_cervello_base_utilizacao', count(*), null FROM dw_positivo.tb_cervello_base_utilizacao
UNION ALL
SELECT 'tb_cervello_pesquisa_satisfacao', count(*), null FROM dw_positivo.tb_cervello_pesquisa_satisfacao;
"

echo "=== 2. LOCALIZAR OCORRÊNCIAS DE 'cervello' E 'tb_cervello' NO SERVIDOR ==="
grep -rnwi "tb_cervello" /home/ 2>/dev/null || true
grep -rnwi "cervello" /home/dw-integration/ 2>/dev/null || true
grep -rnwi "tb_cervello" /opt/ 2>/dev/null || true
grep -rnwi "cervello" /opt/airflow/ 2>/dev/null || true

echo "=== 3. CRON JOBS NO SERVIDOR ==="
crontab -l || true
for user in $(cut -f1 -d: /etc/passwd); do
    crontab -u "$user" -l 2>/dev/null || true
done
cat /etc/crontab 2>/dev/null || true
ls -la /etc/cron.* 2>/dev/null || true

echo "=== 4. DAGS NO AIRFLOW ==="
docker exec $(docker ps -q -f name=airflow-scheduler | head -n 1) airflow dags list 2>/dev/null || true
