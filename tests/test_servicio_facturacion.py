"""Tests de ServicioFacturacion."""

import pytest

from dominio import Comprobante
from dominio.excepciones import EntidadNoEncontradaError, ReglaNegocioError
from servicios import (
    ServicioAtencion,
    ServicioDerivacion,
    ServicioEnvios,
    ServicioFacturacion,
    ServicioLaboratorio,
    VacunaAAplicar,
)

FECHA = "2026-10-22"


@pytest.fixture
def servicio(lab) -> ServicioFacturacion:
    return ServicioFacturacion()


def contar(conexion, tabla: str) -> int:
    return conexion.cursor().execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


def nueva_atencion(lab, tipo, fecha_hora="2026-10-22 18:00", vacunas=()):
    return ServicioAtencion().registrar(
        lab.mascota.id_mascota, lab.vet.id_veterinario, tipo.id_tipo_atencion, fecha_hora, "Motivo",
        vacunas=[VacunaAAplicar(vac.id_vacuna, f"L-{vac.id_vacuna}") for vac in vacunas],
    ).atencion


def por_tipo(comprobante: Comprobante) -> dict[str, list]:
    agrupado: dict[str, list] = {}
    for detalle in comprobante.detalles:
        agrupado.setdefault(detalle.tipo_item, []).append(detalle)
    return agrupado


# =============================================================================
#  Casos OK
# =============================================================================

def test_consulta_simple_tarifa_normal(servicio, lab) -> None:
    comprobante = servicio.emitir_comprobante(lab.atencion.id_atencion, FECHA)
    assert comprobante.numero == "C-2026-00001"
    assert comprobante.id_cliente == lab.cliente.id_cliente
    assert comprobante.id_clinica == lab.clinica.id_clinica
    (detalle,) = comprobante.detalles
    assert detalle.tipo_item == "Atención" and detalle.id_atencion == lab.atencion.id_atencion
    assert (detalle.precio_unitario, detalle.subtotal) == (8000, 8000)
    assert "Consulta - Firulais" in detalle.descripcion and "Tarifa normal" in detalle.descripcion
    assert comprobante.total == 8000


def test_urgencia_aplica_recargo_a_todos_los_items(servicio, lab) -> None:
    atencion = nueva_atencion(lab, lab.urgencia, vacunas=[lab.antirrabica])
    ServicioDerivacion().emitir_orden(atencion.id_atencion, lab.laboratorio.id_laboratorio,
                                      [(lab.hemograma.id_tipo_analisis, 3.0)])

    comprobante = servicio.emitir_comprobante(atencion.id_atencion, FECHA)
    items = por_tipo(comprobante)
    assert [(d.precio_unitario, d.subtotal) for d in items["Atención"]] == [(12000, 15600)]
    assert [(d.precio_unitario, d.subtotal) for d in items["Vacuna"]] == [(6000, 7800)]
    assert [(d.precio_unitario, d.subtotal) for d in items["Análisis"]] == [(5000, 6500)]
    assert items["Análisis"][0].id_muestra is not None
    assert all("+30 %" in d.descripcion for d in comprobante.detalles)
    assert comprobante.total == 15600 + 7800 + 6500


def test_control_aplica_descuento(servicio, lab) -> None:
    atencion = nueva_atencion(lab, lab.control, vacunas=[lab.sextuple])
    comprobante = servicio.emitir_comprobante(atencion.id_atencion, FECHA)
    assert [d.subtotal for d in comprobante.detalles] == [4800, 5600]  # 6000 y 7000 con -20 %
    assert comprobante.total == 10400


