import io
import pandas as pd
import streamlit as st
import requests
import firebase_admin
from firebase_admin import credentials, db, auth

# Streamlit app configuration and title
st.set_page_config(page_title="Anomaly Detection", page_icon="📊")
st.title("Anomaly Detection and Dataset Combination")

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://data-vision-4b7ba-default-rtdb.firebaseio.com"
    })

# Firebase Authentication Helper Functions
def register_user(email, password):
    try:
        user = auth.create_user(email=email, password=password)
        return {"status": "success", "message": f"User {email} registered successfully!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def login_user(email, password):
    ref = db.reference(f"users/{email.replace('.', ',')}").get()
    if ref and ref["password"] == password:
        return {"status": "success", "message": "Login successful!"}
    return {"status": "error", "message": "Invalid credentials."}

def save_user_to_db(email, password):
    ref = db.reference(f"users/{email.replace('.', ',')}")
    ref.set({"email": email, "password": password})

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["email"] = ""
if "datasets" not in st.session_state:
    st.session_state["datasets"] = {}  # Dictionary to store uploaded and combined datasets
if "combined_df" not in st.session_state:
    st.session_state["combined_df"] = None

# Login and registration workflow
if not st.session_state["logged_in"]:
    st.subheader("Login")
    login_email = st.text_input("Email")
    login_password = st.text_input("Password", type="password")
    if st.button("Login"):
        result = login_user(login_email, login_password)
        if result["status"] == "success":
            st.session_state["logged_in"] = True
            st.session_state["email"] = login_email
            st.success(result["message"])
            st.rerun()
        else:
            st.error(result["message"])

    st.subheader("Register")
    reg_email = st.text_input("New Email")
    reg_password = st.text_input("New Password", type="password")
    if st.button("Register"):
        result = register_user(reg_email, reg_password)
        if result["status"] == "success":
            save_user_to_db(reg_email, reg_password)
            st.success(result["message"])
        else:
            st.error(result["message"])
else:
    # Main app functionality after login
    st.success(f"Welcome, {st.session_state['email']}!")
    if st.button("Logout"):
        st.session_state["logged_in"] = False
        st.session_state["email"] = ""
        st.rerun()

    # Upload two CSV files
    st.write("### Upload Two CSV Files to Combine:")
    uploaded_file_1 = st.file_uploader("Upload First CSV File", type=["csv"], key="file_1")
    uploaded_file_2 = st.file_uploader("Upload Second CSV File", type=["csv"], key="file_2")

    # Check if both files are uploaded
    if uploaded_file_1:
        try:
            df1 = pd.read_csv(uploaded_file_1)
            st.session_state["datasets"]["Dataset 1"] = df1
        except Exception as e:
            st.error(f"Error loading the first dataset: {e}")
    if uploaded_file_2:
        try:
            df2 = pd.read_csv(uploaded_file_2)
            st.session_state["datasets"]["Dataset 2"] = df2
        except Exception as e:
            st.error(f"Error loading the second dataset: {e}")

    # Allow editing of all uploaded datasets
    for dataset_name, dataset_df in st.session_state["datasets"].items():
        st.write(f"### {dataset_name} (Editable)")
        editable_df = st.data_editor(dataset_df, num_rows="dynamic", use_container_width=True)
        st.session_state["datasets"][dataset_name] = editable_df

    # Combine datasets if both are uploaded
    if "Dataset 1" in st.session_state["datasets"] and "Dataset 2" in st.session_state["datasets"]:
        combine_prompt = (
            "Combine the following two datasets into a single cohesive dataset. "
            "Ensure all matching columns are aligned, and any non-overlapping columns are included. "
            "Return the result as CSV text."
        )
        query_dataset_1 = st.session_state["datasets"]["Dataset 1"].to_dict(orient="records")
        query_dataset_2 = st.session_state["datasets"]["Dataset 2"].to_dict(orient="records")

        payload = {
            "messages": [
                {"role": "system", "content": combine_prompt},
                {"role": "user", "content": f"Dataset 1: {query_dataset_1}\nDataset 2: {query_dataset_2}"}
            ],
            "model": "grok-beta",
            "stream": False,
            "temperature": 0,
        }

        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer xai-4slNih4UsLZbFmgGKa8sEAn3IEbH01tWdBotTPS1CCxDIryljhcnl6ak6Kn4ega4bgrLIzkotTapmloC",
        }

        if st.button("Combine Datasets"):
            response = requests.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                response_data = response.json()
                content = response_data["choices"][0]["message"]["content"]

                try:
                    if "```csv" in content:
                        csv_start = content.find("```csv") + len("```csv")
                        csv_end = content.find("```", csv_start)
                        csv_data = content[csv_start:csv_end].strip()

                        # Parse the CSV text into a Pandas DataFrame
                        st.session_state["combined_df"] = pd.read_csv(io.StringIO(csv_data))

                        st.write("### Combined Dataset (Editable)")
                        st.session_state["combined_df"] = st.data_editor(
                            st.session_state["combined_df"],
                            num_rows="dynamic",
                            use_container_width=True,
                        )

                        # Save combined dataset for further use
                        st.session_state["datasets"]["Combined Dataset"] = st.session_state["combined_df"]

                        # Option to download the combined dataset
                        csv = st.session_state["combined_df"].to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Download Combined Dataset",
                            data=csv,
                            file_name="combined_dataset.csv",
                            mime="text/csv",
                        )
                    else:
                        st.error("CSV data not found in the response.")
                except Exception as e:
                    st.error(f"Error parsing the combined CSV: {e}")
            else:
                st.error(f"Error: {response.status_code}")
                st.text(response.text)

    # Analyze combined dataset if available
    if st.session_state["combined_df"] is not None:
        st.write("### Analyze Combined Dataset for Anomalies")
        query_combined_dataset = st.session_state["combined_df"].to_dict(orient="records")

        anomaly_payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Analyze the following dataset for anomalies. "
                        "Detect issues such as duplicate records, mismatched information, fraudulent patterns, "
                        "and compliance violations. Return a detailed report."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Dataset: {query_combined_dataset}",
                },
            ],
            "model": "grok-beta",
            "stream": False,
            "temperature": 0,
        }

        if st.button("Analyze Combined Dataset"):
            anomaly_response = requests.post(url, json=anomaly_payload, headers=headers)

            if anomaly_response.status_code == 200:
                anomaly_content = anomaly_response.json()["choices"][0]["message"]["content"]
                st.markdown(f"### Anomaly Analysis Report:\n{anomaly_content}")
            else:
                st.error(f"Error: {anomaly_response.status_code}")
                st.text(anomaly_response.text)
