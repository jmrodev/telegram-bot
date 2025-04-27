# handlers/common.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
import keyboards
# Ya no importa otros handlers, importa utils si es necesario (aquí no lo es directamente)
# from . import turno, receta, pago, misc # <- Quitar
from .utils import send_main_menu, cancel_action # Importar desde utils

# Importar los módulos específicos solo para el router (o quitar el router de aquí)
from . import turno, receta, pago, misc

logger = logging.getLogger(__name__)

# Start sigue igual
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; chat_id = update.effective_chat.id
    logger.info(f"Usuario {user.id} (@{user.username or 'N/A'}) /start chat {chat_id}.")
    await update.message.reply_html(f"¡Hola {user.mention_html()}! Asistente virtual.")
    await send_main_menu(update, context) # Llama a la función desde utils

# Este handler ahora solo maneja texto que NO es un botón conocido Y que está en un estado específico,
# O el fallback final si no hay estado y no es un botón ni Sí/No.
async def route_text_message_by_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dirige mensajes de texto al handler apropiado basado SOLO en ESTADO."""
    calendar_service = context.bot_data.get('calendar_service')
    if not calendar_service: await update.message.reply_text("Error: Servicio calendario no disponible."); logger.critical("route_text: Sin servicio GCal."); return

    text = update.message.text; state = context.user_data.get('state')
    user = update.effective_user; chat_id = update.effective_chat.id
    logger.info(f"Router Texto x Estado: Chat {chat_id}, Estado: {state}, Texto: '{text}'")

    # 1. Dirigir según estado
    state_handlers = {
        config.STATE_WAITING_DOCTOR: turno.handle_turno_solicitar_doctor,
        config.STATE_WAITING_DAY: turno.handle_turno_solicitar_dia,
        config.STATE_WAITING_TIMESLOT: turno.handle_turno_solicitar_hora,
        config.STATE_DELETE_AWAITING_DATE: turno.handle_turno_eliminar_dia,
        config.STATE_DELETE_AWAITING_DOCTOR: turno.handle_turno_eliminar_doctor,
        config.STATE_DELETE_AWAITING_CONFIRMATION: turno.handle_turno_eliminar_confirmacion,
        config.STATE_EDIT_AWAITING_DATE: turno.handle_turno_editar_placeholder,
        config.STATE_RECIPE_AWAITING_INFO: receta.handle_receta_info_text,
        config.STATE_RECIPE_AWAITING_CORRECTION: receta.handle_receta_correction_text,
        config.STATE_TALKING_TO_SECRETARY: misc.handle_secretary_message,
    }
    if state in state_handlers:
        await state_handlers[state](update, context)
        return

    # --- Si no hay estado activo ---
    # 2. Manejar Sí/No (si no es un botón)
    if await misc.handle_yes_no(update, context):
        return

    # 3. Fallback final: Mensaje desconocido
    await handle_unknown_text(update, context)

async def handle_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador para texto no reconocido fuera de un flujo/botón."""
    chat_id = update.effective_chat.id; text = update.message.text
    logger.warning(f"Texto no reconocido (sin estado/botón) de {chat_id}: '{text}'. Mostrando menú.")
    await send_main_menu(update, context, "No entendí tu mensaje. Puedes usar las opciones del menú:")