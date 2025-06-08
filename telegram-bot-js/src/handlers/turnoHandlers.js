// telegram-bot-js/src/handlers/turnoHandlers.js
const config = require('../../config/config');
const keyboards = require('../keyboards/keyboards');
const { sendMainMenu, cancelAction } = require('../utils'); // Corrected path
// const gcal = require('../services/googleCalendar'); // Will be needed for actual logic

// --- Existing Placeholder functions (from textHandler setup) ---
async function handleTurnoSolicitarDoctor(ctx) {
    console.log('Placeholder: handleTurnoSolicitarDoctor called with text:', ctx.message.text);
    // This function is typically called when state IS waitingDoctor, so it processes the doctor's name
    await ctx.reply(`Placeholder: Lógica para procesar selección de doctor: ${ctx.message.text}. Siguiente: pedir día.`);
    // Example: ctx.session.state = config.states.waitingDay;
    // await ctx.reply('Ahora elige el día:', keyboards.createDayKeyboard());
}
async function handleTurnoSolicitarDia(ctx) {
    console.log('Placeholder: handleTurnoSolicitarDia called with text:', ctx.message.text);
    await ctx.reply(`Placeholder: Lógica para procesar selección de día: ${ctx.message.text}. Siguiente: pedir hora.`);
    // Example: ctx.session.state = config.states.waitingTimeslot;
    // await ctx.reply('Ahora elige la hora:', keyboards.createTimeslotKeyboard(['09:00', '09:30']));
}
async function handleTurnoSolicitarHora(ctx) {
    console.log('Placeholder: handleTurnoSolicitarHora called with text:', ctx.message.text);
    await ctx.reply(`Placeholder: Lógica para procesar selección de hora: ${ctx.message.text}. Finalizar turno.`);
    // Example: await sendMainMenu(ctx, 'Turno solicitado (placeholder).');
}

// --- New/Updated Turno Handlers ---

/**
 * Displays the main Turno (appointment) menu.
 * Called when user presses the "📅 Turno" button from the main menu.
 * @param {object} ctx - Telegraf context object.
 */
async function handleTurnoMenu(ctx) {
    console.log(`User ${ctx.from?.id}: Displaying Turno Menu.`);
    try {
        await ctx.reply("Selecciona una opción para Turnos:", keyboards.turnoMenu);
    } catch (error) {
        console.error(`Error in handleTurnoMenu for user ${ctx.from?.id}:`, error);
        await ctx.reply("Ocurrió un error al mostrar el menú de turnos. Por favor, intenta de nuevo.");
    }
}

// --- Placeholder functions for sub-choices ---
async function handleTurnoSolicitar(ctx) {
    console.log(`User ${ctx.from?.id}: Initiating 'Solicitar Turno' flow.`);
    // Set state and ask for doctor
    ctx.session.state = config.states.waitingDoctor;
    await ctx.reply("¿Con qué doctor deseas el turno?", keyboards.createDoctorKeyboard());
    console.log(`State set to ${config.states.waitingDoctor} for user ${ctx.from?.id}.`);
}

async function handleRequestCancelAppointment(ctx) {
    console.log(`User ${ctx.from?.id}: Initiating 'Cancelar Turno' flow (placeholder).`);
    // Actual logic will call gcal.findAllUserAppointments and show inline keyboard
    await ctx.reply("Placeholder: Aquí se mostrarán tus turnos para cancelar. Esta función requiere integración con Google Calendar.");
    // For now, return to turno menu to avoid dead end
    await ctx.reply("Volviendo al menú de turnos.", keyboards.turnoMenu);
}

async function requestAppointmentToEdit(ctx) {
    console.log(`User ${ctx.from?.id}: Initiating 'Editar Turno' flow (placeholder).`);
    // Actual logic will call gcal.findAllUserAppointments and show inline keyboard for editing
    await ctx.reply("Placeholder: Aquí se mostrarán tus turnos para editar. Esta función requiere integración con Google Calendar.");
    // ctx.session.state = config.states.editSelectAppointment; // Set when inline keyboard is shown
    // For now, return to turno menu
    await ctx.reply("Volviendo al menú de turnos.", keyboards.turnoMenu);
}

