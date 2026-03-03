# 📅 Agente Calendario — Asistente Inteligente de Gestión de Servicios

> **Bot de Telegram con IA** para la gestión integral de servicios técnicos:
> agenda, clientes, calendario de Google y cierre de trabajos — todo desde una conversación natural.

---

## 1. Visión General

**Agente Calendario** es un bot de Telegram que funciona como asistente virtual
inteligente para empresas de servicios técnicos (cámaras de seguridad, alarmas,
porteros eléctricos, software, etc.).

El bot permite a los usuarios gestionar su agenda de servicios mediante
**botones interactivos** o **mensajes en lenguaje natural**, manteniendo
sincronizados una **base de datos SQLite** y un **Google Calendar** compartido.

### ¿Por qué este proyecto?

| Problema                                   | Solución                                          |
| ------------------------------------------ | ------------------------------------------------- |
| Agendas manuales en papel o WhatsApp       | Bot centralizado con recordatorios automáticos     |
| Datos de clientes dispersos                | Base de datos CRM liviana integrada                |
| Sin historial de servicios realizados      | Cierre de eventos con fotos, montos y notas        |
| Coordinación entre técnicos es caótica     | Calendario compartido con colores por tipo         |
| Requiere hardware potente                  | Corre en Ubuntu Server con recursos mínimos        |

---

## 2. Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────┐
│                      TELEGRAM (Usuario)                     │
│         ┌────────────┐    ┌─────────────────────┐           │
│         │  Botones    │    │  Mensaje en texto   │           │
│         │  (Menú)     │    │  (lenguaje natural) │           │
│         └─────┬───────┘    └──────────┬──────────┘           │
│               │                       │                      │
│               └───────────┬───────────┘                      │
│                           ▼                                  │
│              ┌────────────────────────┐                      │
│              │   Telegram Bot API     │                      │
│              │  (python-telegram-bot) │                      │
│              └────────────┬───────────┘                      │
└───────────────────────────┼──────────────────────────────────┘
                            ▼
               ┌────────────────────────┐
               │     Orquestador        │
               │   (Lógica Central)     │
               └──┬────────┬────────┬───┘
                  │        │        │
         ┌────────┘        │        └────────┐
         ▼                 ▼                 ▼
┌─────────────┐  ┌─────────────────┐  ┌──────────────┐
│   Parser    │  │   Repositorio   │  │   Google     │
│   LLM      │  │   SQLite        │  │   Calendar   │
│  (Groq /   │  │   (Clientes,    │  │   API        │
│   Gemini)  │  │    Eventos)     │  │              │
└─────────────┘  └─────────────────┘  └──────────────┘
```

### Stack Tecnológico

| Componente          | Tecnología                                  |
| ------------------- | ------------------------------------------- |
| Bot                 | `python-telegram-bot` v20+                  |
| LLM                 | Groq (primario) / Gemini / OpenAI (backup)  |
| Base de Datos       | SQLite 3 con WAL mode                       |
| Calendario          | Google Calendar API v3                       |
| Caché               | LRU in-memory (TTL configurable)            |
| Validación          | Pydantic v2                                  |
| Testing             | pytest + pytest-asyncio                      |
| Deploy              | Ubuntu Server (recursos mínimos)            |
| Lenguaje            | Python 3.11+                                 |

---

## 3. Funcionalidades Principales

### 3.1 Menú de Botones

Al iniciar el bot o enviar `/menu`, el usuario ve los siguientes botones:

| Botón                | Acción                                                  | Permisos          |
| -------------------- | ------------------------------------------------------- | ------------------ |
| 📝 Crear Evento      | Solicita descripción en lenguaje natural y agenda       | Solo Admin         |
| ✏️ Editar Evento     | Muestra lista de eventos pendientes para seleccionar    | Admin + Editor     |
| 📋 Ver Eventos       | Lista todos los eventos pendientes de forma prolija     | Admin + Editor     |
| 🗑️ Eliminar Evento  | Muestra eventos pendientes para seleccionar y eliminar  | Solo Admin         |
| ✅ Terminar Evento   | Muestra eventos del día para marcar como completado     | Admin + Editor     |
| 👥 Ver Contactos     | Lista todos los clientes registrados                    | Admin + Editor     |
| ✏️ Editar Contacto   | Muestra contactos para editar nombre, dirección o tel.  | Solo Admin         |

### 3.2 Lenguaje Natural (Sin botones)

Si el usuario **no presiona ningún botón** y escribe directamente en el chat,
el LLM interpreta la intención y ejecuta la acción correspondiente.

**Ejemplos de mensajes naturales:**

```
"Agendar instalación de 3 cámaras para Juan Pérez en Balcarce 132,
 teléfono 351-1234567, el viernes a las 16:00"

