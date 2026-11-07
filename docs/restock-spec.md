# restock command

## What it's for
A shop owner wants to know what to reorder and how much money it will take to get every product up to a minimum stock level.

## How to run it
```
python3 products.py [--file PATH] restock --target N
```

## Input
`--target N` is required. N has to be a whole number, zero or higher. Same rule as quantity. If it's negative, a decimal, text, or missing, the command prints an error and exits with code 2.

## How it works
- Look at every product with a quantity below N.
- Units needed = N minus the current quantity.
- Cost = units needed times price. I use Decimal so the money math stays exact.
- Results are listed by ID.
- It only reads. It never creates or changes the data file.

## What it prints (exit code 0)
```json
{
  "target": 20,
  "items": [
    {"id": 1, "name": "Notebook", "price": "4.50", "quantity": 12, "needed": 8, "cost": "36.00"}
  ],
  "total_cost": "36.00"
}
```

## Edge case
If nothing is below the target, or the store is empty, or the file doesn't exist yet, it prints an empty `items` list and a `total_cost` of `"0.00"`, with exit code 0.
