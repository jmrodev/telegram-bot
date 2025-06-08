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
     [KeyboardButton(config.BTN_RECETA_CONSULTAR_ESTADO)], # New button
     [KeyboardButton(config.BTN_VOLVER)],],
    resize_keyboard=True
)
pago_menu_markup = ReplyKeyboardMarkup(
    [[KeyboardButton(config.BTN_PAGO_ONLINE_INFO)],
     [KeyboardButton(config.BTN_PAGO_TRANFERENCIA)],
     [KeyboardButton(config.BTN_PAGO_CONSULTORIO)],
     [KeyboardButton(config.BTN_PAGO_RECORDATORIO_INFO)], # New button
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


# --- Función para Teclado Inline de Gestión de Turnos (Cancelar/Editar) ---
def create_appointments_inline_keyboard(appointments: list, button_text_prefix: str, callback_prefix: str) -> InlineKeyboardMarkup | None:
    """
    Crea un InlineKeyboardMarkup con botones para acciones en turnos específicos (ej. cancelar, editar).
    Args:
        appointments: Lista de diccionarios, cada uno representando un turno.
        button_text_prefix: Prefijo para el texto del botón (ej. "🚫 Cancelar", "✏️ Editar").
        callback_prefix: Prefijo para el callback_data (ej. config.CALLBACK_PREFIX_CANCEL).
    """
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
        button_text = f"{button_text_prefix} {doctor_name} - {display_time}"

        # Crear el callback_data: callback_prefix_eventId_doctorKey
        # Usaremos la clave del doctor (ej: "Dr. Rodriguez") en lugar del ID de calendario completo.
        doctor_key = None
        for key, value in config.CALENDAR_IDS_DOCTORES.items(): # Iterate to find key by calendar_id
            if value == calendar_id:
                doctor_key = key
                break

        if not doctor_key:
            # Fallback si el ID no está en el mapeo (raro, indicaría inconsistencia en config o datos de GCal)
            # O si se usa un calendar_id que no es de un doctor específico (ej. calendario general).
            # Intentar usar el doctor_name si está disponible y es una clave válida, sino omitir.
            if doctor_name in config.CALENDAR_IDS_DOCTORES: # Check if doctor_name itself is a valid key
                 doctor_key = doctor_name
            else:
                logging.warning(f"No se pudo determinar doctor_key para calendar_id '{calendar_id}' (doctor: {doctor_name}). Omitiendo botón.")
                continue # Saltar este turno

        callback_data = f"{callback_prefix}{event_id}_{doctor_key}"

        # Comprobar longitud del callback_data (límite Telegram ~64 bytes)
        if len(callback_data.encode('utf-8')) <= 64:
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        else:
            logging.warning(f"Callback data demasiado largo para el botón (omitido): {callback_data}")


    # Añadir botón para cancelar la selección (opcional)
    # keyboard.append([InlineKeyboardButton("No cancelar ninguno", callback_data="cancel_abort")])

    if not keyboard: # Si ningún botón fue válido
        return None

    return InlineKeyboardMarkup(keyboard)


def create_edit_confirmation_keyboard(event_id: str, doctor_key: str, callback_proceed_prefix: str, callback_abort_prefix: str) -> InlineKeyboardMarkup:
    """
    Crea un InlineKeyboardMarkup para confirmar o cancelar la edición de un turno.
    Args:
        event_id: El ID del evento a editar.
        doctor_key: La clave del doctor (para reconstruir callback o identificar).
        callback_proceed_prefix: El prefijo para el callback_data de confirmar.
        callback_abort_prefix: El prefijo para el callback_data de abortar/cancelar.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar Edición", callback_data=f"{callback_proceed_prefix}{event_id}_{doctor_key}"),
            InlineKeyboardButton("❌ Cancelar Edición", callback_data=f"{callback_abort_prefix}{event_id}_{doctor_key}")
            # Consider if event_id and doctor_key are needed for abort, or if a generic "abort_edit_process" is better.
            # For now, keeping them for consistency or potential logging on abort.
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_finalize_edit_keyboard(callback_finalize_prefix: str, callback_cancel_finalize_prefix: str, placeholder_data: str = "confirm") -> InlineKeyboardMarkup:
    """
    Crea un InlineKeyboardMarkup para la confirmación final antes de reagendar.
    Args:
        callback_finalize_prefix: Prefijo para el callback_data de finalizar/confirmar.
        callback_cancel_finalize_prefix: Prefijo para el callback_data de cancelar esta operación final.
        placeholder_data: Datos placeholder para el callback, ya que los detalles se tomarán de user_data.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar y Reagendar", callback_data=f"{callback_finalize_prefix}{placeholder_data}"),
            InlineKeyboardButton("❌ Cancelar Operación", callback_data=f"{callback_cancel_finalize_prefix}{placeholder_data}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)