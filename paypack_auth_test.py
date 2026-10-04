import os
import json
import urllib.request
import urllib.error

data = json.dumps({
    "client_id": os.environ["PAYPACK_CLIENT_ID"],
    "client_secret": os.environ["PAYPACK_CLIENT_SECRET"]
}).encode()

req = urllib.request.Request(
    "https://payments.paypack.rw/api/auth/agents/authorize",
    data=data,
    headers={
        "Accept": "application/json",
        "Content-Type": "application/json"
    },
    method="POST"
)

try:
    r = urllib.request.urlopen(req, timeout=20)
    print("STATUS:", r.status)
    print(r.read().decode())
except urllib.error.HTTPError as e:
    print("STATUS:", e.code)
    print("RESPONSE:", e.read().decode())
