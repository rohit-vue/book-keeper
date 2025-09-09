import pandas as pd
import openai
import json

# Helper function to find a valid column from a list of possibilities
def find_column(df, possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    return None

def process_transactions(qbo_transactions_df, qbo_accounts_df, qbo_classes_df, api_key):
    openai.api_key = api_key
    
    account_list = "\n- ".join(qbo_accounts_df.iloc[:, 0].dropna().astype(str).unique().tolist())
    class_list = "\n- ".join(qbo_classes_df.iloc[:, 0].dropna().astype(str).unique().tolist())
    
    # Find the correct columns dynamically
    uncategorized_col = find_column(qbo_transactions_df, ['Account', 'SPLIT', 'Category'])
    description_col = find_column(qbo_transactions_df, ['Description', 'MEMO/DESCRIPTION', 'Memo'])

    if not uncategorized_col or not description_col:
        raise ValueError("Could not find the necessary 'Account' or 'Description' columns in the transaction file.")

    qbo_transactions_df['Suggested Expense Account'] = ''
    qbo_transactions_df['Suggested Class'] = ''
    qbo_transactions_df['Suggested Vendor'] = ''
    qbo_transactions_df['Confidence'] = ''

    for index, row in qbo_transactions_df.copy().iterrows():
        if pd.isna(row.get(uncategorized_col)) or row.get(uncategorized_col) == '':
            description = row.get(description_col, '')
            
            prompt = f"""
            You are an expert accountant tasked with categorizing a financial transaction. 
            Analyze the transaction description and suggest an appropriate Expense Account, Class, and Vendor.

            **Instructions:**
            1.  You MUST choose an "Expense Account" from the "Available Expense Accounts" list.
            2.  You MUST choose a "Class" from the "Available Classes" list.
            3.  Infer a plausible "Vendor" name from the transaction description (e.g., "Amazon", "Home Depot").
            4.  Provide your answer ONLY in the specified JSON format. Do not add any other text or explanations.

            **Transaction Details:**
            - Description: "{description}"

            **Available Expense Accounts:**
            - {account_list}

            **Available Classes:**
            - {class_list}

            **Output Format (JSON only):**
            {{
              "suggested_account": "string",
              "suggested_class": "string",
              "suggested_vendor": "string"
            }}
            """
            
            # --- THIS IS THE CORRECTED SECTION ---
            try:
                response = openai.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                
                result = json.loads(response.choices[0].message.content)
                
                qbo_transactions_df.at[index, 'Suggested Expense Account'] = result.get('suggested_account', 'AI Error')
                qbo_transactions_df.at[index, 'Suggested Class'] = result.get('suggested_class', 'AI Error')
                qbo_transactions_df.at[index, 'Suggested Vendor'] = result.get('suggested_vendor', 'AI Error')
                qbo_transactions_df.at[index, 'Confidence'] = '75% (AI Suggestion)'
            
            # --- THE MISSING BLOCK IS NOW HERE ---
            except Exception as e:
                print(f"Error processing row {index}: {e}")
                qbo_transactions_df.at[index, 'Confidence'] = 'Error: Could not process'

    return qbo_transactions_df