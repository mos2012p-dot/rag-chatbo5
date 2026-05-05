import streamlit as st
import time
from openai import OpenAI

# إعداد واجهة المستخدم
st.set_page_config(page_title="AI RAG Chatbot", layout="centered")
st.title("🤖 Chat with your Documents")

# --- الشريط الجانبي للإعدادات الأمنة ---
with st.sidebar:
    st.header("Credentials")
    api_key = st.text_input("OpenAI API Key", type="password")
    assistant_id = st.text_input("Assistant ID", type="password")
    
    st.divider()
    st.header("Document Upload")
    uploaded_file = st.file_uploader("Upload a file (PDF, TXT, etc.)", type=['pdf', 'txt', 'docx'])

# التحقق من وجود المدخلات الأساسية
if not api_key or not assistant_id:
    st.info("Please enter your API Key and Assistant ID to start.", icon="🔑")
    st.stop()

# تهيئة عميل OpenAI
client = OpenAI(api_key=api_key)

# --- إدارة الجلسة (Session State) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id

# --- معالجة رفع الملفات ---
if uploaded_file and "file_uploaded" not in st.session_state:
    with st.spinner("Processing document..."):
        # 1. رفع الملف إلى OpenAI
        file_obj = client.files.create(file=uploaded_file, purpose='assistants')
        
        # 2. إضافة الملف إلى الـ Assistant (عبر Vector Store)
        # ملاحظة: نفترض هنا أن الـ Assistant لديه خاصية 'file_search' مفعلة
        client.beta.assistants.update(
            assistant_id=assistant_id,
            tool_resources={"file_search": {"vector_store_ids": []}} # يمكن تخصيص Vector Store هنا
        )
        
        # ربط الملف بالرسالة الأولى في الـ Thread
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content="I have uploaded a document. Please use it to answer my questions.",
            attachments=[{"file_id": file_obj.id, "tools": [{"type": "file_search"}]}]
        )
        st.session_state.file_uploaded = True
        st.success("File uploaded and linked successfully!")

# --- واجهة الدردشة (Chat Interface) ---

# عرض الرسائل السابقة
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# استقبال سؤال المستخدم
if prompt := st.chat_input("Ask something about your document..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # إرسال الرسالة إلى OpenAI
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt
    )

    # تشغيل الـ Assistant
    run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread_id,
        assistant_id=assistant_id
    )

    # انتظار الرد (Polling)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            while run.status != "completed":
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id
                )
            
            # جلب الرسائل الجديدة
            messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
            assistant_response = messages.data[0].content[0].text.value
            
            st.markdown(assistant_response)
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
