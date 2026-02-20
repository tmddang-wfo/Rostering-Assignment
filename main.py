from solver_core import hard_solve, relaxed_solve
import json
from ortools.linear_solver import pywraplp

with open("scheduling_data.json", "r") as f:
    scheduling_data = json.load(f)

staffs = scheduling_data["staffs"]
shifts = scheduling_data["shifts"]
period = scheduling_data["periods"]

staffs_list = [staff["id"] for staff in staffs]
slack = []
shifts_list = [shift["id"] for shift in shifts]

#Define solution structure
scheduling_result = {}
violations = {}

roster_per_day = []

roster_per_staff = []
roster_staffs = {}
for staff in staffs:
     i = staff["id"]
     code = f'staff_{i}'
     roster_staffs.setdefault(code, [])


def export_result(x_var, slack_var, current_week):
    roster_days = {}
    days = [day for day in period 
            if day["week"] == current_week]

    #View roster per day
    for day in days:
             k = day["dayOfWeek"]
             code = (f'day_{day["id"]}')
             roster_days.setdefault(code, [])
             for staff in staffs:
                  i = staff["id"]
                  for shift in shifts:
                       j = shift["id"]
                       val = x_var.get((i,j,k), 0)
                       if val > 0.5:
                            cell = {
                                 "day": day["date"],
                                 "week": day["week"],
                                 "staff": i,
                                 "agency": staff["agency"],
                                 "shift": j,                           
                            }
                            roster_days[code].append(cell)
    roster_per_day.append(roster_days)

    #View roster per staff
    for staff in staffs:
            i = staff["id"]
            code = f'staff_{i}'
            for day in days:
                k = day["dayOfWeek"]
                for shift in shifts:
                    j = shift["id"]
                    val = x_var.get((i,j,k), 0)
                    if val > 0.5:
                        cell = {
                                "date": day["date"],
                                "week": day["week"],
                                "day": k,
                                "dayOfWeek": day["dayOfWeek"],
                                "dayType": day["dayType"],
                                "shift": j,
                        }
                        roster_staffs[code].append(cell)
    

    # #View slack variables created per week
    w_code = f'week_{current_week}'
    violations.setdefault(w_code, {})

    for s_code, s_dict in slack_var.items():
        violations[w_code].setdefault(s_code, [])
        for key, s_info in s_dict.items():
            val = s_info["value"]

            if val > 0:
                violations[w_code][s_code].append({
                    "key": str(key),
                    "slack": val,
                })
        
def run_solver():
    week_list = [1, 2, 3, 4]
    for current_week in week_list:
        print("---------Start solving for ", f'week {current_week}---------')
        result = hard_solve(scheduling_data, current_week)
        if result[0] == None:
            print("Switch to relaxed solving strategy...")
            result = relaxed_solve(scheduling_data, current_week)
            x_var, slack_var = result
            export_result(x_var, slack_var, current_week)
        else:
             x_var, slack_var = result
             export_result(x_var, slack_var, current_week)

    #Add processed rosters for staff out side loop to avoid duplication
    roster_per_staff.append(roster_staffs)

    # #Dump data to json
    scheduling_result = {
            "roster_per_day": roster_per_day,
            "roster_per_staff": roster_per_staff
            }
    with open("result/scheduling_result.json", "w") as json_file:
            json.dump(scheduling_result, json_file, indent=4)
    print("Successfully export scheduling results to json")

    with open("result/violations.json", "w") as json_file:
        json.dump(violations, json_file, indent=4)
    print("Successfully export violation results to json")

if __name__ == "__main__":
    run_solver()


