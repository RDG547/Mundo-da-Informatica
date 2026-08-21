"""Sincroniza o feed HP autorizado configurado."""

from jobs.sync_configured_sources import run


if __name__ == "__main__":
    print(run({"HP"}))
