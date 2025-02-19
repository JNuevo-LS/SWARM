#[derive(Clone)]
pub struct SatelliteRecord {
    pub name: String,
    pub catalog_number: u32,
    pub security_class:char,
    pub international_designator:String,
    pub orbital_records: Vec<OrbitalInstance>
}

#[derive(Clone)]
pub struct OrbitalInstance {
    pub epoch:String,
    pub first_time_derivative:f64,
    pub second_time_derivative:f64,
    pub drag:f64,
    pub inclination:f64,
    pub raan:f64,
    pub eccentricity:f64,
    pub perigee:f64,
    pub mean_anomaly:f64,
    pub mean_motion:f64
}