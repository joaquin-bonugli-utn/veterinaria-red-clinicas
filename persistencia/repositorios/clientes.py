"""Repositorio de clientes."""

from __future__ import annotations

from dominio import Cliente
from persistencia.repositorios.base import RepositorioBase, Tabla


class RepositorioClientes(RepositorioBase):
    TABLAS = (Tabla("cliente", "id_cliente", Cliente),)
    PRINCIPAL = Cliente

    def buscar_por_dni(self, dni: str) -> Cliente | None:
        return self._buscar_uno(Cliente, "dni = ?", (dni.strip(),))

    def buscar_por_apellido(self, texto: str, solo_activos: bool = True) -> list[Cliente]:
        """Clientes cuyo apellido empieza con `texto` (sin distinguir mayúsculas)."""
        condicion = "apellido LIKE ?" + (" AND activo = 1" if solo_activos else "")
        return self._buscar(Cliente, condicion, (f"{texto.strip()}%",), orden="apellido, nombre")

    def buscar(self, texto: str, solo_activos: bool = True) -> list[Cliente]:
        """Búsqueda libre por DNI, nombre o apellido (contiene)."""
        patron = f"%{texto.strip()}%"
        condicion = "(dni LIKE ? OR nombre LIKE ? OR apellido LIKE ?)"
        if solo_activos:
            condicion += " AND activo = 1"
        return self._buscar(Cliente, condicion, (patron, patron, patron), orden="apellido, nombre")
