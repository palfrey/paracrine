from .login import ssh

if __name__ == "__main__":
    ssh("apt-get install -y python3 sudo", as_root=True)
