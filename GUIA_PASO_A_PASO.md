# Guía paso a paso – Construir el TP Veterinaria desde la consola de VS Code

Cada **Paso** tiene: (a) comandos de terminal y/o (b) un **prompt** para copiar y pegar en Claude Code
(abrilo en la terminal de VS Code con `claude`). Hacé los pasos en orden y **no avances si los tests fallan**.

---

## Paso 0 – Preparar el proyecto (terminal de VS Code)

**Windows (PowerShell):**
```powershell
mkdir veterinaria; cd veterinaria
python --version                      # 3.11 o superior
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --upgrade "flet[all]" reportlab matplotlib pytest
pip freeze > requirements.txt
mkdir db
git init
code .
```

**Linux / macOS:**
```bash
mkdir veterinaria && cd veterinaria
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip "flet[all]" reportlab matplotlib pytest
pip freeze > requirements.txt
mkdir db && git init && code .
```

Después **copiá a la carpeta** los archivos que te entregué:
- `CLAUDE.md` → en la raíz `veterinaria/` (Claude Code lo lee automáticamente en cada sesión).
- `schema.sql` → en `veterinaria/db/schema.sql`.

Abrí Claude Code en la terminal de VS Code:
```bash
claude
```

---

## Paso 1 – Estructura y persistencia (Singleton)

```text
Leé CLAUDE.md y db/schema.sql. Creá la estructura de carpetas indicada en CLAUDE.md con sus __init__.py.
Implementá persistencia/conexion.py con el patrón Singleton: clase Conexion con método de clase
obtener(ruta="veterinaria.db") que devuelva siempre la misma instancia; debe activar PRAGMA foreign_keys = ON,
usar row_factory = sqlite3.Row, exponer cursor(), commit(), rollback(), cerrar() y un método
inicializar_esquema() que ejecute db/schema.sql con executescript. Agregá un método reiniciar_para_tests(ruta=":memory:").
Creá tests/conftest.py con un fixture que use una base en memoria y tests/test_conexion.py que verifique:
que dos llamadas devuelven el mismo objeto, que las FK están activas y que existen las 26 tablas.
Corré python -m pytest -q y mostrame el resultado.
```

---

## Paso 2 – Clases de dominio

```text
En dominio/ creá las clases de dominio que corresponden a las tablas de db/schema.sql (Clinica, Laboratorio,
Veterinario, Cliente, Especie, Mascota, HistoriaClinica, Turno, TipoAtencion, Atencion, Vacuna, AplicacionVacuna,
Tratamiento, TipoAnalisis, OrdenDerivacion, Conservadora, RemitoBiologico, PrecintoSanitario, Muestra,
CambioEstadoMuestra, Transportista, TramoEnvio, Recepcion, ResultadoAnalisis, Comprobante, DetalleComprobante).
Usá clases normales con __init__ y atributos, validaciones simples en el constructor (campos obligatorios,
números no negativos, fechas ISO válidas) lanzando ValueError con mensajes en español, y __str__ legibles.
Mascota debe exigir un cliente responsable y tener un método edad_en_dias(fecha).
Creá dominio/excepciones.py con: ReglaNegocioError, TransicionInvalidaError(ReglaNegocioError),
TurnoSuperpuestoError(ReglaNegocioError), PrecintoRotoError(ReglaNegocioError).
No escribas SQL en esta capa. Agregá tests unitarios básicos y corré pytest.
```

---

## Paso 3 – Patrón State (núcleo de la trazabilidad)

```text
Implementá el patrón State en dominio/estados_muestra.py siguiendo el estilo de la guía de la cátedra
(clase abstracta con ABC y abstractmethod, el contexto delega en el estado y cambia con cambiar_estado()).
EstadoMuestra (ABC) define: nombre, empaquetar(muestra), despachar(muestra), recibir(muestra, precinto_intacto),
rechazar(muestra, motivo), registrar_resultado(muestra). Por defecto cada operación lanza TransicionInvalidaError;
cada estado concreto (Extraida, Empaquetada, EnTransito, Recibida, Analizada, Rechazada) sobreescribe solo las
transiciones que permite el diagrama:
Extraída→Empaquetada→En tránsito→Recibida→Analizada; En tránsito→Rechazada (precinto roto en recibir);
Recibida→Rechazada (viabilidad vencida o temperatura fuera de rango).
La clase Muestra guarda el objeto estado y una lista de CambioEstadoMuestra (estado, fecha_hora, responsable,
observacion) a la que solo se puede agregar. Incluí una función estado_desde_nombre(nombre) para reconstruir
el estado al leer de la base.
Hacé lo mismo, más simple, en dominio/estados_remito.py (Emitido→En tránsito→Recibido | Rechazado).
Escribí tests que cubran todas las transiciones válidas y al menos 5 inválidas. Corré pytest.
```

