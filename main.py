# main.py
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    PicklePersistence # Opcional
)
import config
# Importar módulos de handlers desde la carpeta 'handlers'
from handlers import common, turno, receta, pago, misc
import google_calendar_utils as gcal

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Persistencia (Opcional) ---
# persistence = PicklePersistence(filepath="bot_persistence")

# --- Función Principal ---
def main() -> None:
    """Inicia el bot y configura los handlers."""
    calendar_service = gcal.get_calendar_service()
    if not calendar_service: logger.critical("¡ERROR CRÍTICO GCal! Bot NO iniciado."); return

    logger.info(f"Iniciando bot v1.5 (Refactorizado v2)... Cargando config para {len(config.DOCTOR_LIST)} doctores.")
    application = ( Application.builder().token(config.TELEGRAM_TOKEN)
        # .persistence(persistence) # Descomentar para persistencia
        .build() )

    # Guardar servicio de GCal en contexto del bot
    application.bot_data['calendar_service'] = calendar_service
    logger.info("Servicio Google Calendar añadido a bot_data.")

    # --- Registrar Handlers ---
    # Comandos básicos
    application.add_handler(CommandHandler("start", common.start))
    application.add_handler(MessageHandler(filters.Text([config.BTN_CANCELAR_ACCION]), common.cancel_action))

    # Manejador de fotos (va a receta)
    application.add_handler(MessageHandler(filters.PHOTO, receta.handle_photo))

    # Manejadores para los botones de los menús principales y secundarios
    # (Usando filtros de texto exacto para mayor claridad)
    # Menú Principal
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO]), turno.handle_turno_menu))
    application.add_handler(MessageHandler(filters.Text([config.BTN_RECETA]), receta.handle_receta_menu))
    application.add_handler(MessageHandler(filters.Text([config.BTN_PAGO]), pago.handle_pago_menu))

    # Sub-Menú Turno
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_SOLICITAR]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_ELIMINAR]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_EDITAR]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_VIDEO]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_DOCTOR]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_TURNO_SECRETARIA]), turno.handle_turno_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_VOLVER]), common.send_main_menu)) # Volver siempre va al menú principal

    # Sub-Menú Receta
    application.add_handler(MessageHandler(filters.Text([config.BTN_RECETA_SOLICITAR]), receta.handle_receta_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_RECETA_CORREGIR]), receta.handle_receta_sub_choice))
    # Volver ya está cubierto arriba

    # Sub-Menú Pago
    application.add_handler(MessageHandler(filters.Text([config.BTN_PAGO_TRANFERENCIA]), pago.handle_pago_sub_choice))
    application.add_handler(MessageHandler(filters.Text([config.BTN_PAGO_CONSULTORIO]), pago.handle_pago_sub_choice))
    # Volver ya está cubierto arriba


    # Manejador de texto general (grupo 1 para menor prioridad)
    # Este SÓLO se activará si el texto NO coincide con ningún botón de arriba Y no es un comando.
    # Llama a la función 'route_text_message_by_state' en common.py que decide qué hacer según el ESTADO.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, common.route_text_message_by_state), group=1)

    logger.info("Bot listo y escuchando...")
    application.run_polling(allowed_updates=Update.ALL_TYPES) # Recibir todos los tipos de updates

if __name__ == '__main__':
    main()