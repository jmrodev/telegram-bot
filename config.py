# config.py
import os

# --- Configuración Telegram ---
# ¡¡¡IMPORTANTE!!! Reemplaza con tu token real de BotFather
TELEGRAM_TOKEN = '8085015867:AAEeEJg702mgx0kxfsG303LIqf5HOgRsOaI' # Reemplaza con tu token real

# --- Configuración Google Calendar ---
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = "America/Argentina/Buenos_Aires" # Ajusta si es necesario

# Mapeo Doctor -> ID de Calendario (Usa tus IDs reales)
CALENDAR_IDS_DOCTORES = {
   "Dr. Pérez": "ID_CALENDARIO_PEREZ@group.calendar.google.com",
   "Dra. Gómez": "ID_CALENDARIO_GOMEZ@group.calendar.google.com",
   "Dr. Rodríguez": "chello1975@gmail.com" # ID principal para Dr. Rodríguez
}
# Crear mapeo inverso para buscar doctor por ID (útil para mostrar nombre)
DOCTOR_NAMES_FROM_ID = {v: k for k, v in CALENDAR_IDS_DOCTORES.items()}


# --- Datos Configurables del Bot ---
DOCTOR_LIST = list(CALENDAR_IDS_DOCTORES.keys())
DAY_LIST = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

# Textos de botones ReplyKeyboard
BTN_TURNO = "📅 Turno"; BTN_RECETA = "℞ Receta"; BTN_PAGO = "💲 Pago"
BTN_TURNO_SOLICITAR = "➕ Solicitar Turno"; BTN_TURNO_ELIMINAR = "🗑️ Cancelar Turno" # Texto actualizado
BTN_TURNO_EDITAR = "✏️ Editar Turno Existente"; BTN_TURNO_VIDEO = "📹 Videollamada"
BTN_TURNO_DOCTOR = "👨‍⚕️ ¿Con qué doctor?"; BTN_TURNO_SECRETARIA = "🧑‍💼 Comunicarse con Secretaría"
BTN_RECETA_SOLICITAR = "💊 Solicitar Nueva"; BTN_RECETA_CORREGIR = "✍️ Corregir Existente"
BTN_PAGO_TRANFERENCIA = "🏦 Transferencia"; BTN_PAGO_CONSULTORIO = "🏢 En Consultorio"
BTN_VOLVER = "🔙 Volver al Menú Principal"; BTN_CANCELAR_ACCION = "🚫 Cancelar Acción Actual"

# --- Callback Data Prefijos (NUEVO) ---
CALLBACK_PREFIX_CANCEL = "cancel_" # Prefijo para botones de cancelación

# --- Estados de Conversación ---
STATE_WAITING_DOCTOR = 'turno_awaiting_doctor'
STATE_WAITING_DAY = 'turno_awaiting_day'
STATE_WAITING_TIMESLOT = 'turno_awaiting_timeslot'
# Ya no necesitamos estados específicos para la cancelación por pasos
# STATE_DELETE_AWAITING_DATE = 'delete_awaiting_date' # ELIMINADO O COMENTADO
# STATE_DELETE_AWAITING_DOCTOR = 'delete_awaiting_doctor' # ELIMINADO O COMENTADO
# STATE_DELETE_AWAITING_CONFIRMATION = 'delete_awaiting_confirmation' # ELIMINADO O COMENTADO
STATE_EDIT_AWAITING_DATE = 'edit_awaiting_date' # Placeholder
STATE_RECIPE_AWAITING_INFO = 'receta_awaiting_info_or_photo'
STATE_RECIPE_AWAITING_CORRECTION = 'receta_awaiting_correction_info_photo'
STATE_TALKING_TO_SECRETARY = 'talking_to_secretary'


# --- Otros ---
OFFICE_START_HOUR = 9; OFFICE_END_HOUR = 18; SLOT_DURATION_MINUTES = 30
SECRETARY_CHAT_ID = None # !!! Reemplazar con el ID de chat real de la secretaría !!!
# Añadir estas si no las tienes (ejemplo)
OFFICE_ADDRESS = "Calle Falsa 123, Tandil"
OFFICE_HOURS = "Lunes a Viernes de 9:00 a 18:00"

# Límite de botones a mostrar para cancelación (evita teclados enormes)
MAX_CANCEL_BUTTONS = 15