import streamlit as st
import pandas as pd
from lxml import etree
import re
import unicodedata
from difflib import SequenceMatcher

# --- 1. НАСТРОЙКИ СТРАНИЦЫ И СТИЛИ ---
st.set_page_config(page_title="Лингвистический компаратор", layout="wide")

# Подключаем шрифты Menaion и Putyata через Google Fonts (альтернатива)
# Или через локальные файлы, если они загружены
st.markdown("""
    <style>
    /* Подключение шрифтов Menaion и Putyata */
    @font-face {
        font-family: 'Menaion';
        src: url('https://cdn.jsdelivr.net/gh/typiconman/menaion-font@master/fonts/menaion.woff2') format('woff2'),
             url('https://cdn.jsdelivr.net/gh/typiconman/menaion-font@master/fonts/menaion.woff') format('woff'),
             url('https://cdn.jsdelivr.net/gh/typiconman/menaion-font@master/fonts/menaion.ttf') format('truetype');
        font-weight: normal;
        font-style: normal;
    }

    @font-face {
        font-family: 'Putyata';
        src: url('https://cdn.jsdelivr.net/gh/typiconman/menaion-font@master/fonts/Putyata.woff') format('woff'),
             url('https://cdn.jsdelivr.net/gh/typiconman/menaion-font@master/fonts/Putyata.ttf') format('truetype');
        font-weight: normal;
        font-style: normal;
    }

    /* Основной класс для церковнославянского текста */
    .mnn {
        font-family: 'Menaion', 'Putyata', 'BukyVede', 'Segoe UI Historic', serif;
        font-size: 22px;
        color: #650000;
    }

    /* Для крупного отображения */
    .big-word { 
        font-family: 'Menaion', 'Putyata', 'BukyVede', serif;
        font-size: 64px; 
        color: #1E88E5;
        padding: 20px; 
        background: #f1f3f4; 
        border-radius: 12px;
        text-align: center; 
        border: 2px solid #1E88E5; 
        margin: 15px 0;
    }

    /* Таблица */
    [data-testid="stDataFrame"] td, 
    [data-testid="stDataFrame"] th {
        font-family: 'Menaion', 'Putyata', 'BukyVede', 'Segoe UI Historic', monospace !important;
        font-size: 18px !important;
        padding: 8px 12px !important;
    }

    /* Пагинация и служебные элементы */
    .pg {
        font-family: 'Courier New', monospace;
        color: gray;
        font-size: 12px;
    }

    .cnt {
        font-family: 'Verdana', 'Arial', sans-serif;
        font-size: 11px;
        color: gray;
    }

    .stat-card { 
        background-color: #f8f9fa; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #e0e0e0; 
        margin-bottom: 10px; 
    }

    .context-box { 
        background-color: #f5f5f5; 
        padding: 15px; 
        border-radius: 10px; 
        font-family: 'Menaion', 'Putyata', 'BukyVede', serif; 
        font-size: 18px; 
        margin: 10px 0; 
        border-left: 4px solid #1E88E5; 
    }

    /* Цвета для разночтений */
    .diff-lexical { background-color: #ffcdd2; }
    .diff-morphological { background-color: #fff9c4; }
    .diff-graphical { background-color: #e1f5fe; }
    .diff-phonetic { background-color: #e1bee7; }
    .diff-identical { background-color: #c8e6c9; }
    </style>
""", unsafe_allow_html=True)


# --- 2. ФУНКЦИИ НОРМАЛИЗАЦИИ ---

