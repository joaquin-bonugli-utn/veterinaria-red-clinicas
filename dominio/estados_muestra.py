"""Patrón State de la muestra biológica.

El contexto (``Muestra``) delega cada operación en su estado actual. Cada estado
concreto sobreescribe solo las transiciones que permite el diagrama y, para
avanzar, llama a ``muestra.cambiar_estado(nuevo_estado, ...)``. Cualquier otra
operación cae en la implementación por defecto de ``EstadoMuestra``, que lanza
``TransicionInvalidaError``.

    Extraída → Empaquetada → En tránsito → Recibida → Analizada
                                  │            │
                                  └→ Rechazada ←┘
    (En tránsito → Rechazada al recibir con precinto roto;
     Recibida → Rechazada por viabilidad vencida o temperatura fuera de rango)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from dominio.excepciones import TransicionInvalidaError

if TYPE_CHECKING:
    from dominio.derivacion import Muestra


class EstadoMuestra(ABC):
    """Estado abstracto: por defecto ninguna transición está permitida."""

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre del estado tal como se guarda en la base."""

    def empaquetar(self, muestra: Muestra, responsable: str, fecha_hora: str | None = None) -> None:
        self._transicion_invalida("empaquetar")

    def despachar(self, muestra: Muestra, responsable: str, fecha_hora: str | None = None) -> None:
        self._transicion_invalida("despachar")

    def recibir(
        self, muestra: Muestra, precinto_intacto: bool, responsable: str, fecha_hora: str | None = None
    ) -> None:
        self._transicion_invalida("recibir")

    def rechazar(
        self, muestra: Muestra, motivo: str, responsable: str, fecha_hora: str | None = None
    ) -> None:
        self._transicion_invalida("rechazar")

    def registrar_resultado(self, muestra: Muestra, responsable: str, fecha_hora: str | None = None) -> None:
        self._transicion_invalida("registrar el resultado de")

    def _transicion_invalida(self, accion: str) -> None:
        raise TransicionInvalidaError(f"No se puede {accion} una muestra en estado '{self.nombre}'.")

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, EstadoMuestra) and self.nombre == otro.nombre

    def __hash__(self) -> int:
        return hash(self.nombre)

    def __str__(self) -> str:
        return self.nombre


class Extraida(EstadoMuestra):
    """Recién extraída en la clínica: solo puede empaquetarse."""

    @property
    def nombre(self) -> str:
        return "Extraída"

    def empaquetar(self, muestra: Muestra, responsable: str, fecha_hora: str | None = None) -> None:
        muestra.cambiar_estado(Empaquetada(), responsable, fecha_hora, "Empaquetada en conservadora")


class Empaquetada(EstadoMuestra):
    """Dentro de una conservadora precintada: solo puede despacharse."""

    @property
    def nombre(self) -> str:
        return "Empaquetada"

    def despachar(self, muestra: Muestra, responsable: str, fecha_hora: str | None = None) -> None:
        muestra.cambiar_estado(EnTransito(), responsable, fecha_hora, "Despachada al laboratorio")


class EnTransito(EstadoMuestra):
    """Viajando al laboratorio: al recibirse se verifica el precinto."""

    @property
    def nombre(self) -> str:
        return "En tránsito"

    def recibir(
        self, muestra: Muestra, precinto_intacto: bool, responsable: str, fecha_hora: str | None = None
    ) -> None:
        if precinto_intacto:
            muestra.cambiar_estado(Recibida(), responsable, fecha_hora, "Recibida en laboratorio")
        else:
            muestra.cambiar_estado(Rechazada(), responsable, fecha_hora, "Precinto roto en la recepción")


class Recibida(EstadoMuestra):
    """En el laboratorio: se analiza o se rechaza (viabilidad / temperatura)."""

    @property
    def nombre(self) -> str:
        return "Recibida"

    def rechazar(
        self, muestra: Muestra, motivo: str, responsable: str, fecha_hora: str | None = None
    ) -> None:
        if not isinstance(motivo, str) or not motivo.strip():
            raise ValueError("Para rechazar una muestra hay que indicar el motivo.")
        muestra.cambiar_estado(Rechazada(), responsable, fecha_hora, motivo.strip())

    def registrar_resultado(self, muestra: Muestra, responsable: str, fecha_hora: str | None = None) -> None:
        muestra.cambiar_estado(Analizada(), responsable, fecha_hora, "Resultado registrado")


class Analizada(EstadoMuestra):
    """Estado final: el resultado ya fue cargado."""

    @property
    def nombre(self) -> str:
        return "Analizada"


class Rechazada(EstadoMuestra):
    """Estado final: no admite resultados ni otras transiciones."""

    @property
    def nombre(self) -> str:
        return "Rechazada"

    def registrar_resultado(self, muestra: Muestra, responsable: str, fecha_hora: str | None = None) -> None:
        raise TransicionInvalidaError("No se pueden cargar resultados de una muestra rechazada.")


# Camino normal de una muestra (sin rechazo), en orden.
SECUENCIA_NORMAL = ("Extraída", "Empaquetada", "En tránsito", "Recibida", "Analizada")

_ESTADOS: dict[str, type[EstadoMuestra]] = {
    clase().nombre: clase for clase in (Extraida, Empaquetada, EnTransito, Recibida, Analizada, Rechazada)
}


def estado_desde_nombre(nombre: str) -> EstadoMuestra:
    """Reconstruye el objeto estado a partir del texto guardado en la base."""
    try:
        return _ESTADOS[nombre]()
    except (KeyError, TypeError):
        raise ValueError(
            f"Estado de muestra desconocido: {nombre!r}. Válidos: {', '.join(_ESTADOS)}."
        ) from None
