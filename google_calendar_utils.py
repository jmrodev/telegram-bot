# google_calendar_utils.py
import logging
import datetime
import pytz
import os
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import config # Importar configuración

logger = logging.getLogger(__name__)

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

def format_rfc3339(date_obj: datetime.date, time_str: str, timezone_str: str = config.TIMEZONE) -> tuple[str | None, str | None]:
    try:
        time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
        tz = pytz.timezone(timezone_str)
        start_dt = tz.localize(datetime.datetime.combine(date_obj, time_obj))
        end_dt = start_dt + datetime.timedelta(minutes=config.SLOT_DURATION_MINUTES)
        start_rfc = start_dt.isoformat(); end_rfc = end_dt.isoformat()
        logger.info(f"Formateado RFC3339: Inicio={start_rfc}, Fin={end_rfc}")
        return start_rfc, end_rfc
    except Exception as e: logger.error(f"Error format_rfc3339({date_obj}, {time_str}): {e}"); return None, None

# --- Funciones Principales de Google Calendar ---
def get_calendar_service():
    creds = None
    try:
        if not os.path.exists(config.SERVICE_ACCOUNT_FILE):
             logger.critical(f"ERROR: Archivo credenciales '{config.SERVICE_ACCOUNT_FILE}' NO encontrado."); return None
        creds = Credentials.from_service_account_file(config.SERVICE_ACCOUNT_FILE, scopes=config.SCOPES)
        service = build('calendar', 'v3', credentials=creds)
        logger.info("Servicio Google Calendar autenticado OK.")
        return service
    except Exception as e: logger.critical(f"ERROR CRÍTICO autenticando GCal: {e}", exc_info=True); return None

def check_google_calendar_availability(service, doctor_name: str, date_obj: datetime.date) -> list:
    if not service or not date_obj or doctor_name not in config.CALENDAR_IDS_DOCTORES: logger.error(f"check_avail: Args inválidos"); return []
    calendar_id = config.CALENDAR_IDS_DOCTORES[doctor_name]
    logger.info(f"Consultando disponibilidad real GCal Dr:{doctor_name} (Cal:{calendar_id}) en {date_obj.isoformat()}")
    available_slots = []
    try:
        tz = pytz.timezone(config.TIMEZONE)
        day_start = tz.localize(datetime.datetime.combine(date_obj, datetime.time(config.OFFICE_START_HOUR, 0)))
        day_end = tz.localize(datetime.datetime.combine(date_obj, datetime.time(config.OFFICE_END_HOUR, 0)))
        time_min = day_start.isoformat(); time_max = day_end.isoformat()
        body = {"timeMin": time_min, "timeMax": time_max, "timeZone": config.TIMEZONE, "items": [{"id": calendar_id}]}
        results = service.freebusy().query(body=body).execute()
        busy_intervals = results.get('calendars', {}).get(calendar_id, {}).get('busy', [])
        logger.debug(f"Intervalos ocupados: {busy_intervals}")
        now = datetime.datetime.now(tz); current_slot_start = day_start
        while current_slot_start < day_end:
            current_slot_end = current_slot_start + datetime.timedelta(minutes=config.SLOT_DURATION_MINUTES)
            if current_slot_end > day_end: break
            if current_slot_end <= now: current_slot_start = current_slot_end; continue
            is_busy = any(current_slot_start < datetime.datetime.fromisoformat(busy['end']).astimezone(tz) and \
                          current_slot_end > datetime.datetime.fromisoformat(busy['start']).astimezone(tz) \
                          for busy in busy_intervals)
            if not is_busy: available_slots.append(current_slot_start.strftime("%H:%M"))
            current_slot_start = current_slot_end
        logger.info(f"Horarios disponibles {doctor_name} {date_obj.isoformat()}: {available_slots}")
    except HttpError as error: logger.error(f"Error API GCal (freeBusy) Dr {doctor_name}: {error}")
    except Exception as e: logger.error(f"Error check_avail Dr {doctor_name}: {e}", exc_info=True)
    return available_slots

