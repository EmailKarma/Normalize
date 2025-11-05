import os
import re
import pandas as pd

# ---------------------------------
# 1. Reference data loaders
# ---------------------------------

def load_reference_names(extra_first_urls=None, extra_last_urls=None,
                         extra_first_local=None, extra_last_local=None):
    import pandas as pd, os

    first_url = "https://raw.githubusercontent.com/smashew/NameDatabases/master/NamesDatabases/first%20names/us.txt"
    last_url  = "https://raw.githubusercontent.com/smashew/NameDatabases/master/NamesDatabases/surnames/us.txt"

    first_names = set(pd.read_csv(first_url, header=None)[0].astype(str).str.strip().str.lower())
    last_names  = set(pd.read_csv(last_url,  header=None)[0].astype(str).str.strip().str.lower())

    # Optional: extra URLs
    for url in extra_first_urls or []:
        s = set(pd.read_csv(url, header=None)[0].astype(str).str.strip().str.lower())
        first_names |= s
    for url in extra_last_urls or []:
        s = set(pd.read_csv(url, header=None)[0].astype(str).str.strip().str.lower())
        last_names |= s

    # Optional: local text files (one name per line)
    def load_local(path_list):
        out = set()
        for p in path_list or []:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    out |= {line.strip().lower() for line in f if line.strip()}
        return out

    first_names |= load_local(extra_first_local)
    last_names  |= load_local(extra_last_local)

    return first_names, last_names


# ---------------------------------
# 2. Name email helpers
# ---------------------------------

def email_supports_person(email: str, first_clean: str, last_clean: str) -> bool:
    if not isinstance(email, str) or "@" not in email:
        return False
    local = email.split("@", 1)[0].lower()
    # Strip everything except letters to allow matching against concatenations
    local_alpha = re.sub(r"[^a-z]", "", local)
    f = re.sub(r"[^a-z]", "", first_clean.lower())
    l = re.sub(r"[^a-z]", "", last_clean.lower())
    if not f or not l:
        return False
    # direct patterns: first.last, first_last, first-last
    if f in local and l in local:
        # also check common concatenations
        if (f + l) in local_alpha or (l + f) in local_alpha:
            return True
        # or separated by punctuation
        if re.search(rf"\b{re.escape(f)}[-._]{re.escape(l)}\b", local):
            return True
    return False

# ---------------------------------
# 3. Name casing helpers
# ---------------------------------

LOWERCASE_PREFIXES = {
    "van", "von", "der", "den", "de", "del", "della",
    "du", "la", "le", "di", "da", "dos", "das"
}

BUSINESS_KEYWORDS = [
    "inc", "inc.", "ltd", "ltd.", "corp", "corporation",
    "llc", "group", "holdings", "consulting", "agency",
    "studio", "marketing", "solutions", "company", "co.",
    "partners", "associates", "enterprise", "enterprises",
    "support","team","dept","department","customer",
    "service","billing","sales"
]

def smart_case_token(token: str) -> str:
    """
    Apply human-ish casing to a single token.
    Handles:
      - O'NEILL -> O'Neill
      - MCDONALD -> McDonald
      - MACDONALD -> MacDonald (best effort, heuristic)
      - JEAN-LUC -> Jean-Luc
    Falls back to token.capitalize() if nothing special.
    """

    if not token:
        return token

    t = token.lower()

    # O'Neill / D'Angelo style
    if "'" in t:
        parts = t.split("'")
        parts = [p.capitalize() for p in parts]
        return "'".join(parts)

    # Hyphenated names: Jean-Luc
    if "-" in t:
        return "-".join([smart_case_token(p) for p in t.split("-")])

    # McDonald heuristic
    if t.startswith("mc") and len(t) > 2:
        return "Mc" + t[2:].capitalize()

    # MacDonald heuristic
    if t.startswith("mac") and len(t) > 3:
        return "Mac" + t[3:].capitalize()

    # Default
    return t.capitalize()


def smart_case_full(name: str) -> str:
    """
    Apply smart_case_token to each space-delimited part.
    Keep certain lowercase particles (van, de, etc.) in lowercase,
    unless they are the first token.
    """

    if not isinstance(name, str):
        return ""

    # collapse multiple spaces
    name = re.sub(r"\s+", " ", name.strip())

    if not name:
        return ""

    tokens = name.split(" ")
    out_tokens = []

    for i, tok in enumerate(tokens):
        lower_tok = tok.lower()

        if i > 0 and lower_tok in LOWERCASE_PREFIXES:
            # keep particles lowercase if not first word
            out_tokens.append(lower_tok)
        else:
            out_tokens.append(smart_case_token(tok))

    return " ".join(out_tokens)

DEPT_KEYWORDS = {"support","team","dept","department","customer","service","billing","sales","marketing"}

def plausible_surname(last_clean: str) -> bool:
    import re
    if not isinstance(last_clean, str):
        return False
    # allow letters, spaces, hyphens, apostrophes
    core = re.sub(r"[^A-Za-z' -]", "", last_clean).strip()
    if not core:
        return False
    # block department words
    words = {w.lower() for w in re.split(r"\s+", core) if w}
    if words & DEPT_KEYWORDS:
        return False
    # require a reasonable length once punctuation is removed
    alphas = re.sub(r"[^A-Za-z]", "", core)
    return 2 <= len(alphas) <= 40

