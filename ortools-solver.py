from ortools.linear_solver import pywraplp
import json

with open("scheduling_data.json", "r") as f:
    scheduling_data = json.load(f)

# staffs = scheduling_data["staffs"]
# for staff in staffs:
#     print(staff["id"])

def init_solver(current_week):
    solver = pywraplp.Solver.CreateSolver('GLOP')

    #Define sets and indices
    staffs = scheduling_data["staffs"]
    dummy = scheduling_data["dummy"]
    shifts = scheduling_data["shifts"]
    days = scheduling_data["days"]
    current_week = current_week

    staffs_list = (staff["id"] for staff in staffs)
    dummy_list = (dum["id"] for dum in dummy)
    shifts_list = (shift["id"] for shift in shifts)
    days_list = (day["dayOfWeek"] for day in days if day["week"] == current_week)

    #Define parameters
    agency_list = ["agency_1, agency_2, agency_3"]
    penalty = 100
    weekly_WH = 44
    week_start_idx = 0
    week_last_idx = 6

    #Define decision variables
    x = {(i,j,k): solver.IntVar(0.0, 1.0, f'x[Staff_{i}, {j}, {k}]') 
                                 for i in staffs_list
                                 for j in shifts_list
                                 for k in days_list}
    
    z = {(i_prime, j, k): solver.IntVar(0.0, 1.0, f'x[Dummy_{i_prime}, {j}, {k}]')
                                for i_prime in staffs_list
                                for j in shifts_list
                                for k in days_list}
    
    gap_WH = {i: solver.IntVar(0.0, solver.infinity(), f'GapWH_{i}') for i in staffs_list}
    
    actual_WH = {i: solver.IntVar(0.0, solver.infinity(), f'ActualWH_{i}') for i in staffs_list}

    #Define set of constraints
    #Each staff works exactly one shift per day
    for k in days_list:
        for i in staffs_list:
            solver.Add(sum(x(i,j,k)) <= 1 for j in shifts_list)

    #Each staff takes 1 DO per week
    for i in staffs_list:
            solver.Add(sum(x(i,"DO",k) == 1) for k in days_list)

    #Assign PH shift to staff whho needs it
    for day in days:
        if day["dayType"] == "PH":
            for staff in staffs:
                if staff["alwaysOffOnPH"]:
                      solver.Add(x(staff["id"],"PH",k) == 1)
                else:
                     solver.Add(x(staff["id"], "PH", k) == 0)
        else:
            for i in staffs_list:
                 solver.Add(x(i,"PH", k) == 0)

    #Calculate actual working hours for each staff
    for i in staffs_list:
        solver.Add(gap_WH(i) == sum(x(i,j,k)*shifts[j]["duration"] 
                                    for j in shifts_list 
                                    for k in days_list))
        
    #Calculate the gap working hours for each staff per week (linearize)
    for i in staffs_list:
         solver.Add(gap_WH(i) >= weekly_WH - actual_WH(i))
                     
    #Calculate the gap working hours for each staff per week (linearize)
    for i in staffs_list:
         solver.Add(gap_WH(i) >= actual_WH(i) - weekly_WH)

    #Undesire afternoon shift after shift DO 
    for i in staffs_list:
         for k in days_list:
              if k != week_last_idx:
                for shift in shifts:
                    if shift["shiftType"] == "afternoon":
                            solver.Add(x(i,"DO",k) + sum(x(i,shift["id"],k) 
                                                         for shift in shifts 
                                                         if shift["shiftType"] == "afternoon") <= 1)
    
    #Undesire afternoon shift after shift PH
    for i in staffs_list:
         for k in days_list:
              if k != week_last_idx:
                for shift in shifts:
                    if shift["shiftType"] == "afternoon":
                            solver.Add(x(i,"PH",k) + sum(x(i,shift["id"],k) 
                                                         for shift in shifts if shift["shiftType"] == "afternoon") <= 1)

    #Undesire 3 consecutive afternoon shifts
    for i in staffs_list:
         for k in days_list:
              if k not in [week_start_idx, week_last_idx]:
                   day_0 =  sum(x(i,shift["id"],k-1) 
                                for shift in shifts if shift["shiftType"] == "afternoon")   

                   day_1 =  sum(x(i,shift["id"],k) 
                                for shift in shifts if shift["shiftType"] == "afternoon")

                   day_2 = sum(x(i,shift["id"],k+1) 
                                for shift in shifts if shift["shiftType"] == "afternoon")   

                   solver.Add(day_0 + day_1 + day_2 <= 2)
    
    #Morning shift coverage requirement
    for day in days:
         solver.Add(sum(x(i,shift["id"],day["id"]) 
                        for i in staffs_list for shift in shifts if shift["shiftType"] == "morning")
                    # + sum(z(i_prime, shift["id"], day["id"])
                    #       for i_prime in dummy_list for shift in shifts if shift["shiftType"] == "morning")
                    == day["morningShiftCov"])
         
    #Afternoon shift coverage requirement
    for day in days:
         solver.Add(sum(x(i,shift["id"],day["id"]) 
                        for i in staffs_list for shift in shifts if shift["shiftType"] == "afternoon")
                    # + sum(z(i_prime, shift["id"], day["id"])
                    #       for i_prime in dummy_list for shift in shifts if shift["shiftType"] == "afternoon")
                    == day["afternoonShiftCov"])

    #Morning Agency coverage requirement (soft)
    for k in days_list:
        for agency in agency_list:
             solver.Add(sum(x(staff["id"],shift["id"],k)
                            for staff in staffs if staff["agency"] == agency
                            for shift in shifts if shift["shiftType"] == "morning")
                        + sum(z(dum["id"],shift["id"],k)
                            for dum in dummy if d["agency"] == agency
                            for shift in shifts if shift["shiftType"] == "morning")
                              >= 1)
                        

    #Afternoon Agency coverage requirement (soft)
    for k in days_list:
        for agency in agency_list:
             solver.Add(sum(x(staff["id"],shift["id"],k)
                            for staff in staffs if staff["agency"] == agency
                            for shift in shifts if shift["shiftType"] == "afternoon")
                        # + sum(z(dum["id"],shift["id"],k)
                        #     for dum in dummy if d["agency"] == agency
                        #     for shift in shifts if shift["shiftType"] == "afternoon")
                              >= 1)