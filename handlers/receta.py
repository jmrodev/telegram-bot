# handlers/receta.py
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.error import TelegramError # Import TelegramError
from telegram.ext import ContextTypes
import config
import keyboards
# Asegúrate que utils está correctamente importado
from . import utils # Importar utils directamente

# Añadido logger
logger = logging.getLogger(__name__)

async def handle_receta_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"-> Entering handle_receta_menu for user {user.id} (@{user.username or 'N/A'}) in chat {chat_id}")
    try:
        await update.message.reply_text("Selecciona una opción para Recetas:", reply_markup=keyboards.receta_menu_markup)
        context.user_data['handled_in_group_0'] = True
        logger.info(f"<- Exiting handle_receta_menu for user {user.id} in chat {chat_id} (Menu sent, flag set)")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_receta_menu for user {user.id} in chat {chat_id}: {te}", exc_info=True)
        # Sending the menu itself failed, user might not get any response. Global handler might log this.
    except Exception as e: # Other unexpected errors
        logger.error(f"Unexpected error in handle_receta_menu for user {user.id} in chat {chat_id}: {e}", exc_info=True)
        try:
            # Try to inform the user, though the primary action (sending menu) failed.
            await update.message.reply_text("Ocurrió un error inesperado al intentar mostrar el menú de recetas. Por favor, intenta /start de nuevo.")
        except Exception as e_reply:
            logger.error(f"Critical: Failed to send error message to user {user.id} (handle_receta_menu): {e_reply}", exc_info=True)


async def handle_receta_sub_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"

    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} selected recipe sub-option: '{text}'")

    try:
        context.user_data['handled_in_group_0'] = True
        logger.debug(f"Flag 'handled_in_group_0' set for user {user.id} in chat {chat_id} in handle_receta_sub_choice for text '{text}'")

        current_state = context.user_data.get('state')

        if text != config.BTN_VOLVER and current_state:
            logger.warning(f"User {user.id} in chat {chat_id} tried to select recipe option '{text}' while state '{current_state}' is active.")
            try:
                await update.message.reply_text(
                    "Ya hay una acción en curso. Por favor, cancela ('🚫 Cancelar Operación') o completa la acción actual antes de seleccionar una opción de recetas.",
                    reply_markup=keyboards.receta_menu_markup
                )
            except TelegramError as te:
                logger.error(f"TelegramError sending 'action in progress' message in handle_receta_sub_choice for user {user.id}: {te}", exc_info=True)
            return

        # Inner try-except for the main logic of handling text choices and replying
        try:
            if text == config.BTN_RECETA_SOLICITAR:
                logger.debug(f"User {user.id} in chat {chat_id}: Initiating flow to request a new recipe.")
                new_instruction_message = (
                    "Para solicitar una nueva receta:\n"
                    "1. Escribe el nombre del medicamento y la dosis. Si son varios medicamentos, puedes listarlos uno por línea o separados por comas (ej: 'Amoxicilina 500mg, Ibuprofeno 600mg').\n"
                    "2. O puedes adjuntar directamente una foto clara de la receta anterior o de la caja del medicamento.\n\n"
                    "Presiona '🚫 Cancelar Operación' si cambias de opinión."
                )
                await update.message.reply_text(new_instruction_message, reply_markup=keyboards.cancel_markup)
                context.user_data['state'] = config.STATE_RECIPE_AWAITING_INFO
                logger.info(f"State set to STATE_RECIPE_AWAITING_INFO for user {user.id} in chat {chat_id}")
            elif text == config.BTN_RECETA_CORREGIR:
                logger.debug(f"User {user.id} in chat {chat_id}: Initiating flow to correct a recipe.")
                await update.message.reply_text(
                    "Para solicitar una corrección en una receta:\n"
                    "1. Describe brevemente qué necesita corregirse (ej: cambio de dosis, fecha incorrecta).\n"
                    "2. Adjunta una foto clara de la receta que necesita corrección.\n\n"
                    "Presiona '🚫 Cancelar Operación' si cambias de opinión.",
                    reply_markup=keyboards.cancel_markup
                )
                context.user_data['state'] = config.STATE_RECIPE_AWAITING_CORRECTION
                logger.info(f"State set to STATE_RECIPE_AWAITING_CORRECTION for user {user.id} in chat {chat_id}")
            elif text == config.BTN_VOLVER:
                logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} selected '{config.BTN_VOLVER}' from recipe sub-menu. Redirecting to main menu.")
                await utils.send_main_menu(update, context) # utils.send_main_menu has its own error handling
            elif text == config.BTN_RECETA_CONSULTAR_ESTADO: # Conceptual constant
                logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} selected 'Consultar Estado de Receta'.")
                # Attempt to get contact info from config, otherwise use a default
                secretaria_contacto = getattr(config, 'SECRETARIA_CONTACTO_TELEFONO', "nuestro canal de secretaría habitual") # Example config var

                status_message = (
                    "Las solicitudes de recetas suelen procesarse en un plazo de 24-48 horas hábiles. "
                    "Nos comunicaremos contigo directamente cuando tu receta esté lista o si necesitamos más información.\n\n"
                    "Si tu solicitud es urgente o tienes dudas después de este período, por favor, contacta "
                    f"directamente a secretaría (por ejemplo, al {secretaria_contacto}) o espera nuestra notificación.\n\n"
                    "Gracias por tu paciencia."
                )
                await update.message.reply_text(status_message, reply_markup=keyboards.receta_menu_markup)
                # No change in state, just providing information.
            else:
                logger.warning(f"Unrecognized recipe sub-option '{text}' from user {user.id} (@{user.username or 'N/A'}) in chat {chat_id}.")
                await update.message.reply_text(
                    "Opción no reconocida dentro del menú de recetas. Por favor, selecciona una de las opciones disponibles.",
                    reply_markup=keyboards.receta_menu_markup
                )
        except TelegramError as te_reply:
            logger.error(f"TelegramError during reply in handle_receta_sub_choice for user {user.id}, text '{text}': {te_reply}", exc_info=True)
            # User might not have received the intended message. Global handler might take over.
        except Exception as e_reply: # Other errors during reply logic
            logger.error(f"Unexpected error in reply logic of handle_receta_sub_choice for user {user.id}, text '{text}': {e_reply}", exc_info=True)
            try:
                await update.message.reply_text("Ocurrió un error al procesar tu selección. Por favor, intenta de nuevo.")
            except Exception: # If this also fails, nothing more to do here for user.
                 pass # Logging already done, global handler might catch the initial error.

    except TelegramError as te_outer:
        logger.error(f"Outer TelegramError in handle_receta_sub_choice for user {user.id} in chat {chat_id} with text '{text}': {te_outer}", exc_info=True)
        try:
            await update.message.reply_text("Hubo un problema de comunicación al procesar tu opción de receta. Por favor, verifica tu conexión e intenta de nuevo.")
        except Exception as e_reply_tg:
            logger.error(f"Failed to send TelegramError reply to user {user.id} (handle_receta_sub_choice): {e_reply_tg}", exc_info=True)
    except Exception as e: # Catch-all for other unexpected errors (e.g., state check issues before inner try)
        logger.error(f"Unexpected error in handle_receta_sub_choice for user {user.id} in chat {chat_id} with text '{text}': {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al procesar tu selección de receta. Por favor, intenta de nuevo más tarde.")
        except Exception as e_reply: # Broad exception if sending the error message itself fails
            logger.error(f"Critical: Failed to send generic error reply to user {user.id} (handle_receta_sub_choice): {e_reply}", exc_info=True)


