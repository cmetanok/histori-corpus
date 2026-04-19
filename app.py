import streamlit as st
import pandas as pd
from lxml import etree
from lxml.builder import ElementMaker
import re
import unicodedata
from difflib import SequenceMatcher
from datetime import datetime
import io
import zipfile

# --- 1. НАСТРОЙКИ СТРАНИЦЫ И СТИЛИ ---
st.set_page_config(page_title="Лингвистический компаратор", layout="wide")

st.markdown("""
    <style>
    @font-face {
        font-family: 'Menaion';
        src: url('fonts/menaion.woff') format('woff');
        font-weight: normal;
        font-style: normal;
        font-display: swap;
    }

    @font-face {
        font-family: 'Putiata';
        src: url('fonts/putiata.ttf') format('truetype');
        font-weight: normal;
        font-style: normal;
        font-display: swap;
    }

    .big-word { 
        font-family: 'Menaion', 'Putiata', 'Segoe UI Historic', serif;
        font-size: 64px; 
        color: #1E88E5;
        padding: 20px; 
        background: #f1f3f4; 
        border-radius: 12px;
        text-align: center; 
        border: 2px solid #1E88E5; 
        margin: 15px 0;
    }

    [data-testid="stDataFrame"] td, 
    [data-testid="stDataFrame"] th,
    .stDataFrame td,
    .dataframe td,
    .dataframe th {
        font-family: 'Menaion', 'Putiata', 'Segoe UI Historic', serif !important;
        font-size: 20px !important;
    }

    .stDataEditor div[role="grid"] div[role="gridcell"] {
        font-family: 'Menaion', 'Putiata', 'Segoe UI Historic', serif !important;
        font-size: 20px !important;
    }

    .context-box { 
        background-color: #f5f5f5; 
        padding: 15px; 
        border-radius: 10px; 
        font-family: 'Menaion', 'Putiata', 'Segoe UI Historic', serif; 
        font-size: 20px; 
        margin: 10px 0; 
        border-left: 4px solid #1E88E5; 
    }

    .stat-card { 
        background-color: #f8f9fa; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #e0e0e0; 
        margin-bottom: 10px;
    }

    .instruction-step {
        background-color: #f0f7ff;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid #1E88E5;
    }

    .instruction-note {
        background-color: #fff3e0;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid #ff9800;
    }

    * {
        font-feature-settings: "liga" 1, "dlig" 1;
        text-rendering: optimizeLegibility;
    }
    </style>
    """, unsafe_allow_html=True)


# --- 2. ФУНКЦИЯ ПОЛНОЙ ЗАМЕНЫ ТИТЛОВ ---

def remove_titles(text):
    """
    ПОЛНОЕ УДАЛЕНИЕ ВСЕХ ТИТЛОВ И ЗАМЕНА ИХ НА ОБЫЧНЫЕ БУКВЫ
    """
    if not text:
        return text

    # Таблица замены титлов на буквы
    title_replacements = {
        'аⷣ': 'а', 'бⷣ': 'б', 'вⷣ': 'в', 'гⷣ': 'г', 'дⷣ': 'д',
        'еⷣ': 'е', 'жⷣ': 'ж', 'зⷣ': 'з', 'иⷣ': 'и', 'іⷣ': 'і',
        'кⷣ': 'к', 'лⷣ': 'л', 'мⷣ': 'м', 'нⷣ': 'н', 'оⷣ': 'о',
        'пⷣ': 'п', 'рⷣ': 'р', 'сⷣ': 'с', 'тⷣ': 'т', 'уⷣ': 'у',
        'фⷣ': 'ф', 'хⷣ': 'х', 'цⷣ': 'ц', 'чⷣ': 'ч', 'шⷣ': 'ш',
        'щⷣ': 'щ', 'ъⷣ': 'ъ', 'ыⷣ': 'ы', 'ьⷣ': 'ь', 'ѣⷣ': 'ѣ',
        'юⷣ': 'ю', 'яⷣ': 'я', 'ѧⷣ': 'ѧ', 'ѩⷣ': 'ѩ',
        'ⷢ҇': 'г', 'ⷭ҇': 'с', 'ⷣ҇': 'д', 'ⷡ҇': 'в', 'ⷦ҇': 'л',
        'ⷪ҇': 'о', 'ⷫ҇': 'п', 'ⷬ҇': 'р', 'ⷭ҇': 'с', 'ⷮ҇': 'т',
        'ⷯ҇': 'у', 'ⷴ҇': 'ц', 'ⷵ҇': 'ч', 'ⷹ҇': 'ѧ',
        '\u0483': '', '\u0484': '', '\u0485': '', '\u0486': '', '\u0487': '',
        '\u0300': '', '\u0301': '', '\u0302': '', '\u0303': '', '\u0304': '',
        '\u0306': '', '\u0307': '', '\u0308': '', '\u030A': '', '\u030B': '',
        '\u030C': '', '\u0331': '',
    }

    for old, new in title_replacements.items():
        text = text.replace(old, new)

    text = re.sub(r'[\u0300-\u036f\u0483-\u0489]', '', text)

    return text


