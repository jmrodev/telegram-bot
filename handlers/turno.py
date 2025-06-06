# handlers/turno.py
import logging
import datetime
# Add specific imports if used, e.g. for typing
from typing import Any, Dict

from telegram import Update, ReplyKeyboardRemove, InlineKeyboardMarkup
from telegram.error import TelegramError # Import TelegramError
from googleapiclient.errors import HttpError as GoogleApiHttpError # Import Google API errors
from telegram.ext import ContextTypes, ConversationHandler # Importar ConversationHandler si se usara
import config # Assuming config.py has all BTN_*, STATE_*, CALENDAR_IDS_DOCTORES, etc.
import keyboards
import google_calendar_utils as gcal
from . import utils # Importar utils directamente

logger = logging.getLogger(__name__)

# --- Placeholder Constants (normally in config.py) ---
# States
STATE_EDIT_SELECT_APPOINTMENT = 'edit_select_appointment'
STATE_EDIT_AWAITING_CONFIRMATION = 'edit_awaiting_confirmation'
STATE_EDIT_AWAITING_NEW_DAY = 'edit_awaiting_new_day'
STATE_EDIT_AWAITING_NEW_TIMESLOT = 'edit_awaiting_new_timeslot'
STATE_EDIT_AWAITING_FINAL_CONFIRMATION = 'edit_awaiting_final_confirmation' # New for Part 3
# Callbacks
CALLBACK_PREFIX_EDIT = "edit_"
CALLBACK_PREFIX_PROCEED_EDIT = "proceed_edit_"
CALLBACK_PREFIX_ABORT_EDIT = "abort_edit_"
CALLBACK_PREFIX_FINALIZE_EDIT = "finalize_edit_" # New for Part 3
CALLBACK_PREFIX_CANCEL_FINALIZE_EDIT = "cancel_finalize_" # New for Part 3
# --- End Placeholder Constants ---

# --- Funciones para Solicitar Turno ---

async def handle_turno_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el menú principal de turnos."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"-> Entering handle_turno_menu for user {user.id} (@{user.username or 'N/A'}) in chat {chat_id}")
    try:
        await update.message.reply_text("Selecciona una opción para Turnos:", reply_markup=keyboards.turno_menu_markup)
        context.user_data['handled_in_group_0'] = True # Establecer bandera
        logger.info(f"<- Exiting handle_turno_menu for user {user.id} in chat {chat_id} (Menu sent, flag set)")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_turno_menu for user {user.id} in chat {chat_id}: {te}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_turno_menu for user {user.id} in chat {chat_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al mostrar el menú de turnos. Por favor, intenta /start de nuevo.")
        except Exception as e_reply:
            logger.error(f"Critical: Failed to send error message to user {user.id} (handle_turno_menu): {e_reply}", exc_info=True)


async def handle_turno_solicitar_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"
    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} (State {config.STATE_WAITING_DOCTOR}): Received doctor selection '{text}'")
    try:
        if text == config.BTN_CANCELAR_ACCION:
            logger.info(f"Cancellation detected in handle_turno_solicitar_doctor by user {user.id} in chat {chat_id}")
            await utils.cancel_action(update, context)
            return
        if text in config.DOCTOR_LIST:
            selected_doctor = text
            logger.info(f"Doctor chosen by user {user.id} in chat {chat_id}: {selected_doctor}")
            calendar_service = context.bot_data.get('calendar_service')
            if not calendar_service:
                logger.error(f"GCal Service not available for user {user.id} in chat {chat_id} (handle_turno_solicitar_doctor)", exc_info=True)
                await update.message.reply_text("Error de conexión con el calendario. Por favor, intenta más tarde.")
                await utils.send_main_menu(update, context)
                return
            has_existing, existing_details_str = gcal.check_existing_appointment(calendar_service, selected_doctor, user.to_dict())
            if has_existing:
                logger.info(f"User {user.id} in chat {chat_id} already has a future appointment with Dr. {selected_doctor}.")
                message = (
                    f"⚠️ Ya tienes un turno agendado con Dr./Dra. {selected_doctor} "
                    f"{existing_details_str or '(no se pudo obtener el detalle del día/hora)'}.\n\n"
                    f"Solo puedes tener un turno activo por doctor. Si necesitas cambiarlo, "
                    f"primero cancela el existente usando la opción '🗑 Cancelar Turno' del menú.\n\n"
                    f"Puedes elegir otro doctor o cancelar esta acción."
                )
                await update.message.reply_text(message, reply_markup=keyboards.create_doctor_keyboard())
                return
            logger.info(f"User {user.id} in chat {chat_id} does NOT have a future appointment with Dr. {selected_doctor}. Proceeding to request day.")
            context.user_data.setdefault('appointment_request', {})['doctor'] = selected_doctor
            context.user_data['state'] = config.STATE_WAITING_DAY
            markup = keyboards.create_day_keyboard()
            await update.message.reply_text(f"Excelente. ¿Qué día prefieres para tu turno con Dr./Dra. {selected_doctor}?", reply_markup=markup)
            logger.info(f"State set to STATE_WAITING_DAY for user {user.id} in chat {chat_id}")
        else:
            logger.warning(f"Invalid doctor name '{text}' received from user {user.id} in chat {chat_id}.")
            await update.message.reply_text(
                f"'{text}' no es un doctor válido. Por favor, elige un doctor de la lista o presiona '{config.BTN_CANCELAR_ACCION}'.",
                reply_markup=keyboards.create_doctor_keyboard()
            )
    except TelegramError as te:
        logger.error(f"TelegramError in handle_turno_solicitar_doctor for user {user.id} (text: '{text}'): {te}", exc_info=True)
    except GoogleApiHttpError as ge:
        logger.error(f"GoogleApiHttpError in handle_turno_solicitar_doctor for user {user.id} (text: '{text}'): {ge}", exc_info=True)
        try:
            await update.message.reply_text("Hubo un problema al consultar el calendario. Por favor, intenta de nuevo más tarde.")
        except Exception as e_reply:
            logger.error(f"Failed to send GoogleApiHttpError message to user {user.id}: {e_reply}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_turno_solicitar_doctor for user {user.id} (text: '{text}'): {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al seleccionar el doctor. Por favor, intenta de nuevo.")
        except Exception as e_reply:
            logger.error(f"Failed to send generic error message to user {user.id} (handle_turno_solicitar_doctor): {e_reply}", exc_info=True)


