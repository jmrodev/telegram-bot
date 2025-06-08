# handlers/utils.py
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.error import TelegramError # Import TelegramError
from telegram.ext import ContextTypes
# Importar config y keyboards directamente
import config
import keyboards

logger = logging.getLogger(__name__)

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Por favor, elige una opción:") -> None:
    """Envía el menú principal, limpia estado y establece la bandera."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    # It's possible chat_id is None if the update isn't from a chat (e.g. inline query, but less likely for this bot)
    # User might also be None in some rare edge cases or if the update type doesn't involve a user directly.
    user_id_log = user.id if user else "UnknownUser"
    username_log = user.username if user and user.username else "N/A"
    chat_id_log = chat_id if chat_id else "UnknownChat"

    logger.debug(f"Attempting to send main menu to user {user_id_log} (@{username_log}) in chat {chat_id_log}. Text: '{text}'")

    try:
        if not chat_id: # Should be rare given most updates have a chat
            logger.warning(f"send_main_menu called without effective_chat.id for user {user_id_log}. Update type: {update.effective_message.chat.type if update.effective_message else 'N/A'}")
            # Cannot send message without chat_id, so attempting to clear user_data might be the only action.
            if context.user_data: # Check if there's any data to clear
                context.user_data.clear()
                logger.info(f"User_data cleared for user {user_id_log} (chat_id unknown) as part of send_main_menu due to missing chat_id.")
            return

        context.user_data.clear()
        logger.info(f"User_data cleared for user {user_id_log} in chat {chat_id_log}.")

        context.user_data['handled_in_group_0'] = True
        logger.debug(f"Flag 'handled_in_group_0' set for user {user_id_log} in chat {chat_id_log} by send_main_menu.")

        message_to_reply_to = update.message or (update.callback_query.message if update.callback_query else None)

        try:
            if message_to_reply_to:
                await message_to_reply_to.reply_text(text, reply_markup=keyboards.main_menu_markup)
                logger.info(f"Main menu sent as a reply to user {user_id_log} in chat {chat_id_log}.")
            elif update.effective_chat: # Fallback if no direct message to reply to, but there's an effective chat
                await context.bot.send_message(chat_id=chat_id_log, text=text, reply_markup=keyboards.main_menu_markup)
                logger.info(f"Main menu sent as a new message to user {user_id_log} in chat {chat_id_log}.")
            else:
                # This case should be extremely rare if chat_id was present.
                logger.error(f"Cannot determine how to send main menu for user {user_id_log} in chat {chat_id_log}. Update details: {update}", exc_info=True) # No direct user message, relies on global handler
        except TelegramError as te_send:
            logger.error(f"TelegramError sending main menu to user {user_id_log} in chat {chat_id_log}: {te_send}", exc_info=True)
            # No user-facing message here as sending itself failed. Global handler may act.
        except Exception as e_send: # Other unexpected errors during send
            logger.error(f"Unexpected error sending main menu to user {user_id_log} in chat {chat_id_log}: {e_send}", exc_info=True)
            # No user-facing message here.

    except TelegramError as te_outer: # Should be less likely if inner try-except catches te_send
        logger.error(f"Outer TelegramError in send_main_menu for user {user_id_log} in chat {chat_id_log}: {te_outer}", exc_info=True)
    except Exception as e_outer: # General fallback for other logic errors
        logger.error(f"Outer unexpected error in send_main_menu for user {user_id_log} in chat {chat_id_log}: {e_outer}", exc_info=True)
        # Attempt to inform user if possible, though it's a util function, direct error might be unexpected.
        # This path is less likely to be hit due to the inner try-except for sending.


async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador para el botón de cancelar acción global."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    user_id_log = user.id if user else "UnknownUser"
    username_log = user.username if user and user.username else "N/A"
    chat_id_log = chat_id if chat_id else "UnknownChat" # Should usually be present

    estado_anterior = context.user_data.get('state', 'Ninguno')
    logger.info(f"User {user_id_log} (@{username_log}) in chat {chat_id_log} initiated cancel_action. Previous state: '{estado_anterior}'")

    try:
        # send_main_menu handles clearing user_data, setting the handled_in_group_0 flag, and sending the menu.
        await send_main_menu(update, context, "Tu acción anterior ha sido cancelada. Ya puedes seleccionar una nueva opción del menú.")
        # send_main_menu has its own comprehensive logging.
        logger.info(f"cancel_action completed for user {user_id_log} in chat {chat_id_log}. Main menu sent by send_main_menu.")

    except Exception as e:
        # This would catch errors if send_main_menu itself fails catastrophically before its own try-except,
        # or if there was an issue getting user/chat details initially (though less likely).
        logger.error(f"Error during cancel_action for user {user_id_log} in chat {chat_id_log} (State before cancel: '{estado_anterior}'): {e}", exc_info=True)
        # Attempt a basic reply if send_main_menu failed.
        try:
            if chat_id_log != "UnknownChat": # Only attempt if we have a chat_id
                await context.bot.send_message(
                    chat_id=chat_id_log,
                    text="Hubo un error al cancelar la acción. Por favor, intenta usar /start para volver al menú principal.",
                    reply_markup=ReplyKeyboardRemove() # Attempt to remove any custom keyboard
                )
                context.user_data.clear() # Still try to clear data
        except TelegramError as te_reply:
            logger.error(f"TelegramError sending emergency error message in cancel_action to user {user_id_log}: {te_reply}", exc_info=True)
        except Exception as e_reply: # Other errors during emergency reply
            logger.error(f"Unexpected error sending emergency error message/clear data in cancel_action for user {user_id_log}: {e_reply}", exc_info=True)