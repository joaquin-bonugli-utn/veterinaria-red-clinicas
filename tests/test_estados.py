"""Tests del patrón State de muestras y remitos."""

import pytest

from dominio import CambioEstadoMuestra, Muestra, RemitoBiologico
from dominio import estados_muestra as em
from dominio import estados_remito as er
from dominio.excepciones import TransicionInvalidaError

RESP = "Ana Pérez"


def nueva_muestra() -> Muestra:
    return Muestra.nueva("M-0001", 1, 1, "2026-10-22 10:00", RESP, volumen_ml=3)


def muestra_en(estado: str) -> Muestra:
    """Lleva una muestra nueva hasta `estado` por el camino válido."""
    muestra = nueva_muestra()
    pasos = [
        lambda m: m.empaquetar(1, RESP, "2026-10-22 10:30"),
        lambda m: m.despachar("Carlos", "2026-10-22 11:00"),
        lambda m: m.recibir(True, "Lucía", "2026-10-22 13:00"),
        lambda m: m.registrar_resultado("Bioq. Díaz", "2026-10-23 09:00"),
    ]
    for paso in pasos:
        if muestra.estado_actual == estado:
            break
        paso(muestra)
    assert muestra.estado_actual == estado
    return muestra


def nuevo_remito(estado: str = "Emitido") -> RemitoBiologico:
    return RemitoBiologico("R-0001", 1, 1, 1, "2026-10-22", estado=estado)


# =============================================================================
#  Muestra: transiciones válidas
# =============================================================================

def test_muestra_nueva_queda_extraida_con_primer_registro() -> None:
    muestra = nueva_muestra()
    assert isinstance(muestra.estado, em.Extraida)
    assert [c.estado for c in muestra.historial] == ["Extraída"]
    assert muestra.historial[0].responsable == RESP


def test_extraida_a_empaquetada_asigna_remito() -> None:
    muestra = nueva_muestra()
    muestra.empaquetar(7, RESP, "2026-10-22 10:30")
    assert isinstance(muestra.estado, em.Empaquetada)
    assert muestra.id_remito == 7


def test_empaquetada_a_en_transito() -> None:
    muestra = muestra_en("Empaquetada")
    muestra.despachar("Carlos", "2026-10-22 11:00")
    assert isinstance(muestra.estado, em.EnTransito)


def test_en_transito_a_recibida_con_precinto_intacto() -> None:
    muestra = muestra_en("En tránsito")
    muestra.recibir(True, "Lucía", "2026-10-22 13:00")
    assert isinstance(muestra.estado, em.Recibida)


def test_en_transito_a_rechazada_con_precinto_roto() -> None:
    muestra = muestra_en("En tránsito")
    muestra.recibir(False, "Lucía", "2026-10-22 13:00")
    assert isinstance(muestra.estado, em.Rechazada)
    assert "Precinto roto" in muestra.ultimo_cambio.observacion


def test_recibida_a_analizada() -> None:
    muestra = muestra_en("Recibida")
    muestra.registrar_resultado("Bioq. Díaz", "2026-10-23 09:00")
    assert isinstance(muestra.estado, em.Analizada)


@pytest.mark.parametrize("motivo", ["Viabilidad vencida", "Temperatura fuera de rango"])
def test_recibida_a_rechazada_con_motivo(motivo: str) -> None:
    muestra = muestra_en("Recibida")
    muestra.rechazar(motivo, "Lucía", "2026-10-22 13:05")
    assert isinstance(muestra.estado, em.Rechazada)
    assert muestra.ultimo_cambio.observacion == motivo


def test_flujo_completo_registra_historial_en_orden() -> None:
    muestra = muestra_en("Analizada")
    assert [c.estado for c in muestra.historial] == [
        "Extraída", "Empaquetada", "En tránsito", "Recibida", "Analizada"
    ]
    assert [c.fecha_hora for c in muestra.historial] == sorted(c.fecha_hora for c in muestra.historial)


