# handlers/pago.py
import logging
from telegram import Update
from telegram.error import TelegramError # Import TelegramError
from telegram.ext import ContextTypes
import config
import keyboards
# Asegúrate que utils está correctamente importado
from . import utils # Importar utils directamente

# Añadido logger
logger = logging.getLogger(__name__)

async def handle_pago_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"-> Entering handle_pago_menu for user {user.id} (@{user.username or 'N/A'}) in chat {chat_id}")
    try:
        await update.message.reply_text("Selecciona una opción para Pagos:", reply_markup=keyboards.pago_menu_markup)
        context.user_data['handled_in_group_0'] = True
        logger.info(f"<- Exiting handle_pago_menu for user {user.id} in chat {chat_id} (Menu sent, flag set)")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_pago_menu for user {user.id} in chat {chat_id}: {te}", exc_info=True)
        # No user message here as sending the menu itself failed. The global handler might catch this.
    except Exception as e: # Other unexpected errors
        logger.error(f"Unexpected error in handle_pago_menu for user {user.id} in chat {chat_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al intentar mostrar el menú de pagos. Por favor, intenta /start de nuevo.")
        except Exception as e_reply: # Broad exception if sending the error message itself fails
            logger.error(f"Critical: Failed to send error message to user {user.id} (handle_pago_menu): {e_reply}", exc_info=True)


