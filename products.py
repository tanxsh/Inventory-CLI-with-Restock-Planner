#!/usr/bin/env python3
"""Product inventory CLI.

Exit codes: 0 success, 1 not found / bad stored data / file error,
2 bad command syntax or invalid input values.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from decimal import Decimal

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


# ---------------------------------------------------------------------------
# Input validators. Used as argparse `type=` functions, so a bad value makes
# argparse print the message to stderr and exit with code 2.
# Regexes use [0-9] and fullmatch so other-language digits and a trailing
# newline are rejected.
# ---------------------------------------------------------------------------

PRICE_INPUT = re.compile(r"[0-9]+(\.[0-9]{1,2})?")
WHOLE_NUMBER = re.compile(r"[0-9]+")


def valid_name(text):
    name = text.strip()
    if not name:
        raise argparse.ArgumentTypeError("name must contain a non-space character")
    return name


def valid_price(text):
    if not PRICE_INPUT.fullmatch(text):
        raise argparse.ArgumentTypeError(
            f"invalid price {text!r}: use digits with up to two decimal places, e.g. 4.50"
        )
    # .2f formatting is exact for Decimal and, unlike quantize, cannot
    # overflow the decimal context on absurdly long inputs
    return f"{Decimal(text):.2f}"


def whole_number(text, label):
    if not WHOLE_NUMBER.fullmatch(text):
        raise argparse.ArgumentTypeError(
            f"invalid {label} {text!r}: must be a whole number, zero or higher"
        )
    try:
        return int(text)
    except ValueError:  # absurdly long digit strings
        raise argparse.ArgumentTypeError(f"{label} {text[:20]!r}... is too large")


def valid_quantity(text):
    return whole_number(text, "quantity")


def valid_target(text):
    return whole_number(text, "target")


def valid_id(text):
    number = whole_number(text, "id")
    if number < 1:
        raise argparse.ArgumentTypeError(f"invalid id {text!r}: must be a positive integer")
    return number


# ---------------------------------------------------------------------------
# Command line parser
# ---------------------------------------------------------------------------

def build_parser():
    # allow_abbrev=False so "--qty" is not silently accepted as "--quantity"
    parser = argparse.ArgumentParser(
        prog="products.py",
        description="Manage a small store's product inventory in a JSON file.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--file", default="products.json", metavar="PATH",
        help="JSON data file (default: products.json); must come before the command",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    def add_command(name, help_text):
        return sub.add_parser(name, help=help_text, description=help_text, allow_abbrev=False)

    p_add = add_command("add", "create a product")
    p_add.add_argument("--name", required=True, type=valid_name)
    p_add.add_argument("--price", required=True, type=valid_price)
    p_add.add_argument("--quantity", required=True, type=valid_quantity)

    add_command("list", "print all products as a JSON array")

    p_get = add_command("get", "print one product by ID")
    p_get.add_argument("id", type=valid_id)

    p_update = add_command("update", "change fields of a product (at least one required)")
    p_update.add_argument("id", type=valid_id)
    p_update.add_argument("--name", type=valid_name)
    p_update.add_argument("--price", type=valid_price)
    p_update.add_argument("--quantity", type=valid_quantity)

    p_delete = add_command("delete", "delete a product by ID (requires --yes)")
    p_delete.add_argument("id", type=valid_id)
    p_delete.add_argument("--yes", action="store_true", help="confirm the deletion")

    p_restock = add_command(
        "restock", "list products below a target quantity and the cost to restock them"
    )
    p_restock.add_argument(
        "--target", required=True, type=valid_target,
        help="minimum quantity wanted for every product",
    )

    return parser, {"update": p_update, "delete": p_delete}


def check_arguments(args, subparsers):
    """Rules argparse can't express on its own. Exits with code 2 on failure."""
    if args.command == "update" and all(
        getattr(args, field) is None for field in ("name", "price", "quantity")
    ):
        subparsers["update"].error("give at least one of --name, --price, --quantity")
    if args.command == "delete" and not args.yes:
        subparsers["delete"].error("deletion must be confirmed with --yes")


# ---------------------------------------------------------------------------
# Commands. Each handler returns the JSON-serializable result; main() prints
# it. Mutating handlers save before returning, so a later invocation sees the
# change and a failed run never reaches save_store.
# ---------------------------------------------------------------------------

def require_product(products, product_id):
    for product in products:
        if product["id"] == product_id:
            return product
    raise StoreError(f"product with id {product_id} not found")


def sorted_products(products):
    return sorted(products, key=lambda product: product["id"])


def cmd_add(args):
    store = load_store(args.file)
    product = {
        "id": store["next_id"],
        "name": args.name,
        "price": args.price,
        "quantity": args.quantity,
    }
    store["products"].append(product)
    store["next_id"] += 1
    save_store(args.file, store)
    return product


def cmd_list(args):
    store = load_store(args.file)
    return sorted_products(store["products"])


def cmd_get(args):
    store = load_store(args.file)
    return require_product(store["products"], args.id)


def cmd_update(args):
    store = load_store(args.file)
    product = require_product(store["products"], args.id)
    for field in ("name", "price", "quantity"):
        value = getattr(args, field)
        if value is not None:
            product[field] = value
    save_store(args.file, store)
    return product


def cmd_delete(args):
    store = load_store(args.file)
    product = require_product(store["products"], args.id)
    store["products"].remove(product)
    save_store(args.file, store)
    return {"deleted_id": product["id"]}


def cmd_restock(args):
    store = load_store(args.file)
    items = []
    total_cost = Decimal("0")
    for product in sorted_products(store["products"]):
        if product["quantity"] >= args.target:
            continue
        needed = args.target - product["quantity"]
        cost = Decimal(product["price"]) * needed
        total_cost += cost
        items.append({
            "id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "quantity": product["quantity"],
            "needed": needed,
            "cost": f"{cost:.2f}",
        })
    return {"target": args.target, "items": items, "total_cost": f"{total_cost:.2f}"}


COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "get": cmd_get,
    "update": cmd_update,
    "delete": cmd_delete,
    "restock": cmd_restock,
}


def main(argv=None):
    parser, subparsers = build_parser()
    args = parser.parse_args(argv)  # --help, syntax errors and bad values end here
    check_arguments(args, subparsers)

    handler = COMMANDS[args.command]
    try:
        result = handler(args)
    except StoreError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
