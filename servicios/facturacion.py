"""Casos de uso de facturación: emisión de comprobantes con el patrón Strategy."""

from __future__ import annotations

from datetime import date

from dominio import (
    Atencion,
    Comprobante,
    DetalleComprobante,
    HistoriaClinica,
    Mascota,
    TipoAnalisis,
    TipoAtencion,
    Vacuna,
)
from dominio import validaciones as v
from dominio.excepciones import ReglaNegocioError
from dominio.tarifas import CalculadoraImporte, estrategia_para
from persistencia.repositorios import (
    RepositorioAtenciones,
    RepositorioCatalogos,
    RepositorioComprobantes,
    RepositorioDerivaciones,
    RepositorioMascotas,
)
from servicios.base import ServicioBase


class ServicioFacturacion(ServicioBase):
    def __init__(
        self,
        repo_comprobantes: RepositorioComprobantes | None = None,
        repo_atenciones: RepositorioAtenciones | None = None,
        repo_mascotas: RepositorioMascotas | None = None,
        repo_derivaciones: RepositorioDerivaciones | None = None,
        repo_catalogos: RepositorioCatalogos | None = None,
    ) -> None:
        self.comprobantes = repo_comprobantes or RepositorioComprobantes()
        self.atenciones = repo_atenciones or RepositorioAtenciones()
        self.mascotas = repo_mascotas or RepositorioMascotas()
        self.derivaciones = repo_derivaciones or RepositorioDerivaciones()
        self.catalogos = repo_catalogos or RepositorioCatalogos()
        self.calculadora = CalculadoraImporte()

    def emitir_comprobante(self, id_atencion: int, fecha_emision: str | None = None) -> Comprobante:
        """Emite el comprobante de una atención (número correlativo C-AAAA-NNNNN).

        Detalle: la atención, las vacunas aplicadas en ella y los análisis de sus
        muestras NO rechazadas. La tarifa (Strategy) se elige según el tipo de
        atención y se aplica a todos los ítems: precio_unitario es el de lista y
        subtotal el calculado por la estrategia. Una atención no se factura dos veces.
        """
        fecha_emision = v.fecha_iso(fecha_emision or date.today().isoformat(), "fecha_emision")
        try:
            atencion = self._requerir(self.atenciones.obtener_por_id(id_atencion), "la atención")
            if self.comprobantes.existe_para_atencion(id_atencion):
                raise ReglaNegocioError(f"La atención {id_atencion} ya fue facturada.")

            tipo: TipoAtencion = self.catalogos.obtener_por_id(atencion.id_tipo_atencion, TipoAtencion)
            mascota = self._mascota_de(atencion.id_historia)
            self.calculadora.cambiar_estrategia(estrategia_para(tipo.nombre))

            comprobante = Comprobante(self._siguiente_numero(fecha_emision[:4]), mascota.id_cliente,
                                      atencion.id_clinica, fecha_emision)
            comprobante.agregar_detalle(self._detalle(
                "Atención", f"{tipo.nombre} - {mascota.nombre} ({atencion.fecha_hora[:10]})", tipo.precio,
                id_atencion=id_atencion,
            ))
            for aplicacion in self.atenciones.listar_aplicaciones(id_atencion):
                vacuna: Vacuna = self.catalogos.obtener_por_id(aplicacion.id_vacuna, Vacuna)
                comprobante.agregar_detalle(self._detalle(
                    "Vacuna", f"Vacuna {vacuna.nombre} (lote {aplicacion.lote})", vacuna.precio,
                    id_atencion=id_atencion,
                ))
            for muestra in self.derivaciones.listar_muestras_por_atencion(id_atencion):
                if muestra.estado_actual == "Rechazada":
                    continue
                analisis: TipoAnalisis = self.catalogos.obtener_por_id(muestra.id_tipo_analisis, TipoAnalisis)
                comprobante.agregar_detalle(self._detalle(
                    "Análisis", f"Análisis {analisis.nombre} (muestra {muestra.codigo})", analisis.precio,
                    id_muestra=muestra.id_muestra,
                ))

            self.comprobantes.agregar(comprobante)  # inserta cabecera y detalles
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return comprobante

    # --- Consultas ---------------------------------------------------------------------

    def obtener(self, id_comprobante: int) -> Comprobante:
        return self._requerir(self.comprobantes.obtener_por_id(id_comprobante), "el comprobante")

    def buscar_por_numero(self, numero: str) -> Comprobante | None:
        return self.comprobantes.buscar_por_numero(numero)

    def comprobantes_de_cliente(self, id_cliente: int) -> list[Comprobante]:
        return self.comprobantes.listar_por_cliente(id_cliente)

    def comprobantes_por_rango(self, desde: str, hasta: str, id_clinica: int | None = None) -> list[Comprobante]:
        return self.comprobantes.listar_por_rango(desde, hasta, id_clinica)

    def esta_facturada(self, id_atencion: int) -> bool:
        return self.comprobantes.existe_para_atencion(id_atencion)

    def atenciones_sin_facturar(self, desde: str, hasta: str, id_clinica: int | None = None) -> list[Atencion]:
        """Atenciones con fecha en [desde, hasta) que todavía no tienen comprobante."""
        return [a for a in self.atenciones.listar_por_rango(desde, hasta, id_clinica)
                if not self.comprobantes.existe_para_atencion(a.id_atencion)]

    # --- Auxiliares --------------------------------------------------------------------

    def _detalle(self, tipo_item: str, descripcion: str, precio: float, **referencias) -> DetalleComprobante:
        estrategia = self.calculadora.estrategia
        return DetalleComprobante(
            tipo_item, f"{descripcion} - {estrategia.nombre}", precio,
            subtotal=self.calculadora.calcular(precio, 1), **referencias,
        )

    def _mascota_de(self, id_historia: int) -> Mascota:
        historia = self._requerir(self.mascotas.obtener_por_id(id_historia, HistoriaClinica), "la historia clínica")
        return self.mascotas.obtener_por_id(historia.id_mascota)

    def _siguiente_numero(self, anio: str) -> str:
        """Número correlativo por año: C-AAAA-00001, C-AAAA-00002..."""
        prefijo = f"C-{anio}-"
        ultimo = self.comprobantes.ultimo_numero(prefijo)
        siguiente = int(ultimo[len(prefijo):]) + 1 if ultimo else 1
        return f"{prefijo}{siguiente:05d}"
