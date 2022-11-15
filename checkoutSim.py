import simpy
import numpy as np
import matplotlib.pyplot as plt
 
# Constants for the simulation------------------------------------------------------------------------------------------
lambdaC = 1/3 #enhet min**-1
expectedFailureIntensity = 1/(60*4) #4 timer
meanRepairTime = 15 #min
avgServiceTime = 2 #min

SIM_TIME = 60*16 #enhet min, 16 timer

#Global variables for the simulation------------------------------------------------------------------------------------
checkoutSection = 0
downtime = 0
Qtime = []
customersAtCheckout = 0 #Fordi .users også regner med repairman, siden vi bruker request på denne for å markere at counter ikke tilgjenglig

headOfQ = {}
for noOFWorkingCounters in range(0, 5): #for å kunne analysere Qtime vs antall fungerende counters, se impact av failure på Qtime
    headOfQ[noOFWorkingCounters] = []


#Timers-----------------------------------------------------------------------------------------------------------------
def customerInterArrivalTime(lambdaC):
    return np.random.exponential(1/lambdaC) 

def timeBeforeFailure(expectedFailureIntensity):
    return np.random.exponential(1/expectedFailureIntensity) 

def serviceTime(avgValue):
    return np.random.exponential(avgValue)

def repairTime(meanRepairTime):
    return np.random.exponential(meanRepairTime)


#Entity-classes--------------------------------------------------------------------------------------------------
class InterruptGenerator():
    def __init__(self, env, first):
        global checkoutSection
        self.env = env

        if first:
            checkoutSection = CheckoutSection(env)
            first = False

        
    def generateInterrupts(self, env):
        global customersAtCheckout
        while True:
            yield env.timeout(timeBeforeFailure(expectedFailureIntensity))

            if checkoutSection.workingCounters >= 0 and customersAtCheckout < checkoutSection.workingCounters:
                checkoutSection.checkout_proc.interrupt() #Kan ikke sende interrupt om alle counters ute av funksjon eller opptatt

        


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
                if self.workingCounters == 1: #Vil si at den siste counteren feiler, må begynne å logge downtime
                    self.currentDowntime = env.now #start counting downtime
                repair = RepairCounter(env) #schedule repairCounter




class Customer():
    def __init__(self, env):
        self.env = env
        self.process = env.process(self.run(env))
    
    def run(self, env):
        global checkoutSection, headOfQ, customersAtCheckout

        with checkoutSection.counters.request() as reqCounter: 
            startQ = env.now
            yield reqCounter 

            customersAtCheckout+=1

            workingCounters = checkoutSection.workingCounters
            endQ = env.now - startQ

            Qtime.append(endQ)
            headOfQ[workingCounters].append(endQ) #! siden vi logger qtime mot fungerende counters når denne akkurat har fått counter, så vil aldri workingCounters være 0, siden en må være tilgjengelig før vi logger. Skal dette endres? 

            yield self.env.timeout(serviceTime(avgServiceTime))

            customersAtCheckout-=1




class RepairCounter(): 
    def __init__(self, env):
        self.env = env
        self.fix_proc = env.process(self.fix(env))

    def fix(self, env):
        global checkoutSection, downtime, meanRepairTime

        checkoutSection.workingCounters -= 1

        with checkoutSection.counters.request() as reqCounter: 
            yield reqCounter

            with checkoutSection.repairman.request() as reqRepair: 
                yield reqRepair
                yield self.env.timeout(repairTime(meanRepairTime))

        checkoutSection.workingCounters += 1
        if checkoutSection.workingCounters == 1: #Dvs denne reparasjonen fikk systemet opp å gå igjen
            downtime += env.now - checkoutSection.currentDowntime
            checkoutSection.currentDowntime = 0


    


#Running simulation-----------------------------------------------------------------------------
env = simpy.Environment()
i1 = InterruptGenerator(env, True) #En interrupt per counter
i2 = InterruptGenerator(env, False)
i3 = InterruptGenerator(env, False)
i4 = InterruptGenerator(env, False)

env.process(i1.generateInterrupts(env)) #Starter generator for hver av instansene av interruptGenerator
env.process(i2.generateInterrupts(env))
env.process(i3.generateInterrupts(env))
env.process(i4.generateInterrupts(env))

env.run(until=SIM_TIME)


#Calculating service availability and avgQtime---------------------------------------------------------------------
serviceAvailability = 1-(float(downtime)/SIM_TIME) #? spørsmål: Skal man kjøre denne flere ganger? Eller holder det med én?
avgQTime = sum(Qtime)/float(len(Qtime))

print("Asymptotic availability of checkout:                  ", format(serviceAvailability*100, ".8f"), "%")
print("Average waiting time for customers in checkout queue:   ", format(avgQTime, ".8f"), "minutes") 


#Plotting 
#TODO plot the waiting time as a function of number of failures from simulation and analytical models. Compare results and comment on them.
failuresAtHead = {}#lager en dictionary som passer til plotting
for keys in headOfQ.keys(): #keys her er fungerende counters, må ha 4-fungerende for feilet
    try:
        failuresAtHead[4-keys] = sum(headOfQ[keys])/float(len(headOfQ[keys]))
    except:
        failuresAtHead[4-keys] = 0

    print("failed:", 4-keys, "avg time", failuresAtHead[4-keys])


plt.plot(failuresAtHead.keys(), failuresAtHead.values(), 'r.') #number of failures = 4-workingcounters #!vurder å kjøre med boxplot for å få kjørt simuleringen flere ganger
#TODO legg inn analytical:

plt.xlabel("Number of failed counters")
plt.ylabel("Average Qtime for failures")
plt.show()