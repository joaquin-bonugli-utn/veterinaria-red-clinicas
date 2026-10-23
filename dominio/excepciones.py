"""Excepciones de negocio del dominio."""


class ReglaNegocioError(Exception):
    """Base de todas las violaciones de reglas de negocio."""


class EntidadNoEncontradaError(ReglaNegocioError):
    """Se referenció un registro que no existe (cliente, mascota, turno...)."""


class TransicionInvalidaError(ReglaNegocioError):
    """Cambio de estado no permitido (patrón State de muestra y remito)."""


class TurnoSuperpuestoError(ReglaNegocioError):
    """El turno se superpone con otro del mismo veterinario."""


class PrecintoRotoError(ReglaNegocioError):
    """El precinto llegó roto: el remito y sus muestras se rechazan."""
