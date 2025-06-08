// telegram-bot-js/src/services/googleCalendar.js
const { google } = require('googleapis');
const { format, addDays, parse, nextMonday, nextTuesday, nextWednesday, nextThursday, nextFriday, nextSaturday, startOfDay, endOfDay, addMinutes, isAfter, isEqual } = require('date-fns');
const { utcToZonedTime, zonedTimeToUtc } = require('date-fns-tz');
const config = require('../../config/config'); // Adjust path as needed

// --- Authentication ---
let calendarService = null;

/**
 * Authenticates and returns the Google Calendar API service.
 * Uses credentials from config (environment variables).
 */
function getCalendarService() {
    if (calendarService) {
        return calendarService;
    }

    if (!config.googleClientEmail || !config.googlePrivateKey || !config.googleCloudProjectId) {
        console.error('Google Calendar credentials (clientEmail, privateKey, projectId) are not configured in .env.');
        return null;
    }

    const auth = new google.auth.GoogleAuth({
        credentials: {
            client_email: config.googleClientEmail,
            private_key: config.googlePrivateKey,
            project_id: config.googleCloudProjectId,
        },
        scopes: config.googleCalendarScopes,
    });

    calendarService = google.calendar({ version: 'v3', auth });
    console.log('Google Calendar service authenticated successfully.');
    return calendarService;
}

// --- Date Helper Functions ---

/**
 * Calculates the date of the next specified weekday.
 * @param {string} dayName - Name of the day (e.g., "Lunes", "Martes").
 * @returns {Date|null} The date object for the next weekday, or null if invalid.
 */
function getNextWeekdayDate(dayName) {
    const today = new Date();
    const dayMapping = {
        "lunes": nextMonday, "martes": nextTuesday, "miércoles": nextWednesday, "miercoles": nextWednesday,
        "jueves": nextThursday, "viernes": nextFriday, "sábado": nextSaturday, "sabado": nextSaturday
        // Domingo is not in Python's DAY_LIST, so not included here unless specified
    };

    const normalizedDayName = dayName.toLowerCase();
    const nextDayFunction = dayMapping[normalizedDayName];

    if (!nextDayFunction) {
        console.warn(`Invalid day name received: ${dayName}`);
        return null;
    }

    try {
        // The nextXX functions from date-fns find the next given day of the week after the given date.
        // If today is Monday and you ask for nextMonday, it will give next week's Monday.
        // We need to adjust if today IS the day.
        // Python's relativedelta(weekday=XX(+1)) includes today if it matches.
        // date-fns nextDay functions give the *next* one.
        // A simpler approach for "next occurrence including today":
        let targetDate = new Date();
        const dayIndexMap = { "lunes": 1, "martes": 2, "miércoles": 3, "miercoles": 3, "jueves": 4, "viernes": 5, "sábado": 6, "domingo": 0 };
        const targetDayIndex = dayIndexMap[normalizedDayName];
        if (targetDayIndex === undefined) return null;

        // Loop to find the next matching day, ensuring it's today or in the future.
        // Adjust targetDayIndex for JavaScript's getDay() where Sunday is 0 and Monday is 1.
        const jsTargetDayIndex = targetDayIndex; // Already 0 for Sunday, 1 for Mon, etc. in dayIndexMap if we align it.
                                                // Python: Mon=0..Sun=6. JS: Sun=0..Sat=6.
                                                // Our dayIndexMap: Lunes=1..Sabado=6, Domingo=0. This matches JS.

        let i = 0;
        while (true) {
            let tempDate = addDays(new Date(), i); // Check from today onwards
            if (tempDate.getDay() === jsTargetDayIndex) {
                // Ensure the found date is not in the past (e.g. if current time is past office hours for today)
                // This check is more relevant for checkGoogleCalendarAvailability.
                // For just getting the date, this should be fine.
                targetDate = tempDate;
                break;
            }
            if (i > 7) { // Safety break if day name is weird or logic fails
                console.error('Could not find next weekday in a week, something is wrong.'); return null;
            }
            i++;
        }
        console.log(`Calculated date for next '${dayName}': ${format(targetDate, 'yyyy-MM-dd')}`);
        return targetDate;

    } catch (error) {
        console.error(`Error calculating date for ${dayName}:`, error);
        return null;
    }
}


