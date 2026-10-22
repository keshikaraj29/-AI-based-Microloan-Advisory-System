#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════
# MICROLOAN ADVISORY SYSTEM — PROFESSIONAL BANKING VERSION
# Version: 3.0
# Features:
#   ✔ Professional Banking Interface
#   ✔ Strict Validation System
#   ✔ Hindi + English NLP
#   ✔ AGMARKET Integration
#   ✔ Alternative Business Suggestion
#   ✔ Always Generate Dashboard
# ═══════════════════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
import os
import sys
import re
import time
import warnings

from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA

# Warnings remain visible so validation issues can be investigated.


# ═══════════════════════════════════════════════════════════════════════
# PROFESSIONAL DISPLAY ELEMENTS
# ═══════════════════════════════════════════════════════════════════════

HDIVIDER = "═" * 70
DIVIDER = "─" * 70


def print_system_banner():

    print("\n" + HDIVIDER)
    print("   INITIALIZING MICROLOAN ADVISORY SYSTEM  v3.0")
    print(HDIVIDER)

    time.sleep(1)

    print("\n  " + DIVIDER)
    print("   LOADING DATASETS")
    print("  " + DIVIDER)


def print_main_portal():

    now = datetime.now()

    print("\n" + HDIVIDER)
    print("   🏦   MICROCREDIT ADVISORY SYSTEM  —  LOAN APPLICATION PORTAL")
    print(
        f"   📅   {now.strftime('%A, %d %B %Y')}   |   "
        f"{now.strftime('%I:%M %p')}"
    )
    print(HDIVIDER)

    print("\n   Welcome. This system provides an AI-powered")
    print("   micro-loan appraisal for agricultural and")
    print("   dairy sector borrowers.")

    print("\n   Please fill in each section accurately.")
    print("   All information is treated confidentially.")


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

CONFIG = {

    "farm_path":
        os.path.join(BASE_DIR, "data_season.csv"),

    "dairy_path":
        os.path.join(BASE_DIR, "dairy_dataset.csv"),

    "agmarket_path":
        os.path.join(BASE_DIR, "agmarknet_india_historical_prices_2024_2025.csv.xlsx"),

    "clusters": 6,

    "repayment_months": 12,

    "output_graph":
        "microloan_dashboard.png",

    "interest_rates": {

        "Premium Borrower": 0.10,
        "Low Risk": 0.12,
        "Medium Risk": 0.18,
        "Moderate Risk": 0.22,
        "High Risk": 0.26,
        "Emerging Borrower": 0.28,

    }

}


# ═══════════════════════════════════════════════════════════════════════
# HINDI DETECTION ENGINE
# ═══════════════════════════════════════════════════════════════════════

def detect_language(text):
    # TAG: LANGUAGE NLP - detects Hindi text so numbers and vocabulary can be normalized.

    if re.search(r'[\u0900-\u097F]', text):

        return "Hindi"

    return "English"


# ═══════════════════════════════════════════════════════════════════════
# HINDI NUMBER CONVERSION
# ═══════════════════════════════════════════════════════════════════════

HINDI_DIGITS = {

    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9"

}


def convert_hindi_numbers(text):
    # TAG: HINDI NORMALIZATION - converts Hindi numerals into English digits before regex extraction.

    for h, e in HINDI_DIGITS.items():

        text = text.replace(h, e)

    return text


# ═══════════════════════════════════════════════════════════════════════
# FULL HINDI VOCABULARY SUPPORT
# (Expanded — not minimal)
# ═══════════════════════════════════════════════════════════════════════

HINDI_CROP_MAP = {

    "गेहूं": "Wheat",
    "मक्का": "Maize",
    "केला": "Banana",
    "चना": "Gram",
    "सरसों": "Mustard",
    "सोयाबीन": "Soybean",
    "कपास": "Cotton",
    "आलू": "Potato",
    "प्याज": "Onion",
    "टमाटर": "Tomato",
    "बैंगन": "Brinjal",
    "गोभी": "Cabbage",
    "फूलगोभी": "Cauliflower",
    "भिंडी": "Bhindi",
    "हरी मिर्च": "Green Chilli",
    "अदरक": "Ginger",
    "ज्वार": "Jowar",
    "बाजरा": "Bajra"

}


HINDI_DAIRY_MAP = {

    "दूध": "Milk",
    "दही": "Curd",
    "पनीर": "Paneer",
    "मक्खन": "Butter",
    "घी": "Ghee",
    "छाछ": "Buttermilk",
    "क्रीम": "Cream"

}


HINDI_SEASONS = {

    "खरीफ": "Kharif",
    "रबी": "Rabi",
    "जायद": "Zaid"

}


# ═══════════════════════════════════════════════════════════════════════
# PROCESSING ANIMATION
# (Matches your professional interface)
# ═══════════════════════════════════════════════════════════════════════

def show_processing():

    steps = [

        "Analyzing business narrative...",
        "Performing NLP entity extraction...",
        "Estimating financial projections...",
        "Running clustering algorithms...",
        "Computing borrower risk profile...",
        "Calculating EMI schedule...",
        "Preparing microcredit report..."

    ]

    print("\n  Processing application...\n")

    for s in steps:

        print(f"   ➤  {s}")
        time.sleep(0.5)

    print("\n   ✓  Microcredit appraisal report generated.\n")


# ═══════════════════════════════════════════════════════════════════════
# SYSTEM INITIALIZATION DISPLAY
# ═══════════════════════════════════════════════════════════════════════

def initialize_system():

    print_system_banner()

    time.sleep(1)

    print("  ✓  Farm CSV path configured")

    print("  ✓  Dairy CSV path configured")

    print("  ✓  AGMARKET CSV path configured")

    print("\n  " + DIVIDER)
    print("   BUILDING CLUSTER MODELS")
    print("  " + DIVIDER)
# ═══════════════════════════════════════════════════════════════════════
# STRICT VALIDATION ENGINE
# (Professional Banking Input Validation)
# ═══════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# NAME VALIDATION
# ─────────────────────────────────────────────────────────────

def get_valid_name():

    while True:

        name = input(
            "    Full Name (as on ID proof): "
        ).strip()

        if len(name) >= 3:

            return name

        print("    ⚠ Invalid name — please try again.")


# ─────────────────────────────────────────────────────────────
# DATE OF BIRTH VALIDATION (CRITICAL FIX)
# ─────────────────────────────────────────────────────────────

