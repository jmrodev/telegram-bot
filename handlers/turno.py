# handlers/turno.py
import logging
import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes
import config
import keyboards
import google_calendar_utils as gcal
from .utils import send_main_menu, cancel_action # <<< IMPORT DESDE UTILS

logger = logging.getLogger(__name__)

# El resto de las funciones de turno (handle_turno_menu, handle_turno_sub_choice, etc.)
# permanecen igual que en la versión anterior, pero ahora usan send_main_menu de utils
# cuando necesitan volver al menú principal.

# Ejemplo de función (el resto serían similares):
async def handle_turno_sub_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Turno -> '{text}'")
    current_state = context.user_data.get('state')
    if text != config.BTN_VOLVER and text in [config.BTN_TURNO_SOLICITAR, config.BTN_TURNO_ELIMINAR, config.BTN_TURNO_EDITAR] and current_state:
        await update.message.reply_text("Acción en curso. Cancela ('🚫 ...') primero.", reply_markup=keyboards.turno_menu_markup); return

    # ... (lógica para cada botón de turno como antes) ...

    elif text == config.BTN_VOLVER:
        await send_main_menu(update, context) # <<< LLAMADA A FUNCION DE UTILS

    else: await update.message.reply_text("Opción no reconocida.", reply_markup=keyboards.turno_menu_markup)

# --- PEGAR AQUÍ EL RESTO DE FUNCIONES DE TURNO DE LA VERSIÓN ANTERIOR ---
# handle_turno_menu, handle_turno_solicitar_doctor, handle_turno_solicitar_dia,
# handle_turno_solicitar_hora, handle_turno_eliminar_dia, handle_turno_eliminar_doctor,
# handle_turno_eliminar_confirmacion, handle_turno_editar_placeholder
async def handle_turno_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Selecciona una opción para Turnos:", reply_markup=keyboards.turno_menu_markup)

async def handle_turno_solicitar_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    if text in config.DOCTOR_LIST:
        logger.info(f"Doctor elegido {chat_id}: {text}")
        context.user_data.setdefault('appointment_request', {})['doctor'] = text
        context.user_data['state'] = config.STATE_WAITING_DAY
        markup = keyboards.create_day_keyboard()
        await update.message.reply_text(f"Excelente. ¿Qué día para {text}?", reply_markup=markup)
    else: await update.message.reply_text(f"Elige doctor de lista o '{config.BTN_CANCELAR_ACCION}'.")

async def handle_turno_solicitar_dia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    day_str = text.capitalize()
    if day_str in config.DAY_LIST:
         logger.info(f"Día elegido {chat_id}: {day_str}")
         target_date = gcal.get_next_weekday_date(day_str)
         if not target_date: await update.message.reply_text("Error calculando fecha..."); return
         req_data = context.user_data.get('appointment_request')
         if not req_data or 'doctor' not in req_data: await update.message.reply_text("Error interno. /start."); await send_main_menu(update,context); return
         req_data['day'] = day_str; req_data['date_obj'] = target_date
         doctor = req_data.get('doctor')
         calendar_service = context.bot_data.get('calendar_service')
         disponible_slots = gcal.check_google_calendar_availability(calendar_service, doctor, target_date)
         if disponible_slots:
             context.user_data['state'] = config.STATE_WAITING_TIMESLOT
             markup = keyboards.create_timeslot_keyboard(disponible_slots)
             await update.message.reply_text(f"Horarios para {doctor} el {day_str} ({target_date.strftime('%d/%m')}):", reply_markup=markup)
         else: await update.message.reply_text(f"No encontré horarios para {doctor} el {day_str}. Elige otro día o cancela.", reply_markup=keyboards.cancel_markup)
    else: await update.message.reply_text(f"Elige día válido ({', '.join(config.DAY_LIST)}) o '{config.BTN_CANCELAR_ACCION}'.")

