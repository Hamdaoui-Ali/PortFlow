"""Run the PortFlow loopback API for local data entry and snapshot refresh."""

import os
from pathlib import Path

from portflow.db.connection import get_database_url
from portflow.local_api import LocalApiConfig, create_server


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    database_url = get_database_url()
    port = int(os.environ.get("PORTFLOW_LOCAL_API_PORT", "8000"))
    server = create_server(
        LocalApiConfig(
            database_url=database_url,
            output_dir=repository_root / "web" / "public" / "data",
            port=port,
            stream_state_path=repository_root / "data" / "bronze-stream" / ".stream-state.sqlite3",
        )
    )
    actual_port = server.server_address[1]
    print(f"PortFlow local API listening on 127.0.0.1:{actual_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
