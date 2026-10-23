"""Repositorio base con el ABMC genérico sobre la conexión Singleton.

Cada repositorio concreto declara en ``TABLAS`` qué clases de dominio maneja y
en qué tabla se guardan. Las columnas se leen del propio esquema
(``pragma_table_info``) y coinciden con los parámetros de los constructores de
dominio, así que una fila se convierte en objeto con ``Clase(**fila)``.

Los nombres de tabla y columna salen siempre de constantes del código; los
valores van SIEMPRE como parámetros ``?``. Los repositorios NO hacen commit:
la transacción la abre y la cierra el servicio.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, ClassVar

from persistencia.conexion import Conexion


class RegistroNoEncontradoError(LookupError):
    """No existe un registro con el id indicado."""


@dataclass(frozen=True)
class Tabla:
    """Asocia una clase de dominio con su tabla y su clave primaria."""

    nombre: str
    pk: str
    clase: type


class RepositorioBase:
    """ABMC genérico. Las subclases definen TABLAS y, si hace falta, PRINCIPAL."""

    TABLAS: ClassVar[tuple[Tabla, ...]] = ()
    # Clase que se usa cuando no se indica otra; None obliga a indicarla.
    PRINCIPAL: ClassVar[type | None] = None

    _cache_columnas: ClassVar[dict[str, tuple[str, ...]]] = {}

    def __init__(self, conexion: Conexion | None = None) -> None:
        self._conexion = conexion

    @property
    def conexion(self) -> Conexion:
        """Conexión explícita o, si no se pasó, la instancia Singleton vigente."""
        return self._conexion if self._conexion is not None else Conexion.obtener()

    # --- Acceso a SQL ------------------------------------------------------------

    def _ejecutar(self, sql: str, parametros: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conexion.cursor().execute(sql, tuple(parametros))

    def _uno(self, sql: str, parametros: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self._ejecutar(sql, parametros).fetchone()

    def _todos(self, sql: str, parametros: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self._ejecutar(sql, parametros).fetchall()

    def _escalar(self, sql: str, parametros: Iterable[Any] = ()) -> Any:
        fila = self._uno(sql, parametros)
        return None if fila is None else fila[0]

    # --- Metadatos -----------------------------------------------------------------

    def _tabla(self, clase_o_entidad: type | object | None = None) -> Tabla:
        clase = clase_o_entidad if isinstance(clase_o_entidad, type) or clase_o_entidad is None \
            else type(clase_o_entidad)
        if clase is None:
            if self.PRINCIPAL is None:
                raise ValueError(f"{type(self).__name__}: indicá la clase de dominio a consultar.")
            clase = self.PRINCIPAL
        for tabla in self.TABLAS:
            if tabla.clase is clase:
                return tabla
        raise TypeError(f"{type(self).__name__} no maneja objetos {clase.__name__}.")

    def _columnas(self, tabla: Tabla) -> tuple[str, ...]:
        """Columnas de la tabla sin la clave primaria (leídas del esquema)."""
        if tabla.nombre not in self._cache_columnas:
            filas = self._todos("SELECT name FROM pragma_table_info(?)", (tabla.nombre,))
            if not filas:
                raise RuntimeError(f"La tabla {tabla.nombre!r} no existe en el esquema.")
            self._cache_columnas[tabla.nombre] = tuple(f["name"] for f in filas if f["name"] != tabla.pk)
        return self._cache_columnas[tabla.nombre]

    def _tiene_activo(self, tabla: Tabla) -> bool:
        return "activo" in self._columnas(tabla)

    # --- Conversión fila -> objeto -------------------------------------------------

    def _construir(self, tabla: Tabla, fila: sqlite3.Row) -> Any:
        entidad = tabla.clase(**dict(fila))
        self._completar(entidad)
        return entidad

    def _completar(self, entidad: Any) -> None:
        """Gancho para cargar partes del agregado (historial, detalles...)."""

    def _buscar(
        self, clase: type | None, condicion: str = "", parametros: Iterable[Any] = (), orden: str | None = None
    ) -> list[Any]:
        """SELECT * de la tabla de `clase` con un WHERE opcional (con ?)."""
        tabla = self._tabla(clase)
        sql = f"SELECT * FROM {tabla.nombre}"
        if condicion:
            sql += f" WHERE {condicion}"
        sql += f" ORDER BY {orden or tabla.pk}"
        return [self._construir(tabla, fila) for fila in self._todos(sql, parametros)]

    def _buscar_uno(self, clase: type | None, condicion: str, parametros: Iterable[Any] = ()) -> Any | None:
        resultados = self._buscar(clase, condicion, parametros)
        return resultados[0] if resultados else None

    # --- ABMC ----------------------------------------------------------------------

    def agregar(self, entidad: Any) -> int:
        """INSERT de la entidad; le asigna el id generado y lo devuelve."""
        tabla = self._tabla(entidad)
        if getattr(entidad, tabla.pk) is not None:
            raise ValueError(f"La entidad ya tiene {tabla.pk}: usá modificar().")
        columnas = self._columnas(tabla)
        sql = (
            f"INSERT INTO {tabla.nombre} ({', '.join(columnas)}) "
            f"VALUES ({', '.join('?' for _ in columnas)})"
        )
        cursor = self._ejecutar(sql, (getattr(entidad, c) for c in columnas))
        setattr(entidad, tabla.pk, cursor.lastrowid)
        return cursor.lastrowid

    def modificar(self, entidad: Any) -> None:
        """UPDATE de todas las columnas de la entidad según su id."""
        tabla = self._tabla(entidad)
        id_ = getattr(entidad, tabla.pk)
        if id_ is None:
            raise ValueError(f"La entidad no tiene {tabla.pk}: usá agregar().")
        columnas = self._columnas(tabla)
        sql = f"UPDATE {tabla.nombre} SET {', '.join(f'{c} = ?' for c in columnas)} WHERE {tabla.pk} = ?"
        cursor = self._ejecutar(sql, [*(getattr(entidad, c) for c in columnas), id_])
        self._verificar_afectado(cursor, tabla, id_)

    def baja(self, id_: int, clase: type | None = None) -> None:
        """Baja lógica (activo = 0) si la tabla tiene ese campo; si no, DELETE."""
        tabla = self._tabla(clase)
        if self._tiene_activo(tabla):
            cursor = self._ejecutar(f"UPDATE {tabla.nombre} SET activo = 0 WHERE {tabla.pk} = ?", (id_,))
        else:
            cursor = self._ejecutar(f"DELETE FROM {tabla.nombre} WHERE {tabla.pk} = ?", (id_,))
        self._verificar_afectado(cursor, tabla, id_)

    def obtener_por_id(self, id_: int, clase: type | None = None) -> Any | None:
        """Devuelve el objeto de dominio o None si no existe."""
        tabla = self._tabla(clase)
        return self._buscar_uno(clase, f"{tabla.pk} = ?", (id_,))

    def listar(self, clase: type | None = None, solo_activos: bool = True) -> list[Any]:
        """Todos los registros; en tablas con `activo`, por defecto solo los activos."""
        tabla = self._tabla(clase)
        if solo_activos and self._tiene_activo(tabla):
            return self._buscar(clase, "activo = 1")
        return self._buscar(clase)

    @staticmethod
    def _verificar_afectado(cursor: sqlite3.Cursor, tabla: Tabla, id_: int) -> None:
        if cursor.rowcount == 0:
            raise RegistroNoEncontradoError(f"No existe {tabla.nombre} con {tabla.pk} = {id_}.")
