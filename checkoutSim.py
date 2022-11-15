import simpy
import numpy as np

# Konstanter for simulering
lambdaC = 1/3 #enhet min**-1
#lambdaT = 2 #enhet min**-1
uPerSection = [60, 36, 42, 42, 30, 60, 90]
SIM_TIME = 60*16 #enhet min, 16 timer
lambdaF = 1/(60*4) #4 timer
meanRepairTime = 15 #15 min
checkoutSection = 0
avgServiceTime = 2 #min
headOfQ = {}
headOfQ["Working Counters"] = []
headOfQ["QTime"] = []
downtime = 0
Qtime = []

def customerInterArrivalTime(lambdaC):
    return np.random.exponential(1/lambdaC) 

def timeBeforeFailure(lambdaF):
    return np.random.exponential(1/lambdaF) 

def serviceTime(avgValue):
    return np.random.exponential(avgValue)

def repairTime(meanRepairTime):
    return np.random.exponential(meanRepairTime)

def interruptGenerator(env): #Vil kjøre fire av disse samtidig. Vil sørge for at kun kommer når vi er i idle state 
    global checkoutSection
    checkoutSection = CheckoutSection(env)

    while True:
        yield env.timeout(timeBeforeFailure(lambdaF))
        checkoutSection.checkout_proc.interrupt() 


class CheckoutSection():
    def __init__(self, env):
        self.env = env
        self.counters = simpy.Resource(env, capacity=4) 
        self.repairman = simpy.Resource(env, capacity=1)
        self.workingCounters = 4
        self.currentDowntime = 0
        self.checkout_proc = env.process(self.run(env))


    def run(self, env):
        global lambdaC
        while True:
            try:
                yield self.env.timeout(customerInterArrivalTime(lambdaC))
                customer = Customer(env) #schedule Customer-process 

            except simpy.Interrupt:
                if self.workingCounters == 1: #Vil si at denne siste feiler 
                    self.currentDowntime = env.now #start counting downtime
                repair = RepairHandler(env) #schedule repairHandler


class RepairHandler(): 
    def __init__(self, env):
        self.env = env
        self.fix_proc = env.process(self.fix(env))

    def fix(self, env):
        global checkoutSection, downtime, meanRepairTime
        checkoutSection.workingCounters -= 1

        with checkoutSection.counters.request() as reqCounter: #!Tid for repair
            startF = env.now
            yield reqCounter
            with checkoutSection.repairman.request() as reqRepair: 
                yield reqRepair
                yield self.env.timeout(repairTime(meanRepairTime))

        checkoutSection.workingCounters += 1
        if checkoutSection.workingCounters == 1: #Dvs denne reparasjonen fikk systemet opp å gå igjen
            downtime += env.now - checkoutSection.currentDowntime
            checkoutSection.currentDowntime = 0

    
class Customer():
    def __init__(self, env):
        self.env = env
        self.process = env.process(self.run(env))
    
    def run(self, env):
        global checkoutSection, headOfQ

        with checkoutSection.counters.request() as reqCounter: 
            startQ = env.now
            yield reqCounter 
            endQ = env.now - startQ
            Qtime.append(endQ)
            headOfQ["Working Counters"].append(checkoutSection.workingCounters)
            headOfQ["QTime"].append(endQ)
            yield self.env.timeout(serviceTime(avgServiceTime))



env = simpy.Environment()
env.process(interruptGenerator(env))
env.run(until=SIM_TIME)


serviceAvailability = round(1-(float(downtime)/SIM_TIME), 8)
avgQTime = round(sum(Qtime)/float(len(Qtime)), 8)
print("Service Availability:", serviceAvailability)
print("avg Qtime:", avgQTime)

#TODO fiks så flere interrupts
#! Mangler å finne service availability og queue waiting time
# alle counters ikke-fungerende for å begynne å telle - alle checkouts opptatt, eller alle 