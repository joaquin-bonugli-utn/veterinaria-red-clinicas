"""Patrón Strategy para el cálculo de importes.

``CalculadoraImporte`` (contexto) delega el cálculo en una ``EstrategiaTarifa``
intercambiable en tiempo de ejecución con ``cambiar_estrategia()``. La
estrategia se elige según el nombre del tipo de atención:

    Urgencia → TarifaUrgencia (+30 %)
    Control  → TarifaControl  (-20 %)
    otro     → TarifaNormal   (precio de lista)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from dominio import validaciones as v


class EstrategiaTarifa(ABC):
    """Estrategia abstracta: cómo se calcula el importe de un ítem."""

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre legible de la tarifa (se muestra en el detalle del comprobante)."""

    @abstractmethod
    def calcular(self, precio_base: float, cantidad: int = 1) -> float:
        """Importe total de `cantidad` unidades a `precio_base`, redondeado a 2 decimales."""

    @staticmethod
    def _base(precio_base: float, cantidad: int) -> float:
        """Valida los datos y devuelve precio_base × cantidad."""
        return v.numero_no_negativo(precio_base, "precio_base") * v.entero_positivo(cantidad, "cantidad")

    def __str__(self) -> str:
        return self.nombre


class TarifaNormal(EstrategiaTarifa):
    @property
    def nombre(self) -> str:
        return "Tarifa normal"

    def calcular(self, precio_base: float, cantidad: int = 1) -> float:
        return round(self._base(precio_base, cantidad), 2)


class TarifaUrgencia(EstrategiaTarifa):
    RECARGO = 0.30

    @property
    def nombre(self) -> str:
        return "Tarifa urgencia (+30 %)"

    def calcular(self, precio_base: float, cantidad: int = 1) -> float:
        return round(self._base(precio_base, cantidad) * (1 + self.RECARGO), 2)


class TarifaControl(EstrategiaTarifa):
    DESCUENTO = 0.20

    @property
    def nombre(self) -> str:
        return "Tarifa control (-20 %)"

    def calcular(self, precio_base: float, cantidad: int = 1) -> float:
        return round(self._base(precio_base, cantidad) * (1 - self.DESCUENTO), 2)


class CalculadoraImporte:
    """Contexto del patrón Strategy: calcula importes con la estrategia vigente."""

    def __init__(self, estrategia: EstrategiaTarifa | None = None) -> None:
        self._estrategia: EstrategiaTarifa = TarifaNormal()
        if estrategia is not None:
            self.cambiar_estrategia(estrategia)

    @property
    def estrategia(self) -> EstrategiaTarifa:
        return self._estrategia

    def cambiar_estrategia(self, estrategia: EstrategiaTarifa) -> None:
        if not isinstance(estrategia, EstrategiaTarifa):
            raise TypeError("La estrategia debe ser una EstrategiaTarifa.")
        self._estrategia = estrategia

    def calcular(self, precio_base: float, cantidad: int = 1) -> float:
        return self._estrategia.calcular(precio_base, cantidad)


_POR_TIPO_ATENCION: dict[str, type[EstrategiaTarifa]] = {
    "urgencia": TarifaUrgencia,
    "control": TarifaControl,
}


def estrategia_para(nombre_tipo_atencion: str) -> EstrategiaTarifa:
    """Elige la estrategia según tipo_atencion.nombre (sin distinguir mayúsculas)."""
    clave = v.texto_obligatorio(nombre_tipo_atencion, "nombre_tipo_atencion").lower()
    return _POR_TIPO_ATENCION.get(clave, TarifaNormal)()