/**
 * Formats a date object and time string into RFC3339 start and end datetime strings.
 * @param {Date} dateObj - The date (should be start of day in UTC/local, to be combined with time).
 * @param {string} timeStr - The time in "HH:mm" format.
 * @returns {{startRFC: string, endRFC: string}|null}
 */
function formatRFC3339(dateObj, timeStr) {
    try {
        const [hours, minutes] = timeStr.split(':').map(Number);

        // Create a date object that represents the local date and time in the target timezone.
        // dateObj is already the correct day. We just need to set hours/minutes on it
        // then tell date-fns-tz that this combination *is* in the target timezone.
        const year = dateObj.getFullYear();
        const month = dateObj.getMonth();
        const day = dateObj.getDate();

        // Construct a date in the target timezone
        const startDateTimeInTargetTz = zonedTimeToUtc(new Date(year, month, day, hours, minutes), config.timezone);
        // The above will create a UTC date. We need to ensure date-fns-tz knows the input was intended for config.timezone

        // More robust: Create date parts then use date-fns-tz to build it in the target zone
        const referenceDateForTimezone = new Date(year, month, day, hours, minutes);
        const zonedStart = utcToZonedTime(referenceDateForTimezone, config.timezone); // This interprets referenceDateForTimezone as UTC and converts. Not quite.

        // Let's construct the date string and parse it with timezone
        // Or, easier: ensure dateObj is truly "local" and combine, then specify timezone.
        const dateTimeString = `${format(dateObj, 'yyyy-MM-dd')}T${timeStr}:00`; // e.g., "2023-05-15T09:30:00"

        const parsedDateAsLocal = parse(dateTimeString, "yyyy-MM-dd'T'HH:mm:ss", new Date());

        // Now convert this "local" time to a UTC ISO string, considering it was in targetTimezone
        const startUTC = zonedTimeToUtc(parsedDateAsLocal, config.timezone);
        const endUTC = addMinutes(startUTC, config.slotDurationMinutes);

        const startRFC = startUTC.toISOString();
        const endRFC = endUTC.toISOString();

        console.debug(`Formatted RFC3339: Start=${startRFC}, End=${endRFC} for date ${format(dateObj, 'yyyy-MM-dd')} and time ${timeStr}`);
        return { startRFC, endRFC };
    } catch (error) {
        console.error(`Error in formatRFC3339 for date ${dateObj}, time ${timeStr}:`, error);
        return null;
    }
}

// --- Main Google Calendar Functions ---

/**
 * Checks available time slots for a doctor on a specific date.
 * @param {string} doctorKey - Key for the doctor (e.g., "Dr. Pérez").
 * @param {Date} dateObj - The date to check (should be start of day for the target date).
 * @returns {Promise<string[]>} A list of available time slots in "HH:mm" format.
 */
