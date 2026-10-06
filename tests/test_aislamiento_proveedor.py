"""
Ningún test puede llamar al proveedor real del LLM.

La clave de Groq del `.env` queda en el entorno apenas un módulo llama a
`load_dotenv()`. Con esa clave presente, un test que no aísla una llamada al
modelo la hace de verdad: gasta la cuota diaria, depende de la red y, sin cuota,
se queda en los reintentos por 429. Así llamaban a Groq los tests de
`tests/test_api.py` desde que el router incorporó al Agente 06.

La fixture `_sin_clave_del_proveedor` de `tests/conftest.py` quita la clave en
cada test. Un test que necesita una la define él mismo, con un valor falso.
"""

import os

import pytest
from dotenv import load_dotenv

from backend.agents.base_agent import call_provider
from backend.agents.model_tasks import GROQ_MAIN

# Lo mismo que hace `backend.main` al importarse: reproduce la fuga de la clave
# sin depender de qué otros tests corrieron antes.
load_dotenv()


class TestSinClaveDelProveedor:
    def test_la_clave_real_no_esta_en_el_entorno_del_test(self):
        # Sobre un booleano: si falla, pytest no vuelca el entorno ni la clave.
        hay_clave = "GROQ_API_KEY" in os.environ
        assert hay_clave is False

    def test_una_llamada_sin_aislar_falla_antes_de_tocar_la_red(self, monkeypatch):
        monkeypatch.delenv("NEXUS_MOCK_LLM", raising=False)
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            call_provider(
                system_prompt="s", user_message="u", model=GROQ_MAIN,
                max_tokens=16, task="agente06_sintesis",
            )
