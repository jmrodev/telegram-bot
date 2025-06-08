# -*- coding: utf-8 -*-
# mi_bot_consultorio.py (v1.3 - Final con GCal CRUD básico)

import logging
import os.path
import datetime
import pytz # pip install pytz
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU # pip install python-dateutil
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler, # No se usa activamente ahora
)
# Imports Google Calendar
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Configuración ---
# ¡¡¡IMPORTANTE!!! Reemplaza con tu token real de BotFather
TELEGRAM_TOKEN = '8085015867:AAEeEJg702mgx0kxfsG303Llqf5HOgRsOal'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO # Cambia a logging.DEBUG para ver más detalles
)
logger = logging.getLogger(__name__)

# --- Configuración Google Calendar ---
SERVICE_ACCOUNT_FILE = 'credentials.json' # Asume en la misma carpeta
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = "America/Argentina/Buenos_Aires" # ¡Ajusta si es necesario!

# Mapeo Doctor -> ID de Calendario
CALENDAR_IDS_DOCTORES = {
   "Dr. Pérez": "ID_CALENDARIO_PEREZ@group.calendar.google.com", # !!! Reemplaza con el ID real !!!
   "Dra. Gómez": "ID_CALENDARIO_GOMEZ@group.calendar.google.com", # !!! Reemplaza con el ID real !!!
   "Dr. Rodríguez": "chello1975@gmail.com" # ID principal para Dr. Rodríguez
}

# --- Variables Globales / Estado (Almacenamiento temporal) ---
# Considerar usar context.user_data o context.chat_data para mejor manejo de estado por usuario/chat
patient_confirmations = {}
user_state = {} # Estado actual del usuario en un flujo
appointment_requests = {} # Datos temporales para solicitar turno

# --- Datos Configurables ---
DOCTOR_LIST = list(CALENDAR_IDS_DOCTORES.keys())
DAY_LIST = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

# Textos de botones
BTN_TURNO = "📅 Turno"
BTN_RECETA = "℞ Receta"
BTN_PAGO = "💲 Pago"
BTN_TURNO_SOLICITAR = "➕ Solicitar Turno"
BTN_TURNO_ELIMINAR = "🗑️ Cancelar Turno Existente"
BTN_TURNO_EDITAR = "✏️ Editar Turno Existente"
BTN_TURNO_VIDEO = "📹 Videollamada"
BTN_TURNO_DOCTOR = "👨‍⚕️ ¿Con qué doctor?"
BTN_TURNO_SECRETARIA = "🧑‍💼 Comunicarse con Secretaría"
BTN_RECETA_SOLICITAR = "💊 Solicitar Nueva"
BTN_RECETA_CORREGIR = "✍️ Corregir Existente"
BTN_PAGO_TRANFERENCIA = "🏦 Transferencia"
BTN_PAGO_CONSULTORIO = "🏢 En Consultorio"
BTN_VOLVER = "🔙 Volver al Menú Principal"
BTN_CANCELAR_ACCION = "🚫 Cancelar Acción Actual"

# --- Teclados ---
main_menu_markup = ReplyKeyboardMarkup([[KeyboardButton(BTN_TURNO)], [KeyboardButton(BTN_RECETA), KeyboardButton(BTN_PAGO)],], resize_keyboard=True)
turno_menu_markup = ReplyKeyboardMarkup([[KeyboardButton(BTN_TURNO_SOLICITAR)], [KeyboardButton(BTN_TURNO_ELIMINAR), KeyboardButton(BTN_TURNO_EDITAR)], [KeyboardButton(BTN_TURNO_VIDEO), KeyboardButton(BTN_TURNO_DOCTOR)], [KeyboardButton(BTN_TURNO_SECRETARIA)], [KeyboardButton(BTN_VOLVER)],], resize_keyboard=True)
receta_menu_markup = ReplyKeyboardMarkup([[KeyboardButton(BTN_RECETA_SOLICITAR)], [KeyboardButton(BTN_RECETA_CORREGIR)], [KeyboardButton(BTN_VOLVER)],], resize_keyboard=True)
pago_menu_markup = ReplyKeyboardMarkup([[KeyboardButton(BTN_PAGO_TRANFERENCIA)], [KeyboardButton(BTN_PAGO_CONSULTORIO)], [KeyboardButton(BTN_VOLVER)],], resize_keyboard=True)
cancel_markup = ReplyKeyboardMarkup([[KeyboardButton(BTN_CANCELAR_ACCION)]], resize_keyboard=True, one_time_keyboard=True)