def create_google_calendar_event(service, doctor_name: str, day_str: str, time_str: str, user_info: dict) -> tuple[bool, str | None]:
    if not service or doctor_name not in config.CALENDAR_IDS_DOCTORES: logger.error(f"create_event: Args inválidos"); return False, None
    calendar_id = config.CALENDAR_IDS_DOCTORES[doctor_name]
    user_name = user_info.get('username') or user_info.get('first_name','Paciente Tel'); user_id = user_info.get('id', 'N/A')
    logger.info(f"Creando evento GCal: Dr:{doctor_name}, Día:{day_str}, Hora:{time_str}, Paciente:{user_name}(ID:{user_id}) en Cal:{calendar_id}")
    target_date = get_next_weekday_date(day_str)
    if not target_date: logger.error(f"No fecha para '{day_str}'"); return False, None
    start_rfc, end_rfc = format_rfc3339(target_date, time_str, config.TIMEZONE)
    if not start_rfc or not end_rfc: logger.error(f"No formato RFC3339: {target_date} {time_str}"); return False, None
    event_body = {
        'summary': f"Turno {user_name} con {doctor_name}",
        'description': f"Solicitado vía Bot Telegram.\nUsuario: @{user_info.get('username', 'N/A')}\nID Chat: {user_id}", # Guardar ID Chat!
        'start': {'dateTime': start_rfc, 'timeZone': config.TIMEZONE}, 'end': {'dateTime': end_rfc, 'timeZone': config.TIMEZONE},
        'reminders': { 'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 60},{'method': 'popup', 'minutes': 1440},],},
    }
    try:
        created_event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        event_link = created_event.get('htmlLink')
        logger.info(f"Evento creado OK GCal Dr.{doctor_name}. ID: {created_event.get('id')}, Link: {event_link}")
        return True, event_link
    except HttpError as error: logger.error(f"Error API GCal (insert) Dr.{doctor_name}: {error}"); return False, None
    except Exception as e: logger.error(f"Error creando evento GCal Dr.{doctor_name}: {e}", exc_info=True); return False, None

def find_google_calendar_events(service, doctor_name: str, date_obj: datetime.date, user_info: dict) -> list:
    if not service or not date_obj or doctor_name not in config.CALENDAR_IDS_DOCTORES: logger.error(f"find_events: Args inválidos"); return []
    calendar_id = config.CALENDAR_IDS_DOCTORES[doctor_name]; user_id = user_info.get('id', None)
    if not user_id: logger.error("find_events: No user_id"); return []
    logger.info(f"Buscando eventos REALES GCal Dr:{doctor_name} en {date_obj.isoformat()} (Cal:{calendar_id}) para UserID:{user_id}")
    events_found_formatted = []
    try:
        tz = pytz.timezone(config.TIMEZONE)
        time_min = tz.localize(datetime.datetime.combine(date_obj, datetime.time(0, 0))).isoformat()
        time_max = tz.localize(datetime.datetime.combine(date_obj, datetime.time(23, 59, 59))).isoformat()
        search_query = f"ID Chat: {user_id}"
        events_result = service.events().list(
            calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
            q=search_query, singleEvents=True, orderBy='startTime'
        ).execute()
        items = events_result.get('items', [])
        logger.info(f"API encontró {len(items)} eventos potenciales UserID {user_id} en {date_obj.isoformat()}.")
        for event in items:
            if f"ID Chat: {user_id}" in event.get('description', ''):
                start_time_str = event['start'].get('dateTime')
                if start_time_str:
                    try: formatted_start_time = datetime.datetime.fromisoformat(start_time_str).astimezone(tz).strftime('%H:%M')
                    except ValueError: formatted_start_time = "??:??"
                else: continue
                events_found_formatted.append({'summary': event.get('summary','Evento'), 'start_time': formatted_start_time, 'id': event.get('id')})
        logger.info(f"Eventos filtrados/formateados: {events_found_formatted}")
    except HttpError as error: logger.error(f"Error API GCal (list events) Dr {doctor_name}: {error}")
    except Exception as e: logger.error(f"Error find_events Dr {doctor_name}: {e}", exc_info=True)
    return events_found_formatted

def delete_google_calendar_event(service, doctor_name: str, event_id: str) -> bool:
    if not service or doctor_name not in config.CALENDAR_IDS_DOCTORES or not event_id: logger.error(f"delete_event: Args inválidos"); return False
    calendar_id = config.CALENDAR_IDS_DOCTORES[doctor_name]
    logger.info(f"Intentando eliminar evento real ID: {event_id} de Cal: {calendar_id}")
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        logger.info(f"Evento ID: {event_id} eliminado OK de Cal: {calendar_id}")
        return True
    except HttpError as error:
        if error.resp.status in [404, 410]: logger.warning(f"Error 404/410 al eliminar {event_id}. OK."); return True
        logger.error(f"Error API GCal (delete event) ID {event_id}: {error}"); return False
    except Exception as e: logger.error(f"Error delete_event ID {event_id}: {e}", exc_info=True); return False
