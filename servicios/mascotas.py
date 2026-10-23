"""Casos de uso de mascotas e historias clínicas."""

from __future__ import annotations

from datetime import date

from dominio import Especie, HistoriaClinica, Mascota
from persistencia.repositorios import RepositorioCatalogos, RepositorioClientes, RepositorioMascotas
from servicios.base import ServicioBase


class ServicioMascotas(ServicioBase):
    def __init__(
        self,
        repo_mascotas: RepositorioMascotas | None = None,
        repo_clientes: RepositorioClientes | None = None,
        repo_catalogos: RepositorioCatalogos | None = None,
    ) -> None:
        self.mascotas = repo_mascotas or RepositorioMascotas()
        self.clientes = repo_clientes or RepositorioClientes()
        self.catalogos = repo_catalogos or RepositorioCatalogos()

    # --- Casos de uso que modifican datos ------------------------------------------------

    def alta(
        self,
        nombre: str,
        id_especie: int,
        fecha_nacimiento: str,
        id_cliente: int,
        raza: str | None = None,
        sexo: str | None = None,
        peso_kg: float | None = None,
        alergias: str | None = None,
        antecedentes: str | None = None,
        fecha_apertura: str | None = None,
    ) -> Mascota:
        """Crea la mascota y su historia clínica en la MISMA transacción.

        Rechaza la operación si el cliente no existe o está dado de baja.
        """
        mascota = Mascota(nombre, id_especie, fecha_nacimiento, id_cliente, raza, sexo, peso_kg)
        try:
            self._validar_referencias(mascota)
            self.mascotas.agregar(mascota)
            historia = HistoriaClinica(
                mascota.id_mascota, fecha_apertura or date.today().isoformat(), alergias, antecedentes
            )
            self.mascotas.agregar(historia)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            mascota.id_mascota = None  # el INSERT se deshizo
            raise
        return mascota

    def modificar(self, mascota: Mascota) -> None:
        """Guarda cambios (incluido el cambio de responsable, que debe estar activo)."""
        try:
            self._requerir(self.mascotas.obtener_por_id(mascota.id_mascota), "la mascota")
            self._validar_referencias(mascota)
            self.mascotas.modificar(mascota)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

    def baja(self, id_mascota: int) -> None:
        """Baja lógica; la historia clínica se conserva."""
        try:
            self._requerir_activo(self.mascotas.obtener_por_id(id_mascota), "la mascota")
            self.mascotas.baja(id_mascota)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

    def actualizar_historia(
        self, id_mascota: int, alergias: str | None = None, antecedentes: str | None = None
    ) -> HistoriaClinica:
        try:
            historia = self.obtener_historia(id_mascota)
            historia.alergias = alergias
            historia.antecedentes = antecedentes
            self.mascotas.modificar(historia)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return historia

    # --- Consultas ---------------------------------------------------------------------

    def obtener(self, id_mascota: int) -> Mascota:
        return self._requerir(self.mascotas.obtener_por_id(id_mascota), "la mascota")

    def obtener_historia(self, id_mascota: int) -> HistoriaClinica:
        return self._requerir(
            self.mascotas.obtener_historia(id_mascota), "la historia clínica de la mascota"
        )

    def listar_por_cliente(self, id_cliente: int, solo_activas: bool = True) -> list[Mascota]:
        return self.mascotas.listar_por_cliente(id_cliente, solo_activas)

    def buscar_por_nombre(self, texto: str) -> list[Mascota]:
        return self.mascotas.buscar_por_nombre(texto)

    # --- Validaciones ------------------------------------------------------------------

    def _validar_referencias(self, mascota: Mascota) -> None:
        self._requerir_activo(self.clientes.obtener_por_id(mascota.id_cliente), "el cliente responsable")
        self._requerir(self.catalogos.obtener_por_id(mascota.id_especie, Especie), "la especie")