"¿Qué eventos tengo para mañana?"

"Cambiar la hora del evento de García a las 18:00"

"Marcar como terminado el evento de hoy de López,
 se cobraron $45000 y se instalaron 2 cámaras"
```

### 3.3 Flujo Mixto (Botón + Lenguaje Natural)

Después de presionar un botón, el bot hace una pregunta y el usuario responde
en lenguaje natural. El LLM interpreta la respuesta en contexto.

```
Bot:  "Describí el evento a crear:"
User: "Mañana a las 10 revisión de alarma en casa de Martínez,
       calle San Martín 456, tel 351-9876543"
```

---

## 4. Tipos de Servicio y Colores

Cada tipo de servicio tiene un color asignado en Google Calendar para
identificación visual rápida:

| Tipo de Servicio       | Color en Google Calendar | ID Color |
| ---------------------- | ------------------------ | -------- |
| 🔵 Instalación         | Azul (Blueberry)         | `9`      |
| 🟡 Revisión            | Amarillo (Banana)        | `5`      |
| 🟠 Mantenimiento       | Naranja oscuro (Tangerine)| `6`     |
| 🟠 Reparación          | Naranja oscuro (Tangerine)| `6`     |
| 🟡 Presupuesto         | Amarillo (Banana)        | `5`      |
| ⚪ Otro                | Gris (Graphite)          | `8`      |
| 🟢 Servicio Completado | Verde (Sage)             | `2`      |

---

## 5. Modelo de Datos

### 5.1 Tabla `clientes`

| Campo          | Tipo         | Descripción                          |
| -------------- | ------------ | ------------------------------------ |
| `id`           | INTEGER PK   | Identificador único auto-incremental |
| `nombre`       | TEXT NOT NULL | Nombre completo del cliente          |
| `telefono`     | TEXT UNIQUE   | Teléfono de contacto                |
| `direccion`    | TEXT         | Dirección principal                   |
| `notas`        | TEXT         | Observaciones adicionales             |
| `created_at`   | DATETIME     | Fecha de creación                    |
| `updated_at`   | DATETIME     | Última actualización                 |

### 5.2 Tabla `eventos`

| Campo              | Tipo         | Descripción                              |
| ------------------ | ------------ | ---------------------------------------- |
| `id`               | INTEGER PK   | Identificador único auto-incremental     |
| `cliente_id`       | INTEGER FK   | Referencia a `clientes.id`               |
| `google_event_id`  | TEXT UNIQUE  | ID del evento en Google Calendar          |
| `tipo_servicio`    | TEXT NOT NULL | Enum: instalación, revisión, etc.        |
| `fecha_hora`       | DATETIME     | Fecha y hora programada                   |
| `duracion_minutos` | INTEGER      | Duración estimada (default: 60)          |
| `estado`           | TEXT         | pendiente / completado / cancelado        |
| `notas`            | TEXT         | Notas del servicio                        |
| `trabajo_realizado`| TEXT         | Descripción post-servicio                 |
| `monto_cobrado`    | REAL         | Monto cobrado al completar               |
| `notas_cierre`     | TEXT         | Observaciones de cierre                   |
| `fotos`            | TEXT         | Rutas de fotos (JSON array)              |
| `created_at`       | DATETIME     | Fecha de creación                        |
| `updated_at`       | DATETIME     | Última actualización                     |

### 5.3 Tabla `usuarios_autorizados`

| Campo          | Tipo         | Descripción                           |
| -------------- | ------------ | ------------------------------------- |
| `id`           | INTEGER PK   | Identificador único                   |
| `telegram_id`  | INTEGER UNIQUE | ID de Telegram del usuario          |
| `nombre`       | TEXT         | Nombre para logs                      |
| `rol`          | TEXT NOT NULL | `admin` o `editor`                   |
| `activo`       | BOOLEAN      | Si el usuario está habilitado         |
| `created_at`   | DATETIME     | Fecha de alta                         |

---

## 6. Formato de Eventos en Google Calendar

### Título
```
{Nombre del Cliente} — {Teléfono}
```

### Ubicación
```
{Dirección del cliente}
```

### Descripción
```
📋 Tipo: Instalación
📍 Dirección: Balcarce 132
📝 Notas: Poner 3 cámaras y cambiar 1 batería de alarma