async def handle_turno_solicitar_dia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"
    current_actual_state = context.user_data.get('state')
    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} (State {current_actual_state}): Received day selection '{text}'")
    try:
        if text == config.BTN_CANCELAR_ACCION:
            logger.info(f"Cancellation detected in handle_turno_solicitar_dia by user {user.id} in chat {chat_id} (State: {current_actual_state})")
            await utils.cancel_action(update, context)
            return
        day_str = text.capitalize()
        if day_str in config.DAY_LIST:
            target_date = gcal.get_next_weekday_date(day_str)
            if not target_date:
                logger.error(f"Error generating date for day '{day_str}' for user {user.id} in chat {chat_id}", exc_info=True)
                await update.message.reply_text("Hubo un error al procesar el día seleccionado. Por favor, intenta de nuevo.", reply_markup=keyboards.create_day_keyboard())
                return
            is_editing = current_actual_state == STATE_EDIT_AWAITING_NEW_DAY
            appointment_data_storage_key = 'appointment_to_edit' if is_editing else 'appointment_request'
            appointment_data = context.user_data.get(appointment_data_storage_key)
            doctor_identifier_key = 'doctor_key' if is_editing else 'doctor'
            if not appointment_data or doctor_identifier_key not in appointment_data:
                log_message = (f"Error: Missing '{appointment_data_storage_key}' or '{doctor_identifier_key}' within it "
                               f"for user {user.id} in state {current_actual_state}.")
                logger.error(log_message, exc_info=True)
                user_err_message = ("Error interno: No se encontró la información necesaria. "
                                    "Por favor, reinicia el proceso con /start.")
                await update.message.reply_text(user_err_message, reply_markup=keyboards.main_menu_markup)
                await utils.send_main_menu(update, context)
                return
            if is_editing:
                appointment_data['new_day_str'] = day_str
                appointment_data['new_date_obj'] = target_date
                doctor_log_ref = appointment_data.get('doctor_name', appointment_data.get(doctor_identifier_key))
                logger.info(f"Editing appointment for user {user.id}: New day selected: {day_str} ({target_date.isoformat()}) for Dr. {doctor_log_ref}")
            else:
                appointment_data['day'] = day_str
                appointment_data['date_obj'] = target_date
                doctor_log_ref = appointment_data.get(doctor_identifier_key)
                logger.info(f"New appointment for user {user.id}: Day selected: {day_str} ({target_date.isoformat()}) for Dr. {doctor_log_ref}")
            calendar_service = context.bot_data.get('calendar_service')
            if not calendar_service:
                logger.error(f"GCal Service not available for user {user.id} in chat {chat_id} (handle_turno_solicitar_dia, editing: {is_editing})", exc_info=True)
                await update.message.reply_text("Error de conexión con el calendario. Por favor, intenta más tarde.", reply_markup=keyboards.main_menu_markup)
                await utils.send_main_menu(update, context)
                return
            gcal_doctor_ref = appointment_data.get('doctor_key') if is_editing else appointment_data.get('doctor')
            if not gcal_doctor_ref:
                 logger.critical(f"CRITICAL: gcal_doctor_ref is None for user {user.id}. Editing: {is_editing}. Appointment Data: {appointment_data}")
                 await update.message.reply_text("Error fatal de datos internos del doctor. Por favor, reinicia el proceso con /start.")
                 await utils.send_main_menu(update, context)
                 return
            logger.info(f"Querying GCal for Dr. Key '{gcal_doctor_ref}' on {target_date.isoformat()} for user {user.id} in chat {chat_id}")
            disponible_slots = gcal.check_google_calendar_availability(calendar_service, gcal_doctor_ref, target_date)
            display_doctor_name = appointment_data.get('doctor_name', gcal_doctor_ref) if is_editing else gcal_doctor_ref
            if disponible_slots:
                new_state = STATE_EDIT_AWAITING_NEW_TIMESLOT if is_editing else config.STATE_WAITING_TIMESLOT
                context.user_data['state'] = new_state
                markup = keyboards.create_timeslot_keyboard(disponible_slots)
                await update.message.reply_text(f"Horarios disponibles para Dr./Dra. {display_doctor_name} el {day_str} ({target_date.strftime('%d/%m')}):", reply_markup=markup)
                logger.info(f"Available slots shown to user {user.id}. State set to {new_state}.")
            else:
                markup = keyboards.create_day_keyboard()
                await update.message.reply_text(f"No se encontraron horarios disponibles para Dr./Dra. {display_doctor_name} el {day_str} ({target_date.strftime('%d/%m')}). Por favor, elige otro día o cancela la acción.", reply_markup=markup)
                logger.info(f"No slots found for Dr. {gcal_doctor_ref} on {day_str} for user {user.id}. Day selection keyboard reshown. State remains {current_actual_state}.")
        else:
            markup = keyboards.create_day_keyboard()
            logger.warning(f"Invalid day string '{text}' received from user {user.id} in chat {chat_id} (State: {current_actual_state}).")
            await update.message.reply_text(f"'{text}' no es un día válido. Por favor, elige un día de la lista o presiona '{config.BTN_CANCELAR_ACCION}'.", reply_markup=markup)
    except TelegramError as te:
        logger.error(f"TelegramError in handle_turno_solicitar_dia for user {user.id} (text: '{text}'): {te}", exc_info=True)
    except GoogleApiHttpError as ge:
        logger.error(f"GoogleApiHttpError in handle_turno_solicitar_dia for user {user.id} (text: '{text}'): {ge}", exc_info=True)
        try:
            await update.message.reply_text("Hubo un problema al verificar los horarios del calendario para el día seleccionado. Por favor, intenta de nuevo más tarde.")
        except Exception as e_reply:
            logger.error(f"Failed to send GoogleApiHttpError message to user {user.id} (handle_turno_solicitar_dia): {e_reply}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_turno_solicitar_dia for user {user.id} (text: '{text}'): {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al seleccionar el día. Por favor, intenta de nuevo.")
        except Exception as e_reply:
            logger.error(f"Failed to send generic error message to user {user.id} (handle_turno_solicitar_dia): {e_reply}", exc_info=True)

