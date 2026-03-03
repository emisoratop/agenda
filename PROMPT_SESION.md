# Prompt para Nuevas Sesiones — Agente Calendario

Usá este prompt al inicio de una nueva sesión con tu asistente de IA para
retomar el trabajo de forma efectiva.

---

## Prompt Base (copiá y pegá)

```
Estoy trabajando en el proyecto "Agente Calendario" — un bot de Telegram con
IA para gestión de servicios técnicos (cámaras de seguridad, alarmas, porteros,
software).

## Documentación del proyecto
- Documento principal: @idea_general_proyecto.md
- Skills (6 módulos técnicos): carpeta skills/
- Specs (5 sprints + backlog): carpeta specs/
- README con setup: README.md

## Stack
Python 3.11+ | python-telegram-bot v20+ | SQLite (WAL) + aiosqlite |
Groq/Gemini LLM | Google Calendar API v3 | Pydantic v2 | pytest

## Sprints
1. Config core + Database (specs/sprint-1/)
2. LLM Parser con Groq (specs/sprint-2/)
3. Google Calendar CRUD (specs/sprint-3/)
4. Telegram Bot handlers (specs/sprint-4/)
5. Orquestador + integración (specs/sprint-5/)

## Lo que necesito ahora
[DESCRIBÍ ACÁ LO QUE NECESITÁS EN ESTA SESIÓN]

## Reglas
- Revisá las specs y skills antes de implementar.
- Seguí los patrones documentados (Repository, Result pattern, fallback chain).
- Escribí tests unitarios para toda función nueva.
- Marcá como ✅ los objetivos completados en las specs.
- Usá las excepciones de dominio definidas (no genéricas).
- Handlers de Telegram deben ser thin (solo delegar al Orquestador).
```

---

## Variantes del Prompt

### Para implementar un sprint específico

```
Necesito implementar el Sprint [1]. Revisá la/las spec en
specs/sprint-1/ y las skills referenciadas.
Implementá siguiendo los pasos de implementación y verificá
que los criterios de aceptación se cumplen.
Al terminar, ejecutá los tests y marcá los objetivos completados.
Responde siempre en español.
```

### Para corregir tests que fallan

```
Tengo tests que fallan en el proyecto. Ejecutá `pytest` para ver el estado
actual, analizá los errores, corregí el código y volvé a ejecutar los tests
hasta que pasen todos. Revisá las specs y skills para asegurarte de seguir
los patrones correctos.
```

### Para auditoría de código

```
Hacé una auditoría completa del Sprint [N]:
1. Revisá que el código siga los patrones de las skills referenciadas.
2. Verificá que los criterios de aceptación de la spec se cumplen.
3. Ejecutá los tests y verificá cobertura.
4. Listá cualquier inconsistencia o mejora necesaria.
5. Marcá como ✅ los objetivos completados en la spec.
```

### Para agregar una funcionalidad del backlog

```
Quiero implementar la funcionalidad "[nombre]" del backlog post-MVP
(specs/post-mvp/backlog.md). Diseñá la solución siguiendo los patrones
existentes del proyecto, creá una nueva spec si es necesario, implementá
y escribí tests.
```

---

## Notas

- Siempre empezá revisando las specs y skills relevantes.
- Las skills contienen ejemplos de código y anti-patrones a evitar.
- Las specs tienen checkboxes `[ ]` que se deben marcar como `[x]` al completar.
- El archivo `idea_general_proyecto.md` tiene la visión completa del proyecto.
