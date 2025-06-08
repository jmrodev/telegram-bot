// telegram-bot-js/src/utils.js
const keyboards = require('../keyboards/keyboards'); // Adjust path as needed
const config = require('../../config/config'); // Adjust path as needed

/**
 * Sends the main menu to the user, clearing their session state.
 * @param {object} ctx - Telegraf context object.
 * @param {string} [text="Por favor, elige una opción:"] - Optional message text.
 */
async function sendMainMenu(ctx, text = "Por favor, elige una opción:") {
    console.debug(`Attempting to send main menu to user ${ctx.from?.id} in chat ${ctx.chat?.id}. Text: '${text}'`);
    try {
        if (ctx.session) {
            // Clear session properties related to state and temporary data
            ctx.session.state = null;
            ctx.session.appointmentRequest = null;
            ctx.session.appointmentToEdit = null;
            ctx.session.dataForDelete = null; // etc. clear any other flow-specific data
            // handled_in_group_0 flag is more complex in Telegraf, might be managed by middleware order or specific logic
            console.log(`Session cleared for user ${ctx.from?.id}. Current session state:`, ctx.session.state);

        } else {
            console.warn(`No session found for user ${ctx.from?.id} when trying to send main menu.`);
            // If session middleware is correctly set up, ctx.session should always exist.
            // If it can truly be null/undefined here, initialize it to prevent errors downstream.
            ctx.session = {};
        }


        await ctx.reply(text, keyboards.mainMenu);
        console.log(`Main menu sent to user ${ctx.from?.id}.`);
    } catch (error) {
        console.error(`Error sending main menu to user ${ctx.from?.id}:`, error);
        // Avoid sending another message here as this is a utility function
    }
}

/**
 * Handles the global cancel action, clearing state and sending the main menu.
 * @param {object} ctx - Telegraf context object.
 */
async function cancelAction(ctx) {
    const userId = ctx.from?.id;
    const chatId = ctx.chat?.id;
    const previousState = ctx.session?.state || 'Ninguno';
    console.log(`User ${userId} in chat ${chatId} initiated cancelAction. Previous state: '${previousState}'`);

    try {
        // sendMainMenu will clear the session and send the menu
        await sendMainMenu(ctx, "Tu acción anterior ha sido cancelada. Ya puedes seleccionar una nueva opción del menú.");
        console.log(`cancelAction completed for user ${userId}. Main menu sent.`);
    } catch (error) {
        console.error(`Error during cancelAction for user ${userId} (State before cancel: '${previousState}'):`, error);
        try {
            await ctx.reply("Hubo un error al cancelar la acción. Por favor, intenta usar /start para volver al menú principal.");
            if (ctx.session) {
                 ctx.session.state = null; // Attempt to clear state again
                 console.log(`Session state explicitly cleared again in cancelAction error handler for user ${userId}.`);
            }
        } catch (replyError) {
            console.error(`Failed to send emergency error message in cancelAction to user ${userId}:`, replyError);
        }
    }
}

module.exports = {
    sendMainMenu,
    cancelAction,
};