async def handle_receta_info_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"

    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} (State {config.STATE_RECIPE_AWAITING_INFO}): Received text for new recipe: '{text}'")

    try:
        log_msg = f"Solicitud Receta (Texto):\nUser ID: {user.id} (@{user.username or user.first_name})\nChat ID: {chat_id}\nInfo: {text}"
        logger.debug(f"Preparing notification for secretary: {log_msg}")

        if config.SECRETARY_CHAT_ID:
            secretary_notified = False
            user_informed_of_secretary_issue = False
            try:
                await context.bot.send_message(chat_id=config.SECRETARY_CHAT_ID, text=log_msg)
                logger.info(f"New recipe request text from user {user.id} in chat {chat_id} sent to secretary chat ID {config.SECRETARY_CHAT_ID}.")
                secretary_notified = True
            except TelegramError as te_secretary:
                logger.error(f"TelegramError notifying secretary (ID {config.SECRETARY_CHAT_ID}) about new recipe from user {user.id}: {te_secretary}", exc_info=True)
            except Exception as e_secretary: # Other errors sending to secretary
                logger.error(f"Unexpected error notifying secretary (ID {config.SECRETARY_CHAT_ID}) about new recipe from user {user.id}: {e_secretary}", exc_info=True)

            user_message_key = "success" # Default message key
            if not secretary_notified:
                user_message_key = "secretary_fail"

            messages_to_user = {
                "success": "Tu solicitud de receta ha sido enviada. Te avisaremos cuando esté lista.\nVolviendo al menú principal...",
                "secretary_fail": "Tu solicitud fue recibida, pero hubo un problema al notificar a la secretaría en este momento. Por favor, contacta directamente si es urgente.\nVolviendo al menú principal...",
                "secretary_unconfigured": "Tu solicitud de receta fue recibida (pero la secretaría no pudo ser notificada automáticamente en este momento).\nVolviendo al menú principal..."
            }

            if not config.SECRETARY_CHAT_ID:
                logger.warning(f"SECRETARY_CHAT_ID not configured. Cannot send new recipe text from user {user.id} in chat {chat_id} to secretary.")
                user_message_key = "secretary_unconfigured"

            current_user_message = messages_to_user[user_message_key]

            try:
                await update.message.reply_text(current_user_message, reply_markup=keyboards.main_menu_markup)
            except TelegramError as te_user:
                 logger.error(f"TelegramError sending recipe info confirmation to user {user.id}: {te_user}", exc_info=True)
                 # User might not know the status.
            except Exception as e_user:
                 logger.error(f"Unexpected error sending recipe info confirmation to user {user.id}: {e_user}", exc_info=True)

        context.user_data.clear() # Clear state regardless of notification success, as the request is "processed"
        logger.info(f"User data cleared for user {user.id} in chat {chat_id} after processing new recipe text.")
        await utils.send_main_menu(update, context) # This has its own error handling

    except TelegramError as te_outer:
        logger.error(f"Outer TelegramError in handle_receta_info_text for user {user.id} in chat {chat_id} with text '{text}': {te_outer}", exc_info=True)
        # This would likely be an error in the initial reply_text if it were moved outside, or other Telegram specific issue.
        try:
            await update.message.reply_text("Hubo un problema de comunicación al procesar tu solicitud de receta. Por favor, verifica tu conexión e intenta de nuevo.")
        except Exception as e_reply_tg:
            logger.error(f"Failed to send TelegramError reply to user {user.id} (handle_receta_info_text): {e_reply_tg}", exc_info=True)
    except Exception as e: # Catch-all for other unexpected errors
        logger.error(f"Unexpected error in handle_receta_info_text for user {user.id} in chat {chat_id} with text '{text}': {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al procesar tu solicitud de receta. Por favor, intenta de nuevo más tarde.")
        except Exception as e_reply: # Broad exception if sending the error message itself fails
            logger.error(f"Critical: Failed to send generic error reply to user {user.id} (handle_receta_info_text): {e_reply}", exc_info=True)


