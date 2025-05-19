# keyboards.py
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import config # Importar constantes de botones y prefijos

# Teclados Fijos (ReplyKeyboardMarkup)
main_menu_markup = ReplyKeyboardMarkup(
    [[KeyboardButton(config.BTN_TURNO)],
     [KeyboardButton(config.BTN_RECETA), KeyboardButton(config.BTN_PAGO)],],
    resize_keyboard=True
)
turno_menu_markup = ReplyKeyboardMarkup(
    [[KeyboardButton(config.BTN_TURNO_SOLICITAR)],
     [KeyboardButton(config.BTN_TURNO_ELIMINAR), KeyboardButton(config.BTN_TURNO_EDITAR)],
     [KeyboardButton(config.BTN_TURNO_VIDEO), KeyboardButton(config.BTN_TURNO_DOCTOR)],
     [KeyboardButton(config.BTN_TURNO_SECRETARIA)],
     [KeyboardButton(config.BTN_VOLVER)],],
    resize_keyboard=True
)
receta_menu_markup = ReplyKeyboardMarkup(
    [[KeyboardButton(config.BTN_RECETA_SOLICITAR)],
     [KeyboardButton(config.BTN_RECETA_CORREGIR)],
     [KeyboardButton(config.BTN_VOLVER)],],
    resize_keyboard=True
)
pago_menu_markup = ReplyKeyboardMarkup(
    [[KeyboardButton(config.BTN_PAGO_TRANFERENCIA)],
     [KeyboardButton(config.BTN_PAGO_CONSULTORIO)],
     [KeyboardButton(config.BTN_VOLVER)],],
    resize_keyboard=True
)
# Teclado simple para cancelar acción (usado en flujos con estado)
cancel_markup = ReplyKeyboardMarkup(
    [[KeyboardButton(config.BTN_CANCELAR_ACCION)]],
    resize_keyboard=True,
    one_time_keyboard=True # Opcional: oculta teclado después de usar
)

# Funciones para Teclados Dinámicos (ReplyKeyboardMarkup)
def create_doctor_keyboard():
    keys = [[KeyboardButton(doc)] for doc in config.DOCTOR_LIST] + [[KeyboardButton(config.BTN_CANCELAR_ACCION)]]
    return ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)

def create_day_keyboard():
    keys = [[KeyboardButton(day)] for day in config.DAY_LIST] + [[KeyboardButton(config.BTN_CANCELAR_ACCION)]]
    return ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)

def create_timeslot_keyboard(slots: list):
    if not slots:
        return cancel_markup # Si no hay slots, solo mostrar cancelar
    keys = [[KeyboardButton(slot)] for slot in slots] + [[KeyboardButton(config.BTN_CANCELAR_ACCION)]]
    return ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)


# --- NUEVA Función para Teclado Inline de Cancelación ---
def create_cancel_appointments_keyboard(appointments: list) -> InlineKeyboardMarkup | None:
    """Crea un InlineKeyboardMarkup con botones para cancelar turnos específicos."""
    if not appointments:
        return None # No crear teclado si no hay turnos

    keyboard = []
    for appt in appointments:
        event_id = appt.get('event_id')
        calendar_id = appt.get('calendar_id')
        doctor_name = appt.get('doctor_name', 'Dr.?')
        display_time = appt.get('display_datetime', 'Fecha?')

        if not event_id or not calendar_id:
            continue # Saltar si falta información esencial

        # Crear el texto del botón
        button_text = f"🚫 {doctor_name} - {display_time}"

        # Crear el callback_data: prefijo_eventId_calendarId
        # Es importante que el callback_data no sea demasiado largo.
        # Usaremos la clave del doctor (ej: "Dr. Rodriguez") en lugar del ID de calendario completo si es posible.
        doctor_key = config.DOCTOR_NAMES_FROM_ID.get(calendar_id)
        if not doctor_key: # Fallback si el ID no está en el mapeo (raro)
            callback_data = None # O manejar error
            # Alternativa: Hashear calendar_id si es muy largo o contiene caracteres inválidos
            # import hashlib
            # cal_hash = hashlib.md5(calendar_id.encode()).hexdigest()[:8] # Hash corto
            # callback_data = f"{config.CALLBACK_PREFIX_CANCEL}{event_id}_{cal_hash}"
        else:
             callback_data = f"{config.CALLBACK_PREFIX_CANCEL}{event_id}_{doctor_key}"


        # Comprobar longitud del callback_data (límite Telegram ~64 bytes)
        if callback_data and len(callback_data.encode('utf-8')) <= 64:
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        else:
             logging.warning(f"Callback data demasiado largo o inválido, omitiendo botón: {callback_data}")


    # Añadir botón para cancelar la selección (opcional)
    # keyboard.append([InlineKeyboardButton("No cancelar ninguno", callback_data="cancel_abort")])

    if not keyboard: # Si ningún botón fue válido
        return None

    return InlineKeyboardMarkup(keyboard)