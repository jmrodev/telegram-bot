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
TIMEZONE_OBJ = pytz.timezone(config.TIMEZONE) # Crear objeto timezone una vez

# --- Funciones Auxiliares para Fechas ---
def get_next_weekday_date(day_name: str) -> datetime.date | None:
    """Calcula la fecha del próximo día de la semana especificado."""
    today = datetime.date.today()
    # Mapeo robusto para evitar errores de capitalización
    day_mapping = {
        "lunes": MO, "martes": TU, "miércoles": WE, "miercoles": WE,
        "jueves": TH, "viernes": FR, "sábado": SA, "sabado": SA, "domingo": SU
    }
    weekday_const = day_mapping.get(day_name.lower()) # Usar lower()
    if weekday_const is None:
        logger.warning(f"Día inválido recibido: {day_name}")
        return None
    try:
        # Obtener la próxima ocurrencia de ese día de la semana, incluyeno hoy si coincide
        next_date = today + relativedelta(weekday=weekday_const(+1))
        logger.info(f"Calculada fecha para próximo '{day_name.capitalize()}': {next_date.isoformat()}")
        return next_date
    except Exception as e:
        logger.error(f"Error calculando fecha para {day_name}: {e}")
        return None

def format_rfc3339(date_obj: datetime.date, time_str: str, timezone_str: str = config.TIMEZONE) -> tuple[str | None, str | None]:
    """Formatea fecha y hora a strings RFC3339 para inicio y fin de evento."""
    try:
        time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
        tz = pytz.timezone(timezone_str) # Considerar usar TIMEZONE_OBJ global
        start_dt = tz.localize(datetime.datetime.combine(date_obj, time_obj))
        # Calcular fin basado en la duración configurada
        end_dt = start_dt + datetime.timedelta(minutes=config.SLOT_DURATION_MINUTES)
        start_rfc = start_dt.isoformat()
        end_rfc = end_dt.isoformat()
        logger.debug(f"Formateado RFC3339: Inicio={start_rfc}, Fin={end_rfc}")
        return start_rfc, end_rfc
    except Exception as e:
        logger.error(f"Error en format_rfc3339({date_obj}, {time_str}): {e}")
        return None, None

# --- Funciones Principales de Google Calendar ---
def get_calendar_service():
    """Autentica y devuelve el objeto de servicio de Google Calendar."""
    creds = None
    try:
        if not os.path.exists(config.SERVICE_ACCOUNT_FILE):
             logger.critical(f"ERROR: Archivo credenciales '{config.SERVICE_ACCOUNT_FILE}' NO encontrado.")
             return None
        # Usar las SCOPES definidas en config
        creds = Credentials.from_service_account_file(config.SERVICE_ACCOUNT_FILE, scopes=config.SCOPES)
        service = build('calendar', 'v3', credentials=creds)
        logger.info("Servicio Google Calendar autenticado OK.")
        return service
    except Exception as e:
        logger.critical(f"ERROR CRÍTICO autenticando GCal: {e}", exc_info=True)
        return None

