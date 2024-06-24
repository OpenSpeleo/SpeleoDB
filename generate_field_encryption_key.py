import base64
import os

if __name__ == "__main__":
    print(base64.urlsafe_b64encode(os.urandom(32)).decode())  # noqa: T201
