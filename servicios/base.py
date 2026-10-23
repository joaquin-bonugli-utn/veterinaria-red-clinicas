"""Utilidades comunes de la capa de servicios."""

from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from dominio import validaciones as v
from dominio.excepciones import EntidadNoEncontradaError, ReglaNegocioError
from persistencia.conexion import Conexion

T = TypeVar("T")


def ahora() -> str:
    """Fecha y hora actual en formato 'YYYY-MM-DD HH:MM'."""
    return datetime.now().strftime(v.FORMATO_FECHA_HORA)


class ServicioBase:
    """Base de los servicios: acceso a la conexión para commit/rollback.

    Cada caso de uso que modifica datos sigue el esquema:

        try:
            ...operaciones con repositorios...
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
    """

    @property
    def conexion(self) -> Conexion:
        return Conexion.obtener()

    @staticmethod
    def _requerir(entidad: T | None, descripcion: str) -> T:
        """Devuelve la entidad o lanza EntidadNoEncontradaError."""
        if entidad is None:
            raise EntidadNoEncontradaError(f"No existe {descripcion}.")
        return entidad

    @classmethod
    def _requerir_activo(cls, entidad: T | None, descripcion: str) -> T:
        """Como _requerir, pero además exige que la entidad esté activa."""
        entidad = cls._requerir(entidad, descripcion)
        if not getattr(entidad, "activo", True):
            raise ReglaNegocioError(f"{descripcion[0].upper()}{descripcion[1:]} está dado/a de baja.")
        return entidad
