from ortools.linear_solver import pywraplp
import json

with open("scheduling_data.json", "r") as f:
    scheduling_data = json.load(f)

def solve(current_week=1):
    solver = pywraplp.Solver.CreateSolver('SCIP')

    #Define sets and indices
    staffs = scheduling_data["staffs"]
    shifts = scheduling_data["shifts"]
    period = scheduling_data["periods"]
    current_week = current_week

    staffs_list = [staff["id"] for staff in staffs]
    dummy_list = []
    shifts_list = [shift["id"] for shift in shifts]
    days = [day for day in period 
                 if day["week"] == current_week]
    days_list = [day["dayOfWeek"] 
                 for day in days 
                 if day["week"] == current_week]

    #Define parameters
    agency_list = ["agency_1", "agency_2", "agency_3"]
    week_start_idx = 0
    week_last_idx = 6


    #Define decision variables
    x = {(i,j,k): solver.IntVar(0.0, 1.0, f'x_{i}_{j}_{k}') 
                                 for i in staffs_list
                                 for j in shifts_list
                                 for k in days_list}
    
    z = {}
    
    actual_WH = {i: solver.IntVar(0.0, solver.infinity(), f'ActualWH_{i}') for i in staffs_list}

    #Define set of constraints
    #Each staff works exactly one shift per day (hard) => keep
    for k in days_list:
        for i in staffs_list:
            solver.Add(solver.Sum(x[(i,j,k)] for j in shifts_list) == 1)

    #Each staff takes 1 DO per week (hard) => keep
    for i in staffs_list:
            solver.Add(solver.Sum(x[(i,"DO",k)] for k in days_list) == 1)

    #Assign PH shift to staff whho needs it (hard) => keep
    for staff in staffs:
        for day in days:
            if staff["alwaysOffOnPH"] and day["isHoliday"]:
                    solver.Add(x[(staff["id"], "PH", day["dayOfWeek"])] == 1)
            else:
                solver.Add(x[(staff["id"], "PH", day["dayOfWeek"])] == 0)

    #Achive 0.5 working days per week for staff who needs it (hard)
    for staff in staffs:
         if staff["desiredHalfDayShift"]:
              solver.Add(solver.Sum(x[(staff["id"],"M3",k)] for k in days_list) == 1)
                        
    #Undesired 0.5 working days per week for staffs who do NOT need it (hard)
    for staff in staffs:
         if not staff["desiredHalfDayShift"]:
            solver.Add(solver.Sum(x[(staff["id"],"M3",k)] for k in days_list) == 0)

    #Calculate actual working hours for each staff (axiliary)
    for i in staffs_list:
        solver.Add(actual_WH[i] == solver.Sum(x[(i,shift["id"],k)]*shift["duration"] 
                                    for shift in shifts 
                                    for k in days_list))


    #Each staff must work exactly 44 hours per week (hard) => relaxed
    z["Increment_hours"] = {i: solver.IntVar(0.0, solver.infinity(), f'z_{"Increment_hours"}_{i}') for i in staffs_list}
    z["Redundant_hours"] = {i: solver.IntVar(0.0, solver.infinity(), f'z_{"Redundant_hours"}_{i}') for i in staffs_list}
    
    for i in staffs_list:
         solver.Add(actual_WH[i] + z["Increment_hours"][i] - z["Redundant_hours"][i] == 44)
         dummy_list.append(z["Increment_hours"][i])
         dummy_list.append(z["Redundant_hours"][i])

    #Undesire afternoon shift after shift DO (soft)
    z["DO-AM_shifts"] = {(i,k): solver.IntVar(0, solver.infinity(), f'z_{"DO-AM_shifts"}_{i}_{k}') 
         for i in staffs_list 
         for k in days_list if k!=week_last_idx}

    for i in staffs_list:
         for k in days_list:
              if k != week_last_idx:
                solver.Add(x[(i,"DO",k)] + solver.Sum(x[(i,shift["id"],k+1)] 
                                                for shift in shifts 
                                                if shift["shiftType"] == "afternoon")
                            <= 1 + z["DO-AM_shifts"][(i,k)])
                dummy_list.append(z["DO-AM_shifts"][(i,k)])
    
    #Undesire afternoon shift after shift PH (soft)
    z["PH-AM_shifts"] = {(i,k): solver.IntVar(0, solver.infinity(), f'z_{"PH-AM_shifts"}_{i}_{k}') 
         for i in staffs_list 
         for k in days_list if k!=week_last_idx}
    
    for i in staffs_list:
         for k in days_list:
              if k != week_last_idx:
                for shift in shifts:
                    if shift["shiftType"] == "afternoon":
                            solver.Add(x[(i,"PH",k)] + solver.Sum(x[(i,shift["id"],k+1)]
                                                         for shift in shifts if shift["shiftType"] == "afternoon") 
                                                         <= 1 + z["PH-AM_shifts"][(i,k)])
                            dummy_list.append(z["PH-AM_shifts"][(i,k)])

    #Undesire 3 consecutive afternoon shifts (soft)
    z["3_AM_shifts"] = {(i,k): solver.IntVar(0, solver.infinity(), f'z_{"3_AM_shifts"}_{i}_{k}') 
         for i in staffs_list 
         for k in days_list if k!=week_last_idx}
    
    for i in staffs_list:
         for k in days_list:
              if k not in [week_start_idx, week_last_idx]:
                   day_0 =  solver.Sum(x[(i,shift["id"],k-1)] 
                                for shift in shifts if shift["shiftType"] == "afternoon")   

                   day_1 =  solver.Sum(x[(i,shift["id"],k)] 
                                for shift in shifts if shift["shiftType"] == "afternoon")

                   day_2 = solver.Sum(x[(i,shift["id"],k+1)] 
                                for shift in shifts if shift["shiftType"] == "afternoon")   

                   solver.Add(day_0 + day_1 + day_2 <= 2 + z["3_AM_shifts"][(i,k)])
                   dummy_list.append(z["3_AM_shifts"][(i,k)])
    
    #Morning shift coverage requirement (hard) => relaxed
    z["Morning_General_Cov"] = {k: solver.IntVar(0.0, solver.infinity(), f'z_{"Morning_General_Cov"}_{k}') for k in days_list}

    for day in days:
         solver.Add(solver.Sum(x[(i,shift["id"],day["dayOfWeek"])] 
                        for i in staffs_list for shift in shifts if shift["shiftType"] == "morning")
                    >= day["morningShiftCov"] - z["Morning_General_Cov"][day["dayOfWeek"]])
         dummy_list.append(z["Morning_General_Cov"][day["dayOfWeek"]])
         
    #Afternoon shift coverage requirement(hard)
    z["Afternoon_General_Cov"] = {k: solver.IntVar(0.0, solver.infinity(), f'z_{"Afternoon_General_Cov"}_{k}') for k in days_list}
    
    for day in days:
         solver.Add(solver.Sum(x[(i,shift["id"],day["dayOfWeek"])] 
                        for i in staffs_list for shift in shifts if shift["shiftType"] == "afternoon")
                    >= day["afternoonShiftCov"] - z["Afternoon_General_Cov"][day["dayOfWeek"]])
         dummy_list.append(z["Afternoon_General_Cov"][day["dayOfWeek"]])

    #Morning Agency coverage requirement (soft)
    z["Morning_Agency_Cov"] = {(a,k): solver.IntVar(0, solver.infinity(), f'z_{"Morning_Agency_Cov"}_{a}_{k}') 
         for a in agency_list 
         for k in days_list}
    
    for k in days_list:
        for a in agency_list:
             solver.Add(solver.Sum(x[(staff["id"],shift["id"],k)]
                            for staff in staffs if staff["agency"] == a
                            for shift in shifts if shift["shiftType"] == "morning")
                              >= 1 - z["Morning_Agency_Cov"][(a,k)])
             dummy_list.append(z["Morning_Agency_Cov"][(a,k)])
                        

    #Afternoon Agency coverage requirement (hard) => relaxed
    z["Afternoon_Agency_Cov"] = {(a,k): solver.IntVar(0, solver.infinity(), f'z_{"Afternoon_Agency_Cov"}_{a}_{k}') 
         for a in agency_list 
         for k in days_list}

    for k in days_list:
        for a in agency_list:
             solver.Add(solver.Sum(x[(staff["id"],shift["id"],k)]
                            for staff in staffs if staff["agency"] == a
                            for shift in shifts if shift["shiftType"] == "afternoon")
                              >= 1 - z["Afternoon_Agency_Cov"][(a,k)])
             dummy_list.append(z["Afternoon_Agency_Cov"][(a,k)])
    
    #Define objective function
    solver.Minimize(solver.Sum(dummy_list))

    status = solver.Solve()

    if status == pywraplp.Solver.OPTIMAL:
        print(f'Objective value = {solver.Objective().Value()}')
        for k in days_list:
            print(f'---Day {k}---')
            for i in staffs_list:
                 for j in shifts_list:
                    val = x[(i,j,k)].solution_value()
                    if val > 0:
                         print(x[(i,j,k)])
        print('---Dummy variables---')
        for z in dummy_list:
             val = z.solution_value()
             if val > 0:
                  print(f'{z} = {val}')

    elif status == pywraplp.Solver.INFEASIBLE:
        print('Infeasible solution')
    else:
         print("Solver can not find any optimal solution")

solve()