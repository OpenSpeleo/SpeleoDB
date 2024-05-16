import os
import base64

if __name__ == "__main__":
    print(base64.urlsafe_b64encode(os.urandom(32)).decode())
