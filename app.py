import streamlit as st
import pandas as pd
from lxml import etree
import re
import unicodedata
import io

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


# --- 2. ЯДРО ОБРАБОТКИ ---

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
                    morph_val = sym_vals[0]
                    morph[name] = morph_val.strip()

            if text:
                words.append({'id': word_id, 'text': text, 'lemma': lemma, 'morph': morph})
        return words
    except Exception as e:
        st.error(f"Ошибка в файле {file.name}: {e}");
        return []


def align_pair(base_list, target_list):
    n, m = len(base_list), len(target_list)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): dp[i][0] = i * -2
    for j in range(m + 1): dp[0][j] = j * -2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match_score = 5 if base_list[i - 1]['lemma'] == target_list[j - 1]['lemma'] else (
                -1 if base_list[i - 1]['text'] != target_list[j - 1]['text'] else 3)
            dp[i][j] = max(dp[i - 1][j - 1] + match_score, dp[i - 1][j] - 2, dp[i][j - 1] - 2)
    matches = {}
    i, j = n, m
    while i > 0 and j > 0:
        current_score = dp[i][j]
        match_score = 5 if base_list[i - 1]['lemma'] == target_list[j - 1]['lemma'] else (
            -1 if base_list[i - 1]['text'] != target_list[j - 1]['text'] else 3)
        if current_score == dp[i - 1][j - 1] + match_score:
            matches[i - 1] = target_list[j - 1];
            i -= 1;
            j -= 1
        elif current_score == dp[i - 1][j] - 2:
            matches[i - 1] = None;
            i -= 1
        else:
            j -= 1
    return matches


def get_diff_type(w1, w2):
    if not w1 or not w2:
        return "Пропуск"

    if w1['text'] == w2['text']:
        if w1['morph'] == w2['morph']:
            return "Идентично"
        else:
            return "Морфологическое"

    if w1['lemma'] != w2['lemma'] and w1['lemma'] and w2['lemma']:
        return "Лексическое"

    if w1['lemma'] == w2['lemma'] and w1['lemma']:
        return "Графическое/Фон."

    if w1['morph'] != w2['morph'] and w1['morph'] and w2['morph']:
        return "Морфологическое"

    return "Графическое/Фон."


def get_context(words, index, context_size=10):
    start = max(0, index - context_size)
    end = min(len(words), index + context_size + 1)

    context_before = words[start:index]
    context_after = words[index + 1:end]

    return context_before, context_after


# --- 3. ИНТЕРФЕЙС ---

st.title("Сравнительный анализ параллельных корпусов")

# БЛОК ИНСТРУКЦИИ
with st.expander("📖 ПОДРОБНАЯ ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ (нажмите, чтобы развернуть)", expanded=True):
    st.markdown("""
    ### 📌 ОСНОВНЫЕ ВОЗМОЖНОСТИ ПРОГРАММЫ

    Данная программа позволяет сравнивать различные списки древнерусских евангельских текстов, автоматически выявлять разночтения и редактировать результаты.

    ---

    ### 🚀 ШАГ 1: ЗАГРУЗКА ФАЙЛОВ
    1. В левой боковой панели (**Sidebar**) нажмите **"Browse files"** или **"Загрузить XML"**
    2. Выберите один или несколько XML-файлов с евангельскими списками
    3. После загрузки в выпадающем списке **"Эталонный список"** выберите основной текст (относительно него будет проводиться сравнение)

    ---

    ### 🔄 ШАГ 2: ЗАПУСК СРАВНЕНИЯ
    Нажмите кнопку **"🚀 Запустить сравнение"** в левой боковой панели.
    Программа автоматически:
    - Сопоставит слова из разных списков (алгоритм глобального выравнивания)
    - Определит типы разночтений (Лексические, Морфологические, Графические/Фонетические)
    - Построит таблицу-редактор

    ---

    ### 📊 ШАГ 3: РАБОТА С ТАБЛИЦЕЙ-РЕДАКТОРОМ

    **🖱️ Основные действия с таблицей:**

    | Действие | Как выполнить |
    |----------|---------------|
    | **Сортировка данных** | Нажмите на заголовок любой колонки (▲▼) |
    | **Поиск слова** | Нажмите **Ctrl+F** (или Cmd+F на Mac) для поиска по таблице |
    | **Фильтрация** | Нажмите на значок фильтра (≡) в заголовке колонки |
    | **Скрыть колонку** | Нажмите на значок "☰" в правом верхнем углу таблицы и снимите галочку с ненужной колонки |
    | **Редактировать ячейку** | Дважды кликните по любой ячейке в колонке "Тип (...)" и выберите нужное значение |
    | **Изменение ширины колонки** | Перетащите границу между заголовками колонок |

    **📝 Типы разночтений (цветовая индикация):**
    - 🟢 **Идентично** (зеленый) — слова полностью совпадают
    - 🔴 **Лексическое** (красный) — разные слова (разные леммы)
    - 🟡 **Морфологическое** (желтый) — разные грамматические формы
    - 🔵 **Графическое/Фонетическое** (голубой) — разное написание при той же лемме

    **💡 Важно:** Вы можете изменять тип разночтения вручную! Если вы не согласны с автоматическим определением, просто дважды кликните по ячейке в колонке "Тип" и выберите другой вариант. Статистика ниже обновится автоматически.

    ---

    ### 🔍 ШАГ 4: ПРОСМОТР КОНТЕКСТА СЛОВА

    Под таблицей находится блок **"🔍 Контекст слова"**:

    1. **Выберите строку** — введите номер строки, контекст которой хотите увидеть
    2. **Выберите источник** — из какого списка показывать контекст (эталон или любой другой)

    Программа покажет **10 слов до и 10 слов после** выбранного слова, а само слово будет выделено синим цветом.

    ---

    ### 📈 ШАГ 5: АНАЛИЗ СТАТИСТИКИ

    В нижней части страницы отображается статистика по каждому списку:
    - Общее количество слов
    - Процент идентичных слов (сходство текстов)
    - Количество каждого типа разночтений

    Статистика обновляется автоматически при любых изменениях в таблице-редакторе!

    ---

    ### 💾 ШАГ 6: ЭКСПОРТ РЕЗУЛЬТАТОВ

    В самом низу страницы есть кнопки для сохранения результатов:
    - **📥 Скачать результаты (CSV)** — для открытия в Excel или LibreOffice
    - **📊 Скачать Excel** — формат с сохранением форматирования

    ---

    ### ❓ ЧАСТЫЕ ВОПРОСЫ

    **Вопрос:** Почему одинаковые слова иногда определяются как "Морфологическое разночтение"?  
    **Ответ:** В XML-файлах слова могут иметь разные морфологические теги (например, разные падежи или числа). Программа учитывает эти различия.

    **Вопрос:** Можно ли добавить свои XML-файлы?  
    **Ответ:** Да! Просто загрузите их через кнопку загрузки файлов.

    **Вопрос:** Как быстро найти конкретное слово во всех списках?  
    **Ответ:** Используйте **Ctrl+F** в таблице-редакторе.

    **Вопрос:** Что делать, если отображаются квадратики вместо букв?  
    **Ответ:** Установите шрифт **BukyVede** или **Menaion Unicode** на вашем компьютере.
    """)

