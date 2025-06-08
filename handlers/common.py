# handlers/common.py
import logging
from telegram import Update
from telegram.error import TelegramError # Import TelegramError
from telegram.ext import ContextTypes
import config
import keyboards
# Importar utils para funciones comunes
from . import utils # Importar utils directamente
# Importar otros módulos necesarios
from . import misc # Necesario para llamar a handle_yes_no

# Asegúrate de tener esta línea para que los logs funcionen
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador para el comando /start."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User {user.id} (@{user.username or 'N/A'}) executed /start in chat {chat_id}.")
    try:
        await update.message.reply_html(f"¡Hola {user.mention_html()}! Bienvenido al asistente virtual.")
        # Limpiar estado y mostrar menú principal usando la función de utils
        await utils.send_main_menu(update, context, "Por favor, elige una opción del menú:")
    except Exception as e:
        logger.error(f"Error in start handler for user {user.id} in chat {chat_id}: {e}", exc_info=True)
        # Inform the user
        user_message = "Ocurrió un error al iniciar nuestra conversación. Por favor, intenta ejecutar /start nuevamente."
        if isinstance(e, TelegramError):
            user_message = "Hubo un problema de comunicación al intentar iniciar el bot. Por favor, verifica tu conexión e intenta /start de nuevo."

        try:
            await update.message.reply_text(user_message)
        except Exception as e_reply: # Broad exception if sending the error message itself fails
            logger.error(f"Critical: Failed to send error message to user {user.id} in chat {chat_id} during start handler: {e_reply}", exc_info=True)


