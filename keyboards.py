# keyboards.py
from telegram import ReplyKeyboardMarkup, KeyboardButton
import config # Importar constantes de botones

# Teclados Fijos
main_menu_markup = ReplyKeyboardMarkup([[KeyboardButton(config.BTN_TURNO)], [KeyboardButton(config.BTN_RECETA), KeyboardButton(config.BTN_PAGO)],], resize_keyboard=True)
turno_menu_markup = ReplyKeyboardMarkup([[KeyboardButton(config.BTN_TURNO_SOLICITAR)], [KeyboardButton(config.BTN_TURNO_ELIMINAR), KeyboardButton(config.BTN_TURNO_EDITAR)], [KeyboardButton(config.BTN_TURNO_VIDEO), KeyboardButton(config.BTN_TURNO_DOCTOR)], [KeyboardButton(config.BTN_TURNO_SECRETARIA)], [KeyboardButton(config.BTN_VOLVER)],], resize_keyboard=True)
receta_menu_markup = ReplyKeyboardMarkup([[KeyboardButton(config.BTN_RECETA_SOLICITAR)], [KeyboardButton(config.BTN_RECETA_CORREGIR)], [KeyboardButton(config.BTN_VOLVER)],], resize_keyboard=True)
pago_menu_markup = ReplyKeyboardMarkup([[KeyboardButton(config.BTN_PAGO_TRANFERENCIA)], [KeyboardButton(config.BTN_PAGO_CONSULTORIO)], [KeyboardButton(config.BTN_VOLVER)],], resize_keyboard=True)
cancel_markup = ReplyKeyboardMarkup([[KeyboardButton(config.BTN_CANCELAR_ACCION)]], resize_keyboard=True, one_time_keyboard=True)

# Funciones para Teclados Dinámicos
def create_doctor_keyboard():
    keys = [[KeyboardButton(doc)] for doc in config.DOCTOR_LIST] + [[KeyboardButton(config.BTN_CANCELAR_ACCION)]]
    return ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)

def create_day_keyboard():
    keys = [[KeyboardButton(day)] for day in config.DAY_LIST] + [[KeyboardButton(config.BTN_CANCELAR_ACCION)]]
    return ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)

def create_timeslot_keyboard(slots: list):
    if not slots: return cancel_markup # Si no hay slots, solo mostrar cancelar
    keys = [[KeyboardButton(slot)] for slot in slots] + [[KeyboardButton(config.BTN_CANCELAR_ACCION)]]
    return ReplyKeyboardMarkup(keys, one_time_keyboard=True, resize_keyboard=True)