async def handle_pago_sub_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"

    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} selected payment sub-option: '{text}'")

    try:
        context.user_data['handled_in_group_0'] = True
        logger.debug(f"Flag 'handled_in_group_0' set for user {user.id} in chat {chat_id} in handle_pago_sub_choice for text '{text}'")

        current_state = context.user_data.get('state')

        if text != config.BTN_VOLVER and current_state:
            logger.warning(f"User {user.id} in chat {chat_id} tried to select payment option '{text}' while state '{current_state}' is active.")
            try:
                await update.message.reply_text(
                    "Parece que hay otra acción en curso. Por favor, cancela ('🚫 Cancelar Operación') o completa la acción actual antes de seleccionar una opción de pago.",
                    reply_markup=keyboards.pago_menu_markup
                )
            except TelegramError as te:
                 logger.error(f"TelegramError sending 'action in progress' message to user {user.id}: {te}", exc_info=True)
            return

        # Inner try-except for the message sending part based on text choice
        try:
            if text == config.BTN_PAGO_TRANFERENCIA:
                transfer_details = (
                    "Datos para Transferencia Bancaria:\n"
                    "-------------------------------------\n"
                    f"Banco: {getattr(config, 'BANK_NAME', '[Nombre Banco]')}\n"
                    f"Titular: {getattr(config, 'BANK_ACCOUNT_HOLDER', '[Nombre Titular]')}\n"
                    f"Tipo Cuenta: {getattr(config, 'BANK_ACCOUNT_TYPE', '[Tipo Cuenta]')}\n"
                    f"Nro Cuenta: {getattr(config, 'BANK_ACCOUNT_NUMBER', '[Numero Cuenta]')}\n"
                    f"CBU: {getattr(config, 'BANK_CBU', '[CBU]')}\n"
                    f"Alias: {getattr(config, 'BANK_ALIAS', '[Alias]')}\n"
                    f"CUIT/CUIL: {getattr(config, 'BANK_CUIT_CUIL', '[CUIT/CUIL]')}\n"
                    "-------------------------------------\n"
                    "Importante: Envía el comprobante de pago una vez realizada la transferencia."
                )
                await update.message.reply_text(transfer_details, reply_markup=keyboards.pago_menu_markup)
                logger.debug(f"Displayed transfer details to user {user.id} in chat {chat_id}")
            elif text == config.BTN_PAGO_CONSULTORIO:
                office_payment_info = (
                    "Puedes abonar tu consulta directamente en el consultorio.\n"
                    "Medios de pago aceptados:\n"
                    "- Efectivo\n"
                    "- Tarjetas Débito/Crédito\n"
                    "- Mercado Pago (QR)\n\n"
                    f"Dirección: {getattr(config, 'OFFICE_ADDRESS', '[Dirección Consultorio]')}\n"
                    f"Horario Secretaría: {getattr(config, 'OFFICE_HOURS', '[Horario Secretaría]')}"
                )
                await update.message.reply_text(office_payment_info, reply_markup=keyboards.pago_menu_markup)
                logger.debug(f"Displayed in-office payment info to user {user.id} in chat {chat_id}")
            elif text == config.BTN_PAGO_ONLINE_INFO: # Conceptual constant
                logger.debug(f"User {user.id} in chat {chat_id} selected 'Pagar Online (Info)'.")
                default_online_payment_message = ("La información para pagos online no está configurada en este momento. "
                                                  "Por favor, contacta a secretaría para asistencia.")
                online_payment_info = getattr(config, 'ONLINE_PAYMENT_INFO_TEXT', default_online_payment_message)

                # Basic check if the info text is still the placeholder or very generic
                if "[Link al Portal de Pagos]" in online_payment_info or \
                   "[Número de Secretaría]" in online_payment_info and "contacta a secretaría" in online_payment_info.lower() and \
                   len(online_payment_info) < 200 and online_payment_info == default_online_payment_message : # Heuristic for placeholder
                    logger.info(f"ONLINE_PAYMENT_INFO_TEXT for user {user.id} seems to be a placeholder or not fully configured.")
                    # Could use a more specific message if it's a placeholder vs not defined
                    user_message = ("La información detallada para pagos online está siendo actualizada. "
                                    "Por favor, contacta a secretaría para que te asistan con el proceso.")
                else:
                    user_message = online_payment_info

                await update.message.reply_text(user_message, reply_markup=keyboards.pago_menu_markup)
                logger.debug(f"Displayed online payment info to user {user.id} in chat {chat_id}")

            elif text == config.BTN_PAGO_RECORDATORIO_INFO: # Conceptual constant
                logger.debug(f"User {user.id} in chat {chat_id} selected 'Recordatorio de Pago (Info)'.")
                default_reminder_message = ("La información sobre recordatorios de pago no está configurada. "
                                            "Generalmente, los pagos se esperan antes o el día del turno.")
                reminder_info = getattr(config, 'PAYMENT_REMINDER_INFO_TEXT', default_reminder_message)

                # Basic check if the info text is still a placeholder or very generic
                if "[Número de Secretaría]" in reminder_info and len(reminder_info) < 250 and reminder_info == default_reminder_message: # Heuristic for placeholder
                    logger.info(f"PAYMENT_REMINDER_INFO_TEXT for user {user.id} seems to be a placeholder or not fully configured.")
                    user_message = ("La información detallada sobre recordatorios de pago está siendo actualizada. "
                                    "Generalmente, se espera el pago antes o el mismo día del turno. "
                                    "Para dudas, contacta a secretaría.")
                else:
                    user_message = reminder_info

                await update.message.reply_text(user_message, reply_markup=keyboards.pago_menu_markup)
                logger.debug(f"Displayed payment reminder info to user {user.id} in chat {chat_id}")

            elif text == config.BTN_VOLVER:
                logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} selected '{config.BTN_VOLVER}' from payment sub-menu. Redirecting to main menu.")
                await utils.send_main_menu(update, context) # This function has its own error handling
            else:
                logger.warning(f"Unrecognized payment sub-option '{text}' from user {user.id} (@{user.username or 'N/A'}) in chat {chat_id}.")
                await update.message.reply_text("Opción no reconocida dentro del menú de pagos. Por favor, selecciona una de las opciones disponibles.", reply_markup=keyboards.pago_menu_markup)

        except TelegramError as te_reply: # Errors during reply_text or send_main_menu
            logger.error(f"TelegramError replying in handle_pago_sub_choice for user {user.id}, text '{text}': {te_reply}", exc_info=True)
            # User might not have received the intended message. Global handler might pick this up or a follow-up message might be confusing.
        except Exception as e_reply: # Other errors during the reply logic
            logger.error(f"Unexpected error in reply logic of handle_pago_sub_choice for user {user.id}, text '{text}': {e_reply}", exc_info=True)
            # Attempt a generic error message if a specific reply failed.
            try:
                await update.message.reply_text("Ocurrió un error al procesar tu selección. Por favor, intenta de nuevo.")
            except Exception: # If this also fails, nothing more to do here for user.
                pass


    except TelegramError as te_outer:
         logger.error(f"Outer TelegramError in handle_pago_sub_choice for user {user.id} in chat {chat_id} with text '{text}': {te_outer}", exc_info=True)
         try:
            await update.message.reply_text("Hubo un problema de comunicación al procesar tu opción de pago. Por favor, verifica tu conexión e intenta de nuevo.")
         except Exception as e_reply_tg:
            logger.error(f"Failed to send TelegramError reply to user {user.id} (handle_pago_sub_choice): {e_reply_tg}", exc_info=True)
    except Exception as e: # Catch-all for other unexpected errors in the main try block
        logger.error(f"Unexpected error in handle_pago_sub_choice for user {user.id} in chat {chat_id} with text '{text}': {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al procesar tu opción de pago. Por favor, intenta de nuevo más tarde.")
        except Exception as e_reply: # Broad exception if sending the error message itself fails
            logger.error(f"Critical: Failed to send generic error reply to user {user.id} (handle_pago_sub_choice): {e_reply}", exc_info=True)