if 'raw_data' not in st.session_state: st.session_state.raw_data = {}
if 'context_word' not in st.session_state: st.session_state.context_word = None
if 'context_ms' not in st.session_state: st.session_state.context_ms = None

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
                # Новый порядок колонок: ID, Лемма, ЭТАЛОН, затем остальные
                row = {
                    "ID": b_word['id'],
                    "Лемма": b_word['lemma'],
                    f"ЭТАЛОН ({main_file})": b_word['text'],
                }
                for o_name in others:
                    m_word = all_aligns[o_name].get(i)
                    row[f"Слово ({o_name})"] = m_word['text'] if m_word else "---"
                    row[f"Тип ({o_name})"] = get_diff_type(b_word, m_word)
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
        "💡 **Совет:** Нажмите на значок ☰ в правом верхнем углу таблицы, чтобы скрыть ненужные колонки. Используйте Ctrl+F для поиска по таблице.")


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
                elif val == "Графическое/Фон.":
                    styles[i] = 'background-color: #e1f5fe'
                elif val == "Идентично":
                    styles[i] = 'background-color: #c8e6c9'
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

    # Показываем контекст выбранного слова
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
                    if w['text'] == aligned_word['text']:
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
                    context_html += f'{w["text"]} '
                context_html += '</span>'

            context_html += f'<span style="background-color: #1E88E5; color: white; padding: 2px 8px; border-radius: 20px; font-weight: bold;">{selected_word}</span>'

            if context_after:
                context_html += '<span style="color: #666;"> '
                for w in context_after:
                    context_html += f'{w["text"]} '
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
                "Графическое/Фон.": "✍️ Разное написание",
                "Пропуск": "❌ Слово отсутствует"
            }

            for t_name, t_desc in diff_types.items():
                c_val = counts.get(t_name, 0)
                if c_val > 0:
                    st.write(f"- **{t_name}** ({t_desc}): {c_val}")

            st.markdown("</div>", unsafe_allow_html=True)

    # ЭКСПОРТ
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        csv = edited_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Скачать результаты (CSV)", csv, "aligned_corpus.csv", "text/csv",
                           use_container_width=True)

    with col2:
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                edited_df.to_excel(writer, sheet_name='Alignment', index=False)
            st.download_button("📊 Скачать Excel", output.getvalue(), "aligned_corpus.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
        except Exception as e:
            st.warning(f"Экспорт в Excel временно недоступен. Используйте CSV.")

else:
    st.info("👈 Загрузите XML-файлы и нажмите кнопку 'Запустить сравнение' в боковой панели.")