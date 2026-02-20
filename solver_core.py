from ortools.linear_solver import pywraplp


def hard_solve(scheduling_data, current_week):
    solver = pywraplp.Solver.CreateSolver('SCIP')

    #Define sets and indices
    staffs = scheduling_data["staffs"]
    shifts = scheduling_data["shifts"]
    period = scheduling_data["periods"]
    current_week = current_week

    staffs_list = [staff["id"] for staff in staffs]
    slack = []
    shifts_list = [shift["id"] for shift in shifts]
    days = [day for day in period 
                 if day["week"] == current_week]
    days_list = [day["dayOfWeek"] 
                 for day in days]

    #Define parameters
    agency_list = ["agency_1", "agency_2", "agency_3"]
    week_start_idx = 0
    week_last_idx = 6

    #Define decision variables
    x = {(i,j,k): solver.IntVar(0.0, 1.0, f'x_{i}_{j}_{k}') 
                                 for i in staffs_list
                                 for j in shifts_list
                                 for k in days_list}
    
    s = {}
    
    actual_WH = {i: solver.IntVar(0.0, solver.infinity(), f'ActualWH_{i}') for i in staffs_list}

    #Define set of constraints
    #Each staff works exactly one shift per day (hard)
    for k in days_list:
        for i in staffs_list:
            solver.Add(solver.Sum(x[(i,j,k)] for j in shifts_list) == 1)

    #Each staff takes 1 DO per week (hard)
    for i in staffs_list:
            solver.Add(solver.Sum(x[(i,"DO",k)] for k in days_list) == 1)

    #Assign PH shift to staff whho needs it (hard)
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


    #Each staff must work exactly 44 hours per week (hard)
    for i in staffs_list:
         solver.Add(actual_WH[i] == 44)

    #Undesire afternoon shift after shift DO (soft)
    code = "DO-AM_shifts"
    s[code] = {}

    for i in staffs_list:
         for k in days_list:
              if k != week_last_idx:
                v = solver.IntVar(0, solver.infinity(), f'{code}')
                s[code][(f'staff_{i}',f'day_{k}')] = v
                solver.Add(x[(i,"DO",k)] 
                           + solver.Sum(x[(i,shift["id"],k+1)] 
                                        for shift in shifts if shift["shiftType"] == "afternoon")
                            <= 1 + v)
                slack.append(v)
    
    #Undesire afternoon shift after shift PH (soft)    
    code = "PH-AM_shifts"
    s[code] = {}

    for i in staffs_list:
         for k in days_list:
              if k != week_last_idx:
                v = solver.IntVar(0, solver.infinity(), f'{code}')
                s[code][(f'staff_{i}',f'day_{k}')] = v
                for shift in shifts:
                    if shift["shiftType"] == "afternoon":
                            solver.Add(x[(i,"PH",k)] + solver.Sum(x[(i,shift["id"],k+1)]
                                                         for shift in shifts if shift["shiftType"] == "afternoon") 
                                                         <= 1 + v)
                slack.append(v)

    #Undesire 3 consecutive afternoon shifts (soft)
    code = "3AM_shifts"
    s[code] = {}
    
    for i in staffs_list:
         for k in days_list:
              if k not in [week_start_idx, week_last_idx]:
                   v = solver.IntVar(0, solver.infinity(), f'{code}')
                   s[code][(f'staff_{i}',f'day_{k}')] = v

                   day_0 =  solver.Sum(x[(i,shift["id"],k-1)] 
                                for shift in shifts if shift["shiftType"] == "afternoon")   

                   day_1 =  solver.Sum(x[(i,shift["id"],k)] 
                                for shift in shifts if shift["shiftType"] == "afternoon")

                   day_2 = solver.Sum(x[(i,shift["id"],k+1)] 
                                for shift in shifts if shift["shiftType"] == "afternoon")   

                   solver.Add(day_0 + day_1 + day_2 <= 2 + v)
                   slack.append(v)
    
    #Morning shift coverage requirement (hard)
    for day in days:
         solver.Add(solver.Sum(x[(i,shift["id"],day["dayOfWeek"])] 
                        for i in staffs_list for shift in shifts if shift["shiftType"] == "morning")
                    == day["morningShiftCov"])     

    #Afternoon shift coverage requirement(hard)
    for day in days:
         solver.Add(solver.Sum(x[(i,shift["id"],day["dayOfWeek"])] 
                        for i in staffs_list for shift in shifts if shift["shiftType"] == "afternoon")
                    == day["afternoonShiftCov"])  

    #Morning Agency coverage requirement (soft)    
    code = "Morning_Agency_Cov"
    s[code] = {}
    for k in days_list:
        for a in agency_list:
             v = solver.IntVar(0, solver.infinity(), f'{code}')
             s[code][(f'day_{k}',a)] = v
             solver.Add(solver.Sum(x[(staff["id"],shift["id"],k)]
                            for staff in staffs if staff["agency"] == a
                            for shift in shifts if shift["shiftType"] == "morning")
                              >= 1 - v)
             slack.append(v)
                        

    #Afternoon Agency coverage requirement (hard)
    for k in days_list:
        for a in agency_list:
             solver.Add(solver.Sum(x[(staff["id"],shift["id"],k)]
                            for staff in staffs if staff["agency"] == a
                            for shift in shifts if shift["shiftType"] == "afternoon")
                              >= 1)
    
    #Define objective function
    solver.Minimize(solver.Sum(slack))

    status = solver.Solve()
    if status == pywraplp.Solver.OPTIMAL:
        print("Find optimal solution!")
        print(f'Objective value = {solver.Objective().Value()}')
        x_val = {
               key: var.solution_value()
               for key, var in x.items()
               }
        slack_val = {}

        for code in s:
             slack_val[code] = {}
             for key, var in s[code].items():
                  slack_val[code][key] = {
                       "value": var.solution_value(),
                       "name": var.name()
                    }
        return x_val, slack_val

    elif status == pywraplp.Solver.INFEASIBLE:
        print('Infeasible solution!')
        return None, None
        
    else:
         print("Solver can not find any optimal solution!")
         return None, None

