# handlers/turno.py
import logging
import datetime
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler # Importar ConversationHandler si se usara
import config
import keyboards
import google_calendar_utils as gcal
from . import utils # Importar utils directamente

logger = logging.getLogger(__name__)

# --- Funciones para Solicitar Turno ---

async def handle_turno_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el menú principal de turnos."""
    logger.info(f"-> Entrando en handle_turno_menu (Chat ID: {update.effective_chat.id})")
    try:
        await update.message.reply_text("Selecciona una opción para Turnos:", reply_markup=keyboards.turno_menu_markup)
        context.user_data['handled_in_group_0'] = True # Establecer bandera
        logger.info(f"<- Saliendo de handle_turno_menu (Respuesta enviada, bandera establecida)")
    except Exception as e:
        logger.error(f"!! ERROR dentro de handle_turno_menu: {e}", exc_info=True)


# --- MODIFICADO para usar retorno de check_existing_appointment ---
async def handle_turno_solicitar_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador que recibe el doctor elegido y verifica turno existente."""
    text = update.message.text; chat_id = update.effective_chat.id; user = update.effective_user
    logger.debug(f"State {config.STATE_WAITING_DOCTOR}: Recibido '{text}' de {chat_id}")

    # Manejar cancelación primero
    if text == config.BTN_CANCELAR_ACCION:
        logger.info(f"Cancelación detectada en handle_turno_solicitar_doctor por {chat_id}")
        await utils.cancel_action(update, context)
        return

    # Verificar si el doctor es válido
    if text in config.DOCTOR_LIST:
        selected_doctor = text
        logger.info(f"Doctor elegido {chat_id}: {selected_doctor}")

        # Verificar turno existente y obtener detalles si existe
        calendar_service = context.bot_data.get('calendar_service')
        if not calendar_service:
            logger.error("Error GCal Service en handle_turno_solicitar_doctor")
            await update.message.reply_text("Error conexión calendario.")
            await utils.send_main_menu(update, context) # Volver al menú
            return

        # --- LLAMADA A FUNCIÓN MODIFICADA ---
        has_existing, existing_details_str = gcal.check_existing_appointment(
            calendar_service, selected_doctor, user.to_dict()
        )
        # ------------------------------------

        if has_existing:
            logger.info(f"Usuario {chat_id} ya tiene turno futuro con Dr:{selected_doctor}.")
            # --- MENSAJE MEJORADO ---
            message = (
                f"⚠️ Ya tienes un turno agendado con Dr./Dra. {selected_doctor} "
                f"{existing_details_str or '(no se pudo obtener el detalle del día/hora)'}.\n\n" # Usa el detalle devuelto
                f"Solo puedes tener un turno activo por doctor. Si necesitas cambiarlo, "
                f"primero cancela el existente usando la opción '🗑 Cancelar Turno' del menú.\n\n"
                f"Puedes elegir otro doctor o cancelar esta acción."
            )
            await update.message.reply_text(message, reply_markup=keyboards.create_doctor_keyboard())
            # -------------------------
            # MANTENER estado STATE_WAITING_DOCTOR para que elija otro doctor o cancele
            return # Detener el flujo aquí

        # Si NO tiene turno existente, continuar como antes:
        logger.info(f"Usuario {chat_id} NO tiene turno futuro con Dr:{selected_doctor}. Procediendo a solicitar día.")
        context.user_data.setdefault('appointment_request', {})['doctor'] = selected_doctor
        context.user_data['state'] = config.STATE_WAITING_DAY
        markup = keyboards.create_day_keyboard()
        await update.message.reply_text(f"Excelente. ¿Qué día prefieres para tu turno con Dr./Dra. {selected_doctor}?", reply_markup=markup)

    else:
        # Si el texto no es un doctor válido ni el botón cancelar
        await update.message.reply_text(f"'{text}' no es un doctor válido. Elige de la lista o '{config.BTN_CANCELAR_ACCION}'.", reply_markup=keyboards.create_doctor_keyboard())
        # Mantener estado STATE_WAITING_DOCTOR


# --- Resto de funciones SIN CAMBIOS respecto a la versión anterior ---
# (handle_turno_solicitar_dia, handle_turno_solicitar_hora,
#  handle_request_cancel_appointment, handle_cancel_callback,
#  handle_turno_sub_choice, handle_turno_editar_placeholder)
# ... (Pegar aquí el código completo de esas funciones como estaban antes) ...