def get_valid_dob():

    while True:

        dob_input = input(
            "    Date of Birth  (DD/MM/YYYY): "
        )

        try:

            dob = datetime.strptime(
                dob_input,
                "%d/%m/%Y"
            )

            today = datetime.today()

            age = (

                today.year
                - dob.year
                - ((today.month, today.day)
                   < (dob.month, dob.day))

            )

            if age < 18 or age > 70:

                print(
                    "    ⚠ Age must be between 18 and 70."
                )

                print(
                    "    Please re-enter Date of Birth."
                )

                continue

            return dob_input, age

        except:

            print(
                "    ⚠ Invalid date format."
            )

            print(
                "    Use DD/MM/YYYY format."
            )


# ─────────────────────────────────────────────────────────────
# GENDER VALIDATION
# ─────────────────────────────────────────────────────────────

def get_valid_gender():

    while True:

        gender = input(
            "    Gender  (Male / Female / Other): "
        ).strip().upper()

        if gender in ["M", "MALE"]:

            return "Male"

        if gender in ["F", "FEMALE"]:

            return "Female"

        if gender in ["O", "OTHER"]:

            return "Other"

        print(
            "    ⚠ Invalid gender — enter Male/Female/Other."
        )


# ─────────────────────────────────────────────────────────────
# MOBILE VALIDATION
# ─────────────────────────────────────────────────────────────

def get_valid_mobile():

    while True:

        mobile = input(
            "    Mobile Number  (10 digits): "
        ).strip()

        if mobile.isdigit() and len(mobile) == 10:

            return mobile

        print(
            "    ⚠ Invalid mobile — enter 10 digits."
        )


# ─────────────────────────────────────────────────────────────
# ADDRESS VALIDATION
# ─────────────────────────────────────────────────────────────

def get_valid_address():

    while True:

        address = input(
            "    Complete Address / Village / District: "
        ).strip()

        if len(address) >= 5:

            return address

        print(
            "    ⚠ Address too short — re-enter."
        )


# ─────────────────────────────────────────────────────────────
# ID TYPE VALIDATION
# ─────────────────────────────────────────────────────────────

def get_valid_id_type():

    allowed = [

        "AADHAAR",
        "PAN",
        "VOTER ID",
        "PASSPORT"

    ]

    while True:

        id_type = input(
            "    ID Proof Type  "
            "(Aadhaar / PAN / Voter ID / Passport): "
        ).strip().upper()

        if id_type in allowed:

            return id_type.title()

        print(
            "    ⚠ Invalid ID type — try again."
        )


# ─────────────────────────────────────────────────────────────
# ID NUMBER VALIDATION
# ─────────────────────────────────────────────────────────────

def get_valid_id_number(id_type):

    while True:

        id_number = input(
            "    ID Number: "
        ).strip()

        if id_type == "Pan":

            if re.match(r"[A-Z]{5}[0-9]{4}[A-Z]", id_number):

                return id_number

        elif id_type == "Aadhaar":

            if id_number.isdigit() and len(id_number) == 12:

                return id_number

        elif id_type == "Voter Id":

            if len(id_number) >= 6:

                return id_number

        elif id_type == "Passport":

            if len(id_number) >= 6:

                return id_number

        print(
            "    ⚠ Invalid ID number — re-enter."
        )


# ─────────────────────────────────────────────────────────────
# NUMERIC VALIDATION
# ─────────────────────────────────────────────────────────────

def get_positive_number(prompt):

    while True:

        try:

            value = float(input(prompt))

            if value > 0:

                return value

        except:

            pass

        print(
            "    ⚠ Invalid number — try again."
        )


# ─────────────────────────────────────────────────────────────
# YES/NO VALIDATION
# ─────────────────────────────────────────────────────────────

def get_yes_no(prompt):

    while True:

        ans = input(prompt).strip().upper()

        if ans in ["Y", "YES"]:

            return "Yes"

        if ans in ["N", "NO"]:

            return "No"

        print(
            "    ⚠ Enter Y or N only."
        )
# ═══════════════════════════════════════════════════════════════════════
# DATASET LOADING ENGINE
# (Professional Banking Display Style)
# ═══════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# FARM DATA LOADER
# ─────────────────────────────────────────────────────────────

def load_farm_dataset():

    path = CONFIG["farm_path"]

    try:

        if not os.path.exists(path):

            raise FileNotFoundError

        farm_df = pd.read_csv(path)

        farm_df.columns = farm_df.columns.astype(str).str.strip()

        farm_df.rename(
            columns={
                "Soil type": "SoilType",
                "yeilds": "Yield",
                "yield": "Yield",
                "yields": "Yield",
                "Crops": "Crop",
                "price": "Price",
            },
            inplace=True
        )

        required_columns = [
            "Year",
            "Location",
            "Area",
            "Rainfall",
            "Temperature",
            "SoilType",
            "Irrigation",
            "Yield",
            "Humidity",
            "Crop",
            "Price",
            "Season"
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in farm_df.columns
        ]

        if missing_columns:
            raise ValueError(
                "Missing farm dataset columns: "
                + ", ".join(missing_columns)
            )

        farm_df.dropna(subset=required_columns, inplace=True)

        farm_df["Location"] = (
            farm_df["Location"]
            .astype(str)
            .str.strip()
            .str.title()
        )

        farm_df["Crop"] = (
            farm_df["Crop"]
            .astype(str)
            .str.strip()
            .str.title()
        )

        farm_df["Season"] = (
            farm_df["Season"]
            .astype(str)
            .str.strip()
            .str.title()
        )

        farm_df["Revenue"] = (

            farm_df["Area"]
            * farm_df["Yield"]
            * farm_df["Price"]

        ) / 100000

        print(
            f"  ✓  Farm CSV loaded      — "
            f"{len(farm_df):,} records"
        )

        return farm_df

    except:

        print(
            "\n  ✖ ERROR loading Farm dataset."
        )

        sys.exit(1)


# ─────────────────────────────────────────────────────────────
# DAIRY DATA LOADER
# ─────────────────────────────────────────────────────────────

def load_dairy_dataset():

    path = CONFIG["dairy_path"]

    try:

        if not os.path.exists(path):

            raise FileNotFoundError

        dairy_df = pd.read_csv(path)

        dairy_df.columns = dairy_df.columns.str.strip()

        dairy_df.rename(

            columns={

                "Quantity (liters/kg)": "Quantity",
                "Price per Unit": "UnitPrice"

            },

            inplace=True

        )

        if "Product Name" not in dairy_df.columns:

            dairy_df["Product Name"] = "Milk"

        if "Location" not in dairy_df.columns:

            dairy_df["Location"] = "Unknown"

        required_columns = [
            "Location",
            "Product Name",
            "Quantity",
            "UnitPrice"
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in dairy_df.columns
        ]

        if missing_columns:
            raise ValueError(
                "Missing dairy dataset columns: "
                + ", ".join(missing_columns)
            )

        dairy_df.dropna(subset=required_columns, inplace=True)

        dairy_df["Revenue"] = (

            dairy_df["Quantity"]
            * dairy_df["UnitPrice"]

        ) / 100000

        print(
            f"  ✓  Dairy CSV loaded     — "
            f"{len(dairy_df):,} records"
        )

        return dairy_df

    except:

        print(
            "\n  ✖ ERROR loading Dairy dataset."
        )

        sys.exit(1)


