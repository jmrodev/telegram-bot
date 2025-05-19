# Mi Bot de Consultorio para Telegram (v1.x)

Este es un bot de Telegram diseñado para gestionar aspectos básicos de un consultorio médico, incluyendo la solicitud y cancelación de turnos (integrado con Google Calendar), información sobre recetas y pagos.

## Características

*   **Gestión de Turnos:**
    *   Solicitar nuevos turnos con un doctor específico en días y horarios disponibles.
    *   Consultar disponibilidad real de doctores desde Google Calendar.
    *   Cancelar turnos existentes (seleccionando de una lista de turnos del usuario).
    *   Creación automática de eventos en los calendarios de Google de los doctores.
*   **Información sobre Recetas:**
    *   Solicitar nuevas recetas (texto y/o foto).
    *   Solicitar corrección de recetas existentes (texto y/o foto).
*   **Información sobre Pagos:**
    *   Mostrar datos para transferencia bancaria.
    *   Informar sobre pagos en consultorio.
*   **Menús Interactivos:** Navegación sencilla mediante botones de respuesta y botones inline.
*   **Modularidad:** Código organizado en módulos para configuración, utilidades de calendario, teclados y handlers.

## Estructura del Proyecto

```
/mi_bot_consultorio/
├── main.py                     # Script principal del bot, inicializa y registra handlers
├── config.py                   # Configuraciones (tokens, IDs, textos de botones, estados)
├── credentials.json            # Credenciales de la cuenta de servicio de Google (NO INCLUIR EN GIT PÚBLICO)
├── google_calendar_utils.py    # Lógica para interactuar con Google Calendar API
├── keyboards.py                # Definiciones de los teclados (Reply e Inline)
├── requirements.txt            # Dependencias de Python (generar con 'pip freeze > requirements.txt')
├── handlers/                   # Módulo con los manejadores de lógica del bot
│   ├── __init__.py             # Define la carpeta como un paquete Python
│   ├── common.py               # Handlers comunes (start, cancelar, ruteo por estado, desconocido)
│   ├── turno.py                # Handlers para el flujo de turnos
│   ├── receta.py               # Handlers para el flujo de recetas
│   ├── pago.py                 # Handlers para el flujo de pagos
│   ├── misc.py                 # Handlers para mensajes a secretaría, sí/no
│   └── utils.py                # Funciones de utilidad para los handlers (ej. enviar menú)
└── README.md                   # Este archivo
```

## Prerrequisitos

### Generales

1.  **Python:** Versión 3.9 o superior.
2.  **Token de Bot de Telegram:**
    *   Habla con `@BotFather` en Telegram.
    *   Crea un nuevo bot con `/newbot`.
    *   Guarda el **TOKEN** que te proporcione.
