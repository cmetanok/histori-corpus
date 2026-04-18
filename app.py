import streamlit as st
import pandas as pd
from lxml import etree
import re
import unicodedata
from difflib import SequenceMatcher

# --- 1. НАСТРОЙКИ СТРАНИЦЫ И СТИЛИ ---
st.set_page_config(page_title="Лингвистический компаратор", layout="wide")

# Расширенные стили для корректного отображения титла и комбинирующихся символов
st.markdown("""
    <style>
    /* Подключение шрифтов */
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

    /* Базовые настройки для всех элементов */
    * {
        font-feature-settings: "liga" 1, "clig" 1;
        font-variant-ligatures: additional-ligatures;
        text-rendering: optimizeLegibility;
    }

    /* Основной класс для церковнославянского текста */
    .mnn, .church-text {
        font-family: 'Menaion', 'Putyata', 'BukyVede', 'Segoe UI Historic', 'Palatino Linotype', serif;
        font-size: 22px;
        line-height: 1.6;
        color: #2c3e50;
        font-feature-settings: "liga" 1, "clig" 1;
        font-variant-ligatures: additional-ligatures;
        text-rendering: optimizeLegibility;
    }

    /* Для крупного отображения */
    .big-word { 
        font-family: 'Menaion', 'Putyata', 'BukyVede', 'Segoe UI Historic', serif;
        font-size: 64px; 
        color: #1E88E5;
        padding: 20px; 
        background: #f1f3f4; 
        border-radius: 12px;
        text-align: center; 
        border: 2px solid #1E88E5; 
        margin: 15px 0;
        font-feature-settings: "liga" 1, "clig" 1;
        font-variant-ligatures: additional-ligatures;
        text-rendering: optimizeLegibility;
    }

    /* Таблица */
    [data-testid="stDataFrame"] td, 
    [data-testid="stDataFrame"] th,
    .stDataFrame td,
    .stDataFrame th {
        font-family: 'Menaion', 'Putyata', 'BukyVede', 'Segoe UI Historic', monospace !important;
        font-size: 18px !important;
        padding: 8px 12px !important;
        font-feature-settings: "liga" 1, "clig" 1 !important;
        font-variant-ligatures: additional-ligatures !important;
        text-rendering: optimizeLegibility !important;
    }

    /* Контекстное окно */
    .context-box { 
        background-color: #f5f5f5; 
        padding: 15px; 
        border-radius: 10px; 
        font-family: 'Menaion', 'Putyata', 'BukyVede', serif; 
        font-size: 18px; 
        margin: 10px 0; 
        border-left: 4px solid #1E88E5;
        font-feature-settings: "liga" 1, "clig" 1;
        font-variant-ligatures: additional-ligatures;
        text-rendering: optimizeLegibility;
    }

    /* Пагинация */
    .pg {
        font-family: 'Courier New', monospace;
        color: gray;
        font-size: 12px;
    }

    /* Служебные элементы */
    .cnt {
        font-family: 'Verdana', 'Arial', sans-serif;
        font-size: 11px;
        color: gray;
    }

    /* Карточка статистики */
    .stat-card { 
        background-color: #f8f9fa; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #e0e0e0; 
        margin-bottom: 10px; 
    }

    /* Цвета для разночтений */
    .diff-lexical { background-color: #ffcdd2; }
    .diff-morphological { background-color: #fff9c4; }
    .diff-graphical { background-color: #e1f5fe; }
    .diff-phonetic { background-color: #e1bee7; }
    .diff-identical { background-color: #c8e6c9; }

    /* Исправление для комбинирующихся символов */
    .combined-char {
        display: inline-block;
        white-space: normal;
        word-break: keep-all;
    }
    </style>
""", unsafe_allow_html=True)


# --- 2. ФУНКЦИИ НОРМАЛИЗАЦИИ ---

def normalize_text(text):
    """Нормализация текста (убираем диакритику, приводим к нижнему регистру)"""
    if not text:
        return ""
    # Сначала нормализуем Unicode (NFC - соединяем комбинирующиеся символы)
    text = unicodedata.normalize('NFC', text)
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


