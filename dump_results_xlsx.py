import pandas as pd
import json

input_json = "result/Q1/scheduling_result.json"
with open(input_json) as file:
    data = json.load(file)

output = []
for day in data['roster_per_day']:
    for key, value in day.items():
        for cell in value:
            output.append(cell)

df = pd.DataFrame(output)

pivot_df = df.pivot(index = 'staff', columns = 'day', values = 'shift')

file_name = "result/Q1/Solution.xlsx"

with pd.ExcelWriter(file_name, mode = 'a', engine = 'openpyxl', if_sheet_exists='replace') as writer:
    pivot_df.to_excel(writer, sheet_name = 'Raw_results')
print("Sucessfully print result to excel file")