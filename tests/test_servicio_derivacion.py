"""Tests de ServicioDerivacion, ServicioEnvios y ServicioLaboratorio (trazabilidad de muestras)."""

import pytest

from dominio import Conservadora
from dominio.excepciones import (
    EntidadNoEncontradaError,
    PrecintoRotoError,
    ReglaNegocioError,
    TransicionInvalidaError,
)
from persistencia.repositorios import RepositorioEnvios
from servicios import ServicioCatalogos, ServicioDerivacion, ServicioEnvios, ServicioLaboratorio
from tests.conftest import EXTRACCION

# Línea de tiempo del caso feliz (2026-10-22); la atención del fixture `lab` es a las 10:00.
EMPAQUE = "2026-10-22 10:30"
SALIDA_1, LLEGADA_1 = "2026-10-22 11:00", "2026-10-22 11:40"
SALIDA_2, LLEGADA_2 = "2026-10-22 12:00", "2026-10-22 13:00"
RECEPCION = "2026-10-22 13:30"


@pytest.fixture
def derivacion(lab) -> ServicioDerivacion:
    return ServicioDerivacion()


@pytest.fixture
def envios(lab) -> ServicioEnvios:
    return ServicioEnvios()


@pytest.fixture
def laboratorio(lab) -> ServicioLaboratorio:
    return ServicioLaboratorio()


def emitir(derivacion, lab, *tipos, id_laboratorio=None):
    tipos = tipos or (lab.hemograma, lab.bioquimica)
    return derivacion.emitir_orden(lab.atencion.id_atencion, id_laboratorio or lab.laboratorio.id_laboratorio,
                                   [(t.id_tipo_analisis, 3.0) for t in tipos])


def empaquetar(envios, lab, muestras, precinto="P-0001", temp=4, conservadora=None):
    return envios.empaquetar([m.id_muestra for m in muestras], (conservadora or lab.cons_a).id_conservadora,
                             precinto, temp, fecha_hora=EMPAQUE)


def despachar(envios, lab, remito):
    """Dos tramos: clínica → centro logístico → laboratorio."""
    envios.registrar_tramo(remito.id_remito, lab.transportista.id_transportista, "Clínica Centro",
                           "Centro logístico", SALIDA_1, LLEGADA_1, 5.0)
    envios.registrar_tramo(remito.id_remito, lab.transportista.id_transportista, "Centro logístico",
                           "LabVet Central", SALIDA_2, LLEGADA_2, 5.5)


def preparar_en_transito(derivacion, envios, lab, *tipos):
    emitida = emitir(derivacion, lab, *tipos)
    remito = empaquetar(envios, lab, emitida.muestras)
    despachar(envios, lab, remito)
    return emitida, remito


def estados(derivacion, emitida) -> list[str]:
    return [m.estado_actual for m in derivacion.muestras_de_orden(emitida.orden.id_orden)]


def conservadora(lab, cons) -> Conservadora:
    return RepositorioEnvios().obtener_por_id(cons.id_conservadora, Conservadora)


def contar(conexion, tabla: str) -> int:
    return conexion.cursor().execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


# =============================================================================
#  Flujos completos
# =============================================================================

