use std::collections::HashMap;
use rayon::prelude::*;
use satkit::{frametransform::qteme2gcrf, orbitprop::SatState, sgp4::{sgp4, GravConst, OpsMode}, types::Vector3, Instant, TLE};
use anyhow::Result;

pub(crate) fn integrate(map:HashMap<String, Vec<TLE>>) -> Result<()> {//TODO: Use Range-Kutta 9(8) from satkit to create high-accuracy orbits
    println!("Converting to SatStates");
    let time = std::time::Instant::now();
    let _map: HashMap<String, Vec<SatState>> = convert_map_to_gcrf(map)?;
    println!("Converted in {}", time.elapsed().as_secs_f64());
    Ok(())

}

fn convert_map_to_gcrf(map:HashMap<String, Vec<TLE>>) -> Result<HashMap<String, Vec<SatState>>> {
    map.into_par_iter()
        .map(|(id, records)| {
            teme_to_gcrf(records).map(|states| (id, states))
        })
        .collect()
}

fn teme_to_gcrf(records:Vec<TLE>) -> Result<Vec<SatState>> {
    let mut gcrf_states:Vec<SatState> = Vec::new();

    for mut tle in records {
        let epoch: Instant = tle.epoch;
        let (r_teme, v_teme, errs) = sgp4(&mut tle, &[epoch]);

        //used to convert to geocentric (GCRF)
        let q_teme_to_gcrf = qteme2gcrf(&epoch);

        //converts position and velocity vectors from kilometers and TEME formatted matrices to meters and GCRF formatted matrices
        let r_gcrf = q_teme_to_gcrf.to_rotation_matrix() * r_teme * 1000.0;
        let v_gcrf = q_teme_to_gcrf.to_rotation_matrix() * v_teme * 1000.0;

        //fixed object as SatState::from_pv expects it
        let r_fixed = Vector3::new(r_gcrf[0], r_gcrf[1], r_gcrf[2]);
        let v_fixed = Vector3::new(v_gcrf[0], v_gcrf[1], v_gcrf[2]);

        let state: SatState = SatState::from_pv(&epoch, &r_fixed, &v_fixed);

        gcrf_states.push(state);
    }
    Ok(gcrf_states)
}

