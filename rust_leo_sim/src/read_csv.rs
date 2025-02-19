use std::fs::File;
use std::io::{BufRead, BufReader, Lines};
use std::collections::HashMap;
use crate::satellite::{OrbitalInstance, SatelliteRecord};
use sgp4::chrono::NaiveDateTime;
use anyhow::{bail, Result};

pub fn read_csv(file_path: &str) -> Result<HashMap<String, SatelliteRecord>> {
    let file: File = File::open(file_path)?;
    let reader: BufReader<File> = BufReader::new(file);
    
    let mut lines: Lines<BufReader<File>> = reader.lines();
    lines.next(); //skip header

    let mut satellites: HashMap<String, SatelliteRecord> = HashMap::new();

    for line in lines {
        let line: String = line?;
        if line.len() > 0 {
            let split: Vec<&str> = line.split(",").collect();
            
            let year = split[4].parse::<u16>().unwrap();
            let day = split[5].parse::<f64>().unwrap();
            let dt = format_datetime(year, day)?;

            let international_designator: String = split[3].to_string();

            let instance: OrbitalInstance = OrbitalInstance { //creates an instance of the satellite's orbital data including time
                    epoch:dt,
                    first_time_derivative: split[6].parse::<f64>().unwrap(),
                    second_time_derivative: split[7].parse::<f64>().unwrap(),
                    drag: split[8].parse::<f64>().unwrap(),
                    inclination: split[9].parse::<f64>().unwrap(),
                    raan: split[10].parse::<f64>().unwrap(),
                    eccentricity: split[11].parse::<f64>().unwrap(),
                    perigee: split[12].parse::<f64>().unwrap(),
                    mean_anomaly: split[13].parse::<f64>().unwrap(),
                    mean_motion: split[14].parse::<f64>().unwrap()
                };

            if satellites.contains_key(&international_designator) {
                satellites.get_mut(&international_designator).unwrap().orbital_records.push(instance) //pushes the satellite's instance to the SatelliteRecords struct
            } else { //if satellite hasn't been recorded yet, creates a record of it and initializes a new vector of orbital instances
                let orbital_records:Vec<OrbitalInstance> =  Vec::new();

                let satellite_record = SatelliteRecord {
                    name: split[0].to_string(),
                    catalog_number: split[1].trim().parse::<u32>().unwrap(),
                    security_class: split[2].chars().next().unwrap(),
                    international_designator: split[3].to_string(),
                    orbital_records: orbital_records
                };

                satellites.insert(international_designator, satellite_record);
            }
        }
    }
    
    println!("Successfully read everything");

    Ok(satellites)
}

fn format_datetime(year:u16, day:f64) -> Result<String> {
    let year = year+2000;
    let leap_year = is_leap_year(year);
    let (month, day_string) = find_month_and_day(day, leap_year)?;
    let hour = (day*24.0) as u32 % 24;
    let minute = ((day*24.0*60.0)%60.0).floor() as u32;
    let second = (day*24.0*60.0*60.0)%60.0;
    let dt = format!("{year:04}-{month:02}-{day_string}T{hour:02.0}:{minute:02.0}:{second:09.6}");
    Ok(dt)
}

pub fn hour_difference_between_epochs(datetime1:&String, datetime2:&String) -> Result<u32> {
    let seconds_dt1 = parse_datetime(datetime1)?;
    let seconds_dt2 = parse_datetime(datetime2)?;
    if seconds_dt1 > seconds_dt2 { //makes sure output is never negative
        Ok((seconds_dt1 - seconds_dt2) / 3600)
    } else {
        Ok((seconds_dt2 - seconds_dt1) / 3600)
    }
}

fn parse_datetime(datetime: &String) -> Result<u32> {
    let naive_dt = NaiveDateTime::parse_from_str(datetime, "%Y-%m-%dT%H:%M:%S%.6f")?;
    Ok(naive_dt.and_utc().timestamp() as u32)
}


fn is_leap_year(year: u16) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}

fn find_month_and_day(day:f64, leap_year:bool) -> Result<(String, String)> {
    let months: [u16; 12] = if leap_year {
        [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    } else {
        [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    };

    let mut day_int: u16  = day.floor() as u16;


    let max_day: u16 = if leap_year {367} else {366};
    if day_int > max_day {
            bail!("Day {} is outside of range {}", day, max_day);
        }
    

    let mut month_index: u8 = 1;

    for &days_in_month in &months {
        if day_int <= days_in_month {
            break;
        } else {
            day_int -= days_in_month;
            month_index += 1;
        }
    }

    let month_string = String::from(format!("{:02}", month_index));
    let day_string = String::from(format!("{:02}", day_int));
    Ok((month_string, day_string))

}