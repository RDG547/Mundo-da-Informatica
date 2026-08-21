"""Sincroniza os providers de datasheets configurados."""

from jobs.sync_configured_sources import run


if __name__ == "__main__":
    print(run({"Feed licenciado"}))