def check_google_calendar_availability(service, doctor_name: str, date_obj: datetime.date) -> list:
    """Verifica los horarios disponibles para un doctor en una fecha específica."""
    if not service or not date_obj or doctor_name not in config.CALENDAR_IDS_DOCTORES:
        logger.error(f"check_avail: Args inválidos (service: {bool(service)}, date: {date_obj}, doctor: {doctor_name})")
        return []

    calendar_id = config.CALENDAR_IDS_DOCTORES[doctor_name]
    logger.info(f"Consultando disponibilidad GCal Dr:{doctor_name} (Cal:{calendar_id}) en {date_obj.isoformat()}")
    available_slots = []
    try:
        tz = TIMEZONE_OBJ # Usar objeto global
        # Definir inicio y fin del día laboral en la zona horaria correcta
        day_start = tz.localize(datetime.datetime.combine(date_obj, datetime.time(config.OFFICE_START_HOUR, 0)))
        day_end = tz.localize(datetime.datetime.combine(date_obj, datetime.time(config.OFFICE_END_HOUR, 0)))
        time_min = day_start.isoformat()
        time_max = day_end.isoformat()

        # Consultar free/busy API
        body = {"timeMin": time_min, "timeMax": time_max, "timeZone": config.TIMEZONE, "items": [{"id": calendar_id}]}
        results = service.freebusy().query(body=body).execute()
        busy_intervals = results.get('calendars', {}).get(calendar_id, {}).get('busy', [])
        logger.debug(f"Intervalos ocupados para {doctor_name} en {date_obj.isoformat()}: {busy_intervals}")

        # Generar slots potenciales y verificar contra intervalos ocupados y hora actual
        now_local = datetime.datetime.now(tz)
        current_slot_start = day_start
        while current_slot_start < day_end:
            current_slot_end = current_slot_start + datetime.timedelta(minutes=config.SLOT_DURATION_MINUTES)
            # Asegurar que el slot no termine después del fin del día laboral
            if current_slot_end > day_end:
                break
            # Saltar slots que ya terminaron
            if current_slot_end <= now_local:
                current_slot_start = current_slot_end
                continue

            # Verificar si el slot actual se superpone con algún intervalo ocupado
            is_busy = False
            for busy in busy_intervals:
                try:
                    busy_start = datetime.datetime.fromisoformat(busy['start']).astimezone(tz)
                    busy_end = datetime.datetime.fromisoformat(busy['end']).astimezone(tz)
                    # Lógica de superposición: (StartA < EndB) and (EndA > StartB)
                    if current_slot_start < busy_end and current_slot_end > busy_start:
                        is_busy = True
                        break # No necesitamos verificar más intervalos para este slot
                except ValueError:
                     logger.warning(f"Error parseando intervalo busy: Start={busy.get('start')}, End={busy.get('end')}")
                     # Considerar este slot como ocupado por precaución si hay error
                     is_busy = True
                     break

            if not is_busy:
                available_slots.append(current_slot_start.strftime("%H:%M"))

            current_slot_start = current_slot_end # Avanzar al siguiente slot

        logger.info(f"Horarios disponibles calculados para {doctor_name} el {date_obj.isoformat()}: {available_slots}")

    except HttpError as error:
        logger.error(f"Error API GCal (freeBusy) para Dr:{doctor_name}: {error}")
    except Exception as e:
        logger.error(f"Error inesperado en check_avail para Dr:{doctor_name}: {e}", exc_info=True)

    return available_slots


def create_google_calendar_event(service, doctor_name: str, day_str: str, time_str: str, user_info: dict) -> tuple[bool, str | None]:
    """Crea un nuevo evento de turno en el calendario del doctor."""
    if not service or doctor_name not in config.CALENDAR_IDS_DOCTORES or not day_str or not time_str or not user_info:
        logger.error(f"create_event: Args inválidos.")
        return False, None

    calendar_id = config.CALENDAR_IDS_DOCTORES[doctor_name]
    # Extraer datos del usuario de forma segura
    user_name = user_info.get('first_name', 'Paciente') # Usar first_name como fallback más común
    user_username = user_info.get('username')
    user_id = user_info.get('id')
    if not user_id: logger.error("create_event: Falta user ID."); return False, None

    display_name = f"@{user_username}" if user_username else user_name

    logger.info(f"Intentando crear evento GCal: Dr:{doctor_name}, Día:{day_str}, Hora:{time_str}, Paciente:{display_name}(ID:{user_id}) en Cal:{calendar_id}")

    target_date = get_next_weekday_date(day_str)
    if not target_date:
        logger.error(f"No se pudo calcular fecha para día '{day_str}'")
        return False, None

    start_rfc, end_rfc = format_rfc3339(target_date, time_str)
    if not start_rfc or not end_rfc:
        logger.error(f"No se pudo formatear RFC3339 para fecha {target_date}, hora {time_str}")
        return False, None

    # Construir descripción detallada
    description = (
        f"Turno solicitado vía Bot Telegram.\n"
        f"Paciente: {user_name}\n"
        f"Usuario: @{user_username or 'N/A'}\n"
        f"ID Chat: {user_id}\n" # Esencial para búsquedas futuras
        f"Doctor: {doctor_name}\n"
        f"Fecha Solicitud: {datetime.datetime.now(TIMEZONE_OBJ).strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
    )

    event_body = {
        'summary': f"Turno {user_name} con {doctor_name}",
        'description': description,
        'start': {'dateTime': start_rfc, 'timeZone': config.TIMEZONE},
        'end': {'dateTime': end_rfc, 'timeZone': config.TIMEZONE},
        # Añadir participantes (opcional, requiere permisos)
        # 'attendees': [
        #     {'email': calendar_id, 'responseStatus': 'accepted'}, # El calendario del doctor
        #     # Podríamos intentar añadir al paciente si tuviéramos su email, pero no es fiable
        # ],
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 60}, # Recordatorio 1 hora antes
                {'method': 'popup', 'minutes': 1440}, # Recordatorio 1 día antes (24*60)
            ],
        },
        # Añadir un color distintivo (opcional) - IDs de color de GCal: 1-11
        # 'colorId': '5' # Ejemplo: Amarillo
    }

    try:
        created_event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        event_link = created_event.get('htmlLink')
        event_id_created = created_event.get('id')
        logger.info(f"Evento creado OK en GCal para Dr.{doctor_name}. ID: {event_id_created}, Link: {event_link}")
        return True, event_link
    except HttpError as error:
        logger.error(f"Error API GCal (insert) al crear evento para Dr.{doctor_name}: {error}")
        return False, None
    except Exception as e:
        logger.error(f"Error inesperado creando evento GCal para Dr.{doctor_name}: {e}", exc_info=True)
        return False, None

