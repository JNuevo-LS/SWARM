use std::{fs::{File, read_to_string}, io::{BufRead, BufReader, Lines}, collections::HashMap, thread, time::Instant};
use crate::satellite::{OrbitalInstance, SatelliteRecord};
use anyhow::{bail, Context, Ok, Result};
use crate::merge::merge_satellite_hashmaps;
use std::fs;
use std::io;
use std::path::Path;
use satkit::tle::TLE;
// use satkit::sgp4;

pub(crate) fn read_txt_files(year_start:u8, year_end:u8) -> HashMap<String, SatelliteRecord> {
    let mut handles = vec![];

    for i in year_start..year_end {
        let handle = thread::Builder::new()
        .name(String::from(format!("Data Reader for i = {i}")))
        .spawn(move || -> Result<HashMap<String, SatelliteRecord>> { //creates a thread for each .txt file
            let filepath: String = format!("./data/tle20{:02}.txt", i);
            // let _ = clean_file(&filepath);
            let time: Instant = Instant::now();
            println!("[{i}] Now reading");
            let satellites: HashMap<String, SatelliteRecord> = read_txt(&filepath).expect("Failed to read txt file");
            println!("[{i}] Reading is done");
            println!("[{i}] Read in {} seconds", time.elapsed().as_secs_f64());
            println!("[{i}] Size of satellites = {}", satellites.len());
            Ok(satellites)
        }).expect("Failed to spawn thread");
        handles.push(handle);
    }

    //combine all satellite hashmaps from each year into one
    let mut satellites: HashMap<String, SatelliteRecord> = HashMap::new();
    for handle in handles {
        let thread_maps = handle.join().unwrap().unwrap();
        let _ = merge_satellite_hashmaps(&mut satellites, thread_maps); //merges in place doesn't return anything
        println!("Merged with a thread, new size: {}", satellites.len())
    }
    
    return satellites;
}

fn read_txt(filepath: &str) -> Result<HashMap<String, SatelliteRecord>>{
    let file: File = File::open(filepath)?;
    let reader: BufReader<File> = BufReader::new(file);
    
    let mut lines: Lines<BufReader<File>> = reader.lines();
    let mut satellites: HashMap<String, SatelliteRecord> = HashMap::new();

    while let Some(line1_result) = lines.next() { //reads every 2 lines together
        let line1: String = line1_result?.trim_end_matches('\\').to_string();

        if let Some(line2_result) = lines.next() {
            let line2: String = line2_result?.trim_end_matches('\\').to_string();

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
            bail!("Last line (no pair): {}", line1);
        }
    }
    Ok(satellites)
}

pub(crate) fn read_txt_for_satkit(filepath: &str) -> Result<HashMap<String, Vec<TLE>>> {
    let file_as_string = read_to_string(filepath)?.to_string();
    
    let mut lines = file_as_string.lines();
    let mut lines_split: Vec<Vec<String>> = Vec::new();

    println!("Reading lines");
    while let Some(line1) = lines.next() {
        if let Some(line2) = lines.next() {
            lines_split.push(vec![line1.to_string(), line2.to_string()]);
        }
    }
    println!("Creating TLE structs out of lines");
    let mut satellites: HashMap<String, Vec<TLE>> = HashMap::new();
    for satellite in lines_split {
        let tle: TLE = TLE::load_2line(&satellite[0], &satellite[1]).unwrap();

        if is_tle_leo(&tle)? {
            if satellites.contains_key(&tle.intl_desig) {
                satellites.get_mut(&tle.intl_desig).unwrap().push(tle);
            } else {
                let mut tle_vec: Vec<TLE> = Vec::new();
                let id = tle.intl_desig.clone();
                tle_vec.push(tle);
                satellites.insert(id, tle_vec);
            }
        }
    }
    println!("Finished size of HashMap: {}", satellites.len());
    Ok(satellites)
}

fn clean_file<P: AsRef<Path>>(path: P) -> io::Result<()> { //sometimes needed if a file is misformatted
    let content = fs::read_to_string(&path)?;

    let filtered_lines: Vec<&str> = content
        .lines()
        .filter(|line| {
            let trimmed = line.trim();
            !trimmed.is_empty() && trimmed != "\\"
        })
        .collect();
    let new_content = filtered_lines.join("\n");
    fs::write(path, new_content)
}

