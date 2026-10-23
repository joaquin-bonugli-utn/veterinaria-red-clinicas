"""Funciones de validación reutilizadas por los constructores de las entidades.

Todas lanzan ValueError con un mensaje en español y devuelven el valor normalizado.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime

FORMATO_FECHA = "%Y-%m-%d"
FORMATO_FECHA_HORA = "%Y-%m-%d %H:%M"
_PATRON_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")
_PATRON_FECHA_HORA = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")


def texto_obligatorio(valor: object, campo: str) -> str:
    """Exige un texto no vacío y lo devuelve sin espacios sobrantes."""
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"El campo '{campo}' es obligatorio.")
    return valor.strip()


def texto_opcional(valor: object, campo: str) -> str | None:
    """Acepta None o texto; un texto vacío se normaliza a None."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ValueError(f"El campo '{campo}' debe ser un texto.")
    return valor.strip() or None


def id_opcional(valor: object, campo: str) -> int | None:
    """Acepta None (entidad aún no persistida) o un entero positivo."""
    if valor is None:
        return None
    return id_obligatorio(valor, campo)


def id_obligatorio(valor: object, campo: str) -> int:
    """Exige un identificador entero positivo."""
    if valor is None:
        raise ValueError(f"El campo '{campo}' es obligatorio.")
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ValueError(f"El campo '{campo}' debe ser un entero positivo.")
    return valor


def entero_positivo(valor: object, campo: str) -> int:
    """Exige un entero mayor que cero."""
    return id_obligatorio(valor, campo)


def entero_no_negativo(valor: object, campo: str) -> int:
    """Exige un entero mayor o igual que cero."""
    if valor is None:
        raise ValueError(f"El campo '{campo}' es obligatorio.")
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ValueError(f"El campo '{campo}' debe ser un entero no negativo.")
    return valor


def numero(valor: object, campo: str) -> float:
    """Exige un número (int o float); admite negativos, p. ej. temperaturas."""
    if valor is None:
        raise ValueError(f"El campo '{campo}' es obligatorio.")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"El campo '{campo}' debe ser numérico.")
    return float(valor)


def numero_opcional(valor: object, campo: str) -> float | None:
    """Acepta None o un número."""
    return None if valor is None else numero(valor, campo)


def numero_no_negativo(valor: object, campo: str) -> float:
    """Exige un número mayor o igual que cero."""
    resultado = numero(valor, campo)
    if resultado < 0:
        raise ValueError(f"El campo '{campo}' no puede ser negativo.")
    return resultado


def numero_no_negativo_opcional(valor: object, campo: str) -> float | None:
    """Acepta None o un número no negativo."""
    return None if valor is None else numero_no_negativo(valor, campo)


def booleano(valor: object, campo: str) -> bool:
    """Acepta bool o 0/1 (como se guarda en SQLite)."""
    if isinstance(valor, bool):
        return valor
    if valor in (0, 1):
        return bool(valor)
    raise ValueError(f"El campo '{campo}' debe ser verdadero o falso (1/0).")


def opcion(valor: object, campo: str, opciones: Iterable[str]) -> str:
    """Exige que el valor sea una de las opciones permitidas."""
    permitidas = tuple(opciones)
    if valor not in permitidas:
        raise ValueError(
            f"El campo '{campo}' debe ser uno de: {', '.join(permitidas)} (se recibió {valor!r})."
        )
    return valor  # type: ignore[return-value]


def fecha_iso(valor: object, campo: str) -> str:
    """Exige una fecha válida con formato 'YYYY-MM-DD'."""
    texto = texto_obligatorio(valor, campo)
    try:
        if not _PATRON_FECHA.fullmatch(texto):
            raise ValueError
        datetime.strptime(texto, FORMATO_FECHA)
    except ValueError:
        raise ValueError(
            f"El campo '{campo}' debe ser una fecha válida con formato YYYY-MM-DD (se recibió {texto!r})."
        ) from None
    return texto


def fecha_iso_opcional(valor: object, campo: str) -> str | None:
    """Acepta None o una fecha 'YYYY-MM-DD'."""
    return None if valor is None else fecha_iso(valor, campo)


def fecha_hora_iso(valor: object, campo: str) -> str:
    """Exige una fecha y hora válida con formato 'YYYY-MM-DD HH:MM'."""
    texto = texto_obligatorio(valor, campo)
    try:
        if not _PATRON_FECHA_HORA.fullmatch(texto):
            raise ValueError
        datetime.strptime(texto, FORMATO_FECHA_HORA)
    except ValueError:
        raise ValueError(
            f"El campo '{campo}' debe tener formato YYYY-MM-DD HH:MM válido (se recibió {texto!r})."
        ) from None
    return texto


def fecha_hora_iso_opcional(valor: object, campo: str) -> str | None:
    """Acepta None o una fecha y hora 'YYYY-MM-DD HH:MM'."""
    return None if valor is None else fecha_hora_iso(valor, campo)


def a_fecha(valor: str | date) -> date:
    """Convierte 'YYYY-MM-DD' (o un date) a date."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return datetime.strptime(fecha_iso(valor, "fecha"), FORMATO_FECHA).date()


def a_fecha_hora(valor: str | datetime) -> datetime:
    """Convierte 'YYYY-MM-DD HH:MM' (o un datetime) a datetime."""
    if isinstance(valor, datetime):
        return valor
    return datetime.strptime(fecha_hora_iso(valor, "fecha_hora"), FORMATO_FECHA_HORA)