def normalize_for_display(text):
    """Нормализация для отображения (сохраняем оригинал, но обрабатываем комбинирующиеся символы)"""
    if not text:
        return ""
    # Преобразуем в NFC форму (буква + диакритика → один символ)
    return unicodedata.normalize('NFC', text)


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
            # Нормализуем текст для отображения
            text_raw = "".join(w.xpath('text()')).strip()
            text = unicodedata.normalize('NFC', text_raw)

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
    ### 📌 ОСНОВНЫЕ ВОЗМОЖНОСТИ

    Программа сравнивает списки древнерусских евангельских текстов.

    ### 🔤 ОТОБРАЖЕНИЕ ЦЕРКОВНОСЛАВЯНСКИХ СИМВОЛОВ

    Для корректного отображения символов с титлом (например, **мⷭ҇ѧпⷭ҇оу**):

    1. **Установите шрифт Menaion Unicode**:
       - Скачайте с [https://www.ponomar.net/data/Menaion_Unicode.zip](https://www.ponomar.net/data/Menaion_Unicode.zip)
       - Установите в систему (ПКМ → Установить)
       - Перезагрузите браузер

    2. **Альтернативные шрифты**:
       - BukyVede
       - Segoe UI Historic (Windows 10/11)
       - Palatino Linotype

    3. **Если символы всё равно отображаются как квадратики**:
       - Используйте функцию "Лупа" для увеличенного просмотра
       - Скопируйте текст в Word с установленным шрифтом Menaion

    ### 🔍 АЛГОРИТМ ОПРЕДЕЛЕНИЯ ТИПОВ РАЗНОЧТЕНИЙ

    | Тип | Условие |
    |-----|---------|
    | **Идентично** | Normalized и surface совпадают |
    | **Графическое** | Normalized совпадает, surface разный |
    | **Фонетическое** | Phonetic форма совпадает |
    | **Морфологическое** | Lemma совпадает, morph разный |
    | **Лексическое** | Во всех остальных случаях |

    ### 🖱️ РАБОТА С ТАБЛИЦЕЙ

    - **Поиск** — Ctrl+F
    - **Сортировка** — нажмите на заголовок колонки
    - **Фильтрация** — значок ≡ в заголовке
    - **Скрыть колонку** — значок ☰
    - **Редактировать тип** — дважды кликните по ячейке

    ### 🎨 ЦВЕТОВАЯ ИНДИКАЦИЯ

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
                with st.spinner(f"Загрузка {f.name}..."):
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
                # Нормализуем для отображения
                display_word = normalize_for_display(b_word['surface'])
                row = {
                    "ID": b_word['id'],
                    "Лемма": b_word['lemma'],
                    f"ЭТАЛОН ({main_file})": display_word,
                }
                for o_name in others:
                    m_word = all_aligns[o_name].get(i)
                    if m_word:
                        display_match = normalize_for_display(m_word['surface'])
                        row[f"Слово ({o_name})"] = display_match
                        row[f"Тип ({o_name})"] = classify_variant(b_word, m_word)
                    else:
                        row[f"Слово ({o_name})"] = "---"
                        row[f"Тип ({o_name})"] = "Пропуск"
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
        "💡 **Совет:** Если символы отображаются некорректно, используйте блок 'Лупа' ниже для увеличенного просмотра.")


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


    # РЕДАКТОР
    edited_df = st.data_editor(df.style.apply(style_table, axis=1), use_container_width=True, height=400)

    # ЛУПА (для увеличенного просмотра)
    st.divider()
    st.subheader("🔍 Лупа (увеличенный просмотр)")

    if not edited_df.empty:
        c1, c2 = st.columns([1, 2])
        with c1:
            max_idx = max(0, len(edited_df) - 1)
            rid = st.number_input("Выберите строку:", 0, max_idx, 0, key="lupa_row")
            cname = st.selectbox("Выберите колонку:", [c for c in edited_df.columns if "Слово" in c or "ЭТАЛОН" in c],
                                 key="lupa_col")
        with c2:
            word_to_show = edited_df.iloc[rid][cname]
            # Показываем слово увеличенным шрифтом
            st.markdown(f'<div class="big-word">{word_to_show}</div>', unsafe_allow_html=True)
            # Дополнительная информация
            st.caption(f"Строка {rid}, колонка: {cname}")

    # КОНТЕКСТ
    st.divider()
    st.subheader("🔍 Контекст слова (10 слов до и после)")

    col1, col2 = st.columns([1, 2])
    with col1:
        if not edited_df.empty:
            max_idx = max(0, len(edited_df) - 1)
            selected_row = st.number_input("Выберите строку:", 0, max_idx, 0, key="context_row")

    with col2:
        context_texts = st.radio(
            "Источник:",
            options=[f"ЭТАЛОН ({main_file})"] + [f"Слово ({name})" for name in st.session_state.others_list],
            horizontal=True,
            index=0,
            key="context_source"
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
                    if normalize_for_display(w['surface']) == normalize_for_display(aligned_word['surface']):
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
                    context_html += f'{normalize_for_display(w["surface"])} '
                context_html += '</span>'

            context_html += f'<span style="background-color: #1E88E5; color: white; padding: 2px 8px; border-radius: 20px; font-weight: bold;">{normalize_for_display(selected_word)}</span>'

            if context_after:
                context_html += '<span style="color: #666;"> '
                for w in context_after:
                    context_html += f'{normalize_for_display(w["surface"])} '
                context_html += '</span>'

            context_html += '<br><br><span style="font-size: 12px; color: #888;">📌 Источник: ' + source_name + '</span>'
            context_html += '</div>'

            st.markdown(context_html, unsafe_allow_html=True)
        else:
            st.info("Слово не найдено в выбранном списке")

    # СТАТИСТИКА
    st.divider()
    st.subheader("📈 Статистика")

    others = st.session_state.others_list
    stat_cols = st.columns(min(len(others), 4))

    for idx, o_name in enumerate(others):
        if idx < 4:
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