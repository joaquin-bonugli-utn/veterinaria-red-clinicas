"""Tests unitarios de las entidades de dominio (sin base de datos)."""

from datetime import date, timedelta

import pytest

from dominio import (
    AplicacionVacuna,
    Atencion,
    CambioEstadoMuestra,
    Cliente,
    Clinica,
    Comprobante,
    Conservadora,
    DetalleComprobante,
    Especie,
    HistoriaClinica,
    Laboratorio,
    Mascota,
    Muestra,
    OrdenDerivacion,
    PrecintoSanitario,
    Recepcion,
    RemitoBiologico,
    ResultadoAnalisis,
    TipoAnalisis,
    TipoAtencion,
    TramoEnvio,
    Transportista,
    Tratamiento,
    Turno,
    Vacuna,
    Veterinario,
)
from dominio.excepciones import (
    PrecintoRotoError,
    ReglaNegocioError,
    TransicionInvalidaError,
    TurnoSuperpuestoError,
)


def crear_mascota(**cambios) -> Mascota:
    datos = dict(nombre="Firulais", id_especie=1, fecha_nacimiento="2024-01-01", id_cliente=1)
    datos.update(cambios)
    return Mascota(**datos)


def crear_turno(inicio: str, fin: str, **cambios) -> Turno:
    datos = dict(id_veterinario=1, id_mascota=1, fecha_hora_inicio=inicio, fecha_hora_fin=fin)
    datos.update(cambios)
    return Turno(**datos)


def crear_tipo_analisis(**cambios) -> TipoAnalisis:
    datos = dict(nombre="Hemograma", tipo_muestra="Sangre", temp_min=2, temp_max=8,
                 horas_viabilidad=24, precio=5000)
    datos.update(cambios)
    return TipoAnalisis(**datos)


# --- Excepciones -------------------------------------------------------------

@pytest.mark.parametrize("clase", [TransicionInvalidaError, TurnoSuperpuestoError, PrecintoRotoError])
def test_excepciones_heredan_de_regla_negocio(clase) -> None:
    assert issubclass(clase, ReglaNegocioError)
    with pytest.raises(ReglaNegocioError):
        raise clase("x")


# --- Construcción válida de todas las entidades ------------------------------

def test_se_pueden_construir_todas_las_entidades() -> None:
    entidades = [
        Clinica("Centro", "Av. Colón 100"),
        Laboratorio("LabVet", "Bv. San Juan 50"),
        Veterinario("MP-123", "Ana", "Pérez", id_clinica=1),
        Cliente("30111222", "Juan", "Gómez", email="juan@mail.com"),
        Especie("Perro"),
        crear_mascota(),
        HistoriaClinica(id_mascota=1, fecha_apertura="2024-02-01"),
        crear_turno("2026-10-22 10:00", "2026-10-22 10:30"),
        TipoAtencion("Consulta", 8000),
        Atencion(1, 1, 1, 1, "2026-10-22 10:05", "Control anual"),
        Vacuna("Antirrábica", 1, 6000, obligatoria=True, edad_minima_dias=90, refuerzo_dias=365),
        AplicacionVacuna(1, 1, "2026-10-22", "L-001", fecha_proxima_dosis="2027-10-22"),
        Tratamiento(1, "Amoxicilina", "250 mg", "2026-10-22", fecha_fin="2026-10-29"),
        crear_tipo_analisis(),
        OrdenDerivacion(1, 1, "2026-10-22", prioridad="Urgente"),
        Conservadora("CONS-01", 1, capacidad=10, temp_min=2, temp_max=8),
        RemitoBiologico("R-0001", 1, 1, 1, "2026-10-22"),
        PrecintoSanitario("P-0001", 1, "2026-10-22 11:00", temp_cierre=4.5),
        Muestra("M-0001", 1, 1, "2026-10-22 10:20", volumen_ml=3),
        CambioEstadoMuestra(1, "Extraída", "2026-10-22 10:20", "Ana Pérez"),
        Transportista("20333444", "Carlos Ruiz", vehiculo="Moto"),
        TramoEnvio(1, 1, 1, "Clínica Centro", "Laboratorio", "2026-10-22 11:00"),
        Recepcion(1, "2026-10-22 13:00", "Lucía", "Intacto", aceptada=True),
        ResultadoAnalisis(1, "2026-10-23 09:00", "Bioq. Díaz", "Hto 45%"),
        Comprobante("C-0001", 1, 1, "2026-10-22"),
        DetalleComprobante("Atención", "Consulta", 8000, id_atencion=1),
    ]
    assert len(entidades) == 26
    for entidad in entidades:
        texto = str(entidad)
        assert texto and "object at" not in texto


