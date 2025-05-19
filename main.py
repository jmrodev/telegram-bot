# main.py
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    PicklePersistence, CallbackQueryHandler # Añadir CallbackQueryHandler
)
import config
import keyboards
# Importar módulos de handlers desde la carpeta 'handlers'
from handlers import common, turno, receta, pago, misc, utils # Importar utils también
import google_calendar_utils as gcal

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__) # Usar __name__ es estándar

# --- Función Principal ---
def main() -> None:
    """Inicia el bot y configura los handlers."""
    calendar_service = gcal.get_calendar_service()
    if not calendar_service:
        logger.critical("¡ERROR CRÍTICO GCal! Bot NO iniciado.")
        return

    logger.info(f"Iniciando bot...") # Mensaje de inicio simplificado

    application = ( Application.builder().token(config.TELEGRAM_TOKEN)
        .build() )

    application.bot_data['calendar_service'] = calendar_service
    logger.info("Servicio Google Calendar añadido a application.bot_data.")

    # --- Registrar Handlers ---
    # Grupo 0 (por defecto) - Mayor prioridad

    # Comando /start
    application.add_handler(CommandHandler("start", common.start))

    # Botones globales (que no dependen de menú anterior)
    application.add_handler(MessageHandler(filters.Text([config.BTN_CANCELAR_ACCION]), utils.cancel_action))
    application.add_handler(MessageHandler(filters.Text([config.BTN_VOLVER]), utils.send_main_menu))

    # Manejador de Fotos
    application.add_handler(MessageHandler(filters.PHOTO, receta.handle_photo))

    # Botones Menú Principal
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO]), turno.handle_turno_menu))
    application.add_handler(MessageHandler(filters.Text([config.BTN_RECETA]), receta.handle_receta_menu))
    application.add_handler(MessageHandler(filters.Text([config.BTN_PAGO]), pago.handle_pago_menu))

    # Botones Sub-Menús (Llaman a funciones _sub_choice)
    # Turno
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_SOLICITAR]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_ELIMINAR]), turno.handle_turno_sub_choice)) # Ahora llama a la nueva lógica dentro de sub_choice
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_EDITAR]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_VIDEO]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_DOCTOR]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_SECRETARIA]), turno.handle_turno_sub_choice))
    # Receta
    application.add_handler(MessageHandler(filters.Text([config.BTN_RECETA_SOLICITAR]), receta.handle_receta_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_RECETA_CORREGIR]), receta.handle_receta_sub_choice))
    # Pago
    application.add_handler(MessageHandler(filters.Text([config.BTN_PAGO_TRANFERENCIA]), pago.handle_pago_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_PAGO_CONSULTORIO]), pago.handle_pago_sub_choice))

    # --- NUEVO: CallbackQueryHandler para botones inline ---
    # Captura todos los callbacks que empiezan con el prefijo definido en config
    application.add_handler(CallbackQueryHandler(turno.handle_cancel_callback, pattern=f"^{config.CALLBACK_PREFIX_CANCEL}"))
    # Puedes añadir más CallbackQueryHandlers para otros prefijos si es necesario

    # --- Manejador de texto general (Grupo 1 - Menor prioridad) ---
    # Maneja texto que NO coincide con botones y NO es comando (para flujos con estado)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, common.route_text_message_by_state), group=1)

    logger.info("Handlers registrados. Bot listo y escuchando actualizaciones...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()