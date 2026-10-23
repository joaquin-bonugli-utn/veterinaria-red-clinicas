"""Repositorio de catálogos: especies, vacunas, tipos de atención y de análisis,
clínicas, laboratorios y transportistas.

Maneja varias clases, así que obtener_por_id, listar y baja reciben la clase:
``repo.obtener_por_id(3, Especie)``. agregar y modificar la deducen del objeto.
"""

from __future__ import annotations

from typing import TypeVar

from dominio import Clinica, Especie, Laboratorio, TipoAnalisis, TipoAtencion, Transportista, Vacuna
from persistencia.repositorios.base import RepositorioBase, Tabla

T = TypeVar("T")


class RepositorioCatalogos(RepositorioBase):
    TABLAS = (
        Tabla("especie", "id_especie", Especie),
        Tabla("vacuna", "id_vacuna", Vacuna),
        Tabla("tipo_atencion", "id_tipo_atencion", TipoAtencion),
        Tabla("tipo_analisis", "id_tipo_analisis", TipoAnalisis),
        Tabla("clinica", "id_clinica", Clinica),
        Tabla("laboratorio", "id_laboratorio", Laboratorio),
        Tabla("transportista", "id_transportista", Transportista),
    )
    PRINCIPAL = None

    _CON_NOMBRE_UNICO = (Especie, TipoAtencion, TipoAnalisis, Clinica, Laboratorio)

    def buscar_por_nombre(self, clase: type[T], nombre: str) -> T | None:
        """Busca por nombre exacto en los catálogos cuyo nombre es único."""
        if clase not in self._CON_NOMBRE_UNICO:
            raise TypeError(f"{clase.__name__} no tiene un nombre único.")
        return self._buscar_uno(clase, "nombre = ?", (nombre.strip(),))

    def listar_ordenado(self, clase: type[T]) -> list[T]:
        """Listado ordenado por nombre (útil para combos de la UI)."""
        return self._buscar(clase, orden="nombre")

    def vacunas_por_especie(self, id_especie: int, solo_obligatorias: bool = False) -> list[Vacuna]:
        condicion = "id_especie = ?" + (" AND obligatoria = 1" if solo_obligatorias else "")
        return self._buscar(Vacuna, condicion, (id_especie,), orden="edad_minima_dias, nombre")

    def buscar_transportista_por_documento(self, documento: str) -> Transportista | None:
        return self._buscar_uno(Transportista, "documento = ?", (documento.strip(),))
