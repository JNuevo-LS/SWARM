

class Satellite:
   def __init__(self, name: str, id: str, elements: dict):
      self.name = name
      self.id = id
      self.elements = elements

   def __str__(self):
      return f"Satellite Name: {self.name} | ID: {self.id}"

f = open("data/LEO_TLE.txt", "r")
raw = f.read()
lines = raw.split("\n")
numSats = int(len(lines) / 3)
allSatObjects = {}

def parseObjData(metadata: str, orbitals: str):
   #metadata
   metadataSplit = metadata.split()
   metadata = {
      "NORAD": metadataSplit[1],
      "internationalDesignator": metadataSplit[2],
      "epochTime": metadataSplit[3],
      "firstTimeDerivative": metadataSplit[4],
      "secondTimeDerivative": metadataSplit[5],
      "drag": metadataSplit[6]
      }

   #orbital elements
   orbitalsSplit = orbitals.split()
   orbitals = {
      "inclination": orbitalsSplit[2],
      "RAAN": orbitalsSplit[3],
      "eccentricity": orbitalsSplit[4],
      "perigee": orbitalsSplit[5],
      "meanAnomaly": orbitalsSplit[6],
      "meanMotion": orbitalsSplit[7]
   }
   return (metadata, orbitals)

c = 0 #count var
for sat in range(numSats):
   name = " ".join(lines[c].split()[1:])
   metadata = lines[c+1]
   orbitals = lines[c+2]
   metadata, orbitals = parseObjData(metadata, orbitals)
   satObj = Satellite(name, metadata["NORAD"], orbitals)
   print(satObj)
   c += 3
   break
del c