# ─────────────────────────────────────────────────────────────
# AGMARKET DATA LOADER
# ─────────────────────────────────────────────────────────────

def load_agmarket_dataset():

    path = CONFIG["agmarket_path"]

    try:

        if not os.path.exists(path):

            raise FileNotFoundError


        print("\n  ➤ Reading AGMARKET dataset...")


        # 🔴 Detect file type

        if path.endswith(".xlsx") or path.endswith(".xls"):

            print("  Detected Excel file (.xlsx)")

            ag_df = pd.read_excel(

                path,

                engine="openpyxl"

            )

        else:

            print("  Detected CSV file")

            ag_df = pd.read_csv(

                path,

                sep="\t",

                engine="python",

                encoding="latin1",

                on_bad_lines="skip"

            )


        print(
            f"  Raw rows loaded: {len(ag_df):,}"
        )


        # Clean column names

        ag_df.columns = (

            ag_df.columns
            .astype(str)
            .str.strip()
        )


        # Rename columns

        rename_map = {

            "District Name": "District",
            "Market Name": "Market",

            "Min Price (Rs./Quintal)": "Min Price",
            "Max Price (Rs./Quintal)": "Max Price",

            "Modal Price (Rs./Quintal)": "Modal Price"

        }

        ag_df.rename(

            columns=rename_map,

            inplace=True

        )


        # Validate required columns

        required_cols = [

            "District",
            "Market",
            "Commodity",
            "State",
            "Min Price",
            "Max Price"

        ]

        for col in required_cols:

            if col not in ag_df.columns:

                print("\nAvailable Columns:")

                print(ag_df.columns.tolist())

                raise Exception(
                    f"Missing required column: {col}"
                )


        # Normalize text

        for col in [

            "State",
            "District",
            "Market",
            "Commodity"

        ]:

            ag_df[col] = (

                ag_df[col]
                .astype(str)
                .str.strip()
                .str.title()

            )


        # Convert prices

        ag_df["Min Price"] = pd.to_numeric(

            ag_df["Min Price"],

            errors="coerce"

        )

        ag_df["Max Price"] = pd.to_numeric(

            ag_df["Max Price"],

            errors="coerce"

        )


        print(
            f"  Rows before dropna: {len(ag_df):,}"
        )


        ag_df.dropna(

            subset=["Min Price", "Max Price"],

            inplace=True

        )


        print(
            f"  Rows after dropna: {len(ag_df):,}"
        )


        # Compute Avg Price

        ag_df["Avg Price"] = (

            ag_df["Min Price"]
            + ag_df["Max Price"]

        ) / 2


        print(
            f"  ✓ AGMARKET loaded — "
            f"{len(ag_df):,} records"
        )


        return ag_df


    except Exception as e:

        print(
            "\n  ✖ ERROR loading AGMARKET dataset."
        )

        print("Reason:", e)

        sys.exit(1)
# ─────────────────────────────────────────────────────────────
# MASTER DATA LOADER
# ─────────────────────────────────────────────────────────────

def load_all_datasets():

    farm_df = load_farm_dataset()

    dairy_df = load_dairy_dataset()

    ag_df = load_agmarket_dataset()

    return farm_df, dairy_df, ag_df
# ═══════════════════════════════════════════════════════════════════════
# NLP ENGINE — PROFESSIONAL VERSION
# FULL ENGLISH + HINDI SUPPORT
# ═══════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# TEXT NORMALIZATION
# ─────────────────────────────────────────────────────────────

def normalize_text(text):
    # TAG: TEXT NORMALIZATION - prepares English/Hindi borrower story for entity extraction.

    language = detect_language(text)

    if language == "Hindi":

        text = convert_hindi_numbers(text)

    return text.lower()



# ─────────────────────────────────────────────────────────────
# LOAD LOCATION LIST
# ─────────────────────────────────────────────────────────────

def build_location_list(farm_df, dairy_df, ag_df):

    locations = set()

    if "Location" in farm_df.columns:

        locations.update(
            farm_df["Location"].dropna().unique()
        )

    if "Location" in dairy_df.columns:

        locations.update(
            dairy_df["Location"].dropna().unique()
        )

    if "District" in ag_df.columns:

        locations.update(
            ag_df["District"].dropna().unique()
        )

    return list(locations)



# ─────────────────────────────────────────────────────────────
# PRODUCT DETECTION
# ─────────────────────────────────────────────────────────────

def detect_product(text):
    # TAG: RULE-BASED NLP PRODUCT DETECTION - finds crop/dairy product and business category.

    # Hindi Crops

    for h_word, eng in HINDI_CROP_MAP.items():

        if h_word in text:

            return eng, "Farm"

    # Hindi Dairy

    for h_word, eng in HINDI_DAIRY_MAP.items():

        if h_word in text:

            return eng, "Dairy"

    # English Crops

    crops = [

        "wheat",
        "maize",
        "banana",
        "groundnut",
        "mustard",
        "soybean",
        "cotton",
        "potato",
        "onion",
        "tomato",
        "brinjal",
        "cabbage",
        "cauliflower",
        "bhindi",
        "green chilli",
        "ginger",
        "jowar",
        "bajra"

    ]

    for crop in crops:

        if re.search(r'\b' + re.escape(crop) + r'\b', text, re.I):

            return crop.title(), "Farm"

    # Dairy

    dairy_items = [

        "milk",
        "curd",
        "paneer",
        "butter",
        "ghee"

    ]

    for item in dairy_items:

        if re.search(r'\b' + re.escape(item) + r'\b', text, re.I):

            return item.title(), "Dairy"

    return None, None



# ─────────────────────────────────────────────────────────────
# LOAN AMOUNT DETECTION
# ─────────────────────────────────────────────────────────────

