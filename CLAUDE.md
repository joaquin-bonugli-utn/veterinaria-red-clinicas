# TP Integrador DAO 2026 – Tema 2: Veterinaria (Red de Clínicas y Derivación de Laboratorio)

Contexto permanente del proyecto. Leer antes de cada tarea.

## Stack y reglas generales
- Python 3.11+, POO, sin frameworks ORM: persistencia con el módulo estándar `sqlite3`.
- Interfaz gráfica con **Flet** (`ft.run(main)`), reportes PDF con **ReportLab** y gráficos con **Matplotlib**.
- Código, nombres y comentarios en **español**, estilo PEP 8, type hints y docstrings breves.
- Consultas SQL SIEMPRE parametrizadas con `?` (nunca concatenar valores).
- Toda operación que modifique varias tablas va en una transacción: `commit()` si todo sale bien, `rollback()` si falla.
- Fechas como texto ISO: `YYYY-MM-DD` y `YYYY-MM-DD HH:MM`.
- No modificar `db/schema.sql` sin avisar: es el DER entregado. Si hace falta un cambio, proponerlo primero.

## Arquitectura en capas (respetar dependencias: ui → servicios → dominio / persistencia)
```
veterinaria/
├── main.py                  # arranca la app Flet
├── db/schema.sql            # DDL (fuente de verdad del DER)
├── db/seed.py               # datos de prueba
├── persistencia/
│   ├── conexion.py          # Singleton: única conexión sqlite3 (PRAGMA foreign_keys = ON)
│   └── repositorios/        # un repositorio por agregado: ABMC + consultas (devuelven objetos de dominio)
├── dominio/                 # entidades (clases) y reglas puras, sin SQL ni UI
│   ├── estados_muestra.py   # patrón State de la muestra
│   ├── estados_remito.py    # patrón State del remito
│   └── tarifas.py           # patrón Strategy de cálculo de importes
├── servicios/               # casos de uso + validaciones de negocio (orquestan repos y transacciones)
├── reportes/                # 5 reportes PDF (ReportLab + Matplotlib)
├── ui/                      # vistas Flet; solo llaman a servicios
└── tests/                   # pytest, base en memoria (':memory:')
```

## Reglas de negocio obligatorias
1. Toda mascota tiene un cliente responsable (id_cliente NOT NULL).
2. Si el precinto llega **roto** → remito `Rechazado` y todas sus muestras `Rechazada`; no se pueden cargar resultados.
3. Historial de estados de la muestra **inmutable** (solo INSERT; hay triggers en la BD). Secuencia:
   `Extraída → Empaquetada → En tránsito → Recibida → Analizada` (+ `Rechazada` desde En tránsito o Recibida).
4. Cada transición la decide el objeto Estado (patrón State). Transición inválida → `TransicionInvalidaError`.
   Cada transición: actualiza `muestra.estado_actual` + inserta en `historial_estado_muestra`, en la misma transacción.
5. Sin superposición de turnos por veterinario: `inicio_nuevo < fin_existente AND fin_nuevo > inicio_existente`
   (ignorar turnos Cancelados).
6. Al registrar una atención, verificar vacunas obligatorias de la especie según edad (edad_minima_dias, refuerzo_dias)
   y devolver la lista de pendientes/vencidas.
7. Empaquetado: conservadora `Disponible`, capacidad suficiente y rango de temperatura compatible con el TIPO_ANALISIS.

## Patrones de diseño
- **State**: `EstadoMuestra` (ABC) → Extraida, Empaquetada, EnTransito, Recibida, Analizada, Rechazada. Idem remito.
- **Singleton**: `Conexion` en `persistencia/conexion.py`.
- **Strategy**: `EstrategiaTarifa` (ABC) → TarifaNormal, TarifaUrgencia (+30 %), TarifaControl (-20 %).

## Cómo trabajar
- Implementar por etapas pequeñas y correr `python -m pytest -q` al terminar cada etapa.
- No crear archivos fuera de la estructura sin explicarlo.
- Al terminar una etapa, resumir qué archivos se crearon/modificaron y cómo probarlo.
