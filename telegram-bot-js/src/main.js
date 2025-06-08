// telegram-bot-js/src/main.js
const { Telegraf, session } = require('telegraf');
const LocalSession = require('telegraf-session-local');
const config = require('../config/config');
// Corrected path for utils.js, it's in the same directory level (src/utils) not src/utils/utils
const { sendMainMenu, cancelAction } = require('./utils');
const { getCalendarService } = require('./services/googleCalendar'); // Import the getter
const { routeTextMessageByState } = require('./handlers/textHandler');
const turnoHandlers = require('./handlers/turnoHandlers');

// Initialize GCal service early to check credentials
const gcalServiceInstance = getCalendarService();

if (!config.telegramToken) {
    console.error("TELEGRAM_TOKEN is not set in .env file or environment variables. Bot cannot start.");
    process.exit(1);
}

if (!gcalServiceInstance) {
    console.error("Google Calendar service could not be initialized. Check credentials in .env (GCAL_CLIENT_EMAIL, GCAL_PRIVATE_KEY, GCAL_PROJECT_ID). Bot cannot start.");
    process.exit(1);
}

const bot = new Telegraf(config.telegramToken);

// Session middleware
const localSession = new LocalSession({
    database: 'session_db.json',
    storage: LocalSession.storageFileAsync,
    format: {
        serialize: (obj) => JSON.stringify(obj, null, 2),
        deserialize: (str) => JSON.parse(str),
    },
});
bot.use(localSession.middleware());

// Middleware to make gcalService available in ctx and ensure session object
bot.use((ctx, next) => {
    ctx.gcalService = gcalServiceInstance; // Attach the initialized instance
    ctx.session = ctx.session || {}; // Ensure session object exists
    return next();
});


// --- Global Error Handler ---
bot.catch((err, ctx) => {
    const userId = ctx.from?.id || 'N/A';
    const chatId = ctx.chat?.id || 'N/A';
    const updateType = ctx.updateType;
    const updateDetails = ctx.update;

    console.error(`Global error for UserID: ${userId}, ChatID: ${chatId}, UpdateType: ${updateType}`, {
        error: err,
        errorName: err.name,
        errorMessage: err.message,
        errorStack: err.stack,
        update: updateDetails
    });

    // Notify user if possible
    if (ctx.chat?.id) {
        ctx.reply("Lo siento, ha ocurrido un error inesperado en el bot. Ya hemos sido notificados.\nPor favor, intenta usar /start para reiniciar. Si el problema persiste, contacta al administrador.")
            .catch(replyErr => {
                console.error("Failed to send error message to user via global_error_handler:", replyErr);
            });
    }

    // Optional: Notify developer (using secretaryChatId as a stand-in)
    if (config.secretaryChatId && String(config.secretaryChatId).length > 0) {
        const devMessage = \`🚨 Global Error Alert 🚨
Error: ${err.message}
User: ${userId} (@${ctx.from?.username || 'N/A'})
Chat: ${chatId} (Type: ${ctx.chat?.type || 'N/A'})
Update Type: ${updateType}
Stack: ${err.stack?.substring(0, 500)}...\`;
        bot.telegram.sendMessage(config.secretaryChatId, devMessage)
            .catch(devErr => {
                console.error("Failed to send global error alert to developer chat ID:", devErr);
            });
    } else {
        console.warn("No SECRETARY_CHAT_ID configured for developer error notifications, or it's empty.");
    }
});

// --- Command Handlers ---
bot.start(async (ctx) => {
    const userId = ctx.from?.id; // ctx.from is guaranteed in /start from a user
    const username = ctx.from.username || 'N/A';
    console.log(`User ${userId} (@${username}) executed /start.`);
    try {
        await ctx.replyWithHTML(\`¡Hola ${ctx.from.first_name}! Bienvenido al asistente virtual.\`);
        await sendMainMenu(ctx, "Por favor, elige una opción del menú:");
    } catch (error) {
        console.error(`Error in /start handler for user ${userId}:`, error);
        try {
            // Attempt to send a generic error message if specific start actions fail
            await ctx.reply("Ocurrió un error al iniciar nuestra conversación. Por favor, intenta ejecutar /start nuevamente más tarde.");
        } catch (replyError) {
            console.error(`Critical: Failed to send error message to user ${userId} during start handler:`, replyError);
        }
    }
});

// --- Main Menu Button Handlers ---
bot.hears(config.buttons.turno, turnoHandlers.handleTurnoMenu);
// TODO: bot.hears(config.buttons.receta, recetaHandlers.handleRecetaMenu);
// TODO: bot.hears(config.buttons.pago, pagoHandlers.handlePagoMenu);

// --- Turno SubMenu Button Handlers ---
// These call handleTurnoSubChoice, which then routes based on the button text.
bot.hears(config.buttons.turnoSolcitar, turnoHandlers.handleTurnoSubChoice);
bot.hears(config.buttons.turnoEliminar, turnoHandlers.handleTurnoSubChoice);
bot.hears(config.buttons.turnoEditar, turnoHandlers.handleTurnoSubChoice);
bot.hears(config.buttons.turnoVideo, turnoHandlers.handleTurnoSubChoice);
bot.hears(config.buttons.turnoDoctor, turnoHandlers.handleTurnoSubChoice);
bot.hears(config.buttons.turnoSecretaria, turnoHandlers.handleTurnoSubChoice);
// Note: config.buttons.volver within turnoMenu is handled by handleTurnoSubChoice directly.

// --- Global Text-based Button Handlers (Order Matters) ---

// Global "Cancelar Acción" button: Highest priority among text buttons after commands.
bot.hears(config.buttons.cancelarAccion, async (ctx) => {
    // This handler should strictly match the button text.
    if (ctx.message && ctx.message.text === config.buttons.cancelarAccion) { // Ensure exact match for the button
        console.log(`User ${ctx.from?.id} triggered global cancel via button: '${config.buttons.cancelarAccion}'`);
        await cancelAction(ctx);
    } else {
        // If the text is not *exactly* "Cancelar Acción", it might be regular text.
        // This case should ideally not be reached if "Cancelar Acción" is a unique phrase for the button.
        // If it could be part of normal conversation, then this `hears` might be too broad.
        // However, for reply buttons, exact match is the expected behavior.
        // Fallback to general text routing if, for some reason, it wasn't an exact match but was caught by `hears`.
        console.warn(`Text '${ctx.message?.text}' was caught by 'cancelarAccion' hears but wasn't an exact match. Routing to general text handler.`);
        return routeTextMessageByState(ctx);
    }
});