── Post-servicio (completar al terminar) ──
✅ Trabajo realizado:
💰 Monto cobrado:
📝 Notas de cierre:
📷 Fotos:
```

---

## 7. Roles y Permisos

```
┌──────────────────────────────────────────────────────────────┐
│                        PERMISOS                              │
├──────────────┬───────────────────────────────────────────────┤
│              │ Crear │ Editar │ Ver │ Eliminar │ Terminar │  │
│              │ Evento│ Evento │Event│ Evento   │ Evento   │  │
├──────────────┼───────┼────────┼─────┼──────────┼──────────┤  │
│ Admin        │  ✅   │  ✅    │ ✅  │   ✅     │   ✅     │  │
│ Editor       │  ❌   │  ✅    │ ✅  │   ❌     │   ✅     │  │
│ No autorizado│  ❌   │  ❌    │ ❌  │   ❌     │   ❌     │  │
└──────────────┴───────┴────────┴─────┴──────────┴──────────┘
```

- **Admin**: Puede haber varios. Se configuran por `TELEGRAM_ID` en `.env`.
- **Editor**: Acceso limitado. Se configuran por `TELEGRAM_ID` en `.env`.
- **No autorizado**: Recibe mensaje de "Acceso denegado".

---

## 8. Casos de Uso Detallados

### CU-01: Crear Evento (Admin)

**Actor:** Usuario Admin  
**Precondición:** El usuario tiene rol Admin.  
**Flujo principal:**
1. El usuario presiona "📝 Crear Evento" o envía un mensaje natural.
2. El bot solicita la descripción del evento.
3. El usuario describe en lenguaje natural (ej: "Mañana a las 10, instalación de cámaras para Juan, Balcarce 132, tel 351-123456").
4. El LLM extrae: cliente, tipo de servicio, fecha/hora, dirección, notas.
5. Si el cliente no existe, se crea automáticamente en la BD.
6. Se crea el evento en SQLite y en Google Calendar con el color correspondiente.
7. El bot confirma con un resumen del evento creado.

**Flujo alternativo:**
- 4a. El LLM no puede extraer datos suficientes → El bot pregunta lo faltante.
- 6a. Conflicto de horario → El bot informa y sugiere alternativas.

---

### CU-02: Editar Evento (Admin / Editor)

**Actor:** Usuario Admin o Editor  
**Flujo principal:**
1. El usuario presiona "✏️ Editar Evento" o envía un mensaje natural.
2. El bot muestra los eventos pendientes en botones inline.
3. El usuario selecciona el evento a editar.
4. El bot pregunta qué desea modificar.
5. El usuario describe los cambios en lenguaje natural.
6. El LLM interpreta, actualiza SQLite y Google Calendar.
7. El bot confirma los cambios.

---

### CU-03: Ver Eventos (Admin / Editor)

**Actor:** Usuario Admin o Editor  
**Flujo principal:**
1. El usuario presiona "📋 Ver Eventos" o pregunta en lenguaje natural.
2. El bot muestra todos los eventos pendientes agrupados por día.
3. Cada evento muestra: hora, cliente, tipo, dirección (formato compacto).

**Formato de respuesta:**
```
📅 Lunes 03/03/2026
─────────────────────
🔵 10:00 — Juan Pérez
   Instalación · Balcarce 132

🟡 14:00 — María García
   Revisión · San Martín 456

📅 Martes 04/03/2026
─────────────────────
🟠 09:00 — Pedro López
   Reparación · Belgrano 789
