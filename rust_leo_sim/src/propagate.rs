use std::error::Error;
use sgp4::{self, Constants, Elements, Prediction};
use serde_json;
use crate::satellite::OrbitalInstance;

pub fn propagate_elements(name:&String, id:&String, catalog_number:&u32, instance: &OrbitalInstance, time:u32 ) -> Result<Vec<Prediction>, Box<dyn Error>> {
    // let _mu: f64 = 398600.4418;
    println!("Propagating {}", name);
    let elements = format_elements(name, id, catalog_number, instance)?;
    let constants: Constants = sgp4::Constants::from_elements(&elements)?;

    let mut predicted: Vec<Prediction> = Vec::new();

    for hours in 0..time+1 {
        println!("t = {} min, BSTAR = {}", hours * 60, instance.drag);
        let prediction = constants.propagate(sgp4::MinutesSinceEpoch((hours * 60) as f64))?;
        println!("    r = {:?} km", prediction.position);
        println!("    ṙ = {:?} km.s⁻¹", prediction.velocity);
        predicted.push(prediction)
    }
    Ok(predicted)
}

fn format_elements(name:&String, id:&String, catalog_number:&u32, instance: &OrbitalInstance) -> Result<Elements, Box <dyn Error>>{
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
        instance.eccentricity,
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