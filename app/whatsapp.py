import logging
import httpx
from app.config import settings

logger = logging.getLogger("wapp_whatsapp")

async def send_whatsapp_message(to_number: str, text: str, phone_number_id: str = None) -> bool:
    """Envia uma mensagem de texto pelo WhatsApp Cloud API com fallback automático de número."""
    phone_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code in (200, 201):
                logger.info(f"Mensagem enviada com sucesso para {to_number} pelo número {phone_id}")
                return True
            
            logger.warning(f"Erro ao enviar pelo número {phone_id}: {response.status_code} - {response.text}")
            
            # Se der erro de Display Name (131037), tentar pelo número secundário/teste
            if "131037" in response.text and phone_id != "1404678252724977":
                fallback_id = "1404678252724977"
                logger.info(f"Tentando fallback para o número de teste {fallback_id}...")
                fallback_url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{fallback_id}/messages"
                fallback_resp = await client.post(fallback_url, json=payload, headers=headers)
                if fallback_resp.status_code in (200, 201):
                    logger.info(f"Mensagem enviada com sucesso pelo número fallback {fallback_id}")
                    return True
                else:
                    logger.error(f"Fallback falhou: {fallback_resp.status_code} - {fallback_resp.text}")
            return False
    except Exception as e:
        logger.error(f"Exceção enviando mensagem para {to_number}: {e}")
        return False

async def mark_as_read(message_id: str, phone_number_id: str = None) -> bool:
    """Marca a mensagem do usuário como lida (dois tiques azuis)."""
    phone_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            return response.status_code in (200, 201)
    except Exception as e:
        logger.warning(f"Não foi possível marcar mensagem como lida: {e}")
        return False
