pub mod read;
pub mod merge;
pub mod satellite;
use std::collections::HashMap;
use std::thread;
use std::time::Instant;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use satellite::SatelliteRecord;
use anyhow::Result;
fn main() {

    pyo3::prepare_freethreaded_python();

    let mut handles = vec![];

    for i in 0..2{
        let handle = thread::spawn(move || -> Result<HashMap<String, SatelliteRecord>> { //creates a thread for each CSV file
            let filepath: String = format!("./data/tle200{}.txt", 6 + i);
            let time: Instant = Instant::now();
            println!("[{i}] Now reading");
            let satellites: HashMap<String, SatelliteRecord> = read::read_txt(&filepath).expect("Failed to read CSV");
            println!("[{i}] Reading is done");
            println!("[{i}] Read in {} seconds", time.elapsed().as_secs_f64());
            println!("[{i}] Size of satellites = {}", satellites.len());
            Ok(satellites)

        });
        handles.push(handle);
    }

    //combine all satellite hashmaps from each year into one
    let mut satellites: HashMap<String, SatelliteRecord> = HashMap::new();
    for handle in handles {
        let thread_maps = handle.join().unwrap().unwrap();
        let _ = merge::merge_satellite_hashmaps(&mut satellites, thread_maps);
        println!("Merged with a thread, new size: {}", satellites.len())
    }

    //now we process and propagate that data
    Python::with_gil(|py| {
        let sys = py.import("sys").expect("Couldn't import sys");
        let path = sys.getattr("path").unwrap();
        let path = path.downcast::<pyo3::types::PyList>().unwrap();
        path.insert(0, "./python").unwrap();

        let my_script = PyModule::import(py, "propagate").expect("Failed to import module");
        
        let time = Instant::now();
        for (id, satellite_record) in satellites {
            println!("Processing {}", id);
            let satellite_record_py = satellite_record.to_python(py);

            let simulate = my_script.getattr("propagate_between_gaps").expect("Failed to get 'propagate_between_gaps'");
            println!("Processing records into Python CustomTLE Object");
            println!("Simulating Orbits");
            let _sim_result = simulate.call1((satellite_record_py, 10000)).expect("Failed to simulate orbits");
        }
        println!("Processed in {} seconds total", time.elapsed().as_secs_f64());
    });
    
}
