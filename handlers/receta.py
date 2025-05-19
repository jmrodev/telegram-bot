# handlers/receta.py
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
import config
import keyboards
# Asegúrate que utils está correctamente importado
from . import utils # Importar utils directamente

# Añadido logger
logger = logging.getLogger(__name__)

async def handle_receta_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Log al inicio de la función
    logger.info(f"-> Entrando en handle_receta_menu (Chat ID: {update.effective_chat.id})")
    try: # Envolver en try/except
        await update.message.reply_text("Selecciona una opción para Recetas:", reply_markup=keyboards.receta_menu_markup)
        # --- AÑADIR BANDERA ---
        context.user_data['handled_in_group_0'] = True
        # ------------------------
        logger.info(f"<- Saliendo de handle_receta_menu (Respuesta enviada, bandera establecida)")
    except Exception as e:
         logger.error(f"!! ERROR dentro de handle_receta_menu: {e}", exc_info=True)
         try:
             await update.message.reply_text("Ocurrió un error al mostrar el menú de recetas.")
         except Exception as e_reply:
             logger.error(f"!! ERROR enviando mensaje de error en handle_receta_menu: {e_reply}")


async def handle_receta_sub_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Maneja botones DENTRO del menú de recetas
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Receta -> Sub-Opción '{text}'")
    # --- AÑADIR BANDERA TAMBIÉN AQUÍ ---
    context.user_data['handled_in_group_0'] = True
    logger.debug(f"Bandera handled_in_group_0 establecida en handle_receta_sub_choice para '{text}'")
    # ------------------------------------
    current_state = context.user_data.get('state')

    # Prevenir doble acción si ya hay un estado activo (excepto Volver)
    if text != config.BTN_VOLVER and current_state:
        await update.message.reply_text("Ya hay una acción en curso. Cancela ('🚫 ...') o completa la acción actual primero.", reply_markup=keyboards.receta_menu_markup)
        return

    if text == config.BTN_RECETA_SOLICITAR:
        logger.debug(f"{chat_id}: Iniciando flujo para solicitar receta.")
        await update.message.reply_text("Para solicitar una nueva receta:\n1. Escribe el nombre del medicamento y la dosis.\n2. O puedes adjuntar directamente una foto clara de la receta anterior o caja del medicamento.\n\nPresiona '🚫 Cancelar Acción Actual' si cambias de opinión.", reply_markup=keyboards.cancel_markup)
        context.user_data['state'] = config.STATE_RECIPE_AWAITING_INFO # Establecer estado
    elif text == config.BTN_RECETA_CORREGIR:
        logger.debug(f"{chat_id}: Iniciando flujo para corregir receta.")
        await update.message.reply_text("Para solicitar una corrección en una receta:\n1. Describe brevemente qué necesita corregirse (ej: cambio de dosis, fecha incorrecta).\n2. Adjunta una foto clara de la receta que necesita corrección.\n\nPresiona '🚫 Cancelar Acción Actual' si cambias de opinión.", reply_markup=keyboards.cancel_markup)
        context.user_data['state'] = config.STATE_RECIPE_AWAITING_CORRECTION # Establecer estado
    elif text == config.BTN_VOLVER:
        # El botón Volver genérico es manejado directamente en main.py por utils.send_main_menu
        logger.warning(f"{chat_id}: Botón Volver procesado inesperadamente en handle_receta_sub_choice. Redirigiendo a utils.send_main_menu.")
        await utils.send_main_menu(update, context)
    else:
        logger.warning(f"Opción no reconocida en handle_receta_sub_choice: {text}")
        await update.message.reply_text("Opción no reconocida dentro del menú de recetas.", reply_markup=keyboards.receta_menu_markup)


async def handle_receta_info_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Maneja texto cuando se espera info para NUEVA receta
    text = update.message.text; chat_id = update.effective_chat.id; user = update.effective_user
    logger.info(f"State {config.STATE_RECIPE_AWAITING_INFO}: Recibido texto '{text}' de {chat_id}")

    log_msg=f"Solicitud Receta (Texto):\nPaciente: @{user.username or user.first_name} ({chat_id})\nInfo: {text}"
    logger.info(f"Preparando notificación para secretaría: {log_msg}")
    # --- Notificar a Secretaria ---
    if config.SECRETARY_CHAT_ID:
       try:
           await context.bot.send_message(chat_id=config.SECRETARY_CHAT_ID, text=log_msg)
           logger.info(f"Notificación enviada a secretaría ({config.SECRETARY_CHAT_ID}).")
           await update.message.reply_text("Tu solicitud de receta ha sido enviada. Te avisarán cuando esté lista.\nVolviendo...", reply_markup=keyboards.main_menu_markup)
       except Exception as e:
           logger.error(f"Error al notificar a secretaría ({config.SECRETARY_CHAT_ID}): {e}")
           await update.message.reply_text("Solicitud recibida, pero hubo un problema al notificar. Contacta directamente si es urgente.", reply_markup=keyboards.main_menu_markup)
    else:
         logger.warning("SECRETARY_CHAT_ID no configurado.")
         await update.message.reply_text("Solicitud recibida (secretaría no notificada).\nVolviendo...", reply_markup=keyboards.main_menu_markup)

    context.user_data.clear()
    await utils.send_main_menu(update, context)


