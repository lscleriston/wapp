# Arquitetura de Dados - DW Positivo

Este repositório contém a documentação técnica, propostas de arquitetura e artefatos visuais interativos para a reestruturação e modernização do **Data Warehouse (DW Positivo)**, com foco em alinhamento entre as equipes de **Engenharia de Dados**, **Business Intelligence (BI)** e **Segurança da Informação (InfoSec)**.

---

## 📌 Contexto e Problema Atual

Atualmente, a coleta e consolidação dos dados operam no seguinte formato:
- **Hospedagem em VPS Externa:** Os dados de ITSM e Zabbix de clientes são coletados via scripts e armazenados em um banco PostgreSQL (`dw.positivo`).
- **Conexão Direta ao Power BI:** Os relatórios em Power BI Service conectam diretamente à porta 5432 do PostgreSQL público.
- **Limitações e Riscos Críticos Identificados:**
  1. **Exposição de Segurança:** A porta do banco exposta publicamente na internet e o armazenamento de credenciais, tokens de API e topologias de rede Zabbix em VPS de terceiros criam riscos contratuais e de invasão.
  2. **Inviabilidade de Coleta de Clientes Privados:** Clientes cujos ambientes (ITSM/Zabbix) não possuem IP público não podem ser monitorados, pois fechar VPNs Site-to-Site com uma VPS avulsa é inviável técnica e financeiramente.
  3. **Dados de Telefonia (QueueMetrics) Bloqueados:** O servidor QueueMetrics fica no Datacenter corporativo. O acesso a partir da rede do escritório passa por autenticação interativa (Captive Portal Fortinet via navegador), o que impede pipelines de automação e cron jobs.

---

## 📊 Cenários Avaliados

| Cenário | Descrição | Segurança | Telefonia (QueueMetrics) | Power BI | Custo | Confiabilidade |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Cenário 0** | **VPS Atual (Legado)** | ❌ Crítico (Porta aberta) | ❌ Inviável | ⚠️ Direto (Inseguro) | Baixo | Médio |
| **Cenário 1** | **Datacenter Corporativo + PBI Gateway (Recomendado)** | ✅ 100% Isolado | ✅ Nativo (Mesma rede) | ✅ PBI Gateway (Outbound TLS) | Baixo (Infra interna) | Alto (DC) |
| **Cenário 2** | **Azure Híbrida (Hub-and-Spoke via DC)** | ✅ Rede Privada | ✅ Roteado via Túnel DC | ✅ Conexão Nuvem | Médio/Alto ($$) | Altíssimo |
| **Cenário 3** | **Desktops no Escritório (Paliativo)** | ⚠️ Vulnerável fisicamente | ❌ Bloqueado Fortinet | ⚠️ Gateway Local | Baixo | ❌ Sem no-break/SLA |

---

## 🏆 Cenário Recomendado: Cenário 1 (Datacenter Corporativo + Power BI Gateway)

### Topologia Proposta:
1. **VM Linux no Datacenter:**
   * Hospeda o banco de dados PostgreSQL (`dw.positivo`, ~20 GB).
   * Executa os pipelines de ingestão de hora em hora.
   * Conecta diretamente ao banco de telefonia QueueMetrics (mesmo ambiente de DC, eliminando o captive portal do Fortinet).
   * Conecta aos clientes fechados via VPN corporativa existente e Jump Points com contas de serviço.
   * **Nenhuma porta de entrada pública exposta**.
2. **VM Windows no Datacenter:**
   * Executa o **Power BI On-premises Data Gateway**.
   * Conecta internamente ao PostgreSQL e publica os dados na nuvem da Microsoft via canal seguro de saída (**Outbound TLS 443** / Azure Service Bus Relay).
   * Dispensa abertura de portas de entrada em firewalls corporativos.

---

## 🖥️ Como Visualizar a Apresentação Interativa

O repositório inclui a aplicação visual interativa:
- [`arquitetura_dw_positivo.html`](./arquitetura_dw_positivo.html)

### Recursos do Dashboard HTML:
- **Alternador de Cenários:** Navegue facilmente entre os 4 cenários (Cenário 0 ao 3).
- **Diagramas Vetoriais (SVG):** Desenhos técnicos com animação de fluxo de dados, portas de rede e perímetros de segurança.
- **Matriz de Decisão:** Tabela comparativa de riscos, custos e viabilidade técnica.
- **Argumentos de Alinhamento:** Resumo executivo específico para conversar com **Segurança**, **Engenharia de Dados** e **BI**.

> **Para abrir:** Basta clonar o repositório ou baixar o arquivo `arquitetura_dw_positivo.html` e abrir em qualquer navegador web (Google Chrome, Microsoft Edge, etc.).

---

## 🚀 Próximos Passos & Solicitações

- [ ] Solicitar provisionamento das VMs (Linux e Windows Server) junto à equipe de Infraestrutura do Datacenter.
- [ ] Solicitar liberação de rota de rede interna para o servidor de QueueMetrics.
- [ ] Negociar com a Segurança a criação de contas de serviço ou túneis automatizados para os Jump Points dos clientes.
- [ ] Instalar e configurar o Power BI On-premises Data Gateway na VM Windows.
- [ ] Migrar a base de dados PostgreSQL e os agendamentos horários da VPS para o Datacenter.
