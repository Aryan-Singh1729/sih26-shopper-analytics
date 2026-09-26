from __future__ import annotations

import argparse
import logging

from .app import EntranceCounterApp
from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline anonymous entrance counter")
    parser.add_argument("--config", required=True, help="Path to JSON configuration")
    parser.add_argument("--check-config", action="store_true", help="Validate configuration and exit")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.check_config:
        print("configuration valid")
        return
    logging.basicConfig(
        level=getattr(logging, str(config.runtime.get("log_level", "INFO")).upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = EntranceCounterApp(config)
    app.install_signal_handlers()
    try:
        app.run()
    finally:
        app.close()


if __name__ == "__main__":
    main()

