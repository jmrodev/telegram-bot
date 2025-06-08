require('dotenv').config(); // Load environment variables from .env

const config = {
    // --- Telegram Configuration ---
    telegramToken: process.env.TELEGRAM_TOKEN,

    // --- Google Calendar Configuration ---
    googleCloudProjectId: process.env.GCAL_PROJECT_ID,
    googleClientEmail: process.env.GCAL_CLIENT_EMAIL,
    googlePrivateKey: process.env.GCAL_PRIVATE_KEY ? process.env.GCAL_PRIVATE_KEY.replace(/\\n/g, '\n') : null,
    // Or if using GOOGLE_APPLICATION_CREDENTIALS:
    // googleApplicationCredentials: process.env.GOOGLE_APPLICATION_CREDENTIALS,
    googleCalendarScopes: ['https://www.googleapis.com/auth/calendar'],
    timezone: "America/Argentina/Buenos_Aires",

    calendarIdsDoctores: {
        "Dr. Pérez": "ID_CALENDARIO_PEREZ@group.calendar.google.com",
        "Dra. Gómez": "ID_CALENDARIO_GOMEZ@group.calendar.google.com",
        "Dr. Rodríguez": "chello1975@gmail.com"
    },

    // --- Bot Data Configuration ---
    dayList: ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"],

    // Button Texts (ReplyKeyboard)
    buttons: {
        turno: "📅 Turno", receta: "℞ Receta", pago: "💲 Pago",
        turnoSolcitar: "➕ Solicitar Turno", turnoEliminar: "🗑️ Cancelar Turno",
        turnoEditar: "✏️ Editar Turno Existente", turnoVideo: "📹 Videollamada",
        turnoDoctor: "👨‍⚕️ ¿Con qué doctor?", turnoSecretaria: "🧑‍💼 Comunicarse con Secretaría",
        recetaSolicitar: "💊 Solicitar Nueva", recetaCorregir: "✍️ Corregir Existente",
        recetaConsultarEstado: "Consultar Estado de Receta",
        pagoTransferencia: "🏦 Transferencia", pagoConsultorio: "🏢 En Consultorio",
        pagoOnlineInfo: "Información de Pago Online",
        pagoRecordatorioInfo: "Información de Recordatorio de Pago",
        volver: "🔙 Volver al Menú Principal", cancelarAccion: "🚫 Cancelar Acción Actual"
    },

    // Callback Data Prefixes
    callbackPrefixes: {
        cancel: "cancel_",
        edit: "edit_", // Added from turno.py placeholders
        proceedEdit: "proceed_edit_", // Added from turno.py placeholders
        abortEdit: "abort_edit_", // Added from turno.py placeholders
        finalizeEdit: "finalize_edit_", // Added from turno.py placeholders
        cancelFinalizeEdit: "cancel_finalize_" // Added from turno.py placeholders
    },

    // Conversation States
    states: {
        waitingDoctor: 'turno_awaiting_doctor',
        waitingDay: 'turno_awaiting_day',
        waitingTimeslot: 'turno_awaiting_timeslot',
        editAwaitingDate: 'edit_awaiting_date', // Placeholder
        recipeAwaitingInfo: 'receta_awaiting_info_or_photo',
        recipeAwaitingCorrection: 'receta_awaiting_correction_info_photo',
        talkingToSecretary: 'talking_to_secretary',
        // Edit flow states from turno.py placeholders
        editSelectAppointment: 'edit_select_appointment',
        editAwaitingConfirmation: 'edit_awaiting_confirmation',
        editAwaitingNewDay: 'edit_awaiting_new_day',
        editAwaitingNewTimeslot: 'edit_awaiting_new_timeslot',
        editAwaitingFinalConfirmation: 'edit_awaiting_final_confirmation'
    },

    // Other settings
    officeStartHour: 9,
    officeEndHour: 18,
    slotDurationMinutes: 30,
    secretaryChatId: process.env.SECRETARY_CHAT_ID || null,
    officeAddress: "Calle Falsa 123, Tandil",
    officeHours: "Lunes a Viernes de 9:00 a 18:00",
    maxCancelButtons: 15,

    // Derived configurations (similar to Python's dynamic ones)
    get doctorList() {
        return Object.keys(this.calendarIdsDoctores);
    },
    get doctorNamesFromId() {
        const map = {};
        for (const doctor in this.calendarIdsDoctores) {
            map[this.calendarIdsDoctores[doctor]] = doctor;
        }
        return map;
    }
};

module.exports = config;