def normalize_text(text):
    """Нормализация текста"""
    if not text:
        return ""
    text = text.lower()
    replacements = {
        'ѣ': 'е', 'ѳ': 'ф', 'ѵ': 'и', 'ѡ': 'о',
        '́': '', '̀': '', '̑': '', '҃': '',
        'ъ': 'ъ', 'ь': 'ь',
        'ꙗ': 'я', 'ѥ': 'е', 'ѕ': 'з',
        'ѯ': 'кс', 'ѱ': 'пс', 'ѿ': 'от',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def phonetic_normalize(text):
    """Фонетическая нормализация"""
    if not text:
        return ""
    text = normalize_text(text)
    replacements = {'о': 'а', 'е': 'и', 'я': 'а', 'ю': 'у'}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def edit_distance_similarity(s1, s2):
    """Вычисление схожести строк"""
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

        content = re.sub(r'<\?xml[^>]+encoding=["\']UTF-16["\'][^>]*\?>',
                         '<?xml version="1.0" encoding="UTF-8"?>', content, count=1)

        root = etree.fromstring(content.encode('utf-8'), parser=etree.XMLParser(recover=True))
        words = []

        for w in root.xpath('.//*[local-name()="w"]'):
            word_id = w.get('{http://www.w3.org/XML/1998/namespace}id') or w.get('id', 'n/a')
            lemma = (w.get('lemma') or "").strip().lower()
            text = unicodedata.normalize('NFC', "".join(w.xpath('text()')).strip())

            text = remove_titles(text)

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


# --- 5. КЛАССИФИКАЦИЯ ---

def classify_variant(main_word, witness_word):
    if not main_word or not witness_word:
        return "Пропуск"

    if main_word['normalized'] == witness_word['normalized']:
        if main_word['surface'] == witness_word['surface']:
            return "Идентично"
        else:
            return "Графическое"

    if main_word['phonetic'] == witness_word['phonetic']:
        return "Фонетическое"

    if main_word['lemma'] == witness_word['lemma'] and main_word['lemma']:
        if main_word['morph'] != witness_word['morph']:
            return "Морфологическое"
        else:
            return "Графическое"

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


# --- 6. ЭКСПОРТ В XML-TEI ---

def export_aligned_xml(base_words, aligned_words, base_filename, target_filename, variant_types):
    """
    Экспорт выровненных списков в формат XML-TEI
    """
    E = ElementMaker(namespace="http://www.tei-c.org/ns/1.0", nsmap={None: "http://www.tei-c.org/ns/1.0"})

    # Создаем TEI структуру
    tei = E.TEI(
        E.teiHeader(
            E.fileDesc(
                E.titleStmt(
                    E.title(f"Выровненный корпус: {base_filename} ↔ {target_filename}")
                ),
                E.publicationStmt(E.p("Создано Лингвистическим компаратором")),
                E.sourceDesc(
                    E.p(f"Основано на: {base_filename} и {target_filename}")
                )
            ),
            E.encodingDesc(
                E.classDecl(
                    E.taxonomy(
                        E.category(
                            E.catDesc("Лингвистический компаратор - выровненный корпус")
                        )
                    )
                )
            )
        ),
        E.text(
            E.body(
                E.div(
                    E.head("Выровненные тексты"),
                    type="aligned_corpus"
                )
            )
        )
    )

    # Создаем AB элемент для выровненного текста
    ab = E.ab()

    # Добавляем информацию о выравнивании
    ab.append(E.note("Выравнивание выполнено алгоритмом Нидлмана-Вунша"))
    ab.append(E.note(f"Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))

    # Добавляем выровненные слова
    for i, (base_word, aligned_word) in enumerate(zip(base_words, aligned_words)):
        # Создаем группу выравнивания
        alignment_group = E.milestone(unit="alignment", n=str(i))
        ab.append(alignment_group)

        # Базовое слово
        base_elem = E.w(base_word['surface'],
                        xml_id=base_word['id'],
                        lemma=base_word['lemma'],
                        type="base")

        # Добавляем морфологическую информацию
        for morph_name, morph_value in base_word['morph'].items():
            base_elem.append(E.fs(E.f(E.symbol(morph_value), name=morph_name)))

        ab.append(base_elem)

        # Целевое слово (если есть)
        if aligned_word:
            target_elem = E.w(aligned_word['surface'],
                              xml_id=aligned_word['id'],
                              lemma=aligned_word['lemma'],
                              type="target",
                              variant=variant_types.get(i, "unknown"))

            for morph_name, morph_value in aligned_word['morph'].items():
                target_elem.append(E.fs(E.f(E.symbol(morph_value), name=morph_name)))

            ab.append(target_elem)
        else:
            # Если слово отсутствует в целевом тексте
            ab.append(E.w("---", type="missing", variant="Пропуск"))

        # Разделитель между парами
        ab.append(E.pc(" "))

    # Добавляем AB в тело документа
    tei.find('.//{http://www.tei-c.org/ns/1.0}div').append(ab)

    # Преобразуем в строку с красивым форматированием
    xml_string = etree.tostring(tei, encoding='utf-8', pretty_print=True, xml_declaration=True).decode('utf-8')

    return xml_string


def export_all_aligned(data, edited_df):
    """
    Экспорт всех выровненных списков в ZIP-архив
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for idx, o_name in enumerate(data['others_list']):
            # Собираем выровненные слова
            base_words = data['base_words']
            aligned_words = []
            variant_types = {}

            for i, b_word in enumerate(base_words):
                m_word = data['all_aligns'][o_name].get(i)
                aligned_words.append(m_word)
                variant_types[i] = edited_df.iloc[i][f"Тип ({o_name})"]

            # Создаем XML
            xml_content = export_aligned_xml(
                base_words,
                aligned_words,
                data['main_file'],
                o_name,
                variant_types
            )

            # Добавляем в ZIP
            filename = f"aligned_{data['main_file'].replace('.xml', '')}_vs_{o_name.replace('.xml', '')}.xml"
            zip_file.writestr(filename, xml_content)

    zip_buffer.seek(0)
    return zip_buffer


# --- 7. ИНТЕРФЕЙС ---

st.title("Сравнительный анализ параллельных корпусов")

# ПОДРОБНАЯ ИНСТРУКЦИЯ
with st.expander("ПОДРОБНАЯ ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ (нажмите, чтобы развернуть)", expanded=True):
    st.markdown("""
    ### ОСНОВНЫЕ ВОЗМОЖНОСТИ ПРОГРАММЫ

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
    - **Кнопка "Скачать результаты (CSV)"** для сохранения в формате CSV
    - **Кнопка "Экспорт в XML-TEI"** для сохранения выровненных списков в формате XML-TEI (ZIP-архив)

    ---

    ### 💾 ФОРМАТЫ ЭКСПОРТА

    **CSV:** Таблица с результатами сравнения для анализа в Excel/Google Sheets

    **XML-TEI:** Выровненные списки в формате TEI (Text Encoding Initiative) для дальнейшей обработки в лингвистических программах. Экспортируется ZIP-архив с отдельными XML-файлами для каждой пары сравнения.
    """)

if 'raw_data' not in st.session_state:
    st.session_state.raw_data = {}

with st.sidebar:
    st.header("📁 Загрузка XML файлов")
    uploaded_files = st.file_uploader("Выберите XML файлы", type="xml", accept_multiple_files=True)
    if uploaded_files:
        for f in uploaded_files:
            if f.name not in st.session_state.raw_data:
                with st.spinner(f"Загрузка {f.name}..."):
                    st.session_state.raw_data[f.name] = parse_xml_tei(f)

        file_names = list(st.session_state.raw_data.keys())
        if file_names:
            main_file = st.selectbox("📌 Выберите эталонный список", file_names)
            st.success(f"✅ Загружено файлов: {len(file_names)}")

# ЗАПУСК АНАЛИЗА
if 'raw_data' in st.session_state and st.session_state.raw_data and st.button("🚀 Запустить сравнение", type="primary"):
    base_words = st.session_state.raw_data[main_file]
    others = [n for n in st.session_state.raw_data.keys() if n != main_file]

    if others:
        with st.spinner("🔄 Синхронизация текстов..."):
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
                    row[f"Тип ({o_name})"] = classify_variant(b_word, m_word) if m_word else "Пропуск"
                final_rows.append(row)
            st.session_state.comp_df = pd.DataFrame(final_rows)
            st.session_state.others_list = others
            st.session_state.main_file = main_file
            st.session_state.base_words = base_words
            st.session_state.all_aligns = all_aligns
            st.success("✅ Сравнение завершено!")
    else:
        st.warning("⚠️ Загрузите хотя бы два файла для сравнения.")

# ВЫВОД РЕЗУЛЬТАТОВ
if 'comp_df' in st.session_state:
    df = st.session_state.comp_df
    main_file = st.session_state.main_file

    st.subheader("📝 Таблица-редактор")
    st.info(
        "💡 **Совет:** Нажмите на значок ☰ в правом верхнем углу таблицы, чтобы скрыть ненужные колонки. Используйте Ctrl+F для поиска. Дважды кликните по ячейке 'Тип' для изменения категории.")


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
                elif val == "Пропуск":
                    styles[i] = 'background-color: #d7ccc8'
        return styles


    edited_df = st.data_editor(df.style.apply(style_table, axis=1), use_container_width=True, height=500)

    # КОНТЕКСТ
    st.divider()
    st.subheader("🔍 Контекст слова (10 слов до и после)")

    col1, col2 = st.columns([1, 2])
    with col1:
        if not edited_df.empty:
            selected_row = st.number_input("Выберите строку для просмотра контекста:", 0, len(edited_df) - 1, 0,
                                           key="context_row")

    with col2:
        st.markdown("**Выберите текст для просмотра:**")
        context_options = [f"ЭТАЛОН ({main_file})"] + [f"Слово ({name})" for name in st.session_state.others_list]
        context_texts = st.radio(
            "Источник контекста:",
            options=context_options,
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
                word_index = next((i for i, w in enumerate(target_words) if w['surface'] == aligned_word['surface']),
                                  selected_row)
                words_list = target_words
                source_name = ms_name
            else:
                words_list = []
                word_index = 0

        if words_list and word_index < len(words_list):
            before, after = get_context(words_list, word_index)

            context_html = '<div class="context-box">'
            context_html += '<b>📖 Контекст (10 слов до и после):</b><br><br>'
            if before:
                context_html += '<span style="color: #666;">... ' + ' '.join(
                    [w['surface'] for w in before]) + ' </span>'
            context_html += f'<span style="background-color: #1E88E5; color: white; padding: 2px 8px; border-radius: 20px; font-weight: bold;">{selected_word}</span>'
            if after:
                context_html += '<span style="color: #666;"> ' + ' '.join([w['surface'] for w in after]) + ' </span>'
            context_html += f'<br><br><span style="font-size: 12px; color: #888;">📌 Источник: {source_name}</span>'
            context_html += '</div>'
            st.markdown(context_html, unsafe_allow_html=True)
        else:
            st.info("⚠️ Слово не найдено в выбранном списке для отображения контекста.")

    # СТАТИСТИКА
    st.divider()
    st.subheader("📈 Статистика по текстам")

    for o_name in st.session_state.others_list:
        st.markdown(f"**📄 Текст: {o_name}**")
        type_col = f"Тип ({o_name})"
        counts = edited_df[type_col].value_counts()
        total = len(edited_df)
        identical = counts.get("Идентично", 0)
        diffs = total - identical
        similarity = round(identical / total * 100, 1) if total > 0 else 0

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Всего слов", total)
            st.metric("Идентично", f"{identical} ({similarity}%)")
            st.metric("Различий", f"{diffs} ({100 - similarity}%)")
        with col2:
            st.progress(similarity / 100, text=f"Сходство: {similarity}%")
            st.caption("Типы различий:")
            for t_name in ["Лексическое", "Морфологическое", "Графическое", "Фонетическое", "Пропуск"]:
                c_val = counts.get(t_name, 0)
                if c_val > 0:
                    st.write(f"- {t_name}: {c_val}")
        st.divider()

    # ЭКСПОРТ
    st.divider()
    st.subheader("📥 Экспорт результатов")

    col_export1, col_export2, col_export3 = st.columns(3)

    with col_export1:
        csv = edited_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📊 Скачать CSV",
            csv,
            f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
            use_container_width=True,
            help="Экспорт таблицы в формате CSV для анализа в Excel"
        )

    with col_export2:
        # Экспорт в XML-TEI
        export_data = {
            'others_list': st.session_state.others_list,
            'base_words': st.session_state.base_words,
            'all_aligns': st.session_state.all_aligns,
            'main_file': st.session_state.main_file
        }

        zip_buffer = export_all_aligned(export_data, edited_df)

        st.download_button(
            "📚 Экспорт в XML-TEI (ZIP)",
            zip_buffer,
            f"aligned_corpora_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            "application/zip",
            use_container_width=True,
            help="Экспорт выровненных списков в формате XML-TEI (ZIP-архив с отдельными файлами для каждой пары)"
        )

    with col_export3:
        # Кнопка сброса
        if st.button("🔄 Новое сравнение", use_container_width=True):
            for key in ['comp_df', 'others_list', 'main_file', 'base_words', 'all_aligns']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

else:
    st.info("👈 Загрузите XML-файлы в боковой панели и нажмите кнопку 'Запустить сравнение'")