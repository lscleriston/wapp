import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("wapp_rbac")

RBAC_FILE = Path(__file__).parent / "config" / "rbac.json"

def get_user_rbac(phone_number: str) -> Optional[Dict[str, Any]]:
    """Retorna a configuração do usuário pelo número de WhatsApp (com ou sem o dígito 9)."""
    if not RBAC_FILE.exists():
        logger.warning(f"Arquivo RBAC não encontrado em {RBAC_FILE}")
        return None
    try:
        with open(RBAC_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        users = data.get("users", {})
        
        # 1. Busca direta
        clean = phone_number.replace("+", "").replace("-", "").replace(" ", "").strip()
        if clean in users:
            return users[clean]
            
        # 2. Tentar variação com ou sem nono dígito brasileiro (DDD + 8 ou 9 dígitos)
        if clean.startswith("55") and len(clean) == 13:
            without_9 = clean[:4] + clean[5:]
            if without_9 in users:
                return users[without_9]
        elif clean.startswith("55") and len(clean) == 12:
            with_9 = clean[:4] + "9" + clean[4:]
            if with_9 in users:
                return users[with_9]
                
        # 3. Política padrão
        if data.get("default_policy", {}).get("allow_unregistered", False):
            return {
                "name": "Visitante",
                "role": "guest",
                "allowed_scopes": data.get("default_policy", {}).get("default_scopes", [])
            }
        return None
    except Exception as e:
        logger.error(f"Erro lendo RBAC: {e}")
        return None

def check_permission_for_question(phone_number: str, question: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida se o usuário está autorizado a realizar a consulta com base no seu perfil e órgão.
    Retorna: (is_allowed, denial_reason, detected_scope)
    """
    user_info = get_user_rbac(phone_number)
    if not user_info:
        return False, "🔒 Acesso não autorizado: seu número não está registrado no sistema corporativo de BI da Datavizbi. Solicite liberação ao administrador.", None
        
    allowed_scopes = user_info.get("allowed_scopes", [])
    if "*" in allowed_scopes:
        return True, None, "all"
        
    # Verificar se a pergunta menciona algum órgão específico restrito
    q_lower = question.lower()
    scope_keywords = {
        "prf": ["prf", "policia rodoviaria", "dprf", "patrulha"],
        "dnit": ["dnit", "transporte", "rodovias"],
        "dpu": ["dpu", "defensoria"],
        "fnde": ["fnde", "educacao"],
        "mj": ["mj", "ministerio da justica", "justica"],
        "incra": ["incra", "cervello", "reforma agraria"],
        "caesb": ["caesb", "saneamento", "agua", "esgoto"],
        "telefonia": ["telefonia", "ligacoes", "chamadas", "atendidas", "perdidas", "abandono"],
        "glpi": ["glpi", "tickets ti", "chamados ti"]
    }
    
    detected_scope = None
    for scope, kws in scope_keywords.items():
        if any(kw in q_lower for kw in kws):
            detected_scope = scope
            break
            
    if detected_scope and detected_scope not in allowed_scopes:
        return (
            False, 
            f"🔒 Acesso restrito: seu perfil ({user_info.get('role', 'gestor')}) não possui permissão para consultar dados do escopo '{detected_scope.upper()}'.", 
            detected_scope
        )
        
    return True, None, detected_scope
