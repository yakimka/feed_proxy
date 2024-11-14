from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from picodi import Provide, inject

from feed_proxy.configuration import read_configuration_from_folder
from feed_proxy.deps import get_yaml_dumper


@inject
def main(
    config_path: Path, yaml_dumper: Callable[[dict], str] = Provide(get_yaml_dumper)
) -> None:
    conf = read_configuration_from_folder(config_path)
    print(yaml_dumper(conf.raw))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="config")
    args = parser.parse_args()
    main(Path(args.config))
