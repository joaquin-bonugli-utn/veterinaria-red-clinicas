"""Casos de uso de clientes."""

from __future__ import annotations

from dominio import Cliente
from dominio.excepciones import ReglaNegocioError
from persistencia.repositorios import RepositorioClientes, RepositorioMascotas
from servicios.base import ServicioBase


class ServicioClientes(ServicioBase):
    def __init__(
        self,
        repo_clientes: RepositorioClientes | None = None,
        repo_mascotas: RepositorioMascotas | None = None,
    ) -> None:
        self.clientes = repo_clientes or RepositorioClientes()
        self.mascotas = repo_mascotas or RepositorioMascotas()

    # --- Casos de uso que modifican datos ------------------------------------------------

    def alta(
        self,
        dni: str,
        nombre: str,
        apellido: str,
        telefono: str | None = None,
        email: str | None = None,
        direccion: str | None = None,
    ) -> Cliente:
        """Registra un cliente nuevo. El DNI no puede repetirse."""
        cliente = Cliente(dni, nombre, apellido, telefono, email, direccion)
        try:
            self._verificar_dni_libre(cliente.dni)
            self.clientes.agregar(cliente)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return cliente

    def modificar(self, cliente: Cliente) -> None:
        """Guarda los cambios de un cliente existente."""
        try:
            self._requerir(self.clientes.obtener_por_id(cliente.id_cliente), "el cliente")
            self._verificar_dni_libre(cliente.dni, excepto_id=cliente.id_cliente)
            self.clientes.modificar(cliente)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

    def baja(self, id_cliente: int) -> None:
        """Baja lógica. No se permite si el cliente tiene mascotas activas (regla 1)."""
        try:
            self._requerir_activo(self.clientes.obtener_por_id(id_cliente), "el cliente")
            activas = self.mascotas.listar_por_cliente(id_cliente)
            if activas:
                nombres = ", ".join(m.nombre for m in activas)
                raise ReglaNegocioError(
                    f"El cliente tiene mascotas activas a su cargo ({nombres}). Dalas de baja o reasignalas primero."
                )
            self.clientes.baja(id_cliente)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

    def reactivar(self, id_cliente: int) -> None:
        try:
            cliente = self._requerir(self.clientes.obtener_por_id(id_cliente), "el cliente")
            cliente.activo = True
            self.clientes.modificar(cliente)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

    # --- Consultas ---------------------------------------------------------------------

    def obtener(self, id_cliente: int) -> Cliente:
        return self._requerir(self.clientes.obtener_por_id(id_cliente), "el cliente")

    def buscar_por_dni(self, dni: str) -> Cliente | None:
        return self.clientes.buscar_por_dni(dni)

    def buscar(self, texto: str, solo_activos: bool = True) -> list[Cliente]:
        return self.clientes.buscar(texto, solo_activos)

    def listar(self, solo_activos: bool = True) -> list[Cliente]:
        return self.clientes.listar(solo_activos=solo_activos)

    # --- Validaciones ------------------------------------------------------------------

    def _verificar_dni_libre(self, dni: str, excepto_id: int | None = None) -> None:
        existente = self.clientes.buscar_por_dni(dni)
        if existente is not None and existente.id_cliente != excepto_id:
            detalle = "" if existente.activo else " (está dado de baja: reactivalo en lugar de crearlo)"
            raise ReglaNegocioError(f"Ya existe un cliente con DNI {dni}{detalle}.")
