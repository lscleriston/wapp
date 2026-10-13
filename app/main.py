import logging
from fastapi import FastAPI, Request, Response, BackgroundTasks, Query, HTTPException
from app.config import settings
from app.agent import process_user_message
from app.whatsapp import send_whatsapp_message, mark_as_read
from app.database import execute_safe_query
from app.rbac import check_permission_for_question

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("wapp_main")

app = FastAPI(title="Datavizbi WhatsApp BI Agent", version="1.0.0")

processed_message_ids = set()

async def handle_incoming_message(sender_id: str, message_id: str, text: str, recipient_phone_id: str):
    """Executado em segundo plano para não travar a resposta HTTP da Meta."""
    logger.info(f"Processando mensagem de {sender_id} no número {recipient_phone_id}: {text}")
    
    # 1. Marcar como lido no WhatsApp (dois tiques azuis)
    await mark_as_read(message_id, phone_number_id=recipient_phone_id)
    
    # 2. Verificar controle de acesso e RBAC granular (por número e por órgão/escopo)
    is_allowed, denial_reason, detected_scope = check_permission_for_question(sender_id, text)
    if not is_allowed:
        logger.warning(f"Acesso bloqueado por RBAC para {sender_id}: {denial_reason}")
        await send_whatsapp_message(
            sender_id,
            denial_reason,
            phone_number_id=recipient_phone_id
        )
        return
            
    # 3. Processar mensagem com o agente inteligente
    response_text = await process_user_message(sender_id, text, detected_scope=detected_scope)
    
    # 4. Enviar a resposta de volta ao usuário pelo mesmo número que recebeu
    await send_whatsapp_message(sender_id, response_text, phone_number_id=recipient_phone_id)

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """Validação do Webhook exigida pela Meta."""
    logger.info(f"Handshake recebido: mode={hub_mode}, token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook validado com sucesso!")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("Falha na validação do token do webhook.")
    raise HTTPException(status_code=403, detail="Verification token mismatch")

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe eventos de mensagens em tempo real da Meta."""
    payload = await request.json()
    logger.info(f"Webhook POST recebido: {payload}")
    
    entries = payload.get("entry", [])
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            recipient_phone_id = metadata.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
            
            messages = value.get("messages", [])
            for msg in messages:
                message_id = msg.get("id")
                if not message_id or message_id in processed_message_ids:
                    continue
                    
                processed_message_ids.add(message_id)
                if len(processed_message_ids) > 1000:
                    processed_message_ids.clear()
                    
                sender_id = msg.get("from")
                msg_type = msg.get("type")
                
                if msg_type == "text":
                    body_text = msg.get("text", {}).get("body", "").strip()
                    background_tasks.add_task(
                        handle_incoming_message,
                        sender_id,
                        message_id,
                        body_text,
                        recipient_phone_id
                    )
                else:
                    logger.info(f"Recebido tipo de mensagem não-texto: {msg_type} de {sender_id}")
                    background_tasks.add_task(
                        send_whatsapp_message,
                        sender_id,
                        "💡 Olá! Atualmente consigo responder apenas perguntas enviadas em formato de texto.",
                        phone_number_id=recipient_phone_id
                    )
                    
    return {"status": "ok"}

@app.get("/health")
def health_check():
    """Checagem de integridade e conectividade com o banco."""
    test_db = execute_safe_query("SELECT 1 as ping;")
    return {
        "status": "online",
        "database": "connected" if test_db["success"] else "error",
        "database_error": test_db.get("error")
    }
