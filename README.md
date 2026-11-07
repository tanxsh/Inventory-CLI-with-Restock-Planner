# Inventory CLI

Submitted by: Tanish Jagadheshan

A small command-line tool for tracking a store's products. It runs on Python 3 and uses only the standard library. Products are saved in a local JSON file.


## Usage

```
python3 products.py [--file PATH] COMMAND [OPTIONS]
```

`--file PATH` picks the data file. It has to come before the command. The default is `products.json` in the folder you run the command from.

| Command | What it does |
|---|---|
| `add --name NAME --price PRICE --quantity QTY` | Creates a product and prints it |
| `list` | Prints all products, sorted by ID |
| `get ID` | Prints one product |
| `update ID [--name NAME] [--price PRICE] [--quantity QTY]` | Changes the fields you give (at least one) and prints the product |
| `delete ID --yes` | Deletes a product and prints `{"deleted_id": ID}` |
| `restock --target N` | My custom feature, explained below |

Run `python3 products.py --help` or `python3 products.py COMMAND --help` for details.

Rules for values:
- **name**: can't be blank. Spaces at the start and end are trimmed.
- **price**: digits with an optional decimal point and one or two decimals (`0`, `4.5`, `4.50`). It's stored and printed with exactly two decimals, like `"4.50"`.
- **quantity**: a whole number, zero or higher.
- **ID**: a positive whole number. IDs start at 1 and are never reused after a delete.

Exit codes: `0` success, `1` product not found or a problem with the data file, `2` bad command or bad value. Errors are printed to stderr.

## Custom feature: restock

### Who it helps and why
A shop owner who wants to know what to order and how much money it will take. You pick the minimum stock you want for every product, and `restock` shows which products are short, how many units to buy, what each costs, and the total. It's more useful than a plain low-stock list because it gives you the budget too.

### Syntax
```
python3 products.py [--file PATH] restock --target N
```

### Input
`--target N` is required. It's the quantity you want every product to have. It must be a whole number, zero or higher. A negative number, a decimal, text, or leaving it out gives an error and exit code 2.

### How it works
For every product with a quantity below N:
- units needed = N minus the current quantity
- cost = units needed × price

The total is the sum of all the costs. Money is calculated with Python's Decimal, so there are no rounding issues. Products are listed by ID. The command only reads the file, so it never creates or changes it.

### Output
A JSON object with the target, the list of products to restock, and the total cost.

### Example you can run
```bash
python3 products.py --file demo.json add --name "Notebook" --price 4.50 --quantity 12
python3 products.py --file demo.json add --name "Pencil" --price 1.25 --quantity 5
python3 products.py --file demo.json add --name "Stapler" --price 8 --quantity 0
python3 products.py --file demo.json add --name "Marker" --price 2.10 --quantity 30
python3 products.py --file demo.json restock --target 20
```

The last command prints this (shown on several lines here; the tool prints it on one line):

```json
{
  "target": 20,
  "items": [
    {"id": 1, "name": "Notebook", "price": "4.50", "quantity": 12, "needed": 8, "cost": "36.00"},
    {"id": 2, "name": "Pencil", "price": "1.25", "quantity": 5, "needed": 15, "cost": "18.75"},
    {"id": 3, "name": "Stapler", "price": "8.00", "quantity": 0, "needed": 20, "cost": "160.00"}
  ],
  "total_cost": "214.75"
}
```

Marker has 30, which is above the target, so it isn't listed.

### Edge case: Nothing needs restocking
If every product is at or above the target, or the file is empty or doesn't exist yet, you get an empty list and a zero total, with exit code 0:

```bash
python3 products.py --file demo.json restock --target 0
```
```json
{"target": 0, "items": [], "total_cost": "0.00"}
```

An invalid target, such as `restock --target -1`, exits with code 2 and prints nothing to stdout.

## Data file
The tool saves UTF-8 JSON like this:

```json
{
  "next_id": 3,
  "products": [
    {"id": 1, "name": "Notebook", "price": "4.50", "quantity": 12}
  ]
}
```

- A missing file counts as an empty store. Only the first successful `add` creates it.
- If the file is empty, broken JSON, or doesn't match this layout, the tool reports an error and leaves the file alone.
- Changes are written to a temporary file first and then swapped in, so a failed write can't damage your data.
- A failed command never changes the file or uses up an ID.
