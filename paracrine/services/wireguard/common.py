from ...helpers.config import config_path

wg_config = "/etc/wireguard"
private_key_file = f"{wg_config}/privatekey"
public_key_file = f"{wg_config}/publickey"


def public_key_path(name: str) -> str:
    return config_path() + f"/wireguard-public-{name}.key"