def test_excluye_analisis_de_muestras_rechazadas(servicio, lab) -> None:
    emitida = ServicioDerivacion().emitir_orden(
        lab.atencion.id_atencion, lab.laboratorio.id_laboratorio,
        [(lab.hemograma.id_tipo_analisis, 3.0), (lab.urianalisis.id_tipo_analisis, 10.0)],
    )
    envios = ServicioEnvios()
    remito = envios.empaquetar([m.id_muestra for m in emitida.muestras], lab.cons_a.id_conservadora, "P-1", 4,
                               fecha_hora="2026-10-22 10:30")
    envios.registrar_tramo(remito.id_remito, lab.transportista.id_transportista, "Clínica", "Lab",
                           "2026-10-22 11:00", "2026-10-22 12:00")
    # 5 h después de la extracción: Urianálisis (4 h de viabilidad) se rechaza.
    recibido = ServicioLaboratorio().recibir(remito.id_remito, "Lucía", True, 5.0, fecha_hora="2026-10-22 15:00")
    assert len(recibido.rechazadas) == 1

    comprobante = servicio.emitir_comprobante(lab.atencion.id_atencion, FECHA)
    analisis = por_tipo(comprobante)["Análisis"]
    assert [d.id_muestra for d in analisis] == [emitida.muestras[0].id_muestra]
    assert "Hemograma" in analisis[0].descripcion
    assert comprobante.total == 8000 + 5000


def test_comprobante_queda_persistido(servicio, lab, conexion) -> None:
    atencion = nueva_atencion(lab, lab.consulta, vacunas=[lab.antirrabica, lab.lepto])
    emitido = servicio.emitir_comprobante(atencion.id_atencion, FECHA)
    conexion.rollback()  # ya confirmado
    leido = servicio.obtener(emitido.id_comprobante)
    assert leido.numero == emitido.numero and leido.total == emitido.total == 8000 + 6000 + 5000
    assert len(leido.detalles) == 3
    assert servicio.esta_facturada(atencion.id_atencion)
    assert [c.numero for c in servicio.comprobantes_de_cliente(lab.cliente.id_cliente)] == [emitido.numero]


def test_numeracion_correlativa_por_anio(servicio, lab) -> None:
    a2 = nueva_atencion(lab, lab.consulta, "2026-10-22 18:00")
    a3 = nueva_atencion(lab, lab.consulta, "2026-10-22 19:00")
    c1 = servicio.emitir_comprobante(lab.atencion.id_atencion, "2026-10-22")
    c2 = servicio.emitir_comprobante(a2.id_atencion, "2026-10-23")
    c3 = servicio.emitir_comprobante(a3.id_atencion, "2027-01-02")
    assert [c1.numero, c2.numero, c3.numero] == ["C-2026-00001", "C-2026-00002", "C-2027-00001"]


# =============================================================================
#  Casos de error
# =============================================================================

def test_no_se_factura_dos_veces(servicio, lab, conexion) -> None:
    servicio.emitir_comprobante(lab.atencion.id_atencion, FECHA)
    with pytest.raises(ReglaNegocioError, match="ya fue facturada"):
        servicio.emitir_comprobante(lab.atencion.id_atencion, FECHA)
    assert contar(conexion, "comprobante") == 1
    assert contar(conexion, "detalle_comprobante") == 1


def test_atencion_inexistente(servicio, lab) -> None:
    with pytest.raises(EntidadNoEncontradaError, match="atención"):
        servicio.emitir_comprobante(999, FECHA)


def test_fecha_invalida(servicio, lab, conexion) -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        servicio.emitir_comprobante(lab.atencion.id_atencion, "22/10/2026")
    assert contar(conexion, "comprobante") == 0


def test_falla_al_guardar_detalles_deshace_todo(servicio, lab, conexion, monkeypatch) -> None:
    """Si falla un INSERT de detalle, tampoco queda la cabecera (rollback)."""
    def falla(_comprobante):
        raise RuntimeError("falla simulada")

    original = servicio.comprobantes._insertar_detalles_pendientes
    monkeypatch.setattr(servicio.comprobantes, "_insertar_detalles_pendientes", falla)
    with pytest.raises(RuntimeError):
        servicio.emitir_comprobante(lab.atencion.id_atencion, FECHA)
    assert contar(conexion, "comprobante") == 0
    assert not servicio.esta_facturada(lab.atencion.id_atencion)

    # Tras el error se puede facturar normalmente y el número no se "quema".
    monkeypatch.setattr(servicio.comprobantes, "_insertar_detalles_pendientes", original)
    assert servicio.emitir_comprobante(lab.atencion.id_atencion, FECHA).numero == "C-2026-00001"
