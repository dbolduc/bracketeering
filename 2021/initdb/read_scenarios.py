def summarize(scenarios, givens={}):
    ret = {}
    for s in scenarios:
        # filter scenarios that dont match
        for key in givens:
            if s[key] != givens[key]:
                break
        else:
            # store name
            if s[9] not in ret:
                ret[s[9]] = [0, 0]
            if s[12] not in ret:
                ret[s[12]] = [0, 0]
    
            # add the probability
            ret[s[9]][0]+= s[7]
            ret[s[12]][1] += s[7]
    return ret

def print_summary(summary):
    prob = 0
    names = []
    for name in summary:
        names.append(name)
        prob += summary[name][0]
    names.sort()
    for name in names:
        if prob != 0:
            sum2 = "%.2f" % (summary[name][0]/prob*100)
            best = "%.2f" % (summary[name][1]/prob*100)
            print(name, "- Sum2:", sum2, "- Best:", best)


lines = open('scenarios.csv').read().split('\n')

scenarios = []
for line in lines[1:]:
    if line:
        scenario = line.split(',')[:-1]
        scenario[7] = float(scenario[7])
        scenarios.append(scenario)



fixed = {}
fixed[0] = "Houston"
fixed[1] = "Baylor"
fixed[3] = "Gonzaga"

print("\nPREGAME:")
print_summary(summarize(scenarios, fixed))

print("\nIF MICHIGAN")
fixed[2] = "Michigan"
print_summary(summarize(scenarios, fixed))
print("\nIF UCLA")
fixed[2] = "UCLA"
print_summary(summarize(scenarios, fixed))

