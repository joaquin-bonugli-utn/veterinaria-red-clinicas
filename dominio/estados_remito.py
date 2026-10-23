"""Patrón State del remito biológico.

    Emitido → En tránsito → Recibido
                         └→ Rechazado (precinto roto)

El contexto (``RemitoBiologico``) delega en su estado; las operaciones no
permitidas lanzan ``TransicionInvalidaError``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from dominio.excepciones import TransicionInvalidaError

if TYPE_CHECKING:
    from dominio.derivacion import RemitoBiologico


class EstadoRemito(ABC):
    """Estado abstracto: por defecto ninguna transición está permitida."""

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre del estado tal como se guarda en la base."""

    def despachar(self, remito: RemitoBiologico) -> None:
        self._transicion_invalida("despachar")

    def recibir(self, remito: RemitoBiologico, precinto_intacto: bool) -> None:
        self._transicion_invalida("recibir")

    def _transicion_invalida(self, accion: str) -> None:
        raise TransicionInvalidaError(f"No se puede {accion} un remito en estado '{self.nombre}'.")

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, EstadoRemito) and self.nombre == otro.nombre

    def __hash__(self) -> int:
        return hash(self.nombre)

    def __str__(self) -> str:
        return self.nombre


class Emitido(EstadoRemito):
    @property
    def nombre(self) -> str:
        return "Emitido"

    def despachar(self, remito: RemitoBiologico) -> None:
        remito.cambiar_estado(EnTransitoRemito())


class EnTransitoRemito(EstadoRemito):
    @property
    def nombre(self) -> str:
        return "En tránsito"

    def recibir(self, remito: RemitoBiologico, precinto_intacto: bool) -> None:
        remito.cambiar_estado(Recibido() if precinto_intacto else Rechazado())


class Recibido(EstadoRemito):
    @property
    def nombre(self) -> str:
        return "Recibido"


class Rechazado(EstadoRemito):
    @property
    def nombre(self) -> str:
        return "Rechazado"


_ESTADOS: dict[str, type[EstadoRemito]] = {
    clase().nombre: clase for clase in (Emitido, EnTransitoRemito, Recibido, Rechazado)
}


def estado_desde_nombre(nombre: str) -> EstadoRemito:
    """Reconstruye el objeto estado a partir del texto guardado en la base."""
    try:
        return _ESTADOS[nombre]()
    except (KeyError, TypeError):
        raise ValueError(
            f"Estado de remito desconocido: {nombre!r}. Válidos: {', '.join(_ESTADOS)}."
        ) from None
