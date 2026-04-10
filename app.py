import streamlit as st
import pandas as pd
from lxml import etree
import re
import unicodedata

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
            morph = {f.get('name'): f.xpath('.//*[local-name()="symbol"]/@value')[0]
                     for f in w.xpath('.//*[local-name()="f"]')
                     if f.xpath('.//*[local-name()="symbol"]/@value')}
            if text: words.append({'id': word_id, 'text': text, 'lemma': lemma, 'morph': morph})
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
    if not w1 or not w2: return "Пропуск"
    if w1['lemma'] != w2['lemma'] and w1['lemma'] and w2['lemma']: return "Лексическое"
    if w1['morph'] != w2['morph']: return "Морфологическое"
    if w1['text'] != w2['text']: return "Графическое/Фон."
    return "Идентично"


# --- 3. ИНТЕРФЕЙС ---

st.title("☦ Сравнительный анализ параллельных корпусов")

# БЛОК ИНСТРУКЦИИ
with st.expander("📖 Инструкция пользователя", expanded=True):
    st.markdown("""
    1. **Загрузите XML-файлы** в боковой панели.
    2. **Выберите Эталон**: основной текст, с которым будет идти сравнение.
    3. **Нажмите кнопку '🚀 Запустить сравнение'**.
    4. **Редактируйте**: если вы не согласны с типом разночтения, измените его в таблице 'Редактор'.
    5. **Смотрите статистику**: в самом низу отображается процент сходства текстов, рассчитанный по вашим правкам.
    """)

if 'raw_data' not in st.session_state: st.session_state.raw_data = {}

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
                row = {"ID": b_word['id'], f"ЭТАЛОН ({main_file})": b_word['text'], "Лемма": b_word['lemma']}
                for o_name in others:
                    m_word = all_aligns[o_name].get(i)
                    row[f"Слово ({o_name})"] = m_word['text'] if m_word else "---"
                    row[f"Тип ({o_name})"] = get_diff_type(b_word, m_word)
                final_rows.append(row)
            st.session_state.comp_df = pd.DataFrame(final_rows)
            st.session_state.others_list = others
    else:
        st.warning("Загрузите хотя бы два файла.")

# ВЫВОД РЕЗУЛЬТАТОВ (Блок появляется только после нажатия кнопки)
if 'comp_df' in st.session_state:
    df = st.session_state.comp_df

    st.subheader("📝 Таблица-редактор")
    st.info("Вы можете менять значения в колонках 'Тип', статистика ниже обновится автоматически.")


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
        return styles


    # РЕДАКТОР (важно: статистика будет строиться на основе edited_df)
    edited_df = st.data_editor(df.style.apply(style_table, axis=1), use_container_width=True, height=400)

    # ЛУПА (с защитой от ошибки StreamlitValueAboveMaxError)
    st.divider()
    st.subheader("🔍 Лупа")
    if not edited_df.empty:
        c1, c2 = st.columns([1, 2])
        with c1:
            # Защита: max_value не может быть меньше min_value
            max_idx = max(0, len(edited_df) - 1)
            rid = st.number_input("Строка:", 0, max_idx, 0)
            cname = st.selectbox("Колонка:", [c for c in edited_df.columns if "Слово" in c or "ЭТАЛОН" in c])
        with c2:
            st.markdown(f'<div class="big-word">{edited_df.iloc[rid][cname]}</div>', unsafe_allow_html=True)

    # СТАТИСТИКА (Динамическая)
    st.divider()
    st.subheader("📈 Статистика по текстам")

    others = st.session_state.others_list
    stat_cols = st.columns(len(others))

    for idx, o_name in enumerate(others):
        with stat_cols[idx]:
            st.markdown(f"<div class='stat-card'><b>Текст: {o_name}</b>", unsafe_allow_html=True)
            type_col = f"Тип ({o_name})"
            counts = edited_df[type_col].value_counts()

            total = len(edited_df)
            identical = counts.get("Идентично", 0)
            diffs = total - identical

            st.write(f"✅ Идентично: **{identical}** ({round(identical / total * 100, 1)}%)")
            st.write(f"❌ Различий: **{diffs}** ({round(diffs / total * 100, 1)}%)")

            # Таблица типов
            st.markdown("---")
            st.caption("Типы различий:")
            for t_name in ["Лексическое", "Морфологическое", "Графическое/Фон.", "Пропуск"]:
                c_val = counts.get(t_name, 0)
                if c_val > 0:
                    st.write(f"- {t_name}: {c_val}")
            st.markdown("</div>", unsafe_allow_html=True)

    # ЭКСПОРТ
    csv = edited_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Скачать результаты (CSV)", csv, "aligned_corpus.csv", "text/csv")

else:
    st.info("👈 Загрузите файлы и нажмите кнопку 'Запустить сравнение' в боковой панели.")