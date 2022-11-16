import simpy
import numpy as np
from math import factorial
import matplotlib.pyplot as plt
 
# Constants for the simulation------------------------------------------------------------------------------------------
lambdaC = 1/3 #enhet min**-1
expectedFailureIntensity = 1/(60*4) #4 timer
meanRepairTime = 15 #min
avgServiceTime = 2 #min

SIM_TIME = 60*16 #enhet min, 16 timer

#Global variables for the simulation------------------------------------------------------------------------------------
checkoutSection = 0 #for å ha en global variabel for denne
downtime = 0
Qtime = []
headOfQ = {}
customersAtCheckout = 0 #Fordi .users også regner med repairman, siden vi bruker request på denne for å markere at counter ikke tilgjenglig

def resetGlobals(): #For å kunne resette for hver kjøring
    global headOfQ, downtime, Qtime, customersAtCheckout, checkoutSection
    checkoutSection = 0
    downtime = 0
    Qtime = []
    headOfQ = {}
    customersAtCheckout = 0

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

        
    def generateInterrupts(self, env):
        global customersAtCheckout
        while True:
            yield env.timeout(timeBeforeFailure(expectedFailureIntensity))

            if checkoutSection.workingCounters >= 0 and customersAtCheckout < checkoutSection.workingCounters:
                checkoutSection.checkout_proc.interrupt() #Kan ikke sende interrupt om alle counters ute av funksjon eller opptatt

        


class CheckoutSection():
    def __init__(self, env):
        self.env = env
        self.counters = simpy.PriorityResource(env, capacity=4) #For å kunne fikse en interrupt før man tar neste kunde, dersom en interrupt skjer like før en kunde går til kassen
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

        with checkoutSection.counters.request(1) as reqCounter: #Lavere priority
            startQ = env.now
            yield reqCounter 

            customersAtCheckout+=1

            workingCounters = checkoutSection.workingCounters
            endQ = env.now - startQ

            Qtime.append(endQ) 
            headOfQ[workingCounters].append(endQ)

            yield self.env.timeout(serviceTime(avgServiceTime))

        customersAtCheckout-=1




class RepairCounter(): 
    def __init__(self, env):
        self.env = env
        self.fix_proc = env.process(self.fix(env))

    def fix(self, env):
        global checkoutSection, downtime, meanRepairTime

        checkoutSection.workingCounters -= 1

        with checkoutSection.counters.request(0) as reqCounter: 
            yield reqCounter

            with checkoutSection.repairman.request() as reqRepair: 
                yield reqRepair
                yield self.env.timeout(repairTime(meanRepairTime))

        checkoutSection.workingCounters += 1
        if checkoutSection.workingCounters == 1: #Dvs denne reparasjonen fikk systemet opp å gå igjen
            downtime += env.now - checkoutSection.currentDowntime
            checkoutSection.currentDowntime = 0


    
#Setup for values for plotting----------------------------------------------------------------------------------
failuresAtHead = {}#lager en dictionary som passer til plotting

for n in range(0, 4): #stopper på 4 fordi vi aldri logger med 4 failures
    failuresAtHead[n] = []

def updateFailuresAtHead(dictFromRun):
    global failuresAtHead
    for keys in dictFromRun.keys(): #keys her er fungerende counters, må ha 4-fungerende for feilet
        if keys != 0: #vil ikke ha med fra når ingen fungerer i plottet
            try:
                newAvgQ = sum(dictFromRun[keys])/float(len(dictFromRun[keys]))
                failuresAtHead[4-keys].append(newAvgQ)
            except:
                failuresAtHead[4-keys].append(0)


#Calculating service availability and avgQtime---------------------------------------------------------------------
def otherValues(): #! ta snitt av disse etter simulering kjørt, og print til å sette inn for oppgB3
    global downtime, Qtime
    serviceAvailability = 1-(float(downtime)/SIM_TIME) 
    avgQTime = sum(Qtime)/float(len(Qtime))

    print("Asymptotic availability of checkout:                  ", format(serviceAvailability*100, ".8f"), "%")
    print("Average waiting time for customers in checkout queue:   ", format(avgQTime, ".8f"), "minutes") 


#Running simulation-----------------------------------------------------------------------------
def runSim(env):
    global headOfQ
    resetGlobals()

    i1 = InterruptGenerator(env, True) #En interrupt per counter
    i2 = InterruptGenerator(env, False)
    i3 = InterruptGenerator(env, False)
    i4 = InterruptGenerator(env, False)

    env.process(i1.generateInterrupts(env)) #Starter generator for hver av instansene av interruptGenerator
    env.process(i2.generateInterrupts(env))
    env.process(i3.generateInterrupts(env))
    env.process(i4.generateInterrupts(env))

    env.run(until=SIM_TIME)

    updateFailuresAtHead(headOfQ)
    #otherValues() #?skal vi printe denne for hver gang? er vi interessert i denne? Blir spurt etter en oppgave, usikker

#Running simulation-----------------------------------------------------------------------------------------------
noOfSims = 30 
for simulation in range(noOfSims):
    env = simpy.Environment() #?Må denne tas for hver gang
    runSim(env)

# Analytical calculation------------------------------------------------------------------------------------
analytical = {}

def calculateAnalytical():
    global lambdaC, analytical
    mu = 1/2
    A=lambdaC/mu 
    n = 4 

    prob_waiting = []
    for i in range(n):
        prob_waiting.append(A**n/factorial(n)*n/(n-A)/((A**i)/factorial(i)+A**n/factorial(n)*n/(n-A)))

    failedCounters = 0
    expected_waiting = []
    for p_waiting in prob_waiting:
        failedCounters += 1
        analytical[failedCounters] = 1/(mu*(n-A))*p_waiting
        print(1/(mu*(n-A))*p_waiting)
    
calculateAnalytical()

#Plotting --------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots() 
ax.boxplot(failuresAtHead.values(), showfliers=False) #Vil ikke vise outliers, for å kunne se boxplottene ordentlig 
ax.set_xticklabels(failuresAtHead.keys())
plt.plot(analytical.keys(), analytical.values(), 'r.', markersize = 20)

plt.xlabel("Number of failed counters")
plt.ylabel("Average Qtime for failures")
plt.show()

#!oppdater modell når du får noe som kjører rett