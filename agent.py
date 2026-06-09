from __future__ import annotations

# agent.py — Крок 6: LangGraph-агент з інструментами для ChefBot

import json
import os
import re
from typing import Any, TypedDict

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        return None

from recipe_data import normalize_ingredients, suggest_recipes_for_items

load_dotenv()

# ============================================================
# КОНСТАНТИ
# ============================================================
FRIDGE_STATE: dict[str, list[str]] = {}


# ============================================================
# СХЕМА РЕЗУЛЬТАТУ АГЕНТА
# ============================================================
class AgentResult(TypedDict):
    response: str
    fridge_items: list[str]
    suggested_recipes: list[dict[str, object]]
    used_langgraph: bool


# ============================================================
# ІНСТРУМЕНТИ АГЕНТА
# ============================================================
def set_fridge_items(items: list[str], thread_id: str = "default") -> str:
    normalized = normalize_ingredients(items)
    FRIDGE_STATE[thread_id] = normalized
    return f"Список інгредієнтів оновлено: {', '.join(normalized) if normalized else 'порожньо'}."


def add_fridge_item(item: str, thread_id: str = "default") -> str:
    normalized_item = normalize_ingredients([item])
    if not normalized_item:
        return "Інгредієнт не додано, бо назва порожня."

    current_items = FRIDGE_STATE.setdefault(thread_id, [])
    ingredient = normalized_item[0]
    if ingredient not in current_items:
        current_items.append(ingredient)

    return f"Додано інгредієнт: {ingredient}."


def list_fridge_items(thread_id: str = "default") -> str:
    items = FRIDGE_STATE.get(thread_id, [])
    if not items:
        return "Холодильник поки порожній."
    return "У холодильнику є: " + ", ".join(items) + "."


def suggest_recipes(
    thread_id: str = "default",
    vegetarian: bool = False,
    gluten_free: bool = False,
) -> str:
    recipes = suggest_recipes_for_items(FRIDGE_STATE.get(thread_id, []), vegetarian, gluten_free)
    if not recipes:
        return "Не знайшов відповідних рецептів для поточних фільтрів."

    lines = ["Можу запропонувати:"]
    for recipe in recipes:
        ingredients = ", ".join(str(item) for item in recipe["ingredients"])
        lines.append(f"- {recipe['name']} ({recipe['time']}): {ingredients}")
    return "\n".join(lines)


# ============================================================
# ЗАПУСК АГЕНТА
# ============================================================
def run_cooking_agent(
    user_message: str,
    thread_id: str,
    fridge_items: list[str],
    vegetarian: bool,
    gluten_free: bool,
    temperature: float,
    max_tokens: int,
    system_prompt: str,
) -> AgentResult:
    set_fridge_items(fridge_items, thread_id)
    api_key = get_api_key()

    if api_key:
        result = run_langgraph_agent(
            user_message=user_message,
            thread_id=thread_id,
            vegetarian=vegetarian,
            gluten_free=gluten_free,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            api_key=api_key,
        )
        if result is not None:
            return result

    return run_local_agent(user_message, thread_id, vegetarian, gluten_free)


# ============================================================
# LANGGRAPH-АГЕНТ
# ============================================================
def run_langgraph_agent(
    user_message: str,
    thread_id: str,
    vegetarian: bool,
    gluten_free: bool,
    temperature: float,
    max_tokens: int,
    system_prompt: str,
    api_key: str,
) -> AgentResult | None:
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_core.tools import tool
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langgraph.graph import END, START, MessagesState, StateGraph
        from langgraph.prebuilt import ToolNode, tools_condition
    except ImportError:
        return None

    @tool
    def set_fridge_items_tool(items: list[str]) -> str:
        """Оновлює список інгредієнтів у холодильнику."""
        return set_fridge_items(items, thread_id)

    @tool
    def add_fridge_item_tool(item: str) -> str:
        """Додає один інгредієнт у холодильник."""
        return add_fridge_item(item, thread_id)

    @tool
    def list_fridge_items_tool() -> str:
        """Показує поточний список інгредієнтів у холодильнику."""
        return list_fridge_items(thread_id)

    @tool
    def suggest_recipes_tool() -> str:
        """Пропонує рецепти з урахуванням поточних інгредієнтів і фільтрів."""
        return suggest_recipes(thread_id, vegetarian, gluten_free)

    tools = [
        set_fridge_items_tool,
        add_fridge_item_tool,
        list_fridge_items_tool,
        suggest_recipes_tool,
    ]
    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        google_api_key=api_key,
        temperature=temperature,
        max_output_tokens=max_tokens,
    ).bind_tools(tools)

    def call_model(state: MessagesState) -> dict[str, list[Any]]:
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    graph_builder = StateGraph(MessagesState)
    graph_builder.add_node("assistant", call_model)
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.add_edge(START, "assistant")
    graph_builder.add_conditional_edges("assistant", tools_condition)
    graph_builder.add_edge("tools", "assistant")
    graph_builder.add_edge("assistant", END)
    graph = graph_builder.compile()

    messages = [
        SystemMessage(content=build_agent_system_prompt(system_prompt, vegetarian, gluten_free)),
        HumanMessage(content=user_message),
    ]
    try:
        state = graph.invoke({"messages": messages}, config={"configurable": {"thread_id": thread_id}})
    except Exception:
        return None

    response = extract_last_message_content(state.get("messages", []))
    recipes = suggest_recipes_for_items(FRIDGE_STATE.get(thread_id, []), vegetarian, gluten_free)

    return {
        "response": response or run_local_agent(user_message, thread_id, vegetarian, gluten_free)["response"],
        "fridge_items": FRIDGE_STATE.get(thread_id, []),
        "suggested_recipes": recipes,
        "used_langgraph": True,
    }


