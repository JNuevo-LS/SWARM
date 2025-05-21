use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

#[derive(Clone)]
pub(crate) struct SatelliteRecord {
    pub(crate) catalog_number: i32,
    pub(crate) international_designator:String,
    pub(crate) orbital_records: Vec<OrbitalInstance>
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
        
        //items below are hardcoded because they don't matter for propagation and are pretty much the same for everything
        dict.set_item("classification", "U").unwrap();
        dict.set_item("element_number", 999).unwrap();
        dict.set_item("ephemeris_type", 0).unwrap();

        dict.into()
    }
    
    pub(crate) fn to_python(&self, py:Python) -> PyObject {
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
pub(crate) struct OrbitalInstance {
    pub(crate) epoch_year:i32,
    pub(crate) epoch_day:f64,
    pub(crate) first_time_derivative:f64,
    pub(crate) second_time_derivative:f64,
    pub(crate) drag:f64,
    pub(crate) inclination:f64,
    pub(crate) raan:f64,
    pub(crate) eccentricity:f64,
    pub(crate) perigee:f64,
    pub(crate) mean_anomaly:f64,
    pub(crate) mean_motion:f64,
}