# ---------------------------------
# 3. Business detection
# ---------------------------------

def looks_like_business(first_raw: str, last_raw: str) -> bool:
    """
    If we see business-y keywords in either field, call it a business.
    """
    combined = f"{first_raw} {last_raw}".lower()
    for kw in BUSINESS_KEYWORDS:
        if kw in combined:
            return True
    # non-person characters like '&' or digits in "name" are also strong signals
    if re.search(r"[0-9/&]", combined):
        return True
    return False


# ---------------------------------
# 4. Person / Undetermined classification
# ---------------------------------

def is_person(first_clean: str,
              last_clean: str,
              first_names_set: set,
              last_names_set: set) -> bool:
    """
    Rule-based 'is this a person' test.

    We consider multiword names valid if all first-name tokens are known
    given names, and at least one last-name token is a known surname.

    We ignore punctuation in tokens for matching, except we keep hyphen
    and apostrophe logic by normalising those out for lookup.
    """

    if not first_clean or not last_clean:
        return False

    # Break names into tokens on spaces and hyphens
    def tokens_from(value: str):
        # keep apostrophes and hyphens for casing,
        # but strip them before lookup
        raw_tokens = re.split(r"\s+", value.strip())
        final_tokens = []
        for rt in raw_tokens:
            # split hyphenated parts into individual surname/given-name parts
            for piece in rt.split("-"):
                piece_core = piece.replace("'", "")
                if piece_core:
                    final_tokens.append(piece_core.lower())
        return final_tokens

    first_tokens = tokens_from(first_clean)
    last_tokens = tokens_from(last_clean)

    if not first_tokens or not last_tokens:
        return False

    # All first name tokens must be recognised given names
    for t in first_tokens:
        if t not in first_names_set:
            return False

    # At least one last name token must be recognised surname
    if not any(t in last_names_set for t in last_tokens):
        return False

    return True


# ---------------------------------
# 5. Row processor
# ---------------------------------

def process_chunk(df, first_names_set, last_names_set,
                  first_col="FirstName", last_col="LastName"):
    """
    Take a dataframe chunk.
    Create FirstName_Clean, LastName_Clean, and Type.
    Return modified chunk (new columns appended).
    """

    # Ensure columns exist, even if missing
    if first_col not in df.columns:
        df[first_col] = ""
    if last_col not in df.columns:
        df[last_col] = ""

    # Clean / normalise case
    df["FirstName_Clean"] = df[first_col].astype(str).apply(smart_case_full)
    df["LastName_Clean"] = df[last_col].astype(str).apply(smart_case_full)

    types = []
    emails = df["Email"].astype(str) if "Email" in df.columns else [""] * len(df)

    for i, (first_raw, last_raw, first_clean, last_clean, email) in enumerate(
        zip(
            df[first_col].astype(str),
            df[last_col].astype(str),
            df["FirstName_Clean"],
            df["LastName_Clean"],
            emails
        )
    ):
        if looks_like_business(first_raw, last_raw):
            types.append("Business")
        elif is_person(first_clean, last_clean, first_names_set, last_names_set):
            types.append("Person")
        elif email_supports_person(email, first_clean, last_clean):
            types.append("Person")
        elif first_clean and first_clean.split()[0].lower() in first_names_set \
            and plausible_surname(last_clean) \
            and not looks_like_business(first_raw, last_raw):
            # Fallback: strong first-name evidence + plausible last name
            types.append("Person")
        else:
            types.append("Undetermined")

    df["Type"] = types

    return df

# ---------------------------------
# 6. Main runner
# ---------------------------------

def main():
    src_path = input("Enter path to source file (CSV or XLSX): ").strip()

    if not os.path.exists(src_path):
        print("File not found.")
        return

    base, ext = os.path.splitext(src_path)
    out_path = f"{base}_output.csv"

    # Load reference sets once
    print("Loading reference name lists...")
    first_names_set, last_names_set = load_reference_names()

    # Streaming for CSV, direct load for XLSX
    if ext.lower() == ".csv":
        # Create / overwrite output with header on first chunk
        first_write = True

        for chunk in pd.read_csv(src_path, chunksize=100000, dtype=str):
            processed = process_chunk(chunk, first_names_set, last_names_set)

            processed.to_csv(
                out_path,
                mode="w" if first_write else "a",
                header=first_write,
                index=False
            )
            first_write = False

        print(f"Done. Wrote {out_path}")

    elif ext.lower() in [".xls", ".xlsx"]:
        df = pd.read_excel(src_path, dtype=str)
        processed = process_chunk(df, first_names_set, last_names_set)
        processed.to_csv(out_path, index=False)
        print(f"Done. Wrote {out_path}")

    else:
        print("Unsupported file type. Please provide .csv, .xls, or .xlsx.")


if __name__ == "__main__":
    main()
