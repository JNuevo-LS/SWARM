pub mod read_csv;
pub mod propagate;
pub mod merge;
pub mod satellite;
use std::collections::HashMap;
use std::thread;
use std::time::Instant;
use propagate::propagate_elements;
use satellite::SatelliteRecord;
use anyhow::Result;

fn main() {

    let mut handles = vec![];

    for i in 1..2{
        let handle = thread::spawn(move || -> Result<HashMap<String, SatelliteRecord>> { //creates a thread for each CSV file
            let filepath: String = format!("./data/TLE_LEO.{i}.csv");
            let time: Instant = Instant::now();
            let satellites: HashMap<String, SatelliteRecord> = read_csv::read_csv(&filepath).expect("Failed to read CSV");
            println!("[{i}] Reading is done");
            println!("[{i}] Read in {} seconds", time.elapsed().as_secs_f64());
            println!("[{i}] Size of satellites = {}", satellites.len());
            let time = Instant::now();


            let total: f64 = time.elapsed().as_secs_f64();
            println!("[{i}] Total Time Spent: {}", total);
            // let average: f64 = total/satellites.len() as f64;
            // println!("[{i}] Average Time per Item: {}", average);
            Ok(satellites)

        });
        handles.push(handle);
    }

    let mut satellites: HashMap<String, SatelliteRecord> = HashMap::new();
    for handle in handles {
        let thread_maps = handle.join().unwrap().unwrap();
        let _ = merge::merge_satellite_hashmaps(&mut satellites, thread_maps);
        println!("Merged with a thread, new size: {}", satellites.len())
    }

    
    for (_id, satellite_record) in satellites {
        println!("Found {} records for {}", satellite_record.orbital_records.len(), satellite_record.international_designator);
        for window in satellite_record.orbital_records.windows(2).rev() { //iterates in reverse order (which comes out to be chronological order)
            let current = &window[0];
            println!("Current: {}", current.epoch);
            let next = &window[1];
            println!("Next: {}", next.epoch);
            println!("Calculating time");
            let time: u32 = read_csv::hour_difference_between_epochs(&current.epoch, &next.epoch).unwrap();
            println!("Propagating {time} hours");
            let propagation = propagate_elements(&satellite_record.name, &satellite_record.international_designator, &satellite_record.catalog_number, current, time).unwrap();
            println!("Len of propagation: {}", propagation.len())
        }
    }
    
}