def test_fecha_hora_por_defecto_es_ahora() -> None:
    muestra = Muestra("M-1", 1, 1, "2026-10-22 10:00")
    muestra.empaquetar(1, RESP)
    assert len(muestra.ultimo_cambio.fecha_hora) == len("YYYY-MM-DD HH:MM")


# =============================================================================
#  Muestra: transiciones inválidas
# =============================================================================

TODAS_LAS_OPERACIONES = {
    "empaquetar": lambda m: m.empaquetar(1, RESP, "2026-10-24 10:00"),
    "despachar": lambda m: m.despachar(RESP, "2026-10-24 10:00"),
    "recibir": lambda m: m.recibir(True, RESP, "2026-10-24 10:00"),
    "rechazar": lambda m: m.rechazar("motivo", RESP, "2026-10-24 10:00"),
    "registrar_resultado": lambda m: m.registrar_resultado(RESP, "2026-10-24 10:00"),
}

PERMITIDAS = {
    "Extraída": {"empaquetar"},
    "Empaquetada": {"despachar"},
    "En tránsito": {"recibir"},
    "Recibida": {"rechazar", "registrar_resultado"},
    "Analizada": set(),
}

CASOS_INVALIDOS = [
    (estado, operacion)
    for estado, permitidas in PERMITIDAS.items()
    for operacion in TODAS_LAS_OPERACIONES
    if operacion not in permitidas
]


@pytest.mark.parametrize(("estado", "operacion"), CASOS_INVALIDOS)
def test_transiciones_invalidas_lanzan_error(estado: str, operacion: str) -> None:
    muestra = muestra_en(estado)
    largo_historial = len(muestra.historial)
    with pytest.raises(TransicionInvalidaError, match=estado):
        TODAS_LAS_OPERACIONES[operacion](muestra)
    # No cambió el estado ni se agregó nada al historial.
    assert muestra.estado_actual == estado
    assert len(muestra.historial) == largo_historial


@pytest.mark.parametrize("operacion", list(TODAS_LAS_OPERACIONES))
def test_rechazada_es_estado_final(operacion: str) -> None:
    muestra = muestra_en("Recibida")
    muestra.rechazar("Temperatura fuera de rango", "Lucía", "2026-10-22 13:05")
    with pytest.raises(TransicionInvalidaError):
        TODAS_LAS_OPERACIONES[operacion](muestra)
    assert muestra.estado_actual == "Rechazada"


def test_rechazada_no_admite_resultados() -> None:
    muestra = muestra_en("En tránsito")
    muestra.recibir(False, "Lucía", "2026-10-22 13:00")
    with pytest.raises(TransicionInvalidaError, match="rechazada"):
        muestra.registrar_resultado("Bioq. Díaz", "2026-10-23 09:00")


def test_empaquetar_invalido_no_asigna_remito() -> None:
    muestra = muestra_en("Empaquetada")
    with pytest.raises(TransicionInvalidaError):
        muestra.empaquetar(99, RESP, "2026-10-22 12:00")
    assert muestra.id_remito == 1


def test_rechazar_exige_motivo() -> None:
    muestra = muestra_en("Recibida")
    with pytest.raises(ValueError, match="motivo"):
        muestra.rechazar("  ", "Lucía", "2026-10-22 13:05")
    assert muestra.estado_actual == "Recibida"


def test_transicion_sin_responsable_no_cambia_estado() -> None:
    muestra = nueva_muestra()
    with pytest.raises(ValueError, match="responsable"):
        muestra.empaquetar(1, "", "2026-10-22 10:30")
    assert muestra.estado_actual == "Extraída"


def test_cambio_no_puede_ser_anterior_al_ultimo() -> None:
    muestra = nueva_muestra()
    with pytest.raises(ValueError, match="anterior"):
        muestra.empaquetar(1, RESP, "2026-10-22 09:00")
    assert muestra.estado_actual == "Extraída"


# =============================================================================
#  Historial: solo se puede agregar
# =============================================================================

def test_historial_es_de_solo_lectura() -> None:
    muestra = nueva_muestra()
    assert isinstance(muestra.historial, tuple)
    with pytest.raises(AttributeError):
        muestra.historial = []  # type: ignore[misc]
    with pytest.raises(AttributeError):
        muestra.historial.append("x")  # type: ignore[attr-defined]