async def handle_turno_solicitar_hora(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"
    selected_time = text
    current_actual_state = context.user_data.get('state')
    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} (State {current_actual_state}): Received time slot selection '{selected_time}'")
    try:
        if text == config.BTN_CANCELAR_ACCION:
            logger.info(f"Cancellation detected in handle_turno_solicitar_hora by user {user.id} in chat {chat_id} (State: {current_actual_state})")
            await utils.cancel_action(update, context)
            return
        try:
            datetime.datetime.strptime(selected_time, '%H:%M')
            valid_time_format = True
        except ValueError:
            valid_time_format = False
        is_editing = current_actual_state == STATE_EDIT_AWAITING_NEW_TIMESLOT
        appointment_data_storage_key = 'appointment_to_edit' if is_editing else 'appointment_request'
        appointment_data = context.user_data.get(appointment_data_storage_key)
        if not appointment_data:
            logger.error(f"Error: Missing '{appointment_data_storage_key}' for user {user.id} in state {current_actual_state}.", exc_info=True)
            await update.message.reply_text("Error interno: No se encontró la información necesaria. Por favor, reinicia el proceso con /start.", reply_markup=keyboards.main_menu_markup)
            await utils.send_main_menu(update, context)
            return
        doctor_id_key = 'doctor_key' if is_editing else 'doctor'
        day_str_key = 'new_day_str' if is_editing else 'day'
        date_obj_key = 'new_date_obj' if is_editing else 'date_obj'
        doctor_gcal_id = appointment_data.get(doctor_id_key)
        display_doctor_name = appointment_data.get('doctor_name', doctor_gcal_id)
        day_str_value = appointment_data.get(day_str_key)
        target_date_value = appointment_data.get(date_obj_key)
        calendar_service = context.bot_data.get('calendar_service')
        if not all([doctor_gcal_id, day_str_value, target_date_value, calendar_service]):
            missing_elements = { 'doctor_gcal_id': doctor_gcal_id, 'day_str': day_str_value, 'target_date': target_date_value, 'calendar_service': calendar_service }
            missing_keys = [k for k, v in missing_elements.items() if not v]
            logger.error(f"Error: Missing critical data for user {user.id} in {current_actual_state}. Missing: {missing_keys}. Data: {appointment_data}", exc_info=True)
            await update.message.reply_text("Error interno: falta información para procesar tu solicitud. Por favor, reinicia el proceso con /start.", reply_markup=keyboards.main_menu_markup)
            await utils.send_main_menu(update, context)
            return
        if not valid_time_format:
            logger.warning(f"Invalid time format '{selected_time}' from user {user.id} in {current_actual_state}.")
            disponible_slots = gcal.check_google_calendar_availability(calendar_service, doctor_gcal_id, target_date_value)
            markup = keyboards.create_timeslot_keyboard(disponible_slots if disponible_slots else [])
            await update.message.reply_text(f"El formato de hora '{selected_time}' no es válido (debe ser HH:MM). Por favor, elige una hora de la lista o cancela la acción.", reply_markup=markup)
            return
        logger.info(f"Time slot chosen by user {user.id}: {selected_time}. Verifying availability for Dr. {doctor_gcal_id} on {target_date_value.isoformat()} (Editing: {is_editing}).")
        available_slots_now = gcal.check_google_calendar_availability(calendar_service, doctor_gcal_id, target_date_value)
        if selected_time not in available_slots_now:
            logger.warning(f"Time slot {selected_time} for Dr. {doctor_gcal_id} on {target_date_value.isoformat()} is no longer available (user {user.id}).")
            markup = keyboards.create_timeslot_keyboard(available_slots_now if available_slots_now else [])
            await update.message.reply_text(f"El horario de las {selected_time} lamentablemente acaba de ser ocupado. Estos son los horarios ahora disponibles para Dr./Dra. {display_doctor_name}:", reply_markup=markup)
            return
        if is_editing:
            appointment_data['new_selected_time'] = selected_time
            logger.info(f"Editing appointment for user {user.id}: New time selected: {selected_time}. Current edit data: {appointment_data}")
            new_day_display = appointment_data.get('new_day_str', 'Día no especificado')
            new_date_obj = appointment_data.get('new_date_obj')
            new_date_display_str = new_date_obj.strftime('%d/%m/%Y') if new_date_obj else "Fecha no especificada"
            original_display_dt = appointment_data.get('original_display_datetime', 'No disponible')
            original_doctor_name = appointment_data.get('doctor_name', appointment_data.get('doctor_key', 'Dr. Desconocido'))
            summary_text = (
                f"Estás a punto de cambiar tu turno:\n\n"
                f"Turno Original:\n"
                f"  Doctor/a: {original_doctor_name}\n"
                f"  Horario: {original_display_dt}\n\n"
                f"NUEVO Turno Propuesto:\n"
                f"  Doctor/a: {display_doctor_name}\n"
                f"  Día: {new_day_display} ({new_date_display_str})\n"
                f"  Hora: {selected_time}\n\n"
                f"¿Confirmas para reagendar el turno con estos nuevos detalles?"
            )
            finalize_keyboard = keyboards.create_finalize_edit_keyboard(
                callback_finalize_prefix=CALLBACK_PREFIX_FINALIZE_EDIT,
                callback_cancel_finalize_prefix=CALLBACK_PREFIX_CANCEL_FINALIZE_EDIT
            )
            await update.message.reply_text(summary_text, reply_markup=finalize_keyboard)
            context.user_data['state'] = STATE_EDIT_AWAITING_FINAL_CONFIRMATION
            logger.info(f"Edit Part 2 (time selection) complete for user {user.id}. Awaiting final confirmation. State: {STATE_EDIT_AWAITING_FINAL_CONFIRMATION}")
        else:
            logger.info(f"Time slot {selected_time} is available for user {user.id} (new appointment). Creating GCal event...")
            success, event_link = gcal.create_google_calendar_event(calendar_service, doctor_gcal_id, day_str_value, selected_time, user.to_dict())
            if success:
                await update.message.reply_text(
                    f"¡Turno confirmado! Dr./Dra. {display_doctor_name} el {day_str_value} ({target_date_value.strftime('%d/%m/%Y')}) a las {selected_time}.\n"
                    f"Puedes ver los detalles de tu turno aquí: {event_link or 'No disponible'}\n\n"
                    "Volviendo al menú principal...",
                    reply_markup=keyboards.main_menu_markup,
                    disable_web_page_preview=True
                )
                logger.info(f"Appointment created successfully in GCal for user {user.id}. Link: {event_link}")
            else:
                logger.error(f"Failed to create GCal event for user {user.id} (Dr. {doctor_gcal_id}, {day_str_value}, {selected_time})", exc_info=True)
                await update.message.reply_text("Hubo un error al intentar agendar tu turno en el calendario. Por favor, contacta a la secretaría para confirmar.", reply_markup=keyboards.main_menu_markup)
            context.user_data.clear()
            logger.info(f"User data cleared for user {user.id} after new appointment processing.")
            await utils.send_main_menu(update, context, "Puedes elegir otra opción del menú:")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_turno_solicitar_hora for user {user.id} (text: '{text}'): {te}", exc_info=True)
    except GoogleApiHttpError as ge:
        logger.error(f"GoogleApiHttpError in handle_turno_solicitar_hora for user {user.id} (text: '{text}'): {ge}", exc_info=True)
        user_msg = "Hubo un problema con el calendario al intentar confirmar tu turno. Por favor, intenta de nuevo más tarde."
        if "already exists" in str(ge).lower():
             user_msg = "Parece que ya existe un turno muy cercano o un conflicto. Por favor, intenta con otro horario o contacta a secretaría."
        try:
            await update.message.reply_text(user_msg)
        except Exception as e_reply:
            logger.error(f"Failed to send GoogleApiHttpError message to user {user.id} (handle_turno_solicitar_hora): {e_reply}", exc_info=True)
        context.user_data.clear()
        await utils.send_main_menu(update, context, "Volviendo al menú principal debido a un error con el calendario.")
    except Exception as e:
        logger.error(f"Unexpected error in handle_turno_solicitar_hora for user {user.id} (text: '{text}'): {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al seleccionar la hora. Por favor, intenta de nuevo.")
        except Exception as e_reply:
            logger.error(f"Failed to send generic error message to user {user.id} (handle_turno_solicitar_hora): {e_reply}", exc_info=True)
        context.user_data.clear()
        await utils.send_main_menu(update, context, "Volviendo al menú principal debido a un error.")

