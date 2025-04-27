# handlers/utils.py
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
# Importar config y keyboards directamente, ya que son de nivel superior
import config
import keyboards

logger = logging.getLogger(__name__)

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Por favor, elige una opción:") -> None:
    """Envía el menú principal y limpia estado."""
    chat_id = update.effective_chat.id
    if not chat_id: # Seguridad por si no hay chat_id
        logger.warning("send_main_menu llamado sin chat_id efectivo.")
        return

    context.user_data.clear() # Limpiar datos/estado del usuario
    logger.debug(f"Limpiando estado y enviando menú principal a {chat_id}")

    # --- Lógica Corregida ---
    message_to_reply = update.message or (update.callback_query.message if update.callback_query else None)

    if message_to_reply:
        # Si tenemos un mensaje (del comando /start o de un botón/texto), respondemos a él
        await message_to_reply.reply_text(text, reply_markup=keyboards.main_menu_markup)
    elif update.effective_chat:
        # Si NO tenemos un mensaje específico pero sí un chat, enviamos un nuevo mensaje
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboards.main_menu_markup)
        except Exception as e:
            logger.error(f"Error enviando mensaje a {chat_id} en send_main_menu fallback: {e}")
    else:
        logger.error(f"No se pudo determinar cómo enviar el menú principal para el update: {update}")
    # --- Fin Lógica Corregida ---


async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
     """Manejador para el botón de cancelar acción."""
     chat_id = update.effective_chat.id
     logger.info(f"Acción cancelada por {chat_id}. Estado anterior: {context.user_data.get('state')}")
     # Llamamos a la versión corregida de send_main_menu
     await send_main_menu(update, context, "Acción cancelada.")