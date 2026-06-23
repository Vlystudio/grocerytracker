"""Rule-based enrichment for grocery deals: category, unit, is_grocery.

Deliberately dependency-free (just regex + keyword tables) so it runs anywhere —
including the cloud cron — with no LLM/Ollama dependency. Fast and deterministic.

`categorize()` returns (category, is_grocery). `parse_unit()` returns the unit a
price is quoted in (lb / each / bundle / null).
"""
from __future__ import annotations

import re
from typing import Optional

# Order matters: earlier categories win when keywords overlap. Each entry is a
# category label mapped to substrings matched (word-ish) against name + brand.
_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Non-grocery", [
        "tv", "television", "laptop", "tablet", "headphone", "earbud", "monitor",
        "mattress", "furniture", "sofa", "couch", "recliner", "patio", "shed",
        "tire", "vacuum", "appliance", "refrigerator", "washer", "dryer",
        "toy", "lego", "video game", "gift card", "jewelry", "watch", "apparel",
        "clothing", "shoe", "sneaker", "boot", "jacket", "tool", "drill",
        "phone", "iphone", "smartwatch", "printer", "router", "speaker",
        "grill ", "lawn", "mower", "generator", "cookware set", "luggage",
    ]),
    ("Produce", [
        "apple", "banana", "avocado", "berry", "blueberr", "strawberr", "raspberr",
        "grape", "peach", "nectarine", "plum", "melon", "watermelon", "cantaloupe",
        "lettuce", "spinach", "kale", "broccoli", "cauliflower", "carrot", "celery",
        "onion", "potato", "tomato", "cucumber", "pepper", "squash", "zucchini",
        "mushroom", "corn", "lemon", "lime", "orange", "mango", "pineapple",
        "cherr", "pear", "salad", "herb", "cilantro", "garlic", "ginger", "produce",
    ]),
    ("Meat & Seafood", [
        "chicken", "beef", "pork", "turkey", "bacon", "sausage", "steak", "ground beef",
        "ground turkey", "ribs", "ham", "hot dog", "franks", "salmon", "shrimp",
        "tilapia", "cod", "tuna", "seafood", "crab", "lobster", "wings", "deli meat",
        "ground chuck", "filet", "roast", "brisket",
    ]),
    ("Dairy & Eggs", [
        "milk", "cheese", "yogurt", "butter", "egg", "cream", "sour cream",
        "cottage", "half & half", "creamer", "string cheese", "mozzarella", "cheddar",
    ]),
    ("Bakery", [
        "bread", "bagel", "roll", "muffin", "cake", "donut", "doughnut", "pie",
        "croissant", "bun", "tortilla", "pita", "baguette", "pastry", "cookie dough",
    ]),
    ("Frozen", [
        "frozen", "ice cream", "popsicle", "frozen pizza", "waffle", "gelato",
        "sorbet", "frozen meal",
    ]),
    ("Beverages", [
        "soda", "cola", "pepsi", "coke", "juice", "water", "seltzer", "sparkling",
        "kombucha", "energy drink", "gatorade", "powerade", "coffee", "tea", "mate",
        "lemonade", "smoothie", "drink", "beer", "wine", "spirits", "cider",
    ]),
    ("Snacks", [
        "chips", "cracker", "cookie", "candy", "chocolate", "popcorn", "pretzel",
        "nuts", "trail mix", "granola bar", "snack", "salsa", "dip", "jerky",
    ]),
    ("Pantry", [
        "pasta", "rice", "cereal", "oatmeal", "sauce", "soup", "canned", "beans",
        "flour", "sugar", "olive oil", "oil", "ketchup", "mustard", "mayo",
        "peanut butter", "jam", "jelly", "honey", "syrup", "spice", "seasoning",
        "broth", "noodle", "condiment", "baking", "pancake",
    ]),
    ("Household", [
        "paper towel", "toilet paper", "napkin", "detergent", "cleaner", "trash bag",
        "foil", "plastic wrap", "dish soap", "laundry", "sponge", "bleach",
        "air freshener", "battery", "light bulb",
    ]),
    ("Health & Beauty", [
        "shampoo", "conditioner", "body wash", "soap", "lotion", "vitamin",
        "toothpaste", "toothbrush", "deodorant", "razor", "makeup", "sunscreen",
        "supplement", "pain relief", "ibuprofen", "cough", "bandage",
    ]),
    ("Baby", ["diaper", "baby formula", "baby food", "wipes", "infant"]),
    ("Pet", ["dog food", "cat food", "dog treat", "cat litter", "pet food", "pet "]),
]

# Categories that are NOT food/grocery-store staples (hidden by default).
_NON_GROCERY = {"Non-grocery"}

# Precompiled WORD-BOUNDARY patterns per category. Anchoring at \b avoids false
# positives from substrings (e.g. "egg" inside "veggie", "ham" inside "shampoo").
_CATEGORY_PATTERNS: list[tuple[str, re.Pattern]] = [
    (cat, re.compile(r"\b(?:" + "|".join(re.escape(k) for k in kws) + r")", re.I))
    for cat, kws in _CATEGORY_RULES
]


def categorize(name: Optional[str], brand: Optional[str] = None) -> tuple[str, bool]:
    """Return (category, is_grocery). Unmatched items become ('Other', True)."""
    hay = f"{name or ''} {brand or ''}"
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(hay):
            return category, category not in _NON_GROCERY
    return "Other", True


_LB_RE = re.compile(r"/\s*lb|per\s*lb|\blb\b", re.I)
_EACH_RE = re.compile(r"\bea\b|each", re.I)
_MULTI_RE = re.compile(r"\d+\s*for\s*\$", re.I)


def parse_unit(*price_texts: Optional[str]) -> Optional[str]:
    """Infer the unit a price is quoted in from messy price strings."""
    for t in price_texts:
        if not t:
            continue
        if _LB_RE.search(t):
            return "lb"
        if _MULTI_RE.search(t):
            return "each"   # "2 for $8" -> per-unit price we computed
        if _EACH_RE.search(t):
            return "each"
    return None
