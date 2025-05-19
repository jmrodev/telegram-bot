# handlers/pago.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
import keyboards
# Asegúrate que utils está correctamente importado
from . import utils # Importar utils directamente

# Añadido logger
logger = logging.getLogger(__name__)

async def handle_pago_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Log al inicio de la función
    logger.info(f"-> Entrando en handle_pago_menu (Chat ID: {update.effective_chat.id})")
    try: # Envolver en try/except
        await update.message.reply_text("Selecciona una opción para Pagos:", reply_markup=keyboards.pago_menu_markup)
        # --- AÑADIR BANDERA ---
        context.user_data['handled_in_group_0'] = True
        # ------------------------
        logger.info(f"<- Saliendo de handle_pago_menu (Respuesta enviada, bandera establecida)")
    except Exception as e:
         logger.error(f"!! ERROR dentro de handle_pago_menu: {e}", exc_info=True)
         try:
             await update.message.reply_text("Ocurrió un error al mostrar el menú de pagos.")
         except Exception as e_reply:
             logger.error(f"!! ERROR enviando mensaje de error en handle_pago_menu: {e_reply}")


async def handle_pago_sub_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Maneja botones DENTRO del menú de pagos
    text = update.message.text; chat_id = update.effective_chat.id
    logger.info(f"Chat {chat_id}: Menú Pago -> Sub-Opción '{text}'")
    # --- AÑADIR BANDERA TAMBIÉN AQUÍ ---
    context.user_data['handled_in_group_0'] = True
    logger.debug(f"Bandera handled_in_group_0 establecida en handle_pago_sub_choice para '{text}'")
    # ------------------------------------
    current_state = context.user_data.get('state') # Verificar estado por si acaso

    # Prevenir acción si hay un estado activo (poco probable aquí, pero por seguridad)
    if text != config.BTN_VOLVER and current_state:
        await update.message.reply_text("Parece que hay otra acción en curso. Cancela ('🚫 ...') o completa la acción actual primero.", reply_markup=keyboards.pago_menu_markup)
        return

    if text == config.BTN_PAGO_TRANFERENCIA:
        transfer_details = ( # Usar f-string o .format para insertar datos reales si los tienes en config
            "Datos para Transferencia Bancaria:\n"
            "-------------------------------------\n"
            f"Banco: [Nombre Banco]\n"
            f"Titular: [Nombre Titular]\n"
            f"Tipo Cuenta: [Tipo Cuenta]\n"
            f"Nro Cuenta: [Numero Cuenta]\n"
            f"CBU: [CBU]\n"
            f"Alias: [Alias]\n"
            f"CUIT/CUIL: [CUIT/CUIL]\n"
            "-------------------------------------\n"
            "Importante: Envía el comprobante de pago una vez realizada."
        )
        await update.message.reply_text(transfer_details, reply_markup=keyboards.pago_menu_markup)
        logger.debug(f"Mostrando detalles de transferencia a {chat_id}")
    elif text == config.BTN_PAGO_CONSULTORIO:
        office_payment_info = (
            "Puedes abonar tu consulta directamente en el consultorio.\n"
            "Medios de pago aceptados:\n"
            "- Efectivo\n"
            "- Tarjetas Débito/Crédito\n"
            "- Mercado Pago (QR)\n\n"
            f"Dirección: {config.OFFICE_ADDRESS if hasattr(config, 'OFFICE_ADDRESS') else '[Dirección Consultorio]'}\n" # Ejemplo si tuvieras la dirección en config
            f"Horario Secretaría: {config.OFFICE_HOURS if hasattr(config, 'OFFICE_HOURS') else '[Horario Secretaría]'}"
        )
        await update.message.reply_text(office_payment_info, reply_markup=keyboards.pago_menu_markup)
        logger.debug(f"Mostrando info de pago en consultorio a {chat_id}")
    elif text == config.BTN_VOLVER:
        # El botón Volver genérico es manejado directamente en main.py por utils.send_main_menu
        logger.warning(f"{chat_id}: Botón Volver procesado inesperadamente en handle_pago_sub_choice. Redirigiendo a utils.send_main_menu.")
        await utils.send_main_menu(update, context)
    else:
        # Opción no reconocida dentro del menú de pagos
        logger.warning(f"Opción no reconocida en handle_pago_sub_choice: {text}")
        await update.message.reply_text("Opción no reconocida dentro del menú de pagos.", reply_markup=keyboards.pago_menu_markup)