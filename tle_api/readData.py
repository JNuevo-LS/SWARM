import logging
import re
class Satellite:
   def __init__(self, name: str, metadata: dict, orbitals: dict):
      self.name = name
      self.id = metadata["satelliteCatalogNumber"]
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
      csv = f'{self.name}'
      for value in (*self.metadata.values(), *self.orbitals.values()):
         csv += "," + str(value)
      return csv
   
def convert_scientific(value:str) -> float:
    def addUp(string:str, start_i:int ,end_shift:int):
        i = start_i
        n = 0
        while i < len(string) - end_shift:
            n *= 10
            if string[i].isnumeric(): n += int(string[i])
            i+=1
        return n

    try:
        value = value.strip()
        numeric_value = 0
        negative = False
        if value[0] == '-':
            if value[-3] == 'e':
                numeric_value = addUp(value, 1, 3)
            else:
                numeric_value = addUp(value, 1, 2)
        else:
            if value[-3] == 'e':
                numeric_value = addUp(value, 0, 3)
            else:
                numeric_value = addUp(value, 0, 2)
    
        if negative: 
            return float(f"-0.{numeric_value}e{value[-2:]}")
        else:
            return float(f"0.{numeric_value}e{value[-2:]}")

    except Exception as e:
        raise ValueError

def parseObjData(metadata: str, orbitals: str):
   try:
      #metadata
      metadata = {
         "satelliteCatalogNumber":  metadata[2:7],
         "securityClass": metadata[7],
         "internationalDesignator": metadata[9:17].strip(),
         "year": int(metadata[18:20].strip()),
         "day": float(metadata[20:33]),
         "firstTimeDerivative": float(metadata[33:44]),
         "secondTimeDerivative": convert_scientific(metadata[44:52]),
         "drag": convert_scientific(metadata[54:62]),
         }

      #orbital elements
      orbitals = {
         "inclination": float(orbitals[8:16]),
         "RAAN": float(orbitals[17:25]),
         "eccentricity": f"0.{orbitals[26:33]}",
         "perigee": float(orbitals[34:42]),
         "meanAnomaly": float(orbitals[43:51]),
         "meanMotion": float(orbitals[52:63]),
         "revolutionNumber": int(orbitals[63:68])
      }
      return (metadata, orbitals)
   except Exception as e:
      logging.critical(f"Failed to write to CSV: {e}")
      raise RuntimeError(f"Failed to Write: {e}")


def createSatObj(name, tle1, tle2):
   metadata, orbitals = parseObjData(tle1, tle2)
   sat = Satellite(name, metadata, orbitals)
   return sat
