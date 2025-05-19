# handlers/utils.py
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
# Importar config y keyboards directamente
import config
import keyboards

logger = logging.getLogger(__name__)

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Por favor, elige una opción:") -> None:
    """Envía el menú principal, limpia estado y establece la bandera."""
    chat_id = update.effective_chat.id
    if not chat_id:
        logger.warning("send_main_menu llamado sin chat_id efectivo.")
        return

    logger.debug(f"Intentando enviar menú principal a {chat_id}. Texto: '{text}'")
    context.user_data.clear() # Limpiar datos/estado del usuario
    logger.debug(f"Estado limpiado para {chat_id}.")

    # --- AÑADIR BANDERA ---
    # Establecerla aquí asegura que si este handler (vía main.py) maneja el botón 'Volver',
    # el mensaje no se procese de nuevo en Grupo 1.
    context.user_data['handled_in_group_0'] = True
    logger.debug(f"Bandera handled_in_group_0 establecida en send_main_menu")
    # ------------------------

    message_to_reply = update.message or (update.callback_query.message if update.callback_query else None)

    try:
        if message_to_reply:
            await message_to_reply.reply_text(text, reply_markup=keyboards.main_menu_markup)
            logger.info(f"Menú principal enviado como respuesta a {chat_id}.")
        elif update.effective_chat:
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboards.main_menu_markup)
            logger.info(f"Menú principal enviado como nuevo mensaje a {chat_id}.")
        else:
            logger.error(f"No se pudo determinar cómo enviar el menú principal para el update: {update}")
    except Exception as e:
        logger.error(f"Error enviando menú principal a {chat_id}: {e}", exc_info=True)


async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
     """Manejador para el botón de cancelar acción global."""
     chat_id = update.effective_chat.id
     estado_anterior = context.user_data.get('state', 'Ninguno') # Guardar estado antes de limpiar
     logger.info(f"Acción cancelada por {chat_id}. Estado anterior: {estado_anterior}")

     # Limpiar estado y enviar menú principal usando la otra función de utils
     # send_main_menu ya limpia el estado y establece la bandera.
     await send_main_menu(update, context, "Acción cancelada.")
     # No necesitamos poner la bandera aquí explícitamente porque send_main_menu ya lo hace.
     logger.info(f"Cancelación completada para {chat_id}, menú principal enviado.")