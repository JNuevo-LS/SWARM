use std::fs::File;
use std::io::{BufRead, BufReader, Lines, Error};

pub struct Satellite {
    name: String,
    satellite_catalog_number: u32,
    security_class:char,
    international_designator:String,
    year:u8,
    day:f64,
    first_time_derivative:f64,
    second_time_derivative:f64,
    drag:f64,
    inclination:f64,
    raan:f64,
    eccentricity:f64,
    perigee:f64,
    mean_anomaly:f64,
    mean_motion:f64
}

pub fn read_csv(file_path: &str) -> Result<Vec<Satellite>, Error> {
    let file: File = File::open(file_path)?;
    let reader: BufReader<File> = BufReader::new(file);
    
    let mut lines: Lines<BufReader<File>> = reader.lines();
    lines.next(); //skip header

    let mut satellites: Vec<Satellite> = Vec::new();

    for line in lines {
        let line: String = line?;
        if line.len() > 0 {
            let split: Vec<&str> = line.split(",").collect();
            
            let satellite: Satellite = Satellite {
                name: split[0].to_string(),
                satellite_catalog_number: split[1].trim().parse::<u32>().unwrap(),
                security_class: split[2].chars().next().unwrap(),
                international_designator: split[3].to_string(),
                year: split[4].parse::<u8>().unwrap(),
                day: split[5].parse::<f64>().unwrap(),
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
            satellites.push(satellite);
        }
    }
    
    println!("Successfully read everything");

    Ok(satellites)
}

