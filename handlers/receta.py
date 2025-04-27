# handlers/receta.py
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
import config
import keyboards
from .utils import send_main_menu # <<< IMPORT DESDE UTILS

logger = logging.getLogger(__name__)

# --- PEGAR AQUÍ EL RESTO DE FUNCIONES DE RECETA DE LA VERSIÓN ANTERIOR ---
# handle_receta_menu, handle_receta_sub_choice, handle_receta_info_text,
# handle_receta_correction_text, handle_photo
async def handle_receta_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Selecciona una opción para Recetas:", reply_markup=keyboards.receta_menu_markup)

async def handle_receta_sub_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Receta -> '{text}'")
    current_state = context.user_data.get('state')
    if text != config.BTN_VOLVER and text in [config.BTN_RECETA_SOLICITAR, config.BTN_RECETA_CORREGIR] and current_state:
        await update.message.reply_text("Acción en curso. Cancelar ('🚫 ...') primero.", reply_markup=keyboards.receta_menu_markup); return

    if text == config.BTN_RECETA_SOLICITAR:
        await update.message.reply_text("Solicitar:\n1. Escribe nombre medicamento.\n2. O adjunta foto.\n('🚫 Cancelar Acción Actual')", reply_markup=keyboards.cancel_markup)
        context.user_data['state'] = config.STATE_RECIPE_AWAITING_INFO
    elif text == config.BTN_RECETA_CORREGIR:
        await update.message.reply_text("Corregir:\n1. Describe corrección.\n2. Adjunta foto receta.\n('🚫 Cancelar Acción Actual')", reply_markup=keyboards.cancel_markup)
        context.user_data['state'] = config.STATE_RECIPE_AWAITING_CORRECTION
    elif text == config.BTN_VOLVER: await send_main_menu(update, context)
    else:
       if not current_state: await update.message.reply_text("Opción no reconocida.", reply_markup=keyboards.main_menu_markup); await send_main_menu(update, context)

async def handle_receta_info_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id; user = update.effective_user
    logger.info(f"{chat_id}: Receta txt:'{text}'")
    log_msg=f"Receta(Txt):@{user.username or user.first_name}({chat_id}):{text}"
    logger.info(log_msg); # TODO: Notificar secretaria
    await update.message.reply_text("Info recibida. Si adjuntas foto, la añadiré. Volviendo.", reply_markup=keyboards.main_menu_markup)
    context.user_data.clear()

async def handle_receta_correction_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"{chat_id}: Corrección receta txt:'{text}'")
    context.user_data['correction_text'] = text # Guardar texto para asociar con foto
    await update.message.reply_text(f"Descrip:'{text}'. Adjunta foto receta a corregir o cancela.", reply_markup=keyboards.cancel_markup)
    # Mantenemos estado esperando foto

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id; user = update.effective_user
    current_state = context.user_data.get('state')
    if not update.message or not update.message.photo: logger.warning(f"handle_photo llamado sin foto?"); return
    photo_file_id = update.message.photo[-1].file_id; caption = update.message.caption or ""
    logger.info(f"Foto de {chat_id}(@{user.username or 'N/A'}), Estado:{current_state}, FileID:{photo_file_id}, Caption:'{caption}'")

    if current_state == config.STATE_RECIPE_AWAITING_INFO:
        logger.info(f"Foto NUEVA receta ({chat_id}).")
        log_msg = f"Receta(FOTO):\nPac:@{user.username or user.first_name}({chat_id})\nFileID:{photo_file_id}\nTexto:{caption or '(Sin texto)'}"
        logger.info(log_msg); # TODO: Notificar secretaria con log_msg (y tal vez file_id)
        await update.message.reply_text("Foto recibida. Secretaría procesará. Volviendo menú.", reply_markup=keyboards.main_menu_markup)
        context.user_data.clear()
    elif current_state == config.STATE_RECIPE_AWAITING_CORRECTION:
        logger.info(f"Foto CORREGIR receta ({chat_id}).")
        correction_text = context.user_data.pop('correction_text', caption or '(Sin texto adicional)')
        log_msg = f"Corrección Receta(FOTO):\nPac:@{user.username or user.first_name}({chat_id})\nFileID:{photo_file_id}\nDescrip:{correction_text}"
        logger.info(log_msg); # TODO: Notificar secretaria con log_msg (y file_id)
        await update.message.reply_text("Foto y descrip recibidas. Secretaría revisará. Volviendo menú.", reply_markup=keyboards.main_menu_markup)
        context.user_data.clear()
    else:
        logger.info(f"Foto {chat_id} fuera de flujo. Ignorando.")
        await update.message.reply_text("Recibí foto, pero no la esperaba. Usa /start.")