fn process_tle_instance(line1: &String, line2: &String) -> Result<OrbitalInstance> {

    if line1.chars().nth(0) != Some('1') {
        bail!("Line 1 input invalid: {}", line1)
    }  
    if line2.chars().nth(0) != Some('2') {
        bail!("Line 2 input invalid: {}", line1)
    }  

    // Process line1 fields
    let epoch_year_str = line1.get(18..20)
        .with_context(|| format!("line1 does not contain epoch_year field (indices 18..20) Line 1: {}, Line 2: {}", line1, line2))?;
    let epoch_year: u16 = epoch_year_str.trim().parse::<u16>()
        .with_context(|| format!("Error parsing epoch_year: '{}' Line 1: {}, Line 2: {}", epoch_year_str, line1, line2))? + 2000;

    let epoch_day_str = line1.get(20..32)
        .with_context(|| format!("line1 does not contain epoch_day field (indices 20..32) Line 1: {}, Line 2: {}", line1, line2))?;
    let epoch_day: f64 = epoch_day_str.trim().parse()
        .with_context(|| format!("Error parsing epoch_day: '{}' Line 1: {}, Line 2: {}", epoch_day_str, line1, line2))?;

    let first_time_derivative_str = line1.get(33..43)
        .with_context(|| format!("line1 does not contain first_time_derivative field (indices 33..43) Line 1: {}, Line 2: {}", line1, line2))?;
    let first_time_derivative: f64 = first_time_derivative_str.trim().parse()
        .with_context(|| format!("Error parsing first_time_derivative: '{}' Line 1: {}, Line 2: {}", first_time_derivative_str, line1, line2))?;

    let second_time_derivative_str = line1.get(44..53)
        .with_context(|| format!("line1 does not contain second_time_derivative field (indices 44..53) Line 1: {}, Line 2: {}", line1, line2))?;
    let second_time_derivative: f64 = convert_scientific(second_time_derivative_str)
        .with_context(|| format!("Error parsing second_time_derivative: '{}' Line 1: {}, Line 2: {}", second_time_derivative_str, line1, line2))?;

    let drag_str = line1.get(53..62)
        .with_context(|| format!("line1 does not contain drag field (indices 53..62) Line 1: {}, Line 2: {}", line1, line2))?;
    let drag: f64 = convert_scientific(drag_str)
        .with_context(|| format!("Error parsing drag: '{}' Line 1: {}, Line 2: {}", drag_str, line1, line2))?;

    // Process line2 fields
    let inclination_str = line2.get(8..16)
        .with_context(|| format!("line2 does not contain inclination field (indices 8..16) Line 1: {}, Line 2: {}", line1, line2))?;
    let inclination: f64 = inclination_str.trim().parse()
        .with_context(|| format!("Error parsing inclination: '{}' Line 1: {}, Line 2: {}", inclination_str, line1, line2))?;

    let raan_str = line2.get(17..25)
        .with_context(|| "line2 does not contain raan field (indices 17..25)")?;
    let raan: f64 = raan_str.trim().parse()
        .with_context(|| format!("Error parsing raan: '{}' Line 1: {}, Line 2: {}", raan_str, line1, line2))?;

    let eccentricity_str = line2.get(26..33)
        .with_context(|| "line2 does not contain eccentricity field (indices 26..33)")?;
    let eccentricity: f64 = format!("0.{}", eccentricity_str.trim()).parse()
        .with_context(|| format!("Error parsing eccentricity: '{}' Line 1: {}, Line 2: {}", eccentricity_str, line1, line2))?;

    let perigee_str = line2.get(34..42)
        .with_context(|| "line2 does not contain perigee field (indices 34..42)")?;
    let perigee: f64 = perigee_str.trim().parse()
        .with_context(|| format!("Error parsing perigee: '{}' Line 1: {}, Line 2: {}", perigee_str, line1, line2))?;

    let mean_anomaly_str = line2.get(43..51)
        .with_context(|| "line2 does not contain mean_anomaly field (indices 43..51)")?;
    let mean_anomaly: f64 = mean_anomaly_str.trim().parse()
        .with_context(|| format!("Error parsing mean_anomaly: '{}' Line 1: {}, Line 2: {}", mean_anomaly_str, line1, line2))?;

    let mean_motion_str = line2.get(52..63)
        .with_context(|| "line2 does not contain mean_motion field (indices 52..63)")?;
    let mean_motion: f64 = mean_motion_str.trim().parse()
        .with_context(|| format!("Error parsing mean_motion: '{}' Line 1: {}, Line 2: {}", mean_motion_str, line1, line2))?;

    let orbitals = OrbitalInstance {
        epoch_year,
        epoch_day,
        first_time_derivative,
        second_time_derivative,
        drag,
        inclination,
        raan,
        eccentricity,
        perigee,
        mean_anomaly,
        mean_motion,
    };

    Ok(orbitals)
}

fn is_tle_leo(instance:&TLE) -> Result<bool> {
    if instance.eccen < 0.25 && instance.mean_motion > 11.25 {
        Ok(true)
    } else {
        Ok(false)
    }
}

fn is_leo(instance:&OrbitalInstance) -> Result<bool> { //checks if the satellite meets the criteria of low earth satellite status
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