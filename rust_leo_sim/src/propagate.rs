use std::error::Error;
use sgp4::{self, Constants, Elements};
use serde_json;
use crate::satellite::OrbitalInstance;

pub fn propagate_elements(instance: &OrbitalInstance, time:u32 ) -> Result<(), Box<dyn Error>> {
    // let _mu: f64 = 398600.4418;

    let elements = format_elements(instance)?;
    let constants: Constants = sgp4::Constants::from_elements(&elements)?;

    for hours in 0..time {
        println!("t = {} min", hours * 60);
        let prediction = constants.propagate(sgp4::MinutesSinceEpoch((hours * 60) as f64))?;
        println!("    r = {:?} km", prediction.position);
        println!("    ṙ = {:?} km.s⁻¹", prediction.velocity);
    }
    Ok(())
}

fn format_elements(instance: &OrbitalInstance) -> Result<Elements, Box <dyn Error>>{
    let elements: String = format!(
        r#"{{
            "OBJECT_NAME": "a",
            "OBJECT_ID": "b",
            "EPOCH": "{}",
            "MEAN_MOTION": {},
            "ECCENTRICITY": {},
            "INCLINATION": {},
            "RA_OF_ASC_NODE": {},
            "ARG_OF_PERICENTER": {},
            "MEAN_ANOMALY": {},
            "EPHEMERIS_TYPE": 0,
            "CLASSIFICATION_TYPE": "U",
            "NORAD_CAT_ID": c,
            "ELEMENT_SET_NO": 999,
            "REV_AT_EPOCH": 9999,
            "BSTAR": {},
            "MEAN_MOTION_DOT": {},
            "MEAN_MOTION_DDOT": {}
        }}"#,
        instance.epoch,
        instance.mean_motion,
        instance.eccentricity,
        instance.inclination,
        instance.raan,
        instance.perigee,
        instance.mean_anomaly,
        instance.drag,
        instance.first_time_derivative,
        instance.second_time_derivative
    );
    
    let elements: Elements  = serde_json::from_str(elements.as_str())?;
    Ok(elements)
}