async def route_text_message_by_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Router principal para mensajes de texto (Grupo 1).
    """

    # --- VERIFICACIÓN DE BANDERA (AÑADIDO AL INICIO) ---
    if context.user_data.get('handled_in_group_0', False):
        logger.debug(f"route_text_message_by_state: Mensaje ya manejado en Grupo 0 (bandera encontrada). Ignorando update ID: {update.update_id}")
        # Limpiar la bandera para el próximo mensaje
        context.user_data.pop('handled_in_group_0', None)
        return # Salir inmediatamente
    # -----------------------------------------

    # --- Resto de la lógica ---
    calendar_service = context.bot_data.get('calendar_service')
    if not calendar_service: logger.critical("GCal Service Missing"); await update.message.reply_text("Error calendario."); return
    if not update.message or not update.message.text: logger.warning("No text in update"); return

    text = update.message.text
    state = context.user_data.get('state')
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"Router Texto x Estado (G1): User {user.id} (@{user.username or 'N/A'}) in chat {chat_id}, State: {state}, Text: '{text}' (Not handled G0)")

    try:
        # --- PASO 1: DIRIGIR SEGÚN ESTADO ---
        from . import turno, receta, misc
    except ImportError as e:
        logger.critical(f"Failed to import state handlers (turno, receta, misc): {e}", exc_info=True)
        await update.message.reply_text("Ocurrió un error interno al procesar tu solicitud. Por favor, intenta más tarde.")
        return # Exit the function if imports fail

    # Outer try for the entire main logic of the function
    try:
        # --- BEGINNING OF OUTER TRY BLOCK ---
        state_handlers = {
            config.STATE_WAITING_DOCTOR: turno.handle_turno_solicitar_doctor,
            config.STATE_WAITING_DAY: turno.handle_turno_solicitar_dia,
            config.STATE_WAITING_TIMESLOT: turno.handle_turno_solicitar_hora,
            config.STATE_EDIT_AWAITING_DATE: turno.handle_turno_editar_placeholder,
            config.STATE_RECIPE_AWAITING_INFO: receta.handle_receta_info_text,
            config.STATE_RECIPE_AWAITING_CORRECTION: receta.handle_receta_correction_text,
            config.STATE_TALKING_TO_SECRETARY: misc.handle_secretary_message,
        }

        if state in state_handlers:
            logger.debug(f"Estado '{state}' activo, llamando a {state_handlers[state].__name__}")
            try:
                await state_handlers[state](update, context)
            except Exception as e_handler: # Error within a specific state handler
                logger.error(f"Error executing handler for state '{state}' for user {user.id} in chat {chat_id}: {e_handler}", exc_info=True)

                state_friendly_names = {
                    config.STATE_WAITING_DOCTOR: "selección de doctor",
                    config.STATE_WAITING_DAY: "selección de día",
                    config.STATE_WAITING_TIMESLOT: "selección de hora",
                    config.STATE_EDIT_AWAITING_DATE: "edición de turno",
                    config.STATE_RECIPE_AWAITING_INFO: "solicitud de receta",
                    config.STATE_RECIPE_AWAITING_CORRECTION: "corrección de receta",
                    config.STATE_TALKING_TO_SECRETARY: "contacto con secretaría",
                }
                state_desc = state_friendly_names.get(state, "acción actual")
                user_message = f"Hubo un problema al procesar tu solicitud relacionada con la {state_desc}. Por favor, intenta de nuevo."
                if isinstance(e_handler, TelegramError): # Check specific exception variable
                     user_message = f"Hubo un problema de comunicación procesando tu solicitud de {state_desc}. Por favor, verifica tu conexión e intenta de nuevo."

                try:
                    await update.message.reply_text(user_message)
                except Exception as e_reply_handler: # Specific variable name
                    logger.error(f"Failed to send error message to user {user.id} in chat {chat_id} (after state handler error): {e_reply_handler}", exc_info=True)
                # Considerar limpiar estado aquí si el error es irrecuperable
                # context.user_data.pop('state', None)
                # await utils.send_main_menu(update, context, "Debido a un error, hemos cancelado la acción anterior.")
            return # Important: return after handling state or its error

        # --- SI NO HABÍA ESTADO ACTIVO O ESTADO NO MAPEADO ---
        logger.debug(f"No hay estado activo o '{state}' no mapeado. Verificando Sí/No.")

        # --- PASO 2: Manejar Sí/No si no hay estado ---
        try:
            processed_yes_no = await misc.handle_yes_no(update, context)
            if processed_yes_no:
                logger.info("Mensaje procesado como Sí/No.")
                return
        except Exception as e_yes_no: # Specific variable name
            logger.error(f"Error llamando misc.handle_yes_no: {e_yes_no}", exc_info=True)
            # Fall through to PASO 3 is acceptable if Yes/No handler fails

        # --- PASO 3: Fallback final: Mensaje desconocido ---
        logger.info(f"Text '{text}' from user {user.id} in chat {chat_id} does not correspond to a state or Yes/No. Calling handle_unknown_text...")
        await handle_unknown_text(update, context)
        # --- END OF OUTER TRY BLOCK ---

    except Exception as e:  # This is the except block from original line 150
        logger.error(f"Unhandled error in route_text_message_by_state for user {user.id} in chat {chat_id}: {e}", exc_info=True)
        user_message = "Lo siento, ocurrió un error inesperado al procesar tu mensaje. Por favor, intenta de nuevo o usa /start para volver al menú principal."
        if isinstance(e, TelegramError):
            user_message = "Hubo un problema de comunicación al procesar tu mensaje. Por favor, verifica tu conexión e intenta de nuevo, o usa /start."

        try:
            await update.message.reply_text(user_message)
        except Exception as e_reply: # Specific variable name
            logger.error(f"Critical: Failed to send generic error message to user {user.id} in chat {chat_id} (route_text_message_by_state): {e_reply}", exc_info=True)


async def handle_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador fallback para texto no reconocido."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"
    logger.warning(f"-> Entering handle_unknown_text (User {user.id} (@{user.username or 'N/A'}) in Chat ID: {chat_id}, Text: '{text}')")
    try:
        await utils.send_main_menu(update, context, "No entendí tu mensaje. Usa las opciones del menú:")
        logger.info(f"<- Exiting handle_unknown_text for user {user.id} in chat {chat_id} (Main menu sent via utils.send_main_menu)")
    except TelegramError as te: # Specific Telegram errors
        logger.error(f"TelegramError in handle_unknown_text for user {user.id} in chat {chat_id} while trying to send main menu: {te}", exc_info=True)
        # utils.send_main_menu itself logs errors if it fails to send.
        # A direct reply here might be redundant or also fail.
        # If send_main_menu failed, the user might not get a response.
    except Exception as e: # Other unexpected errors
        logger.error(f"Unexpected error in handle_unknown_text for user {user.id} in chat {chat_id}: {e}", exc_info=True)
        try:
            # This is a last resort message if send_main_menu failed for a non-TelegramError reason
            # or if some other unexpected error happened before calling send_main_menu.
            await update.message.reply_text("No pude procesar tu último mensaje y tampoco pude mostrar el menú principal. Por favor, intenta /start.")
        except Exception as e_reply:
            logger.error(f"Critical: Failed to send final error message in handle_unknown_text to user {user.id} in chat {chat_id}: {e_reply}", exc_info=True)

# --- Global Error Handler ---
# This function should be registered in main.py using:
# application.add_error_handler(global_error_handler)
#
# It's useful for catching errors that occur outside of the regular handler flows
# or errors in the framework itself.
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler to log unhandled exceptions and notify user/devs."""

    logger.error(f"Unhandled exception caught by global_error_handler: {context.error}", exc_info=context.error)

    # Try to get user and chat information from the update if available
    user_info_str = "N/A"
    chat_info_str = "N/A"

    if isinstance(update, Update):
        effective_user = update.effective_user
        effective_chat = update.effective_chat
        if effective_user:
            user_info_str = f"User ID {effective_user.id} (@{effective_user.username or 'N/A'})"
        if effective_chat:
            chat_info_str = f"Chat ID {effective_chat.id} (Type: {effective_chat.type})"

    logger.critical(
        f"GLOBAL ERROR HANDLER TRIGGERED:\n"
        f"Error: {context.error}\n"
        f"Update: {update}\n"
        f"User: {user_info_str}\n"
        f"Chat: {chat_info_str}\n",
        exc_info=context.error # Ensure stack trace is logged
    )

    # Notify the user if possible (and if the update object is an Update instance)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Lo siento, ha ocurrido un error inesperado en el bot. Ya hemos sido notificados.\n"
                     "Por favor, intenta usar /start para reiniciar. Si el problema persiste, contacta al administrador."
            )
            logger.info(f"Sent generic error message to chat {update.effective_chat.id} via global_error_handler.")
        except TelegramError as te:
            logger.error(f"Failed to send generic error message via global_error_handler to chat {update.effective_chat.id}: {te}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred while trying to send generic error message via global_error_handler to chat {update.effective_chat.id}: {e}", exc_info=True)

    # (Optional) Here you could add code to notify developers, e.g., via another Telegram message to a specific chat_id
    # if config.DEVELOPER_CHAT_ID:
    #     try:
    #         await context.bot.send_message(
    #             chat_id=config.DEVELOPER_CHAT_ID,
    #             text=f"🚨 Global Error Alert 🚨\nError: {context.error}\nUser: {user_info_str}\nChat: {chat_info_str}"
    #         )
    #     except Exception:
    #         logger.error(f"Failed to send global error alert to developer chat ID {config.DEVELOPER_CHAT_ID}", exc_info=True)