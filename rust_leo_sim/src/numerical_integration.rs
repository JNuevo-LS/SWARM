use std::{collections::HashMap, fs::File, io::{BufWriter, Write}};
use rayon::prelude::*;
use satkit::{frametransform::qteme2gcrf, orbitprop::{propagate, PropSettings, PropagationResult, SatState}, sgp4::sgp4, types::Vector3, Duration, Instant, TLE};
use anyhow::Result;
use nalgebra::SVector;
use std::mem;
use zstd::Encoder;

pub(crate) fn integrate(map: HashMap<String, Vec<TLE>>, density:u16, compression_level:i32) -> Result<()> { //integration using streaming to upload to S3 and save space on device
    println!("Converting to SatStates");
    let time = std::time::Instant::now();
    let map: HashMap<String, Vec<SatState>> = convert_map_to_gcrf(map)?;
    println!("Converted in {}", time.elapsed().as_secs_f64());

    let mut settings = PropSettings::default();
    settings.gravity_order = 8;

    println!("Starting Numerical Integration Process");
    let time = std::time::Instant::now();
    let _integration_results = parallel_stream_integration(map, &settings, density, compression_level)?; //integrates satellites in parallel and saves to a .txt file in a streaming fashion
    println!("Integrated in {}", time.elapsed().as_secs_f64());

    Ok(())
}

fn save_time_steps(id: &String, steps: &Vec<SatState>, file_index:usize, compression_level:i32) -> Result<()> {
    let filename = format!("integration_{}_{}.txt.zst", &id, &file_index);
    let path = format!("./data/output/raw/{}", filename);
    let destination = format!("S:/SWARM/data/output/raw/{}", filename);

    let file = File::create(&path)?;
    let writer = BufWriter::new(file);
    let mut encoder = Encoder::new(writer, compression_level)?;

    for step in steps.into_iter() {
        let formatted_step: String = format_step(&step);
        let _ = writeln!(encoder, "{}", formatted_step);
    }
    let mut inner_writer = encoder.finish()?;
    let _flush = inner_writer.flush();

    let _ = move_file(&path, &destination);
    Ok(())
}

fn format_step(step: &SatState) -> String {
    let time = step.time.as_unixtime();
    let pos_gcrf = step.pos_gcrf();
    let vel_gcrf = step.vel_gcrf();
    let formatted_step = format!("{},{},{},{},{},{},{}", time, pos_gcrf[0], pos_gcrf[1], pos_gcrf[2], vel_gcrf[0], vel_gcrf[1], vel_gcrf[2]);
    return formatted_step;
}

fn make_sat_state(time: Instant, svec: SVector<f64, 6>) -> SatState {
    let pos = Vector3::new(svec[0], svec[1], svec[2]);
    let vel = Vector3::new(svec[3], svec[4], svec[5]);

    SatState::from_pv(&time, &pos, &vel)
}

fn integrate_between_gaps(records: Vec<SatState>, settings: &PropSettings) -> Result<Vec<PropagationResult<1>>> {
    let mut result_vec: Vec<PropagationResult<1>> =  Vec::new();
    for window in records.windows(2) {
        let current_record: &SatState = &window[0];
        let next_record: &SatState = &window[1];

        let start: &Instant = &current_record.time;
        let stop: &Instant = &next_record.time;
        let dt: f64 = (stop - start).as_seconds(); 

        if start == stop || dt < 60.0*30.0 { //skips cases where TLEs updated too frequently to propagate in between
            continue;
        }

        //extracts position and velocity from SatState to create a state
        let pos = current_record.pos_gcrf();
        let vel = current_record.vel_gcrf();
        let state = SVector::<f64, 6>::new(pos[0], pos[1], pos[2], vel[0], vel[1], vel[2]);

        let result = propagate(&state, start, stop, settings, None).unwrap();
        result_vec.push(result)
    }
    Ok(result_vec)
}

fn tle_teme_to_gcrf(records:Vec<TLE>) -> Result<Vec<SatState>> {
    let mut gcrf_states:Vec<SatState> = Vec::new();

    for mut tle in records {
        let epoch: Instant = tle.epoch;
        let (r_teme, v_teme, _errs) = sgp4(&mut tle, &[epoch]);

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

fn gcrf_to_teme(states: Vec<SatState>) {
    let teme_states: Vec<SatState> = Vec::new();

}

fn convert_map_to_gcrf(map:HashMap<String, Vec<TLE>>) -> Result<HashMap<String, Vec<SatState>>> {
    map.into_par_iter()
        .map(|(id, records)| {
            tle_teme_to_gcrf(records).map(|states| (id, states))
        })
        .collect()
}

fn parallel_stream_integration(map: HashMap<String, Vec<SatState>>, settings: &PropSettings, density:u16, compression_level:i32) -> Result<()> {
    const MAX_VEC_SIZE:usize = 1_572_864_000 ; //1.5 GB in mem change as needed
    map.into_par_iter()
        .try_for_each(|(id, records)| -> Result<()>{
            Ok(stream(records, settings, &id, density, MAX_VEC_SIZE, compression_level)?)
        })?;
    Ok(())
}

fn move_file(filepath: &str, destination_filepath: &str) -> Result<()> {
    let _copy = std::fs::copy(filepath, destination_filepath)?;
    let deleted: () = std::fs::remove_file(filepath)?;
    Ok(deleted)
}

fn stream(records: Vec<SatState>, settings: &PropSettings, id: &String, density:u16, max_vec_size: usize, compression_level: i32) -> Result<()>{
    let results = integrate_between_gaps(records, settings)?;
    
    let mut time_steps: Vec<SatState> = Vec::new();
    let mut file_index:usize = 0;

    for result in results.into_iter() {
        let start = result.time_start;
        let end = result.time_end;
        let dt = end -  result.time_start;

        let interval = dt.as_seconds() / density as f64;
        for i in 0..density {
            let shift = interval * i as f64;
            let time = start + Duration::from_seconds(shift);
            let matrix_at_time = result.interp(&time).unwrap();
            let state_at_time = make_sat_state(time, matrix_at_time);
            time_steps.push(state_at_time);
            
            let vec_size_in_bytes = time_steps.len() * mem::size_of::<SatState>();
            if vec_size_in_bytes > max_vec_size {
                let _ = save_time_steps(&id, &time_steps, file_index, compression_level);
                time_steps.clear();
                file_index += 1;
            }
        }
        time_steps.push(make_sat_state(end, result.state_end));
    }
    if !time_steps.is_empty() {
        let _ = save_time_steps(id, &time_steps, file_index, compression_level);
    }
    Ok(())
}