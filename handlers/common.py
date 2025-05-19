# handlers/common.py
import logging
from telegram import Update
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
    user = update.effective_user; chat_id = update.effective_chat.id
    logger.info(f"Usuario {user.id} (@{user.username or 'N/A'}) ejecutó /start en chat {chat_id}.")
    await update.message.reply_html(f"¡Hola {user.mention_html()}! Bienvenido al asistente virtual.")
    # Limpiar estado y mostrar menú principal usando la función de utils
    await utils.send_main_menu(update, context, "Por favor, elige una opción del menú:")


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
    user = update.effective_user; chat_id = update.effective_chat.id
    logger.info(f"Router Texto x Estado (G1): Chat {chat_id}, Estado: {state}, Texto: '{text}' (No manejado G0)")

    # --- PASO 1: DIRIGIR SEGÚN ESTADO ---
    from . import turno, receta, misc

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
        except Exception as e:
            logger.error(f"Error ejecutando handler para estado '{state}': {e}", exc_info=True)
            await update.message.reply_text("Error procesando solicitud.")
            # Considerar limpiar estado aquí
        return

    # --- SI NO HABÍA ESTADO ACTIVO O ESTADO NO MAPEADO ---
    logger.debug(f"No hay estado activo o '{state}' no mapeado. Verificando Sí/No.")

    # --- PASO 2: Manejar Sí/No si no hay estado ---
    try:
        processed_yes_no = await misc.handle_yes_no(update, context)
        if processed_yes_no: logger.info("Mensaje procesado como Sí/No."); return
    except Exception as e: logger.error(f"Error llamando misc.handle_yes_no: {e}", exc_info=True)

    # --- PASO 3: Fallback final: Mensaje desconocido ---
    logger.info(f"Texto '{text}' no corresponde a estado ni Sí/No. Llamando a handle_unknown_text...")
    await handle_unknown_text(update, context)


async def handle_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador fallback para texto no reconocido."""
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"
    logger.warning(f"-> Entrando en handle_unknown_text (Chat ID: {chat_id}, Texto: '{text}')")
    await utils.send_main_menu(update, context, "No entendí tu mensaje. Usa las opciones del menú:")
    logger.warning(f"<- Saliendo de handle_unknown_text (Menú principal enviado)")