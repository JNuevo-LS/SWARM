use pyo3::prelude::*;
use rayon::prelude::*;
use std::{collections::HashMap, time::Instant};
use crate::satellite::SatelliteRecord;

pub(crate) fn propagate_satellites(satellites: HashMap<String, SatelliteRecord>) { 
    Python::with_gil(|outer_py|{
        let _ = outer_py.allow_threads(|| {
            satellites.par_iter().for_each(|(id, satellite_record)| {
                simulate(id, satellite_record);
            });
        });
    })
}

fn simulate(id: &String, satellite_record: &SatelliteRecord) {
    Python::with_gil(|py| {
        let sys = py.import("sys").expect("Couldn't import sys");
        let path = sys.getattr("path").unwrap();
        let path = path.downcast::<pyo3::types::PyList>().unwrap();
        path.insert(0, "./python").unwrap();

        let propagate_py = PyModule::import(py, "propagate").expect("Failed to import module");
        let satellite_record_py = satellite_record.to_python(py);
        
        // let model = start_up_model.call0().expect("Failed to start up ml_dsgp4 model");
        let simulator = propagate_py.getattr("propagate_between_gaps").expect("Failed to get 'propagate_between_gaps'");
        println!("[{id}] Simulating Orbits");
        let time = Instant::now();
        let _sim_result = simulator.call1((satellite_record_py, 10000)).expect("Failed to simulate orbits");
        println!("[{id} Finished simulating orbits in {}", time.elapsed().as_secs_f64())
    });
}