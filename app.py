from __future__ import annotations

import json
import os
import uuid
from collections.abc import Generator

import streamlit as st

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        return None

from agent import run_cooking_agent
from recipe_data import (
    AVAILABLE_INGREDIENTS,
    build_shopping_list,
    estimate_tokens,
    normalize_ingredients,
    suggest_recipes_for_items,
)

load_dotenv()

DEFAULT_SYSTEM_PROMPT = (
    "Ти ChefBot, кулінарний помічник. Допомагай підібрати рецепти з наявних "
    "інгредієнтів, враховуй дієтичні обмеження, пропонуй короткі кроки "
    "приготування та список покупок українською мовою."
)


def main() -> None:
    st.set_page_config(
        page_title="ChefBot",
        page_icon="🍳",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_styles()
    initialize_session_state()
    render_sidebar()
    render_header()

    chat_tab, recipes_tab, menu_tab = st.tabs(["Чат", "Рецепти", "Меню"])
    with chat_tab:
        render_chat()
    with recipes_tab:
        render_recipe_dashboard()
    with menu_tab:
        render_menu_planner()


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            .vr-hero {
                padding: 1.2rem 1.4rem;
                border-radius: 8px;
                background: linear-gradient(135deg, #fff4df 0%, #ffe0b6 52%, #eaf7dc 100%);
                border: 1px solid #f2c98f;
                margin-bottom: 1rem;
            }
            .vr-hero h1 {
                margin: 0 0 .35rem;
                color: #663b12;
                letter-spacing: 0;
            }
            .vr-hero p {
                margin: 0;
                color: #6b4a22;
                font-size: 1rem;
            }
            .vr-chip {
                display: inline-block;
                padding: .25rem .55rem;
                border-radius: 999px;
                background: #fff7e8;
                border: 1px solid #f0c27b;
                color: #70430f;
                margin: .15rem .2rem .15rem 0;
                font-size: .88rem;
            }
            .vr-muted {
                color: #765f45;
                font-size: .92rem;
            }
            .vr-recipe-meta {
                color: #6d4e25;
                font-weight: 600;
                margin-bottom: .4rem;
            }
            .vr-small-note {
                font-size: .86rem;
                color: #725d42;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_session_state() -> None:
    defaults = {
        "messages": [
            {
                "role": "assistant",
                "content": "Вітаю! Напишіть, які інгредієнти є вдома, і я запропоную рецепти.",
            }
        ],
        "thread_id": str(uuid.uuid4()),
        "fridge": ["курка", "рис", "броколі"],
        "suggested_recipes": [],
        "mode": "Звичайний чат",
        "temperature": 0.6,
        "max_tokens": 700,
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "diet_restrictions": {"vegetarian": False, "gluten_free": False},
        "weekly_menu": {},
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    refresh_recipe_suggestions()


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Мій холодильник")
        ingredient_options = build_ingredient_options()
        selected = st.multiselect(
            "Оберіть інгредієнти",
            options=ingredient_options,
            default=st.session_state.fridge,
        )

        with st.form("fridge_form"):
            custom_item = st.text_input("Додати власний інгредієнт")
            submitted = st.form_submit_button("Оновити холодильник")
            if submitted:
                updated_items = selected[:]
                if custom_item.strip():
                    updated_items.append(custom_item)
                st.session_state.fridge = normalize_ingredients(updated_items)
                refresh_recipe_suggestions()
                st.rerun()

        st.divider()
        st.subheader("Обмеження")
        vegetarian = st.checkbox(
            "Вегетаріанське",
            value=st.session_state.diet_restrictions["vegetarian"],
        )
        gluten_free = st.checkbox(
            "Без глютену",
            value=st.session_state.diet_restrictions["gluten_free"],
        )
        st.session_state.diet_restrictions = {
            "vegetarian": vegetarian,
            "gluten_free": gluten_free,
        }
        refresh_recipe_suggestions()

        st.divider()
        st.subheader("Налаштування")
        st.session_state.mode = st.radio(
            "Режим роботи",
            options=["Звичайний чат", "Агент з інструментами"],
            index=0 if st.session_state.mode == "Звичайний чат" else 1,
        )
        st.session_state.temperature = st.slider(
            "Температура",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.temperature),
            step=0.05,
        )
        st.session_state.max_tokens = st.slider(
            "Max tokens",
            min_value=200,
            max_value=2000,
            value=int(st.session_state.max_tokens),
            step=100,
        )
        with st.expander("Системний промпт"):
            st.session_state.system_prompt = st.text_area(
                "Поведінка асистента",
                value=st.session_state.system_prompt,
                height=160,
            )

        if st.button("Очистити історію"):
            clear_chat()
            st.rerun()

        st.divider()
        render_usage_stats()
        render_history_download()
        st.caption("ChefBot підбирає рецепти, веде холодильник і формує список покупок.")


def render_header() -> None:
    st.markdown(
        """
        <div class="vr-hero">
            <h1>ChefBot</h1>
            <p>Кулінарний помічник для рецептів із продуктів, які вже є вдома.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.fridge:
        chips = "".join(f'<span class="vr-chip">{item}</span>' for item in st.session_state.fridge)
        st.markdown(chips, unsafe_allow_html=True)


def render_chat() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input("Напишіть, що є в холодильнику або яку страву хочете")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("ChefBot готує відповідь..."):
            if st.session_state.mode == "Агент з інструментами":
                response = handle_agent_message(prompt)
                st.write(response)
            else:
                response = st.write_stream(stream_gemini_response(prompt))

    st.session_state.messages.append({"role": "assistant", "content": str(response)})


def handle_agent_message(prompt: str) -> str:
    restrictions = st.session_state.diet_restrictions
    result = run_cooking_agent(
        user_message=prompt,
        thread_id=st.session_state.thread_id,
        fridge_items=st.session_state.fridge,
        vegetarian=restrictions["vegetarian"],
        gluten_free=restrictions["gluten_free"],
        temperature=float(st.session_state.temperature),
        max_tokens=int(st.session_state.max_tokens),
        system_prompt=st.session_state.system_prompt,
    )
    st.session_state.fridge = result["fridge_items"]
    st.session_state.suggested_recipes = result["suggested_recipes"]
    return result["response"]


def stream_gemini_response(prompt: str) -> Generator[str, None, None]:
    api_key = get_secret("GOOGLE_API_KEY")
    if not api_key:
        yield build_local_chat_response(prompt)
        return

    try:
        client = get_gemini_client(api_key)
        contents = build_gemini_contents(prompt)
        stream = client.models.generate_content_stream(
            model=get_secret("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=contents,
            config={
                "temperature": float(st.session_state.temperature),
                "max_output_tokens": int(st.session_state.max_tokens),
                "system_instruction": st.session_state.system_prompt,
            },
        )
        for chunk in stream:
            text = getattr(chunk, "text", "")
            if text:
                yield text
    except Exception as exc:
        yield f"Не вдалося отримати відповідь Gemini. Локальна підказка: {build_local_chat_response(prompt)}"
        yield f"\n\nТехнічна причина: {exc}"


@st.cache_resource
def get_gemini_client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


def build_gemini_contents(prompt: str) -> list[dict[str, object]]:
    history = st.session_state.messages[-12:-1]
    contents = []
    for message in history:
        role = "model" if message["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message["content"]}]})
    contents.append({"role": "user", "parts": [{"text": build_prompt_context(prompt)}]})
    return contents


def build_prompt_context(prompt: str) -> str:
    restrictions = st.session_state.diet_restrictions
    return (
        f"Запит користувача: {prompt}\n"
        f"Інгредієнти в холодильнику: {', '.join(st.session_state.fridge) or 'немає'}\n"
        f"Вегетаріанське: {restrictions['vegetarian']}; Без глютену: {restrictions['gluten_free']}."
    )


def build_local_chat_response(prompt: str) -> str:
    detected_items = normalize_ingredients([item for item in AVAILABLE_INGREDIENTS if item in prompt.lower()])
    if detected_items:
        st.session_state.fridge = normalize_ingredients(st.session_state.fridge + detected_items)
        refresh_recipe_suggestions()

    recipes = st.session_state.suggested_recipes[:3]
    if not recipes:
        return "Додайте кілька інгредієнтів у холодильник, і я запропоную рецепти."

    lines = ["Можу запропонувати:"]
    for recipe in recipes:
        lines.append(f"- {recipe['name']} ({recipe['time']}): {recipe['description']}")
    return "\n".join(lines)


def render_recipe_dashboard() -> None:
    recipes = st.session_state.suggested_recipes
    if not recipes:
        st.info("Додайте інгредієнти в холодильник, щоб побачити рекомендації.")
        return

    st.subheader("Рекомендовані рецепти")
    cols = st.columns(2)
    for index, recipe in enumerate(recipes):
        with cols[index % 2]:
            render_recipe_card(recipe)

    shopping_list = build_shopping_list(recipes, st.session_state.fridge)
    with st.expander("Список покупок"):
        if shopping_list:
            st.table({"Потрібно докупити": shopping_list})
        else:
            st.success("Усе необхідне для рекомендованих рецептів уже є.")


def build_ingredient_options() -> list[str]:
    options = AVAILABLE_INGREDIENTS[:]
    for item in st.session_state.fridge:
        if item not in options:
            options.append(item)
    return options


def render_recipe_card(recipe: dict[str, object]) -> None:
    with st.container(border=True):
        image_url = str(recipe.get("image_url", ""))
        if image_url:
            st.image(image_url, width="stretch")
        st.subheader(str(recipe["name"]))
        st.markdown(f'<div class="vr-recipe-meta">{recipe["time"]}</div>', unsafe_allow_html=True)
        st.write(str(recipe["description"]))
        st.progress(min(max(int(recipe.get("match_score", 0)) + 4, 0), 10) / 10)
        with st.expander("Інгредієнти"):
            for ingredient in recipe.get("ingredients", []):
                st.write(f"- {ingredient}")
        with st.expander("Кроки"):
            for step in recipe.get("steps", []):
                st.write(f"- {step}")


def render_menu_planner() -> None:
    recipes = st.session_state.suggested_recipes
    if not recipes:
        st.info("Спочатку отримайте рекомендовані рецепти.")
        return

    st.subheader("План меню")
    days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
    recipe_names = [str(recipe["name"]) for recipe in recipes]

    with st.form("menu_form"):
        planned_menu = {}
        columns = st.columns(2)
        for index, day in enumerate(days):
            with columns[index % 2]:
                planned_menu[day] = st.selectbox(
                    day,
                    options=["Не обрано"] + recipe_names,
                    index=0,
                    key=f"menu_{day}",
                )
        saved = st.form_submit_button("Зберегти меню")
        if saved:
            st.session_state.weekly_menu = planned_menu
            st.success("Меню збережено.")

    if st.session_state.weekly_menu:
        st.dataframe(
            [{"День": day, "Страва": meal} for day, meal in st.session_state.weekly_menu.items()],
            width="stretch",
            hide_index=True,
        )


def render_usage_stats() -> None:
    user_messages = sum(1 for message in st.session_state.messages if message["role"] == "user")
    assistant_messages = sum(1 for message in st.session_state.messages if message["role"] == "assistant")
    tokens = estimate_tokens(st.session_state.messages)
    col_1, col_2 = st.columns(2)
    col_1.metric("Запити", user_messages)
    col_2.metric("Відповіді", assistant_messages)
    st.metric("Оцінка токенів", tokens)


def render_history_download() -> None:
    payload = {
        "thread_id": st.session_state.thread_id,
        "fridge": st.session_state.fridge,
        "diet_restrictions": st.session_state.diet_restrictions,
        "messages": st.session_state.messages,
    }
    st.download_button(
        "Експорт історії JSON",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name="chefbot_history.json",
        mime="application/json",
    )


def refresh_recipe_suggestions() -> None:
    restrictions = st.session_state.diet_restrictions
    st.session_state.suggested_recipes = suggest_recipes_for_items(
        st.session_state.fridge,
        vegetarian=restrictions["vegetarian"],
        gluten_free=restrictions["gluten_free"],
    )


def clear_chat() -> None:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Історію очищено. Напишіть, які продукти маєте сьогодні.",
        }
    ]
    st.session_state.thread_id = str(uuid.uuid4())


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return str(value or os.getenv(name, default))


if __name__ == "__main__":
    main()
