use std::collections::HashMap;
use crate::satellite::SatelliteRecord;
use anyhow::Result;
 
//this inserts all of the data from the "lost" hashmap and extends the orbital_records vec of existing satellites in "kept" with the entries in "lost"
pub fn merge_satellite_hashmaps(kept:&mut HashMap<String, SatelliteRecord>, lost:HashMap<String, SatelliteRecord>) -> Result<()> { 
    for (id, satellite) in lost {
        if let Some(kept_record) = kept.get_mut(&id) {
            kept_record.orbital_records.extend(satellite.orbital_records);
        } else {
            kept.insert(id, satellite);
        }
    }
    Ok(())
}                                                                                                                          