// Global "Volver al Menú Principal" button
bot.hears(config.buttons.volver, async (ctx) => {
    // This handler should strictly match the button text.
    if (ctx.message && ctx.message.text === config.buttons.volver) {
        console.log(`User ${ctx.from?.id} pressed global 'Volver' button.`);
        await sendMainMenu(ctx); // sendMainMenu clears state
    } else {
        // If not an exact match, let it fall through to the general text router.
        console.warn(`Text '${ctx.message?.text}' was caught by 'volver' hears but wasn't an exact match. Routing to general text handler.`);
        return routeTextMessageByState(ctx);
    }
});

// General text handler - should be registered after specific `hears` for buttons
bot.on('text', routeTextMessageByState);

// TODO: Implement bot.on('photo', handlePhoto);
// TODO: Implement callback query handlers for various actions (cancel, edit, etc.)
// e.g. bot.action(/pattern/, async (ctx) => { ... });

// Launch the bot
bot.launch().then(() => {
    console.log('Telegram bot started successfully!');
    console.log(`Bot username: @${bot.botInfo?.username || 'N/A (fetch manually if needed)'}`);
    console.log('Ensure bot is added to groups and has necessary permissions if applicable.');
    console.log('Ensure .env is populated with TELEGRAM_TOKEN and Google Calendar credentials.');
    if (!config.secretaryChatId) {
        console.warn("SECRETARY_CHAT_ID is not set in .env. Some features (e.g., secretary communication, dev error alerts) might be affected.");
    }

}).catch(err => {
    console.error('Failed to launch bot:', err);
    if (err.message?.includes('401: Unauthorized')) {
        console.error("Error 401: Unauthorized. This usually means your TELEGRAM_TOKEN is invalid or expired. Please check your .env file.");
    } else if (err.message?.includes('ETIMEDOUT') || err.message?.includes('ESOCKETTIMEDOUT')) {
         console.error("Network timeout error. Check your internet connection and firewall settings.");
    }
    process.exit(1); // Exit if launch fails
});

// Enable graceful stop
process.once('SIGINT', () => {
    console.log("SIGINT received, stopping bot...");
    bot.stop('SIGINT');
    process.exit(0);
});
process.once('SIGTERM', () => {
    console.log("SIGTERM received, stopping bot...");
    bot.stop('SIGTERM');
    process.exit(0);
});

console.log("Main.js script finished execution sequence. Bot launch is asynchronous.");