---

## Paso 4 – Repositorios (ABMC con sqlite3)

```text
En persistencia/repositorios/ creá un repositorio por agregado usando la Conexion Singleton:
RepositorioClientes, RepositorioMascotas (incluye historia clínica), RepositorioVeterinarios, RepositorioTurnos,
RepositorioAtenciones (incluye tratamientos y aplicaciones de vacuna), RepositorioCatalogos (especie, vacuna,
tipo_atencion, tipo_analisis, clinica, laboratorio, transportista), RepositorioDerivaciones (orden, muestra,
historial), RepositorioEnvios (conservadora, remito, precinto, tramo, recepción), RepositorioResultados y
RepositorioComprobantes.
Cada uno con: agregar, modificar, baja (lógica cuando hay campo activo), obtener_por_id, listar y búsquedas útiles
(ej. clientes por DNI/apellido, turnos de un veterinario en un rango). Los métodos devuelven objetos de dominio.
SQL parametrizado con ?. Los repositorios NO hacen commit: eso lo deciden los servicios.
El repositorio de muestras solo debe INSERTAR en historial_estado_muestra (nunca UPDATE/DELETE).
Tests con base en memoria para cada repositorio. Corré pytest.
```

---

## Paso 5 – Servicios: clientes, mascotas, turnos y atención

```text
Creá en servicios/: ServicioClientes, ServicioMascotas, ServicioTurnos y ServicioAtencion.
- ServicioMascotas.alta(): crea la mascota y su historia clínica en la MISMA transacción; rechaza si el cliente
  no existe o está inactivo.
- ServicioTurnos.reservar(): lanza TurnoSuperpuestoError si el veterinario ya tiene un turno no cancelado que
  se superpone (inicio_nuevo < fin_existente AND fin_nuevo > inicio_existente).
- ServicioAtencion.registrar(): registra la atención (con o sin turno; si tiene turno lo marca Atendido),
  tratamientos y vacunas aplicadas, calculando fecha_proxima_dosis con refuerzo_dias. Debe devolver también
  la lista de vacunas obligatorias pendientes o vencidas para la especie y edad de la mascota
  (método vacunas_pendientes(id_mascota, fecha)).
Usá try/commit/except rollback en cada caso de uso. Tests de cada validación (casos OK y casos de error). Corré pytest.
```

---

## Paso 6 – Servicios: derivación, empaquetado, envío, recepción y resultados

```text
Creá ServicioDerivacion, ServicioEnvios y ServicioLaboratorio en servicios/, usando el patrón State del Paso 3:
1. emitir_orden(id_atencion, id_laboratorio, muestras=[(id_tipo_analisis, volumen_ml)...]): crea la orden y las
   muestras en estado Extraída (con su primer registro en el historial).
2. empaquetar(ids_muestras, id_conservadora, numero_precinto, temp_cierre): valida conservadora Disponible,
   capacidad suficiente y que temp_cierre esté dentro del rango de cada TIPO_ANALISIS y de la conservadora;
   genera remito (número correlativo REM-AAAA-00001) y precinto; muestras → Empaquetada; conservadora → En uso.
3. registrar_tramo(id_remito, id_transportista, origen, destino, salida, llegada, temperatura): primer tramo pasa
   remito y muestras a En tránsito.
4. recibir(id_remito, receptor, precinto_intacto, temperatura_llegada): si el precinto está roto → remito
   Rechazado, precinto Roto, todas las muestras Rechazada con motivo; si está intacto → Recibido/Recibida, pero
   rechazar individualmente las muestras con viabilidad vencida (horas desde la extracción > horas_viabilidad)
   o temperatura fuera de rango. Siempre libera la conservadora (Disponible).
5. registrar_resultado(id_muestra, bioquimico, valores, conclusion): solo si la muestra está Recibida → Analizada.
   Si todas las muestras de la orden terminaron, la orden pasa a Finalizada.
Todo en transacciones. Tests del flujo feliz completo y del flujo con precinto roto. Corré pytest.
```

---

## Paso 7 – Patrón Strategy y comprobantes