def find_google_calendar_events(service, calendar_id: str, date_obj: datetime.date, user_info: dict) -> list:
    """Busca eventos en un calendario/fecha específicos para un usuario."""
    # (Sin cambios respecto a la versión anterior)
    if not service or not date_obj or not calendar_id: logger.error(f"find_events: Args inválidos"); return []
    user_id = user_info.get('id', None);
    if not user_id: logger.error("find_events: No user_id"); return []
    doctor_name = config.DOCTOR_NAMES_FROM_ID.get(calendar_id, "Desconocido")
    logger.info(f"Buscando eventos GCal Dr:{doctor_name} en {date_obj.isoformat()} (Cal:{calendar_id}) para UserID:{user_id}")
    events_found_formatted = []
    try:
        tz = TIMEZONE_OBJ
        time_min = tz.localize(datetime.datetime.combine(date_obj, datetime.time(0, 0))).isoformat()
        time_max = tz.localize(datetime.datetime.combine(date_obj, datetime.time(23, 59, 59))).isoformat()
        search_query = f"ID Chat: {user_id}"
        events_result = service.events().list(
            calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
            q=search_query, singleEvents=True, orderBy='startTime'
        ).execute()
        items = events_result.get('items', [])
        logger.info(f"API encontró {len(items)} eventos pot. UserID {user_id} en {date_obj.isoformat()} Cal:{calendar_id}.")
        for event in items:
            if f"ID Chat: {user_id}" in event.get('description', '') and 'start' in event and 'dateTime' in event['start']:
                start_time_str = event['start']['dateTime']
                try:
                    start_dt_local = datetime.datetime.fromisoformat(start_time_str).astimezone(tz)
                    formatted_start_time = start_dt_local.strftime('%H:%M')
                    formatted_date = start_dt_local.strftime('%Y-%m-%d')
                except ValueError: logger.warning(f"Error parseando fecha GCal: {start_time_str}"); continue
                events_found_formatted.append({
                    'summary': event.get('summary','Evento'), 'start_time': formatted_start_time,
                    'date': formatted_date, 'id': event.get('id'),
                    'calendar_id': calendar_id, 'doctor_name': doctor_name })
        logger.info(f"Eventos filtrados/formateados Cal:{calendar_id} en {date_obj.isoformat()}: {events_found_formatted}")
    except HttpError as error: logger.error(f"Error API GCal (list events) Cal:{calendar_id}: {error}")
    except Exception as e: logger.error(f"Error find_events Cal:{calendar_id}: {e}", exc_info=True)
    return events_found_formatted

