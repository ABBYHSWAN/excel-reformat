import streamlit as st
import io
import pandas as pd
import numpy as np
import zipfile
import ast
import re

# --- Hide Streamlit default error tracebacks ---
hide_streamlit_style = """
    <style>
    .stException {display: none;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- Page setup ---
st.set_page_config(page_title="File Reformatting App", 
                    page_icon="📊",
                    layout="centered")

st.title("📁 Platform Eleven to Investran  Excel Sheet Converter")
st.caption("Easily upload, process, and download your Investran data files.")

# --- File uploaders ---
st.subheader("Step 1️⃣: Upload Files")
# Initialize dataframes if uploaded 
trans_df, cont_df = None, None

# --- Combine files into one DataFrame ---
def combine_uploaded_files(uploaded_files):
    if not uploaded_files:
        return None
    dfs = []
    for file in uploaded_files:
        try:
            df = pd.read_csv(file)
            dfs.append(df)
        except Exception as e:
            st.warning(f"⚠️ Could not read {file.name}: {e}")
    if dfs:
        combined_df = pd.concat(dfs, ignore_index=True)
        st.success(f"✅ Combined {len(dfs)} files ({sum(len(d) for d in dfs)} total rows)")
        return combined_df
    return None

# Upload and process Transaction files
uploaded_trans = st.file_uploader("Upload **TRANSACTION** CSV files (you may select multiple files)", 
                                  type=["csv"], 
                                  accept_multiple_files=True) 

trans_df = combine_uploaded_files(uploaded_trans)

if trans_df is not None:
    st.write("Preview of combined TRANSACTION file:")
    st.dataframe(trans_df.head())

# Upload and process Contact files
uploaded_cont = st.file_uploader("Upload **CONTACT** CSV files (you may select multiple files)", 
                                 type=["csv"],
                                 accept_multiple_files=True)


cont_df = combine_uploaded_files(uploaded_cont)

if cont_df is not None:
    st.write("Preview of combined CONTACT file:")
    st.dataframe(cont_df.head())

# --- Text inputs ---
st.divider()
st.subheader("Step 2️⃣: Provide Input Details")

contact_domain = st.text_input('Enter "Contact Domain" for sheet 1:')
vehicle = st.text_input('Enter "Vehicle" for sheet 4:')
vehicle_close_date = st.text_input('Enter "Specific Vehicle Close Date" (MM/DD/YYYY) for sheet 5:')
commitment_date = st.text_input('Enter "Investor Commitment Date" (MM/DD/YYYY) for sheet 5:')

# --- Button to continue ---
if st.button("Process Data"):
    if trans_df is not None and cont_df is not None:
        st.success("Files and inputs captured successfully!")
        st.write("**Contact Domain:**", contact_domain)
        st.write("**Vehicle:**", vehicle)
        st.write("**Vehicle Close Date:**", vehicle_close_date)
        st.write("**Investor Commitment Date:**", commitment_date)
    else:
        st.error("Please upload both TRANSACTION and CONTACT files before proceeding.")

# ------------------------------------------------------------------------------------------------------------------------

# Initialize additional packages and import and reformat starting CSVs
trans_df = trans_df.reindex(columns=["investorName", "investorSourceId", "fundName", "commitment", "authorizedInvestor", "domicile", 
                                     "formPfInvestorType", "investorType", "isDisregardedEntity", "isUsTaxExempt", "qpAssets25",
                                     "qpAssets5", "signers", "ssn", "ein", "personOrEntity", "state", "street", "city","zip",
                                     "nomineeName", "nomineeAccountNo", "erisaVehicle", "benefitPlanPercent"], fill_value = pd.NA)
cont_df = cont_df.reindex(columns=["transactionContactId", "investmentId", "relationship", "email", "firstName", "lastName","fullName",
                                   "contactPhone"], fill_value = pd.NA)

pd.set_option('display.max_columns', None)

# Intialize 5 dataframes with column names. To be populated with information later
df1 = pd.DataFrame(columns=["Contact Domain", "Contact File As", "Contact Type", "Individual First Name", "Individual Last Name"])
df2 = pd.DataFrame(columns=["Contact ID", "Contact Type", "Contact Domain", "Contact File As", "Email Email", "Email Email is Default",
                            "Business Address is Default", "Business Address Street", "Business Address City", "Business Address State",
                            "Business Address Zip/Postal Code", "Home Phone", "Primary Phone"])
df3 = pd.DataFrame(columns=["Investor Domain", "Investor Socium ID", "Investor Name", "Linked Contact", "Linked Contact ID",
                            "Linked Contact Type", "Linked Contact Domain", "Client GL Investor Name", "Investor Legal Name",
                            "Investor Classification", "Individual or Organization", "Investor SubType", "Investor Tax ID",
                            "Qualified Purchaser", "Accredited Investor", "Is IRA", "Domicile", "Domestic/Foreign",
                            "Relationship", "Client GL Investor ID", "Tax Exempt", "Disregarded Entity", "ERISA", "ERISA %",
                            "Form PF Investor Type"])
df4 = pd.DataFrame(columns=["Legal Entity", "Vehicle", "Investor"])
df5 = pd.DataFrame(columns=["Legal Entity", "Vehicle", "Specific Vehicle Close Date", "Investor", "Investor Commitment Amount",
                            "Investor Commitment Closing Date", "Investor Commitment Commitment Date"])

# ------------------------------------------------------------------------------------------------------------------------

# Remove unecessary contacts
def parse_signers_robust(value):
    """
    Return a list of integer signer IDs extracted from 'value'.
    Handles formats like:
      - [1234567, 7654321]
      - "[1234567,7654321]" or "[1234567, null]"
      - NaN -> []
    """
    if pd.isna(value):
        return []
    if isinstance(value, (list, tuple)):
        ids = []
        for x in value:
            if isinstance(x, int):
                ids.append(x)
            elif isinstance(x, str) and x.isdigit():
                ids.append(int(x))
        return ids

    s = str(value).strip()
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, (list, tuple)):
            ids = []
            for x in parsed:
                if isinstance(x, int):
                    ids.append(x)
                elif isinstance(x, str) and x.isdigit():
                    ids.append(int(x))
            if ids:
                return ids
    except Exception:
        pass

    found = re.findall(r'\b(\d{7})\b', s)
    return [int(x) for x in found]

# Parse and extract signer IDs
trans_df["parsed_signers"] = trans_df["signers"].apply(parse_signers_robust)
trans_df["first_signer"] = trans_df["parsed_signers"].apply(lambda x: int(x[0]) if len(x) >= 1 else None)
trans_df["second_signer"] = trans_df["parsed_signers"].apply(lambda x: int(x[1]) if len(x) >= 2 else None)

# Build ID sets
first_ids = set(trans_df["first_signer"].dropna().astype(int).tolist())
second_ids = set(trans_df["second_signer"].dropna().astype(int).tolist())
all_signer_ids = set()
for lst in trans_df["parsed_signers"]:
    all_signer_ids.update(lst)

# Keep only rows where transactionContactId is a valid first signer
filtered_cont_df = cont_df[cont_df["transactionContactId"].isin(first_ids)].copy()

# Preserve original order
filtered_cont_df = filtered_cont_df.reset_index(drop=True)

# (Optional) Clean up helper columns if not needed
trans_df.drop(columns=["parsed_signers", "first_signer", "second_signer"], inplace=True)
cont_df = filtered_cont_df

# ------------------------------------------------------------------------------------------------------------------------

# Populate df1
df1["Contact Domain"] = contact_domain
df1["Contact File As"] = cont_df["fullName"]
df1["Contact Type"] = "Individual"
df1["Individual First Name"] = cont_df["firstName"]
df1["Individual Last Name"] = cont_df["lastName"]

# ------------------------------------------------------------------------------------------------------------------------

# Populate df2
df2["Contact ID"] = None # Manual Entry (to be done after files are output)
df2["Contact Type"] = df1["Contact Type"]
df2["Contact Domain"] = df1["Contact Domain"]
df2["Contact File As"] = df1["Contact File As"]
df2["Email Email"] = cont_df["email"]
df2["Email Email is Default"] = np.where(df2["Email Email"].notna(), "yes", pd.NA)
df2["Business Address Street"] = trans_df["street"]
df2["Business Address is Default"] = np.where(df2["Business Address Street"].notna(), "yes", pd.NA)
df2["Business Address City"] = trans_df["city"]

# Assign df2 "Business Address State" using mapping
state_mapping = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "AS": "American Samoa",
	"CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
	"FL": "Florida", "GA": "Georgia","GU": "Guam","HI": "Hawaii","ID": "Idaho","IL": "Illinois",
	"IN": "Indiana","IA": "Iowa","KS": "Kansas","KY": "Kentucky","LA": "Louisiana","ME": "Maine",
	"MD": "Maryland","MA": "Massachusetts","MI": "Michigan","MN": "Minnesota","MS": "Mississippi",
	"MO": "Missouri","MT": "Montana","NE": "Nebraska","NV": "Nevada","NH": "New Hampshire","NJ": "New Jersey",
	"NM": "New Mexico","NY": "New York","NC": "North Carolina","ND": "North Dakota","MP": "Northern Mariana Islands",
	"OH": "Ohio","OK": "Oklahoma","OR": "Oregon","PA": "Pennsylvania","PR": "Puerto Rico","RI": "Rhode Island",
	"SC": "South Carolina","SD": "South Dakota","TN": "Tennessee","TX": "Texas","TT": "Trust Territories",
	"UT": "Utah","VT": "Vermont","VA": "Virginia","VI": "Virgin Islands","WA": "Washington","WV": "West Virginia",
	"WI": "Wisconsin","WY": "Wyoming",
}
df2["Business Address State"] = trans_df["state"].map(state_mapping).fillna(trans_df["state"])

df2["Business Address Zip/Postal Code"] = trans_df["zip"]
df2["Home Phone"] = cont_df["contactPhone"]
df2["Primary Phone"] = np.where(df2["Home Phone"].notna(), "yes", pd.NA)

# ------------------------------------------------------------------------------------------------------------------------

# Populate df 3
df3["Investor Domain"] = df1["Contact Domain"]
df3["Investor Socium ID"] = trans_df["investorSourceId"]
df3["Investor Name"]  = trans_df["investorName"] + ":  " + trans_df["investorSourceId"]
df3["Linked Contact"] = df2["Contact File As"]
df3["Linked Contact ID"] = df2["Contact ID"]
df3["Linked Contact Type"] = df2["Contact Type"]
df3["Linked Contact Domain"] = df2["Contact Domain"]
df3["Client GL Investor Name"] = trans_df["investorName"]
df3["Investor Legal Name"] = trans_df["investorName"]

# Assign df3 "Investor Classification" using np.where
df3["Investor Classification"] = np.where(trans_df["personOrEntity"] == "entity", "Organization", "Individual")

df3["Individual or Organization"] = df3["Investor Classification"]

# Assign df3 "Investor SubType" using a mapping
investor_subtype_mapping = {
    "trust": "Trust",
    "revocableTrust": "Revocable Trust",
    "jointTenants": "Joint TIC",
    "tenantsInCommon": "Joint TIC",
    "nonRetirement": "Natural Person",
    "partnership": "Limited Partnership",
    "llc": "Limited Liability Company",
    "corporation": "Corporation",
    "ira": "IRA",
    "privatePension": "Pension Plan",
    "foundation": "Foundation",
    "governmentNonPension": "Government Entity"
}
df3["Investor SubType"] = trans_df["investorType"].map(investor_subtype_mapping).fillna("Unrecognized value") # Handle unrecognized values

# Assign df3 "Investor Tax ID" based on 'ssn' and 'ein'
def get_tax_id(row):
    ssn = row["ssn"]
    ein = row["ein"]
    if pd.notna(ssn) and pd.isna(ein):
        return ssn
    elif pd.isna(ssn) and pd.notna(ein):
        return ein
    else:
        return "Error: Exactly one of SSN or EIN must be populated"

df3["Investor Tax ID"] = trans_df.apply(get_tax_id, axis=1)
df3["Investor Tax ID"] = df3["Investor Tax ID"].astype(str).str.replace("-", "")

# Assign "Qualified Purchaser" using mapping
qualified_purchaser_mapping = {
    "yes": "Y",
    "no": "N"
}
df3["Qualified Purchaser"] = trans_df["qpAssets5"].map(qualified_purchaser_mapping).fillna("Y") # Assuming blank means Y

# Assign "Accredited Investor" using mapping
accredited_investor_mapping = {
    "Yes": "Y",
    "No": "N"
}
df3["Accredited Investor"] = trans_df["authorizedInvestor"].map(accredited_investor_mapping).fillna("Unrecognized value") # Handle unrecognized values
# If Qualified Purchaser == "Y", then Accredited Investor should also be "Y"
df3.loc[df3["Qualified Purchaser"] == "Y", "Accredited Investor"] = "Y"


# Assign "Is IRA" using np.where
df3["Is IRA"] = np.where(trans_df["investorType"] == "ira", "Y", "N")

# Assign df3 "Domicile" using a mapping
domicile_mapping = {
    "CA": "Canada",
    "KY": "Cayman Islands",
    "JE": "Jersey",
    "LU": "Luxembourg",
    "MC": "Monaco",
    "PA": "Republic of Panama",
    "GB": "Scotland",
    "SG": "Singapore",
    "KR": "South Korea",
    "ES": "Spain",
    "CH": "Switzerland",
    "US": "USA",
}
df3["Domicile"] = trans_df["domicile"].map(domicile_mapping).fillna("Unrecognized value") # Handle unrecognized values

# Assign "Is IRA" using np.where
df3["Domestic/Foreign"] = np.where(df3["Domicile"] == "USA", "Domestic", "Foreign")

df3["Relationship"] = trans_df["nomineeName"]
df3["Client GL Investor ID"] = trans_df["nomineeAccountNo"]

#Assign "Tax Exempt" using mapping
tax_exempt_mapping = {
    "yes": "Y",
    "no": "N"
}
df3["Tax Exempt"] = trans_df["isUsTaxExempt"].map(tax_exempt_mapping)

# Assign "Disregarded Entity" using mapping
disregarded_entity_mapping = {
    "yes": "Y",
    "no": "N"
}
df3["Disregarded Entity"] = trans_df["isDisregardedEntity"].map(disregarded_entity_mapping)

# Assign "ERISA" using np.where
df3["ERISA"] = np.where(trans_df["erisaVehicle"] == "yes", "Y", "N")
#Assign "ERISA" using mapping
erisa_mapping = {
    "yes": "Y",
    "no": "N"
}
df3["ERISA"] = trans_df["erisaVehicle"].map(erisa_mapping)

# Assign "ERISA %" but stripping "%" and makig it a decimal
df3["ERISA %"] = trans_df["benefitPlanPercent"].apply(
    lambda x: float(str(x).replace('%', '')) / 100 if pd.notna(x) else pd.NA)

# Assign "Form PF Investor Type" using mapping
form_pf_investor_type_mapping = {
    "formPfBankThirft": "Bank or Thrift Institution (proprietary)",
    "formPfBrokerDealer": "Broker-Dealer",
    "formPfInsurance": "Insurance Company",
    "formPfNonProfit": "Investment Company registered with the SEC",
    "formPfNonUsMultiple": "Non-Profit",
    "formPfNonUsPerson": "Non-US Individual or Trust",
    "formPfOther": "Non-US Investor beneficial ownership unknown & held through a chain of intermediaries",
    "formPfPension": "Other",
    "formPfPrivateFund": "Pension Plan (Government)",
    "formPfRegInvCo": "Pension plan (Non-Government)",
    "formPfSwf": "Private Fund",
    "formPfUsGov": "Sovereign Wealth Fund / Foreign Official Institution",
    "formPfUsPension": "State or Municipal Government entity (not pension plan)",
    "formPfUsPerson": "United States Individual or Trust"
}
df3["Form PF Investor Type"] = trans_df["formPfInvestorType"].map(form_pf_investor_type_mapping)

# ------------------------------------------------------------------------------------------------------------------------

# Populate df4
df4["Legal Entity"] = trans_df["fundName"]
df4["Vehicle"] = vehicle
df4["Investor"] = df3["Investor Name"]

# ------------------------------------------------------------------------------------------------------------------------

# Populate df5
df5["Legal Entity"] = trans_df["fundName"]
df5["Vehicle"] = df4["Vehicle"]
df5["Specific Vehicle Close Date"] = vehicle_close_date
df5["Investor"] = df3["Investor Name"]
df5["Investor Commitment Amount"] = trans_df["commitment"]
df5["Investor Commitment Closing Date"] = commitment_date
df5["Investor Commitment Commitment Date"] = commitment_date

# ------------------------------------------------------------------------------------------------------------------------

# Make sure manual input domains are properly assigned
df1["Contact Domain"] = contact_domain
df4["Vehicle"] = vehicle
df5["Specific Vehicle Close Date"] = vehicle_close_date
df5["Investor Commitment Closing Date"] = commitment_date
df5["Investor Commitment Commitment Date"] = commitment_date

df2["Contact Domain"] = df1["Contact Domain"]
df3["Investor Domain"] = df1["Contact Domain"]
df3["Linked Contact Domain"] = df2["Contact Domain"]
df5["Vehicle"] = df4["Vehicle"]

# Make sure all sheets have the same number of rows 
trans_df = trans_df.dropna(subset=["investorName"])
num_rows = len(trans_df)

# Assign number of transaction rows to all other DataFrames 
df1 = df1.head(num_rows).copy()
df2 = df2.head(num_rows).copy()
df3 = df3.head(num_rows).copy()
df4 = df4.head(num_rows).copy()
df5 = df5.head(num_rows).copy()

# ------------------------------------------------------------------------------------------------------------------------

# Output DataFrame contnets as excel files 
# Create an in-memory ZIP file
zip_buffer = io.BytesIO()

with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
    # Write each Excel file into the ZIP
    for df, filename in [
        (df1, "1 - Investran Contact Upload.xlsx"),
        (df2, "2 - Investran Contact Details.xlsx"),
        (df3, "3 - Investran Investor Upload.xlsx"),
        (df4, "4 - Investran Specific Investors.xlsx"),
        (df5, "5 - Investran Commitments.xlsx"),
    ]:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Sheet1")
        excel_buffer.seek(0)
        zf.writestr(filename, excel_buffer.read())

# Move to the start of the stream so it can be read
zip_buffer.seek(0)

st.divider()
st.subheader("Step 3️⃣: Process & Download") 

st.markdown("Reminder! - Contact ID fields must be filled manually after running through Investran. " \
            "\n\nThese fields are in sheets **2** and **3**.")

# Streamlit download button for ZIP
st.download_button(
    label="📦 Download All Processed Files (ZIP)",
    data=zip_buffer,
    file_name= "Investran Uploads Reformatted.zip",
    mime= "application/zip"
)

