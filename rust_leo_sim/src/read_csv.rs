use std::fs::File;
use std::io::{self, BufRead, BufReader, Error, Lines};
#[derive(Clone)]
pub struct Satellite {
    pub name: String,
    pub catalog_number: u32,
    pub security_class:char,
    pub international_designator:String,
    pub epoch:String,
    pub first_time_derivative:f64,
    pub second_time_derivative:f64,
    pub drag:f64,
    pub inclination:f64,
    pub raan:f64,
    pub eccentricity:f64,
    pub perigee:f64,
    pub mean_anomaly:f64,
    pub mean_motion:f64
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
            
            let year = split[4].parse::<u16>().unwrap();
            let day = split[5].parse::<f64>().unwrap();
            let dt = format_datetime(year, day)?;
            
            let satellite: Satellite = Satellite {
                name: split[0].to_string(),
                catalog_number: split[1].trim().parse::<u32>().unwrap(),
                security_class: split[2].chars().next().unwrap(),
                international_designator: split[3].to_string(),
                epoch: dt,
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

fn format_datetime(year:u16, day:f64) -> Result<String, Error> {
    let year = year+2000;
    let leap_year = is_leap_year(year);
    let (month, day_string) = find_month_and_day(day, leap_year)?;
    let hour = (day*24.0)%24.0;
    let minute = (day*24.0*60.0)%60.0;
    let second = (day*24.0*60.0*60.0)%100.0;
    let dt = format!("{year}-{month}-{day_string}T{hour:.0}:{minute:.0}:{second:.6}");
    Ok(dt)

}

fn is_leap_year(year: u16) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}

fn find_month_and_day(mut day:f64, leap_year:bool) -> Result<(String, String), Error> {
    if leap_year && day > 61.0 {
        day = day-1.0; //makes it easier to deal with leap years after february
    }

    let month: String;
    if day < 31.0 {
        month = String::from("01");
    } else if (leap_year == true && day < 60.0) || (leap_year == false && day < 59.0 ){
        month = String::from("02");
        day -= 31.0;
    } else if day < 90.0 {
        month = String::from("03");
        day -= 59.0;
    } else if day < 120.0 {
        month = String::from("04");
        day -= 90.0;
    } else if day < 151.0 {
        month = String::from("05");
        day -= 120.0;
    } else if day < 181.0 {
        month = String::from("06");
        day -= 151.0;
    } else if day < 212.0 {
        month = String::from("07");
        day -= 181.0;
    } else if day < 243.0 {
        month =String::from("08");
        day -= 212.0;
    } else if day < 273.0 {
        month = String::from("09");
        day -= 243.0;
    } else if day < 304.0 {
        month =String::from("10");
        day -= 273.0;
    } else if day < 334.0 {
        month = String::from("11");
        day -= 304.0;
    } else if day < 366.0 {
        month = String::from("12");
        day -= 334.0;
    }
     else {
        println!("{}", day);
        return Err(Error::new(io::ErrorKind::Other, "Day outside of expected range"));
    }
    let day_string: String = String::from(format!("{}", day.floor()));
    let date: (String, String) = (month, day_string);
    Ok(date)
}