```text
Implementá dominio/tarifas.py con el patrón Strategy (estilo de la guía de la cátedra): EstrategiaTarifa (ABC)
con calcular(precio_base, cantidad); TarifaNormal, TarifaUrgencia (+30 %) y TarifaControl (-20 %), y una
CalculadoraImporte con cambiar_estrategia(). La estrategia se elige según tipo_atencion.nombre.
Creá ServicioFacturacion.emitir_comprobante(id_atencion): genera comprobante (número correlativo) con detalle
de la atención, las vacunas aplicadas y los análisis de las muestras NO rechazadas de esa atención; calcula
subtotales y total. No permitir facturar dos veces la misma atención. Tests. Corré pytest.
```

---

## Paso 8 – Datos de prueba

```text
Creá db/seed.py que reinicie veterinaria.db, aplique db/schema.sql y cargue datos realistas usando los SERVICIOS
(no INSERT directos, así se validan las reglas): 3 clínicas, 1 laboratorio central, 6 veterinarios,
3 especies con sus vacunas obligatorias, 15 clientes, 25 mascotas, turnos y atenciones de los últimos 3 meses,
10 órdenes de derivación con muestras, 5 remitos con tramos (al menos 1 con precinto roto y 1 con una muestra
de viabilidad vencida), resultados y comprobantes. Ejecutalo con python db/seed.py y mostrame un resumen de
cantidades por tabla.
```

---

## Paso 9 – Reportes (ReportLab + Matplotlib)

```text
En reportes/ implementá 5 reportes PDF no triviales (con filtros de fecha desde/hasta y clínica opcional),
siguiendo el estilo de la guía de ReportLab de la cátedra (SimpleDocTemplate, Table, TableStyle) y gráficos
con Matplotlib insertados con BytesIO:
1. Atenciones clínicas y derivaciones por clínica y mes (tabla + gráfico de barras).
2. Muestras rechazadas por fallas en el transporte, agrupadas por transportista y clínica de origen, con motivo.
3. Tratamientos aplicados y vacunas pendientes/vencidas por mascota (con datos del responsable).
4. Facturación desglosada por clínica y por tipo de servicio (Atención / Vacuna / Análisis), con totales (torta).
5. Tiempo promedio de tránsito (primer tramo → recepción) y de procesamiento (recepción → resultado) por tipo
   de análisis, en horas.
Las consultas SQL de los reportes van en un RepositorioReportes. Cada reporte se genera en la carpeta salida/.
Agregá un script reportes/generar_todos.py y ejecutalo con los datos del seed.
```

---

## Paso 10 – Interfaz gráfica con Flet

```text
Implementá la interfaz en ui/ con Flet (API ft.run(main), como en la guía de la cátedra). main.py inicializa
la base y abre una ventana con NavigationRail con secciones: Clientes, Mascotas, Turnos, Atención, Derivaciones,
Envíos, Laboratorio, Comprobantes y Reportes. Cada vista es una clase en su propio archivo que SOLO llama a
servicios (nada de SQL en la UI). Formularios con TextField/Dropdown/DatePicker, tablas con DataTable, mensajes
de error de ReglaNegocioError en un SnackBar. En Derivaciones mostrar la línea de tiempo de estados de cada
muestra (historial). En Reportes, botones para generar cada PDF y abrirlo.
Hacelo por partes: primero el esqueleto de navegación + Clientes; mostrame cómo ejecutarlo (python main.py)
y esperá mi confirmación antes de seguir con las demás vistas.
```

Luego, vista por vista:
```text
Seguí con la vista de <Mascotas | Turnos | Atención | Derivaciones | Envíos | Laboratorio | Comprobantes | Reportes>.
```

---

## Paso 11 – Revisión final antes de entregar

```text
Hacé una revisión completa del proyecto contra el enunciado y CLAUDE.md:
1) los 7 procesos obligatorios funcionan de punta a punta; 2) las 5 validaciones de negocio están implementadas
y testeadas; 3) los patrones State, Singleton y Strategy están aplicados y explicados en docstrings;
4) los 5 reportes se generan; 5) no hay SQL fuera de persistencia/ ni lógica de negocio en ui/.
Corré todos los tests, listá lo que falte o esté mal y corregilo. Finalmente generá un README.md con:
instalación, cómo cargar datos de prueba, cómo ejecutar, estructura del proyecto y patrones usados.
```

---

### Comandos útiles durante el desarrollo
```bash
python -m pytest -q             # correr tests
python db/seed.py               # regenerar base con datos de prueba
python main.py                  # abrir la aplicación (o: flet run main.py)
git add . && git commit -m "Paso N"   # guardá un commit al terminar cada paso
```
