"""Sessões e transações com credenciais sintéticas."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from passvault.crypto import ler_envelope
from passvault.errors import (DadosInvalidos, ErroArmazenamento, InvalidMasterPassword,
                              SessaoBloqueada)
from passvault.storage import Armazenamento
from passvault.vault import Cofre, Conta


class Sessao(unittest.TestCase):
    def setUp(self) -> None:
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.d = Armazenamento(Path(pasta.name) / "cofre")
        self.v = Cofre(self.d)
        self.v.criar("mestra-fake")
        self.c = Conta("Café", "USUÁRIO", "SENHA-FAKE", "https://exemplo.invalid", "nota privada",
                       ["Pessoal", "pessoal", "café"], {"campo": "extra"})

    def test_crud_busca_e_serializacao(self) -> None:
        self.v.adicionar(self.c)
        self.v.bloquear()
        self.v.desbloquear("mestra-fake")
        self.assertEqual(self.v.obter(self.c.id), self.c)
        self.assertEqual(self.c.tags, ["Pessoal", "café"])
        for termo in ("CAFE", "usuario", "pessoal", ".invalid"):
            self.assertEqual(self.v.buscar(termo), [self.c])
        for termo in ("SENHA-FAKE", "nota privada"):
            self.assertFalse(self.v.buscar(termo))
        self.v.editar(self.c.id, service="Outro")
        self.assertEqual(self.v.obter(self.c.id).extra, self.c.extra)
        self.v.excluir(self.c.id)
        self.assertEqual(self.v.buscar(""), [])

    def test_troca_de_senha(self) -> None:
        self.v.adicionar(self.c)
        anterior = self.d.ler()
        with self.assertRaises(InvalidMasterPassword):
            self.v.trocar_senha("errada", "nova-fake")
        self.assertEqual(anterior, self.d.ler())
        self.v.trocar_senha("mestra-fake", "nova-fake")
        self.assertNotEqual(ler_envelope(anterior).parametros,
                            ler_envelope(self.d.ler()).parametros)
        self.v.bloquear()
        atual = self.d.ler()
        with self.assertRaises(InvalidMasterPassword):
            self.v.desbloquear("mestra-fake")
        self.assertEqual(atual, self.d.ler())
        self.v.desbloquear("nova-fake")
        self.assertEqual(self.v.obter(self.c.id), self.c)

    def test_lock_sobrescreve_chave(self) -> None:
        chave = self.v._chave
        self.v.bloquear()
        self.assertEqual(chave, bytearray(32))
        with self.assertRaises(SessaoBloqueada):
            self.v.adicionar(self.c)

    def test_falha_de_gravacao_preserva_sessao(self) -> None:
        with patch.object(self.d, "gravar", side_effect=ErroArmazenamento):
            with self.assertRaises(ErroArmazenamento):
                self.v.adicionar(self.c)
            with self.assertRaises(ErroArmazenamento):
                self.v.trocar_senha("mestra-fake", "nova-fake")
        self.assertEqual(self.v.buscar(""), [])
        self.v.adicionar(self.c)
        self.v.desbloquear("mestra-fake")

    def test_restauracao_valida_antes_de_confirmar(self) -> None:
        self.v.adicionar(self.c)
        dados = self.d.ler_backup(self.d.criar_backup())
        self.v.excluir(self.c.id)
        anterior = self.d.ler()
        with self.assertRaises(InvalidMasterPassword):
            self.v.restaurar(dados, "errada", lambda: self.fail("Confirmação prematura"))
        self.assertFalse(self.v.restaurar(dados, "mestra-fake", lambda: False))
        self.assertEqual(self.d.ler(), anterior)
        self.assertTrue(self.v.restaurar(dados, "mestra-fake", lambda: True))
        self.assertEqual(self.v.buscar(""), [self.c])
        self.assertEqual(self.d.anterior.read_bytes(), anterior)
        self.assertEqual(self.d.ler_backup(self.d.listar()[0].caminho), anterior)

    def test_validacao(self) -> None:
        with self.assertRaises(DadosInvalidos):
            Conta(" ")
        with self.assertRaises(DadosInvalidos):
            self.v.trocar_senha("mestra-fake", "curta")