3.  **Cuenta de Google y Proyecto en Google Cloud:**
    *   Crea un proyecto en [Google Cloud Console](https://console.cloud.google.com/).
    *   Habilita la **API de Google Calendar** para tu proyecto.
    *   Crea una **Cuenta de Servicio**:
        *   Ve a "APIs y servicios" > "Credenciales" > "Crear credenciales" > "Cuenta de servicio".
        *   Descarga el archivo JSON de la clave de la cuenta de servicio. **Renómbralo a `credentials.json`** y colócalo en la raíz del proyecto.
    *   **Comparte tus Calendarios de Google:**
        *   Obtén el email de la cuenta de servicio desde `credentials.json` (campo `client_email`).
        *   Para cada calendario de doctor que vayas a usar:
            *   Ve a la configuración del calendario en Google Calendar.
            *   En "Compartir con determinadas personas", añade el email de la cuenta de servicio.
            *   Asígnale el permiso **"Hacer cambios en eventos"**.
        *   Obtén los **IDs de los calendarios** de los doctores.

### Específicos para Android (Termux)

*   **Termux:** Aplicación de terminal para Android (recomendado desde F-Droid).
*   Dependencias de compilación (se instalan con `pkg` en Termux).

## Configuración del Bot

1.  **Clona el repositorio (si aplica):**
    ```bash
    git clone https://github.com/TU_USUARIO_GITHUB/TU_REPOSITORIO_BOT.git
    cd TU_REPOSITORIO_BOT
    ```
    O descarga los archivos directamente.

2.  **Crea y configura `config.py`:**
    *   Utiliza el archivo `config.py` proporcionado en el proyecto.
    *   Edita `config.py` y completa:
        *   `TELEGRAM_TOKEN = 'TU_TOKEN_DE_TELEGRAM_AQUI'` (Reemplaza el token de ejemplo).
        *   `CALENDAR_IDS_DOCTORES`: Reemplaza los IDs de calendario placeholder con los IDs reales.
            ```python
            CALENDAR_IDS_DOCTORES = {
               "Dr. Pérez": "ID_REAL_CALENDARIO_PEREZ@group.calendar.google.com",
               # ... otros doctores
            }
            ```
        *   `SECRETARY_CHAT_ID` (Opcional): Si deseas que el bot envíe notificaciones a un chat de secretaría, obtén el ID de ese chat y configúralo.
        *   Ajusta `TIMEZONE`, `OFFICE_START_HOUR`, `OFFICE_END_HOUR`, etc., según sea necesario.

3.  **Coloca `credentials.json`:** Asegúrate de que el archivo `credentials.json` (descargado de Google Cloud) esté en el directorio raíz del proyecto (junto a `main.py` y `config.py`).
    **¡NUNCA subas `credentials.json` a un repositorio Git público!** Añádelo a tu archivo `.gitignore` si usas Git:
    ```
    # .gitignore
    credentials.json
    __pycache__/
    *.pyc
    .venv/
    *.log
    ```

## Instalación y Ejecución

### En PC (Linux / macOS / Windows)

1.  **Navega al directorio del proyecto:**
    ```bash
    cd ruta/a/tu_proyecto_bot
    ```

2.  **Crea y activa un entorno virtual (altamente recomendado):**
    ```bash
    python -m venv .venv
    # En Linux/macOS:
    source .venv/bin/activate
    # En Windows (cmd):
    # .venv\Scripts\activate.bat
    # En Windows (PowerShell):
    # .venv\Scripts\Activate.ps1
    ```

3.  **Genera `requirements.txt` (si no lo tienes):**
    Si ya instalaste los paquetes, desde el entorno activado:
    ```bash
    pip freeze > requirements.txt
    ```
    Si es la primera vez, puedes instalar los paquetes principales y luego generar el archivo.

4.  **Instala las dependencias:**
    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```
    Si no tienes `requirements.txt`, instala las principales manualmente:
    ```bash
    pip install python-telegram-bot google-api-python-client google-auth-oauthlib google-auth-httplib2 pytz python-dateutil # y otras que puedas necesitar por las dependencias
    ```

5.  **Ejecuta el bot:**
    ```bash
    python main.py
    ```
    Deberías ver logs en la consola indicando que el bot se ha iniciado.

### En Android (usando Termux)

1.  **Prepara Termux:**
    ```bash
    pkg update -y && pkg upgrade -y
    pkg install python python-pip libjpeg-turbo libffi openssl clang make git -y # git es opcional
    ```

2.  **Transfiere los archivos del proyecto a Termux:**
    *   Crea un directorio para el bot:
        ```bash
        mkdir ~/mi_bot_telegram
        cd ~/mi_bot_telegram
        ```
    *   Copia todos los archivos `.py` del proyecto (incluyendo los de la carpeta `handlers/`) y `credentials.json` a este directorio. Si tienes `requirements.txt`, cópialo también.
    *   Mantén la estructura de carpetas (crea la carpeta `handlers` dentro de `~/mi_bot_telegram` y pon los archivos correspondientes allí).
        *   Puedes usar `termux-setup-storage` para acceder a tu almacenamiento compartido.

3.  **Instala las dependencias en Termux:**
    *   Si tienes `requirements.txt`:
        ```bash
        pip install --upgrade pip
        pip install -r requirements.txt
        ```
    *   Si no, instala manualmente (igual que en PC, pero sin entorno virtual explícito):
        ```bash
        pip install python-telegram-bot google-api-python-client google-auth-oauthlib google-auth-httplib2 pytz python-dateutil # y otras de tu requirements.txt
        ```
        *Nota: Si encuentras errores de compilación para algún paquete en Termux, puede que necesites instalar dependencias adicionales del sistema con `pkg install ...`.*

4.  **Ejecuta el bot en Termux:**
    ```bash
    python main.py
    ```

5.  **Mantener el bot activo en Termux (importante):**
    Android puede detener procesos en segundo plano. Para evitarlo:
    *   En la sesión de Termux donde ejecutarás el bot:
        ```bash
        termux-wake-lock
        ```
    *   Luego, ejecuta el bot:
        ```bash
        python main.py
        ```
    *   Para detener el `wake-lock`, abre una *nueva sesión* de Termux y ejecuta:
        ```bash
        termux-wake-unlock
        ```

## Uso

Una vez que el bot esté corriendo:

1.  Abre Telegram.
2.  Busca tu bot por el nombre de usuario que le diste en BotFather.
3.  Envía el comando `/start` para iniciar la interacción y ver el menú principal.
4.  Sigue las opciones del menú para solicitar turnos, recetas, etc.

## Logging

El bot genera logs en la consola. El nivel de logging está configurado en `INFO` por defecto en `main.py`. Puedes cambiarlo a `DEBUG` para obtener información más detallada durante el desarrollo o para solucionar problemas.

## Contribuir (Opcional)

Si deseas contribuir, por favor sigue estos pasos:
1. Haz un Fork del proyecto.
2. Crea tu Feature Branch (`git checkout -b feature/AmazingFeature`).
3. Haz Commit de tus cambios (`git commit -m 'Add some AmazingFeature'`).
4. Haz Push a la Branch (`git push origin feature/AmazingFeature`).
5. Abre una Pull Request.

## Licencia 

## Contacto

Juan Marcelo Rodriguez  juanmarcelo.rodrigueztandil~gmail.com
