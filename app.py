import streamlit as st
import pandas as pd
from lxml import etree
import re
import unicodedata
from difflib import SequenceMatcher

# --- 1. НАСТРОЙКИ СТРАНИЦЫ И СТИЛИ ---
st.set_page_config(page_title="Лингвистический компаратор", layout="wide")

st.markdown("""
    <style>
    @font-face { font-family: 'BukyVede'; src: local('BukyVede'); }
    .big-word { 
        font-family: 'BukyVede', serif; font-size: 64px; color: #1E88E5;
        padding: 20px; background: #f1f3f4; border-radius: 12px;
        text-align: center; border: 2px solid #1E88E5; margin: 15px 0;
    }
    [data-testid="stDataFrame"] td { font-family: 'BukyVede', serif !important; font-size: 18px !important; }
    .legend-item { padding: 5px 15px; border-radius: 4px; margin-right: 10px; font-size: 14px; display: inline-block; border: 1px solid #ddd; }
    .stat-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 10px; }
    .context-box { background-color: #f5f5f5; padding: 15px; border-radius: 10px; font-family: 'BukyVede', serif; font-size: 18px; margin: 10px 0; border-left: 4px solid #1E88E5; }
    </style>
    """, unsafe_allow_html=True)


# --- 2. ФУНКЦИИ НОРМАЛИЗАЦИИ ---

