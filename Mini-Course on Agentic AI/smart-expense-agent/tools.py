import json
from pathlib import Path
from datetime import datetime

DATA_FILE = Path(__file__).parent / "expenses.json"

def load_expenses():
    if not DATA_FILE.exists():
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []

def save_expenses(expenses):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(expenses, file, indent=4)

def add_expense(amount: float, category: str):
    if amount <= 0:
        return {
            "success": False,
            "message": "Amount must be greater than zero."
        }

    if amount > 1000000:
        return {
            "success": False,
            "message": "Amount exceeds the allowed limit."
        }

    category = category.strip()

    if not category:
        return {
            "success": False,
            "message": "Category cannot be empty."
        }

    expenses = load_expenses()

    expense = {
        "id": len(expenses) + 1,
        "amount": round(amount, 2),
        "category": category,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    expenses.append(expense)
    save_expenses(expenses)

    return {
        "success": True,
        "message": "Expense added successfully.",
        "expense": expense
    }

def list_expenses():
    expenses = load_expenses()

    return {
        "count": len(expenses),
        "expenses": expenses
    }

def get_total_expenses():
    expenses = load_expenses()

    total = sum(item["amount"] for item in expenses)

    return {
        "total": round(total, 2),
        "count": len(expenses)
    }

def get_expenses_by_category(category: str):
    expenses = load_expenses()

    matched = [
        item for item in expenses
        if item["category"].lower() == category.strip().lower()
    ]

    total = sum(item["amount"] for item in matched)

    return {
        "category": category,
        "total": round(total, 2),
        "count": len(matched),
        "expenses": matched
    }

if __name__ == "__main__":
    print(add_expense(250, "Food"))
    print(add_expense(500, "Travel"))
    print(get_total_expenses())
    print(list_expenses())
