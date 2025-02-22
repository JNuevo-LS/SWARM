use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

#[derive(Clone)]
pub struct SatelliteRecord {
    pub catalog_number: u32,
    pub international_designator:String,
    pub orbital_records: Vec<OrbitalInstance>
}

impl SatelliteRecord {
    fn to_py_dict(&self, py:Python, instance: &OrbitalInstance) -> PyObject {
        let dict = PyDict::new(py);
        dict.set_item("satellite_catalog_number", self.catalog_number).unwrap();
        dict.set_item("international_designator", self.international_designator.clone()).unwrap();
        dict.set_item("epoch_year", instance.epoch_year).unwrap();
        dict.set_item("epoch_days", instance.epoch_day).unwrap();
        dict.set_item("mean_motion_first_derivative", instance.first_time_derivative).unwrap();
        dict.set_item("mean_motion_second_derivative", instance.second_time_derivative).unwrap();
        dict.set_item("b_star", instance.drag).unwrap();
        dict.set_item("inclination", instance.inclination).unwrap();
        dict.set_item("raan", instance.raan).unwrap();
        dict.set_item("eccentricity", instance.eccentricity).unwrap();
        dict.set_item("argument_of_perigee", instance.perigee).unwrap();
        dict.set_item("mean_anomaly", instance.mean_anomaly).unwrap();
        dict.set_item("mean_motion", instance.mean_motion).unwrap();
        dict.set_item("revolution_number_at_epoch", instance.revolution_number).unwrap();
        
        //items below are hardcoded because they don't matter for propagation and are pretty much the same for everything
        dict.set_item("classification", "U").unwrap();
        dict.set_item("element_number", 999).unwrap();
        dict.set_item("ephemeris_type", 0).unwrap();

        dict.into()
    }
    
    pub fn to_python(&self, py:Python) -> PyObject {
        let dicts: Vec<PyObject> = self
        .orbital_records
        .iter()
        .map(|instance: &OrbitalInstance| self.to_py_dict(py, instance))
        .collect();
        let pylist = PyList::new(py, dicts).unwrap().into();
        return pylist;
    }
}

#[derive(Clone)]
pub struct OrbitalInstance {
    pub epoch_year:u16,
    pub epoch_day:f64,
    pub first_time_derivative:f64,
    pub second_time_derivative:f64,
    pub drag:f64,
    pub inclination:f64,
    pub raan:f64,
    pub eccentricity:f64,
    pub perigee:f64,
    pub mean_anomaly:f64,
    pub mean_motion:f64,
    pub revolution_number:u32
}