async def handle_turno_solicitar_dia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    logger.debug(f"State {config.STATE_WAITING_DAY}: Recibido '{text}' de {chat_id}")
    if text == config.BTN_CANCELAR_ACCION: logger.info(f"Cancelación {chat_id}"); await utils.cancel_action(update, context); return
    day_str = text.capitalize()
    if day_str in config.DAY_LIST:
        logger.info(f"Día elegido {chat_id}: {day_str}")
        target_date = gcal.get_next_weekday_date(day_str)
        if not target_date: logger.error(f"Error fecha {day_str}"); await update.message.reply_text("Error fecha.", reply_markup=keyboards.create_day_keyboard()); return
        req_data = context.user_data.get('appointment_request'); doctor = req_data.get('doctor')
        if not req_data or not doctor: logger.error(f"Error {chat_id}: Falta doctor"); await update.message.reply_text("Error interno.", reply_markup=keyboards.main_menu_markup); await utils.send_main_menu(update,context); return
        req_data['day'] = day_str; req_data['date_obj'] = target_date
        calendar_service = context.bot_data.get('calendar_service')
        if not calendar_service: logger.error("Error GCal Svc"); await update.message.reply_text("Error calendario.", reply_markup=keyboards.main_menu_markup); await utils.send_main_menu(update, context); return
        logger.info(f"Consultando GCal Dr.{doctor} en {target_date.isoformat()}")
        disponible_slots = gcal.check_google_calendar_availability(calendar_service, doctor, target_date)
        if disponible_slots:
            context.user_data['state'] = config.STATE_WAITING_TIMESLOT
            markup = keyboards.create_timeslot_keyboard(disponible_slots)
            await update.message.reply_text(f"Horarios para Dr./Dra. {doctor} el {day_str} ({target_date.strftime('%d/%m')}):", reply_markup=markup)
        else:
            markup = keyboards.create_day_keyboard()
            await update.message.reply_text(f"No hay horarios para Dr./Dra. {doctor} el {day_str}. Elige otro día o cancela.", reply_markup=markup)
    else:
        markup = keyboards.create_day_keyboard()
        await update.message.reply_text(f"'{text}' no es día válido. Elige o '{config.BTN_CANCELAR_ACCION}'.", reply_markup=markup)