async def handle_request_cancel_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    if not user:
        logger.warning("handle_request_cancel_appointment called without effective_user.")
        return
    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id}: Initiating appointment cancellation flow.")
    try:
        calendar_service = context.bot_data.get('calendar_service')
        if not calendar_service:
            logger.error(f"GCal Service not available for user {user.id} in chat {chat_id} (handle_request_cancel_appointment)", exc_info=True)
            await update.message.reply_text("Error de conexión con el calendario. Por favor, intenta más tarde.")
            return
        user_appointments = gcal.find_all_user_appointments(calendar_service, user.to_dict())
        if not user_appointments:
            logger.info(f"No future appointments found for user {user.id} in chat {chat_id}.")
            await update.message.reply_text("No encontré turnos futuros agendados a tu nombre.")
            return
        logger.info(f"Found {len(user_appointments)} appointments for user {user.id} in chat {chat_id}. Displaying them for cancellation.")
        cancel_keyboard_markup = keyboards.create_appointments_inline_keyboard(
            user_appointments,
            button_text_prefix="🚫 Cancelar",
            callback_prefix=config.CALLBACK_PREFIX_CANCEL
        )
        if not cancel_keyboard_markup:
            logger.warning(f"Could not create cancellation keyboard for user {user.id} in chat {chat_id}, though appointments were found.", exc_info=True)
            await update.message.reply_text("Hubo un problema al intentar mostrar tus turnos para cancelar. Por favor, contacta a la secretaría.")
            return
        await update.message.reply_text(
            "Encontré estos turnos futuros a tu nombre. ¿Cuál deseas cancelar?",
            reply_markup=cancel_keyboard_markup
        )
        logger.debug(f"Cancellation options displayed to user {user.id} in chat {chat_id}.")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_request_cancel_appointment for user {user.id}: {te}", exc_info=True)
    except GoogleApiHttpError as ge:
        logger.error(f"GoogleApiHttpError in handle_request_cancel_appointment for user {user.id}: {ge}", exc_info=True)
        try:
            await update.message.reply_text("Hubo un problema al consultar el calendario para buscar tus turnos. Por favor, intenta de nuevo más tarde.")
        except Exception as e_reply:
            logger.error(f"Failed to send GoogleApiHttpError message to user {user.id} (handle_request_cancel_appointment): {e_reply}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_request_cancel_appointment for user {user.id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al buscar tus turnos. Por favor, intenta de nuevo más tarde.")
        except Exception as e_reply:
            logger.error(f"Failed to send generic error message to user {user.id} (handle_request_cancel_appointment): {e_reply}", exc_info=True)