async def handle_turno_solicitar_hora(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id; user = update.effective_user
    selected_time = text
    try: datetime.datetime.strptime(selected_time, '%H:%M'); valid_time = True
    except ValueError: valid_time = False
    if not valid_time: await update.message.reply_text(f"Formato hora inválido (HH:MM). Elige botón o '{config.BTN_CANCELAR_ACCION}'."); return

    logger.info(f"Horario elegido {chat_id}: {selected_time}")
    req_data = context.user_data.get('appointment_request', {}); doctor = req_data.get('doctor'); day_str = req_data.get('day')
    if doctor and day_str:
        calendar_service = context.bot_data.get('calendar_service')
        success, event_link = gcal.create_google_calendar_event(calendar_service, doctor, day_str, selected_time, user.to_dict())
        if success:
            await update.message.reply_text(f"¡Turno confirmado! {doctor} el {day_str} a las {selected_time}.\nVer: {event_link}\nVolviendo...", reply_markup=keyboards.main_menu_markup, disable_web_page_preview=True)
            logger.info(f"Turno creado GCal {chat_id}. Link: {event_link}"); # TODO: Notificar secretaria
        else: await update.message.reply_text("Error al crear evento. Contacta a secretaría.", reply_markup=keyboards.main_menu_markup)
    else: await update.message.reply_text("Error interno. /start.", reply_markup=keyboards.main_menu_markup)
    context.user_data.clear() # Limpiar datos al finalizar

async def handle_turno_eliminar_dia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    day_str = text.capitalize()
    logger.info(f"Chat {chat_id}: Fecha para eliminar: {day_str}")
    target_date = gcal.get_next_weekday_date(day_str)
    if not target_date: await update.message.reply_text("Día inválido. Intenta de nuevo o cancela."); return
    context.user_data['date_to_delete'] = target_date
    context.user_data['state'] = config.STATE_DELETE_AWAITING_DOCTOR
    markup = keyboards.create_doctor_keyboard()
    await update.message.reply_text(f"¿De qué doctor es el turno del {day_str} ({target_date.strftime('%d/%m')}) a cancelar?", reply_markup=markup)

async def handle_turno_eliminar_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id; user = update.effective_user
    doctor_name = text
    if doctor_name in config.DOCTOR_LIST:
         target_date = context.user_data.get('date_to_delete')
         if not target_date: await update.message.reply_text("Error interno (sin fecha). /start."); return
         logger.info(f"Chat {chat_id}: Buscando turnos Dr.{doctor_name} en {target_date.isoformat()} para eliminar.")
         calendar_service = context.bot_data.get('calendar_service')
         found_events = gcal.find_google_calendar_events(calendar_service, doctor_name, target_date, user.to_dict())
         if not found_events:
             await update.message.reply_text(f"No encontré turnos a tu nombre con {doctor_name} el {target_date.strftime('%d/%m')}. Volviendo menú.", reply_markup=keyboards.main_menu_markup)
             context.user_data.clear(); return

         context.user_data['events_to_confirm_delete'] = found_events
         context.user_data['doctor_for_delete'] = doctor_name
         context.user_data['state'] = config.STATE_DELETE_AWAITING_CONFIRMATION
         event_list_text = f"Turnos para {doctor_name} el {target_date.strftime('%d/%m')}:\n"
         event_list_text += "\n".join([f"- {e.get('start_time','??:??')} ({e.get('summary','Ev.')})" for e in found_events])
         event_list_text += f"\nEscribe HORA (HH:MM) a cancelar o '{config.BTN_CANCELAR_ACCION}'."
         await update.message.reply_text(event_list_text, reply_markup=keyboards.cancel_markup)
    else: await update.message.reply_text(f"Doctor no válido. Elige de lista o '{config.BTN_CANCELAR_ACCION}'.")

async def handle_turno_eliminar_confirmacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    selected_time_to_delete = text
    try: datetime.datetime.strptime(selected_time_to_delete, '%H:%M'); valid_time = True
    except ValueError: valid_time = False
    if not valid_time: await update.message.reply_text(f"Formato hora inválido ({selected_time_to_delete}). Escribe HH:MM o cancela."); return

    found_events = context.user_data.get('events_to_confirm_delete', [])
    doctor_name = context.user_data.get('doctor_for_delete')
    event_to_delete_id = None; summary = "Evento"
    for event in found_events:
        if event.get('start_time') == selected_time_to_delete: event_to_delete_id = event.get('id'); summary = event.get('summary'); break

    if event_to_delete_id and doctor_name:
        logger.info(f"Chat {chat_id}: Confirmado borrar evento ID {event_to_delete_id} ('{summary}')")
        calendar_service = context.bot_data.get('calendar_service')
        success = gcal.delete_google_calendar_event(calendar_service, doctor_name, event_to_delete_id)
        if success: await update.message.reply_text(f"Turno '{summary}' cancelado OK. Volviendo menú.", reply_markup=keyboards.main_menu_markup)
        else: await update.message.reply_text("Error al cancelar turno. Contacta a secretaría.", reply_markup=keyboards.main_menu_markup)
    elif not doctor_name: await update.message.reply_text("Error interno. /start.", reply_markup=keyboards.main_menu_markup)
    else: await update.message.reply_text(f"No encontré turno a las {selected_time_to_delete}. Revisa o cancela.", reply_markup=keyboards.cancel_markup)
    context.user_data.clear()

async def handle_turno_editar_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Chat {update.effective_chat.id}: Placeholder para editar fecha: {update.message.text}")
    await update.message.reply_text("Función Editar - Pendiente.", reply_markup=keyboards.main_menu_markup)
    context.user_data.clear(); # Limpiar estado por ahora