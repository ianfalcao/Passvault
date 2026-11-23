"""Executa a interface gráfica."""

try:
    from .app import principal
except ModuleNotFoundError as erro:
    if erro.name in {"tkinter", "_tkinter"}:
        raise SystemExit("Instale o suporte ao tkinter fornecido pela sua distribuição.") from None
    if erro.name and erro.name.startswith("cryptography"):
        raise SystemExit("Instale cryptography pelos pacotes da distribuição.") from None
    raise

if __name__ == "__main__":
    raise SystemExit(principal())