async function checkGoogleCalendarAvailability(doctorKey, dateObj) {
    const service = getCalendarService();
    if (!service || !dateObj || !config.calendarIdsDoctores[doctorKey]) {
        console.error('checkAvailability: Invalid arguments or GCal service not available.');
        return [];
    }

    const calendarId = config.calendarIdsDoctores[doctorKey];
    const targetDateFormatted = format(dateObj, 'yyyy-MM-dd');
    console.log(`Querying GCal availability for Dr: ${doctorKey} (Cal: ${calendarId}) on ${targetDateFormatted}`);
    const availableSlots = [];

    try {
        // Define working hours for the given dateObj in the target timezone
        // dateObj is already the correct day. Construct start/end times using its year/month/day.
        const year = dateObj.getFullYear();
        const month = dateObj.getMonth();
        const day = dateObj.getDate();

        const dayStartDateTime = zonedTimeToUtc(new Date(year, month, day, config.officeStartHour, 0, 0), config.timezone);
        const dayEndDateTime = zonedTimeToUtc(new Date(year, month, day, config.officeEndHour, 0, 0), config.timezone);

        const timeMin = dayStartDateTime.toISOString();
        const timeMax = dayEndDateTime.toISOString();

        const response = await service.freebusy.query({
            requestBody: {
                timeMin,
                timeMax,
                timeZone: config.timezone, // Important for free/busy query interpretation
                items: [{ id: calendarId }],
            },
        });

        const busyIntervals = response.data.calendars[calendarId]?.busy || [];
        console.debug(`Busy intervals for ${doctorKey} on ${targetDateFormatted}:`, busyIntervals.map(b => ({start: b.start, end: b.end})));

        const nowInSystemTz = new Date(); // Current time in system's timezone

        // Iterate through potential slots within office hours for the given dateObj
        let currentSlotStartLocal = new Date(year, month, day, config.officeStartHour, 0, 0);

        while (isAfter(dayEndDateTime, zonedTimeToUtc(currentSlotStartLocal, config.timezone))) {
            const currentSlotEndLocal = addMinutes(currentSlotStartLocal, config.slotDurationMinutes);

            // Convert current slot to UTC for comparison with busy intervals (which are UTC)
            // and for checking if it's in the past.
            const currentSlotStartUtc = zonedTimeToUtc(currentSlotStartLocal, config.timezone);
            const currentSlotEndUtc = zonedTimeToUtc(currentSlotEndLocal, config.timezone);

            // Skip slots that have already passed (compare with current system time)
            if (isAfter(nowInSystemTz, currentSlotEndUtc) || isEqual(nowInSystemTz, currentSlotEndUtc)) {
                currentSlotStartLocal = currentSlotEndLocal;
                continue;
            }

            let isBusy = false;
            for (const busy of busyIntervals) {
                const busyStart = new Date(busy.start); // Busy times are UTC
                const busyEnd = new Date(busy.end);
                // Check for overlap: (StartA < EndB) and (EndA > StartB)
                if (isAfter(busyEnd, currentSlotStartUtc) && isAfter(currentSlotEndUtc, busyStart)) {
                    isBusy = true;
                    break;
                }
            }

            if (!isBusy) {
                // Format the slot time using the original local time for display
                availableSlots.push(format(currentSlotStartLocal, 'HH:mm'));
            }
            currentSlotStartLocal = currentSlotEndLocal;
             if (availableSlots.length > 50) { console.warn("More than 50 slots, breaking"); break; } // Safety break
        }
        console.log(`Available slots for ${doctorKey} on ${targetDateFormatted}: ${availableSlots}`);
    } catch (error) {
        console.error(`GCal API Error (freeBusy) for Dr ${doctorKey} on ${targetDateFormatted}:`, error.response?.data?.error || error.message);
    }
    return availableSlots;
}

/**
 * Creates a new appointment event in Google Calendar.
 * @param {string} doctorKey - Key for the doctor.
 * @param {string} dayStr - Day of the week (e.g., "Lunes").
 * @param {string} timeStr - Time in "HH:mm" format.
 * @param {object} userInfo - User information (id, first_name, username).
 * @param {Date|null} specificDate - Optional. If provided, use this date instead of calculating from dayStr.
 * @returns {Promise<{success: boolean, eventLink: string|null, eventId: string|null}>}
 */
