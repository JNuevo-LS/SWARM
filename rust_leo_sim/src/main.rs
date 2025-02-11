mod read_csv;
use std::thread;

fn main() {

    let mut handles = vec![];

    for i in 1..13 {
        let handle = thread::spawn(move || {
            let filepath = format!("./data/TLE_LEO.{i}.csv");
            let satellites = read_csv::read_csv(&filepath);
            println!("Reading {i} is done");
            println!("Size of satellites = {}", satellites.expect("REASON").len())
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.join().unwrap();
    }
}