def detect_loan_amount(text):
    """Require money/loan context, support Indian multipliers and Hindi digits."""
    text = convert_hindi_numbers(str(text)).lower()
    number = r"([0-9][0-9,]*(?:\.[0-9]+)?)"
    multiplier = r"\s*(lakh|lakhs|lac|lacs|crore|crores|thousand|k|लाख|हजार|हज़ार|करोड़)?"
    patterns = [
        r"(?:loan|ऋण|लोन|borrow|amount|राशि)\s*(?:of|for|is|around|about|चाहिए)?\s*(?:inr|rs\.?|₹|रुपये)?\s*" + number + multiplier,
        r"(?:inr|rs\.?|₹)\s*" + number + multiplier,
        number + multiplier + r"\s*(?:rupees|रुपये|रूपये|loan|ऋण|लोन)",
        r"(?:need|request|requires?)\s*(?:of|for|is|around|about)?\s*(?:inr|rs\.?|₹)?\s*" + number + multiplier + r"(?![\w]|\s*(?:acres?|hectares?|liters?|litres?|cows?))",
    ]
    factors = {'lakh':100000,'lakhs':100000,'lac':100000,'lacs':100000,'लाख':100000,
               'crore':10000000,'crores':10000000,'करोड़':10000000,
               'thousand':1000,'k':1000,'हजार':1000,'हज़ार':1000}
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if re.match(r'\s*(?:per|/|प्रति)\s*(?:lit|kg|quintal|unit|day|month|लीटर|किलो)', text[match.end():]):
                continue
            return float(match.group(1).replace(',', '')) * factors.get(match.group(2), 1)
    return 0


def detect_area(text):
    """Normalize every supported area into acres."""
    text = convert_hindi_numbers(str(text)).lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(acres?|एकड़|hectares?|हेक्टेयर)", text)
    if not match:
        return 0
    return float(match.group(1)) * (2.4710538147 if match.group(2).startswith(('hectare', 'हेक्टेयर')) else 1)


def detect_quantity(text):
    # TAG: RULE-BASED NLP QUANTITY EXTRACTION - finds liters/kg from dairy or product stories.

    patterns = [

        r'(\d+(?:\.\d+)?)\s*liters?',
        r'(\d+(?:\.\d+)?)\s*litres?',
        r'(\d+(?:\.\d+)?)\s*लीटर',
        r'(\d+(?:\.\d+)?)\s*kg',
        r'(\d+(?:\.\d+)?)\s*किलो'

    ]

    for pat in patterns:

        m = re.search(pat, text)

        if m:

            return float(m.group(1))

    return 0



# ─────────────────────────────────────────────────────────────
# UNIT PRICE DETECTION
# ─────────────────────────────────────────────────────────────

def detect_unit_price(text):
    # TAG: RULE-BASED NLP PRICE EXTRACTION - finds price per unit from the borrower story.

    patterns = [

        r'(?:inr|rs\.?|₹)?\s*(\d+(?:\.\d+)?)\s*(?:rupees|रुपये)?\s*(?:per|/|प्रति)\s*(?:liters?|litres?|kg|quintals?|units?|लीटर|किलो|क्विंटल)',

    ]

    for pat in patterns:

        m = re.search(pat, text)

        if m:

            return float(m.group(1))

    return 0



# ─────────────────────────────────────────────────────────────
# SEASON DETECTION
# ─────────────────────────────────────────────────────────────

def detect_season(text):
    # TAG: RULE-BASED NLP SEASON EXTRACTION - detects Kharif/Rabi/Zaid from English or Hindi terms.

    # Hindi

    for h, e in HINDI_SEASONS.items():

        if h in text:

            return e

    seasons = [

        "kharif",
        "rabi",
        "zaid"

    ]

    for s in seasons:

        if s in text:

            return s.title()

    return None



# ─────────────────────────────────────────────────────────────
# LOCATION DETECTION
# ─────────────────────────────────────────────────────────────

def detect_location(text, locations):
    # TAG: RULE-BASED NLP LOCATION EXTRACTION - matches borrower text against known dataset locations.

    for loc in locations:

        if loc.lower() in text:

            return loc

    return None



# ─────────────────────────────────────────────────────────────
# MAIN ENTITY EXTRACTION
# ─────────────────────────────────────────────────────────────

def extract_entities(

        text,
        location_list

):
    # TAG: CORE NLP ENTITY PIPELINE - combines product, loan, area, quantity, price, season, and location extraction.

    text = normalize_text(text)

    product, category = detect_product(text)

    loan = detect_loan_amount(text)

    area = detect_area(text)

    quantity = detect_quantity(text)

    price = detect_unit_price(text)

    season = detect_season(text)

    location = detect_location(

        text,
        location_list

    )

    return {

        "product": product,
        "category": category,
        "loan_amount": loan,
        "area": area,
        "quantity": quantity,
        "unit_price": price,
        "season": season,
        "location": location

    }
# ═══════════════════════════════════════════════════════════════════════
# CLUSTER ENGINE — PROFESSIONAL VERSION
# Builds Farm + Dairy Clusters
# Assigns Risk Tiers
# Suggests Alternative Business
# ═══════════════════════════════════════════════════════════════════════