# --- Validaciones genéricas --------------------------------------------------

@pytest.mark.parametrize("nombre", ["", "   ", None])
def test_campo_obligatorio_vacio(nombre) -> None:
    with pytest.raises(ValueError, match="obligatorio"):
        Clinica(nombre, "Av. Colón 100")


def test_textos_se_normalizan() -> None:
    clinica = Clinica("  Centro  ", "Av. Colón 100", telefono="  ")
    assert clinica.nombre == "Centro"
    assert clinica.telefono is None


@pytest.mark.parametrize("precio", [-1, -0.01])
def test_precio_negativo(precio) -> None:
    with pytest.raises(ValueError, match="negativo"):
        TipoAtencion("Consulta", precio)


def test_precio_no_numerico() -> None:
    with pytest.raises(ValueError, match="numérico"):
        TipoAtencion("Consulta", "mil")


@pytest.mark.parametrize("fecha", ["2026-13-01", "2026-02-30", "22/10/2026", "2026-1-5", "20261022"])
def test_fecha_iso_invalida(fecha) -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        HistoriaClinica(id_mascota=1, fecha_apertura=fecha)


@pytest.mark.parametrize("fecha_hora", ["2026-10-22", "2026-10-22 25:00", "2026-10-22T10:00", "2026-10-22 10:00:00"])
def test_fecha_hora_iso_invalida(fecha_hora) -> None:
    with pytest.raises(ValueError, match="HH:MM"):
        Muestra("M-1", 1, 1, fecha_hora)


@pytest.mark.parametrize("id_invalido", [0, -3, "1", 1.5, True])
def test_ids_deben_ser_enteros_positivos(id_invalido) -> None:
    with pytest.raises(ValueError, match="entero positivo"):
        Veterinario("MP-1", "Ana", "Pérez", id_clinica=id_invalido)


def test_opcion_invalida() -> None:
    with pytest.raises(ValueError, match="debe ser uno de"):
        crear_turno("2026-10-22 10:00", "2026-10-22 10:30", estado="Pendiente")


def test_booleano_acepta_0_y_1() -> None:
    assert Veterinario("MP-1", "Ana", "Pérez", 1, activo=0).activo is False
    with pytest.raises(ValueError):
        Veterinario("MP-1", "Ana", "Pérez", 1, activo=2)


# --- Cliente y mascota -------------------------------------------------------

def test_cliente_dni_y_email() -> None:
    with pytest.raises(ValueError, match="DNI"):
        Cliente("30.111.222", "Juan", "Gómez")
    with pytest.raises(ValueError, match="email"):
        Cliente("30111222", "Juan", "Gómez", email="sin-arroba")


def test_mascota_exige_cliente_responsable() -> None:
    with pytest.raises(ValueError, match="cliente responsable"):
        crear_mascota(id_cliente=None)


def test_mascota_no_puede_nacer_en_el_futuro() -> None:
    manana = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="futura"):
        crear_mascota(fecha_nacimiento=manana)


def test_mascota_sexo_y_peso() -> None:
    with pytest.raises(ValueError):
        crear_mascota(sexo="X")
    with pytest.raises(ValueError, match="negativo"):
        crear_mascota(peso_kg=-2)


def test_edad_en_dias() -> None:
    mascota = crear_mascota(fecha_nacimiento="2024-01-01")
    assert mascota.edad_en_dias("2024-01-01") == 0
    assert mascota.edad_en_dias("2024-03-01") == 60  # 2024 es bisiesto
    assert mascota.edad_en_dias(date(2025, 1, 1)) == 366
    assert mascota.edad_en_dias() == (date.today() - date(2024, 1, 1)).days


def test_edad_en_dias_fecha_anterior_al_nacimiento() -> None:
    with pytest.raises(ValueError, match="anterior al nacimiento"):
        crear_mascota(fecha_nacimiento="2024-01-01").edad_en_dias("2023-12-31")


# --- Turnos ------------------------------------------------------------------

def test_turno_fin_posterior_al_inicio() -> None:
    with pytest.raises(ValueError, match="posterior"):
        crear_turno("2026-10-22 10:00", "2026-10-22 10:00")


def test_turnos_superpuestos() -> None:
    base = crear_turno("2026-10-22 10:00", "2026-10-22 10:30")
    assert base.se_superpone_con(crear_turno("2026-10-22 10:15", "2026-10-22 10:45"))
    assert base.se_superpone_con(crear_turno("2026-10-22 09:00", "2026-10-22 11:00"))


