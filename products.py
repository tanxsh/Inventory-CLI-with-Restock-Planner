#!/usr/bin/env python3
"""Product inventory CLI. Storage layer (step 4): load and save only."""

import json
import os
import re
import shutil
import tempfile

PRICE_PATTERN = re.compile(r"[0-9]+\.[0-9]{2}")  # used with fullmatch


class StoreError(Exception):
    """Problem with the data file (unreadable, invalid, or unwritable).

    The CLI will turn this into exit code 1.
    """


def empty_store():
    return {"next_id": 1, "products": []}


def is_int(value):
    # bool is a subclass of int in Python, so exclude it explicitly
    return isinstance(value, int) and not isinstance(value, bool)


def validate_store(data):
    """Raise StoreError unless data matches the required file schema."""
    if not isinstance(data, dict):
        raise StoreError("data file must contain a JSON object")
    if "next_id" not in data or "products" not in data:
        raise StoreError("data file must have 'next_id' and 'products'")

    next_id = data["next_id"]
    if not is_int(next_id) or next_id < 1:
        raise StoreError("'next_id' must be a positive integer")

    products = data["products"]
    if not isinstance(products, list):
        raise StoreError("'products' must be a list")

    seen_ids = set()
    for item in products:
        if not isinstance(item, dict):
            raise StoreError("each product must be a JSON object")
        for key in ("id", "name", "price", "quantity"):
            if key not in item:
                raise StoreError(f"product is missing '{key}'")

        pid = item["id"]
        if not is_int(pid) or pid < 1:
            raise StoreError("product 'id' must be a positive integer")
        if pid in seen_ids:
            raise StoreError(f"duplicate product id {pid}")
        seen_ids.add(pid)

        name = item["name"]
        if not isinstance(name, str) or not name.strip():
            raise StoreError(f"product {pid} has an invalid name")
        price = item["price"]
        if not isinstance(price, str) or not PRICE_PATTERN.fullmatch(price):
            raise StoreError(f"product {pid} has an invalid price")
        quantity = item["quantity"]
        if not is_int(quantity) or quantity < 0:
            raise StoreError(f"product {pid} has an invalid quantity")

    if seen_ids and next_id <= max(seen_ids):
        raise StoreError("'next_id' must be greater than every product id")


def load_store(path):
    """Read and validate the data file.

    A missing file is an empty store (and is NOT created here).
    Anything else wrong raises StoreError and leaves the file untouched.
    """
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return empty_store()
    except OSError as e:
        raise StoreError(f"cannot read {path}: {e.strerror or e}")

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise StoreError(f"{path} is empty or not valid UTF-8 JSON")

    validate_store(data)
    return data


def save_store(path, data):
    """Write data atomically: temp file in the same folder, then rename.

    If anything fails, the original file is left as it was.
    Missing parent folders are not created.
    """
    folder = os.path.dirname(os.path.abspath(path))
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=folder, prefix=".products-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(path):
            shutil.copymode(path, tmp_path)
        os.replace(tmp_path, path)
    except OSError as e:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise StoreError(f"cannot write {path}: {e.strerror or e}")
