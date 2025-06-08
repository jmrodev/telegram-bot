// telegram-bot-js/src/handlers/recetaHandlers.js
const { sendMainMenu } = require('../utils/utils'); // Example import

async function handleRecetaInfoText(ctx) {
    console.log('Placeholder: handleRecetaInfoText called with text:', ctx.message.text);
    await ctx.reply('Placeholder: Lógica para info de receta.');
    // For placeholder, good to send back to main menu
    await sendMainMenu(ctx, "Función de recetas aún no completada.");
}
async function handleRecetaCorrectionText(ctx) {
    console.log('Placeholder: handleRecetaCorrectionText called with text:', ctx.message.text);
    await ctx.reply('Placeholder: Lógica para corrección de receta.');
    // For placeholder, good to send back to main menu
    await sendMainMenu(ctx, "Función de recetas aún no completada.");
}
module.exports = { handleRecetaInfoText, handleRecetaCorrectionText };
