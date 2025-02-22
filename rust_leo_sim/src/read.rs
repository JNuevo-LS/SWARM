use std::fs::File;
use std::io::{BufRead, BufReader, Lines};
use std::collections::HashMap;
use crate::satellite::{OrbitalInstance, SatelliteRecord};
use anyhow::{bail, Result};

pub fn read_txt(file_path: &str) -> Result<HashMap<String, SatelliteRecord>>{
    let file: File = File::open(file_path)?;
    let reader: BufReader<File> = BufReader::new(file);
    
    let mut lines: Lines<BufReader<File>> = reader.lines();
    let mut satellites: HashMap<String, SatelliteRecord> = HashMap::new();

    while let Some(line1_result) = lines.next() {
        let line1: String = line1_result?;
        if let Some(line2_result) = lines.next() {
            let line2: String = line2_result?;
            let instance: OrbitalInstance = process_tle_instance(&line1, &line2)?;
            if is_leo(&instance)? {
                let id: String = line1[9..17].trim().to_string();
                if satellites.contains_key(&id) {
                    satellites.get_mut(&id).unwrap().orbital_records.push(instance); //pushes the satellite's instance to the SatelliteRecords struct
                } else { //if satellite hasn't been recorded yet in HashMap, creates a record of it and initializes a new vector of orbital instances
                    let mut orbital_records: Vec<OrbitalInstance> = Vec::new();
                    orbital_records.push(instance);
    
                    let satellite_record: SatelliteRecord = SatelliteRecord {
                        catalog_number: line1[2..7].trim().parse::<u32>()?,
                        international_designator: line1[9..17].to_string(),
                        orbital_records: orbital_records
                    };
                    satellites.insert(id, satellite_record);
                }
            } else {
                continue;
            }
        } else {
            println!("Last line (no pair): {}", line1);
        }
    }
    Ok(satellites)
}

fn process_tle_instance(line1:&String, line2:&String) -> Result<OrbitalInstance> {
    let orbitals = OrbitalInstance {
        epoch_year: line1[18..20].trim().parse::<u16>()? + 2000,
        epoch_day: line1[20..32].trim().parse::<f64>()?,
        first_time_derivative: line1[33..43].trim().parse::<f64>()?,
        second_time_derivative: convert_scientific(&line1[44..53])?,
        drag: convert_scientific(&line1[53..62])?,
        inclination: line2[8..16].trim().parse::<f64>()?,
        raan: line2[17..25].trim().parse::<f64>()?,
        eccentricity: format!("0.{}", line2[26..33].trim()).parse::<f64>()?,
        perigee: line2[34..42].trim().parse::<f64>()?,
        mean_anomaly: line2[43..51].trim().parse::<f64>()?,
        mean_motion: line2[52..63].trim().parse::<f64>()?,
        revolution_number: line2[63..68].trim().parse::<u32>()?
    };
    Ok(orbitals)
}

fn is_leo(instance:&OrbitalInstance) -> Result<bool> {
    if instance.eccentricity < 0.25 && instance.mean_motion > 11.25 {
        Ok(true)
    } else {
        Ok(false)
    }
}

fn add_up(chars:&Vec<char> , start_i: usize, end_shift: usize) -> Result<u64> { //TODO: FIX THIS
    if chars.len() < start_i + end_shift {
        bail!("String too short in add_up");
    }
    let mut n: u64 = 0;
    for i in start_i..(chars.len() - end_shift) {
        n *= 10;
        if chars[i].is_digit(10) {
            //convert the char to its numeric value value
            if let Some(digit) = chars[i].to_digit(10) {
                n += digit as u64;
            }
        }
    }
    Ok(n)
}

fn convert_scientific(value: &str) -> Result<f64> {
    let value = value.trim();
    if value.is_empty() {
        bail!("Empty input");
    }

    let chars: Vec<char> = value.chars().collect();
    if chars.len() < 3 {
        bail!("Input too short");
    }

    let mut negative = false;
    let numeric_value: u64;

    if chars[0] == '-' {
        negative = true;
        if chars[chars.len() - 3] == 'e' { // deals with different formats
            numeric_value = add_up(&chars, 1, 3)?;
        } else {
            numeric_value = add_up(&chars, 1, 2)?;
        }
    } else {
        if chars[chars.len() - 3] == 'e' {
            numeric_value = add_up(&chars, 0, 3)?;
        } else {
            numeric_value = add_up(&chars, 0, 2)?;
        }
    }

    let exponent: String = chars[chars.len()-2..].iter().collect();

    let result_str = if negative {
        format!("-0.{}e{}", numeric_value, exponent)
    } else {
        format!("0.{}e{}", numeric_value, exponent)
    };

    Ok(result_str.parse::<f64>()?)

}