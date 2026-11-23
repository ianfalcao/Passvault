"""Entrada compartilhada pelo módulo Python e pelo executável portátil."""

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

from passvault import __version__, plataforma
from passvault.errors import ErroPassVault, InstanciaAberta


def autoteste() -> None:
    """Exercita dependências e transações usando exclusivamente um cofre descartável."""
    import tkinter
    from passvault.storage import Armazenamento
    from passvault.vault import Cofre, Conta

    tcl = tkinter.Tcl()
    tcl.eval("info patchlevel")
    if getattr(sys, "frozen", False):
        if not (Path(sys._MEIPASS) / "_tk_data" / "tk.tcl").is_file():
            raise RuntimeError("Recursos do Tk ausentes.")
    with tempfile.TemporaryDirectory() as pasta:
        disco = Armazenamento(Path(pasta))
        cofre = Cofre(disco)
        disco.adquirir()
        try:
            outro = Armazenamento(Path(pasta))
            try:
                outro.adquirir()
            except InstanciaAberta:
                pass
            else:
                outro.liberar()
                raise RuntimeError("Falha no lock.")
            conta = Conta("Conta de autoteste", password="fictícia")
            cofre.criar("mestra-do-autoteste")
            cofre.adicionar(conta)
            cofre.bloquear()
            cofre.desbloquear("mestra-do-autoteste")
            cofre.trocar_senha("mestra-do-autoteste", "nova-do-autoteste")
            cofre.bloquear()
            cofre.desbloquear("nova-do-autoteste")
            if cofre.obter(conta.id) != conta or disco.ler_backup(disco.criar_backup()) != disco.ler():
                raise RuntimeError("Falha na conferência.")
        finally:
            cofre.bloquear()
            disco.liberar()


def principal() -> int:
    parser = argparse.ArgumentParser(prog="PassVault")
    parser.add_argument("--version", action="store_true", help="mostrar versão")
    parser.add_argument("--self-test", action="store_true", help="executar autoteste isolado")
    parser.add_argument("--data-dir", type=Path, help="usar outra pasta de dados")
    args = parser.parse_args()
    if args.version:
        if sys.stdout:
            print(f"PassVault {__version__}")
        elif plataforma.WINDOWS:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, __version__, "PassVault", 0x40)
        return 0
    if args.self_test:
        try:
            autoteste()
        except Exception:
            if sys.stderr:
                print("O autoteste falhou.", file=sys.stderr)
            return 1
        if sys.stdout:
            print("Autoteste concluído.")
        return 0
    if args.data_dir:
        os.environ["PASSVAULT_HOME"] = str(args.data_dir.expanduser().absolute())
    try:
        from passvault.storage import configurar_log
        configurar_log()
        plataforma.preparar_windows()
        from passvault.app import principal as iniciar
        return iniciar()
    except (ImportError, OSError, ErroPassVault, RuntimeError) as exc:
        texto = str(exc) if isinstance(exc, ErroPassVault) else (
            "Falha ao iniciar. Verifique Tcl/Tk, cryptography e a pasta de dados.")
        logging.getLogger("passvault").error("Falha de inicialização.")
        plataforma.erro_fatal("PassVault", texto)
        return 1


if __name__ == "__main__":
    raise SystemExit(principal())
