-- =====================================================================
--  TP Integrador DAO 2026 - Tema 2
--  Veterinaria: Red de Clínicas y Derivación de Laboratorio
--  Esquema de base de datos (SQLite)
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
--  1. ESTRUCTURA DE LA RED
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clinica (
    id_clinica      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL UNIQUE,
    direccion       TEXT NOT NULL,
    telefono        TEXT
);

CREATE TABLE IF NOT EXISTS laboratorio (
    id_laboratorio  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL UNIQUE,
    direccion       TEXT NOT NULL,
    telefono        TEXT
);

CREATE TABLE IF NOT EXISTS veterinario (
    id_veterinario  INTEGER PRIMARY KEY AUTOINCREMENT,
    matricula       TEXT NOT NULL UNIQUE,
    nombre          TEXT NOT NULL,
    apellido        TEXT NOT NULL,
    especialidad    TEXT,
    id_clinica      INTEGER NOT NULL REFERENCES clinica(id_clinica),
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

-- ---------------------------------------------------------------------
--  2. CLIENTES, MASCOTAS E HISTORIAS CLÍNICAS
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cliente (
    id_cliente      INTEGER PRIMARY KEY AUTOINCREMENT,
    dni             TEXT NOT NULL UNIQUE,
    nombre          TEXT NOT NULL,
    apellido        TEXT NOT NULL,
    telefono        TEXT,
    email           TEXT,
    direccion       TEXT,
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS especie (
    id_especie      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL UNIQUE
);

-- Validación: toda mascota debe tener un responsable (id_cliente NOT NULL)
CREATE TABLE IF NOT EXISTS mascota (
    id_mascota       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT NOT NULL,
    id_especie       INTEGER NOT NULL REFERENCES especie(id_especie),
    raza             TEXT,
    sexo             TEXT CHECK (sexo IN ('M', 'H')),
    fecha_nacimiento TEXT NOT NULL,              -- ISO 'YYYY-MM-DD'
    peso_kg          REAL,
    id_cliente       INTEGER NOT NULL REFERENCES cliente(id_cliente),
    activo           INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

-- 1 mascota : 1 historia clínica
CREATE TABLE IF NOT EXISTS historia_clinica (
    id_historia     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_mascota      INTEGER NOT NULL UNIQUE REFERENCES mascota(id_mascota),
    fecha_apertura  TEXT NOT NULL,
    alergias        TEXT,
    antecedentes    TEXT
);

-- ---------------------------------------------------------------------
--  3. AGENDA Y ATENCIÓN CLÍNICA
-- ---------------------------------------------------------------------
-- Validación: no superposición de turnos por veterinario (se controla en
-- la capa de negocio: inicio_nuevo < fin_existente AND fin_nuevo > inicio_existente)
CREATE TABLE IF NOT EXISTS turno (
    id_turno          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_veterinario    INTEGER NOT NULL REFERENCES veterinario(id_veterinario),
    id_mascota        INTEGER NOT NULL REFERENCES mascota(id_mascota),
    fecha_hora_inicio TEXT NOT NULL,             -- ISO 'YYYY-MM-DD HH:MM'
    fecha_hora_fin    TEXT NOT NULL,
    estado            TEXT NOT NULL DEFAULT 'Reservado'
                      CHECK (estado IN ('Reservado', 'Atendido', 'Cancelado', 'Ausente')),
    CHECK (fecha_hora_fin > fecha_hora_inicio)
);

CREATE TABLE IF NOT EXISTS tipo_atencion (
    id_tipo_atencion INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT NOT NULL UNIQUE,       -- Consulta, Control, Urgencia
    precio           REAL NOT NULL CHECK (precio >= 0)
);

CREATE TABLE IF NOT EXISTS atencion (
    id_atencion      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_historia      INTEGER NOT NULL REFERENCES historia_clinica(id_historia),
    id_veterinario   INTEGER NOT NULL REFERENCES veterinario(id_veterinario),
    id_clinica       INTEGER NOT NULL REFERENCES clinica(id_clinica),
    id_tipo_atencion INTEGER NOT NULL REFERENCES tipo_atencion(id_tipo_atencion),
    id_turno         INTEGER UNIQUE REFERENCES turno(id_turno),   -- NULL en urgencias sin turno
    fecha_hora       TEXT NOT NULL,
    motivo           TEXT NOT NULL,
    diagnostico      TEXT,
    peso_kg          REAL
);

-- Esquema de vacunación por especie
CREATE TABLE IF NOT EXISTS vacuna (
    id_vacuna        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT NOT NULL,
    id_especie       INTEGER NOT NULL REFERENCES especie(id_especie),
    obligatoria      INTEGER NOT NULL DEFAULT 0 CHECK (obligatoria IN (0, 1)),
    edad_minima_dias INTEGER NOT NULL DEFAULT 0,
    refuerzo_dias    INTEGER,                    -- NULL = dosis única
    precio           REAL NOT NULL CHECK (precio >= 0),
    UNIQUE (nombre, id_especie)
);

CREATE TABLE IF NOT EXISTS aplicacion_vacuna (
    id_aplicacion       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_atencion         INTEGER NOT NULL REFERENCES atencion(id_atencion),
    id_vacuna           INTEGER NOT NULL REFERENCES vacuna(id_vacuna),
    fecha_aplicacion    TEXT NOT NULL,
    lote                TEXT NOT NULL,
    fecha_proxima_dosis TEXT
);

CREATE TABLE IF NOT EXISTS tratamiento (
    id_tratamiento  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_atencion     INTEGER NOT NULL REFERENCES atencion(id_atencion),
    medicamento     TEXT NOT NULL,
    dosis           TEXT NOT NULL,
    frecuencia      TEXT,
    fecha_inicio    TEXT NOT NULL,
    fecha_fin       TEXT
);

-- ---------------------------------------------------------------------
--  4. DERIVACIÓN A LABORATORIO Y MUESTRAS
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tipo_analisis (
    id_tipo_analisis INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT NOT NULL UNIQUE,       -- Hemograma, Bioquímica, Urianálisis...
    tipo_muestra     TEXT NOT NULL,              -- Sangre, Orina, Tejido...
    temp_min         REAL NOT NULL,              -- °C de conservación
    temp_max         REAL NOT NULL,
    horas_viabilidad INTEGER NOT NULL,           -- horas máximas desde la extracción
    precio           REAL NOT NULL CHECK (precio >= 0),
    CHECK (temp_max >= temp_min)
);

CREATE TABLE IF NOT EXISTS orden_derivacion (
    id_orden        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_atencion     INTEGER NOT NULL REFERENCES atencion(id_atencion),
    id_laboratorio  INTEGER NOT NULL REFERENCES laboratorio(id_laboratorio),
    fecha_emision   TEXT NOT NULL,
    prioridad       TEXT NOT NULL DEFAULT 'Normal' CHECK (prioridad IN ('Normal', 'Urgente')),
    indicaciones    TEXT,
    estado          TEXT NOT NULL DEFAULT 'Emitida'
                    CHECK (estado IN ('Emitida', 'En proceso', 'Finalizada', 'Anulada'))
);

-- Conservadora isotérmica (contenedor reutilizable)
CREATE TABLE IF NOT EXISTS conservadora (
    id_conservadora INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT NOT NULL UNIQUE,
    id_clinica      INTEGER NOT NULL REFERENCES clinica(id_clinica),
    capacidad       INTEGER NOT NULL CHECK (capacidad > 0),   -- cantidad de muestras
    temp_min        REAL NOT NULL,
    temp_max        REAL NOT NULL,
    estado          TEXT NOT NULL DEFAULT 'Disponible'
                    CHECK (estado IN ('Disponible', 'En uso', 'Fuera de servicio'))
);

-- Remito biológico: documenta el envío de una conservadora con sus muestras
CREATE TABLE IF NOT EXISTS remito_biologico (
    id_remito        INTEGER PRIMARY KEY AUTOINCREMENT,
    numero           TEXT NOT NULL UNIQUE,
    id_clinica       INTEGER NOT NULL REFERENCES clinica(id_clinica),          -- origen
    id_laboratorio   INTEGER NOT NULL REFERENCES laboratorio(id_laboratorio),  -- destino
    id_conservadora  INTEGER NOT NULL REFERENCES conservadora(id_conservadora),
    fecha_emision    TEXT NOT NULL,
    estado           TEXT NOT NULL DEFAULT 'Emitido'
                     CHECK (estado IN ('Emitido', 'En tránsito', 'Recibido', 'Rechazado'))
);

-- Precinto sanitario: 1 por remito (sella la conservadora)
CREATE TABLE IF NOT EXISTS precinto_sanitario (
    id_precinto      INTEGER PRIMARY KEY AUTOINCREMENT,
    numero           TEXT NOT NULL UNIQUE,
    id_remito        INTEGER NOT NULL UNIQUE REFERENCES remito_biologico(id_remito),
    fecha_colocacion TEXT NOT NULL,
    temp_cierre      REAL,
    estado           TEXT NOT NULL DEFAULT 'Colocado'
                     CHECK (estado IN ('Colocado', 'Intacto', 'Roto'))
);

-- Muestra biológica: núcleo de la trazabilidad (patrón State)
CREATE TABLE IF NOT EXISTS muestra (
    id_muestra            INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo                TEXT NOT NULL UNIQUE,
    id_orden              INTEGER NOT NULL REFERENCES orden_derivacion(id_orden),
    id_tipo_analisis      INTEGER NOT NULL REFERENCES tipo_analisis(id_tipo_analisis),
    id_remito             INTEGER REFERENCES remito_biologico(id_remito),  -- NULL hasta empaquetar
    fecha_hora_extraccion TEXT NOT NULL,
    volumen_ml            REAL,
    estado_actual         TEXT NOT NULL DEFAULT 'Extraída'
                          CHECK (estado_actual IN ('Extraída', 'Empaquetada', 'En tránsito',
                                                   'Recibida', 'Analizada', 'Rechazada'))
);

-- Historial INMUTABLE de estados de la muestra (solo INSERT)
CREATE TABLE IF NOT EXISTS historial_estado_muestra (
    id_historial    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_muestra      INTEGER NOT NULL REFERENCES muestra(id_muestra),
    estado          TEXT NOT NULL
                    CHECK (estado IN ('Extraída', 'Empaquetada', 'En tránsito',
                                      'Recibida', 'Analizada', 'Rechazada')),
    fecha_hora      TEXT NOT NULL,
    responsable     TEXT NOT NULL,
    observacion     TEXT
);

CREATE TRIGGER IF NOT EXISTS trg_historial_no_update
BEFORE UPDATE ON historial_estado_muestra
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados de la muestra es inmutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_historial_no_delete
BEFORE DELETE ON historial_estado_muestra
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados de la muestra es inmutable');
END;

-- ---------------------------------------------------------------------
--  5. CADENA DE ENVÍO Y RECEPCIÓN
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transportista (
    id_transportista INTEGER PRIMARY KEY AUTOINCREMENT,
    documento        TEXT NOT NULL UNIQUE,
    nombre           TEXT NOT NULL,
    telefono         TEXT,
    vehiculo         TEXT
);

-- Cada tramo de la cadena de custodia (clínica -> centro logístico -> laboratorio)
CREATE TABLE IF NOT EXISTS tramo_envio (
    id_tramo           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_remito          INTEGER NOT NULL REFERENCES remito_biologico(id_remito),
    id_transportista   INTEGER NOT NULL REFERENCES transportista(id_transportista),
    nro_tramo          INTEGER NOT NULL,
    origen             TEXT NOT NULL,
    destino            TEXT NOT NULL,
    fecha_hora_salida  TEXT NOT NULL,
    fecha_hora_llegada TEXT,
    temperatura        REAL,                    -- registrada al entregar el tramo
    UNIQUE (id_remito, nro_tramo)
);

-- Recepción en laboratorio: 1 por remito, verifica el precinto
CREATE TABLE IF NOT EXISTS recepcion (
    id_recepcion        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_remito           INTEGER NOT NULL UNIQUE REFERENCES remito_biologico(id_remito),
    fecha_hora          TEXT NOT NULL,
    receptor            TEXT NOT NULL,
    estado_precinto     TEXT NOT NULL CHECK (estado_precinto IN ('Intacto', 'Roto')),
    temperatura_llegada REAL,
    aceptada            INTEGER NOT NULL CHECK (aceptada IN (0, 1)),
    observaciones       TEXT
);

CREATE TABLE IF NOT EXISTS resultado_analisis (
    id_resultado    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_muestra      INTEGER NOT NULL UNIQUE REFERENCES muestra(id_muestra),
    fecha_hora      TEXT NOT NULL,
    bioquimico      TEXT NOT NULL,
    valores         TEXT NOT NULL,
    conclusion      TEXT
);

-- ---------------------------------------------------------------------
--  6. FACTURACIÓN
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comprobante (
    id_comprobante  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero          TEXT NOT NULL UNIQUE,
    id_cliente      INTEGER NOT NULL REFERENCES cliente(id_cliente),
    id_clinica      INTEGER NOT NULL REFERENCES clinica(id_clinica),
    fecha_emision   TEXT NOT NULL,
    total           REAL NOT NULL DEFAULT 0 CHECK (total >= 0)
);

CREATE TABLE IF NOT EXISTS detalle_comprobante (
    id_detalle      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_comprobante  INTEGER NOT NULL REFERENCES comprobante(id_comprobante),
    tipo_item       TEXT NOT NULL CHECK (tipo_item IN ('Atención', 'Vacuna', 'Análisis')),
    id_atencion     INTEGER REFERENCES atencion(id_atencion),
    id_muestra      INTEGER REFERENCES muestra(id_muestra),
    descripcion     TEXT NOT NULL,
    cantidad        INTEGER NOT NULL DEFAULT 1 CHECK (cantidad > 0),
    precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
    subtotal        REAL NOT NULL CHECK (subtotal >= 0),
    CHECK (id_atencion IS NOT NULL OR id_muestra IS NOT NULL)
);

-- Índices útiles para reportes y validaciones
CREATE INDEX IF NOT EXISTS idx_turno_vet_inicio  ON turno(id_veterinario, fecha_hora_inicio);
CREATE INDEX IF NOT EXISTS idx_atencion_fecha    ON atencion(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_muestra_estado    ON muestra(estado_actual);
CREATE INDEX IF NOT EXISTS idx_historial_muestra ON historial_estado_muestra(id_muestra, fecha_hora);
