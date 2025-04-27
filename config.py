# config.py
import os

# --- Configuración Telegram ---
# ¡¡¡IMPORTANTE!!! Reemplaza con tu token real de BotFather
TELEGRAM_TOKEN = '8085015867:AAEeEJg702mgx0kxfsG303LIqf5HOgRsOaI'

# --- Configuración Google Calendar ---
# Asumiendo que 'credentials.json' está en la misma carpeta que main.py
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = "America/Argentina/Buenos_Aires" # ¡Ajusta si es necesario!

# Mapeo Doctor -> ID de Calendario
# !!! Reemplaza con los IDs reales !!!
CALENDAR_IDS_DOCTORES = {
   "Dr. Pérez": "ID_CALENDARIO_PEREZ@group.calendar.google.com",
   "Dra. Gómez": "ID_CALENDARIO_GOMEZ@group.calendar.google.com",
   "Dr. Rodríguez": "chello1975@gmail.com" # ID principal para Dr. Rodríguez
}

# --- Datos Configurables del Bot ---
DOCTOR_LIST = list(CALENDAR_IDS_DOCTORES.keys())
DAY_LIST = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

# Textos de botones
BTN_TURNO = "📅 Turno"; BTN_RECETA = "℞ Receta"; BTN_PAGO = "💲 Pago"
BTN_TURNO_SOLICITAR = "➕ Solicitar Turno"; BTN_TURNO_ELIMINAR = "🗑️ Cancelar Turno Existente"
BTN_TURNO_EDITAR = "✏️ Editar Turno Existente"; BTN_TURNO_VIDEO = "📹 Videollamada"
BTN_TURNO_DOCTOR = "👨‍⚕️ ¿Con qué doctor?"; BTN_TURNO_SECRETARIA = "🧑‍💼 Comunicarse con Secretaría"
BTN_RECETA_SOLICITAR = "💊 Solicitar Nueva"; BTN_RECETA_CORREGIR = "✍️ Corregir Existente"
BTN_PAGO_TRANFERENCIA = "🏦 Transferencia"; BTN_PAGO_CONSULTORIO = "🏢 En Consultorio"
BTN_VOLVER = "🔙 Volver al Menú Principal"; BTN_CANCELAR_ACCION = "🚫 Cancelar Acción Actual"

# --- Estados de Conversación (usados como claves en context.user_data['state']) ---
STATE_WAITING_DOCTOR = 'turno_awaiting_doctor'
STATE_WAITING_DAY = 'turno_awaiting_day'
STATE_WAITING_TIMESLOT = 'turno_awaiting_timeslot'
STATE_DELETE_AWAITING_DATE = 'delete_awaiting_date'
STATE_DELETE_AWAITING_DOCTOR = 'delete_awaiting_doctor'
STATE_DELETE_AWAITING_CONFIRMATION = 'delete_awaiting_confirmation'
STATE_EDIT_AWAITING_DATE = 'edit_awaiting_date' # Placeholder
STATE_RECIPE_AWAITING_INFO = 'receta_awaiting_info_or_photo'
STATE_RECIPE_AWAITING_CORRECTION = 'receta_awaiting_correction_info_photo'
STATE_TALKING_TO_SECRETARY = 'talking_to_secretary'

# --- Otros ---
OFFICE_START_HOUR = 9; OFFICE_END_HOUR = 18; SLOT_DURATION_MINUTES = 30
SECRETARY_CHAT_ID = None # !!! Reemplazar con el ID de chat real de la secretaría !!!