def test_flujo_feliz_completo(derivacion, envios, laboratorio, lab) -> None:
    # 1. Orden con dos muestras Extraída
    emitida = emitir(derivacion, lab)
    assert emitida.orden.estado == "Emitida"
    assert [m.estado_actual for m in emitida.muestras] == ["Extraída", "Extraída"]

    # 2. Empaquetado
    remito = empaquetar(envios, lab, emitida.muestras)
    assert remito.numero == "REM-2026-00001" and remito.estado == "Emitido"
    assert envios.obtener_precinto(remito.id_remito).estado == "Colocado"
    assert conservadora(lab, lab.cons_a).estado == "En uso"
    assert derivacion.obtener_orden(emitida.orden.id_orden).estado == "En proceso"
    assert estados(derivacion, emitida) == ["Empaquetada", "Empaquetada"]

    # 3. Tramos
    despachar(envios, lab, remito)
    assert envios.obtener_remito(remito.id_remito).estado == "En tránsito"
    assert [t.nro_tramo for t in envios.tramos_de(remito.id_remito)] == [1, 2]
    assert estados(derivacion, emitida) == ["En tránsito", "En tránsito"]

    # 4. Recepción con precinto intacto
    recibido = laboratorio.recibir(remito.id_remito, "Lucía Ramos", True, 5.0, fecha_hora=RECEPCION)
    assert recibido.recepcion.aceptada and recibido.rechazadas == []
    assert len(recibido.aceptadas) == 2
    assert envios.obtener_remito(remito.id_remito).estado == "Recibido"
    assert envios.obtener_precinto(remito.id_remito).estado == "Intacto"
    assert conservadora(lab, lab.cons_a).estado == "Disponible"
    assert estados(derivacion, emitida) == ["Recibida", "Recibida"]

    # 5. Resultados: la orden se finaliza recién con el último
    m1, m2 = emitida.muestras
    laboratorio.registrar_resultado(m1.id_muestra, "Bioq. Díaz", "Hto 45 %", "Normal", fecha_hora="2026-10-23 09:00")
    assert derivacion.obtener_orden(emitida.orden.id_orden).estado == "En proceso"
    laboratorio.registrar_resultado(m2.id_muestra, "Bioq. Díaz", "Urea 30 mg/dl", fecha_hora="2026-10-23 09:30")
    assert derivacion.obtener_orden(emitida.orden.id_orden).estado == "Finalizada"
    assert len(laboratorio.resultados_de_orden(emitida.orden.id_orden)) == 2

    # Historial completo e inmutable de cada muestra
    for muestra in emitida.muestras:
        historial = derivacion.historial_de_muestra(muestra.id_muestra)
        assert [c.estado for c in historial] == ["Extraída", "Empaquetada", "En tránsito", "Recibida", "Analizada"]
        assert [c.fecha_hora for c in historial] == [EXTRACCION, EMPAQUE, SALIDA_1, RECEPCION, historial[-1].fecha_hora]
        assert historial[2].responsable == "Carlos Ruiz"
        assert historial[3].responsable == "Lucía Ramos"


def test_flujo_precinto_roto(derivacion, envios, laboratorio, lab, conexion) -> None:
    emitida, remito = preparar_en_transito(derivacion, envios, lab)

    recibido = laboratorio.recibir(remito.id_remito, "Lucía Ramos", False, 5.0, fecha_hora=RECEPCION)

    assert recibido.recepcion.aceptada is False and recibido.recepcion.estado_precinto == "Roto"
    assert recibido.aceptadas == [] and len(recibido.rechazadas) == 2
    assert envios.obtener_remito(remito.id_remito).estado == "Rechazado"
    assert envios.obtener_precinto(remito.id_remito).estado == "Roto"
    assert conservadora(lab, lab.cons_a).estado == "Disponible"
    assert estados(derivacion, emitida) == ["Rechazada", "Rechazada"]
    for muestra in emitida.muestras:
        ultimo = derivacion.historial_de_muestra(muestra.id_muestra)[-1]
        assert ultimo.estado == "Rechazada" and "Precinto roto" in ultimo.observacion
    # Todas las muestras terminaron (rechazadas): la orden se cierra.
    assert derivacion.obtener_orden(emitida.orden.id_orden).estado == "Finalizada"

    # No se pueden cargar resultados (regla 2).
    with pytest.raises(PrecintoRotoError, match="precinto roto"):
        laboratorio.registrar_resultado(emitida.muestras[0].id_muestra, "Bioq. Díaz", "x")
    assert contar(conexion, "resultado_analisis") == 0


def test_precinto_intacto_rechaza_muestra_con_viabilidad_vencida(derivacion, envios, laboratorio, lab) -> None:
    emitida, remito = preparar_en_transito(derivacion, envios, lab, lab.hemograma, lab.urianalisis)
    # 5 h después de la extracción: Urianálisis (4 h) vencida; Hemograma (24 h) OK.
    recibido = laboratorio.recibir(remito.id_remito, "Lucía", True, 5.0, fecha_hora="2026-10-22 15:00")

    assert recibido.recepcion.aceptada is True
    assert envios.obtener_remito(remito.id_remito).estado == "Recibido"
    assert [m.codigo for m in recibido.aceptadas] == [emitida.muestras[0].codigo]
    (rechazada,) = recibido.rechazadas
    assert rechazada.codigo == emitida.muestras[1].codigo
    assert "Viabilidad vencida: 5.0 h" in rechazada.ultimo_cambio.observacion
    assert [c.estado for c in rechazada.historial][-2:] == ["Recibida", "Rechazada"]

    # La rechazada no admite resultado; la otra sí y con eso se cierra la orden.
    with pytest.raises(TransicionInvalidaError):
        laboratorio.registrar_resultado(rechazada.id_muestra, "Bioq. Díaz", "x")
    laboratorio.registrar_resultado(emitida.muestras[0].id_muestra, "Bioq. Díaz", "Hto 45 %",
                                    fecha_hora="2026-10-22 16:00")
    assert derivacion.obtener_orden(emitida.orden.id_orden).estado == "Finalizada"