# --- Funciones Auxiliares para Fechas ---
def get_next_weekday_date(day_name: str) -> datetime.date | None:
    today = datetime.date.today()
    day_mapping = {"Lunes": MO, "Martes": TU, "Miércoles": WE, "Jueves": TH, "Viernes": FR, "Sábado": SA, "Domingo": SU}
    weekday_const = day_mapping.get(day_name.capitalize())
    if weekday_const is None: logger.warning(f"Día inválido: {day_name}"); return None
    try:
        next_date = today + relativedelta(weekday=weekday_const(+1))
        logger.info(f"Calculada fecha para próximo '{day_name}': {next_date.isoformat()}")
        return next_date
    except Exception as e: logger.error(f"Error calculando fecha para {day_name}: {e}"); return None

def format_rfc3339(date_obj: datetime.date, time_str: str, timezone_str: str = TIMEZONE) -> tuple[str | None, str | None]:
    try:
        time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
        tz = pytz.timezone(timezone_str)
        start_dt = tz.localize(datetime.datetime.combine(date_obj, time_obj))
        end_dt = start_dt + datetime.timedelta(minutes=30) # Duración turno 30 min
        start_rfc = start_dt.isoformat(); end_rfc = end_dt.isoformat()
        logger.info(f"Formateado RFC3339: Inicio={start_rfc}, Fin={end_rfc}")
        return start_rfc, end_rfc
    except Exception as e: logger.error(f"Error format_rfc3339({date_obj}, {time_str}): {e}"); return None, None

# --- Funciones de Google Calendar ---
def get_calendar_service():
    """Crea y retorna objeto servicio autenticado para Google Calendar."""
    creds = None
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
             logger.critical(f"ERROR: Archivo credenciales '{SERVICE_ACCOUNT_FILE}' NO encontrado en {os.getcwd()}."); return None
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=creds)
        logger.info("Servicio Google Calendar autenticado OK.")
        return service
    except Exception as e: logger.critical(f"ERROR CRÍTICO autenticando GCal: {e}", exc_info=True); return None

calendar_service = get_calendar_service()

def check_google_calendar_availability(service, doctor_name: str, date_obj: datetime.date) -> list:
    """Consulta GCal para obtener horarios libres para un doctor/fecha."""
    if not service or not date_obj or doctor_name not in CALENDAR_IDS_DOCTORES: logger.error(f"check_avail: Args inválidos"); return []
    calendar_id = CALENDAR_IDS_DOCTORES[doctor_name]
    logger.info(f"Consultando disponibilidad real GCal Dr:{doctor_name} (Cal:{calendar_id}) en {date_obj.isoformat()}")
    available_slots = []
    try:
        tz = pytz.timezone(TIMEZONE)
        day_start = tz.localize(datetime.datetime.combine(date_obj, datetime.time(9, 0))) # 9 AM
        day_end = tz.localize(datetime.datetime.combine(date_obj, datetime.time(18, 0))) # 6 PM
        time_min = day_start.isoformat(); time_max = day_end.isoformat()
        body = {"timeMin": time_min, "timeMax": time_max, "timeZone": TIMEZONE, "items": [{"id": calendar_id}]}
        results = service.freebusy().query(body=body).execute()
        busy_intervals = results.get('calendars', {}).get(calendar_id, {}).get('busy', [])
        logger.debug(f"Intervalos ocupados: {busy_intervals}")
        # Calcular huecos libres
        office_start_hour = 9; office_end_hour = 18; slot_duration_minutes = 30
        now = datetime.datetime.now(tz); current_slot_start = day_start
        while current_slot_start < day_end:
            current_slot_end = current_slot_start + datetime.timedelta(minutes=slot_duration_minutes)
            if current_slot_end > day_end: break
            if current_slot_end <= now: current_slot_start = current_slot_end; continue
            is_busy = any(current_slot_start < datetime.datetime.fromisoformat(busy['end']).astimezone(tz) and \
                          current_slot_end > datetime.datetime.fromisoformat(busy['start']).astimezone(tz) \
                          for busy in busy_intervals)
            if not is_busy: available_slots.append(current_slot_start.strftime("%H:%M"))
            current_slot_start = current_slot_end
        logger.info(f"Horarios disponibles para {doctor_name} en {date_obj.isoformat()}: {available_slots}")
    except HttpError as error: logger.error(f"Error API GCal (freeBusy) Dr {doctor_name}: {error}")
    except Exception as e: logger.error(f"Error check_avail Dr {doctor_name}: {e}", exc_info=True)
    return available_slots

