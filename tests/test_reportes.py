"""Tests de RepositorioReportes y de la generación de los 5 PDF (sobre los datos del seed)."""

from datetime import date

import pytest

from db.seed import cargar_datos
from persistencia.repositorios import RepositorioReportes
from reportes import REPORTES, FiltrosReporte
from reportes.base import moneda

HOY = date(2026, 10, 23)


@pytest.fixture
def filtros(conexion) -> FiltrosReporte:
    cargar_datos(HOY)
    return FiltrosReporte.ultimos_dias(91, hoy=HOY)


@pytest.fixture
def repo() -> RepositorioReportes:
    return RepositorioReportes()


# --- Filtros y formatos -------------------------------------------------------------

def test_filtros_validan_fechas() -> None:
    f = FiltrosReporte("2026-10-01", "2026-10-31", 2)
    assert f.parametros == ("2026-10-01", "2026-11-01", 2)  # 'hasta' inclusivo
    with pytest.raises(ValueError, match="anterior"):
        FiltrosReporte("2026-10-31", "2026-10-01")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        FiltrosReporte("01/10/2026", "2026-10-31")


def test_formato_moneda() -> None:
    assert moneda(1393500) == "$ 1.393.500,00"
    assert moneda(-11400) == "-$ 11.400,00"


# --- Consultas ------------------------------------------------------------------------

def test_atenciones_por_clinica_y_mes(repo, filtros) -> None:
    filas = repo.atenciones_por_clinica_y_mes(*filtros.parametros)
    assert sum(f["atenciones"] for f in filas) > 0
    assert sum(f["ordenes"] for f in filas) == 10
    assert all(f["consultas"] + f["controles"] + f["urgencias"] == f["atenciones"] for f in filas)
    assert all(f["atenciones_derivadas"] <= f["atenciones"] for f in filas)


def test_rechazos_en_transporte(repo, filtros) -> None:
    filas = repo.muestras_rechazadas_en_transporte(*filtros.parametros)
    categorias = sorted(f["categoria"] for f in filas)
    assert categorias == ["Precinto roto"] * 3 + ["Viabilidad vencida"]
    assert all(f["transportista"] and f["clinica"] for f in filas)


def test_facturacion_cuadra_con_los_comprobantes(repo, filtros) -> None:
    filas = repo.facturacion_por_clinica_y_tipo(*filtros.parametros)
    resumen = repo.resumen_comprobantes(*filtros.parametros)
    assert resumen["comprobantes"] > 0
    assert round(sum(f["importe_facturado"] for f in filas), 2) == resumen["total"]
    assert {f["tipo_item"] for f in filas} == {"Atención", "Vacuna", "Análisis"}


def test_tiempos_por_tipo_analisis(repo, filtros) -> None:
    filas = repo.tiempos_por_tipo_analisis(*filtros.parametros)
    assert filas
    for f in filas:
        assert 0 < f["transito_minimo"] <= f["transito_promedio"] <= f["transito_maximo"]
        assert f["analizadas"] <= f["muestras"]
        assert (f["procesamiento_promedio"] is None) == (f["analizadas"] == 0)


def test_filtro_por_clinica_reduce_resultados(repo, filtros) -> None:
    todas = sum(f["atenciones"] for f in repo.atenciones_por_clinica_y_mes(*filtros.parametros))
    por_clinica = [
        sum(f["atenciones"] for f in repo.atenciones_por_clinica_y_mes(filtros.desde, filtros.hasta_exclusivo, i))
        for i in (1, 2, 3)
    ]
    assert sum(por_clinica) == todas
    assert all(0 < n < todas for n in por_clinica)


def test_mascotas_y_tratamientos(repo, filtros) -> None:
    mascotas = repo.mascotas_atendidas(*filtros.parametros)
    tratamientos = repo.tratamientos_aplicados(*filtros.parametros)
    ids = {m["id_mascota"] for m in mascotas}
    assert mascotas and tratamientos
    assert {t["id_mascota"] for t in tratamientos} <= ids
    assert all(m["responsable"] and m["dni"] for m in mascotas)


# --- PDFs -----------------------------------------------------------------------------

@pytest.mark.parametrize("clase", REPORTES, ids=lambda c: c.__name__)
def test_genera_pdf(clase, filtros, tmp_path) -> None:
    ruta = clase().generar(filtros, tmp_path)
    assert ruta.exists() and ruta.parent == tmp_path
    contenido = ruta.read_bytes()
    assert contenido.startswith(b"%PDF")
    assert len(contenido) > 15_000  # incluye al menos una tabla y un gráfico


@pytest.mark.parametrize("clase", REPORTES, ids=lambda c: c.__name__)
def test_genera_pdf_por_clinica_y_sin_datos(clase, filtros, tmp_path) -> None:
    con_clinica = FiltrosReporte(filtros.desde, filtros.hasta, 1)
    assert clase().generar(con_clinica, tmp_path).name.endswith("_clinica1.pdf")
    # Un período sin datos igual genera el PDF con un aviso.
    vacio = FiltrosReporte("2020-01-01", "2020-01-31")
    assert clase().generar(vacio, tmp_path / "vacio").read_bytes().startswith(b"%PDF")