def normalize_text(text):
    """Нормализация текста (убираем диакритику, приводим к нижнему регистру)"""
    if not text:
        return ""
    # Приводим к нижнему регистру
    text = text.lower()
    # Заменяем распространенные варианты букв
    replacements = {
        'ѣ': 'е', 'ѳ': 'ф', 'ѵ': 'и', 'ѡ': 'о',
        '́': '', '̀': '', '̑': '', '҃': '',  # Убираем диакритику
        'ъ': 'ъ', 'ь': 'ь',  # оставляем еры
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def phonetic_normalize(text):
    """Фонетическая нормализация для сравнения произношения"""
    if not text:
        return ""
    text = normalize_text(text)
    # Фонетические замены
    replacements = {
        'о': 'а',  # аканье
        'е': 'и',  # иканье
        'я': 'а',
        'ю': 'у',
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

            # Собираем морфологические признаки
            morph = {}
            for f in w.xpath('.//*[local-name()="f"]'):
                name = f.get('name')
                sym_vals = f.xpath('.//*[local-name()="symbol"]/@value')
                if name and sym_vals:
                    morph[name] = sym_vals[0].strip()

            if text:
                words.append({
                    'id': word_id,
                    'surface': text,  # оригинальное написание
                    'lemma': lemma,
                    'morph': morph,
                    'normalized': normalize_text(text),
                    'phonetic': phonetic_normalize(text)
                })
        return words
    except Exception as e:
        st.error(f"Ошибка в файле {file.name}: {e}")
        return []


# --- 4. АЛГОРИТМ ВЫРАВНИВАНИЯ (Нидлман-Вунш) ---

def similarity_score(w1, w2):
    """
    Оценка схожести двух токенов
    normalized совпадает           → +10 баллов
    lemma + morph совпадают        → +8 баллов
    lemma совпадает                → +6 баллов
    phonetic совпадает             → +5 баллов
    текстовая схожесть ≥ 0.8       → +3 балла
    текстовая схожесть ≥ 0.65      → +1 балл
    иначе                          → -4 балла
    """
    if not w1 or not w2:
        return -4

    # 1. Normalized совпадает
    if w1['normalized'] == w2['normalized']:
        return 10

    # 2. Lemma + morph совпадают
    if w1['lemma'] == w2['lemma'] and w1['lemma']:
        if w1['morph'] == w2['morph']:
            return 8

    # 3. Lemma совпадает
    if w1['lemma'] == w2['lemma'] and w1['lemma']:
        return 6

    # 4. Phonetic совпадает
    if w1['phonetic'] == w2['phonetic']:
        return 5

    # 5. Текстовая схожесть
    similarity = edit_distance_similarity(w1['normalized'], w2['normalized'])
    if similarity >= 0.8:
        return 3
    elif similarity >= 0.65:
        return 1

    return -4


def align_pair(base_list, target_list):
    """Глобальное выравнивание Нидлмана-Вунша"""
    n, m = len(base_list), len(target_list)

    # Инициализация матрицы
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i * -2
    for j in range(m + 1):
        dp[0][j] = j * -2

    # Заполнение матрицы
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match_score = similarity_score(base_list[i - 1], target_list[j - 1])
            dp[i][j] = max(
                dp[i - 1][j - 1] + match_score,
                dp[i - 1][j] - 2,
                dp[i][j - 1] - 2
            )

    # Обратный проход для восстановления соответствий
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
    """
    Классификация типа разночтения.

    Порядок проверки (строго по порядку):

    1. EXACT (Идентично)
       - normalized совпадает И surface совпадает

    2. GRAPHICAL (Графическое)
       - normalized совпадает, но surface разный

    3. PHONETIC (Фонетическое)
       - phonetic совпадает

    4. MORPHOLOGICAL (Морфологическое)
       - lemma совпадает, но morph разный

    5. GRAPHICAL (Графическое)
       - lemma совпадает и morph совпадает (разница только в surface)

    6. SYNTACTIC (Синтаксическое)
       - сцепление нескольких токенов

    7. LEXICAL (Лексическое)
       - во всех остальных случаях
    """

    # Проверка на пропуск
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
            # Лемма совпадает, морфология совпадает, но normalized разный
            return "Графическое"

    # 4. Проверка текстовой схожести (для графических различий)
    similarity = edit_distance_similarity(main_word['normalized'], witness_word['normalized'])
    if similarity >= 0.62:
        return "Графическое"

    # 5. По умолчанию - лексическое
    return "Лексическое"


def get_context(words, index, context_size=10):
    """Возвращает контекст: до 10 слов до и 10 слов после указанного индекса"""
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

    Данная программа позволяет сравнивать различные списки древнерусских евангельских текстов, автоматически выявлять разночтения и редактировать результаты.

    ---

    ### 🔍 АЛГОРИТМ ОПРЕДЕЛЕНИЯ ТИПОВ РАЗНОЧТЕНИЙ

    | Приоритет | Тип | Условие | Пример |
    |-----------|-----|---------|--------|
    | 1 | **Идентично** | Normalized и surface совпадают | "странѣ" = "странѣ" |
    | 2 | **Графическое** | Normalized совпадает, surface разный | "грѣшницѣ" vs "грѣшници" |
    | 3 | **Фонетическое** | Phonetic форма совпадает | "оу" vs "у" |
    | 4 | **Морфологическое** | Lemma совпадает, morph разный | "грѣшницѣ" (дат.п.) vs "грѣшника" (вин.п.) |
    | 5 | **Лексическое** | Во всех остальных случаях | "человѣкъ" vs "господь" |

    ---

    ### 🚀 ШАГ 1: ЗАГРУЗКА ФАЙЛОВ
    1. В левой боковой панели (**Sidebar**) нажмите **"Browse files"** или **"Загрузить XML"**
    2. Выберите один или несколько XML-файлов с евангельскими списками
    3. После загрузки в выпадающем списке **"Эталонный список"** выберите основной текст

    ---

    ### 🖱️ ШАГ 2: РАБОТА С ТАБЛИЦЕЙ-РЕДАКТОРОМ

    | Действие | Как выполнить |
    |----------|---------------|
    | **Сортировка** | Нажмите на заголовок колонки (▲▼) |
    | **Поиск** | Нажмите **Ctrl+F** (или Cmd+F на Mac) |
    | **Фильтрация** | Нажмите на значок фильтра (≡) в заголовке |
    | **Скрыть колонку** | Нажмите ☰ в правом верхнем углу таблицы |
    | **Редактировать тип** | Дважды кликните по ячейке в колонке "Тип (...)" |

    ### 🎨 Цветовая индикация:
    - 🟢 **Идентично** — зеленый фон
    - 🔴 **Лексическое** — красный фон
    - 🟡 **Морфологическое** — желтый фон
    - 🔵 **Графическое** — голубой фон
    - 🟣 **Фонетическое** — фиолетовый фон

    ---

    ### 🔍 ШАГ 3: ПРОСМОТР КОНТЕКСТА

    Под таблицей находится блок **"🔍 Контекст слова"**:
    1. Введите номер строки
    2. Выберите источник (эталон или другой список)
    3. Программа покажет 10 слов до и 10 слов после

    ---

    ### 📈 ШАГ 4: СТАТИСТИКА И ЭКСПОРТ

    Внизу страницы:
    - **Статистика** по каждому списку (обновляется при редактировании)
    - **Кнопка "Скачать результаты (CSV)"** для сохранения
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
    st.info(
        "💡 **Совет:** Нажмите на значок ☰ в правом верхнем углу таблицы, чтобы скрыть ненужные колонки. Используйте Ctrl+F для поиска. Дважды кликните по ячейке 'Тип' для изменения категории.")


    # Цветовая схема
    def style_table(row):
        styles = [''] * len(row)
        for i, col in enumerate(row.index):
            if "Тип" in col:
                val = row[col]
                if val == "Лексическое":
                    styles[i] = 'background-color: #ffcdd2'  # красный
                elif val == "Морфологическое":
                    styles[i] = 'background-color: #fff9c4'  # желтый
                elif val == "Графическое":
                    styles[i] = 'background-color: #e1f5fe'  # голубой
                elif val == "Фонетическое":
                    styles[i] = 'background-color: #e1bee7'  # фиолетовый
                elif val == "Идентично":
                    styles[i] = 'background-color: #c8e6c9'  # зеленый
        return styles


    # РЕДАКТОР
    edited_df = st.data_editor(df.style.apply(style_table, axis=1), use_container_width=True, height=400)

    # КОНТЕКСТ
    st.divider()
    st.subheader("🔍 Контекст слова (10 слов до и после)")

    col1, col2 = st.columns([1, 2])
    with col1:
        if not edited_df.empty:
            max_idx = max(0, len(edited_df) - 1)
            selected_row = st.number_input("Выберите строку для просмотра контекста:", 0, max_idx, 0)

    with col2:
        st.markdown("**Выберите текст для просмотра:**")
        context_texts = st.radio(
            "Источник контекста:",
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
            st.info("Слово не найдено в выбранном списке для отображения контекста.")

    # СТАТИСТИКА
    st.divider()
    st.subheader("📈 Статистика по текстам")

    others = st.session_state.others_list
    stat_cols = st.columns(len(others))

    for idx, o_name in enumerate(others):
        with stat_cols[idx]:
            st.markdown(f"<div class='stat-card'><b>📄 Текст: {o_name}</b>", unsafe_allow_html=True)
            type_col = f"Тип ({o_name})"
            counts = edited_df[type_col].value_counts()

            total = len(edited_df)
            identical = counts.get("Идентично", 0)
            diffs = total - identical

            similarity = round(identical / total * 100, 1) if total > 0 else 0

            st.markdown(f"**📊 Общее количество слов:** {total}")
            st.markdown(f"**✅ Идентично:** {identical} ({similarity}%)")
            st.markdown(f"**❌ Различий:** {diffs} ({100 - similarity}%)")

            st.progress(similarity / 100)

            st.markdown("---")
            st.caption("📋 Типы различий:")

            diff_types = {
                "Лексическое": "🔄 Разные слова",
                "Морфологическое": "📚 Разные формы",
                "Графическое": "✍️ Разное написание",
                "Фонетическое": "🔊 Разное произношение",
                "Пропуск": "❌ Слово отсутствует"
            }

            for t_name, t_desc in diff_types.items():
                c_val = counts.get(t_name, 0)
                if c_val > 0:
                    st.write(f"- **{t_name}** ({t_desc}): {c_val}")

            st.markdown("</div>", unsafe_allow_html=True)

    # ЭКСПОРТ
    st.divider()
    csv = edited_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Скачать результаты (CSV)", csv, "aligned_corpus.csv", "text/csv", use_container_width=True)

else:
    st.info("👈 Загрузите XML-файлы и нажмите кнопку 'Запустить сравнение' в боковой панели.")