async def handle_receta_correction_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Maneja texto cuando se espera info para CORREGIR receta
    text = update.message.text; chat_id = update.effective_chat.id; user = update.effective_user
    logger.info(f"State {config.STATE_RECIPE_AWAITING_CORRECTION}: Recibido texto '{text}' de {chat_id}")

    context.user_data['correction_text'] = text # Guardar texto
    logger.debug(f"Texto de corrección guardado para {chat_id}. Esperando foto.")
    await update.message.reply_text(f"Descrip: '{text}'. Adjunta foto de receta a corregir o cancela.", reply_markup=keyboards.cancel_markup)
    # Mantenemos estado STATE_RECIPE_AWAITING_CORRECTION


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Maneja CUALQUIER foto recibida
    # NO necesita la bandera 'handled_in_group_0' porque tiene su propio filtro PHOTO
    if not update.message or not update.message.photo: logger.warning("handle_photo llamado sin msg/foto."); return

    chat_id = update.effective_chat.id; user = update.effective_user
    current_state = context.user_data.get('state')
    photo_file_id = update.message.photo[-1].file_id
    caption = update.message.caption or ""
    logger.info(f"Foto de {chat_id} (@{user.username or 'N/A'}), Estado:{current_state}, FileID:{photo_file_id}, Caption:'{caption}'")

    log_msg_base = f"Paciente: @{user.username or user.first_name} ({chat_id})\nFileID: {photo_file_id}"
    notification_text = None
    reply_text = "Foto recibida, pero no sé qué hacer con ella. Usa /start."
    clear_state_and_menu = True

    if current_state == config.STATE_RECIPE_AWAITING_INFO:
        logger.info(f"Foto para NUEVA receta ({chat_id}).")
        recipe_info = caption if caption else "(Solo Foto)"
        notification_text = f"Solicitud Receta (FOTO):\n{log_msg_base}\nInfo: {recipe_info}"
        reply_text = "Foto de receta recibida. Secretaría procesará.\nVolviendo..."

    elif current_state == config.STATE_RECIPE_AWAITING_CORRECTION:
        logger.info(f"Foto para CORREGIR receta ({chat_id}).")
        correction_text = context.user_data.pop('correction_text', caption if caption else "(Sin descrip.)")
        notification_text = f"Corrección Receta (FOTO):\n{log_msg_base}\nDescrip: {correction_text}"
        reply_text = "Foto y descrip. recibidas. Secretaría revisará.\nVolviendo..."

    else:
        logger.warning(f"Foto recibida en estado inesperado: {current_state}.")
        notification_text = f"Foto Inesperada:\n{log_msg_base}\nEstado: {current_state}\nCaption: {caption or '(Ninguno)'}"
        reply_text = "Recibí foto, pero no la esperaba. Usa /start."

    # --- Notificar a Secretaria ---
    if notification_text and config.SECRETARY_CHAT_ID:
        logger.info(f"Notificando a secretaría: {notification_text}")
        try:
            await context.bot.send_message(chat_id=config.SECRETARY_CHAT_ID, text=notification_text)
            logger.info(f"Notificación enviada a secretaría ({config.SECRETARY_CHAT_ID}).")
        except Exception as e:
            logger.error(f"Error al notificar a secretaría ({config.SECRETARY_CHAT_ID}): {e}")
            reply_text += "\n(Error al notificar a secretaría.)"
    elif notification_text:
        logger.warning("SECRETARY_CHAT_ID no configurado.")
        reply_text += "\n(Secretaría no notificada.)"

    # --- Responder y limpiar ---
    await update.message.reply_text(reply_text, reply_markup=keyboards.main_menu_markup)
    if clear_state_and_menu:
        context.user_data.clear()
        await utils.send_main_menu(update, context)