class ClusterEngine:
    # TAG: ML CLUSTER ENGINE - groups farm/dairy dataset rows for risk and recommendation logic.

    def __init__(self, farm_df, dairy_df):

        print(
            "  ✓  Building clustering models..."
        )

        self.build_farm_clusters(farm_df)

        self.build_dairy_clusters(dairy_df)

        self.assign_risk_labels()



    # ─────────────────────────────────────────────────────────────
    # FARM CLUSTERS
    # ─────────────────────────────────────────────────────────────

    def build_farm_clusters(self, df):

        features = [

            "Area",
            "Price",
            "Revenue",
            "Rainfall",
            "Temperature",
            "Humidity"

        ]

        X = df[features].fillna(0)

        self.scaler_farm = StandardScaler()

        Xs = self.scaler_farm.fit_transform(X)

        farm_cluster_count = max(1, min(CONFIG["clusters"], len(Xs)))

        self.kmeans_farm = KMeans(

            n_clusters=farm_cluster_count,
            random_state=42,
            n_init=10

        )

        df = df.copy()

        df["Cluster"] = self.kmeans_farm.fit_predict(Xs)

        self.farm_df = df

        sil = (
            silhouette_score(
                Xs,
                df["Cluster"]
            )
            if farm_cluster_count > 1 and len(Xs) > farm_cluster_count
            else 0
        )

        print(
            f"  ✓  Farm clusters built  — "
            f"silhouette: {sil:.3f}"
        )



    # ─────────────────────────────────────────────────────────────
    # DAIRY CLUSTERS
    # ─────────────────────────────────────────────────────────────

    def build_dairy_clusters(self, df):

        features = [

            "Quantity",
            "UnitPrice",
            "Revenue"

        ]

        X = df[features].fillna(0)

        self.scaler_dairy = StandardScaler()

        Xs = self.scaler_dairy.fit_transform(X)

        dairy_cluster_count = max(1, min(CONFIG["clusters"], len(Xs)))

        self.kmeans_dairy = KMeans(

            n_clusters=dairy_cluster_count,
            random_state=42,
            n_init=10

        )

        df = df.copy()

        df["Cluster"] = self.kmeans_dairy.fit_predict(Xs)

        self.dairy_df = df

        sil = (
            silhouette_score(
                Xs,
                df["Cluster"]
            )
            if dairy_cluster_count > 1 and len(Xs) > dairy_cluster_count
            else 0
        )

        print(
            f"  ✓  Dairy clusters built — "
            f"silhouette: {sil:.3f}"
        )



    # ─────────────────────────────────────────────────────────────
    # RISK LABELING
    # ─────────────────────────────────────────────────────────────

    def assign_risk_labels(self):

        def compute_map(df):

            revenue_map = {

                cid: df[
                    df["Cluster"] == cid
                ]["Revenue"].mean()

                for cid in sorted(df["Cluster"].dropna().unique())

            }

            ranked = sorted(

                revenue_map,
                key=revenue_map.get,
                reverse=True

            )

            risk_levels = list(
                CONFIG["interest_rates"].keys()
            )

            return {

                cid: risk_levels[i]

                for i, cid in enumerate(ranked)

            }

        self.farm_risk_map = compute_map(

            self.farm_df
        )

        self.dairy_risk_map = compute_map(

            self.dairy_df
        )



    # ─────────────────────────────────────────────────────────────
    # ASSIGN USER TO CLUSTER
    # ─────────────────────────────────────────────────────────────

    def assign_cluster(self, entities):

        category = entities["category"]

        if category == "Farm":

            vec = np.array([[

                entities["area"],
                entities["unit_price"],
                0,
                100,
                25,
                70

            ]])

            X = self.scaler_farm.transform(vec)

            cid = int(

                self.kmeans_farm.predict(X)[0]

            )

            return cid, "Farm"

        else:

            vec = np.array([[

                entities["quantity"],
                entities["unit_price"],
                0

            ]])

            X = self.scaler_dairy.transform(vec)

            cid = int(

                self.kmeans_dairy.predict(X)[0]

            )

            return cid, "Dairy"



    # ─────────────────────────────────────────────────────────────
    # CLUSTER SUMMARY
    # ─────────────────────────────────────────────────────────────

    def cluster_summary(

            self,
            cid,
            category

    ):

        if category == "Farm":

            df = self.farm_df

            risk_map = self.farm_risk_map

            name_col = "Crop"

        else:

            df = self.dairy_df

            risk_map = self.dairy_risk_map

            name_col = "Product Name"

        subset = df[
            df["Cluster"] == cid
        ]

        return {

            "size": len(subset),

            "avg_revenue":

                subset["Revenue"].mean(),

            "dominant_product":

                subset[name_col]
                .value_counts()
                .idxmax(),

            "dominant_location":

                subset["Location"]
                .value_counts()
                .idxmax(),

            "risk_label":

                risk_map.get(cid)

        }



    # ─────────────────────────────────────────────────────────────
    # ALTERNATIVE BUSINESS SUGGESTION
    # ─────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────
# ALTERNATIVE BUSINESS SUGGESTION (FIXED INDENTATION + REALISTIC VALUES)
# ─────────────────────────────────────────────────────────────

def recommend_alternative_business(
        self,
        location,
        investment_amount
):

    farm_avg = (

        self.farm_df
        .groupby("Crop")["Revenue"]
        .mean()
        .sort_values(ascending=False)

    )

    best_crop = farm_avg.index[0]


    # Realistic scaling

    expected_revenue = investment_amount * 1.8

    expected_profit = investment_amount * 0.5


    # Strict caps

    expected_revenue = max(
        50000,
        min(expected_revenue, 100000)
    )

    expected_profit = max(
        20000,
        min(expected_profit, 60000)
    )


    return {

        "business": best_crop,

        "location": location,

        "expected_revenue":
            round(expected_revenue, 2),

        "expected_profit":
            round(expected_profit, 2)

    }
# ═══════════════════════════════════════════════════════════════════════
# FINANCIAL ENGINE — PROFESSIONAL VERSION
# AGMARKET Integration + ROI + EMI + Loan Decision
# ═══════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────
# MARKET PRICE LOOKUP (AGMARKET)
# ─────────────────────────────────────────────────────────────

def get_market_price(
        ag_df,
        district=None,
        commodity=None,
        state=None
):

    df = ag_df.copy()

    if district:

        df = df[
            df["District"]
            == str(district).title()
        ]

    if commodity:

        df = df[
            df["Commodity"]
            == str(commodity).title()
        ]

    if state:

        df = df[
            df["State"]
            == str(state).title()
        ]

    if len(df) == 0:

        return 0

    return df["Avg Price"].mean()



# ─────────────────────────────────────────────────────────────
# INCOME ESTIMATION
# ─────────────────────────────────────────────────────────────

def estimate_income(entities, ag_df):

    loan_amount = entities.get("loan_amount", 50000)

    crop = entities.get("product")

    location = entities.get("location")

    area = entities.get("area", 2)

    if area == 0:

        area = 2   # default acreage



    # Filter AGMARKET data

    df = ag_df[

        (ag_df["Commodity"] == crop) &
        (ag_df["District"] == location)

    ]


    if len(df) == 0:

        avg_price = 2200

    else:

        avg_price = df["Avg Price"].mean()



    # Realistic yield assumptions

    yield_per_acre = 20   # quintals

    cost_per_acre = 12000



    total_yield = area * yield_per_acre

    gross_income = total_yield * avg_price

    total_cost = area * cost_per_acre



    # Net income

    net_income = gross_income - total_cost



    # Limit unrealistic scaling

    max_income_limit = loan_amount * 4

    net_income = min(

        net_income,

        max_income_limit

    )



    return max(net_income, 0)


# ─────────────────────────────────────────────────────────────
# PROFIT & ROI
# ─────────────────────────────────────────────────────────────

def calculate_profit_roi(

        income,
        loan_amount

):

    profit = income - loan_amount

    if loan_amount == 0:

        roi = 0

    else:

        roi = profit / loan_amount

    return profit, roi



# ─────────────────────────────────────────────────────────────
# RISK PROFILE
# ─────────────────────────────────────────────────────────────

def compute_risk_profile(

        borrower,
        roi

):
    # TAG: RISK SCORING MODEL - converts age, income, loan size, business years, and ROI into a risk tier.

    score = 0

    age = borrower["age"]

    income = borrower["monthly_income"]

    loan = borrower["loan_amount"]

    years = borrower["years_in_business"]

    if 25 <= age <= 55:

        score += 2

    if income > 0:

        ratio = loan / (income * 12)

        if ratio < 1:

            score += 4

        elif ratio < 2:

            score += 3

        elif ratio < 4:

            score += 2

    if years >= 5:

        score += 2

    elif years >= 2:

        score += 1

    if roi >= 0.5:

        score += 3

    elif roi >= 0.3:

        score += 2

    elif roi >= 0.1:

        score += 1

    if score >= 11:

        tier = "Premium Borrower"

    elif score >= 9:

        tier = "Low Risk"

    elif score >= 7:

        tier = "Medium Risk"

    elif score >= 5:

        tier = "Moderate Risk"

    elif score >= 3:

        tier = "High Risk"

    else:

        tier = "Emerging Borrower"

    rate = CONFIG["interest_rates"][tier]

    return tier, rate, score