def relaxed_solve(scheduling_data, current_week):
    solver = pywraplp.Solver.CreateSolver('SCIP')

    #Define sets and indices
    staffs = scheduling_data["staffs"]
    shifts = scheduling_data["shifts"]
    period = scheduling_data["periods"]
    current_week = current_week

    staffs_list = [staff["id"] for staff in staffs]
    slack = []
    shifts_list = [shift["id"] for shift in shifts]
    days = [day for day in period 
                 if day["week"] == current_week]
    days_list = [day["dayOfWeek"] 
                 for day in days]

    #Define parameters
    agency_list = ["agency_1", "agency_2", "agency_3"]
    week_start_idx = 0
    week_last_idx = 6

    #Define decision variables
    x = {(i,j,k): solver.IntVar(0.0, 1.0, f'x_{i}_{j}_{k}') 
                                 for i in staffs_list
                                 for j in shifts_list
                                 for k in days_list}
    
    s = {}
    
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
    code_1 = "Add_hours"
    s[code_1] = {}

    code_2 = "Minus_hours"
    s[code_2] = {} 
  
    for i in staffs_list:
         v_add = solver.IntVar(0.0, solver.infinity(), f'{code_1}')
         s[code_1][f'staff_{i}'] = v_add

         v_minus = solver.IntVar(0.0, solver.infinity(), f'{code_2}')
         s[code_2][f'staff_{i}'] = v_minus

         solver.Add(actual_WH[i] + v_add - v_minus == 44)
         slack.append(v_add)
         slack.append(v_minus)

    #Undesire afternoon shift after shift DO (soft)
    code = "DO-AM_shifts"
    s[code] = {}

    for i in staffs_list:
         for k in days_list:
              if k != week_last_idx:
                v = solver.IntVar(0, solver.infinity(), f'{code}')
                s[code][(f'staff_{i}',f'day_{k}')] = v
                solver.Add(x[(i,"DO",k)] 
                           + solver.Sum(x[(i,shift["id"],k+1)] 
                                        for shift in shifts if shift["shiftType"] == "afternoon")
                            <= 1 + v)
                slack.append(v)
    
    #Undesire afternoon shift after shift PH (soft)    
    code = "PH-AM_shifts"
    s[code] = {}

    for i in staffs_list:
         for k in days_list:
              if k != week_last_idx:
                v = solver.IntVar(0, solver.infinity(), f'{code}')
                s[code][(f'staff_{i}',f'day_{k}')] = v
                for shift in shifts:
                    if shift["shiftType"] == "afternoon":
                            solver.Add(x[(i,"PH",k)] + solver.Sum(x[(i,shift["id"],k+1)]
                                                         for shift in shifts if shift["shiftType"] == "afternoon") 
                                                         <= 1 + v)
                slack.append(v)

    #Undesire 3 consecutive afternoon shifts (soft)
    code = "3AM_shifts"
    s[code] = {}
    
    for i in staffs_list:
         for k in days_list:
              if k not in [week_start_idx, week_last_idx]:
                   v = solver.IntVar(0, solver.infinity(), f'{code}')
                   s[code][(f'staff_{i}',f'day_{k}')] = v

                   day_0 =  solver.Sum(x[(i,shift["id"],k-1)] 
                                for shift in shifts if shift["shiftType"] == "afternoon")   

                   day_1 =  solver.Sum(x[(i,shift["id"],k)] 
                                for shift in shifts if shift["shiftType"] == "afternoon")

                   day_2 = solver.Sum(x[(i,shift["id"],k+1)] 
                                for shift in shifts if shift["shiftType"] == "afternoon")   

                   solver.Add(day_0 + day_1 + day_2 <= 2 + v)
                   slack.append(v)
    
    #Morning shift coverage requirement (hard) => relaxed
    code_1 = "+AM_General_Cov"
    s[code_1] = {}

    code_2 = "-AM_General_Cov"
    s[code_2] = {}

    for day in days:
         v_add = solver.IntVar(0.0, solver.infinity(), f'{code_1}')
         s[code_1][f'day_{day["id"]}'] = v_add
         v_minus = solver.IntVar(0.0, solver.infinity(), f'{code_2}')
         s[code_2][f'day_{day["id"]}'] = v_minus

         solver.Add(solver.Sum(x[(i,shift["id"],day["dayOfWeek"])] 
                        for i in staffs_list for shift in shifts if shift["shiftType"] == "morning")
                    == day["morningShiftCov"] 
                         + v_add
                         - v_minus)     
         slack.append(v_add)
         slack.append(v_minus)

         
    #Afternoon shift coverage requirement(hard)
    code_1 = "+PM_General_Cov"
    s[code_1] = {}
    code_2 = "-PM_General_Cov"
    s[code_2] = {}
    for day in days:
         v_add = solver.IntVar(0.0, solver.infinity(), f'{"+PM_General_Cov"}')
         s[code_1][f'day_{day["id"]}'] = v_add
         v_minus = solver.IntVar(0.0, solver.infinity(), f'{"-PM_General_Cov"}')
         s[code_2][f'day_{day["id"]}'] = v_minus
         
         solver.Add(solver.Sum(x[(i,shift["id"],day["dayOfWeek"])] 
                        for i in staffs_list for shift in shifts if shift["shiftType"] == "afternoon")
                    == day["afternoonShiftCov"] 
                         + v_add
                         - v_minus)  
         slack.append(v_add)
         slack.append(v_minus)

    #Morning Agency coverage requirement (soft)    
    code = "Morning_Agency_Cov"
    s[code] = {}
    for k in days_list:
        for a in agency_list:
             v = solver.IntVar(0, solver.infinity(), f'{code}')
             s[code][(f'day_{k}',a)] = v
             solver.Add(solver.Sum(x[(staff["id"],shift["id"],k)]
                            for staff in staffs if staff["agency"] == a
                            for shift in shifts if shift["shiftType"] == "morning")
                              >= 1 - v)
             slack.append(v)
                        

    #Afternoon Agency coverage requirement (hard) => relaxed
    code = "Afternoon_Agency_Cov"
    s[code] = {}
    for k in days_list:
        for a in agency_list:
             v = solver.IntVar(0, solver.infinity(), f'{code}')
             s[code][(f'day_{k}',a)] = v
             solver.Add(solver.Sum(x[(staff["id"],shift["id"],k)]
                            for staff in staffs if staff["agency"] == a
                            for shift in shifts if shift["shiftType"] == "afternoon")
                              >= 1 - v)
             slack.append(v)
    
    #Define objective function
    solver.Minimize(solver.Sum(slack))

    status = solver.Solve()
    if status == pywraplp.Solver.OPTIMAL:
        print("Find optimal solution!")
        print(f'Objective value = {solver.Objective().Value()}')
        x_val = {
               key: var.solution_value()
               for key, var in x.items()
               }
        slack_val = {}

        for code in s:
             slack_val[code] = {}
             for key, var in s[code].items():
                  slack_val[code][key] = {
                       "value": var.solution_value(),
                       "name": var.name()
                    }
        return x_val, slack_val

    elif status == pywraplp.Solver.INFEASIBLE:
        print('Infeasible solution!')
        return None, None
        
    else:
         print("Solver can not find any optimal solution!")
         return None, None