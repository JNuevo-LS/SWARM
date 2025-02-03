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
      csv = f'"{self.name}"'
      for value in (*self.metadata.values(), *self.orbitals.values()):
         csv += "," + str(value)
      return csv
   
def convert_scientific(value):
    value = value.strip() 
    try:
      if value in ["+00000+0", "00000+0", "-00000+0", "00000-0", "+00000-0", "-00000-0", "0"]:
         return 0.0  #convert to actual zero
      if re.match(r"^[+-]?\d+([+-]\d+)?$", value):  #matches '49332-4', '+12345+3'
         return float(value[:-2] + "e" + value[-2:])
      return float(value)
    except Exception as e:
      logging.error(f"Unexpected scientific notation format: '{value}'")
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
         "firstTimeDerivative": convert_scientific(metadata[33:44]),
         "secondTimeDerivative": convert_scientific(metadata[44:52]),
         "drag": convert_scientific(metadata[54:62])
         }

      #orbital elements
      orbitals = {
         "inclination": float(orbitals[8:16]),
         "RAAN": float(orbitals[17:25]),
         "eccentricity": f"0.{orbitals[26:33]}",
         "perigee": float(orbitals[34:42]),
         "meanAnomaly": float(orbitals[43:51]),
         "meanMotion": convert_scientific(orbitals[52:63]),
      }
      return (metadata, orbitals)
   except Exception as e:
      logging.critical(f"Failed to write to CSV: {e}")
      raise RuntimeError(f"Failed to Write: {e}")


def createSatObj(name, tle1, tle2):
   metadata, orbitals = parseObjData(tle1, tle2)
   sat = Satellite(name, metadata, orbitals)
   return sat
