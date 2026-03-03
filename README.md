# Agente Calendario

> **Bot de Telegram con IA** para gestion integral de servicios tecnicos:
> agenda, clientes, Google Calendar y cierre de trabajos — todo desde una conversacion natural.

---

## Requisitos Previos

- **Python 3.11** o superior
- **pip** (gestor de paquetes de Python)
- **Cuenta de Telegram** + Token de Bot (via [@BotFather](https://t.me/BotFather))
- **Cuenta de Google Cloud** con Calendar API habilitada + Service Account
- **API Key de Groq** (gratuito en [console.groq.com](https://console.groq.com))

---

## Instalacion en Ubuntu Server

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/agente-calendario.git
cd agente-calendario
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
nano .env
```

Completar con tus datos reales:

```env
# Obligatorios
TELEGRAM_BOT_TOKEN=tu_token_aqui
ADMIN_TELEGRAM_IDS=[tu_telegram_id]
GROQ_API_KEY=gsk_tu_api_key
GOOGLE_CALENDAR_ID=tu_calendar_id@group.calendar.google.com
```

> Para obtener tu Telegram ID, usa [@userinfobot](https://t.me/userinfobot).

### 4. Configurar Google Calendar

1. Ir a [Google Cloud Console](https://console.cloud.google.com).
2. Crear un proyecto o seleccionar uno existente.
3. Habilitar **Google Calendar API**.
4. Crear una **Service Account** y descargar la clave JSON.
5. Guardar el archivo en `credentials/service_account.json`.
6. En Google Calendar, compartir el calendario con el email de la Service Account
   (con permisos de "Hacer cambios en eventos").

### 5. Crear directorios necesarios

```bash
mkdir -p data logs credentials
```

> `data/` y `logs/` se crean automaticamente al arrancar, pero es buena practica tenerlos listos.

---

## Levantar el bot

### Opcion A: Foreground (para probar)

```bash
cd /home/emisorato-ubu/calendario
.venv/bin/python -m src.main
```

Para detener: `Ctrl+C`.

### Opcion B: Background con screen (recomendado)

Instalar screen si no esta instalado:

```bash
sudo apt install screen -y
```

Arrancar el bot en una sesion screen:

```bash
cd /home/emisorato-ubu/calendario
screen -S bot
.venv/bin/python -m src.main
```

- **Desconectarse sin matar el bot**: `Ctrl+A` luego `D`
- **Reconectarse**: `screen -r bot`
- **Ver sesiones activas**: `screen -ls`

### Opcion C: Background con nohup (sin instalar nada)

```bash
cd /home/emisorato-ubu/calendario
nohup .venv/bin/python -m src.main >> logs/bot_stdout.log 2>&1 &
echo $!  # Anota el PID
```

- **Ver si esta corriendo**: `ps aux | grep src.main`
- **Detener**: `kill <PID>`

---

## Verificar que funciona

1. Despues de arrancar, los logs deben mostrar:
   ```
   INFO  __main__  | Configuracion cargada correctamente
   INFO  __main__  | Google Calendar inicializado
   INFO  __main__  | LLM Parser inicializado
   INFO  __main__  | Base de datos inicializada: data/crm.db
   INFO  __main__  | Orquestador creado e inyectado
   INFO  __main__  | Bot iniciando en modo polling...
   INFO  telegram.ext.Application | Application started
   ```

2. Abrir Telegram desde el celular y buscar tu bot.
3. Enviar `/start` — deberia aparecer un mensaje de bienvenida.
4. Enviar `/menu` — deberia mostrar botones con las acciones disponibles.

### Ver logs en tiempo real

```bash
tail -f /home/emisorato-ubu/calendario/logs/agente.log
```

---

## Tests

```bash
cd /home/emisorato-ubu/calendario

# Todos los tests
.venv/bin/pytest tests/ -v

# Solo unitarios
.venv/bin/pytest tests/unit/ -v

# Solo integracion
.venv/bin/pytest tests/integration/ -v

# Con cobertura
.venv/bin/pytest --cov=src --cov-report=term-missing
```

---

## Estructura del proyecto

```
calendario/
├── .env                        # Variables de entorno (no versionado)
├── .env.example                # Plantilla de variables
├── credentials/                # Service Account de Google (no versionado)
│   └── service_account.json
├── src/                        # Codigo fuente
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuracion centralizada (Pydantic)
│   ├── core/                   # Logging, excepciones, Result pattern
│   ├── bot/                    # Telegram handlers y menus
│   ├── llm/                    # Parser LLM (Groq con fallback)
│   ├── calendar_api/           # Google Calendar wrapper
│   ├── db/                     # Modelos, repositorio, cache
│   └── orchestrator/           # Logica de negocio central
├── tests/                      # Tests unitarios y de integracion
│   ├── unit/
│   └── integration/
├── skills/                     # Documentacion tecnica por modulo
├── specs/                      # Especificaciones por sprint
├── data/                       # SQLite DB (auto-generado)
├── logs/                       # Archivos de log (auto-generado)
└── pyproject.toml              # Dependencias y metadata
```

---

## Variables de entorno

| Variable                      | Requerida | Default                            | Descripcion                    |
| ----------------------------- | --------- | ---------------------------------- | ------------------------------ |
| `TELEGRAM_BOT_TOKEN`         | Si        | —                                  | Token del bot de Telegram      |
| `ADMIN_TELEGRAM_IDS`         | Si        | —                                  | IDs de admins (formato JSON)   |
| `EDITOR_TELEGRAM_IDS`        | No        | `[]`                               | IDs de editors (formato JSON)  |
| `GROQ_API_KEY`               | Si        | —                                  | API key de Groq                |
| `GROQ_MODEL_PRIMARY`         | No        | `llama-3.3-70b-versatile`          | Modelo LLM primario            |
| `GROQ_MODEL_FALLBACK`        | No        | `llama-3.1-8b-instant`             | Modelo LLM de respaldo         |
| `GOOGLE_CALENDAR_ID`         | Si        | —                                  | ID del calendario de Google    |
| `GOOGLE_SERVICE_ACCOUNT_PATH`| No        | `credentials/service_account.json` | Ruta al archivo de credenciales|
| `SQLITE_DB_PATH`             | No        | `data/crm.db`                      | Ruta de la base de datos       |
| `WORK_DAYS_WEEKDAY_START`    | No        | `15:00`                            | Inicio jornada Lunes-Viernes   |
| `WORK_DAYS_WEEKDAY_END`      | No        | `21:00`                            | Fin jornada Lunes-Viernes      |
| `WORK_DAYS_SATURDAY_START`   | No        | `08:00`                            | Inicio jornada Sabado          |
| `WORK_DAYS_SATURDAY_END`     | No        | `20:00`                            | Fin jornada Sabado             |
| `TIMEZONE`                    | No        | `America/Argentina/Buenos_Aires`   | Zona horaria                   |
| `LOG_LEVEL`                   | No        | `DEBUG`                            | Nivel de logging               |
| `LOG_FILE`                    | No        | `logs/agente.log`                  | Ruta del archivo de log        |

---

## Tipos de servicio y colores en Calendar

| Tipo             | Color en Calendar  |
| ---------------- | ------------------ |
| Instalacion      | Azul (Blueberry)   |
| Revision         | Amarillo (Banana)  |
| Mantenimiento    | Naranja (Tangerine)|
| Reparacion       | Naranja (Tangerine)|
| Presupuesto      | Amarillo (Banana)  |
| Otro             | Gris (Graphite)    |
| Completado       | Verde (Sage)       |

---

## Roles y permisos

| Accion            | Admin | Editor |
| ----------------- | ----- | ------ |
| Crear Evento      | Si    | No     |
| Editar Evento     | Si    | Si     |
| Ver Eventos       | Si    | Si     |
| Eliminar Evento   | Si    | No     |
| Terminar Evento   | Si    | Si     |
| Ver Contactos     | Si    | Si     |
| Editar Contacto   | Si    | No     |

---

## Troubleshooting

**El bot no arranca / error de configuracion:**
```bash
# Verificar que .env tiene todos los campos obligatorios
cat .env | grep -E "^(TELEGRAM_BOT_TOKEN|ADMIN_TELEGRAM_IDS|GROQ_API_KEY|GOOGLE_CALENDAR_ID)="
```

**Error de permisos de Google Calendar:**
```bash
# Verificar que el archivo de credenciales existe
ls -la credentials/service_account.json
```

**Ver si el bot esta corriendo:**
```bash
ps aux | grep "src.main"
```

**Matar el bot si quedo colgado:**
```bash
pkill -f "src.main"
```

**Revisar logs de error:**
```bash
grep ERROR logs/agente.log | tail -20
```



# Restart bot
$ kill 248588 2>/dev/null; sleep 2; nohup .venv/bin/python -m src.main > /dev/null 2>&1 & sleep 3 && ps aux | grep "[p]ython -m src.main"
emisora+  257863  0.0  0.0   7436  3684 ?        Ss   23:10   0:00 /bin/bash -c kill 248588 2>/dev/null; sleep 2; nohup .venv/bin/python -m src.main > /dev/null 2>&1 & sleep 3 && ps aux | grep "[p]ython -m src.main"
emisora+  257878 29.5  0.4 248096 78992 ?        Sl   23:10   0:00 .venv/bin/python -m src.mai