# ─────────────────────────────────────────────────────────────
# EMI CALCULATION
# ─────────────────────────────────────────────────────────────

def calculate_emi(principal, annual_rate, months):
    if not all(np.isfinite(x) for x in (principal, annual_rate, months)):
        raise ValueError('Repayment inputs must be finite.')
    if principal < 0 or annual_rate < 0 or int(months) != months or months < 1 or months > 1200:
        raise ValueError('Use non-negative principal/rate and a positive whole term up to 1200 months.')
    if principal == 0:
        return 0.0, 0.0
    rate = annual_rate / 12
    emi = principal / months if rate == 0 else principal * rate / (1 - (1 + rate) ** -months)
    return round(emi, 2), round(emi * months - principal, 2)


def generate_repayment_schedule(loan, annual_rate, months=12):
    """Cent-reconciled schedule with an adjusted final installment."""
    from decimal import Decimal, ROUND_HALF_UP
    emi, _ = calculate_emi(loan, annual_rate, months)
    cent = Decimal('0.01')
    quantize = lambda x: x.quantize(cent, rounding=ROUND_HALF_UP)
    balance = quantize(Decimal(str(loan)))
    rate = Decimal(str(annual_rate)) / 12
    regular = Decimal(str(emi))
    interest_total = Decimal('0')
    rows = []
    for month in range(1, int(months) + 1):
        interest = quantize(balance * rate)
        principal = balance if month == months else min(balance, max(regular - interest, Decimal('0')))
        payment = principal + interest
        balance -= principal
        interest_total += interest
        rows.append({'Month': month, 'EMI': float(payment), 'Principal': float(principal), 'Interest': float(interest), 'Balance': float(balance)})
    return pd.DataFrame(rows), emi, float(interest_total)


def check_eligibility(

        borrower,
        loan_amount

):
    # TAG: ELIGIBILITY RULE - checks requested loan against income-based maximum capacity.

    monthly_income = borrower["monthly_income"]

    max_allowed = (

        monthly_income
        * 12
        * 5

    )

    eligible = loan_amount <= max_allowed

    return eligible, max_allowed



# ─────────────────────────────────────────────────────────────
# FINAL LOAN DECISION
# ─────────────────────────────────────────────────────────────

def make_loan_decision(

        profit,
        roi,
        eligible

):

    if not eligible:

        return "❌ LOAN REJECTED — Eligibility exceeded"

    if roi >= 0.3:

        return "✅ STRONG ROI — RECOMMENDED FOR APPROVAL"

    elif roi >= 0.1:

        return "⚠ MODERATE ROI — CONDITIONAL APPROVAL"

    else:

        return "❌ LOAN REJECTED — Low Profitability"
# ═══════════════════════════════════════════════════════════════════════
# PROFESSIONAL DASHBOARD ENGINE
# Always generates visualization output
# ═══════════════════════════════════════════════════════════════════════

def generate_dashboard(

        borrower,
        entities,
        income,
        profit,
        roi,
        repayment_df,
        cluster_engine,
        cluster_id,
        risk_tier,
        alternative=None

):

    import matplotlib.pyplot as plt
    import numpy as np

    plt.style.use("dark_background")

    fig = plt.figure(figsize=(18, 10))

    fig.suptitle(
        "MICROCREDIT FINANCIAL DASHBOARD",
        fontsize=18,
        fontweight="bold"
    )



    # ============================
    # PANEL 1 — FINANCIAL OVERVIEW
    # ============================

    ax1 = plt.subplot(2, 3, 1)

    values = [

        borrower["loan_amount"],
        income

    ]

    labels = [

        "Loan Amount",
        "Estimated Income"

    ]

    colors = [

        "#f04e23",
        "#63b33d"

    ]

    bars = ax1.bar(
        labels,
        values,
        color=colors
    )

    ax1.set_title(
        "1. FINANCIAL OVERVIEW (Loan vs Income)"
    )

    for bar in bars:

        height = bar.get_height()

        ax1.text(
            bar.get_x() + bar.get_width()/2,
            height,
            f"₹{height:,.0f}",
            ha="center",
            fontsize=10,
            fontweight="bold"
        )



    # ============================
    # PANEL 2 — PROFIT & ROI
    # ============================

    ax2 = plt.subplot(2, 3, 2)

    vals = [

        profit,
        roi * 100

    ]

    labels = [

        "Net Profit (₹)",
        "ROI (%)"

    ]

    colors = [

        "#3fbf3f",
        "#2f74d0"

    ]

    bars = ax2.bar(
        labels,
        vals,
        color=colors
    )

    ax2.set_title(
        "2. PROFIT & ROI"
    )

    for bar in bars:

        height = bar.get_height()

        ax2.text(
            bar.get_x() + bar.get_width()/2,
            height,
            f"{height:,.1f}",
            ha="center"
        )



    # ============================
    # PANEL 3 — REPAYMENT
    # ============================

    ax3 = plt.subplot(2, 3, 3)

    months = repayment_df["Month"]

    emi_vals = repayment_df["EMI"]

    balance_vals = repayment_df["Balance"]

    ax3.bar(
        months,
        emi_vals,
        color="#a64ac9"
    )

    ax3.set_title(
        "3. REPAYMENT SCHEDULE"
    )

    ax3b = ax3.twinx()

    ax3b.plot(
        months,
        balance_vals,
        color="yellow",
        marker="o"
    )



    # ============================
    # PANEL 4 — NEAREST BUSINESSES
    # ============================

    ax4 = plt.subplot(2, 3, 4)

    if entities["category"] == "Farm":

        df = cluster_engine.farm_df
        name_col = "Crop"

    else:

        df = cluster_engine.dairy_df
        name_col = "Product Name"

    subset = df[
        df["Cluster"] == cluster_id
    ]

    if len(subset) == 0:

        subset = df

    top5 = (

        subset.groupby(name_col)["Revenue"]
        .mean()
        .sort_values(ascending=False)
        .head(5)

    )

    ax4.barh(

        top5.index,
        top5.values,
        color="#42c5d6"

    )

    ax4.set_title(
        "4. NEAREST SIMILAR BUSINESSES"
    )



    # ============================
    # PANEL 5 — CLUSTER REVENUE
    # ============================

    ax5 = plt.subplot(2, 3, 5)

    cluster_rev = (

        df.groupby("Cluster")["Revenue"]
        .mean()

    )

    colors = [

        "orange" if i == cluster_id
        else "#4f81bd"

        for i in cluster_rev.index

    ]

    ax5.bar(

        cluster_rev.index.astype(str),
        cluster_rev.values,
        color=colors

    )

    ax5.set_title(
        f"5. CLUSTER REVENUE (Cluster {cluster_id})"
    )



    # ============================
    # PANEL 6 — ALTERNATIVE
    # ============================

    ax6 = plt.subplot(2, 3, 6)

    if alternative:

        vals = [

            alternative["expected_revenue"],
            alternative["expected_profit"]

        ]

        labels = [

            "Expected Revenue",
            "Expected Profit"

        ]

        colors = [

            "#f04e23",
            "#63b33d"

        ]

        ax6.bar(
            labels,
            vals,
            color=colors
        )

        ax6.set_title(
            "6. ALTERNATIVE BUSINESS"
        )

    else:

        ax6.bar(
            ["Profit"],
            [profit],
            color="#63b33d"
        )

        ax6.set_title(
            "6. PRIMARY BUSINESS PROFIT"
        )



    plt.tight_layout()

    plt.savefig(

        CONFIG["output_graph"],
        dpi=300

    )

    plt.close()

    print(
        "\n📊 Dashboard saved →",
        CONFIG["output_graph"]
    )
