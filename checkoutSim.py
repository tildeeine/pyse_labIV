import simpy
import numpy as np
from math import factorial
import matplotlib.pyplot as plt
 

 
# Constants for the simulation------------------------------------------------------------------------------------------
lambdaC = 1/3 #enhet min**-1
expectedFailureIntensity = 1/(60*4) #4 timer
meanRepairTime = 15 #min
avgServiceTime = 2 #min



#Global variables for the simulation------------------------------------------------------------------------------------
checkoutSection = 0 #for å ha en global variabel for denne
downtime = 0
Qtime = []
headOfQ = {}

def resetGlobals(): #For å kunne resette for hver kjøring
    global headOfQ, downtime, Qtime, checkoutSection
    checkoutSection = 0
    downtime = 0
    Qtime = []
    headOfQ = {}
    for noOFWorkingCounters in range(1, 5): #for å kunne analysere Qtime vs antall fungerende counters, se impact av failure på Qtime. Logger uansett aldri for 0
        headOfQ[noOFWorkingCounters] = []




#Values for keeping track of important results-------------------------------------------------------------------------
allServiceA = []
allQtimes = []
avgNoOfFailures = [0, 0, 0, 0]



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
        while True:
            yield env.timeout(timeBeforeFailure(expectedFailureIntensity))

            if checkoutSection.workingCounters > 0:
                checkoutSection.checkout_proc.interrupt() #Kan ikke sende interrupt om alle counters ute av funksjon. Hvis alle opptatt blir denne satt i Q ved at den venter på kasse-ressurs, men med prioritet. Gir failure til kasse like etter kunde ferdig. 

        

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
        global checkoutSection, headOfQ

        with checkoutSection.counters.request(1) as reqCounter: #Lavere priority
            startQ = env.now
            yield reqCounter 

            workingCounters = checkoutSection.workingCounters
            endQ = env.now - startQ

            Qtime.append(endQ) 
            headOfQ[workingCounters].append(endQ)

            yield self.env.timeout(serviceTime(avgServiceTime))



class RepairCounter(): 
    def __init__(self, env):
        self.env = env
        self.fix_proc = env.process(self.fix(env))

    def fix(self, env):
        global checkoutSection, downtime, meanRepairTime

        with checkoutSection.counters.request(0) as reqCounter: 
            yield reqCounter
            checkoutSection.workingCounters -= 1 #failure/interrupt registreres først når en kasse er tilgjenglig for å ha en failure

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



# Calculating service availability and avgQtime---------------------------------------------------------------------
def logValues(headOfQ): 
    global allServiceA, allQtimes
    allServiceA.append(1-(float(downtime)/SIM_TIME))
    allQtimes.append(sum(Qtime)/float(len(Qtime)))

    updateFailuresAtHead(headOfQ)
    logNoOfFailures(headOfQ)


def logNoOfFailures(dictionary):
    global avgNoOfFailures
    for keys in headOfQ.keys(): #1, 2, 3, 4
        avgNoOfFailures[4-keys] = (avgNoOfFailures[4-keys]+len(headOfQ[keys]))/float(2)
    


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

    logValues(headOfQ)



# Methods for analytical calculation------------------------------------------------------------------------------------
def prob(n):
    global lambdaC
    mu = 1/2
    A=lambdaC/mu 

    teller = (A**n/factorial(n))*(n/(n-A)) 
    nevner = 0
    for i in range(n):
        nevner += ((A**i/factorial(i)))
    nevner += teller

    return teller/float(nevner)

def time(n):
    global lambdaC
    mu = 1/2
    A=lambdaC/mu 
    return (1/(mu*(n-A)))

def calculateAnalytical():
    timeToWait = []
    totalWait = 0
    for a in range(0, 4): #antall ødelagte counters
        waitTime = time(4-a)*prob(4-a)
        timeToWait.append(waitTime)
        stateProb = [48/10675, 384/10675, 2048/10675, 8192/10675] #sannsynligheten for at 1 fungerer til at 4 fungerer
        stateProb.reverse() #vil ha sannsynligheten fra at 4 til at 1 fungerer
        totalWait += waitTime*stateProb[a] #ganger forventet ventetid med sannsynligheten for at n counters fungerer 
    return totalWait, timeToWait



#Running simulation-----------------------------------------------------------------------------------------------
SIM_TIME = 60*200##enhet min, 200 timer
noOfSims = 200

for simulation in range(noOfSims):
    env = simpy.Environment() 
    runSim(env)



# Printing values from simulations-----------------------------------------------------------------------
avgAvailability = sum(allServiceA)/float(len(allServiceA))
avgQtime = sum(allQtimes)/float(len(allQtimes))
print("Average asymptotic availability of checkout:           ", format(avgAvailability*100, ".8f"), "%")
print("Average waiting time for customers in checkout queue:   ", format(avgQtime, ".8f"), "minutes \n") 

totalWait, timeToWait = calculateAnalytical()
for times in range(len(timeToWait)):
    print("Expected waiting time with", times, "counter failures:", format(timeToWait[times], ".6f"), "minutes")
print("                  Total expected waiting time:", format(totalWait, ".6f"), "minutes")


print("\nThe average number of times we experienced x failures:")
for avgFailures in range(len(avgNoOfFailures)):
    print(avgFailures, "counter failures: ", format(avgNoOfFailures[avgFailures], ".2f"), "times")


#Plotting --------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots()
ax.boxplot(failuresAtHead.values(), showfliers=False, positions=list(failuresAtHead.keys())) #Vil ikke vise outliers, for å kunne se boxplottene ordentlig 
plt.plot(list(failuresAtHead.keys()), timeToWait, 'r.', markersize = 20)

plt.xlabel("Number of failed counters")
plt.ylabel("Average Qtime")
plt.show()