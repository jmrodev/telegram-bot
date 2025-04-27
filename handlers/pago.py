# handlers/pago.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
import keyboards
from .utils import send_main_menu # <<< IMPORT DESDE UTILS

logger = logging.getLogger(__name__)

# --- PEGAR AQUÍ EL RESTO DE FUNCIONES DE PAGO DE LA VERSIÓN ANTERIOR ---
# handle_pago_menu, handle_pago_sub_choice
async def handle_pago_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Selecciona una opción para Pagos:", reply_markup=keyboards.pago_menu_markup)

async def handle_pago_sub_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Pago -> '{text}'")
    if text == config.BTN_PAGO_TRANFERENCIA: await update.message.reply_text("Datos Transferencia:\nCBU: [Tu CBU]\nAlias: [Tu Alias]\nTitular: [Nombre Titular]\nEnviar comprobante.", reply_markup=keyboards.pago_menu_markup)
    elif text == config.BTN_PAGO_CONSULTORIO: await update.message.reply_text("Puedes abonar en consultorio.", reply_markup=keyboards.pago_menu_markup)
    elif text == config.BTN_VOLVER: await send_main_menu(update, context)
    else:
        if not context.user_data.get('state'): await update.message.reply_text("Opción no reconocida.", reply_markup=keyboards.main_menu_markup); await send_main_menu(update, context)