import fitz  # PyMuPDF
import os
import csv
import re
from datetime import datetime

REPORT_FOLDER = "Daily Report"
OUTPUT_FOLDER = "Extracted Data"
OUTPUT_FILE = os.path.join(OUTPUT_FOLDER, "MOPS Fuel Markets Daily Data.csv")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def extract_report_date_from_pdf(pdf_path):
    """Extracts the date (e.g., 'January 8, 2025') from the first page of the PDF."""
    try:
        with fitz.open(pdf_path) as doc:
            text = doc.load_page(0).get_text("text")
    except Exception as e:
        print(f"⚠️ Could not read {pdf_path} for date extraction: {e}")
        return None

    # Look for patterns like: January 8, 2025 or March 12, 2024
    match = re.search(r"([A-Za-z]+ \d{1,2}, \d{4})", text)
    if not match:
        return None

    date_str = match.group(1)
    try:
        # Convert to datetime
        date_obj = datetime.strptime(date_str, "%B %d, %Y")
        return date_obj.strftime("%Y%m%d")
    except ValueError:
        return None

def extract_line_from_pdf(pdf_path):
    try:
        with fitz.open(pdf_path) as doc:
            # page = doc.load_page(0)
            # text = page.get_text("text")
            text = ""
            for page in doc:
                text += page.get_text("text") + "\n"
    except Exception as e:
        print(f"⚠️ Could not read {pdf_path}: {e}")
        return None, None, None

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    keywords = ["Gasoline 97 unleaded", "PGAMS00"]

    for i, line in enumerate(lines):
        if any(k.lower() in line.lower() for k in keywords):
            context = " ".join(lines[i:i+5])
            context = re.sub(r"\s+", " ", context).strip()
            context = re.sub(r'(?<=\d)[\-–—](?=\d)', '–', context)

            # match = re.search(r"(\d{2}\.\d{3})", context)
            # match = re.search(r"(\d+\.\d{3})", context)
            # numbers = re.findall(r"[+-]?\d+\.\d{3,3}", context)
            numbers = re.findall(r"(?<!\d)([+-]?\d+\.\d{2,3})", context)

            mid = numbers[-2] if len(numbers) >= 2 else (numbers[-1] if numbers else None)
            change = numbers[-1] if numbers else None

            return context, mid, change
            # value = match.group(1) if match else None
            # return context, value
        

    # text = page.get_text("text")
    # print("=== RAW TEXT START ===")
    # print(text[:1000])  # print first 1000 chars
    # print("=== RAW TEXT END ===")


    return None, None, None

# def load_existing_dates():
#     """Loads existing report dates from the output CSV file (if present)."""
#     existing_dates = set()
#     if os.path.isfile(OUTPUT_FILE):
#         with open(OUTPUT_FILE, newline="", encoding="utf-8-sig") as f:
#             reader = csv.DictReader(f)
#             for row in reader:
#                 existing_dates.add(row["Date"])
#     return existing_dates

def process_reports():
    results = []
    # existing_dates = load_existing_dates()
    for file in os.listdir(REPORT_FOLDER):
        if file.lower().endswith(".pdf"):
            pdf_path = os.path.join(REPORT_FOLDER, file)
            print(f"Processing: {file}")

            # line, mid, change = extract_line_from_pdf(pdf_path)
            # # date_match = re.search(r"\d{4}-\d{2}-\d{2}", file)
            # # report_date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")
            # date_match = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", file)

            # if date_match:
            #     year, month, day = date_match.groups()
            #     report_date = f"{year}-{month}-{day}"  # normalize to YYYY-MM-DD
            # else:
            #     report_date = datetime.now().strftime("%Y-%m-%d")

            date_match = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", file)

            if not date_match:
                print(f"\n❌ ERROR: Cannot find a valid date in file name '{file}'.")
                print("   💡 Hint: The filename must include a date in the format YYYYMMDD.")
                print("   💡 Example: APAG_20250811.pdf  → valid\n")
                raise ValueError(f"Invalid filename: missing date pattern in '{file}'")
        
        # If valid, normalize to YYYY-MM-DD
        year, month, day = date_match.groups()
        filename_date = f"{year}{month}{day}"
        formatted_filename_date = f"{year}-{month}-{day}"

        # line, value = extract_line_from_pdf(pdf_path)
        # if report_date in existing_dates:
        # status = "Successfully extracted" if value else "Fail to extract"
        # # else:
        # #     status = ""
        #         # Extract data from PDF
        line, mid, change = extract_line_from_pdf(pdf_path)
        pdf_date = extract_report_date_from_pdf(pdf_path)

        # Compare date in PDF with filename
        if pdf_date:
            date_match_status = "True" if pdf_date == filename_date else f"{file} Mismatch ({pdf_date})"
        else:
            date_match_status = "Not found"

        status = "Successfully extracted" if mid else "Fail to extract"
        results.append([formatted_filename_date, file, line or "Not found", mid or "", change or "", status, date_match_status, filename_date])

    results.sort(key=lambda x: x[-1], reverse=True)

    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date", "File Name", "Extracted Line", "Mid", "Change (Positive Sign Omitted)", "Status", "Filename Date Validation"])
        for row in results:
            writer.writerow(row[:-1])

    print(f"✅ Extraction complete. Data saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    process_reports()