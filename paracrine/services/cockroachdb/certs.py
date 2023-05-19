from pathlib import Path

from ...helpers.config import config_path, data_path
from ...helpers.fs import build_with_command, download_and_unpack, make_directory
from ...helpers.network import wireguard_ips
from .common import binary_path, cockroach_hash, cockroach_url

options = {}


def local():
    store_path = Path(data_path()).joinpath("cockroach")
    make_directory(store_path)
    download_and_unpack(
        cockroach_url,
        cockroach_hash,
        dir_name=store_path,
        compressed_root=data_path(),
    )
    cockroach = store_path.joinpath(binary_path)
    certs_dir = Path(config_path()).joinpath("cockroach-certs")
    make_directory(certs_dir)
    build_with_command(
        store_path.joinpath("ca.key"),
        f"{cockroach} cert create-ca --certs-dir={certs_dir} --ca-key={store_path}/ca.key --overwrite --allow-ca-key-reuse",
    )
    build_with_command(
        certs_dir.joinpath("client.root.key"),
        f"{cockroach} cert create-client root --certs-dir={certs_dir} --ca-key={store_path}/ca.key --overwrite",
        deps=[f"{store_path}/ca.key"],
    )

    for ip in wireguard_ips().values():
        crt_path = certs_dir.joinpath(f"{ip}.crt")
        build_with_command(
            crt_path,
            f"{cockroach} cert create-node localhost {ip} --certs-dir={certs_dir} --ca-key={store_path}/ca.key --overwrite && mv {certs_dir.joinpath('node.crt')} {crt_path} && mv {certs_dir.joinpath('node.key')} {crt_path.with_suffix('.key')}",
            deps=[f"{store_path}/ca.key"],
        )