async def handle_receta_correction_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"

    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} (State {config.STATE_RECIPE_AWAITING_CORRECTION}): Received text for recipe correction: '{text}'")

    try:
        context.user_data['correction_text'] = text
        logger.debug(f"Correction text saved for user {user.id} in chat {chat_id}. Awaiting photo.")
        await update.message.reply_text(
            f"Descripción de la corrección: '{text}'.\nAhora, por favor, adjunta una foto de la receta que necesita ser corregida, o presiona '🚫 Cancelar Operación'.",
            reply_markup=keyboards.cancel_markup
        )
        # Mantenemos estado STATE_RECIPE_AWAITING_CORRECTION
        logger.info(f"Awaiting photo for recipe correction from user {user.id} in chat {chat_id}.")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_receta_correction_text for user {user.id} in chat {chat_id} with text '{text}': {te}", exc_info=True)
        # User message might not have been sent.
        # No specific user reply here as the main action (prompting for photo) might have failed.
        # Global error handler or subsequent actions would need to manage this.
    except Exception as e: # Other unexpected errors
        logger.error(f"Unexpected error in handle_receta_correction_text for user {user.id} in chat {chat_id} with text '{text}': {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al procesar tu descripción para la corrección de receta. Por favor, intenta de nuevo más tarde.")
        except Exception as e_reply: # Broad exception if sending the error message itself fails
            logger.error(f"Critical: Failed to send generic error reply to user {user.id} (handle_receta_correction_text): {e_reply}", exc_info=True)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id # Will be same as user.id in DMs

    if not update.message or not update.message.photo:
        logger.warning(f"handle_photo called for user {user.id if user else 'UnknownUser'} in chat {chat_id if chat_id else 'UnknownChat'} without message or photo object.")
        return

    current_state = context.user_data.get('state')
    photo_file_id = update.message.photo[-1].file_id
    caption = update.message.caption or ""

    logger.info(f"Photo received from user {user.id} (@{user.username or 'N/A'}) in chat {chat_id}. State: {current_state}, FileID: {photo_file_id}, Caption: '{caption}'")

    try:
        log_msg_base = f"User ID: {user.id} (@{user.username or user.first_name})\nChat ID: {chat_id}\nFileID: {photo_file_id}"
        notification_text = None
        reply_user_text = "Foto recibida, pero no sé qué hacer con ella en este momento. Usa /start para volver al menú principal."
        clear_state_and_menu = True # Default to clearing state and showing main menu

        if current_state == config.STATE_RECIPE_AWAITING_INFO:
            logger.info(f"Photo from user {user.id} in chat {chat_id} is for a NEW recipe request.")
            recipe_info = caption if caption else "(Solo Foto, sin descripción adicional)"
            notification_text = f"Solicitud Receta (FOTO):\n{log_msg_base}\nInfo Adicional: {recipe_info}"
            reply_user_text = "He recibido la foto para tu nueva receta. La secretaría la procesará y te avisaremos cuando esté lista.\nVolviendo al menú principal..."
            logger.debug(f"New recipe photo processed for user {user.id} in chat {chat_id}.")

        elif current_state == config.STATE_RECIPE_AWAITING_CORRECTION:
            logger.info(f"Photo from user {user.id} in chat {chat_id} is for a recipe CORRECTION.")
            correction_desc = context.user_data.pop('correction_text', caption if caption else "(Sin descripción previa, usando caption o vacío)")
            notification_text = f"Corrección Receta (FOTO):\n{log_msg_base}\nDescripción: {correction_desc}"
            reply_user_text = "He recibido la foto y la descripción para la corrección de tu receta. La secretaría la revisará y te informaremos.\nVolviendo al menú principal..."
            logger.debug(f"Recipe correction photo processed for user {user.id} in chat {chat_id}. Description used: '{correction_desc}'")

        else:
            logger.warning(f"Photo received from user {user.id} in chat {chat_id} in an unexpected state: '{current_state}'. Caption: '{caption}'")
            notification_text = f"Foto Inesperada (Chequear):\n{log_msg_base}\nEstado Actual del Usuario: {current_state}\nCaption de la Foto: {caption or '(Ninguno)'}"
            reply_user_text = "He recibido tu foto, pero no la esperaba en este momento. Si necesitas algo, por favor usa los comandos del menú o /start."
            # For unexpected photos, we might not want to aggressively clear state if the user was in the middle of something else valid.
            # However, current bot structure implies photos are mostly for recipes.
            # If other photo states are added, this logic might need refinement.
            # For now, clearing state is consistent with other final actions.

        if notification_text and config.SECRETARY_CHAT_ID:
            logger.debug(f"Attempting to send notification to secretary for photo from user {user.id}: {notification_text}")
            try:
                await context.bot.send_message(chat_id=config.SECRETARY_CHAT_ID, text=notification_text)
                logger.info(f"Notification for photo from user {user.id} in chat {chat_id} sent to secretary chat ID {config.SECRETARY_CHAT_ID}.")
            except TelegramError as te_secretary:
                logger.error(f"TelegramError notifying secretary (ID {config.SECRETARY_CHAT_ID}) about photo from user {user.id}: {te_secretary}", exc_info=True)
                reply_user_text += "\n(Importante: Hubo un problema de comunicación al notificar a la secretaría.)"
            except Exception as e_secretary: # Other errors
                logger.error(f"Unexpected error notifying secretary (ID {config.SECRETARY_CHAT_ID}) about photo from user {user.id}: {e_secretary}", exc_info=True)
                reply_user_text += "\n(Importante: Hubo un error inesperado al notificar a la secretaría.)"
        elif notification_text: # Notification was prepared but no SECRETARY_CHAT_ID
            logger.warning(f"SECRETARY_CHAT_ID not configured. Cannot send notification for photo from user {user.id} in chat {chat_id}.")
            reply_user_text += "\n(Nota: La secretaría no pudo ser notificada automáticamente en este momento.)"

        try:
            await update.message.reply_text(reply_user_text, reply_markup=keyboards.main_menu_markup)
        except TelegramError as te_user_reply:
            logger.error(f"TelegramError sending final reply in handle_photo to user {user.id}: {te_user_reply}", exc_info=True)
            # If this fails, user might not know the outcome.
        except Exception as e_user_reply:
            logger.error(f"Unexpected error sending final reply in handle_photo to user {user.id}: {e_user_reply}", exc_info=True)

        if clear_state_and_menu:
            logger.debug(f"Clearing user_data for user {user.id} in chat {chat_id} after photo handling.")
            context.user_data.clear()
            # No need to call utils.send_main_menu if main_menu_markup is already used and state is cleared.

    except TelegramError as te_outer:
        logger.error(f"Outer TelegramError in handle_photo for user {user.id} in chat {chat_id} (FileID: {photo_file_id}): {te_outer}", exc_info=True)
        try:
            await update.message.reply_text("Hubo un problema de comunicación al procesar la foto. Por favor, verifica tu conexión e intenta de nuevo.")
        except Exception as e_reply_tg:
            logger.error(f"Failed to send TelegramError reply to user {user.id} (handle_photo): {e_reply_tg}", exc_info=True)
    except Exception as e: # Catch-all for other unexpected errors
        logger.error(f"Unexpected error in handle_photo for user {user.id} in chat {chat_id} (FileID: {photo_file_id}): {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al procesar la foto que enviaste. Por favor, intenta de nuevo o contacta a la secretaría si el problema persiste.")
        except Exception as e_reply: # Broad exception if sending the error message itself fails
            logger.error(f"Critical: Failed to send generic error reply to user {user.id} (handle_photo): {e_reply}", exc_info=True)