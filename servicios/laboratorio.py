"""Casos de uso del laboratorio: recepción de remitos y carga de resultados."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from dominio import (
    Conservadora,
    Muestra,
    PrecintoSanitario,
    Recepcion,
    RemitoBiologico,
    ResultadoAnalisis,
    TipoAnalisis,
)
from dominio import validaciones as v
from dominio.excepciones import PrecintoRotoError
from persistencia.repositorios import (
    RepositorioCatalogos,
    RepositorioDerivaciones,
    RepositorioEnvios,
    RepositorioResultados,
)
from servicios.base import ServicioBase, ahora

ESTADOS_FINALES = ("Analizada", "Rechazada")


@dataclass
class ResultadoRecepcion:
    recepcion: Recepcion
    aceptadas: list[Muestra] = field(default_factory=list)
    rechazadas: list[Muestra] = field(default_factory=list)  # el motivo queda en muestra.ultimo_cambio


class ServicioLaboratorio(ServicioBase):
    def __init__(
        self,
        repo_envios: RepositorioEnvios | None = None,
        repo_derivaciones: RepositorioDerivaciones | None = None,
        repo_resultados: RepositorioResultados | None = None,
        repo_catalogos: RepositorioCatalogos | None = None,
    ) -> None:
        self.envios = repo_envios or RepositorioEnvios()
        self.derivaciones = repo_derivaciones or RepositorioDerivaciones()
        self.resultados = repo_resultados or RepositorioResultados()
        self.catalogos = repo_catalogos or RepositorioCatalogos()

    # --- 4. Recepción ------------------------------------------------------------------

    def recibir(
        self,
        id_remito: int,
        receptor: str,
        precinto_intacto: bool,
        temperatura_llegada: float | None,
        *,
        fecha_hora: str | None = None,
        observaciones: str | None = None,
    ) -> ResultadoRecepcion:
        """Recibe un remito En tránsito y verifica el precinto (regla 2).

        - Precinto roto: remito Rechazado, precinto Roto y TODAS las muestras Rechazada.
        - Precinto intacto: remito Recibido y muestras Recibida, salvo las que
          tengan la viabilidad vencida (horas desde la extracción > horas_viabilidad)
          o lleguen con temperatura fuera del rango de su análisis, que se rechazan
          individualmente con el motivo.
        En ambos casos la conservadora vuelve a Disponible y se actualizan las órdenes.
        """
        precinto_intacto = v.booleano(precinto_intacto, "precinto_intacto")
        fecha_hora = v.fecha_hora_iso(fecha_hora or ahora(), "fecha_hora")
        temperatura_llegada = v.numero_opcional(temperatura_llegada, "temperatura_llegada")
        try:
            remito: RemitoBiologico = self._requerir(self.envios.obtener_por_id(id_remito), "el remito")
            remito.recibir(precinto_intacto)  # State: solo desde En tránsito
            self.envios.modificar(remito)

            precinto: PrecintoSanitario = self._requerir(
                self.envios.obtener_precinto_por_remito(id_remito), "el precinto del remito"
            )
            precinto.estado = "Intacto" if precinto_intacto else "Roto"
            self.envios.modificar(precinto)

            recepcion = Recepcion(id_remito, fecha_hora, receptor, precinto.estado, aceptada=precinto_intacto,
                                  temperatura_llegada=temperatura_llegada, observaciones=observaciones)
            self.envios.agregar(recepcion)

            resultado = ResultadoRecepcion(recepcion)
            muestras = self.derivaciones.listar_muestras_por_remito(id_remito)
            for muestra in muestras:
                muestra.recibir(precinto_intacto, recepcion.receptor, fecha_hora)  # State
                if precinto_intacto:
                    motivo = self._motivo_rechazo(muestra, fecha_hora, temperatura_llegada)
                    if motivo:
                        muestra.rechazar(motivo, recepcion.receptor, fecha_hora)  # State
                self.derivaciones.modificar(muestra)
                (resultado.aceptadas if muestra.estado_actual == "Recibida" else resultado.rechazadas).append(muestra)

            conservadora: Conservadora = self.envios.obtener_por_id(remito.id_conservadora, Conservadora)
            conservadora.estado = "Disponible"
            self.envios.modificar(conservadora)

            self._actualizar_ordenes({m.id_orden for m in muestras})
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return resultado

    # --- 5. Resultados -----------------------------------------------------------------

    def registrar_resultado(
        self,
        id_muestra: int,
        bioquimico: str,
        valores: str,
        conclusion: str | None = None,
        *,
        fecha_hora: str | None = None,
    ) -> ResultadoAnalisis:
        """Carga el resultado de una muestra Recibida (→ Analizada).

        Si con esto todas las muestras de la orden quedan Analizada o Rechazada,
        la orden pasa a Finalizada. Una muestra de un remito con precinto roto
        lanza PrecintoRotoError; cualquier otro estado, TransicionInvalidaError.
        """
        fecha_hora = v.fecha_hora_iso(fecha_hora or ahora(), "fecha_hora")
        try:
            muestra: Muestra = self._requerir(self.derivaciones.obtener_por_id(id_muestra, Muestra), "la muestra")
            if muestra.estado_actual == "Rechazada" and self._precinto_roto(muestra):
                raise PrecintoRotoError(
                    f"La muestra {muestra.codigo} llegó con el precinto roto: no se pueden cargar resultados."
                )
            resultado = ResultadoAnalisis(muestra.id_muestra, fecha_hora, bioquimico, valores, conclusion)
            muestra.registrar_resultado(resultado.bioquimico, fecha_hora)  # State: solo desde Recibida
            self.derivaciones.modificar(muestra)
            self.resultados.agregar(resultado)
            self._actualizar_ordenes({muestra.id_orden})
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return resultado

    # --- Consultas ---------------------------------------------------------------------

    def obtener_recepcion(self, id_remito: int) -> Recepcion | None:
        return self.envios.obtener_recepcion_por_remito(id_remito)

    def obtener_resultado(self, id_muestra: int) -> ResultadoAnalisis | None:
        return self.resultados.obtener_por_muestra(id_muestra)

    def resultados_de_orden(self, id_orden: int) -> list[ResultadoAnalisis]:
        return self.resultados.listar_por_orden(id_orden)

    def remitos_en_transito(self) -> list[RemitoBiologico]:
        return self.envios.listar_remitos_por_estado("En tránsito")

    def muestras_para_analizar(self) -> list[Muestra]:
        return self.derivaciones.listar_muestras_por_estado("Recibida")

    def resultados_recientes(self, limite: int = 15) -> list[tuple[Muestra, ResultadoAnalisis]]:
        """Últimos resultados cargados (más reciente primero), con su muestra."""
        pares = [(m, self.resultados.obtener_por_muestra(m.id_muestra))
                 for m in self.derivaciones.listar_muestras_por_estado("Analizada")]
        pares = [(m, r) for m, r in pares if r is not None]
        return sorted(pares, key=lambda par: par[1].fecha_hora, reverse=True)[:limite]

    # --- Auxiliares --------------------------------------------------------------------

    def _motivo_rechazo(self, muestra: Muestra, fecha_hora: str, temperatura: float | None) -> str | None:
        tipo: TipoAnalisis = self.catalogos.obtener_por_id(muestra.id_tipo_analisis, TipoAnalisis)
        if not muestra.es_viable(fecha_hora, tipo):
            horas = (v.a_fecha_hora(fecha_hora) - v.a_fecha_hora(muestra.fecha_hora_extraccion)).total_seconds() / 3600
            return (f"Viabilidad vencida: {horas:.1f} h desde la extracción "
                    f"(máximo {tipo.horas_viabilidad} h para {tipo.nombre})")
        if temperatura is not None and not tipo.admite_temperatura(temperatura):
            return (f"Temperatura de llegada {temperatura:g} °C fuera de rango para {tipo.nombre} "
                    f"({tipo.temp_min:g} a {tipo.temp_max:g} °C)")
        return None

    def _precinto_roto(self, muestra: Muestra) -> bool:
        if muestra.id_remito is None:
            return False
        precinto = self.envios.obtener_precinto_por_remito(muestra.id_remito)
        return precinto is not None and precinto.roto

    def _actualizar_ordenes(self, ids_ordenes: Iterable[int]) -> None:
        """Pasa a Finalizada las órdenes cuyas muestras terminaron (Analizada o Rechazada)."""
        for id_orden in ids_ordenes:
            orden = self.derivaciones.obtener_por_id(id_orden)
            if orden.estado in ("Finalizada", "Anulada"):
                continue
            muestras = self.derivaciones.listar_muestras_por_orden(id_orden)
            if muestras and all(m.estado_actual in ESTADOS_FINALES for m in muestras):
                orden.estado = "Finalizada"
                self.derivaciones.modificar(orden)