async function createGoogleCalendarEvent(doctorKey, dayStr, timeStr, userInfo, specificDate = null) {
    const service = getCalendarService();
    if (!service || !config.calendarIdsDoctores[doctorKey] || (!dayStr && !specificDate) || !timeStr || !userInfo || !userInfo.id) {
        console.error('createGoogleCalendarEvent: Invalid arguments.');
        return { success: false, eventLink: null, eventId: null };
    }

    const calendarId = config.calendarIdsDoctores[doctorKey];
    const userName = userInfo.first_name || 'Paciente';
    const userUsername = userInfo.username;
    const userId = userInfo.id;
    const displayName = userUsername ? `@${userUsername}` : userName;

    console.log(`Attempting to create GCal event: Dr:${doctorKey}, Day:${dayStr || 'SpecificDate'}, Time:${timeStr}, Patient:${displayName}(ID:${userId}) in Cal:${calendarId}`);

    const targetDate = specificDate ? startOfDay(specificDate) : getNextWeekdayDate(dayStr); // Ensure targetDate is start of day for formatRFC3339
    if (!targetDate) {
        console.error(`Could not calculate date for day '${dayStr}' and no specificDate provided.`);
        return { success: false, eventLink: null, eventId: null };
    }

    const rfcTimes = formatRFC3339(targetDate, timeStr);
    if (!rfcTimes) {
        console.error(`Could not format RFC3339 for date ${format(targetDate, 'yyyy-MM-dd')}, time ${timeStr}`);
        return { success: false, eventLink: null, eventId: null };
    }
    const { startRFC, endRFC } = rfcTimes;

    const description = \`Turno solicitado vía Bot Telegram.
Paciente: ${userName}
Usuario: @${userUsername || 'N/A'}
ID Chat: ${userId}
Doctor: ${doctorKey}
Fecha Solicitud: ${format(utcToZonedTime(new Date(), config.timezone), 'yyyy-MM-dd HH:mm:ss zzz')}\`;

    const eventBody = {
        summary: \`Turno ${userName} con ${doctorKey}\`,
        description,
        start: { dateTime: startRFC, timeZone: config.timezone }, // Timezone here is for Google to interpret the dateTime
        end: { dateTime: endRFC, timeZone: config.timezone },
        reminders: {
            useDefault: false,
            overrides: [
                { method: 'popup', minutes: 60 },
                { method: 'popup', minutes: 1440 }, // 1 day
            ],
        },
    };

    try {
        const createdEvent = await service.events.insert({
            calendarId: calendarId,
            requestBody: eventBody,
        });
        const eventLink = createdEvent.data.htmlLink;
        const eventId = createdEvent.data.id;
        console.log(`Event created successfully in GCal for Dr.${doctorKey}. ID: ${eventId}, Link: ${eventLink}`);
        return { success: true, eventLink, eventId };
    } catch (error) {
        console.error(`GCal API Error (insert) for Dr.${doctorKey}:`, error.response?.data?.error || error.message);
        return { success: false, eventLink: null, eventId: null };
    }
}

/**
 * Finds all future appointments for a user across all configured doctor calendars.
 * @param {object} userInfo - User information (id).
 * @returns {Promise<object[]>} A list of appointment objects.
 */
async function findAllUserAppointments(userInfo) {
    const service = getCalendarService();
    if (!service || !userInfo || !userInfo.id) {
        console.error('findAllUserAppointments: GCal service not available or missing user ID.');
        return [];
    }
    const userId = String(userInfo.id); // Ensure it's a string for comparison
    console.log(`Finding ALL future appointments for UserID:${userId} across all calendars.`);
    const allFoundEvents = [];
    const nowUtc = new Date().toISOString();

    for (const doctorKey in config.calendarIdsDoctores) {
        const calendarId = config.calendarIdsDoctores[doctorKey];
        try {
            // Using q to search in description. Might need to be specific if descriptions are complex.
            const search_query = \`ID Chat: ${userId}\`;
            const response = await service.events.list({
                calendarId: calendarId,
                timeMin: nowUtc,
                q: search_query,
                singleEvents: true,
                orderBy: 'startTime',
                maxResults: config.maxCancelButtons + 5, // Fetch a bit more in case some are filtered out
            });
            const items = response.data.items || [];
            console.log(`API found ${items.length} potential future events for UserID ${userId} in Cal:${calendarId} (${doctorKey}).`);

            for (const event of items) {
                // Double check the description contains the exact ID Chat phrase
                if (event.description?.includes(\`ID Chat: ${userId}\`) && event.start?.dateTime) {
                    const startDateTime = utcToZonedTime(new Date(event.start.dateTime), config.timezone);
                    const displayDateTime = format(startDateTime, 'EEE dd/MM HH:mm', { timeZone: config.timezone });

                    allFoundEvents.push({
                        summary: event.summary || 'Evento',
                        eventId: event.id,
                        calendarId: calendarId,
                        doctorName: config.doctorNamesFromId[calendarId] || doctorKey, // Use mapping for consistency
                        startDateTime: startDateTime, // Date object for sorting
                        displayDateTime: displayDateTime,
                        doctorKey: doctorKey
                    });
                }
            }
        } catch (error) {
            if (error.response && error.response.status === 404) {
                console.warn(`Calendar ${calendarId} not found (404) while searching all appointments for user ${userId}.`);
                continue;
            }
            console.error(`GCal API Error (list future) for Cal:${calendarId}:`, error.response?.data?.error || error.message);
        }
    }
    allFoundEvents.sort((a, b) => a.startDateTime.getTime() - b.startDateTime.getTime());
    console.log(`Total future appointments for UserID:${userId}: ${allFoundEvents.length}`);
    return allFoundEvents.slice(0, config.maxCancelButtons); // Apply max limit after sorting
}

/**
 * Checks if a user already has a future appointment with a specific doctor.
 * @param {string} doctorKey - Key for the doctor.
 * @param {object} userInfo - User information (id).
 * @returns {Promise<{exists: boolean, details: string|null}>}
 */
async function checkExistingAppointment(doctorKey, userInfo) {
    const service = getCalendarService();
    if (!service || !config.calendarIdsDoctores[doctorKey] || !userInfo || !userInfo.id) {
        console.error('checkExistingAppointment: Invalid arguments or GCal service not available.');
        return { exists: false, details: null };
    }
    const userId = String(userInfo.id);
    const calendarId = config.calendarIdsDoctores[doctorKey];
    console.log(`Checking for existing future appointment for UserID:${userId} with Dr:${doctorKey} (Cal:${calendarId})`);
    const nowUtc = new Date().toISOString();

    try {
        const search_query = \`ID Chat: ${userId}\`;
        const response = await service.events.list({
            calendarId: calendarId,
            timeMin: nowUtc,
            q: search_query,
            singleEvents: true,
            maxResults: 5, // Usually a user has few appointments with one doctor
            orderBy: 'startTime',
        });
        const items = response.data.items || [];
        for (const event of items) {
            if (event.description?.includes(\`ID Chat: ${userId}\`) && event.start?.dateTime) {
                const startDateTimeLocal = utcToZonedTime(new Date(event.start.dateTime), config.timezone);
                const appointmentDetailsStr = \`el \${format(startDateTimeLocal, 'EEEE dd/MM 'a las' HH:mm', { timeZone: config.timezone })}\`;
                console.log(`Existing future appointment found for UserID:${userId} with Dr:${doctorKey}: ${appointmentDetailsStr}`);
                return { exists: true, details: appointmentDetailsStr };
            }
        }
        console.log(`No existing future appointments found for UserID:${userId} with Dr:${doctorKey}.`);
        return { exists: false, details: null };
    } catch (error) {
        if (error.response && error.response.status === 404) {
            console.warn(`Calendar ${calendarId} not found (404) while checking existing for Dr:${doctorKey}.`);
        } else {
            console.error(`GCal API Error (list check) for Dr:${doctorKey}:`, error.response?.data?.error || error.message);
        }
        return { exists: false, details: null };
    }
}

/**
 * Deletes a specific Google Calendar event.
 * @param {string} calendarId - The ID of the calendar.
 * @param {string} eventId - The ID of the event to delete.
 * @returns {Promise<boolean>} True if successful or event already gone, false otherwise.
 */
async function deleteGoogleCalendarEvent(calendarId, eventId) {
    const service = getCalendarService();
    if (!service || !calendarId || !eventId) {
        console.error('deleteGoogleCalendarEvent: Invalid arguments.');
        return false;
    }
    const doctorName = config.doctorNamesFromId[calendarId] || "Unknown Doctor";
    console.log(`Attempting to delete event ID: ${eventId} from Cal: ${calendarId} (Dr: ${doctorName})`);
    try {
        await service.events.delete({
            calendarId: calendarId,
            eventId: eventId,
        });
        console.log(`Event ID: ${eventId} deleted successfully from Cal: ${calendarId}`);
        return true;
    } catch (error) {
        if (error.response && (error.response.status === 404 || error.response.status === 410)) {
            console.warn(`Event ID: ${eventId} not found (status ${error.response.status}) on Cal: ${calendarId}. Assuming already deleted.`);
            return true;
        }
        console.error(`GCal API Error (delete event) ID ${eventId} on Cal ${calendarId}:`, error.response?.data?.error || error.message);
        return false;
    }
}

/**
 * Fetches details for a specific event.
 * @param {string} calendarId - The ID of the calendar.
 * @param {string} eventId - The ID of the event.
 * @returns {Promise<object|null>} Event details or null if not found/error.
 */
async function getEventDetails(calendarId, eventId) {
    const service = getCalendarService();
    if (!service || !calendarId || !eventId) {
        console.error('getEventDetails: Invalid arguments.');
        return null;
    }
    try {
        const response = await service.events.get({
            calendarId: calendarId,
            eventId: eventId,
        });
        const event = response.data;
        if (!event || !event.start) { // Ensure event and event.start exist
             console.warn(`Event ${eventId} on Cal ${calendarId} not found or has no start time.`);
             return null;
        }

        const doctorName = config.doctorNamesFromId[calendarId] || "Unknown Doctor";
        let displayDateTime = 'Fecha/hora desconocida';
        if (event.start.dateTime) { // Check dateTime specifically
            const startDt = utcToZonedTime(new Date(event.start.dateTime), config.timezone);
            displayDateTime = format(startDt, 'EEE dd/MM/yyyy HH:mm', { timeZone: config.timezone });
        } else if (event.start.date) { // Handle all-day events if necessary, though not expected for appointments
            const startDt = utcToZonedTime(startOfDay(new Date(event.start.date)), config.timezone); // Treat as start of day in target TZ
            displayDateTime = format(startDt, 'EEE dd/MM/yyyy (Todo el día)', { timeZone: config.timezone });
        }


        return {
            eventId: event.id,
            calendarId: calendarId,
            doctorName: doctorName,
            summary: event.summary,
            description: event.description,
            startDateTimeIso: event.start.dateTime || event.start.date, // Return what's available
            endDateTimeIso: event.end?.dateTime || event.end?.date,
            displayDateTime: displayDateTime,
        };
    } catch (error) {
        if (error.response && error.response.status === 404) {
            console.warn(`Event ${eventId} on Cal ${calendarId} not found (404).`);
        } else {
            console.error(`GCal API Error (get event) ID ${eventId} on Cal ${calendarId}:`, error.response?.data?.error || error.message);
        }
        return null;
    }
}


module.exports = {
    getCalendarService,
    getNextWeekdayDate,
    formatRFC3339,
    checkGoogleCalendarAvailability,
    createGoogleCalendarEvent,
    findAllUserAppointments,
    checkExistingAppointment,
    deleteGoogleCalendarEvent,
    getEventDetails,
};
