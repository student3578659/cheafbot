from __future__ import annotations

from dataclasses import dataclass


AVAILABLE_INGREDIENTS = [
    "курка",
    "яловичина",
    "риба",
    "рис",
    "макарони",
    "картопля",
    "морква",
    "цибуля",
    "часник",
    "помідори",
    "броколі",
    "перець",
    "кабачок",
    "гриби",
    "сир",
    "пармезан",
    "молоко",
    "яйця",
    "олія",
    "сіль",
    "квасоля",
    "нут",
    "гречка",
    "шпинат",
    "лимон",
]

MEAT_AND_FISH = {"курка", "яловичина", "риба"}
GLUTEN_INGREDIENTS = {"макарони"}


@dataclass(frozen=True)
class Recipe:
    name: str
    time: str
    description: str
    ingredients: tuple[str, ...]
    steps: tuple[str, ...]
    vegetarian: bool
    gluten_free: bool
    image_url: str


RECIPE_BOOK = [
    Recipe(
        name="Курка з рисом і броколі",
        time="35 хв",
        description="Поживна вечеря з м'якою куркою, гарніром із рису та зеленими овочами.",
        ingredients=("курка", "рис", "броколі", "часник", "олія", "сіль"),
        steps=(
            "Відваріть рис до готовності.",
            "Обсмажте курку з часником до золотистої скоринки.",
            "Додайте броколі, трохи води та протушкуйте 7-10 хвилин.",
        ),
        vegetarian=False,
        gluten_free=True,
        image_url="https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?auto=format&fit=crop&w=900&q=80",
    ),
    Recipe(
        name="Овочеве рагу з нутом",
        time="30 хв",
        description="Яскрава вегетаріанська страва з овочами, нутом і легкою томатною основою.",
        ingredients=("нут", "помідори", "морква", "цибуля", "кабачок", "часник", "олія", "сіль"),
        steps=(
            "Обсмажте цибулю, моркву й часник.",
            "Додайте кабачок, помідори та нут.",
            "Тушкуйте до м'якості овочів і подавайте гарячим.",
        ),
        vegetarian=True,
        gluten_free=True,
        image_url="https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=80",
    ),
    Recipe(
        name="Паста з грибами та пармезаном",
        time="25 хв",
        description="Швидка паста з вершковими нотами, грибами та солоним пармезаном.",
        ingredients=("макарони", "гриби", "пармезан", "молоко", "часник", "олія", "сіль"),
        steps=(
            "Відваріть макарони до стану al dente.",
            "Обсмажте гриби з часником.",
            "Додайте молоко, пармезан і змішайте з пастою.",
        ),
        vegetarian=True,
        gluten_free=False,
        image_url="https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=900&q=80",
    ),
    Recipe(
        name="Риба з картоплею та лимоном",
        time="40 хв",
        description="Легка запечена страва з лимонною свіжістю та простим картопляним гарніром.",
        ingredients=("риба", "картопля", "лимон", "часник", "олія", "сіль"),
        steps=(
            "Наріжте картоплю часточками та змастіть олією.",
            "Викладіть рибу з лимоном і часником.",
            "Запікайте до готовності картоплі та риби.",
        ),
        vegetarian=False,
        gluten_free=True,
        image_url="https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=900&q=80",
    ),
    Recipe(
        name="Гречка з грибами та шпинатом",
        time="25 хв",
        description="Ситна безглютенова каша з грибами, зеленню та ароматним часником.",
        ingredients=("гречка", "гриби", "шпинат", "цибуля", "часник", "олія", "сіль"),
        steps=(
            "Відваріть гречку.",
            "Обсмажте цибулю, гриби й часник.",
            "Змішайте зі шпинатом і гречкою, прогрійте 2 хвилини.",
        ),
        vegetarian=True,
        gluten_free=True,
        image_url="https://images.unsplash.com/photo-1604909052743-94e838986d24?auto=format&fit=crop&w=900&q=80",
    ),
    Recipe(
        name="Омлет із сиром та помідорами",
        time="15 хв",
        description="Швидкий сніданок або легка вечеря з базових продуктів холодильника.",
        ingredients=("яйця", "сир", "помідори", "олія", "сіль"),
        steps=(
            "Збийте яйця із сіллю.",
            "Додайте помідори та сир.",
            "Готуйте на сковороді під кришкою до стабільної текстури.",
        ),
        vegetarian=True,
        gluten_free=True,
        image_url="https://images.unsplash.com/photo-1525351484163-7529414344d8?auto=format&fit=crop&w=900&q=80",
    ),
]


def normalize_ingredient(value: str) -> str:
    return value.strip().lower()


def normalize_ingredients(items: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    normalized = []
    for item in items:
        ingredient = normalize_ingredient(str(item))
        if ingredient and ingredient not in normalized:
            normalized.append(ingredient)
    return normalized


def recipe_to_dict(recipe: Recipe, match_score: int = 0) -> dict[str, object]:
    return {
        "name": recipe.name,
        "time": recipe.time,
        "description": recipe.description,
        "ingredients": list(recipe.ingredients),
        "steps": list(recipe.steps),
        "vegetarian": recipe.vegetarian,
        "gluten_free": recipe.gluten_free,
        "image_url": recipe.image_url,
        "match_score": match_score,
    }


def suggest_recipes_for_items(
    fridge_items: list[str],
    vegetarian: bool = False,
    gluten_free: bool = False,
    limit: int = 4,
) -> list[dict[str, object]]:
    normalized_fridge = set(normalize_ingredients(fridge_items))
    ranked_recipes = []

    for recipe in RECIPE_BOOK:
        if vegetarian and not recipe.vegetarian:
            continue
        if gluten_free and not recipe.gluten_free:
            continue

        required = set(recipe.ingredients)
        matched = required.intersection(normalized_fridge)
        required_main = required.difference({"олія", "сіль", "часник"})
        missing_main = required_main.difference(normalized_fridge)
        score = len(matched) * 2 - len(missing_main)
        ranked_recipes.append((score, len(matched), recipe))

    ranked_recipes.sort(key=get_recipe_rank, reverse=True)
    return [recipe_to_dict(recipe, score) for score, _, recipe in ranked_recipes[:limit]]


def get_recipe_rank(item: tuple[int, int, Recipe]) -> tuple[int, int, int]:
    score, matched_count, recipe = item
    return score, matched_count, -len(recipe.ingredients)


def build_shopping_list(recipes: list[dict[str, object]], fridge_items: list[str]) -> list[str]:
    fridge = set(normalize_ingredients(fridge_items))
    missing = []

    for recipe in recipes:
        for ingredient in recipe.get("ingredients", []):
            normalized = normalize_ingredient(str(ingredient))
            if normalized not in fridge and normalized not in missing:
                missing.append(normalized)

    return missing


def estimate_tokens(messages: list[dict[str, str]]) -> int:
    total_chars = sum(len(message.get("content", "")) for message in messages)
    return max(1, total_chars // 4) if messages else 0
