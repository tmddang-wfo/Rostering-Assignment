import json
import pandas as pd
from datetime import datetime

input_data_dir = "C:\\Users\\trinh\\WS_Python\\genesix-assignment\\rostering-assignment\\monthly_data.xlsx"
roster_dates = pd.read_excel(input_data_dir, header=None, sheet_name="roster_date")

#-----Scheduling parameters-----
staff_num = 9
shift_num = 7
week_num = 4
roster_start_date = "2020-12-09"
roster_end_date = "2021-01-05"
days_num = len(roster_dates.columns)
default_day_type = "weekday"
default_morning_shift_coverage = 4
default_afternoon_shift_coverage = 3

#-----Generate staffs data-----
staffs = []

default_agency = "agency_1"

for idx in range(staff_num):
    staff = {
                "id": idx + 1,
                "agency": default_agency,
                "fixedShiftGroup": False,
                "alwaysOffOnPH": False, 
            }
    staffs.append(staff)

for staff in staffs:
    if staff["id"] in [5, 6]:
        staff["agency"] = "Agency_3"
    elif staff["id"] in [7, 8,9]:
        staff["agency"] = "Agency_2"
    elif staff["id"] in [1, 6]:
        staff["fixedShiftGroup"] = True
    elif staff["id"] in [2, 3, 4]:
        staff["alwaysOffOnPH"] = True

#-----Generate dummy data------
dummy = [
    {"id": 1,
     "agency": "agency_1"
     },
     {"id": 2,
     "agency": "agency_2"
     },
     {"id": 3,
     "agency": "agency_3"
     },
]


#-----Generate shifts data-----
shifts = [
    {
        "id": "M1",
        "duration": 8,
        "workingShift": True,
        "shiftType": "morning"
    },
    {
        "id": "M2",
        "duration": 7,
        "workingShift": True,
        "shiftType": "morning"
    },
    {     
        "id": "M3",
        "duration": 4,
        "workingShift": True,
        "shiftType": "morning"
    },
    {
        "id": "A1",
        "duration": 8,
        "workingShift": True,
        "shiftType": "afternoon"
    },
    {
        "id": "A2",
        "duration": 7,
        "workingShift": True,
        "shiftType": "afternoon"
    },
    {
        "id": "DO",
        "duration": 0,
        "workingShift": True,
        "shiftType": "other"
    },
    {
        "id": "PH",
        "duration": 8,
        "workingShift": False,
        "shiftType": "other"
    },
    {
        "id": "Empty",
        "durarion": 0,
        "workingShift": False,
        "shiftType": "other"
    },
]

days = []
day_count = 0

for i in range(days_num):
    date_value = roster_dates.iloc[0, i]
    day =   {
                "date": date_value.strftime("%Y-%m-%d"),
                "id": day_count,
                "dayOfWeek": date_value.weekday(), 
                "dayType": default_day_type,
                "week": day_count // 7 + 1,
                "morningShiftCov": default_morning_shift_coverage,
                "afternoonShiftCov": default_afternoon_shift_coverage,
            }
    day_count += 1
    days.append(day)


for day in days:
    if day["dayOfWeek"] > 5:
        day["dayType"] = "weekend"
        day["morningShiftCov"] = 3
    elif day["date"] in ["2019-24-12", "2019-25-12", "2019-12-31", "2020-01-01"]:
        day["dayType"] = "PH"
        day["morningShiftCov"] = 3

scheduling_data = {
    "staffs": staffs,
    "dummy": dummy,
    "shifts": shifts,
    "days": days
}

with open("scheduling_data.json", "w") as json_file:
    json.dump(scheduling_data, json_file, indent=4)

print(shifts[0]["id"])