# ═══════════════════════════════════════════════════════════════════════
# MAIN PROFESSIONAL APPLICATION ENGINE
# Full Banking Workflow
# ═══════════════════════════════════════════════════════════════════════


def collect_personal_information():

    print("\n  ┌──────────────────────────────────────────────────┐")
    print("  │   SECTION 1  —  PERSONAL INFORMATION              │")
    print("  └──────────────────────────────────────────────────┘")

    borrower = {}

    borrower["name"] = get_valid_name()

    dob, age = get_valid_dob()

    borrower["dob"] = dob
    borrower["age"] = age

    borrower["gender"] = get_valid_gender()

    borrower["mobile"] = get_valid_mobile()

    borrower["address"] = get_valid_address()

    return borrower



# ─────────────────────────────────────────────
# KYC SECTION
# ─────────────────────────────────────────────

def collect_kyc_information():

    print("\n  ┌──────────────────────────────────────────────────┐")
    print("  │   SECTION 2  —  IDENTITY & KYC                   │")
    print("  └──────────────────────────────────────────────────┘")

    id_type = get_valid_id_type()

    id_number = get_valid_id_number(id_type)

    return {

        "id_type": id_type,
        "id_number": id_number

    }



# ─────────────────────────────────────────────
# FINANCIAL SECTION
# ─────────────────────────────────────────────

def collect_financial_information():

    print("\n  ┌──────────────────────────────────────────────────┐")
    print("  │   SECTION 3  —  FINANCIAL BACKGROUND             │")
    print("  └──────────────────────────────────────────────────┘")

    monthly_income = get_positive_number(
        "    Monthly Household Income (₹): "
    )

    bank_account = get_yes_no(
        "    Do you hold a Bank Account? (Y/N): "
    )

    credit_card = get_yes_no(
        "    Do you hold Credit/Debit Card? (Y/N): "
    )

    existing_loan = get_yes_no(
        "    Do you have existing loans? (Y/N): "
    )

    years_business = get_positive_number(
        "    Years in current business: "
    )

    return {

        "monthly_income": monthly_income,
        "bank_account": bank_account,
        "credit_card": credit_card,
        "existing_loan": existing_loan,
        "years_in_business": years_business

    }



# ─────────────────────────────────────────────
# BUSINESS DESCRIPTION SECTION
# ─────────────────────────────────────────────

def collect_business_description():

    print("\n  ┌──────────────────────────────────────────────────┐")
    print("  │   SECTION 4  —  LOAN REQUEST DETAILS             │")
    print("  └──────────────────────────────────────────────────┘")

    print("\n    Select Description Language")

    print("      1 — English")
    print("      2 — Hindi")

    choice = input("    Enter Choice: ")

    if choice == "2":

        print("\n    Enter description in Hindi:")

    else:

        print("\n    Enter description in English:")

    description = input(
        "\n    Your Business Description: "
    )

    return description



# ─────────────────────────────────────────────
# COLLATERAL SECTION
# ─────────────────────────────────────────────

def collect_collateral():

    print("\n  ┌──────────────────────────────────────────────────┐")
    print("  │   SECTION 5  —  COLLATERAL & SECURITY            │")
    print("  └──────────────────────────────────────────────────┘")

    collateral = get_yes_no(
        "    Do you have collateral? (Y/N): "
    )

    collateral_type = None

    if collateral == "Yes":

        collateral_type = input(
            "    Type of collateral: "
        )

    guarantor = get_yes_no(
        "    Do you have guarantor? (Y/N): "
    )

    return {

        "collateral": collateral,
        "collateral_type": collateral_type,
        "guarantor": guarantor

    }



# ─────────────────────────────────────────────
# FINAL REPORT GENERATION
# ─────────────────────────────────────────────

