"""Casos de uso de catálogos (clínicas, laboratorios, especies, vacunas, tipos de
atención y de análisis, transportistas y conservadoras) y de veterinarios."""

from __future__ import annotations

import sqlite3
from typing import Any, TypeVar

from dominio import (
    Clinica,
    Conservadora,
    Especie,
    Laboratorio,
    TipoAnalisis,
    TipoAtencion,
    Transportista,
    Vacuna,
    Veterinario,
)
from dominio.excepciones import ReglaNegocioError
from persistencia.repositorios import RepositorioCatalogos, RepositorioEnvios, RepositorioVeterinarios
from servicios.base import ServicioBase

T = TypeVar("T")

_CON_NOMBRE_UNICO = (Clinica, Laboratorio, Especie, TipoAtencion, TipoAnalisis)
_PK = {
    Clinica: "id_clinica", Laboratorio: "id_laboratorio", Especie: "id_especie",
    TipoAtencion: "id_tipo_atencion", TipoAnalisis: "id_tipo_analisis", Vacuna: "id_vacuna",
    Transportista: "id_transportista", Conservadora: "id_conservadora",
}


def _id_de(entidad: Any) -> int | None:
    return getattr(entidad, _PK[type(entidad)])


class ServicioCatalogos(ServicioBase):
    """ABM de las tablas de referencia. Las conservadoras viven en RepositorioEnvios."""

    def __init__(
        self,
        repo_catalogos: RepositorioCatalogos | None = None,
        repo_envios: RepositorioEnvios | None = None,
    ) -> None:
        self.catalogos = repo_catalogos or RepositorioCatalogos()
        self.envios = repo_envios or RepositorioEnvios()

    def alta(self, entidad: T) -> T:
        """Da de alta cualquier entidad de catálogo validando unicidad y referencias."""
        try:
            self._validar(entidad)
            self._repo(entidad).agregar(entidad)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return entidad

    def modificar(self, entidad: Any) -> None:
        try:
            self._validar(entidad)
            self._repo(entidad).modificar(entidad)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

    def baja(self, id_: int, clase: type) -> None:
        """Baja física; si el registro está referenciado se informa en vez de romper la FK."""
        try:
            self._repo(clase).baja(id_, clase)
            self.conexion.commit()
        except sqlite3.IntegrityError:
            self.conexion.rollback()
            raise ReglaNegocioError(f"No se puede eliminar: el/la {clase.__name__} está en uso.") from None
        except Exception:
            self.conexion.rollback()
            raise

    def obtener(self, id_: int, clase: type[T]) -> T:
        return self._requerir(self._repo(clase).obtener_por_id(id_, clase), f"el/la {clase.__name__} {id_}")

    def listar(self, clase: type[T]) -> list[T]:
        if clase is Conservadora:
            return self.envios.listar(Conservadora)
        return self.catalogos.listar_ordenado(clase)

    def vacunas_de_especie(self, id_especie: int, solo_obligatorias: bool = False) -> list[Vacuna]:
        return self.catalogos.vacunas_por_especie(id_especie, solo_obligatorias)

    # --- Auxiliares --------------------------------------------------------------------

    def _repo(self, entidad_o_clase: Any):
        clase = entidad_o_clase if isinstance(entidad_o_clase, type) else type(entidad_o_clase)
        return self.envios if clase is Conservadora else self.catalogos

    def _validar(self, entidad: Any) -> None:
        clase = type(entidad)
        if clase not in _PK:
            raise TypeError(f"ServicioCatalogos no maneja {clase.__name__}.")
        id_propio = _id_de(entidad)

        if isinstance(entidad, _CON_NOMBRE_UNICO):
            existente = self.catalogos.buscar_por_nombre(clase, entidad.nombre)
            if existente is not None and _id_de(existente) != id_propio:
                raise ReglaNegocioError(f"Ya existe {clase.__name__} con nombre {entidad.nombre!r}.")
        elif isinstance(entidad, Vacuna):
            self._requerir(self.catalogos.obtener_por_id(entidad.id_especie, Especie), "la especie")
            repetida = [x for x in self.catalogos.vacunas_por_especie(entidad.id_especie)
                        if x.nombre.lower() == entidad.nombre.lower() and x.id_vacuna != id_propio]
            if repetida:
                raise ReglaNegocioError(f"La especie ya tiene una vacuna {entidad.nombre!r}.")
        elif isinstance(entidad, Transportista):
            existente = self.catalogos.buscar_transportista_por_documento(entidad.documento)
            if existente is not None and existente.id_transportista != id_propio:
                raise ReglaNegocioError(f"Ya existe un transportista con documento {entidad.documento}.")
        elif isinstance(entidad, Conservadora):
            self._requerir(self.catalogos.obtener_por_id(entidad.id_clinica, Clinica), "la clínica")
            existente = self.envios.buscar_conservadora_por_codigo(entidad.codigo)
            if existente is not None and existente.id_conservadora != id_propio:
                raise ReglaNegocioError(f"Ya existe una conservadora con código {entidad.codigo}.")


class ServicioVeterinarios(ServicioBase):
    def __init__(
        self,
        repo_veterinarios: RepositorioVeterinarios | None = None,
        repo_catalogos: RepositorioCatalogos | None = None,
    ) -> None:
        self.veterinarios = repo_veterinarios or RepositorioVeterinarios()
        self.catalogos = repo_catalogos or RepositorioCatalogos()

    def alta(
        self, matricula: str, nombre: str, apellido: str, id_clinica: int, especialidad: str | None = None
    ) -> Veterinario:
        veterinario = Veterinario(matricula, nombre, apellido, id_clinica, especialidad)
        try:
            self._validar(veterinario)
            self.veterinarios.agregar(veterinario)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return veterinario

    def modificar(self, veterinario: Veterinario) -> None:
        try:
            self._requerir(self.veterinarios.obtener_por_id(veterinario.id_veterinario), "el veterinario")
            self._validar(veterinario)
            self.veterinarios.modificar(veterinario)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

    def baja(self, id_veterinario: int) -> None:
        try:
            self._requerir_activo(self.veterinarios.obtener_por_id(id_veterinario), "el veterinario")
            self.veterinarios.baja(id_veterinario)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

    def obtener(self, id_veterinario: int) -> Veterinario:
        return self._requerir(self.veterinarios.obtener_por_id(id_veterinario), "el veterinario")

    def listar(self, solo_activos: bool = True) -> list[Veterinario]:
        return self.veterinarios.listar(solo_activos=solo_activos)

    def listar_por_clinica(self, id_clinica: int, solo_activos: bool = True) -> list[Veterinario]:
        return self.veterinarios.listar_por_clinica(id_clinica, solo_activos)

    def _validar(self, veterinario: Veterinario) -> None:
        self._requerir(self.catalogos.obtener_por_id(veterinario.id_clinica, Clinica), "la clínica")
        existente = self.veterinarios.buscar_por_matricula(veterinario.matricula)
        if existente is not None and existente.id_veterinario != veterinario.id_veterinario:
            raise ReglaNegocioError(f"Ya existe un veterinario con matrícula {veterinario.matricula}.")