def test_historial_solo_admite_cambios() -> None:
    with pytest.raises(TypeError):
        nueva_muestra().agregar_al_historial("Empaquetada")  # type: ignore[arg-type]


def test_reconstruir_muestra_desde_la_base() -> None:
    muestra = Muestra("M-1", 1, 1, "2026-10-22 10:00", id_remito=1, estado_actual="En tránsito", id_muestra=5)
    for estado, fecha in [("Extraída", "2026-10-22 10:00"), ("Empaquetada", "2026-10-22 10:30"),
                          ("En tránsito", "2026-10-22 11:00")]:
        muestra.agregar_al_historial(CambioEstadoMuestra(5, estado, fecha, RESP, id_historial=1))
    assert isinstance(muestra.estado, em.EnTransito)
    muestra.recibir(True, "Lucía", "2026-10-22 13:00")
    assert muestra.ultimo_cambio.id_muestra == 5
    assert len(muestra.historial) == 4


# =============================================================================
#  estado_desde_nombre (muestra)
# =============================================================================

@pytest.mark.parametrize(
    ("nombre", "clase"),
    [("Extraída", em.Extraida), ("Empaquetada", em.Empaquetada), ("En tránsito", em.EnTransito),
     ("Recibida", em.Recibida), ("Analizada", em.Analizada), ("Rechazada", em.Rechazada)],
)
def test_estado_muestra_desde_nombre(nombre: str, clase: type) -> None:
    estado = em.estado_desde_nombre(nombre)
    assert isinstance(estado, clase)
    assert estado.nombre == nombre == str(estado)


@pytest.mark.parametrize("nombre", ["Extraida", "perdida", "", None])
def test_estado_muestra_desde_nombre_invalido(nombre) -> None:
    with pytest.raises(ValueError, match="desconocido"):
        em.estado_desde_nombre(nombre)


def test_estado_muestra_es_abstracto() -> None:
    with pytest.raises(TypeError):
        em.EstadoMuestra()  # type: ignore[abstract]


# =============================================================================
#  Remito
# =============================================================================

def test_remito_emitido_a_en_transito() -> None:
    remito = nuevo_remito()
    assert isinstance(remito.estado_obj, er.Emitido)
    remito.despachar()
    assert isinstance(remito.estado_obj, er.EnTransitoRemito)
    assert remito.estado == "En tránsito"


def test_remito_en_transito_a_recibido() -> None:
    remito = nuevo_remito("En tránsito")
    remito.recibir(precinto_intacto=True)
    assert isinstance(remito.estado_obj, er.Recibido)


def test_remito_en_transito_a_rechazado_con_precinto_roto() -> None:
    remito = nuevo_remito("En tránsito")
    remito.recibir(precinto_intacto=False)
    assert isinstance(remito.estado_obj, er.Rechazado)


@pytest.mark.parametrize(
    ("estado", "operacion"),
    [
        ("Emitido", lambda r: r.recibir(True)),
        ("En tránsito", lambda r: r.despachar()),
        ("Recibido", lambda r: r.despachar()),
        ("Recibido", lambda r: r.recibir(True)),
        ("Rechazado", lambda r: r.despachar()),
        ("Rechazado", lambda r: r.recibir(True)),
    ],
)
def test_remito_transiciones_invalidas(estado: str, operacion) -> None:
    remito = nuevo_remito(estado)
    with pytest.raises(TransicionInvalidaError, match=estado):
        operacion(remito)
    assert remito.estado == estado


@pytest.mark.parametrize("nombre", ["Emitido", "En tránsito", "Recibido", "Rechazado"])
def test_estado_remito_desde_nombre(nombre: str) -> None:
    assert er.estado_desde_nombre(nombre).nombre == nombre


def test_estado_remito_desde_nombre_invalido() -> None:
    with pytest.raises(ValueError, match="desconocido"):
        er.estado_desde_nombre("Perdido")
    with pytest.raises(ValueError):
        nuevo_remito("Perdido")
