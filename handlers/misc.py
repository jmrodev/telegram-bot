# handlers/misc.py
import logging
from telegram import Update
from telegram.error import TelegramError # Import TelegramError
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
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"

    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} sending message to secretary: '{text}'")

    try:
        log_msg = f"Message to Secretary from User ID {user.id} (@{user.username or user.first_name}) in Chat ID {chat_id}: {text}"
        # logger.info(f"Simulating send: {log_msg}") # This log seems redundant if the next one succeeds or if there's an error.

        if config.SECRETARY_CHAT_ID:
            secretary_notification_sent = False
            try:
                await context.bot.send_message(chat_id=config.SECRETARY_CHAT_ID, text=log_msg)
                logger.info(f"Message sent to secretary chat ID {config.SECRETARY_CHAT_ID} from user {user.id}.")
                secretary_notification_sent = True
            except TelegramError as te:
                logger.error(f"TelegramError notifying secretary (chat ID {config.SECRETARY_CHAT_ID}) for user {user.id}: {te}", exc_info=True)
                # User will be notified by the reply_text in the outer block or specific message below
            except Exception as e: # Other errors sending to secretary
                logger.error(f"Unexpected error notifying secretary (chat ID {config.SECRETARY_CHAT_ID}) for user {user.id}: {e}", exc_info=True)

            # Notify user about the outcome
            user_reply = ""
            if secretary_notification_sent:
                user_reply = "Tu mensaje ha sido enviado a la secretaría. Puedes continuar usando el bot o iniciar una nueva acción con /start."
            else: # Secretary notification failed
                user_reply = "Hemos recibido tu mensaje, pero hubo un problema al intentar notificar a la secretaría en este momento. Por favor, considera contactarlos directamente si es urgente."

            try:
                await update.message.reply_text(user_reply)
            except TelegramError as te_user:
                logger.error(f"TelegramError replying to user {user.id} in handle_secretary_message after secretary notification attempt: {te_user}", exc_info=True)
            except Exception as e_user:
                logger.error(f"Unexpected error replying to user {user.id} in handle_secretary_message: {e_user}", exc_info=True)

        else: # SECRETARY_CHAT_ID not configured
            logger.warning(f"SECRETARY_CHAT_ID not configured. Cannot send message from user {user.id} in chat {chat_id} to secretary.")
            try:
                await update.message.reply_text("No fue posible enviar tu mensaje directamente a la secretaría en este momento (servicio no configurado). Sin embargo, tu mensaje ha sido registrado. Considera usar /start para otras opciones.")
            except Exception as e_user_reply: # Catch error during this reply too
                 logger.error(f"Error replying to user {user.id} about unconfigured secretary: {e_user_reply}", exc_info=True)
        # Mantenemos estado
    except TelegramError as te_outer:
        logger.error(f"TelegramError in handle_secretary_message for user {user.id} in chat {chat_id}: {te_outer}", exc_info=True)
        # Attempt to notify user, though this might also fail
        try:
            await update.message.reply_text("Hubo un problema de comunicación al procesar tu solicitud para contactar a la secretaría. Por favor, intenta de nuevo.")
        except Exception as e_reply_tg:
            logger.error(f"Failed to send TelegramError reply to user {user.id} (handle_secretary_message): {e_reply_tg}", exc_info=True)
    except Exception as e: # Catch-all for other unexpected errors in the main try block
        logger.error(f"Unexpected error in handle_secretary_message for user {user.id} in chat {chat_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al procesar tu solicitud para contactar a la secretaría. Por favor, intenta de nuevo más tarde.")
        except Exception as e_reply: # Broad exception if sending the error message itself fails
            logger.error(f"Critical: Failed to send generic error reply to user {user.id} (handle_secretary_message): {e_reply}", exc_info=True)

async def handle_yes_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"
    lower_case_text = text.lower()
    processed = False
    notification_text = None

    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} sent text for Yes/No check: '{text}'")

    try:
        if lower_case_text in ['sí', 'si']:
            logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} confirmed 'Yes'.")
            context.user_data['last_confirmation'] = {"r": "Sí", "t": update.message.date}
            await update.message.reply_text("Confirmado. ¡Gracias!")
            notification_text = f"Confirmación SÍ: User ID {user.id} (@{user.username or user.first_name}) en Chat ID {chat_id}"
            processed = True
        elif lower_case_text == 'no':
            logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} confirmed 'No'.")
            context.user_data['last_confirmation'] = {"r": "No", "t": update.message.date}
            await update.message.reply_text("Entendido. Gracias.")
            notification_text = f"Confirmación NO: User ID {user.id} (@{user.username or user.first_name}) en Chat ID {chat_id}"
            processed = True

        if processed:
            logger.debug(f"Yes/No processed for user {user.id} in chat {chat_id}. Result: {'Yes' if lower_case_text in ['sí', 'si'] else 'No'}")
            if config.SECRETARY_CHAT_ID and notification_text:
                try:
                    await context.bot.send_message(chat_id=config.SECRETARY_CHAT_ID, text=notification_text)
                    logger.info(f"Yes/No confirmation from user {user.id} sent to secretary chat ID {config.SECRETARY_CHAT_ID}.")
                except TelegramError as te:
                    logger.error(f"TelegramError notifying secretary about Yes/No from user {user.id} (Secretary chat ID {config.SECRETARY_CHAT_ID}): {te}", exc_info=True)
                    # User has already received confirmation, this error is about secretary notification.
                except Exception as e: # Other errors
                    logger.error(f"Unexpected error notifying secretary about Yes/No from user {user.id} (Secretary chat ID {config.SECRETARY_CHAT_ID}): {e}", exc_info=True)
            elif processed and not config.SECRETARY_CHAT_ID: # Added 'processed' to ensure this warning is relevant
                logger.warning(f"Yes/No confirmation received from user {user.id}, but SECRETARY_CHAT_ID is not configured. No notification sent to secretary.")
        else:
            logger.debug(f"Text '{text}' from user {user.id} in chat {chat_id} was not a Yes/No confirmation.")

        return processed

    except TelegramError as te_outer:
        logger.error(f"TelegramError in handle_yes_no for user {user.id} in chat {chat_id} with text '{text}': {te_outer}", exc_info=True)
        if lower_case_text in ['sí', 'si', 'no']: # Only reply if it was a clear Yes/No attempt
            try:
                await update.message.reply_text("Hubo un problema de comunicación al procesar tu confirmación (Sí/No). Por favor, intenta de nuevo.")
            except Exception as e_reply_tg:
                logger.error(f"Failed to send TelegramError reply in handle_yes_no to user {user.id}: {e_reply_tg}", exc_info=True)
        return False
    except Exception as e: # Catch-all for other unexpected errors
        logger.error(f"Unexpected error in handle_yes_no for user {user.id} in chat {chat_id} with text '{text}': {e}", exc_info=True)
        if lower_case_text in ['sí', 'si', 'no']: # Only reply if it was a clear Yes/No attempt
            try:
                 await update.message.reply_text("Ocurrió un error inesperado al procesar tu confirmación (Sí/No). Por favor, intenta de nuevo.")
            except Exception as e_reply: # Broad exception if sending the error message itself fails
                logger.error(f"Critical: Failed to send generic error reply in handle_yes_no to user {user.id}: {e_reply}", exc_info=True)
        return False # Return False in case of an error to indicate not processed