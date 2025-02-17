pub mod read_csv;
pub mod propagate;
use std::thread;
use std::time::Instant;
use propagate::propagate_elements;
use serde_json::Error;

fn main() {

    let mut handles = vec![];

    for i in 1..6{
        let handle = thread::spawn(move || -> Result<(), Error> { //Creates a thread for each CSV file
            let filepath = format!("./data/TLE_LEO.{i}.csv");
            let time = Instant::now();
            let satellites = read_csv::read_csv(&filepath).expect("Failed to read CSV");
            println!("[{i}] Reading is done");
            println!("[{i}] Read in {} seconds", time.elapsed().as_secs_f64());
            println!("[{i}] Size of satellites = {}", satellites.len());
            let mut j: usize = 0;
            let time = Instant::now();
            while j < satellites.len() {
                let _p = propagate_elements(&satellites[i]);
                j+=1;
            }
            let total: f64 = time.elapsed().as_secs_f64();
            println!("[{i}] Total Time Spent: {}", total);
            let average: f64 = total/satellites.len() as f64;
            println!("[{i}] Average Time per Item: {}", average);
            Ok(())

        });
        handles.push(handle);
    }

    for handle in handles {
        let _ = handle.join().unwrap();
    }
}
