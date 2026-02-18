import pandas as pd
import docplex.mp.model as cpx

SHIFT_TYPE_MORNING = 0
SHIFT_TYPE_AFTERNOON = 1
SHIFT_TYPE_OTHER = 2

DAY_TYPE_WE = 1
DAY_TYPE_PH = 2

GROUP_FIXED_SHIFT = 1
GROUP_PH_OFF = 2

SHIFT_PH = 6
SHIFT_DO = 5

STAFF_NUM = 9
DAY_NUM = 7
SHIFT_NUM = 7
WEEK_NUM = 7

PENALTY = 100

input_data_dir = "C:/Users/trinh/RustroverProjects/ANLS/monthly_data.xlsx"
monthly_data = pd.read_excel(input_data_dir, header=None, sheet_name="input_data")

week_1 = range(0, 7)
week_2 = range(7, 14)
week_3 = range(14, 21)
week_4 = range(21, 28)
current_week = week_4

Week = pd.DataFrame(columns = ["day", "day_type", "morning_cov", "afternoon_cov"])
Week["day"] = [0, 1, 2, 3, 4, 5, 6]
Week["day_type"] = [monthly_data.iloc[1, k] for k in current_week]
Week["morning_cov"] = [monthly_data.iloc[2, k] for k in current_week]
Week["afternoon_cov"] = [monthly_data.iloc[3, k] for k in current_week]

Staffs = pd.DataFrame(columns = ["id", "agency", "group"])
Staffs["id"] = [0, 1, 2, 3, 4, 5, 6, 7, 8]
Staffs["agency"] = [0, 0, 0, 0, 2, 2, 1, 1, 1]
Staffs["group"] = [1, 2, 2, 2, 0, 1, 0, 0, 2]

Dummy = pd.DataFrame(columns = ["id", "agency"])
Dummy["id"] = [0, 1, 2] 
Dummy["agency"] = [0, 1, 2]

Shifts = pd.DataFrame(columns = ["id", "shift_type", "duration"])
Shifts["id"] = [0, 1, 2, 3, 4, 5, 6]
Shifts["shift_type"] = [0, 0, 0, 1, 1, 2, 2]
Shifts["duration"] = [8, 7, 4, 8, 7, 0, 8]

#Define decision variables
opt_model = cpx.Model(name="Staff Scheduling Problem")
x = opt_model.binary_var_dict(
     keys = [(i, j, k)
          for i in Staffs["id"]
          for j in Shifts["id"]
          for k in Week["day"]],
     name = "x")

z = opt_model.integer_var_dict(
    keys = [(i_prime, j, k)
        for i_prime in Dummy["id"]
        for j in Shifts["id"]
        for k in Week["day"]],
    name = "z")

ActualWH = opt_model.integer_var_dict(
    keys = [i for i in Staffs["id"]],
    name = "ActualWH"
)

GapWH = opt_model.integer_var_dict(
     keys = [i for i in Staffs["id"]],
     name = "GapWH"
)

#Define objective function
Z_obj = (opt_model.sum(GapWH[i] for i in Staffs["id"])
        + opt_model.sum(z[i_prime,j,k]*PENALTY
                             for i_prime in Dummy["id"] 
                             for j in Shifts["id"] 
                             for k in Week["day"]))

#Define set of constraints
## Each staff works exactly one shift per day
opt_model.add_constraints(opt_model.sum(x[i,j,k] for j in Shifts["id"]) == 1
                          for i in Staffs["id"] for k in Week["day"])

## Each staff takes 1 DO per week
opt_model.add_constraints(opt_model.sum(x[i,SHIFT_DO,k] for k in Week["day"]) == 1
                          for i in Staffs["id"])

##Assign PH shift to staff whho needs it
opt_model.add_constraints(x[i, SHIFT_PH, k] == 1 
                          for i in Staffs["id"] if Staffs["group"][i] == GROUP_PH_OFF
                          for k in Week["day"] if Week["day_type"][k] == DAY_TYPE_PH)

opt_model.add_constraints(x[i, SHIFT_PH, k] == 0
                          for i in Staffs["id"] if Staffs["group"][i] != GROUP_PH_OFF
                          for k in Week["day"] if Week["day_type"][k] != DAY_TYPE_PH)

##Calculate actual working hours for each staff
opt_model.add_constraints(ActualWH[i] == opt_model.sum(x[i,j,k]*Shifts["duration"][j]
                                                       for j in Shifts["id"] for k in Week["day"])
                                                       for i in Staffs["id"])

##Calculate the gap working hours for each staff per week
opt_model.add_constraints(GapWH[i] >= 44 - ActualWH[i] for i in Staffs["id"])
opt_model.add_constraints(GapWH[i] >= ActualWH[i] - 44 for i in Staffs["id"])

##Undesire afternoon shift after a day off (shift DO or shift PH)
opt_model.add_constraints(x[i, SHIFT_DO, k] 
                          + opt_model.sum(x[i, j, k+1] for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_AFTERNOON) <= 1
                          for i in Staffs["id"]
                          for k in Week["day"] if k != WEEK_NUM - 1)

