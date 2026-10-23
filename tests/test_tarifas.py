"""Tests del patrón Strategy de tarifas."""

import pytest

from dominio.tarifas import (
    CalculadoraImporte,
    EstrategiaTarifa,
    TarifaControl,
    TarifaNormal,
    TarifaUrgencia,
    estrategia_para,
)


@pytest.mark.parametrize(
    ("estrategia", "precio", "cantidad", "esperado"),
    [
        (TarifaNormal(), 8000, 1, 8000),
        (TarifaNormal(), 2500.5, 2, 5001),
        (TarifaUrgencia(), 12000, 1, 15600),
        (TarifaUrgencia(), 100, 3, 390),
        (TarifaControl(), 6000, 1, 4800),
        (TarifaControl(), 99.99, 1, 79.99),  # redondeo a 2 decimales
        (TarifaUrgencia(), 0, 1, 0),
    ],
)
def test_calculo_de_cada_estrategia(estrategia, precio, cantidad, esperado) -> None:
    assert estrategia.calcular(precio, cantidad) == esperado


@pytest.mark.parametrize("estrategia", [TarifaNormal(), TarifaUrgencia(), TarifaControl()])
def test_validaciones(estrategia) -> None:
    with pytest.raises(ValueError, match="negativo"):
        estrategia.calcular(-1, 1)
    with pytest.raises(ValueError, match="entero positivo"):
        estrategia.calcular(100, 0)


def test_estrategia_es_abstracta() -> None:
    with pytest.raises(TypeError):
        EstrategiaTarifa()  # type: ignore[abstract]


def test_calculadora_por_defecto_usa_tarifa_normal() -> None:
    calculadora = CalculadoraImporte()
    assert isinstance(calculadora.estrategia, TarifaNormal)
    assert calculadora.calcular(1000) == 1000


def test_cambiar_estrategia_cambia_el_resultado() -> None:
    calculadora = CalculadoraImporte(TarifaUrgencia())
    assert calculadora.calcular(1000) == 1300
    calculadora.cambiar_estrategia(TarifaControl())
    assert calculadora.calcular(1000) == 800
    calculadora.cambiar_estrategia(TarifaNormal())
    assert calculadora.calcular(1000, 2) == 2000


def test_cambiar_estrategia_rechaza_otros_objetos() -> None:
    with pytest.raises(TypeError):
        CalculadoraImporte().cambiar_estrategia("Urgencia")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("nombre", "clase"),
    [("Urgencia", TarifaUrgencia), ("URGENCIA", TarifaUrgencia), (" control ", TarifaControl),
     ("Control", TarifaControl), ("Consulta", TarifaNormal), ("Cirugía", TarifaNormal)],
)
def test_estrategia_segun_tipo_de_atencion(nombre, clase) -> None:
    assert isinstance(estrategia_para(nombre), clase)


def test_estrategia_para_nombre_vacio() -> None:
    with pytest.raises(ValueError):
        estrategia_para("")


def test_nombres_legibles() -> None:
    assert str(TarifaUrgencia()) == "Tarifa urgencia (+30 %)"
    assert str(TarifaControl()) == "Tarifa control (-20 %)"