def test_turnos_no_superpuestos() -> None:
    base = crear_turno("2026-10-22 10:00", "2026-10-22 10:30")
    # Turnos contiguos no se pisan.
    assert not base.se_superpone_con(crear_turno("2026-10-22 10:30", "2026-10-22 11:00"))
    # Otro veterinario o turno cancelado no cuentan.
    assert not base.se_superpone_con(crear_turno("2026-10-22 10:00", "2026-10-22 10:30", id_veterinario=2))
    assert not base.se_superpone_con(crear_turno("2026-10-22 10:00", "2026-10-22 10:30", estado="Cancelado"))


# --- Vacunas y tratamientos --------------------------------------------------

def test_vacuna_dosis_unica_y_refuerzo_invalido() -> None:
    assert Vacuna("Séxtuple", 1, 5000).es_dosis_unica
    with pytest.raises(ValueError):
        Vacuna("Séxtuple", 1, 5000, refuerzo_dias=0)
    with pytest.raises(ValueError, match="no negativo"):
        Vacuna("Séxtuple", 1, 5000, edad_minima_dias=-1)


def test_aplicacion_proxima_dosis_posterior() -> None:
    with pytest.raises(ValueError, match="posterior"):
        AplicacionVacuna(1, 1, "2026-10-22", "L-1", fecha_proxima_dosis="2026-10-22")


def test_tratamiento_fechas() -> None:
    with pytest.raises(ValueError, match="anterior"):
        Tratamiento(1, "Amoxicilina", "250 mg", "2026-10-22", fecha_fin="2026-10-21")


# --- Laboratorio y muestras --------------------------------------------------

def test_rangos_de_temperatura() -> None:
    with pytest.raises(ValueError, match="máxima"):
        crear_tipo_analisis(temp_min=8, temp_max=2)
    with pytest.raises(ValueError, match="máxima"):
        Conservadora("C-1", 1, 5, temp_min=8, temp_max=2)


def test_conservadora_compatible_con_analisis() -> None:
    tipo = crear_tipo_analisis(temp_min=2, temp_max=8)
    assert Conservadora("C-1", 1, 5, temp_min=3, temp_max=6).es_compatible_con(tipo)
    assert not Conservadora("C-2", 1, 5, temp_min=-20, temp_max=-10).es_compatible_con(tipo)
    with pytest.raises(ValueError):
        Conservadora("C-3", 1, capacidad=0, temp_min=2, temp_max=8)


def test_muestra_estado_por_defecto_e_invalido() -> None:
    assert Muestra("M-1", 1, 1, "2026-10-22 10:00").estado_actual == "Extraída"
    with pytest.raises(ValueError):
        Muestra("M-1", 1, 1, "2026-10-22 10:00", estado_actual="Perdida")


def test_muestra_viabilidad() -> None:
    muestra = Muestra("M-1", 1, 1, "2026-10-22 10:00")
    tipo = crear_tipo_analisis(horas_viabilidad=24)
    assert muestra.es_viable("2026-10-23 10:00", tipo)
    assert not muestra.es_viable("2026-10-23 10:01", tipo)


def test_cambio_estado_muestra_es_inmutable() -> None:
    cambio = CambioEstadoMuestra(1, "Recibida", "2026-10-22 13:00", "Lucía")
    with pytest.raises(AttributeError):
        cambio.estado = "Analizada"
    with pytest.raises(AttributeError):
        cambio.nuevo_atributo = 1


def test_recepcion_con_precinto_roto_no_puede_aceptarse() -> None:
    with pytest.raises(ValueError, match="precinto roto"):
        Recepcion(1, "2026-10-22 13:00", "Lucía", "Roto", aceptada=True)
    assert not Recepcion(1, "2026-10-22 13:00", "Lucía", "Roto", aceptada=False).aceptada


def test_tramo_llegada_no_anterior_a_salida() -> None:
    with pytest.raises(ValueError, match="anterior"):
        TramoEnvio(1, 1, 1, "A", "B", "2026-10-22 11:00", fecha_hora_llegada="2026-10-22 10:00")


# --- Facturación -------------------------------------------------------------

def test_detalle_requiere_atencion_o_muestra() -> None:
    with pytest.raises(ValueError, match="atención o a una muestra"):
        DetalleComprobante("Vacuna", "Antirrábica", 6000)


def test_detalle_calcula_subtotal_y_comprobante_total() -> None:
    comprobante = Comprobante("C-1", 1, 1, "2026-10-22")
    comprobante.agregar_detalle(DetalleComprobante("Atención", "Consulta", 8000, id_atencion=1))
    comprobante.agregar_detalle(DetalleComprobante("Análisis", "Hemograma", 2500.5, cantidad=2, id_muestra=1))
    assert comprobante.detalles[1].subtotal == 5001.0
    assert comprobante.total == 13001.0
