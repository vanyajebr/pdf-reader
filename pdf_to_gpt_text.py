import streamlit as st
import pdfplumber
import io
from typing import List, Dict, Tuple


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract plain text from a PDF file given as bytes.
    """
    text_chunks: List[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)
    return "\n".join(text_chunks)


def parse_filename(filename: str) -> Tuple[str, str, str]:
    """
    Parse a filename like SC_payslip_2025-03.pdf into (client_id, doc_type, label).

    Returns:
        client_id: e.g. 'SC'
        doc_type: 'payslip' or 'statement' (falls back to 'unknown')
        label: e.g. '2025-03' or '2025-03-08_2025-04-08'
    """
    name = filename.rsplit(".", 1)[0]
    parts = name.split("_")
    if len(parts) < 3:
        return "", "unknown", name

    client_id = parts[0]
    doc_type = parts[1]
    label = "_".join(parts[2:])
    return client_id, doc_type, label


def main():
    st.title("PDF → Structured Text for GPT (Payslips + Bank Statements)")

    st.markdown(
        """
        ### 1. Rename your files before upload

        Use a consistent pattern so GPT can understand what is what:

        - Payslips: `SC_payslip_2025-03.pdf`, `SC_payslip_2025-04.pdf`  
        - Bank statements: `SC_statement_2025-03-08_2025-04-08.pdf`,
          `SC_statement_2025-04-09_2025-05-08.pdf`  

        Where:
        - `SC` is the client ID (e.g. initials for Stephen Calberg).  
        - For payslips, `YYYY-MM` is the month.  
        - For statements, the two dates are the statement start and end dates.

        Upload **only one client's documents at a time**.
        """
    )

    uploaded_files = st.file_uploader(
        "2. Upload payslips and bank statements (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload 6–10+ correctly named PDF files to continue.")
        return

    if st.button("Generate structured text for ChatGPT 4o mini"):
        # Collect docs grouped by type and label
        client_id_global = ""
        docs: List[Dict] = []

        for file in uploaded_files:
            filename = file.name
            file_bytes = file.read()

            client_id, doc_type, label = parse_filename(filename)
            if client_id and not client_id_global:
                client_id_global = client_id
            elif client_id and client_id_global and client_id != client_id_global:
                st.warning(
                    f"Mixed client IDs detected in filenames: {client_id_global} and {client_id}."
                )

            text = extract_text_from_pdf(file_bytes)

            docs.append(
                {
                    "filename": filename,
                    "client_id": client_id,
                    "doc_type": doc_type,
                    "label": label,
                    "text": text,
                }
            )

        if not client_id_global:
            client_id_global = "UNKNOWN_CLIENT"

        st.subheader("Preview of extracted documents")
        st.write("Client ID detected:", client_id_global)

        for d in docs:
            header = f"{d['doc_type'].upper()} – {d['label']} – {d['filename']}"
            st.markdown(f"#### {header}")
            st.text_area(
                header,
                d["text"][:4000],  # preview only
                height=200,
            )

        # Build one big structured block for GPT
        structured_blocks: List[str] = []
        structured_blocks.append(f"CLIENT_ID: {client_id_global}\n")

        # Payslips and statements separated, sorted by label for readability
        payslips = [d for d in docs if d["doc_type"] == "payslip"]
        statements = [d for d in docs if d["doc_type"] == "statement"]
        others = [d for d in docs if d["doc_type"] not in ("payslip", "statement")]

        # Sort by label (so months are in order)
        payslips.sort(key=lambda x: x["label"])
        statements.sort(key=lambda x: x["label"])

        # Number them PS1, PS2, BS1, BS2, etc.
        for idx, d in enumerate(payslips, start=1):
            block = (
                f"\n\n[PAYSLIP {idx} – LABEL: {d['label']} – FILE: {d['filename']}]\n"
                f"{d['text']}\n"
            )
            structured_blocks.append(block)

        for idx, d in enumerate(statements, start=1):
            block = (
                f"\n\n[BANK STATEMENT {idx} – LABEL: {d['label']} – FILE: {d['filename']}]\n"
                f"{d['text']}\n"
            )
            structured_blocks.append(block)

        for idx, d in enumerate(others, start=1):
            block = (
                f"\n\n[OTHER DOC {idx} – LABEL: {d['label']} – FILE: {d['filename']}]\n"
                f"{d['text']}\n"
            )
            structured_blocks.append(block)

        final_text = "".join(structured_blocks)

        st.subheader("Structured text for ChatGPT 4o mini")
        st.markdown(
            """
            Copy the text below into ChatGPT 4o mini (or your Zapier AI step)
            as the **input text**.  
            You can then give it instructions like:  
            “For each month, match payslip net pay to statement salary deposit, find
            other income and commitments, and summarise issues for Vikki.”
            """
        )
        st.text_area("GPT_input_text", final_text, height=400)

        # Optional: download as .txt file
        st.download_button(
            label="Download structured text as .txt",
            data=final_text.encode("utf-8"),
            file_name=f"{client_id_global}_precheck_input.txt",
            mime="text/plain",
        )


if __name__ == "__main__":
    main()