def normalize_text(text):
    """Нормализация текста (убираем диакритику, приводим к нижнему регистру)"""
    if not text:
        return ""
    text = text.lower()
    replacements = {
        'ѣ': 'е', 'ѳ': 'ф', 'ѵ': 'и', 'ѡ': 'о',
        '́': '', '̀': '', '̑': '', '҃': '',
        'ъ': 'ъ', 'ь': 'ь',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def phonetic_normalize(text):
    """Фонетическая нормализация для сравнения произношения"""
    if not text:
        return ""
    text = normalize_text(text)
    replacements = {
        'о': 'а', 'е': 'и', 'я': 'а', 'ю': 'у',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def edit_distance_similarity(s1, s2):
    """Вычисление схожести строк (0-1)"""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1, s2).ratio()


# --- 3. ПАРСИНГ XML ---

def parse_xml_tei(file):
    raw = file.read()
    try:
        try:
            content = raw.decode('utf-16')
        except:
            content = raw.decode('utf-8')
        content = re.sub(r'<\?xml[^>]+encoding=["\']UTF-16["\'][^>]*\?>', '<?xml version="1.0" encoding="UTF-8"?>',
                         content, count=1)
        root = etree.fromstring(content.encode('utf-8'), parser=etree.XMLParser(recover=True))
        words = []
        for w in root.xpath('.//*[local-name()="w"]'):
            word_id = w.get('{http://www.w3.org/XML/1998/namespace}id') or w.get('id', 'n/a')
            lemma = (w.get('lemma') or "").strip().lower()
            text = unicodedata.normalize('NFC', "".join(w.xpath('text()')).strip())

            morph = {}
            for f in w.xpath('.//*[local-name()="f"]'):
                name = f.get('name')
                sym_vals = f.xpath('.//*[local-name()="symbol"]/@value')
                if name and sym_vals:
                    morph[name] = sym_vals[0].strip()

            if text:
                words.append({
                    'id': word_id,
                    'surface': text,
                    'lemma': lemma,
                    'morph': morph,
                    'normalized': normalize_text(text),
                    'phonetic': phonetic_normalize(text)
                })
        return words
    except Exception as e:
        st.error(f"Ошибка в файле {file.name}: {e}")
        return []


# --- 4. АЛГОРИТМ ВЫРАВНИВАНИЯ ---

def similarity_score(w1, w2):
    if not w1 or not w2:
        return -4

    if w1['normalized'] == w2['normalized']:
        return 10

    if w1['lemma'] == w2['lemma'] and w1['lemma']:
        if w1['morph'] == w2['morph']:
            return 8

    if w1['lemma'] == w2['lemma'] and w1['lemma']:
        return 6

    if w1['phonetic'] == w2['phonetic']:
        return 5

    similarity = edit_distance_similarity(w1['normalized'], w2['normalized'])
    if similarity >= 0.8:
        return 3
    elif similarity >= 0.65:
        return 1

    return -4


def align_pair(base_list, target_list):
    n, m = len(base_list), len(target_list)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i * -2
    for j in range(m + 1):
        dp[0][j] = j * -2

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match_score = similarity_score(base_list[i - 1], target_list[j - 1])
            dp[i][j] = max(
                dp[i - 1][j - 1] + match_score,
                dp[i - 1][j] - 2,
                dp[i][j - 1] - 2
            )

    matches = {}
    i, j = n, m
    while i > 0 and j > 0:
        current_score = dp[i][j]
        match_score = similarity_score(base_list[i - 1], target_list[j - 1])

        if current_score == dp[i - 1][j - 1] + match_score:
            matches[i - 1] = target_list[j - 1]
            i -= 1
            j -= 1
        elif current_score == dp[i - 1][j] - 2:
            matches[i - 1] = None
            i -= 1
        else:
            j -= 1

    return matches


# --- 5. КЛАССИФИКАЦИЯ ТИПОВ РАЗНОЧТЕНИЙ ---

def classify_variant(main_word, witness_word):
    if not main_word or not witness_word:
        return "Пропуск"

    # 1. Проверка normalized
    if main_word['normalized'] == witness_word['normalized']:
        if main_word['surface'] == witness_word['surface']:
            return "Идентично"
        else:
            return "Графическое"

    # 2. Проверка phonetic
    if main_word['phonetic'] == witness_word['phonetic']:
        return "Фонетическое"

    # 3. Проверка lemma
    if main_word['lemma'] == witness_word['lemma'] and main_word['lemma']:
        if main_word['morph'] != witness_word['morph']:
            return "Морфологическое"
        else:
            return "Графическое"

    # 4. Проверка текстовой схожести
    similarity = edit_distance_similarity(main_word['normalized'], witness_word['normalized'])
    if similarity >= 0.62:
        return "Графическое"

    return "Лексическое"


def get_context(words, index, context_size=10):
    start = max(0, index - context_size)
    end = min(len(words), index + context_size + 1)

    context_before = words[start:index]
    context_after = words[index + 1:end]

    return context_before, context_after


# --- 6. ИНТЕРФЕЙС ---

st.title("Сравнительный анализ параллельных корпусов")

# БЛОК ИНСТРУКЦИИ
with st.expander("📖 ПОДРОБНАЯ ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ (нажмите, чтобы развернуть)", expanded=True):
    st.markdown("""
    ### 📌 ОСНОВНЫЕ ВОЗМОЖНОСТИ ПРОГРАММЫ

    Данная программа позволяет сравнивать различные списки древнерусских евангельских текстов.

    ### 🔤 ОТОБРАЖЕНИЕ ШРИФТОВ

    Для корректного отображения церковнославянских символов и титла используются шрифты:
    - **Menaion** — основной шрифт для текста
    - **Putyata** — дополнительный шрифт

    Если символы отображаются некорректно (квадратики), установите шрифты:
    1. Скачайте [Menaion Unicode](https://www.ponomar.net/data/Menaion_Unicode.zip)
    2. Установите шрифт в систему

    ### 🔍 АЛГОРИТМ ОПРЕДЕЛЕНИЯ ТИПОВ РАЗНОЧТЕНИЙ

    | Приоритет | Тип | Условие |
    |-----------|-----|---------|
    | 1 | **Идентично** | Normalized и surface совпадают |
    | 2 | **Графическое** | Normalized совпадает, surface разный |
    | 3 | **Фонетическое** | Phonetic форма совпадает |
    | 4 | **Морфологическое** | Lemma совпадает, morph разный |
    | 5 | **Лексическое** | Во всех остальных случаях |

    ### 🖱️ РАБОТА С ТАБЛИЦЕЙ

    - **Сортировка** — нажмите на заголовок колонки
    - **Поиск** — Ctrl+F
    - **Фильтрация** — значок ≡ в заголовке
    - **Скрыть колонку** — значок ☰
    - **Редактировать тип** — дважды кликните по ячейке

    ### 🎨 Цветовая индикация:
    - 🟢 **Идентично** — зеленый
    - 🔴 **Лексическое** — красный
    - 🟡 **Морфологическое** — желтый
    - 🔵 **Графическое** — голубой
    - 🟣 **Фонетическое** — фиолетовый
    """)

if 'raw_data' not in st.session_state:
    st.session_state.raw_data = {}

with st.sidebar:
    st.header("📁 Загрузка")
    uploaded_files = st.file_uploader("Загрузить XML", type="xml", accept_multiple_files=True)
    if uploaded_files:
        for f in uploaded_files:
            if f.name not in st.session_state.raw_data:
                st.session_state.raw_data[f.name] = parse_xml_tei(f)

        file_names = list(st.session_state.raw_data.keys())
        main_file = st.selectbox("Эталонный список", file_names)

# ЗАПУСК АНАЛИЗА
if st.session_state.raw_data and st.button("🚀 Запустить сравнение"):
    base_words = st.session_state.raw_data[main_file]
    others = [n for n in st.session_state.raw_data.keys() if n != main_file]

    if others:
        with st.spinner("Синхронизация текстов..."):
            all_aligns = {name: align_pair(base_words, st.session_state.raw_data[name]) for name in others}
            final_rows = []
            for i, b_word in enumerate(base_words):
                row = {
                    "ID": b_word['id'],
                    "Лемма": b_word['lemma'],
                    f"ЭТАЛОН ({main_file})": b_word['surface'],
                }
                for o_name in others:
                    m_word = all_aligns[o_name].get(i)
                    row[f"Слово ({o_name})"] = m_word['surface'] if m_word else "---"
                    row[f"Тип ({o_name})"] = classify_variant(b_word, m_word)
                final_rows.append(row)
            st.session_state.comp_df = pd.DataFrame(final_rows)
            st.session_state.others_list = others
            st.session_state.main_file = main_file
            st.session_state.base_words = base_words
            st.session_state.all_aligns = all_aligns
    else:
        st.warning("Загрузите хотя бы два файла.")

# ВЫВОД РЕЗУЛЬТАТОВ
if 'comp_df' in st.session_state:
    df = st.session_state.comp_df
    main_file = st.session_state.main_file

    st.subheader("📝 Таблица-редактор")
    st.info("💡 Дважды кликните по ячейке 'Тип' для изменения категории. Используйте Ctrl+F для поиска.")


    # Цветовая схема
    def style_table(row):
        styles = [''] * len(row)
        for i, col in enumerate(row.index):
            if "Тип" in col:
                val = row[col]
                if val == "Лексическое":
                    styles[i] = 'background-color: #ffcdd2'
                elif val == "Морфологическое":
                    styles[i] = 'background-color: #fff9c4'
                elif val == "Графическое":
                    styles[i] = 'background-color: #e1f5fe'
                elif val == "Фонетическое":
                    styles[i] = 'background-color: #e1bee7'
                elif val == "Идентично":
                    styles[i] = 'background-color: #c8e6c9'
        return styles


    edited_df = st.data_editor(df.style.apply(style_table, axis=1), use_container_width=True, height=400)

    # КОНТЕКСТ
    st.divider()
    st.subheader("🔍 Контекст слова (10 слов до и после)")

    col1, col2 = st.columns([1, 2])
    with col1:
        if not edited_df.empty:
            max_idx = max(0, len(edited_df) - 1)
            selected_row = st.number_input("Выберите строку:", 0, max_idx, 0)

    with col2:
        context_texts = st.radio(
            "Источник:",
            options=[f"ЭТАЛОН ({main_file})"] + [f"Слово ({name})" for name in st.session_state.others_list],
            horizontal=True,
            index=0
        )

    if not edited_df.empty:
        selected_word = edited_df.iloc[selected_row][f"ЭТАЛОН ({main_file})"]

        if context_texts.startswith("ЭТАЛОН"):
            words_list = st.session_state.base_words
            word_index = selected_row
            source_name = main_file
        else:
            ms_name = context_texts.replace("Слово (", "").replace(")", "")
            aligned_word = st.session_state.all_aligns.get(ms_name, {}).get(selected_row)
            if aligned_word:
                target_words = st.session_state.raw_data[ms_name]
                for idx, w in enumerate(target_words):
                    if w['surface'] == aligned_word['surface']:
                        word_index = idx
                        break
                else:
                    word_index = selected_row
                words_list = target_words
                source_name = ms_name
            else:
                words_list = []
                word_index = 0

        if words_list and word_index < len(words_list):
            context_before, context_after = get_context(words_list, word_index, context_size=10)

            context_html = '<div class="context-box">'
            context_html += '<b>📖 Контекст (10 слов до и после):</b><br><br>'

            if context_before:
                context_html += '<span style="color: #666;">... '
                for w in context_before:
                    context_html += f'{w["surface"]} '
                context_html += '</span>'

            context_html += f'<span style="background-color: #1E88E5; color: white; padding: 2px 8px; border-radius: 20px; font-weight: bold;">{selected_word}</span>'

            if context_after:
                context_html += '<span style="color: #666;"> '
                for w in context_after:
                    context_html += f'{w["surface"]} '
                context_html += '</span>'

            context_html += '<br><br><span style="font-size: 12px; color: #888;">📌 Источник: ' + source_name + '</span>'
            context_html += '</div>'

            st.markdown(context_html, unsafe_allow_html=True)
        else:
            st.info("Слово не найдено")

    # СТАТИСТИКА
    st.divider()
    st.subheader("📈 Статистика")

    others = st.session_state.others_list
    stat_cols = st.columns(len(others))

    for idx, o_name in enumerate(others):
        with stat_cols[idx]:
            st.markdown(f"<div class='stat-card'><b>📄 {o_name}</b>", unsafe_allow_html=True)
            type_col = f"Тип ({o_name})"
            counts = edited_df[type_col].value_counts()

            total = len(edited_df)
            identical = counts.get("Идентично", 0)
            similarity = round(identical / total * 100, 1) if total > 0 else 0

            st.markdown(f"**✅ Идентично:** {identical} ({similarity}%)")
            st.progress(similarity / 100)

            st.markdown("---")
            st.caption("Типы различий:")

            for t_name in ["Лексическое", "Морфологическое", "Графическое", "Фонетическое", "Пропуск"]:
                c_val = counts.get(t_name, 0)
                if c_val > 0:
                    st.write(f"- {t_name}: {c_val}")

            st.markdown("</div>", unsafe_allow_html=True)

    # ЭКСПОРТ
    st.divider()
    csv = edited_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Скачать CSV", csv, "aligned_corpus.csv", "text/csv", use_container_width=True)

else:
    st.info("👈 Загрузите XML-файлы и нажмите 'Запустить сравнение'")