async def handle_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    chat_id = query.message.chat.id if query.message else "N/A"
    await query.answer()
    callback_data = query.data
    logger.info(f"User {user_id} (@{user.username or 'N/A'}) in chat {chat_id} initiated cancel callback with data: '{callback_data}'")
    try:
        if not callback_data or not callback_data.startswith(config.CALLBACK_PREFIX_CANCEL):
            logger.warning(f"Invalid callback data received from user {user_id} in chat {chat_id}: {callback_data}")
            await query.edit_message_text(text="Error: Botón de cancelación inválido.")
            return
        try:
            parts = callback_data.split('_')
            if len(parts) != 3:
                raise ValueError("Callback data format is incorrect (expected 3 parts).")
            _, event_id, doctor_key = parts
            calendar_id = config.CALENDAR_IDS_DOCTORES.get(doctor_key)
            if not calendar_id:
                logger.error(f"No calendar_id found for doctor_key '{doctor_key}' from callback data '{callback_data}' (user {user_id}).", exc_info=True)
                raise ValueError(f"Configuración de doctor inválida para {doctor_key}.")
        except ValueError as ve:
            logger.error(f"Error parsing callback data '{callback_data}' for user {user_id} in chat {chat_id}: {ve}", exc_info=True)
            await query.edit_message_text(text="Error al procesar la solicitud de cancelación. Datos inválidos.")
            return
        logger.info(f"Attempting to cancel EventID: {event_id} in CalendarID: {calendar_id} (DoctorKey: {doctor_key}) for user {user_id}.")
        calendar_service = context.bot_data.get('calendar_service')
        if not calendar_service:
            logger.error(f"GCal Service not available for user {user_id} in chat {chat_id} (handle_cancel_callback)", exc_info=True)
            await query.edit_message_text(text="Error de conexión con el calendario. No se pudo cancelar el turno.")
            return
        success = gcal.delete_google_calendar_event(calendar_service, calendar_id, event_id)
        if success:
            logger.info(f"Event {event_id} successfully cancelled for user {user_id} (DoctorKey: {doctor_key}).")
            await query.edit_message_text(text=f"✅ ¡Turno cancelado con éxito!\n(Doctor: {doctor_key}, ID de Turno: ...{event_id[-6:]})")
        else:
            logger.error(f"Failed to cancel event {event_id} for user {user_id} (DoctorKey: {doctor_key}). gcal.delete_google_calendar_event returned False.", exc_info=True)
            await query.edit_message_text(text="❌ Error al cancelar el turno en el calendario. Por favor, contacta a la secretaría.")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_cancel_callback for user {user_id} (data '{callback_data}'): {te}", exc_info=True)
    except GoogleApiHttpError as ge:
        logger.error(f"GoogleApiHttpError in handle_cancel_callback for user {user_id} (data '{callback_data}'): {ge}", exc_info=True)
        try:
            await query.edit_message_text(text="❌ Hubo un problema con el calendario al intentar cancelar tu turno. Por favor, verifica el calendario o contacta a secretaría.")
        except Exception as e_reply:
            logger.error(f"Failed to send GoogleApiHttpError message to user {user_id} (handle_cancel_callback): {e_reply}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_cancel_callback for user {user_id} (data '{callback_data}'): {e}", exc_info=True)
        try:
            await query.edit_message_text(text="Ocurrió un error inesperado al procesar tu solicitud de cancelación. Por favor, intenta de nuevo o contacta a secretaría.")
        except Exception as e_reply:
            logger.error(f"Failed to send generic error message to user {user_id} (handle_cancel_callback): {e_reply}", exc_info=True)

async def handle_turno_sub_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"
    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} selected turnos sub-option: '{text}'")
    try:
        context.user_data['handled_in_group_0'] = True
        logger.debug(f"Flag 'handled_in_group_0' set for user {user.id} in chat {chat_id} in handle_turno_sub_choice for '{text}'")
        if text == config.BTN_TURNO_SOLICITAR:
            logger.debug(f"User {user.id} in chat {chat_id}: Initiating 'Solicitar Turno' flow.")
            await update.message.reply_text("¿Con qué doctor deseas el turno?", reply_markup=keyboards.create_doctor_keyboard())
            context.user_data['state'] = config.STATE_WAITING_DOCTOR
            logger.info(f"State set to STATE_WAITING_DOCTOR for user {user.id} in chat {chat_id}")
        elif text == config.BTN_TURNO_ELIMINAR:
            logger.debug(f"User {user.id} in chat {chat_id}: Initiating 'Cancelar Turno' flow.")
            await handle_request_cancel_appointment(update, context)
        elif text == config.BTN_TURNO_EDITAR:
            logger.debug(f"User {user.id} in chat {chat_id}: Selected 'Editar Turno'.")
            await request_appointment_to_edit(update, context)
            return
        elif text == config.BTN_TURNO_VIDEO:
            logger.debug(f"User {user.id} in chat {chat_id}: Requested 'Info Videollamada'.")
            video_info = getattr(config, 'VIDEO_CALL_INFO_TEXT', "") # Use the new config variable name
            if video_info and "[ENLACE_VIDEOCONSULTA_AQUI]" not in video_info: # Basic check if it's configured and not just placeholder
                user_message = video_info
            elif video_info and "[ENLACE_VIDEOCONSULTA_AQUI]" in video_info: # It's the placeholder
                 logger.warning(f"VIDEO_CALL_INFO_TEXT for user {user.id} seems to be the placeholder.")
                 user_message = "La información detallada para videollamadas está siendo actualizada. Por favor, contacte a secretaría por ahora para obtener los detalles."
            else: # Not defined or empty
                logger.warning(f"VIDEO_CALL_INFO_TEXT not configured or empty for user {user.id}.")
                user_message = "La información sobre videollamadas no está configurada actualmente. Por favor, contacte a secretaría."
            await update.message.reply_text(user_message, reply_markup=keyboards.turno_menu_markup)
        elif text == config.BTN_TURNO_DOCTOR:
            logger.debug(f"User {user.id} in chat {chat_id}: Requested 'Ver Doctores'.")
            doctor_list_str = ", ".join(config.DOCTOR_LIST) if config.DOCTOR_LIST else "No hay doctores configurados."
            await update.message.reply_text(f"Doctores disponibles: {doctor_list_str}.", reply_markup=keyboards.turno_menu_markup)
        elif text == config.BTN_TURNO_SECRETARIA:
            logger.debug(f"User {user.id} in chat {chat_id}: Initiating 'Comunicarse con Secretaría'.")
            await update.message.reply_text("Por favor, escribe tu mensaje para la secretaría:", reply_markup=keyboards.cancel_markup)
            context.user_data['state'] = config.STATE_TALKING_TO_SECRETARY
            logger.info(f"State set to STATE_TALKING_TO_SECRETARY for user {user.id} in chat {chat_id}")
        else:
            logger.warning(f"Unrecognized sub-option '{text}' in handle_turno_sub_choice from user {user.id} in chat {chat_id}.")
            await update.message.reply_text("Opción no reconocida dentro del menú de turnos. Por favor, selecciona una de las opciones disponibles.", reply_markup=keyboards.turno_menu_markup)
    except TelegramError as te_reply:
        logger.error(f"TelegramError replying within handle_turno_sub_choice for user {user.id} (text '{text}'): {te_reply}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_turno_sub_choice for user {user.id} (text '{text}'): {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado al procesar tu selección. Por favor, intenta /start de nuevo.")
        except Exception as e_reply:
            logger.error(f"Critical: Failed to send generic error reply to user {user.id} (handle_turno_sub_choice): {e_reply}", exc_info=True)

