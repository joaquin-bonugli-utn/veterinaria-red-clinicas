# Veterinaria – Red de Clínicas y Derivación de Laboratorio

TP Integrador DAO 2026 – Tema 2. Aplicación de escritorio para una red de clínicas veterinarias:
clientes, mascotas e historias clínicas, agenda de turnos, atención clínica con vacunas y tratamientos,
derivación de muestras a un laboratorio central con trazabilidad completa (empaquetado, cadena de envío,
recepción y resultados), facturación y reportes PDF.

**Tecnologías:** Python 3.11+, SQLite (`sqlite3`, sin ORM), Flet (interfaz), ReportLab + Matplotlib (reportes), pytest.

---

## Instalación

```bash
python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

python -m pip install -r requirements.txt
```

## Cargar datos de prueba

```bash
python db/seed.py
```

Borra y recrea `veterinaria.db` con el esquema de `db/schema.sql` y carga datos de ejemplo **a través de
los servicios** (sin INSERT directos), así cada dato pasa por las reglas de negocio:

- 3 clínicas, 1 laboratorio central, 6 veterinarios, 3 especies con sus vacunas obligatorias
- 15 clientes, 25 mascotas y sus historias clínicas
- turnos y atenciones de los últimos 3 meses (más 2 semanas de agenda futura), urgencias sin turno
- 10 órdenes de derivación, 5 remitos con tramos: uno completo, uno con **precinto roto**, uno con una
  muestra de **viabilidad vencida**, uno con resultados parciales y uno en tránsito
- resultados de laboratorio y comprobantes

Las fechas son relativas al día de ejecución y el azar usa una semilla fija: el resultado es reproducible.
Al terminar se imprime la cantidad de filas por tabla.

## Ejecutar

```bash
python main.py          # o: flet run main.py
```

La primera vez Flet prepara su cliente de escritorio (tarda un poco). `main.py` crea la base si no existe;
para tener datos, correr antes `python db/seed.py`.

Secciones de la ventana (NavigationRail): **Clientes, Mascotas, Turnos, Atención, Derivaciones** (con la línea
de tiempo de estados de cada muestra), **Envíos, Laboratorio, Comprobantes y Reportes**. Los errores de negocio
se muestran en un SnackBar rojo.

### Reportes desde la consola

```bash
python reportes/generar_todos.py                                   # últimos 3 meses, todas las clínicas
python reportes/generar_todos.py --desde 2026-08-01 --hasta 2026-10-31 --clinica 1
```

Los PDF se guardan en `salida/`:

| # | Reporte | Gráfico |
|---|---|---|
| 1 | Atenciones clínicas y derivaciones por clínica y mes | Barras agrupadas |
| 2 | Muestras rechazadas por fallas en el transporte, por transportista y clínica, con motivo | Barras apiladas |
| 3 | Tratamientos aplicados y vacunas pendientes/vencidas por mascota, con datos del responsable | Barras |
| 4 | Facturación por clínica y tipo de servicio (Atención / Vacuna / Análisis), con totales | Torta + barras |
| 5 | Tiempo promedio de tránsito y de procesamiento por tipo de análisis (horas) | Barras horizontales |

### Tests

```bash
python -m pytest -q
```

Todos los tests usan una base en memoria (`:memory:`). Incluyen pruebas de punta a punta de los procesos
(`tests/test_procesos.py`), de la carga de datos de prueba y de las vistas de la UI sin abrir ventana.

---

## Estructura del proyecto

```
├── main.py                       # arranca la app Flet (ft.run(main))
├── db/
│   ├── schema.sql                # DDL: 26 tablas, triggers del historial inmutable (fuente de verdad del DER)
│   └── seed.py                   # datos de prueba (usa los servicios)
├── persistencia/
│   ├── conexion.py               # Singleton: única conexión sqlite3 (PRAGMA foreign_keys = ON)
│   └── repositorios/             # un repositorio por agregado; ABMC genérico en base.py
│       └── reportes.py           # consultas SQL agregadas de los 5 reportes
├── dominio/                      # entidades y reglas puras (sin SQL ni UI)
│   ├── red.py, clientes.py, atencion.py, derivacion.py, envio.py, facturacion.py
│   ├── estados_muestra.py        # State de la muestra
│   ├── estados_remito.py         # State del remito
│   ├── tarifas.py                # Strategy de cálculo de importes
│   ├── validaciones.py           # validaciones de campos (obligatorios, números, fechas ISO)
│   └── excepciones.py            # ReglaNegocioError y derivadas
├── servicios/                    # casos de uso: validaciones de negocio + transacciones
├── reportes/                     # 5 reportes PDF (Template Method en base.py) y generar_todos.py
├── ui/                           # vistas Flet: una clase por sección, solo llaman a servicios
└── tests/                        # pytest
```

### Arquitectura en capas

`ui → servicios → dominio / persistencia`

