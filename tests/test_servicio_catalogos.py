"""Tests de ServicioCatalogos y ServicioVeterinarios."""

import pytest

from dominio import Clinica, Conservadora, Especie, Transportista, Vacuna
from dominio.excepciones import EntidadNoEncontradaError, ReglaNegocioError
from servicios import ServicioCatalogos, ServicioVeterinarios


@pytest.fixture
def cat(catalogo) -> ServicioCatalogos:
    return ServicioCatalogos()


def test_alta_y_nombre_unico(cat) -> None:
    conejo = cat.alta(Especie("Conejo"))
    assert conejo.id_especie is not None
    assert "Conejo" in [e.nombre for e in cat.listar(Especie)]
    with pytest.raises(ReglaNegocioError, match="Ya existe"):
        cat.alta(Especie("Conejo"))


def test_modificar_no_choca_consigo_mismo(cat, catalogo) -> None:
    clinica = cat.obtener(catalogo.clinica.id_clinica, Clinica)
    clinica.telefono = "351-000"
    cat.modificar(clinica)
    assert cat.obtener(clinica.id_clinica, Clinica).telefono == "351-000"
    clinica.nombre = "Norte"  # nombre de otra clínica
    with pytest.raises(ReglaNegocioError):
        cat.modificar(clinica)


def test_vacuna_unica_por_especie(cat, catalogo) -> None:
    with pytest.raises(ReglaNegocioError, match="ya tiene una vacuna"):
        cat.alta(Vacuna("antirrábica", catalogo.perro.id_especie, 100))
    cat.alta(Vacuna("Antirrábica", catalogo.gato.id_especie, 100))  # otra especie: OK
    with pytest.raises(EntidadNoEncontradaError, match="especie"):
        cat.alta(Vacuna("X", 999, 100))


def test_transportista_y_conservadora(cat, catalogo) -> None:
    cat.alta(Transportista("20111", "Carlos"))
    with pytest.raises(ReglaNegocioError, match="documento"):
        cat.alta(Transportista("20111", "Otro"))
    cat.alta(Conservadora("C-1", catalogo.clinica.id_clinica, 5, 2, 8))
    assert [c.codigo for c in cat.listar(Conservadora)] == ["C-1"]
    with pytest.raises(ReglaNegocioError, match="código"):
        cat.alta(Conservadora("C-1", catalogo.clinica.id_clinica, 5, 2, 8))
    with pytest.raises(EntidadNoEncontradaError, match="clínica"):
        cat.alta(Conservadora("C-2", 999, 5, 2, 8))


def test_baja_en_uso_se_informa(cat, catalogo) -> None:
    with pytest.raises(ReglaNegocioError, match="en uso"):
        cat.baja(catalogo.perro.id_especie, Especie)
    conejo = cat.alta(Especie("Conejo"))
    cat.baja(conejo.id_especie, Especie)
    with pytest.raises(EntidadNoEncontradaError):
        cat.obtener(conejo.id_especie, Especie)


def test_veterinarios(catalogo) -> None:
    servicio = ServicioVeterinarios()
    vet = servicio.alta("MP-9", "Eva", "Ríos", catalogo.clinica.id_clinica)
    assert vet.id_veterinario in [v.id_veterinario for v in servicio.listar_por_clinica(catalogo.clinica.id_clinica)]
    with pytest.raises(ReglaNegocioError, match="matrícula"):
        servicio.alta("MP-9", "Otra", "Persona", catalogo.clinica.id_clinica)
    with pytest.raises(EntidadNoEncontradaError, match="clínica"):
        servicio.alta("MP-10", "Otra", "Persona", 999)
    servicio.baja(vet.id_veterinario)
    assert servicio.obtener(vet.id_veterinario).activo is False
    with pytest.raises(ReglaNegocioError):
        servicio.baja(vet.id_veterinario)
