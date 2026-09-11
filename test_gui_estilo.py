import importlib

modulo = importlib.import_module("organizador_arquivos")


def test_estilo_botao_acao_define_cor_do_texto():
    assert hasattr(modulo, "COR_TEXTO_BOTAO_ACAO")
    assert modulo.COR_TEXTO_BOTAO_ACAO == "#111827"