def find_all_user_appointments(service, user_info: dict) -> list:
    """Busca todos los eventos futuros de un usuario en TODOS los calendarios."""
    # (Sin cambios respecto a la versión anterior)
    if not service: logger.error("find_all_user_appointments: No service"); return []
    user_id = user_info.get('id');
    if not user_id: logger.error("find_all_user_appointments: No user_id"); return []
    logger.info(f"Buscando TODOS los turnos futuros UserID:{user_id} en todos los cals.")
    all_found_events = []
    now_utc = datetime.datetime.now(pytz.utc)
    for doctor_key, calendar_id in config.CALENDAR_IDS_DOCTORES.items():
        try:
            search_query = f"ID Chat: {user_id}"
            logger.debug(f"Consultando Cal: {calendar_id} ({doctor_key}) UserID: {user_id}")
            events_result = service.events().list(
                calendarId=calendar_id, timeMin=now_utc.isoformat(), q=search_query,
                singleEvents=True, orderBy='startTime', maxResults=50 ).execute()
            items = events_result.get('items', [])
            logger.info(f"API encontró {len(items)} eventos pot. futuros UserID {user_id} en Cal:{calendar_id}.")
            for event in items:
                if f"ID Chat: {user_id}" in event.get('description', '') and 'start' in event and 'dateTime' in event['start']:
                    start_time_str = event['start']['dateTime']
                    try:
                        start_dt_local = datetime.datetime.fromisoformat(start_time_str).astimezone(TIMEZONE_OBJ)
                        # Formato localizado para mostrar al usuario
                        formatted_datetime_str = start_dt_local.strftime('%a %d/%m %H:%M') # Ej: Lun 28/04 09:30
                    except ValueError: logger.warning(f"Error parseando fecha GCal: {start_time_str}"); continue
                    # Extraer nombre del doctor de la descripción o usar mapeo
                    event_doctor = "Desconocido"
                    desc_lines = event.get('description', '').split('\n')
                    for line in desc_lines:
                        if line.startswith("Doctor:"): event_doctor = line.split(":", 1)[1].strip(); break
                    if event_doctor == "Desconocido": event_doctor = config.DOCTOR_NAMES_FROM_ID.get(calendar_id, doctor_key)

                    all_found_events.append({
                        'summary': event.get('summary','Evento'), 'event_id': event.get('id'),
                        'calendar_id': calendar_id, 'doctor_name': event_doctor,
                        'start_datetime': start_dt_local, # Objeto datetime para ordenar
                        'display_datetime': formatted_datetime_str # String para mostrar
                    })
            logger.debug(f"Eventos en Cal {calendar_id}: {len(items)}")
        except HttpError as error:
             # Ignorar errores 404 de calendarios no encontrados/accesibles
             if error.resp.status == 404: logger.warning(f"Calendario {calendar_id} no encontrado (404) al buscar todos los turnos."); continue
             logger.error(f"Error API GCal (list futuros) Cal:{calendar_id}: {error}")
        except Exception as e: logger.error(f"Error buscando en Cal:{calendar_id}: {e}", exc_info=True)
    all_found_events.sort(key=lambda x: x['start_datetime'])
    logger.info(f"Total turnos futuros UserID:{user_id}: {len(all_found_events)}")
    # Aplicar límite definido en config
    return all_found_events[:config.MAX_CANCEL_BUTTONS]


