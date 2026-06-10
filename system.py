
import streamlit as st
from google import genai
import pandas as pd
import json
import re
from docx import Document

# =========================
# CONFIG
# =========================

MODEL_NAME = "gemini-2.5-flash"

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"]
)

# =========================
# UI
# =========================

st.set_page_config(
    page_title="MakeUrQuiz",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ MakeUrQuiz")
st.caption("Made by Đăng Khoa 🔰")
st.caption("Tạo bộ câu hỏi từ tài liệu học tập")

# =========================
# INPUT DATA
# =========================

st.header("📚 Nguồn dữ liệu")

col1, col2 = st.columns([2, 1])

with col1:

    source_type = st.selectbox(
        "Chọn nguồn dữ liệu",
        [
            "Dán văn bản",
            "Upload file"
        ]
    )

    raw_text = ""

    if source_type == "Dán văn bản":
        raw_text = st.text_area(
            "Dán nội dung tại đây",
            height=300
        )

        MAX_CHARS = 10000
        if len(raw_text) > MAX_CHARS:
            st.warning("Dữ liệu quá dài, chỉ lấy 10.000 ký tự đầu.")
            raw_text = raw_text[:MAX_CHARS]
    else:
        uploaded_file = st.file_uploader(
            "Upload file",
            type=["txt", "docx"]
        )

        if uploaded_file:

            try:

                if uploaded_file.name.endswith(".docx"):

                    doc = Document(uploaded_file)

                    raw_text = "\n".join(
                        para.text
                        for para in doc.paragraphs
                    )

                else:
                    raw_text = uploaded_file.read().decode("utf-8")

                MAX_CHARS = 10000

                if len(raw_text) > MAX_CHARS:
                    st.warning(
                        f"File quá dài ({len(raw_text):,} ký tự). "
                        f"Chỉ lấy {MAX_CHARS:,} ký tự đầu."
                    )
                    raw_text = raw_text[:MAX_CHARS]

            except Exception as e:
                st.error(f"Lỗi đọc file: {e}")

with col2:

    q_type = st.selectbox(
        "Loại câu hỏi",
        [
            "Trắc nghiệm (MCQ)",
            "Tự luận",
            "True/False",
            "Mix"
        ]
    )

    num_q = st.number_input(
        "Số lượng câu hỏi",
        min_value=1,
        max_value=100,
        value=4
    )

    difficulty = st.selectbox(
        "Độ khó",
        [
            "Dễ",
            "Trung bình",
            "Khó"
        ]
    )

    generate_btn = st.button(
        "🚀 Tạo câu hỏi",
        use_container_width=True
    )


# =========================
# PROMPT
# =========================

def make_prompt(text, q_type, num_q, difficulty):

    if q_type == "Trắc nghiệm (MCQ)":

        instruction = f"""
Tạo {num_q} câu hỏi trắc nghiệm.

Độ khó: {difficulty}

Mỗi câu gồm:
- question
- options (A,B,C,D)
- answer
- explanation

Trả về JSON LIST duy nhất.
"""

    elif q_type == "Tự luận":

        instruction = f"""
Tạo {num_q} câu hỏi tự luận.

Độ khó: {difficulty}

Mỗi câu gồm:
- question
- hint

Trả về JSON LIST duy nhất.
"""

    elif q_type == "True/False":

        instruction = f"""
Tạo {num_q} câu hỏi đúng/sai.

Độ khó: {difficulty}

Mỗi câu gồm:
- question
- answer
- explanation

Trả về JSON LIST duy nhất.
"""

    else:

        instruction = f"""
Tạo {num_q} câu hỏi hỗn hợp.

Độ khó: {difficulty}

Mỗi item gồm:
- type
- question
- options (nếu có)
- answer
- explanation

Trả về JSON LIST duy nhất.
"""

    return f"""
{instruction}

NỘI DUNG:

{text}

CHỈ TRẢ VỀ JSON.
KHÔNG markdown.
KHÔNG giải thích thêm.
"""


# =========================
# GENERATE
# =========================

if generate_btn:

    if len(raw_text.strip()) < 20:
        st.warning("Vui lòng nhập ít nhất 20 ký tự.")
        st.stop()

    with st.spinner("Đang tạo câu hỏi..."):

        try:

            prompt = make_prompt(
                raw_text,
                q_type,
                int(num_q),
                difficulty
            )

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

            model_text = response.text.strip()

            # Xử lý nếu model trả markdown
            model_text = re.sub(
                r"^```json",
                "",
                model_text
            )

            model_text = re.sub(
                r"```$",
                "",
                model_text
            ).strip()

            q_list = json.loads(model_text)

            rows = []

            for idx, item in enumerate(q_list, start=1):

                options = item.get("options", {})

                if isinstance(options, dict):

                    a = options.get("A", "")
                    b = options.get("B", "")
                    c = options.get("C", "")
                    d = options.get("D", "")

                else:

                    a = b = c = d = ""

                rows.append(
                    {
                        "id": idx,
                        "type": item.get("type", q_type),
                        "question": item.get("question", ""),
                        "A": a,
                        "B": b,
                        "C": c,
                        "D": d,
                        "answer": item.get("answer", ""),
                        "explanation": item.get(
                            "explanation",
                            item.get("hint", "")
                        )
                    }
                )

            df_out = pd.DataFrame(rows)

            st.success(
                f"Đã tạo {len(df_out)} câu hỏi."
            )

            st.subheader("📋 Preview")

            st.dataframe(
                df_out,
                use_container_width=True
            )

            txt_content = ""

            for i, item in enumerate(q_list, start=1):

                txt_content += f"Câu {i}: {item.get('question', '')}\n"

                options = item.get("options", {})

                if isinstance(options, dict):
                    txt_content += f"A. {options.get('A', '')}\n"
                    txt_content += f"B. {options.get('B', '')}\n"
                    txt_content += f"C. {options.get('C', '')}\n"
                    txt_content += f"D. {options.get('D', '')}\n"

                txt_content += f"Đáp án: {item.get('answer', '')}\n"

                if item.get("explanation"):
                    txt_content += f"Giải thích: {item.get('explanation')}\n"

                if item.get("hint"):
                    txt_content += f"Gợi ý: {item.get('hint')}\n"

                txt_content += "\n" + "=" * 50 + "\n\n"

            st.download_button(
                "⬇️ Tải TXT",
                data=txt_content,
                file_name="questions.txt",
                mime="text/plain"
            )

        except Exception as e:

            st.error(f"Lỗi: {e}")