def create_google_calendar_event(service, doctor_name: str, day_str: str, time_str: str, user_info: dict) -> tuple[bool, str | None]:
    """Crea un evento (turno) en el calendario correcto del doctor."""
    if not service or doctor_name not in CALENDAR_IDS_DOCTORES: logger.error(f"create_event: Args inválidos"); return False, None
    calendar_id = CALENDAR_IDS_DOCTORES[doctor_name]
    user_name = user_info.get('username') or user_info.get('first_name','Paciente Tel'); user_id = user_info.get('id', 'N/A')
    logger.info(f"Creando evento GCal: Dr:{doctor_name}, Día:{day_str}, Hora:{time_str}, Paciente:{user_name}(ID:{user_id}) en Cal:{calendar_id}")
    target_date = get_next_weekday_date(day_str)
    if not target_date: logger.error(f"No fecha para '{day_str}'"); return False, None
    start_rfc, end_rfc = format_rfc3339(target_date, time_str, TIMEZONE)
    if not start_rfc or not end_rfc: logger.error(f"No formato RFC3339: {target_date} {time_str}"); return False, None
    event_body = {
        'summary': f"Turno {user_name} con {doctor_name}",
        'description': f"Solicitado vía Bot Telegram.\nUsuario: @{user_info.get('username', 'N/A')}\nID Chat: {user_id}", # Guardar ID Chat!
        'start': {'dateTime': start_rfc, 'timeZone': TIMEZONE}, 'end': {'dateTime': end_rfc, 'timeZone': TIMEZONE},
        'reminders': { 'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 60},{'method': 'popup', 'minutes': 1440},],},
    }
    try:
        logger.info(f"Enviando evento a GCal API: {event_body}")
        created_event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        event_link = created_event.get('htmlLink')
        logger.info(f"Evento creado OK GCal Dr.{doctor_name}. ID: {created_event.get('id')}, Link: {event_link}")
        return True, event_link
    except HttpError as error: logger.error(f"Error API GCal (insert) Dr.{doctor_name}: {error}"); return False, None
    except Exception as e: logger.error(f"Error creando evento GCal Dr.{doctor_name}: {e}", exc_info=True); return False, None

def find_google_calendar_events(service, doctor_name: str, date_obj: datetime.date, user_info: dict) -> list:
    """Busca eventos en GCal para un doctor/fecha/usuario específico (IMPLEMENTACIÓN REAL)."""
    if not service or not date_obj or doctor_name not in CALENDAR_IDS_DOCTORES: logger.error(f"find_events: Args inválidos"); return []
    calendar_id = CALENDAR_IDS_DOCTORES[doctor_name]; user_id = user_info.get('id', None)
    if not user_id: logger.error("find_events: No user_id"); return []
    logger.info(f"Buscando eventos REALES GCal Dr:{doctor_name} en {date_obj.isoformat()} (Cal:{calendar_id}) para UserID:{user_id}")
    events_found_formatted = []
    try:
        tz = pytz.timezone(TIMEZONE)
        time_min_dt = tz.localize(datetime.datetime.combine(date_obj, datetime.time(0, 0)))
        time_max_dt = tz.localize(datetime.datetime.combine(date_obj, datetime.time(23, 59, 59)))
        time_min = time_min_dt.isoformat(); time_max = time_max_dt.isoformat()
        # Buscar usando 'q' para filtrar por ID de Chat en la descripción
        search_query = f"ID Chat: {user_id}"
        logger.debug(f"Llamando events.list: calendarId={calendar_id}, timeMin={time_min}, timeMax={time_max}, q='{search_query}'")
        # --- LLAMADA REAL A LA API ---
        events_result = service.events().list(
            calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
            q=search_query, singleEvents=True, orderBy='startTime'
        ).execute()
        # ----------------------------
        items = events_result.get('items', [])
        logger.info(f"API encontró {len(items)} eventos potenciales para UserID {user_id} en {date_obj.isoformat()}.")
        for event in items:
            # Doble verificación en descripción (más seguro)
            if f"ID Chat: {user_id}" in event.get('description', ''):
                start_time_str = event['start'].get('dateTime')
                if start_time_str:
                    try: formatted_start_time = datetime.datetime.fromisoformat(start_time_str).astimezone(tz).strftime('%H:%M')
                    except ValueError: formatted_start_time = "Hora Inválida"
                else: continue # Ignorar eventos de todo el día
                events_found_formatted.append({
                    'summary': event.get('summary', 'Sin Título'),
                    'start_time': formatted_start_time,
                    'id': event.get('id') # ID del evento
                })
        logger.info(f"Eventos formateados/filtrados encontrados: {events_found_formatted}")
    except HttpError as error: logger.error(f"Error API GCal (list events) Dr {doctor_name}: {error}")
    except Exception as e: logger.error(f"Error find_events Dr {doctor_name}: {e}", exc_info=True)
    return events_found_formatted

def delete_google_calendar_event(service, doctor_name: str, event_id: str) -> bool:
    """Elimina un evento de GCal por su ID usando la API real."""
    if not service or doctor_name not in CALENDAR_IDS_DOCTORES or not event_id: logger.error(f"delete_event: Args inválidos"); return False
    calendar_id = CALENDAR_IDS_DOCTORES[doctor_name]
    logger.info(f"Intentando eliminar evento real ID: {event_id} de Cal: {calendar_id}")
    try:
        # --- LLAMADA REAL A LA API ---
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        # ----------------------------
        logger.info(f"Evento ID: {event_id} eliminado OK de Cal: {calendar_id}")
        return True
    except HttpError as error:
        if error.resp.status == 404 or error.resp.status == 410: # Not Found or Gone
             logger.warning(f"Error 404/410 al eliminar evento ID {event_id}. Asumiendo éxito (ya no existía).")
             return True # Considerarlo éxito si ya no estaba
        logger.error(f"Error API GCal (delete event) ID {event_id}: {error}"); return False
    except Exception as e: logger.error(f"Error delete_event ID {event_id}: {e}", exc_info=True); return False

# --- Funciones del Bot de Telegram ---
async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Por favor, elige una opción:") -> None:
    """Envía menú principal y limpia estados."""
    chat_id = update.effective_chat.id
    user_state.pop(chat_id, None); appointment_requests.pop(chat_id, None); context.user_data.clear()
    await update.message.reply_text(text, reply_markup=main_menu_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador /start."""
    user = update.effective_user; chat_id = update.effective_chat.id
    logger.info(f"Usuario {user.id} (@{user.username or 'N/A'}) /start chat {chat_id}.")
    await update.message.reply_html(f"¡Hola {user.mention_html()}! Asistente virtual.")
    await send_main_menu(update, context)

async def handle_main_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja selección menú principal."""
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Principal -> '{text}'")
    if text == BTN_TURNO: await update.message.reply_text("Opción Turnos:", reply_markup=turno_menu_markup)
    elif text == BTN_RECETA: await update.message.reply_text("Opción Recetas:", reply_markup=receta_menu_markup)
    elif text == BTN_PAGO: await update.message.reply_text("Opción Pagos:", reply_markup=pago_menu_markup)
    else: await send_main_menu(update, context, "Opción no reconocida.")

async def handle_turno_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja selección sub-menú Turnos."""
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Turno -> '{text}'")
    if text in [BTN_TURNO_SOLICITAR, BTN_TURNO_ELIMINAR, BTN_TURNO_EDITAR] and user_state.get(chat_id):
        await update.message.reply_text("Acción en curso. Cancela ('🚫 ...') primero.", reply_markup=turno_menu_markup); return

    if text == BTN_TURNO_SOLICITAR:
        user_state[chat_id] = 'turno_awaiting_doctor'
        keys = [[KeyboardButton(doc)] for doc in DOCTOR_LIST] + [[KeyboardButton(BTN_CANCELAR_ACCION)]]
        markup = ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("¿Con qué doctor?", reply_markup=markup)
    elif text == BTN_TURNO_ELIMINAR:
        logger.info(f"Chat {chat_id}: Inicia flujo eliminar turno.")
        user_state[chat_id] = 'delete_awaiting_date'
        keys = [[KeyboardButton(day)] for day in DAY_LIST] + [[KeyboardButton(BTN_CANCELAR_ACCION)]]
        markup = ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("¿De qué día es el turno a cancelar?", reply_markup=markup)
    elif text == BTN_TURNO_EDITAR:
        logger.info(f"Chat {chat_id}: Inicia flujo editar turno.")
        user_state[chat_id] = 'edit_awaiting_date'
        await update.message.reply_text("Función 'Editar Turno' - Pendiente. Contacta a secretaría.", reply_markup=turno_menu_markup)
        user_state.pop(chat_id, None) # Limpiar estado por ahora
    elif text == BTN_TURNO_VIDEO: await update.message.reply_text("Videollamadas: Coordinar con secretaría.")
    elif text == BTN_TURNO_DOCTOR: await update.message.reply_text(f"Doctores:\n{chr(10).join([f'• {d}' for d in DOCTOR_LIST])}\nPuedes elegir otra opción.", reply_markup=turno_menu_markup)
    elif text == BTN_TURNO_SECRETARIA: await update.message.reply_text("Escribe tu consulta para secretaría. Usa /start para volver.", reply_markup=ReplyKeyboardRemove()); user_state[chat_id] = 'talking_to_secretary'
    elif text == BTN_VOLVER: await send_main_menu(update, context)
    else:
        if not user_state.get(chat_id): await update.message.reply_text("Opción no reconocida.", reply_markup=main_menu_markup); await send_main_menu(update, context)

async def handle_receta_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja selección sub-menú Recetas."""
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Receta -> '{text}'")
    if text == BTN_RECETA_SOLICITAR:
        if user_state.get(chat_id): await update.message.reply_text("Acción en curso. Cancelar primero.", reply_markup=receta_menu_markup); return
        await update.message.reply_text("Solicitar:\n1. Escribe nombre medicamento.\n2. O adjunta foto.\n('🚫 Cancelar Acción Actual')", reply_markup=cancel_markup)
        user_state[chat_id] = 'receta_awaiting_info_or_photo'
    elif text == BTN_RECETA_CORREGIR:
        if user_state.get(chat_id): await update.message.reply_text("Acción en curso. Cancelar primero.", reply_markup=receta_menu_markup); return
        await update.message.reply_text("Corregir:\n1. Describe corrección.\n2. Adjunta foto receta.\n('🚫 Cancelar Acción Actual')", reply_markup=cancel_markup)
        user_state[chat_id] = 'receta_awaiting_correction_info_photo'
    elif text == BTN_VOLVER: await send_main_menu(update, context)
    else:
       if not user_state.get(chat_id): await update.message.reply_text("Opción no reconocida.", reply_markup=main_menu_markup); await send_main_menu(update, context)

async def handle_pago_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja selección sub-menú Pagos."""
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Pago -> '{text}'")
    if text == BTN_PAGO_TRANFERENCIA: await update.message.reply_text("Datos Transferencia:\nCBU: [Tu CBU]\nAlias: [Tu Alias]\nTitular: [Nombre Titular]\nEnviar comprobante.", reply_markup=pago_menu_markup)
    elif text == BTN_PAGO_CONSULTORIO: await update.message.reply_text("Puedes abonar en consultorio.", reply_markup=pago_menu_markup)
    elif text == BTN_VOLVER: await send_main_menu(update, context)
    else:
        if not user_state.get(chat_id): await update.message.reply_text("Opción no reconocida.", reply_markup=main_menu_markup); await send_main_menu(update, context)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador principal para texto."""
    if not calendar_service: await update.message.reply_text("Error: Servicio calendario no disponible."); logger.critical("handle_text: Sin servicio GCal."); return

    text = update.message.text; chat_id = update.effective_chat.id
    current_simple_state = user_state.get(chat_id); user = update.effective_user
    logger.info(f"Texto de {chat_id} (@{user.username or 'N/A'}), Estado: {current_simple_state}, Texto: '{text}'")

    # 0. Cancelación Global
    if text == BTN_CANCELAR_ACCION:
        logger.info(f"Acción cancelada por {chat_id}. Estado: {current_simple_state}")
        user_state.pop(chat_id, None); appointment_requests.pop(chat_id, None); context.user_data.clear()
        await update.message.reply_text("Acción cancelada."); await send_main_menu(update, context); return

    # --- Flujo Turno: Solicitar ---
    if current_simple_state == 'turno_awaiting_doctor':
        if text in DOCTOR_LIST:
            logger.info(f"Doctor elegido {chat_id}: {text}")
            if chat_id not in appointment_requests: appointment_requests[chat_id] = {}
            appointment_requests[chat_id]['doctor'] = text; user_state[chat_id] = 'turno_awaiting_day'
            keys = [[KeyboardButton(day)] for day in DAY_LIST] + [[KeyboardButton(BTN_CANCELAR_ACCION)]]
            markup = ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(f"Excelente. ¿Qué día para {text}?", reply_markup=markup)
        else: await update.message.reply_text(f"Elige doctor de lista o '{BTN_CANCELAR_ACCION}'.")
        return
    elif current_simple_state == 'turno_awaiting_day':
        day_str = text.capitalize()
        if day_str in DAY_LIST:
             logger.info(f"Día elegido {chat_id}: {day_str}")
             target_date = get_next_weekday_date(day_str)
             if not target_date: await update.message.reply_text("Error calculando fecha..."); return
             if chat_id not in appointment_requests: await update.message.reply_text("Error interno. Empieza /start."); await send_main_menu(update,context); return
             appointment_requests[chat_id]['day'] = day_str; appointment_requests[chat_id]['date_obj'] = target_date
             doctor = appointment_requests.get(chat_id, {}).get('doctor')
             disponible_slots = check_google_calendar_availability(calendar_service, doctor, target_date)
             if disponible_slots:
                 user_state[chat_id] = 'turno_awaiting_timeslot'; keys = [[KeyboardButton(s)] for s in disponible_slots] + [[KeyboardButton(BTN_CANCELAR_ACCION)]]; markup = ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)
                 await update.message.reply_text(f"Horarios para {doctor} el {day_str} ({target_date.strftime('%d/%m')}):", reply_markup=markup)
             else: await update.message.reply_text(f"No encontré horarios para {doctor} el {day_str}. Elige otro día o cancela.", reply_markup=cancel_markup)
        else: await update.message.reply_text(f"Elige día válido ({', '.join(DAY_LIST)}) o '{BTN_CANCELAR_ACCION}'.")
        return
    elif current_simple_state == 'turno_awaiting_timeslot':
        selected_time = text
        try: datetime.datetime.strptime(selected_time, '%H:%M'); valid_time = True
        except ValueError: valid_time = False
        if not valid_time: await update.message.reply_text(f"Formato hora inválido (HH:MM). Elige botón o '{BTN_CANCELAR_ACCION}'."); return

        logger.info(f"Horario elegido {chat_id}: {selected_time}")
        req_data = appointment_requests.get(chat_id, {}); doctor = req_data.get('doctor'); day_str = req_data.get('day'); user_info = user.to_dict()
        if doctor and day_str:
            success, event_link = create_google_calendar_event(calendar_service, doctor, day_str, selected_time, user_info)
            if success: await update.message.reply_text(f"¡Turno confirmado! {doctor} el {day_str} a las {selected_time}.\nVer: {event_link}\nVolviendo...", reply_markup=main_menu_markup, disable_web_page_preview=True); logger.info(f"Turno creado GCal {chat_id}. Link: {event_link}"); # TODO: Notificar
            else: await update.message.reply_text("Error al crear evento. Contacta a secretaría.", reply_markup=main_menu_markup)
        else: await update.message.reply_text("Error interno. Empieza /start.", reply_markup=main_menu_markup)
        user_state.pop(chat_id, None); appointment_requests.pop(chat_id, None); context.user_data.clear(); return

    # --- Flujo Eliminar Turno ---
    elif current_simple_state == 'delete_awaiting_date':
        day_str = text.capitalize()
        logger.info(f"Chat {chat_id}: Fecha para eliminar: {day_str}")
        target_date = get_next_weekday_date(day_str)
        if not target_date: await update.message.reply_text("Día inválido. Intenta de nuevo o cancela."); return
        context.user_data['date_to_delete'] = target_date
        user_state[chat_id] = 'delete_awaiting_doctor'
        keys = [[KeyboardButton(doc)] for doc in DOCTOR_LIST] + [[KeyboardButton(BTN_CANCELAR_ACCION)]]
        markup = ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(f"¿De qué doctor es el turno del {day_str} ({target_date.strftime('%d/%m')}) a cancelar?", reply_markup=markup)
        return
    elif current_simple_state == 'delete_awaiting_doctor':
         doctor_name = text
         if doctor_name in DOCTOR_LIST:
             target_date = context.user_data.get('date_to_delete')
             if not target_date: await update.message.reply_text("Error interno (sin fecha). /start."); return
             logger.info(f"Chat {chat_id}: Buscando turnos Dr.{doctor_name} en {target_date.isoformat()} para eliminar.")
             found_events = find_google_calendar_events(calendar_service, doctor_name, target_date, user.to_dict())
             if not found_events:
                 await update.message.reply_text(f"No encontré turnos a tu nombre con {doctor_name} el {target_date.strftime('%d/%m')}. Volviendo menú.", reply_markup=main_menu_markup)
                 user_state.pop(chat_id, None); context.user_data.clear(); return

             context.user_data['events_to_confirm_delete'] = found_events
             context.user_data['doctor_for_delete'] = doctor_name
             user_state[chat_id] = 'delete_awaiting_confirmation'
             event_list_text = f"Turnos para {doctor_name} el {target_date.strftime('%d/%m')}:\n"
             event_list_text += "\n".join([f"- {e.get('start_time','??:??')} ({e.get('summary','Ev.')})" for e in found_events])
             event_list_text += f"\nEscribe la HORA (HH:MM) del turno a cancelar o '{BTN_CANCELAR_ACCION}'."
             await update.message.reply_text(event_list_text, reply_markup=cancel_markup)
         else: await update.message.reply_text(f"Doctor no válido. Elige de lista o '{BTN_CANCELAR_ACCION}'.")
         return
    elif current_simple_state == 'delete_awaiting_confirmation':
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
            success = delete_google_calendar_event(calendar_service, doctor_name, event_to_delete_id)
            if success: await update.message.reply_text(f"Turno '{summary}' cancelado OK. Volviendo menú.", reply_markup=main_menu_markup)
            else: await update.message.reply_text("Error al cancelar turno en calendario. Contacta a secretaría.", reply_markup=main_menu_markup)
        elif not doctor_name: await update.message.reply_text("Error interno (sin doctor). /start.", reply_markup=main_menu_markup)
        else: await update.message.reply_text(f"No encontré turno a las {selected_time_to_delete}. Revisa o cancela.", reply_markup=cancel_markup)
        user_state.pop(chat_id, None); context.user_data.clear(); return

    # --- Flujo Editar Turno (Placeholder) ---
    elif current_simple_state == 'edit_awaiting_date':
        logger.info(f"Chat {chat_id}: Recibida fecha para editar: {text}")
        await update.message.reply_text("Función Editar - Pendiente.", reply_markup=main_menu_markup)
        user_state.pop(chat_id, None); return

    # --- Flujos Receta / Secretaria / Sí-No / Botones / Fallback ---
    elif current_simple_state == 'receta_awaiting_info_or_photo': logger.info(f"{chat_id}: Receta txt:'{text}'"); log_msg=f"Receta(Txt):@{user.username or user.first_name}({chat_id}):{text}"; logger.info(log_msg); await update.message.reply_text("Info recibida. Adjunta foto si es necesario. Volviendo.", reply_markup=main_menu_markup); user_state.pop(chat_id, None); return
    elif current_simple_state == 'receta_awaiting_correction_info_photo': logger.info(f"{chat_id}: Corrección receta txt:'{text}'"); context.user_data['correction_text'] = text; await update.message.reply_text(f"Descrip:'{text}'. Adjunta foto receta o cancela.", reply_markup=cancel_markup); return
    elif current_simple_state == 'talking_to_secretary': logger.info(f"{chat_id}: Msj p/Sec:'{text}'"); log_msg = f"Msj Sec de @{user.username or user.first_name}({chat_id}):{text}"; logger.info(f"Simulando envío:{log_msg}"); await update.message.reply_text("Msj enviado. Sigue o /start."); return # TODO: Implementar reenvío
    elif not current_simple_state: # Sin estado activo
        button_texts = [BTN_TURNO, BTN_RECETA, BTN_PAGO, BTN_TURNO_SOLICITAR, BTN_TURNO_ELIMINAR, BTN_TURNO_EDITAR, BTN_TURNO_VIDEO, BTN_TURNO_DOCTOR, BTN_TURNO_SECRETARIA, BTN_RECETA_SOLICITAR, BTN_RECETA_CORREGIR, BTN_PAGO_TRANFERENCIA, BTN_PAGO_CONSULTORIO, BTN_VOLVER]
        if text in button_texts:
            if text in [BTN_TURNO, BTN_RECETA, BTN_PAGO]: await handle_main_menu_choice(update, context)
            elif text in [BTN_TURNO_SOLICITAR, BTN_TURNO_ELIMINAR, BTN_TURNO_EDITAR, BTN_TURNO_VIDEO, BTN_TURNO_DOCTOR, BTN_TURNO_SECRETARIA, BTN_VOLVER]: await handle_turno_choice(update, context)
            elif text in [BTN_RECETA_SOLICITAR, BTN_RECETA_CORREGIR]: await handle_receta_choice(update, context)
            elif text in [BTN_PAGO_TRANFERENCIA, BTN_PAGO_CONSULTORIO]: await handle_pago_choice(update, context)
            return
        elif text.lower() in ['sí', 'si']: logger.info(f"SÍ de {chat_id} (no state)"); patient_confirmations[chat_id]={"r":"Sí","t":update.message.date,"u":user.to_dict()}; await update.message.reply_text("Confirmado. Gracias!"); logger.info(f"Confirma:{patient_confirmations}"); return # TODO: Notificar
        elif text.lower() == 'no': logger.info(f"NO de {chat_id} (no state)"); patient_confirmations[chat_id]={"r":"No","t":update.message.date,"u":user.to_dict()}; await update.message.reply_text("Entendido. Gracias."); logger.info(f"Confirma:{patient_confirmations}"); return # TODO: Notificar
        else: logger.warning(f"Msg no reconocido {chat_id}:'{text}'. Menú."); await send_main_menu(update, context, "No entendí. Usa el menú:")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja recepción de fotos para recetas."""
    chat_id = update.effective_chat.id; user = update.effective_user
    current_simple_state = user_state.get(chat_id)
    photo_file_id = update.message.photo[-1].file_id; caption = update.message.caption or ""
    logger.info(f"Foto de {chat_id}(@{user.username or 'N/A'}), Estado:{current_simple_state}, FileID:{photo_file_id}, Caption:'{caption}'")
    if current_simple_state == 'receta_awaiting_info_or_photo':
        logger.info(f"Foto NUEVA receta ({chat_id}).")
        log_msg = f"Receta(FOTO):\nPac:@{user.username or user.first_name}({chat_id})\nFileID:{photo_file_id}\nTexto:{caption}"
        logger.info(log_msg); # TODO: Notificar secretaria
        await update.message.reply_text("Foto recibida. Secretaría procesará. Volviendo menú.", reply_markup=main_menu_markup)
        user_state.pop(chat_id, None)
    elif current_simple_state == 'receta_awaiting_correction_info_photo':
        logger.info(f"Foto CORREGIR receta ({chat_id}).")
        correction_text = context.user_data.pop('correction_text', caption or '(Sin texto adicional)')
        log_msg = f"Corrección Receta(FOTO):\nPac:@{user.username or user.first_name}({chat_id})\nFileID:{photo_file_id}\nDescrip:{correction_text}"
        logger.info(log_msg); # TODO: Notificar secretaria
        await update.message.reply_text("Foto y descrip recibidas. Secretaría revisará. Volviendo menú.", reply_markup=main_menu_markup)
        user_state.pop(chat_id, None)
    else: logger.info(f"Foto {chat_id} fuera de flujo. Ignorando."); await update.message.reply_text("Recibí foto, pero no la esperaba. Usa /start.")

# --- Función Principal (main) ---
def main() -> None:
    """Inicia el bot."""
    if not calendar_service: logger.critical("¡ERROR CRÍTICO! No auth GCal."); print("\n---¡ERROR AL INICIAR!---\nRevisa logs/JSON.\nBot NO iniciado.\n----------------------\n"); return

    logger.info("Iniciando bot v1.3 (GCal CRUD Real)...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message), group=1)
    logger.info("Bot escuchando...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