def test_precinto_intacto_rechaza_por_temperatura_de_llegada(derivacion, envios, laboratorio, lab) -> None:
    emitida, remito = preparar_en_transito(derivacion, envios, lab)
    recibido = laboratorio.recibir(remito.id_remito, "Lucía", True, 12.0, fecha_hora=RECEPCION)
    assert recibido.aceptadas == [] and len(recibido.rechazadas) == 2
    assert "Temperatura de llegada 12 °C fuera de rango" in recibido.rechazadas[0].ultimo_cambio.observacion
    assert envios.obtener_remito(remito.id_remito).estado == "Recibido"  # el remito sí se recibió


# =============================================================================
#  1. emitir_orden
# =============================================================================

def test_emitir_orden_crea_muestras_con_historial(derivacion, lab) -> None:
    emitida = emitir(derivacion, lab)
    assert [m.codigo for m in emitida.muestras] == [f"M-{emitida.orden.id_orden:05d}-1",
                                                    f"M-{emitida.orden.id_orden:05d}-2"]
    for muestra in emitida.muestras:
        (registro,) = derivacion.historial_de_muestra(muestra.id_muestra)
        assert (registro.estado, registro.fecha_hora, registro.responsable) == ("Extraída", EXTRACCION, "Pérez, Ana")
    assert emitida.orden.fecha_emision == "2026-10-22"


@pytest.mark.parametrize(
    ("cambios", "error", "mensaje"),
    [
        ({"id_atencion": 999}, EntidadNoEncontradaError, "atención"),
        ({"id_laboratorio": 999}, EntidadNoEncontradaError, "laboratorio"),
        ({"muestras": [(999, 1.0)]}, EntidadNoEncontradaError, "tipo de análisis"),
        ({"muestras": []}, ReglaNegocioError, "al menos una muestra"),
        ({"fecha_hora_extraccion": "2026-10-22 09:00"}, ReglaNegocioError, "anterior a la atención"),
        ({"prioridad": "Altísima"}, ValueError, "prioridad"),
    ],
)
def test_emitir_orden_errores_no_dejan_nada(derivacion, lab, conexion, cambios, error, mensaje) -> None:
    datos = {"id_atencion": lab.atencion.id_atencion, "id_laboratorio": lab.laboratorio.id_laboratorio,
             "muestras": [(lab.hemograma.id_tipo_analisis, 3.0)]}
    extra = {k: cambios.pop(k) for k in list(cambios) if k in ("fecha_hora_extraccion", "prioridad")}
    datos.update(cambios)
    with pytest.raises(error, match=mensaje):
        derivacion.emitir_orden(datos["id_atencion"], datos["id_laboratorio"], datos["muestras"], **extra)
    assert contar(conexion, "orden_derivacion") == contar(conexion, "muestra") == 0
    assert contar(conexion, "historial_estado_muestra") == 0


# =============================================================================
#  2. empaquetar
# =============================================================================

def test_numero_de_remito_correlativo(derivacion, envios, lab) -> None:
    r1 = empaquetar(envios, lab, emitir(derivacion, lab, lab.hemograma).muestras, "P-1", conservadora=lab.cons_a)
    r2 = empaquetar(envios, lab, emitir(derivacion, lab, lab.hemograma).muestras, "P-2", conservadora=lab.cons_b)
    assert (r1.numero, r2.numero) == ("REM-2026-00001", "REM-2026-00002")


def _sin_cambios_tras_empaquetar_fallido(derivacion, envios, lab, conexion, emitida) -> None:
    assert contar(conexion, "remito_biologico") == contar(conexion, "precinto_sanitario") == 0
    for cons in (lab.cons_a, lab.cons_b, lab.cons_norte):
        assert conservadora(lab, cons).estado == "Disponible"
    assert conservadora(lab, lab.cons_fuera).estado == "Fuera de servicio"
    assert set(estados(derivacion, emitida)) == {"Extraída"}
    assert derivacion.obtener_orden(emitida.orden.id_orden).estado == "Emitida"
    for muestra in emitida.muestras:
        assert len(derivacion.historial_de_muestra(muestra.id_muestra)) == 1


@pytest.mark.parametrize(
    ("cons", "temp", "mensaje"),
    [
        ("cons_fuera", 4, "no está disponible"),
        ("cons_b", 4, "admite 1 muestras"),                     # capacidad 1, se piden 2
        ("cons_a", 10, "fuera del rango de Hemograma"),         # 10 °C: OK conservadora (0-30), no el análisis (2-8)
        ("cons_a", 1, "fuera del rango de Hemograma"),
        ("cons_norte", 4, "otra clínica"),
    ],
)
def test_empaquetar_validaciones(derivacion, envios, lab, conexion, cons, temp, mensaje) -> None:
    emitida = emitir(derivacion, lab)
    with pytest.raises(ReglaNegocioError, match=mensaje):
        empaquetar(envios, lab, emitida.muestras, temp=temp, conservadora=getattr(lab, cons))
    _sin_cambios_tras_empaquetar_fallido(derivacion, envios, lab, conexion, emitida)


