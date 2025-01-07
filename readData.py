

class Satellite:
   def __init__(self, name: str, metadata: dict, orbitals: dict):
      self.name = name
      self.id = metadata["NORAD"]
      self.metadata = metadata
      self.orbitals = orbitals

   def __str__(self):
      return f"Satellite Name: {self.name} | ID: {self.id}"
   
   def __getitem__(self, key):
      if key == "metadata":
         return self.metadata
      elif key == "orbitals":
         return self.orbitals
      elif key == "name":
         return self.name
      elif key == "id":
         return self.id
      else:
         raise KeyError(f"{key} not found in Satellite object.")
      
   def formatCSV(self):
      csv = ""
      for value in (*self.metadata.values(), *self.orbitals.values()):
         csv += "," + value
      return csv

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

def createSatObj(name, tle1, tle2):
   metadata, orbitals = parseObjData(tle1, tle2)
   sat = Satellite(name, metadata["NORAD"], metadata, orbitals)
   return sat

c = 0 #count var
for sat in range(numSats):
   name = " ".join(lines[c].split()[1:])
   metadata = lines[c+1]
   orbitals = lines[c+2]
   metadata, orbitals = parseObjData(metadata, orbitals)
   satObj = Satellite(name, metadata, orbitals)
   print(satObj)
   c += 3
   break
del c