async function displayVideoCallInfo(ctx) {
    console.log(`User ${ctx.from?.id}: Requesting video call info.`);
    // Assuming VIDEO_CALL_INFO_TEXT is defined in your main config object in config.js
    // If not, you'll need to add it there.
    const videoInfo = config.videoCallInfoText || "La información sobre videollamadas actualmente no está disponible. Por favor, consulta más tarde.";
    await ctx.reply(videoInfo, keyboards.turnoMenu); // Keep user in turnoMenu
}

async function displayDoctorList(ctx) {
    console.log(`User ${ctx.from?.id}: Requesting doctor list.`);
    const doctorListStr = config.doctorList.length > 0 ? config.doctorList.join(', ') : "No hay doctores configurados actualmente.";
    await ctx.reply(`Doctores disponibles: ${doctorListStr}.`, keyboards.turnoMenu); // Keep user in turnoMenu
}

async function initiateSecretaryContact(ctx) {
    console.log(`User ${ctx.from?.id}: Initiating contact with secretary.`);
    ctx.session.state = config.states.talkingToSecretary;
    await ctx.reply("Por favor, escribe tu mensaje para la secretaría. Para cancelar, usa el botón provisto.", keyboards.cancelActionMenu);
    console.log(`State set to ${config.states.talkingToSecretary} for user ${ctx.from?.id}.`);
}


/**
 * Handles sub-choices from the Turno menu.
 * Called when user presses a button from the turnoMenu.
 * @param {object} ctx - Telegraf context object.
 */
async function handleTurnoSubChoice(ctx) {
    const userId = ctx.from?.id;
    const text = ctx.message?.text;
    console.log(`User ${userId}: Turno sub-choice -> '${text}'`);

    try {
        // If user is in a state and tries a new action (other than Volver)
        // it's better to ask them to cancel the current action.
        if (text !== config.buttons.volver && ctx.session?.state) {
            console.warn(`User ${userId} (state: ${ctx.session.state}) tried Turno option '${text}' without cancelling.`);
            await ctx.reply(
                "Estás en medio de otra acción. Por favor, primero cancela la acción actual usando el botón '🚫 Cancelar Acción Actual' si deseas iniciar una nueva.",
                keyboards.cancelActionMenu // Provide the cancel action menu
            );
            return;
        }

        // Route based on button text
        if (text === config.buttons.turnoSolcitar) {
            await handleTurnoSolicitar(ctx);
        } else if (text === config.buttons.turnoEliminar) {
            await handleRequestCancelAppointment(ctx);
        } else if (text === config.buttons.turnoEditar) {
            await requestAppointmentToEdit(ctx);
        } else if (text === config.buttons.turnoVideo) {
            await displayVideoCallInfo(ctx);
        } else if (text === config.buttons.turnoDoctor) {
            await displayDoctorList(ctx);
        } else if (text === config.buttons.turnoSecretaria) {
            await initiateSecretaryContact(ctx);
        } else if (text === config.buttons.volver) {
            // sendMainMenu already clears state
            await sendMainMenu(ctx, "Has vuelto al menú principal.");
        } else {
            console.warn(`Unrecognized sub-option '${text}' in handleTurnoSubChoice from user ${userId}. This should not happen if bot.hears is specific.`);
            await ctx.reply("Opción no reconocida dentro del menú de turnos. Por favor, elige una de las opciones disponibles.", keyboards.turnoMenu);
        }
    } catch (error) {
        console.error(`Error in handleTurnoSubChoice for user ${userId}, text '${text}':`, error);
        await ctx.reply("Ocurrió un error al procesar tu selección de turno. Por favor, intenta de nuevo.");
        // Optionally, send to main menu on error to reset flow
        // await sendMainMenu(ctx, "Debido a un error, hemos cancelado la acción anterior.");
    }
}

module.exports = {
    handleTurnoMenu,
    handleTurnoSubChoice,
    // Exporting existing state handlers
    handleTurnoSolicitarDoctor,
    handleTurnoSolicitarDia,
    handleTurnoSolicitarHora,
    // Exporting new action handlers
    handleTurnoSolicitar, // This initiates the flow
    handleRequestCancelAppointment,
    requestAppointmentToEdit, // This initiates the edit flow
    displayVideoCallInfo,
    displayDoctorList,
    initiateSecretaryContact
};
