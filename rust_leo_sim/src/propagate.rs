use std::error::Error;
use sgp4::{self, Constants, Elements};
use serde_json;
use crate::read_csv::Satellite;

pub fn propagate_elements(satellite:&Satellite) -> Result<(), Box<dyn Error>> {
    let _mu: f64 = 398600.4418;

    let elements: String = format!(
        r#"{{
            "OBJECT_NAME": {},
            "OBJECT_ID": "{}",
            "EPOCH": "{}",
            "MEAN_MOTION": {},
            "ECCENTRICITY": {},
            "INCLINATION": {},
            "RA_OF_ASC_NODE": {},
            "ARG_OF_PERICENTER": {},
            "MEAN_ANOMALY": {},
            "EPHEMERIS_TYPE": 0,
            "CLASSIFICATION_TYPE": "{}",
            "NORAD_CAT_ID": {},
            "ELEMENT_SET_NO": 999,
            "REV_AT_EPOCH": 9999,
            "BSTAR": {},
            "MEAN_MOTION_DOT": {},
            "MEAN_MOTION_DDOT": {}
        }}"#,
        satellite.name,
        satellite.international_designator,
        satellite.epoch,
        satellite.mean_motion,
        satellite.eccentricity,
        satellite.inclination,
        satellite.raan,
        satellite.perigee,
        satellite.mean_anomaly,
        satellite.security_class,
        satellite.catalog_number,
        satellite.drag,
        satellite.first_time_derivative,
        satellite.second_time_derivative
    );
    let json: Elements  = serde_json::from_str(elements.as_str())?;
    let constants: Constants = sgp4::Constants::from_elements(&json)?;

    for hours in 0..24 {
        // println!("t = {} min", hours * 60);
        let _prediction = constants.propagate(sgp4::MinutesSinceEpoch((hours * 60) as f64))?;
        // println!("    r = {:?} km", prediction.position);
        // println!("    ṙ = {:?} km.s⁻¹", prediction.velocity);
    }
    Ok(())
}