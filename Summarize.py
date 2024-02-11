


import pandas as pd

def summarize_csv(csv_path):
    try:
        # Load the CSV file
        df = pd.read_csv(csv_path)

        # Perform the group by and aggregation
        summary = df.groupby('Test Case').agg(
            Total=('Result', 'size'),
            Passed=('Result', lambda x: (x == 'Passed').sum()),
            Failed=('Result', lambda x: ((x == 'Failed') | (x == 'Failed with error')).sum()),
            Average_Response_Time=('Response Time', lambda x: pd.to_numeric(x, errors='coerce').mean()),
            Min_Response_Time=('Response Time', 'min'),
            Max_Response_Time=('Response Time', 'max'),
            Common_Selector=('Selector', lambda x: x.mode()[0] if not x.mode().empty else ' ')
        ).reset_index()

        # Round the response times
        for col in ['Average_Response_Time', 'Min_Response_Time', 'Max_Response_Time']:
            summary[col] = summary[col].round(3)

        # Save the summary as a new CSV file
        summary_csv_path = csv_path.replace('.csv', '_summary.csv')
        summary.to_csv(summary_csv_path, index=False)

        return f"Summary saved to {summary_csv_path}"
    except Exception as e:
        return f"Error processing file: {e}"

# File path
file_path = r"C:\Users\epinhasov\PycharmProjects\Clarian\UF_Results\2024-02-07_19-13__10.50.153.201\results_2024-02-07_19-13.csv"

# Generate and save the summary
result = summarize_csv(file_path)
print(result)