async def handle_turno_solicitar_hora(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id; user = update.effective_user
    selected_time = text
    logger.debug(f"State {config.STATE_WAITING_TIMESLOT}: Recibido '{text}' de {chat_id}")
    if text == config.BTN_CANCELAR_ACCION: logger.info(f"Cancelación {chat_id}"); await utils.cancel_action(update, context); return
    try: datetime.datetime.strptime(selected_time, '%H:%M'); valid_time = True
    except ValueError: valid_time = False
    req_data = context.user_data.get('appointment_request', {}); doctor = req_data.get('doctor'); day_str = req_data.get('day'); target_date = req_data.get('date_obj'); calendar_service = context.bot_data.get('calendar_service')
    if not doctor or not day_str or not target_date or not calendar_service: logger.error(f"Error {chat_id}: Faltan datos"); await update.message.reply_text("Error interno.", reply_markup=keyboards.main_menu_markup); await utils.send_main_menu(update, context); return
    if not valid_time:
        logger.warning(f"Hora inválida '{selected_time}' {chat_id}")
        disponible_slots = gcal.check_google_calendar_availability(calendar_service, doctor, target_date)
        markup = keyboards.create_timeslot_keyboard(disponible_slots)
        await update.message.reply_text(f"Formato hora '{selected_time}' inválido (HH:MM). Elige o cancela.", reply_markup=markup); return
    logger.info(f"Horario elegido {chat_id}: {selected_time}")
    logger.info(f"Verificando GCal Dr.{doctor} a {selected_time} en {target_date.isoformat()}")
    available_slots_now = gcal.check_google_calendar_availability(calendar_service, doctor, target_date)
    if selected_time not in available_slots_now:
        logger.warning(f"Slot Ocupado {chat_id}: {selected_time} Dr.{doctor} {target_date.isoformat()}")
        markup = keyboards.create_timeslot_keyboard(available_slots_now)
        await update.message.reply_text(f"El horario {selected_time} fue ocupado. Disponibles:", reply_markup=markup); return
    logger.info(f"Slot {selected_time} OK. Creando evento GCal...")
    success, event_link = gcal.create_google_calendar_event(calendar_service, doctor, day_str, selected_time, user.to_dict())
    if success:
        await update.message.reply_text(f"¡Turno confirmado! Dr./Dra. {doctor} el {day_str} a las {selected_time}.\nVer: {event_link or 'No disp.'}\n\nVolviendo...", reply_markup=keyboards.main_menu_markup, disable_web_page_preview=True)
        logger.info(f"Turno creado GCal {chat_id}. Link: {event_link}")
    else:
        await update.message.reply_text("Error al agendar. Contacta secretaría.", reply_markup=keyboards.main_menu_markup)
        logger.error(f"Fallo GCal create event {chat_id} Dr:{doctor} {day_str} {selected_time}")
    context.user_data.clear()
    await utils.send_main_menu(update, context, "Puedes elegir otra opción:")

async def handle_request_cancel_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; chat_id = update.effective_chat.id
    if not user: return
    logger.info(f"Iniciando flujo cancelación UserID:{user.id}")
    calendar_service = context.bot_data.get('calendar_service')
    if not calendar_service: logger.error("Error GCal Svc"); await update.message.reply_text("Error calendario."); return
    user_appointments = gcal.find_all_user_appointments(calendar_service, user.to_dict())
    if not user_appointments: logger.info(f"No hay turnos futuros UserID:{user.id}"); await update.message.reply_text("No encontré turnos futuros."); return
    logger.info(f"Encontrados {len(user_appointments)} turnos UserID:{user.id}. Mostrando.")
    cancel_keyboard_markup = keyboards.create_cancel_appointments_keyboard(user_appointments)
    if not cancel_keyboard_markup: logger.warning(f"No se pudo crear teclado cancel UserID:{user.id}"); await update.message.reply_text("Problema al mostrar turnos. Contacta secretaría."); return
    await update.message.reply_text( "Turnos futuros encontrados. ¿Cuál deseas cancelar?", reply_markup=cancel_keyboard_markup )

async def handle_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer()
    callback_data = query.data; user_id = query.from_user.id
    logger.info(f"Callback cancelar: '{callback_data}' UserID:{user_id}")
    if not callback_data or not callback_data.startswith(config.CALLBACK_PREFIX_CANCEL): logger.warning(f"Callback inválido: {callback_data}"); await query.edit_message_text(text="Error: Botón inválido."); return
    try:
        parts = callback_data.split('_');
        if len(parts) != 3: raise ValueError("Formato callback")
        _, event_id, doctor_key = parts
        calendar_id = config.CALENDAR_IDS_DOCTORES.get(doctor_key)
        if not calendar_id: logger.error(f"No cal_id para key '{doctor_key}'"); raise ValueError("Key doctor inválido")
    except Exception as e: logger.error(f"Error parseando callback '{callback_data}': {e}"); await query.edit_message_text(text="Error procesando."); return
    logger.info(f"Intentando cancelar EventoID:{event_id} CalID:{calendar_id} (Key:{doctor_key}) UserID:{user_id}")
    calendar_service = context.bot_data.get('calendar_service')
    if not calendar_service: logger.error("Error GCal Svc"); await query.edit_message_text(text="Error conexión calendario."); return
    success = gcal.delete_google_calendar_event(calendar_service, calendar_id, event_id)
    if success: logger.info(f"Evento {event_id} cancelado UserID:{user_id}."); await query.edit_message_text(text=f"✅ ¡Turno cancelado!\n({doctor_key} ID: ...{event_id[-6:]})")
    else: logger.error(f"Fallo cancelar evento {event_id} UserID:{user_id}."); await query.edit_message_text(text="❌ Error al cancelar. Contacta secretaría.")

async def handle_turno_sub_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Turno -> Sub-Opción '{text}'")
    context.user_data['handled_in_group_0'] = True
    logger.debug(f"Bandera G0 set en handle_turno_sub_choice para '{text}'")
    if text == config.BTN_TURNO_SOLICITAR:
        logger.debug(f"{chat_id}: Iniciando flujo solicitar turno.")
        await update.message.reply_text("¿Con qué doctor?", reply_markup=keyboards.create_doctor_keyboard())
        context.user_data['state'] = config.STATE_WAITING_DOCTOR
    elif text == config.BTN_TURNO_ELIMINAR:
        logger.debug(f"{chat_id}: Iniciando NUEVO flujo cancelar (buscar todos).")
        await handle_request_cancel_appointment(update, context)
    elif text == config.BTN_TURNO_EDITAR: logger.debug(f"{chat_id}: Editar (placeholder)."); await update.message.reply_text("Editar no implementado.", reply_markup=keyboards.turno_menu_markup)
    elif text == config.BTN_TURNO_VIDEO: logger.debug(f"{chat_id}: Info videollamada."); await update.message.reply_text("Info Videollamada: [Detalles].", reply_markup=keyboards.turno_menu_markup)
    elif text == config.BTN_TURNO_DOCTOR: logger.debug(f"{chat_id}: Mostrando doctores."); await update.message.reply_text(f"Doctores: {', '.join(config.DOCTOR_LIST)}.", reply_markup=keyboards.turno_menu_markup)
    elif text == config.BTN_TURNO_SECRETARIA: logger.debug(f"{chat_id}: Comunicar secretaría."); await update.message.reply_text("Escribe tu mensaje:", reply_markup=keyboards.cancel_markup); context.user_data['state'] = config.STATE_TALKING_TO_SECRETARY
    else: logger.warning(f"Opción no reconocida handle_turno_sub_choice: {text}"); await update.message.reply_text("Opción no reconocida.", reply_markup=keyboards.turno_menu_markup)

async def handle_turno_editar_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id; text = update.message.text if update.message else "N/A"
    logger.info(f"Chat {chat_id}: Placeholder Editar Turno (Estado {context.user_data.get('state')}, Texto: {text})")
    await update.message.reply_text("Editar no implementado.\nVolviendo...", reply_markup=keyboards.main_menu_markup)
    context.user_data.clear();
    await utils.send_main_menu(update, context)