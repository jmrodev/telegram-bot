// telegram-bot-js/src/keyboards/keyboards.js
const { Markup } = require('telegraf');
const config = require('../../config/config'); // Adjust path as needed

// --- Fixed ReplyKeyboards ---
const mainMenu = Markup.keyboard([
    [config.buttons.turno],
    [config.buttons.receta, config.buttons.pago],
]).resize();

const turnoMenu = Markup.keyboard([
    [config.buttons.turnoSolcitar],
    [config.buttons.turnoEliminar, config.buttons.turnoEditar],
    [config.buttons.turnoVideo, config.buttons.turnoDoctor],
    [config.buttons.turnoSecretaria],
    [config.buttons.volver],
]).resize();

const recetaMenu = Markup.keyboard([
    [config.buttons.recetaSolicitar],
    [config.buttons.recetaCorregir],
    [config.buttons.recetaConsultarEstado],
    [config.buttons.volver],
]).resize();

const pagoMenu = Markup.keyboard([
    [config.buttons.pagoOnlineInfo],
    [config.buttons.pagoTransferencia],
    [config.buttons.pagoConsultorio],
    [config.buttons.pagoRecordatorioInfo],
    [config.buttons.volver],
]).resize();

const cancelActionMenu = Markup.keyboard([
    [Markup.button.text(config.buttons.cancelarAccion)], // Ensure Markup.button.text is used for ReplyKeyboard
]).resize().oneTime(); // one_time_keyboard equivalent

// --- Dynamic ReplyKeyboards ---
function createDoctorKeyboard() {
    const doctorButtons = config.doctorList.map(doc => [Markup.button.text(doc)]);
    return Markup.keyboard([
        ...doctorButtons,
        [Markup.button.text(config.buttons.cancelarAccion)],
    ]).resize().oneTime();
}

function createDayKeyboard() {
    const dayButtons = config.dayList.map(day => [Markup.button.text(day)]);
    return Markup.keyboard([
        ...dayButtons,
        [Markup.button.text(config.buttons.cancelarAccion)],
    ]).resize().oneTime();
}

function createTimeslotKeyboard(slots) {
    if (!slots || slots.length === 0) {
        // If no slots, provide a keyboard that still allows cancelling the action.
        return Markup.keyboard([
            [Markup.button.text(config.buttons.cancelarAccion)],
        ]).resize().oneTime();
    }
    const timeslotButtons = slots.map(slot => [Markup.button.text(slot)]);
    return Markup.keyboard([
        ...timeslotButtons,
        [Markup.button.text(config.buttons.cancelarAccion)],
    ]).resize().oneTime();
}

// --- Dynamic InlineKeyboards ---

/**
 * Creates an InlineKeyboardMarkup for managing specific appointments (cancel/edit).
 * @param {object[]} appointments - List of appointment objects.
 * @param {string} buttonTextPrefix - Prefix for the button text (e.g., "🚫 Cancelar").
 * @param {string} callbackPrefix - Prefix for the callback_data.
 * @returns {Markup.Markup<import('telegraf/typings/core/types/typegram').InlineKeyboardMarkup>|null}
 */
function createAppointmentsInlineKeyboard(appointments, buttonTextPrefix, callbackPrefix) {
    if (!appointments || appointments.length === 0) {
        return null;
    }

    const keyboard = appointments.reduce((acc, appt) => {
        const eventId = appt.eventId;
        const doctorKey = appt.doctorKey;
        const doctorName = appt.doctorName || config.doctorNamesFromId[appt.calendarId] || 'Dr.?'; // Fallback for doctorName
        const displayTime = appt.displayDateTime || 'Fecha?';

        if (!eventId || !doctorKey) {
            console.warn('Skipping appointment button due to missing eventId or doctorKey:', appt);
            return acc;
        }

        const buttonText = `${buttonTextPrefix} ${doctorName} - ${displayTime}`;
        // callback_prefix_eventId_doctorKey
        const callbackData = `${callbackPrefix}${eventId}_${doctorKey}`;

        // Telegram callback_data has a max length of 64 bytes.
        if (Buffer.from(callbackData).length <= 64) {
            acc.push([Markup.button.callback(buttonText, callbackData)]);
        } else {
            console.warn(`Callback data too long for button (max 64 bytes), button skipped: ${callbackData.substring(0, 20)}...`);
        }
        return acc;
    }, []);

    if (keyboard.length === 0) {
        return null; // No valid buttons could be created
    }
    return Markup.inlineKeyboard(keyboard);
}

/**
 * Creates an InlineKeyboardMarkup to confirm or cancel editing an appointment.
 * @param {string} eventId - The event ID.
 * @param {string} doctorKey - The doctor key.
 * @returns {Markup.Markup<import('telegraf/typings/core/types/typegram').InlineKeyboardMarkup>}
 */
function createEditConfirmationKeyboard(eventId, doctorKey) {
    return Markup.inlineKeyboard([
        Markup.button.callback("✅ Confirmar Edición", `${config.callbackPrefixes.proceedEdit}${eventId}_${doctorKey}`),
        Markup.button.callback("❌ Cancelar Edición", `${config.callbackPrefixes.abortEdit}${eventId}_${doctorKey}`),
    ]);
}

/**
 * Creates an InlineKeyboardMarkup for the final confirmation before rescheduling.
 * @param {string} placeholderData - Placeholder data for callback (actual data from context).
 * @returns {Markup.Markup<import('telegraf/typings/core/types/typegram').InlineKeyboardMarkup>}
 */
function createFinalizeEditKeyboard(placeholderData = "confirm") {
    const finalPlaceholderData = String(placeholderData);
    return Markup.inlineKeyboard([
        Markup.button.callback("✅ Confirmar y Reagendar", `${config.callbackPrefixes.finalizeEdit}${finalPlaceholderData}`),
        Markup.button.callback("❌ Cancelar Operación", `${config.callbackPrefixes.cancelFinalizeEdit}${finalPlaceholderData}`),
    ]);
}

module.exports = {
    mainMenu,
    turnoMenu,
    recetaMenu,
    pagoMenu,
    cancelActionMenu,
    createDoctorKeyboard,
    createDayKeyboard,
    createTimeslotKeyboard,
    createAppointmentsInlineKeyboard,
    createEditConfirmationKeyboard,
    createFinalizeEditKeyboard,
};