async def request_appointment_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User {user.id} in chat {chat_id}: Requesting to select an appointment to edit.")
    calendar_service = context.bot_data.get('calendar_service')
    if not calendar_service:
        logger.error(f"GCal Service not available for user {user.id} (request_appointment_to_edit)")
        await update.message.reply_text("Error de conexión con el calendario. No se pueden buscar turnos para editar.")
        await utils.send_main_menu(update, context)
        return
    try:
        user_appointments = gcal.find_all_user_appointments(calendar_service, user.to_dict())
        if not user_appointments:
            logger.info(f"No future appointments found for user {user.id} to edit.")
            await update.message.reply_text("No tienes turnos futuros para editar.", reply_markup=keyboards.turno_menu_markup)
            context.user_data.pop('state', None)
            return
        logger.info(f"Found {len(user_appointments)} appointments for user {user.id} to potentially edit.")
        edit_keyboard_markup = keyboards.create_appointments_inline_keyboard(
            user_appointments,
            button_text_prefix="✏️ Editar",
            callback_prefix=CALLBACK_PREFIX_EDIT
        )
        if not edit_keyboard_markup:
            logger.warning(f"Could not create edit appointments keyboard for user {user.id}, though appointments were found.")
            await update.message.reply_text("No se pudieron mostrar los turnos para editar en este momento. Intenta más tarde.", reply_markup=keyboards.turno_menu_markup)
            context.user_data.pop('state', None)
            return
        await update.message.reply_text(
            "Selecciona el turno que deseas editar:",
            reply_markup=edit_keyboard_markup
        )
        context.user_data['state'] = STATE_EDIT_SELECT_APPOINTMENT
        logger.debug(f"State set to STATE_EDIT_SELECT_APPOINTMENT for user {user.id}")
    except GoogleApiHttpError as ge:
        logger.error(f"GoogleApiHttpError in request_appointment_to_edit for user {user.id}: {ge}", exc_info=True)
        await update.message.reply_text("Hubo un problema al acceder a tu calendario para buscar turnos. Intenta más tarde.")
        await utils.send_main_menu(update, context)
    except TelegramError as te:
        logger.error(f"TelegramError in request_appointment_to_edit for user {user.id}: {te}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in request_appointment_to_edit for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text("Ocurrió un error inesperado al buscar tus turnos para editar. Por favor, intenta /start de nuevo.")
        await utils.send_main_menu(update, context)

async def handle_edit_appointment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id if query.message else "N/A"
    await query.answer()
    callback_data = query.data
    logger.info(f"User {user.id} in chat {chat_id}: handle_edit_appointment_callback with data '{callback_data}'")
    try:
        parts = callback_data.replace(CALLBACK_PREFIX_EDIT, "").split('_')
        if len(parts) < 2:
            raise ValueError("Callback data for edit selection is malformed.")
        event_id = parts[0]
        doctor_key = "_".join(parts[1:])
        calendar_service = context.bot_data.get('calendar_service')
        if not calendar_service:
            logger.error(f"GCal Service not available for user {user.id} (handle_edit_appointment_callback)")
            await query.edit_message_text(text="Error de conexión con el calendario. No se puede proceder con la edición.")
            return
        calendar_id = config.CALENDAR_IDS_DOCTORES.get(doctor_key)
        if not calendar_id:
            logger.error(f"No calendar_id found for doctor_key '{doctor_key}' for user {user.id}. Cannot fetch event details.")
            await query.edit_message_text(text="Error de configuración del doctor. No se puede proceder.")
            return
        event_details = gcal.get_event_details(calendar_service, calendar_id, event_id)
        if not event_details:
            logger.warning(f"Could not fetch details for event {event_id} (Dr. {doctor_key}) for user {user.id}.")
            await query.edit_message_text(text="No se pudieron obtener los detalles del turno seleccionado. Intenta de nuevo.")
            return
        context.user_data['appointment_to_edit'] = {
            'event_id': event_id,
            'doctor_key': doctor_key,
            'calendar_id': calendar_id,
            'doctor_name': event_details.get('doctor_name', doctor_key),
            'original_summary': event_details.get('summary', f"Turno con {doctor_key}"),
            'original_start_datetime_iso': event_details.get('start_datetime_iso'),
            'original_end_datetime_iso': event_details.get('end_datetime_iso'),
            'original_display_datetime': event_details.get('display_datetime', 'Fecha/hora desconocida'),
        }
        logger.info(f"Stored detailed appointment for edit: EventID {event_id} for user {user.id}. Details: {context.user_data['appointment_to_edit']}")
        confirmation_keyboard = keyboards.create_edit_confirmation_keyboard(
            event_id,
            doctor_key,
            callback_proceed_prefix=CALLBACK_PREFIX_PROCEED_EDIT,
            callback_abort_prefix=CALLBACK_PREFIX_ABORT_EDIT
        )
        confirmation_text = (
            f"Has seleccionado editar el siguiente turno:\n"
            f"Doctor/a: {event_details.get('doctor_name', doctor_key)}\n"
            f"Fecha y Hora: {event_details.get('display_datetime', 'No disponible')}\n\n"
            f"¿Confirmas que quieres cambiar la fecha/hora de este turno?"
        )
        await query.edit_message_text(
            text=confirmation_text,
            reply_markup=confirmation_keyboard
        )
        context.user_data['state'] = STATE_EDIT_AWAITING_CONFIRMATION
        logger.debug(f"State set to STATE_EDIT_AWAITING_CONFIRMATION for user {user.id}")
    except ValueError as ve:
        logger.error(f"ValueError parsing callback_data in handle_edit_appointment_callback for user {user.id}: {ve}", exc_info=True)
        await query.edit_message_text(text="Error al procesar tu selección. Intenta de nuevo.")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_edit_appointment_callback for user {user.id}: {te}", exc_info=True)
    except GoogleApiHttpError as ge:
        logger.error(f"GoogleApiHttpError in handle_edit_appointment_callback for user {user.id}: {ge}", exc_info=True)
        await query.edit_message_text(text="Error al obtener detalles del turno del calendario. Intenta de nuevo.")
    except Exception as e:
        logger.error(f"Unexpected error in handle_edit_appointment_callback for user {user.id}: {e}", exc_info=True)
        try:
            await query.edit_message_text(text="Ocurrió un error inesperado al seleccionar el turno para editar. Por favor, intenta /start de nuevo.")
        except Exception as e_reply:
            logger.error(f"Failed to send error message to user {user.id} (handle_edit_appointment_callback): {e_reply}", exc_info=True)

async def handle_proceed_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id if query.message else "N/A"
    await query.answer()
    logger.info(f"User {user.id} in chat {chat_id} confirmed to proceed with editing appointment.")
    try:
        appointment_to_edit = context.user_data.get('appointment_to_edit')
        if not appointment_to_edit or not appointment_to_edit.get('event_id'):
            logger.warning(f"User {user.id} clicked proceed_edit but 'appointment_to_edit' data is missing from user_data.")
            await query.edit_message_text("Hubo un problema al recuperar los datos de tu turno. Por favor, intenta seleccionar el turno a editar nuevamente desde el menú de turnos.")
            context.user_data.pop('state', None)
            context.user_data.pop('appointment_to_edit', None)
            return
        doctor_name = appointment_to_edit.get('doctor_name', 'el doctor/a seleccionado/a')
        await query.edit_message_text(text=f"Editando turno: {appointment_to_edit.get('original_summary', 'Turno Seleccionado')}\n\n"
                                           f"Por favor, selecciona el NUEVO día para tu turno con Dr./Dra. {doctor_name}.")
        day_keyboard_markup = keyboards.create_day_keyboard()
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Elige el nuevo día para el turno con Dr./Dra. {doctor_name}:",
            reply_markup=day_keyboard_markup
        )
        context.user_data['state'] = STATE_EDIT_AWAITING_NEW_DAY
        logger.info(f"State set to STATE_EDIT_AWAITING_NEW_DAY for user {user.id} to select new day for editing.")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_proceed_edit_callback for user {user.id}: {te}", exc_info=True)
        try:
            await query.edit_message_text(text="Hubo un problema de comunicación. Por favor, intenta la edición nuevamente.")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Unexpected error in handle_proceed_edit_callback for user {user.id}: {e}", exc_info=True)
        try:
            await query.edit_message_text(text="Ocurrió un error inesperado al proceder con la edición. Por favor, intenta /start de nuevo.")
        except Exception as e_reply:
            logger.error(f"Failed to send error message to user {user.id} (handle_proceed_edit_callback): {e_reply}", exc_info=True)
        context.user_data.pop('appointment_to_edit', None)
        context.user_data.pop('state', None)

