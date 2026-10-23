"""Conexión única a la base SQLite — patrón **Singleton**.

Toda la aplicación (repositorios, servicios, reportes y UI) comparte UNA sola
conexión ``sqlite3``. Así todos ven la misma transacción en curso: un servicio
puede usar varios repositorios y confirmar o deshacer todo junto con un único
``commit()`` / ``rollback()``.

Cómo se garantiza la instancia única:
- ``Conexion.obtener()`` crea la instancia la primera vez y luego devuelve siempre la misma.
- El constructor exige un token privado: ``Conexion(...)`` desde afuera lanza TypeError.
- ``reiniciar_para_tests()`` reemplaza la instancia por una base en memoria (solo tests).

La conexión se abre con ``check_same_thread=False`` porque Flet ejecuta los
manejadores de eventos en hilos del ThreadPoolExecutor, distintos del hilo que
abrió la base. Es una app de escritorio de un solo usuario: no hay escrituras
concurrentes reales.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_ESQUEMA = RAIZ_PROYECTO / "db" / "schema.sql"
# Ruta absoluta: la app y el seed usan el mismo archivo sin importar desde dónde se ejecuten.
RUTA_DB = RAIZ_PROYECTO / "veterinaria.db"


class Conexion:
    """Envuelve una única conexión sqlite3 compartida por toda la aplicación.

    No instanciar directamente: usar ``Conexion.obtener()``.
    """

    _instancia: Conexion | None = None
    _TOKEN = object()  # solo los métodos de clase lo conocen

    def __init__(self, ruta: str, _token: object = None) -> None:
        if _token is not Conexion._TOKEN:
            raise TypeError("Conexion es un Singleton: usá Conexion.obtener() en lugar de instanciarla.")
        self.ruta = ruta
        self._conexion = sqlite3.connect(ruta, check_same_thread=False)
        self._conexion.row_factory = sqlite3.Row
        self._conexion.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def obtener(cls, ruta: str = str(RUTA_DB)) -> Conexion:
        """Devuelve la instancia única; la crea en la primera llamada.

        La ruta solo se usa al crearla: llamadas posteriores la ignoran.
        """
        if cls._instancia is None:
            cls._instancia = cls(ruta, cls._TOKEN)
        return cls._instancia

    @classmethod
    def reiniciar_para_tests(cls, ruta: str = ":memory:") -> Conexion:
        """Cierra la instancia actual y crea una nueva con el esquema cargado."""
        if cls._instancia is not None:
            cls._instancia.cerrar()
        cls._instancia = cls(ruta, cls._TOKEN)
        cls._instancia.inicializar_esquema()
        return cls._instancia

    def cursor(self) -> sqlite3.Cursor:
        """Devuelve un cursor nuevo sobre la conexión."""
        return self._conexion.cursor()

    def commit(self) -> None:
        """Confirma la transacción en curso."""
        self._conexion.commit()

    def rollback(self) -> None:
        """Deshace la transacción en curso."""
        self._conexion.rollback()

    def cerrar(self) -> None:
        """Cierra la conexión y libera la instancia única."""
        self._conexion.close()
        if Conexion._instancia is self:
            Conexion._instancia = None

    def inicializar_esquema(self, ruta_esquema: Path = RUTA_ESQUEMA) -> None:
        """Ejecuta el DDL de db/schema.sql (idempotente: usa IF NOT EXISTS)."""
        script = Path(ruta_esquema).read_text(encoding="utf-8")
        self._conexion.executescript(script)
        self._conexion.commit()

    def cantidades_por_tabla(self) -> dict[str, int]:
        """Cantidad de filas de cada tabla del esquema, en orden de creación."""
        tablas = [
            fila["name"]
            for fila in self._conexion.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name NOT LIKE ? ORDER BY rowid",
                ("table", "sqlite_%"),
            )
        ]
        # Los nombres salen del propio catálogo de SQLite, no de datos del usuario.
        return {t: self._conexion.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}