# ============================================================
# ЛОКАЛЬНИЙ РЕЖИМ БЕЗ API-КЛЮЧА
# ============================================================
def run_local_agent(
    user_message: str,
    thread_id: str,
    vegetarian: bool,
    gluten_free: bool,
) -> AgentResult:
    detected_items = extract_ingredients_from_text(user_message)
    for item in detected_items:
        add_fridge_item(item, thread_id)

    wants_list = contains_any(user_message, ("що є", "список", "холодильник", "переглянь"))
    wants_recipe = contains_any(user_message, ("приготувати", "рецепт", "запропонуй", "порадь", "страва", "меню"))
    recipes = suggest_recipes_for_items(FRIDGE_STATE.get(thread_id, []), vegetarian, gluten_free)

    if wants_list and not wants_recipe:
        response = list_fridge_items(thread_id)
    elif wants_recipe or detected_items:
        response = build_recipe_response(recipes, vegetarian, gluten_free)
    else:
        response = (
            "Я можу вести список продуктів у холодильнику та пропонувати рецепти. "
            "Напишіть, які інгредієнти маєте, або попросіть запропонувати страву."
        )

    return {
        "response": response,
        "fridge_items": FRIDGE_STATE.get(thread_id, []),
        "suggested_recipes": recipes,
        "used_langgraph": False,
    }


def build_recipe_response(
    recipes: list[dict[str, object]],
    vegetarian: bool,
    gluten_free: bool,
) -> str:
    if not recipes:
        return "Для поточного набору інгредієнтів і фільтрів я не знайшов відповідних рецептів."

    filters = []
    if vegetarian:
        filters.append("вегетаріанські")
    if gluten_free:
        filters.append("безглютенові")

    prefix = "Ось ідеї з урахуванням ваших продуктів"
    if filters:
        prefix += " та фільтрів: " + ", ".join(filters)

    lines = [prefix + ":"]
    for recipe in recipes[:3]:
        lines.append(f"- {recipe['name']} — {recipe['description']} Час: {recipe['time']}.")
    return "\n".join(lines)


# ============================================================
# ДОПОМІЖНІ ФУНКЦІЇ
# ============================================================
def extract_ingredients_from_text(text: str) -> list[str]:
    known_ingredients = {
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
    }
    normalized_text = text.lower()
    found = [ingredient for ingredient in known_ingredients if re.search(rf"\b{re.escape(ingredient)}\b", normalized_text)]
    return normalize_ingredients(found)


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def get_api_key() -> str:
    return os.getenv("GOOGLE_API_KEY", "")


def build_agent_system_prompt(system_prompt: str, vegetarian: bool, gluten_free: bool) -> str:
    return "\n".join(
        [
            system_prompt,
            "Використовуй інструменти для оновлення холодильника та підбору рецептів.",
            f"Фільтр vegetarian={vegetarian}; gluten_free={gluten_free}.",
            "Відповідай українською, коротко і практично.",
        ]
    )


def extract_last_message_content(messages: list[Any]) -> str:
    for message in reversed(messages):
        content = getattr(message, "content", "")
        if isinstance(content, str) and content:
            return content
        if isinstance(content, list):
            return json.dumps(content, ensure_ascii=False)
    return ""