# --- MODIFICADA para devolver detalles ---
def check_existing_appointment(service, doctor_name: str, user_info: dict) -> tuple[bool, str | None]:
    """
    Verifica si un usuario ya tiene un turno futuro con un doctor específico.
    Devuelve: (True, "el [Día] [dd]/[mm] a las HH:MM") si existe, (False, None) si no.
    """
    appointment_details_str = None # Inicializar
    if not service or doctor_name not in config.CALENDAR_IDS_DOCTORES:
        logger.error(f"check_existing: Args inválidos (service:{bool(service)}, doctor:{doctor_name})")
        return False, None
    user_id = user_info.get('id')
    if not user_id:
        logger.error("check_existing_appointment: No user_id")
        return False, None

    calendar_id = config.CALENDAR_IDS_DOCTORES[doctor_name]
    logger.info(f"Verificando turno futuro existente UserID:{user_id} Dr:{doctor_name} (Cal:{calendar_id})")
    now_utc = datetime.datetime.now(pytz.utc) # Hora actual en UTC para comparar

    try:
        search_query = f"ID Chat: {user_id}" # Buscar por ID en la descripción
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now_utc.isoformat(), # Buscar desde ahora hacia el futuro
            q=search_query,
            singleEvents=True,
            maxResults=5, # Optimización: solo necesitamos encontrar uno
            orderBy='startTime' # Tomar el más próximo si hay varios (raro por la regla)
        ).execute()
        items = events_result.get('items', [])

        # Iterar y verificar si el evento coincide y tiene fecha válida
        for event in items:
            if f"ID Chat: {user_id}" in event.get('description', '') and 'start' in event and 'dateTime' in event['start']:
                start_time_str = event['start']['dateTime']
                try:
                    start_dt_local = datetime.datetime.fromisoformat(start_time_str).astimezone(TIMEZONE_OBJ)
                    # Formato para mostrar al usuario (ajustar si se necesita locale español)
                    # locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8') # O es_AR, etc. - Requiere locale instalado en el sistema
                    appointment_details_str = start_dt_local.strftime("el %A %d/%m a las %H:%M") # Ej: el Lunes 28/04 a las 09:30
                    # Si prefieres formato corto:
                    # appointment_details_str = start_dt_local.strftime("el %a %d/%m %H:%M") # Ej: el Lun 28/04 09:30

                    logger.info(f"Turno futuro existente encontrado UserID:{user_id} Dr:{doctor_name}: {appointment_details_str}")
                    return True, appointment_details_str # Encontrado!

                except ValueError:
                    logger.warning(f"Error parseando fecha GCal: {start_time_str} al verificar turno existente.")
                    continue # Ignorar este evento e intentar con el siguiente si lo hubiera

        # Si el bucle termina sin encontrar un evento válido
        logger.info(f"No se encontraron turnos futuros para UserID:{user_id} con Dr:{doctor_name}.")
        return False, None

    except HttpError as error:
        if error.resp.status == 404:
             logger.warning(f"Calendario {calendar_id} no encontrado (404) al verificar Dr:{doctor_name}.")
        else:
             logger.error(f"Error API GCal (list check) Dr:{doctor_name}: {error}")
        return False, None # Asumir que no hay turno si el calendario no existe o hay error
    except Exception as e:
        logger.error(f"Error inesperado en check_existing_appointment Dr:{doctor_name}: {e}", exc_info=True)
        return False, None


def delete_google_calendar_event(service, calendar_id: str, event_id: str) -> bool:
    """Elimina un evento específico de un calendario específico."""
    # (Sin cambios respecto a la versión anterior)
    if not service or not calendar_id or not event_id:
        logger.error(f"delete_event: Args inválidos (service: {bool(service)}, cal_id: {calendar_id}, event_id: {event_id})")
        return False

    doctor_name = config.DOCTOR_NAMES_FROM_ID.get(calendar_id, "Desconocido") # Para logs
    logger.info(f"Intentando eliminar evento ID: {event_id} de Cal: {calendar_id} (Dr: {doctor_name})")
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        logger.info(f"Evento ID: {event_id} eliminado OK de Cal: {calendar_id}")
        return True
    except HttpError as error:
        # Si el evento ya no existe (404 o 410), consideramos la eliminación exitosa
        if error.resp.status in [404, 410]:
            logger.warning(f"Evento ID: {event_id} no encontrado (status {error.resp.status}) al intentar eliminar de Cal: {calendar_id}. Asumiendo OK.")
            return True
        logger.error(f"Error API GCal (delete event) ID {event_id} en Cal {calendar_id}: {error}")
        return False
    except Exception as e:
        logger.error(f"Error delete_event ID {event_id} en Cal {calendar_id}: {e}", exc_info=True)
        return False