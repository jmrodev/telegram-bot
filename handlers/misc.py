# handlers/misc.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
import keyboards
from .utils import send_main_menu # <<< IMPORT DESDE UTILS

logger = logging.getLogger(__name__)

# Almacenamiento temporal (Considerar context.bot_data o BD)
patient_confirmations = {}

# --- PEGAR AQUÍ EL RESTO DE FUNCIONES MISC DE LA VERSIÓN ANTERIOR ---
# handle_secretary_message, handle_yes_no
async def handle_secretary_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id; user = update.effective_user
    logger.info(f"{chat_id}: Msj p/Sec:'{text}'")
    log_msg = f"Msj Sec de @{user.username or user.first_name}(ID:{chat_id}): {text}"
    logger.info(f"Simulando envío: {log_msg}")
    # --- TODO: Notificar a Secretaria ---
    if config.SECRETARY_CHAT_ID:
       try: await context.bot.send_message(chat_id=config.SECRETARY_CHAT_ID, text=log_msg)
       except Exception as e: logger.error(f"Error notificar sec ({config.SECRETARY_CHAT_ID}): {e}")
       await update.message.reply_text("Mensaje enviado. Sigue o /start.")
    else:
         logger.warning("SECRETARY_CHAT_ID no config. No notificar.")
         await update.message.reply_text("Mensaje recibido (Sec no notificada). Usa /start.")
    # Mantenemos estado

async def handle_yes_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    text = update.message.text; chat_id = update.effective_chat.id; user = update.effective_user
    lower_case_text = text.lower(); processed = False; notification_text = None
    if lower_case_text in ['sí', 'si']:
        logger.info(f"SÍ de {chat_id} (no state)")
        context.user_data['last_confirmation'] = {"r": "Sí", "t": update.message.date}
        await update.message.reply_text("Confirmado. ¡Gracias!")
        notification_text = f"Confirmación SÍ: @{user.username or user.first_name}({chat_id})"
        processed = True
    elif lower_case_text == 'no':
        logger.info(f"NO de {chat_id} (no state)")
        context.user_data['last_confirmation'] = {"r": "No", "t": update.message.date}
        await update.message.reply_text("Entendido. Gracias.")
        notification_text = f"Confirmación NO: @{user.username or user.first_name}({chat_id})"
        processed = True
    # --- TODO: Notificar a Secretaria ---
    if processed and config.SECRETARY_CHAT_ID and notification_text:
         try: await context.bot.send_message(chat_id=config.SECRETARY_CHAT_ID, text=notification_text)
         except Exception as e: logger.error(f"Error notificar S/N a sec: {e}")
    elif processed and not config.SECRETARY_CHAT_ID: logger.warning("Conf S/N recibida, SECRETARY_CHAT_ID no config.")
    # ------------------------------------
    return processed