def test_empaquetar_temperatura_fuera_del_rango_de_la_conservadora(derivacion, envios, lab, conexion) -> None:
    emitida = emitir(derivacion, lab, lab.hemograma)
    with pytest.raises(ReglaNegocioError, match="rango de la conservadora"):  # 7 °C: OK Hemograma, no CONS-B (2-6)
        empaquetar(envios, lab, emitida.muestras, temp=7, conservadora=lab.cons_b)
    _sin_cambios_tras_empaquetar_fallido(derivacion, envios, lab, conexion, emitida)


def test_empaquetar_conservadora_con_rango_incompatible(derivacion, envios, lab, conexion) -> None:
    """Regla 7: una conservadora de congelado (-20 a -10 °C) no sirve para un hemograma (2 a 8 °C)."""
    congeladora = ServicioCatalogos().alta(Conservadora("CONS-F", lab.clinica.id_clinica, 5, -20, -10))
    emitida = emitir(derivacion, lab, lab.hemograma)
    with pytest.raises(ReglaNegocioError, match="no es compatible con Hemograma"):
        empaquetar(envios, lab, emitida.muestras, temp=-15, conservadora=congeladora)
    _sin_cambios_tras_empaquetar_fallido(derivacion, envios, lab, conexion, emitida)


def test_empaquetar_muestra_ya_empaquetada_lo_decide_el_state(derivacion, envios, lab, conexion) -> None:
    emitida = emitir(derivacion, lab, lab.hemograma)
    empaquetar(envios, lab, emitida.muestras, "P-1", conservadora=lab.cons_a)
    with pytest.raises(TransicionInvalidaError, match="Empaquetada"):
        empaquetar(envios, lab, emitida.muestras, "P-2", conservadora=lab.cons_b)
    assert contar(conexion, "remito_biologico") == 1  # el segundo remito se deshizo
    assert conservadora(lab, lab.cons_b).estado == "Disponible"


def test_empaquetar_otras_validaciones(derivacion, envios, lab) -> None:
    emitida = emitir(derivacion, lab, lab.hemograma)
    otra_lab = emitir(derivacion, lab, lab.hemograma, id_laboratorio=lab.laboratorio2.id_laboratorio)
    with pytest.raises(ReglaNegocioError, match="mismo laboratorio"):
        empaquetar(envios, lab, emitida.muestras + otra_lab.muestras)
    with pytest.raises(ReglaNegocioError, match="repetidas"):
        envios.empaquetar([emitida.muestras[0].id_muestra] * 2, lab.cons_a.id_conservadora, "P-1", 4)
    with pytest.raises(ReglaNegocioError, match="al menos una"):
        envios.empaquetar([], lab.cons_a.id_conservadora, "P-1", 4)
    with pytest.raises(EntidadNoEncontradaError, match="muestra 999"):
        envios.empaquetar([999], lab.cons_a.id_conservadora, "P-1", 4)

    empaquetar(envios, lab, emitida.muestras, "P-1")
    with pytest.raises(ReglaNegocioError, match="precinto con número P-1"):
        empaquetar(envios, lab, otra_lab.muestras, "P-1", conservadora=lab.cons_b)


# =============================================================================
#  3. registrar_tramo
# =============================================================================