```

---

### CU-04: Eliminar Evento (Admin)

**Actor:** Usuario Admin  
**Flujo principal:**
1. El usuario presiona "🗑️ Eliminar Evento" o envía un mensaje natural.
2. El bot muestra eventos pendientes.
3. El usuario selecciona el evento a eliminar.
4. El bot pide confirmación.
5. Se elimina de SQLite y Google Calendar.
6. El bot confirma la eliminación.

---

### CU-05: Terminar Evento (Admin / Editor)

**Actor:** Usuario Admin o Editor  
**Flujo principal:**
1. El usuario presiona "✅ Terminar Evento".
2. El bot muestra los eventos **del día actual**.
3. El usuario selecciona el evento completado.
4. El bot solicita: trabajo realizado, monto cobrado, notas de cierre.
5. Opcionalmente el usuario envía fotos.
6. Se actualiza el evento en SQLite (estado → completado).
7. Se actualiza Google Calendar: color → verde, descripción con datos de cierre.
8. El bot confirma el cierre del servicio.

---

### CU-06: Ver Contactos (Admin / Editor)

**Actor:** Usuario Admin o Editor  
**Flujo principal:**
1. El usuario presiona "👥 Ver Contactos".
2. El bot muestra la lista de clientes registrados:
   ```
   👤 Juan Pérez — 351-1234567
   📍 Balcarce 132
   
   👤 María García — 351-9876543
   📍 San Martín 456
   ```

---

### CU-07: Editar Contacto (Admin)

**Actor:** Usuario Admin  
**Flujo principal:**
1. El usuario presiona "✏️ Editar Contacto".
2. El bot muestra los contactos disponibles.
3. El usuario selecciona el contacto.
4. El bot pregunta qué desea modificar (nombre, dirección, teléfono).
5. El usuario responde en lenguaje natural.
6. Se actualiza la BD.
7. El bot confirma los cambios.

---

## 9. Lineamientos Técnicos

### 9.1 Principios de Diseño

- **KISS**: Simplicidad ante todo. SQLite sobre PostgreSQL, archivos `.env` sobre config servers.
- **SOLID**: Cada módulo tiene una responsabilidad clara y bien definida.
- **DRY**: Lógica reutilizable centralizada en el orquestador.
- **Fail-Safe**: Si el LLM falla, el bot ofrece opciones de botones como fallback.
- **Offline-First DB**: SQLite es la fuente de verdad; Calendar es la vista compartida.

### 9.2 Manejo de Errores

- Reintentos con backoff exponencial para APIs externas (Groq, Google).
- Fallback de LLM: Si Groq falla → Gemini → OpenAI.
- Logging estructurado con rotación de archivos.
- Mensajes de error amigables al usuario, logs técnicos en archivo.

### 9.3 Seguridad

- Validación de `TELEGRAM_ID` en cada mensaje recibido.
- Variables sensibles en `.env` (nunca en código fuente).
- `credentials/` en `.gitignore`.
- Rate limiting por usuario para prevenir abuso.

### 9.4 Rendimiento (Recursos Mínimos)

- SQLite con WAL mode para concurrencia ligera.
- Caché LRU para contactos frecuentes.
- Polling de Telegram (no webhooks) para simplificar deploy.
- Sin servicios externos adicionales (Redis, RabbitMQ, etc.).

---

## 10. Estructura del Proyecto

```
calendario/
├── idea_general_proyecto.md    # Este documento
├── .env                        # Variables de entorno (no versionado)
├── .env.example                # Plantilla de variables de entorno
├── credentials/                # Service account de Google (no versionado)
│   └── service_account.json
├── skills/                     # Módulos de conocimiento técnico
│   └── <skill>/
│       ├── SKILL.md
│       └── references/
├── specs/                      # Especificaciones técnicas por sprint
│   ├── README.md
│   ├── diagram.md
│   ├── sprint-1/
│   ├── sprint-2/
│   ├── sprint-3/
│   ├── sprint-4/
│   ├── sprint-5/
│   └── post-mvp/
├── src/                        # Código fuente
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuración centralizada (Pydantic)
│   ├── bot/                    # Telegram handlers y menús
│   ├── llm/                    # Parser LLM (Groq / Gemini)
│   ├── calendar_api/           # Google Calendar wrapper
│   ├── db/                     # Modelos, repositorio, migraciones
│   └── orchestrator/           # Lógica de negocio central
├── tests/                      # Tests unitarios y de integración
├── data/                       # SQLite database (auto-generado)
├── logs/                       # Archivos de log (auto-generado)
├── pyproject.toml              # Dependencias y metadata
└── README.md                   # Guía de inicio rápido
```

---

## 11. Roadmap de Sprints

| Sprint   | Entregable                                         | Semana Est. |
| -------- | -------------------------------------------------- | ----------- |
| Sprint 1 | Configuración, DB, modelos, repositorio, caché     | Semana 1    |
| Sprint 2 | Parser LLM (Groq) con fallback                     | Semana 2    |
| Sprint 3 | Google Calendar: CRUD de eventos                    | Semana 3    |
| Sprint 4 | Bot Telegram: menú, handlers, flujo interactivo     | Semana 4    |
| Sprint 5 | Orquestador: integración completa + cierre servicio | Semana 5    |
| Post-MVP | Notificaciones, reportes, multi-calendario, web UI  | Futuro      |

---

## 12. Referencias

- [Documentación de Skills](skills/)
- [Especificaciones por Sprint](specs/)
- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)
- [Google Calendar API](https://developers.google.com/calendar/api)
- [Groq API](https://console.groq.com/docs)
- [SQLite Best Practices](https://www.sqlite.org/bestpractice.html)