async def handle_abort_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id if query.message else "N/A"
    await query.answer()
    logger.info(f"User {user.id} in chat {chat_id} aborted editing appointment.")
    try:
        context.user_data.pop('appointment_to_edit', None)
        context.user_data.pop('state', None)
        await query.edit_message_text(text="La edición del turno ha sido cancelada.")
        await utils.send_main_menu(update, context, "Puedes seleccionar otra opción:")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_abort_edit_callback for user {user.id}: {te}", exc_info=True)
        try:
            await utils.send_main_menu(update, context, "Hubo un error al cancelar. Volviendo al menú principal.")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Unexpected error in handle_abort_edit_callback for user {user.id}: {e}", exc_info=True)
        try:
            await query.edit_message_text(text="Ocurrió un error inesperado al cancelar la edición.")
        except Exception:
            pass
        await utils.send_main_menu(update, context, "Volviendo al menú principal debido a un error.")

async def handle_finalize_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the final confirmation to edit an appointment: Deletes old, creates new."""
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id if query.message else "N/A" # Should have message
    await query.answer()

    logger.info(f"User {user.id} in chat {chat_id} pressed finalize edit appointment.")
    appointment_to_edit = context.user_data.get('appointment_to_edit')

    required_keys = ['original_event_id', 'calendar_id', 'doctor_key',
                     'new_date_obj', 'new_selected_time', 'doctor_name']
    if not appointment_to_edit or not all(k in appointment_to_edit for k in required_keys):
        logger.error(f"User {user.id} in finalize_edit_callback: 'appointment_to_edit' data is incomplete or missing. Data: {appointment_to_edit}")
        await query.edit_message_text("Error: No se pudo recuperar la información completa del turno a editar. Por favor, reinicia el proceso de edición.")
        context.user_data.clear()
        await utils.send_main_menu(update, context)
        return

    calendar_service = context.bot_data.get('calendar_service')
    if not calendar_service:
        logger.error(f"GCal Service not available for user {user.id} (handle_finalize_edit_callback)")
        await query.edit_message_text("Error de conexión con el calendario. No se pudo reagendar el turno.")
        context.user_data.clear()
        await utils.send_main_menu(update, context)
        return

    original_event_id = appointment_to_edit['original_event_id']
    original_calendar_id = appointment_to_edit['calendar_id']
    new_event_doctor_key = appointment_to_edit['doctor_key']
    new_event_doctor_display_name = appointment_to_edit.get('doctor_name', new_event_doctor_key)
    new_date_obj = appointment_to_edit['new_date_obj']
    new_selected_time = appointment_to_edit['new_selected_time']
    new_day_str = new_date_obj.strftime('%A')
    user_info_for_gcal = user.to_dict()

    try:
        logger.info(f"User {user.id}: Attempting to delete old event {original_event_id} from calendar {original_calendar_id}.")
        delete_success = gcal.delete_google_calendar_event(calendar_service, original_calendar_id, original_event_id)

        if not delete_success:
            logger.error(f"User {user.id}: Failed to delete old event {original_event_id} during edit.")
            await query.edit_message_text("Error: No se pudo cancelar el turno original. El turno NO ha sido reagendado. Por favor, contacta a secretaría o inténtalo de nuevo.")
            return

        logger.info(f"User {user.id}: Old event {original_event_id} deleted successfully. Creating new one.")
        create_success, new_event_link = gcal.create_google_calendar_event(
            calendar_service, new_event_doctor_key, new_day_str,
            new_selected_time, user_info_for_gcal, specific_date=new_date_obj
        )
        if create_success:
            success_message = (
                f"¡Turno reagendado con éxito!\n\n"
                f"Nuevo Turno:\n"
                f"  Doctor/a: {new_event_doctor_display_name}\n"
                f"  Día: {new_day_str} ({new_date_obj.strftime('%d/%m/%Y')})\n"
                f"  Hora: {new_selected_time}\n"
                f"Puedes ver los detalles aquí: {new_event_link or 'No disponible'}"
            )
            await query.edit_message_text(text=success_message, disable_web_page_preview=True)
            logger.info(f"User {user.id}: New event created successfully. Link: {new_event_link}")
        else:
            logger.error(f"User {user.id}: Failed to create new event after deleting old one. Old event {original_event_id} is deleted.")
            error_msg_critical = (
                "¡Atención! Se canceló tu turno original, pero NO se pudo agendar el nuevo horario "
                "debido a un conflicto o error (posiblemente el horario fue ocupado).\n\n"
                "Por favor, contacta a la secretaría URGENTEMENTE para resolver esto o intenta solicitar un turno nuevo desde el menú."
            )
            await query.edit_message_text(text=error_msg_critical)
    except GoogleApiHttpError as ge:
        logger.error(f"GoogleApiHttpError in handle_finalize_edit_callback for user {user.id}: {ge}", exc_info=True)
        await query.edit_message_text("Hubo un error con el servicio de calendario al intentar reagendar tu turno. Por favor, contacta a secretaría.")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_finalize_edit_callback for user {user.id}: {te}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_finalize_edit_callback for user {user.id}: {e}", exc_info=True)
        try:
            await query.edit_message_text("Ocurrió un error inesperado al finalizar el reagendamiento. Por favor, verifica tu calendario o contacta a secretaría.")
        except Exception:
            pass
    finally:
        context.user_data.clear()
        logger.info(f"User {user.id}: Finalize edit process complete, user_data cleared.")
        await utils.send_main_menu(update, context, "Puedes realizar otra operación.")

async def handle_cancel_finalize_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles cancelling the final edit confirmation."""
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id if query.message else "N/A"
    await query.answer()
    logger.info(f"User {user.id} in chat {chat_id} cancelled the finalization of edit (via cancel_finalize_edit_callback).")
    try:
        await query.edit_message_text(text="Operación de reagendamiento cancelada.")
    except TelegramError as te:
        logger.error(f"TelegramError editing message in handle_cancel_finalize_edit_callback: {te}", exc_info=True)
    finally:
        context.user_data.clear() # Clear all user_data including 'appointment_to_edit' and 'state'
        await utils.send_main_menu(update, context, "Operación cancelada. Puedes seleccionar otra opción:")