def generate_final_report(

        borrower,
        entities,
        income,
        profit,
        roi,
        decision,
        repayment_df,
        alternative=None

):

    sentiment, confidence = analyze_sentiment(
        borrower["description"]
    )

    print("\n" + HDIVIDER)
    print("   MICROCREDIT APPRAISAL REPORT")
    print(
        "   Generated:",
        datetime.now().strftime(
            "%d-%b-%Y  %I:%M %p"
        )
    )
    print(HDIVIDER)



    # =====================================================
    # APPLICANT DETAILS
    # =====================================================

    print("\n   APPLICANT DETAILS")
    print(DIVIDER)

    print(
        f"\n   Applicant Name : {borrower['name']}"
    )

    print(
        f"   Age            : {borrower['age']} Years"
    )

    print(
        f"   Mobile Number  : {borrower['mobile']}"
    )

    print(
        f"   Address        : {borrower['address']}"
    )



    # =====================================================
    # BUSINESS DESCRIPTION
    # =====================================================

    print("\n" + DIVIDER)
    print("   BUSINESS DESCRIPTION (as provided)")
    print(DIVIDER)

    print(
        "\n   " +
        borrower["description"]
    )



    # =====================================================
    # NLP EXTRACTED ENTITIES
    # =====================================================

    print("\n" + DIVIDER)
    print("   NLP EXTRACTED ENTITIES")
    print(DIVIDER)

    for k, v in entities.items():

        if not k.startswith("_"):

            print(
                f"   {k:20}: {v}"
            )



    # =====================================================
    # SENTIMENT ANALYSIS
    # =====================================================

    print("\n" + DIVIDER)
    print("   SENTIMENT ANALYSIS")
    print(DIVIDER)

    print(
        f"\n   Overall Sentiment : {sentiment}"
    )

    print(
        f"   Confidence Score : {confidence:.2f}"
    )



    # =====================================================
    # FINANCIAL PROJECTION
    # =====================================================

    print("\n" + DIVIDER)
    print("   FINANCIAL PROJECTION")
    print(DIVIDER)

    print(
        f"\n   Estimated Income : ₹{income:,.2f}"
    )

    print(
        f"   Net Profit       : ₹{profit:,.2f}"
    )

    print(
        f"   ROI              : {roi*100:.2f}%"
    )



    # =====================================================
    # REPAYMENT DETAILS
    # =====================================================

    print("\n" + DIVIDER)
    print("   REPAYMENT SUMMARY")
    print(DIVIDER)

    print(
        f"\n   Monthly EMI      : ₹{repayment_df['EMI'].iloc[0]:,.2f}"
    )

    print(
        f"   Loan Duration    : {len(repayment_df)} months"
    )



    # =====================================================
    # FINAL DECISION
    # =====================================================

    print("\n" + DIVIDER)
    print("   LOAN APPRAISAL DECISION")
    print(DIVIDER)

    print(
        f"\n   {decision}"
    )



    # =====================================================
    # ALTERNATIVE BUSINESS (IF FAILED)
    # =====================================================

    if alternative:

        print("\n" + DIVIDER)
        print("   SUGGESTED ALTERNATIVE BUSINESS")
        print(DIVIDER)

        print(
            f"\n   Suggested Business : {alternative['business']}"
        )

        print(
            f"   Location           : {alternative['location']}"
        )

        print(
            f"   Expected Revenue   : ₹{alternative['expected_revenue']:,.2f}"
        )

        print(
            f"   Expected Profit    : ₹{alternative['expected_profit']:,.2f}"
        )

def analyze_sentiment(text):

    text = text.lower()

    # Positive indicators

    positive_words = [

        "increase",
        "expand",
        "profit",
        "growth",
        "stable",
        "improve",
        "develop",
        "good",
        "strong",
        "plan",
        "benefit",
        "efficient",
        "profitable",

        "लाभ",
        "वृद्धि",
        "मजबूत",
        "सफल",
        "अच्छा",
        "फायदा"

    ]


    # Negative indicators

    negative_words = [

        "loss",
        "risk",
        "damage",
        "problem",
        "debt",
        "failure",
        "unstable",
        "weak",
        "bad",

        "हानि",
        "जोखिम",
        "समस्या",
        "नुकसान"

    ]


    pos_score = 0
    neg_score = 0


    for word in positive_words:

        if word in text:

            pos_score += 1


    for word in negative_words:

        if word in text:

            neg_score += 1


    score = pos_score - neg_score


    # Sentiment Decision

    if score > 0:

        sentiment = "POSITIVE"

    elif score < 0:

        sentiment = "NEGATIVE"

    else:

        sentiment = "NEUTRAL"


    # Confidence

    total_words = pos_score + neg_score

    if total_words == 0:

        confidence = 0.50

    else:

        confidence = min(
            abs(score) / (total_words),
            1.0
        )


    return sentiment, confidence
# ═══════════════════════════════════════════════════════════════════════
# FINAL SYSTEM RUNNER
# (Master Controller)
# ═══════════════════════════════════════════════════════════════════════


def run_microloan_system():

    # ─────────────────────────────────────────────
    # SYSTEM INITIALIZATION
    # ─────────────────────────────────────────────

    initialize_system()

    # Load datasets

    farm_df, dairy_df, ag_df = load_all_datasets()

    # Build location list

    location_list = build_location_list(
        farm_df,
        dairy_df,
        ag_df
    )

    # Build cluster engine

    cluster_engine = ClusterEngine(
        farm_df,
        dairy_df
    )

    # Show main portal

    print_main_portal()

    # ─────────────────────────────────────────────
    # SECTION COLLECTION
    # ─────────────────────────────────────────────

    borrower = collect_personal_information()

    kyc = collect_kyc_information()

    financial = collect_financial_information()

    description = collect_business_description()

    collateral = collect_collateral()

    # Merge data

    borrower.update(kyc)

    borrower.update(financial)

    borrower.update(collateral)

    borrower["description"] = description



    # ─────────────────────────────────────────────
    # NLP PROCESSING
    # ─────────────────────────────────────────────

    entities = extract_entities(
        description,
        location_list
    )

    borrower["loan_amount"] = entities.get(
        "loan_amount",
        0
    )



    # ─────────────────────────────────────────────
    # PROCESSING DISPLAY
    # ─────────────────────────────────────────────

    show_processing()



    # ─────────────────────────────────────────────
    # FINANCIAL CALCULATIONS
    # ─────────────────────────────────────────────

    income = estimate_income(
        entities,
        ag_df
    )

    profit, roi = calculate_profit_roi(
        income,
        borrower["loan_amount"]
    )



    risk_tier, annual_rate, score = compute_risk_profile(
        borrower,
        roi
    )



    eligible, max_loan = check_eligibility(
        borrower,
        borrower["loan_amount"]
    )



    repayment_df, emi, total_interest = (
        generate_repayment_schedule(
            borrower["loan_amount"],
            annual_rate,
            CONFIG["repayment_months"]
        )
    )



    # ─────────────────────────────────────────────
    # CLUSTER ANALYSIS
    # ─────────────────────────────────────────────

    cluster_id, category = (
        cluster_engine.assign_cluster(
            entities
        )
    )



    summary = cluster_engine.cluster_summary(
        cluster_id,
        category
    )



    # ─────────────────────────────────────────────
    # FINAL DECISION
    # ─────────────────────────────────────────────

    decision = make_loan_decision(
        profit,
        roi,
        eligible
    )



    alternative = None

    if "REJECTED" in decision:

        alternative = (
            cluster_engine
            .recommend_alternative_business(
                entities.get("location"),
                borrower["loan_amount"]
            )
        )



    # ─────────────────────────────────────────────
    # DASHBOARD GENERATION
    # ─────────────────────────────────────────────

    generate_dashboard(

    borrower,
    entities,
    income,
    profit,
    roi,
    repayment_df,
    cluster_engine,
    cluster_id,
    risk_tier,
    alternative

    ) 



    # ─────────────────────────────────────────────
    # FINAL REPORT DISPLAY
    # ─────────────────────────────────────────────

    generate_final_report(

        borrower,
        entities,
        income,
        profit,
        roi,
        decision,
        repayment_df,
        alternative

    )



# ─────────────────────────────────────────────
# PROGRAM ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print('The Phase 1 interactive CLI is retired because it used unsupported business projections.')
    print('Run python run.py for the supported application, explicit financial inputs and review policy.')
