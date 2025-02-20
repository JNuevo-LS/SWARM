use sgp4::{self, Constants, Elements, Prediction};
use serde_json;
use crate::satellite::OrbitalInstance;
use anyhow::Result;

pub fn propagate_elements(name:&String, id:&String, catalog_number:&u32, instance: &OrbitalInstance) -> Result<Prediction> {
    // let _mu: f64 = 398600.4418;
    let elements = format_elements(name, id, catalog_number, instance)?;
    let constants: Constants = sgp4::Constants::from_elements(&elements)?;

    let prediction: Prediction = constants.propagate(sgp4::MinutesSinceEpoch(0.0))?;
    Ok(prediction)
}

fn format_elements(name:&String, id:&String, catalog_number:&u32, instance: &OrbitalInstance) -> Result<Elements>{
    let ecc_unsafe = instance.eccentricity < 0.0;
    let elements: String = format!(
        r#"{{
            "OBJECT_NAME": "{}",
            "OBJECT_ID": "{}",
            "EPOCH": "{}",
            "MEAN_MOTION": {},
            "ECCENTRICITY": {},
            "INCLINATION": {},
            "RA_OF_ASC_NODE": {},
            "ARG_OF_PERICENTER": {},
            "MEAN_ANOMALY": {},
            "EPHEMERIS_TYPE": 0,
            "CLASSIFICATION_TYPE": "U",
            "NORAD_CAT_ID": {},
            "ELEMENT_SET_NO": 999,
            "REV_AT_EPOCH": {},
            "BSTAR": {},
            "MEAN_MOTION_DOT": {},
            "MEAN_MOTION_DDOT": {}
        }}"#,
        name,
        id,
        instance.epoch,
        instance.mean_motion,
        if ecc_unsafe {0.0} else {instance.eccentricity},
        instance.inclination,
        instance.raan,
        instance.perigee,
        instance.mean_anomaly,
        catalog_number,
        instance.revolution_number,
        instance.drag,
        instance.first_time_derivative,
        instance.second_time_derivative
    );
    
    let elements: Elements  = serde_json::from_str(elements.as_str())?;
    Ok(elements)
}