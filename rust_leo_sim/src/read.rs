use std::{fs::read_to_string, collections::HashMap, thread, time::Instant};
use crate::satellite::{OrbitalInstance, SatelliteRecord};
use anyhow::{bail, Ok, Result};
use crate::merge::merge_satellite_hashmaps;
use std::fs;
use std::io;
use std::path::Path;
use satkit::tle::TLE;
use sgp4::chrono::{TimeZone, Utc, Datelike, Timelike};

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

fn read_txt(filepath: &str) -> Result<HashMap<String, SatelliteRecord>> {
    let file_contents = read_to_string(filepath)?;
    let lines: Vec<&str> = file_contents.lines().collect();
    let mut satellites: HashMap<String, SatelliteRecord> = HashMap::new();

    for chunk in lines.chunks(2).into_iter() {
        if chunk.len() < 2 {
            bail!("Last line (no pair): {}", chunk[0]);
        }

        let line1 = chunk[0].trim_end_matches('\\');
        let line2 = chunk[1].trim_end_matches('\\');

        let tle = TLE::load_2line(line1, line2).unwrap();

        if is_leo(&tle)? {
            let id = tle.intl_desig.clone();

            let unix_time: f64 = tle.epoch.as_unixtime();
            let whole_seconds = unix_time.trunc() as i64;
            let fractional_part = unix_time - unix_time.trunc();
            let nanos = (fractional_part * 1.0e9) as u32;

            let dt = Utc.timestamp_opt(whole_seconds, nanos).unwrap();
        
            let year = dt.year();
            let day_of_year = dt.ordinal();
            let fraction_of_day = (dt.hour() as f64
            + (dt.minute() as f64 / 60.0)
            + (dt.second() as f64 / 3600.0)
            + (dt.nanosecond() as f64 / 3.6e12)) / 24.0;  
            let day_of_year_fractional = (day_of_year as f64) + fraction_of_day;

            let instance = OrbitalInstance {
                epoch_year:           year, // or however you want
                epoch_day:            day_of_year_fractional,
                first_time_derivative: tle.mean_motion_dot,
                second_time_derivative: tle.mean_motion_dot_dot,
                drag:                 tle.bstar, // or however you store it
                inclination:          tle.inclination,
                raan:                 tle.raan,
                eccentricity:         tle.eccen,
                perigee:              tle.raan,
                mean_anomaly:         tle.mean_anomaly,
                mean_motion:          tle.mean_motion,
            };

            satellites
                .entry(id)
                .and_modify(|sat_rec| sat_rec.orbital_records.push(instance.clone()))
                .or_insert_with(|| SatelliteRecord {
                    catalog_number: tle.sat_num,
                    international_designator: tle.intl_desig.clone(),
                    orbital_records: vec![instance],
                });
        }
    }

    Ok(satellites)
}

pub(crate) fn read_txt_for_integration(filepath: &str) -> Result<HashMap<String, Vec<TLE>>> {
    let file_contents = read_to_string(filepath)?;
    let lines: Vec<&str> = file_contents.lines().collect();

    println!("Creating TLE structs out of lines");
    let time = Instant::now();
    let mut satellites: HashMap<String, Vec<TLE>> = HashMap::new();
    for satellite_tle in lines.chunks(2).into_iter() {
        let tle: TLE = TLE::load_2line(satellite_tle[0], satellite_tle[1]).unwrap();

        if is_leo(&tle)? {
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
    println!("Finished! \n Size of HashMap: {} \n Time Elapsed (s): {}", satellites.len(), time.elapsed().as_secs());
    Ok(satellites)
}

#[allow(dead_code)]
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

fn is_leo(instance:&TLE) -> Result<bool> {
    if instance.eccen < 0.25 && instance.mean_motion > 11.25 {
        Ok(true)
    } else {
        Ok(false)
    }
}