async def handle_turno_editar_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text if update.message else "N/A"
    current_state = context.user_data.get('state')
    logger.info(f"User {user.id} (@{user.username or 'N/A'}) in chat {chat_id} reached 'handle_turno_editar_placeholder' (State: {current_state}, Received text: '{text}')")
    try:
        await update.message.reply_text(
            "La función para editar turnos aún no está implementada.\nVolviendo al menú principal...",
            reply_markup=keyboards.main_menu_markup
        )
        context.user_data.clear()
        logger.info(f"User data cleared for user {user.id} in chat {chat_id} after 'handle_turno_editar_placeholder'.")
        await utils.send_main_menu(update, context)
        logger.debug(f"Main menu sent to user {user.id} in chat {chat_id} after placeholder edit.")
    except TelegramError as te:
        logger.error(f"TelegramError in handle_turno_editar_placeholder for user {user.id}: {te}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_turno_editar_placeholder for user {user.id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("Ocurrió un error inesperado. Serás redirigido al menú principal. Intenta /start si el problema persiste.")
        except Exception as e_reply:
            logger.error(f"Failed to send generic error message to user {user.id} (handle_turno_editar_placeholder): {e_reply}", exc_info=True)
        if context:
            context.user_data.clear()
            try:
                await utils.send_main_menu(update, context)
            except Exception as e_final_send:
                 logger.error(f"Failed to send final main menu in handle_turno_editar_placeholder error path: {e_final_send}", exc_info=True)