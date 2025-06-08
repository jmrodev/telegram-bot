// telegram-bot-js/src/handlers/textHandler.js
const config = require('../../config/config');
const { sendMainMenu } = require('../utils'); // Corrected path: up one level to src/, then into utils.js
// Placeholder for actual handler modules - these will be created later
const turnoHandlers = require('./turnoHandlers');
const recetaHandlers = require('./recetaHandlers');
const miscHandlers = require('./miscHandlers');

/**
 * Handles text messages that are not commands and routes them based on user's current session state.
 * @param {object} ctx - Telegraf context object.
 */
async function routeTextMessageByState(ctx) {
    // Ensure gcalService is available (should be set by middleware in main.js)
    if (!ctx.gcalService) {
        console.error("GCal Service Missing in routeTextMessageByState. ctx.gcalService:", ctx.gcalService);
        await ctx.reply("Error: El servicio de calendario no está disponible. Por favor, intente más tarde o contacte a soporte.");
        return;
    }
    if (!ctx.message || !ctx.message.text) {
        console.warn("routeTextMessageByState called without message text. Update:", ctx.update);
        // Avoid acting on non-text messages in a text router
        return;
    }

    const text = ctx.message.text;
    const state = ctx.session?.state;
    const userId = ctx.from?.id;
    const chatId = ctx.chat?.id;

    console.log(`Router Texto x Estado: User ${userId} in chat ${chatId}, State: '${state || 'N/A'}', Text: '${text}'`);

    try {
        const stateActionMap = {
            [config.states.waitingDoctor]: turnoHandlers.handleTurnoSolicitarDoctor,
            [config.states.waitingDay]: turnoHandlers.handleTurnoSolicitarDia,
            [config.states.waitingTimeslot]: turnoHandlers.handleTurnoSolicitarHora,
            [config.states.editAwaitingDate]: turnoHandlers.handleTurnoEditarPlaceholder,
            [config.states.editAwaitingNewDay]: turnoHandlers.handleTurnoSolicitarDia,
            [config.states.editAwaitingNewTimeslot]: turnoHandlers.handleTurnoSolicitarHora,

            [config.states.recipeAwaitingInfo]: recetaHandlers.handleRecetaInfoText,
            [config.states.recipeAwaitingCorrection]: recetaHandlers.handleRecetaCorrectionText,
            [config.states.talkingToSecretary]: miscHandlers.handleSecretaryMessage,
            // Note: editSelectAppointment, editAwaitingConfirmation, editAwaitingFinalConfirmation
            // are typically handled by callback_query handlers, not general text.
        };

        if (state && stateActionMap[state]) {
            console.debug(`State '${state}' active for user ${userId}, calling corresponding handler.`);
            await stateActionMap[state](ctx);
        } else {
            console.debug(`User ${userId} has no active/mapped state ('${state}'). Treating as unknown text.`);
            await handleUnknownText(ctx);
        }
    } catch (error) {
        console.error(`Error in routeTextMessageByState for state '${state}', user ${userId}:`, error);
        const friendlyStateName = Object.keys(config.states).find(key => config.states[key] === state) || 'acción actual';
        try {
            await ctx.reply(`Hubo un problema al procesar tu solicitud para ${friendlyStateName}. Por favor, intenta de nuevo o cancela la acción.`);
        } catch (replyError) {
            console.error("Failed to send error reply in routeTextMessageByState:", replyError);
        }
        // Consider clearing state or sending to main menu on significant errors to avoid loops.
        // Example: await sendMainMenu(ctx, "Debido a un error, la acción anterior ha sido cancelada.");
    }
}

/**
 * Handles text messages that are not recognized as commands or part of a known conversation flow.
 * @param {object} ctx - Telegraf context object.
 */
async function handleUnknownText(ctx) {
    const userId = ctx.from?.id;
    const text = ctx.message?.text || "N/A"; // Should have text if called from routeTextMessageByState after check
    console.warn(`Handling unknown text from user ${userId}: '${text}'. Current session state: '${ctx.session?.state || 'N/A'}'`);
    try {
        // Avoid sending main menu if user is in a state, as it might be an invalid input for that state
        // instead of a truly "unknown" context. The state handler should manage invalid input.
        // This function is for when there's NO state or the state isn't in the map.
        if (!ctx.session?.state) {
            await sendMainMenu(ctx, "No entendí tu mensaje. Por favor, usa las opciones del menú principal o /start.");
        } else {
            // If there IS a state, but it wasn't in stateActionMap or was null initially.
            // This case implies a logic error or incomplete state map.
            // The state handler itself should manage invalid inputs for that state.
            // For now, if a state exists but isn't in map, it's safer to prompt for specific action or cancel.
            await ctx.reply("No entendí tu respuesta en el contexto actual. Por favor, intenta de nuevo o cancela la acción actual usando el botón correspondiente.");
        }
    } catch (error) {
        console.error(`Error in handleUnknownText for user ${userId}:`, error);
    }
}

module.exports = {
    routeTextMessageByState,
    handleUnknownText, // Though primarily called internally by routeTextMessageByState
};
