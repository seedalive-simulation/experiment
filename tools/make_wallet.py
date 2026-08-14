"""Generate the experiment's Solana keypair. Run once; refuses to overwrite."""
import json
import os
import sys

from solders.keypair import Keypair

KEY_PATH = os.path.join(os.path.dirname(__file__), "..", "wallet", "keypair.json")
KEY_PATH = os.path.abspath(KEY_PATH)

if os.path.exists(KEY_PATH):
    print("keypair already exists, refusing to overwrite:", KEY_PATH)
    sys.exit(1)

kp = Keypair()
os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
# Standard solana-cli format: JSON array of 64 bytes
with open(KEY_PATH, "w") as f:
    json.dump(list(bytes(kp)), f)
os.chmod(KEY_PATH, 0o600)

print("address:", kp.pubkey())