- **ui/** no tiene SQL ni accede a repositorios: cada vista llama a servicios (`ServicioReportes` es la
  fachada de los reportes para la UI).
- **servicios/** orquesta repositorios y decide la transacción: cada caso de uso que modifica datos hace
  `commit()` si todo sale bien y `rollback()` si algo falla (los repositorios nunca hacen commit).
- **persistencia/** es la única capa con SQL; todas las consultas son parametrizadas con `?`.
- **dominio/** contiene las entidades con sus validaciones y las reglas que no dependen de la base.

---

## Reglas de negocio

| # | Regla | Dónde | Tests |
|---|---|---|---|
| 1 | Toda mascota tiene un cliente responsable (activo) | `Mascota.__init__`, `ServicioMascotas.alta` | `test_servicio_mascotas.py` |
| 2 | Precinto roto → remito Rechazado, muestras Rechazada, sin resultados (`PrecintoRotoError`) | `ServicioLaboratorio.recibir/registrar_resultado` | `test_servicio_derivacion.py`, `test_procesos.py` |
| 3 | Historial de estados inmutable (solo INSERT) | triggers de `schema.sql`, `RepositorioDerivaciones`, `CambioEstadoMuestra` | `test_repositorios.py`, `test_estados.py` |
| 4 | Cada transición la decide el objeto Estado; inválida → `TransicionInvalidaError`; estado + historial en la misma transacción | `estados_muestra.py`, `estados_remito.py` | `test_estados.py` |
| 5 | Sin superposición de turnos por veterinario (ignora cancelados) → `TurnoSuperpuestoError` | `ServicioTurnos`, `RepositorioTurnos.buscar_superpuestos` | `test_servicio_turnos.py` |
| 6 | Al registrar una atención se devuelven las vacunas obligatorias pendientes/vencidas según especie y edad | `ServicioAtencion.vacunas_pendientes` | `test_servicio_atencion.py` |
| 7 | Empaquetado: conservadora Disponible, capacidad suficiente, rango de temperatura compatible con el análisis | `ServicioEnvios.empaquetar`, `Conservadora.es_compatible_con` | `test_servicio_derivacion.py` |

Otras reglas implementadas: DNI, matrícula, nombres y precintos únicos; un cliente con mascotas activas no
puede darse de baja; una atención no se factura dos veces; los análisis de muestras rechazadas no se facturan;
la orden pasa a Finalizada cuando todas sus muestras están Analizada o Rechazada.

---

## Patrones de diseño

### State – `dominio/estados_muestra.py`, `dominio/estados_remito.py`
`EstadoMuestra` (ABC) declara las operaciones `empaquetar`, `despachar`, `recibir`, `rechazar` y
`registrar_resultado`; por defecto todas lanzan `TransicionInvalidaError`. Cada estado concreto
(`Extraida`, `Empaquetada`, `EnTransito`, `Recibida`, `Analizada`, `Rechazada`) sobreescribe solo las
transiciones que permite el diagrama y avanza con `muestra.cambiar_estado(...)`, que además agrega el
registro al historial. `Muestra` es el contexto y delega en su estado. Lo mismo, más simple, para el remito
(`Emitido → En tránsito → Recibido | Rechazado`).

```
Extraída → Empaquetada → En tránsito → Recibida → Analizada
                              └─(precinto roto)→ Rechazada ←─(viabilidad / temperatura)─┘
```

### Singleton – `persistencia/conexion.py`
`Conexion.obtener()` devuelve siempre la misma instancia, que envuelve la única conexión `sqlite3`. Así
todos los repositorios comparten la transacción en curso y un servicio puede confirmar o deshacer en un solo
paso. El constructor exige un token privado: instanciar `Conexion(...)` directamente lanza `TypeError`.

### Strategy – `dominio/tarifas.py`
`EstrategiaTarifa` (ABC) define `calcular(precio_base, cantidad)`; las estrategias concretas son
`TarifaNormal`, `TarifaUrgencia` (+30 %) y `TarifaControl` (-20 %). `CalculadoraImporte` es el contexto y
la cambia con `cambiar_estrategia()`. `ServicioFacturacion` elige la estrategia según `tipo_atencion.nombre`
y la aplica a cada ítem del comprobante.

### Template Method (adicional) – `reportes/base.py`
`Reporte.generar()` arma el documento (título, filtros, pie con numeración) y delega el cuerpo en
`contenido()`, que implementa cada uno de los 5 reportes.

---

## Decisiones y limitaciones

- **Tarifas:** la tarifa del tipo de atención se aplica a todos los ítems del comprobante (atención,
  vacunas y análisis).
- **Reporte 2:** cada rechazo se atribuye al transportista del último tramo (el que entregó en el laboratorio).
- **Fechas pasadas:** se permiten turnos y atenciones con fecha pasada, para poder cargar el historial.
- **Concurrencia:** la conexión se comparte entre los hilos de Flet (`check_same_thread=False`). Es una app de
  escritorio de un solo usuario, así que no hay escrituras concurrentes.
- **Búsquedas con acentos:** el `LIKE` y el `ORDER BY` de SQLite distinguen acentos ("go" no encuentra
  "Gómez").