opt_model.add_constraints(x[i, SHIFT_PH, k] 
                          + opt_model.sum(x[i, j, k+1] for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_AFTERNOON) <= 1 
                          for i in Staffs["id"] if Staffs["group"][i] == GROUP_PH_OFF 
                          for k in Week["day"] if Week["day_type"][k] == 2 and k != WEEK_NUM - 1)

##Undesire 3 consecutive afternoon shifts (new constrint)
opt_model.add_constraints(opt_model.sum(x[i,j,k-1] for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_AFTERNOON)
                          + opt_model.sum(x[i,j,k] for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_AFTERNOON)
                          + opt_model.sum(x[i,j,k+1]for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_AFTERNOON)
                           <= 2 for i in Staffs["id"] for k in Week["day"] if k != 0 and k != WEEK_NUM - 1)
                                                                                  
##Undesire mix AM-PM shift for fixed shift group
##TBD

##Morning shift coverage requirement
opt_model.add_constraints(opt_model.sum(x[i,j,k] for i in Staffs["id"]
                                       for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_MORNING)
                        + opt_model.sum(z[i_prime,j,k] for i_prime in Dummy["id"]
                                        for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_MORNING)
                                       >= Week["morning_cov"][k] for k in Week["day"])

##Afternoon shift coverage requirement
opt_model.add_constraints(opt_model.sum(x[i,j,k] for i in Staffs["id"]
                                       for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_AFTERNOON)
                        + opt_model.sum(z[i_prime,j,k] for i_prime in Dummy["id"]
                                        for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_AFTERNOON)
                                       >= Week["afternoon_cov"][k] for k in Week["day"])


##Morning Agency coverage requirement
for a in Staffs["agency"].unique():
    opt_model.add_constraints(opt_model.sum(x[i,j,k] for i in Staffs["id"] if Staffs["agency"][i] == a
                                           for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_MORNING)
                            + opt_model.sum(z[i_prime, j, k] for i_prime in Dummy["id"] if Dummy["agency"][i_prime] == a
                                            for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_MORNING)               
                                           >= 1
                                           for k in Week["day"])
    
##Afternoon Agency coverage requirement
for a in Staffs["agency"].unique():
    opt_model.add_constraints(opt_model.sum(x[i,j,k] for i in Staffs["id"] if Staffs["agency"][i] == a
                                           for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_AFTERNOON)
                            + opt_model.sum(z[i_prime, j, k] for i_prime in Dummy["id"] if Dummy["agency"][i_prime] == a
                                            for j in Shifts["id"] if Shifts["shift_type"][j] == SHIFT_TYPE_AFTERNOON)               
                                           >= 1 for k in Week["day"])

#Solve the model
opt_model.minimize(Z_obj)
solution = opt_model.solve(log_output=True)
opt_model.set_time_limit(60)
solving_time = opt_model.solve_details.time
print(opt_model.get_solve_details())

#Get the solution
opt_x = {(i, j, k): x[i, j, k].solution_value
          for i in Staffs["id"]
          for j in Shifts["id"]
          for k in Week["day"]
         if x[(i, j, k)].solution_value >= 0.5}


opt_z = {(i_prime, j, k): z[i_prime, j, k].solution_value
          for i_prime in Dummy["id"]
          for j in Shifts["id"]
          for k in Week["day"]
         if z[(i_prime, j, k)].solution_value >= 0.5}

opt_actual = {i: ActualWH[i].solution_value
              for i in Staffs["id"]
              if ActualWH[i].solution_value >= 0.5}


#Print the results
solution = opt_model.solve(clean_before_solve = True, log_output = True) #Adjust log_out = False to hide solving infos

print("Solver: CPLEX")
print("Week 4")
if solution is not None:
    print("Objective value:", solution.get_objective_value())
    #print("Solving time= ", solving_time)
else:
    print("No solution found. Check memory or infeasibility.")

#Staff schedule results
schedule_res = [[] for _ in range(STAFF_NUM)]
for (i, j, k), val in opt_x.items():
    schedule_res[i].append((k, j))

for i in range(STAFF_NUM):
    schedule_res[i].sort(key=lambda x: x[0])
    schedule_res[i] = [j for (k,j) in schedule_res[i]]

print("---Staffs Schedule---")
for i, row in enumerate(schedule_res):
    print(f"Staff {i+1}: {row}")

#Dummy assignment results
row = []
for (i, j, k), val in opt_z.items():
    row.append({
        "Shift": j,
        "Day": k,
        "Dummy": val
        })
dummy_assignment = pd.DataFrame(row)    
print("---Dummy assignment---")
print(dummy_assignment)


#Actual working hour of staffs
actual_list = []

for i, val in opt_actual.items():
    actual_list.append(val)

print("---Actual WH---")
for i in range(STAFF_NUM):
    print(f"Staff {i+1}: {actual_list[i]}")