def test_tramos_validaciones(derivacion, envios, lab) -> None:
    emitida = emitir(derivacion, lab, lab.hemograma)
    remito = empaquetar(envios, lab, emitida.muestras)
    t = lab.transportista.id_transportista

    with pytest.raises(EntidadNoEncontradaError, match="transportista"):
        envios.registrar_tramo(remito.id_remito, 999, "A", "B", SALIDA_1)
    # Salir antes del empaquetado viola el orden cronológico del historial.
    with pytest.raises(ValueError, match="anterior"):
        envios.registrar_tramo(remito.id_remito, t, "A", "B", "2026-10-22 10:00", "2026-10-22 10:20")
    assert envios.obtener_remito(remito.id_remito).estado == "Emitido"
    assert envios.tramos_de(remito.id_remito) == []

    tramo1 = envios.registrar_tramo(remito.id_remito, t, "Clínica", "Centro", SALIDA_1)  # sin llegada
    with pytest.raises(ReglaNegocioError, match="todavía no registró su llegada"):
        envios.registrar_tramo(remito.id_remito, t, "Centro", "Lab", SALIDA_2)
    envios.registrar_llegada_tramo(tramo1.id_tramo, LLEGADA_1, 5.0)
    with pytest.raises(ReglaNegocioError, match="ya tiene registrada"):
        envios.registrar_llegada_tramo(tramo1.id_tramo, LLEGADA_1)
    with pytest.raises(ReglaNegocioError, match="antes de la llegada"):
        envios.registrar_tramo(remito.id_remito, t, "Centro", "Lab", "2026-10-22 11:30")
    envios.registrar_tramo(remito.id_remito, t, "Centro", "Lab", SALIDA_2, LLEGADA_2)
    # El segundo tramo no vuelve a despachar las muestras.
    assert [c.estado for c in derivacion.historial_de_muestra(emitida.muestras[0].id_muestra)] == [
        "Extraída", "Empaquetada", "En tránsito"
    ]


def test_no_se_registran_tramos_de_un_remito_recibido(derivacion, envios, laboratorio, lab) -> None:
    _, remito = preparar_en_transito(derivacion, envios, lab, lab.hemograma)
    laboratorio.recibir(remito.id_remito, "Lucía", True, 5.0, fecha_hora=RECEPCION)
    with pytest.raises(ReglaNegocioError, match="ya fue recibido"):
        envios.registrar_tramo(remito.id_remito, lab.transportista.id_transportista, "X", "Y", "2026-10-22 14:00")


# =============================================================================
#  4 y 5. recibir / registrar_resultado: transiciones inválidas
# =============================================================================

def test_recibir_remito_no_despachado_o_ya_recibido(derivacion, envios, laboratorio, lab, conexion) -> None:
    emitida = emitir(derivacion, lab, lab.hemograma)
    remito = empaquetar(envios, lab, emitida.muestras)
    with pytest.raises(TransicionInvalidaError, match="Emitido"):
        laboratorio.recibir(remito.id_remito, "Lucía", True, 5.0, fecha_hora=RECEPCION)
    assert contar(conexion, "recepcion") == 0
    assert conservadora(lab, lab.cons_a).estado == "En uso"

    despachar(envios, lab, remito)
    laboratorio.recibir(remito.id_remito, "Lucía", True, 5.0, fecha_hora=RECEPCION)
    with pytest.raises(TransicionInvalidaError, match="Recibido"):
        laboratorio.recibir(remito.id_remito, "Lucía", True, 5.0, fecha_hora=RECEPCION)
    assert contar(conexion, "recepcion") == 1
    with pytest.raises(EntidadNoEncontradaError):
        laboratorio.recibir(999, "Lucía", True, 5.0)


def test_resultado_solo_desde_recibida(derivacion, envios, laboratorio, lab, conexion) -> None:
    emitida = emitir(derivacion, lab, lab.hemograma)
    muestra = emitida.muestras[0]
    with pytest.raises(TransicionInvalidaError, match="Extraída"):
        laboratorio.registrar_resultado(muestra.id_muestra, "Bioq. Díaz", "x", fecha_hora="2026-10-23 09:00")

    remito = empaquetar(envios, lab, emitida.muestras)
    despachar(envios, lab, remito)
    laboratorio.recibir(remito.id_remito, "Lucía", True, 5.0, fecha_hora=RECEPCION)
    laboratorio.registrar_resultado(muestra.id_muestra, "Bioq. Díaz", "Hto 45 %", fecha_hora="2026-10-23 09:00")
    with pytest.raises(TransicionInvalidaError, match="Analizada"):
        laboratorio.registrar_resultado(muestra.id_muestra, "Bioq. Díaz", "otra vez", fecha_hora="2026-10-23 10:00")
    assert contar(conexion, "resultado_analisis") == 1
    assert laboratorio.obtener_resultado(muestra.id_muestra).valores == "Hto 45 %"


def test_resultado_con_datos_invalidos_no_cambia_estado(derivacion, envios, laboratorio, lab) -> None:
    emitida, remito = preparar_en_transito(derivacion, envios, lab, lab.hemograma)
    laboratorio.recibir(remito.id_remito, "Lucía", True, 5.0, fecha_hora=RECEPCION)
    muestra = emitida.muestras[0]
    with pytest.raises(ValueError, match="valores"):
        laboratorio.registrar_resultado(muestra.id_muestra, "Bioq. Díaz", "  ", fecha_hora="2026-10-23 09:00")
    assert derivacion.obtener_muestra(muestra.id_muestra).estado_actual == "Recibida"
