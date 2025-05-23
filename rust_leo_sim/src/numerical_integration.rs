use std::{collections::HashMap, fs::File, io::{BufWriter, Write}, str::FromStr};
use rayon::prelude::*;
use satkit::{frametransform::qteme2gcrf, orbitprop::{propagate, PropSettings, PropagationResult, SatState}, sgp4::sgp4, types::Vector3, Duration, Instant, TLE};
use anyhow::Result;
use nalgebra::SVector;
use std::mem;
use zstd::Encoder;

pub(crate) fn integrate(map: HashMap<String, Vec<TLE>>, density:u16, compression_level:i32) -> Result<()> { //integration using streaming to upload to S3 and save space on device
    println!("Converting to SatStates");
    let time = std::time::Instant::now();
    let map: HashMap<String, (Vec<TLE>, Vec<SatState>)> = convert_map_to_gcrf(map)?;
    println!("Converted in {}", time.elapsed().as_secs_f64());

    let mut settings = PropSettings::default();
    settings.gravity_order = 8;

    println!("Starting Numerical Integration Process");
    let time = std::time::Instant::now();
    let _integration_results = parallel_stream_integration(map, &settings, density, compression_level)?; //integrates satellites in parallel and saves to a .txt file in a streaming fashion (compressed with zstandard)
    println!("Integrated in {}", time.elapsed().as_secs_f64());

    Ok(())
}

fn save_time_steps_zstd(mut encoder:Encoder<'static, BufWriter<File>>, steps: Vec<SatState>) -> Result<BufWriter<File>> {
    for step in steps.into_iter() {
        let formatted_step: String = format_step(&step);
        let _ = writeln!(encoder, "{}", formatted_step);
    }
    let mut inner_writer = encoder.finish()?;
    let _flush = inner_writer.flush();

    Ok(inner_writer)
}

fn create_file(filename: &String) -> Result<File> {
    let path = format!("./data/output/raw/{}", filename);
    let file: File = File::create(&path)?;
    Ok(file)
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

fn integrate_between_gaps(states: Vec<SatState>, settings: &PropSettings) -> Result<Vec<PropagationResult<1>>> {
    let mut result_vec: Vec<PropagationResult<1>> =  Vec::new();
    for window in states.windows(2) {
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

fn tle_teme_to_gcrf(mut records:Vec<TLE>) -> Result<(Vec<TLE>, Vec<SatState>)> {
    //Converts TLEs in TEME to GCRF SatStates

    let mut gcrf_states:Vec<SatState> = Vec::new();

    for mut tle in records.iter_mut() {
        let epoch: Instant = tle.epoch;
        let (r_teme, v_teme, _errs) = sgp4(&mut tle, &[epoch]);

        //used to convert to geocentric (GCRF)
        let q_teme_to_gcrf = qteme2gcrf(&epoch);

        //converts position and velocity vectors from TEME formatted matrices to GCRF formatted matrices (both in kilometers)
        let r_gcrf = q_teme_to_gcrf.to_rotation_matrix() * r_teme;
        let v_gcrf = q_teme_to_gcrf.to_rotation_matrix() * v_teme;

        //fixed object as SatState::from_pv expects it
        let r_fixed = Vector3::new(r_gcrf[0], r_gcrf[1], r_gcrf[2]);
        let v_fixed = Vector3::new(v_gcrf[0], v_gcrf[1], v_gcrf[2]);

        let state: SatState = SatState::from_pv(&epoch, &r_fixed, &v_fixed);

        gcrf_states.push(state);
    }
    Ok((records, gcrf_states))
}

// fn gcrf_to_teme(states: Vec<SatState>) { //todo, possibly not needed
//     let teme_states: Vec<SatState> = Vec::new();

// }

fn convert_map_to_gcrf(map:HashMap<String, Vec<TLE>>) -> Result<HashMap<String, (Vec<TLE>, Vec<SatState>)>> {
    map.into_par_iter()
        .map(|(id, records)| {
            tle_teme_to_gcrf(records).map(|states| (id, states))
        })
        .collect()
}

fn parallel_stream_integration(map: HashMap<String, (Vec<TLE>, Vec<SatState>)>, settings: &PropSettings, density:u16, compression_level:i32) -> Result<()> {
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

fn stream(records: (Vec<TLE>, Vec<SatState>), settings: &PropSettings, id: &String, density:u16, max_vec_size: usize, compression_level: i32) -> Result<()>{
    let (tles, states) = records;
    let results = integrate_between_gaps(states, settings)?; //this generates a propagation result object in between every SatState (instance in time)
    
    let mut time_steps: Vec<SatState> = Vec::new();
    let mut file_index:usize = 0;

    let filename: String = format!("integration_{}_{}.txt.zst", &id, &file_index);
    let file: File = create_file(&filename)?;
    let writer: BufWriter<File> = BufWriter::new(file);
    let mut encoder: Encoder<'static, BufWriter<File>> = Encoder::new(writer, compression_level)?; //used to compress with
    for (i, result) in results.into_iter().enumerate() { //this then uses the propagation results generated to save n = density instances in time between each interval
        let start = result.time_start;                                       //each instance contains the time, position, and velocity of the satellite (i.e they're all SatStates)
        let end = result.time_end;
        let dt = end -  result.time_start;

        write_TLE_data(encoder, tles[i]);

        let interval = dt.as_seconds() / density as f64;
        for j in 0..density {
            let shift = interval * j as f64;
            let time = start + Duration::from_seconds(shift);
            let matrix_at_time = result.interp(&time).unwrap();
            let state_at_time = make_sat_state(time, matrix_at_time);
            time_steps.push(state_at_time);
            
            let vec_size_in_bytes = time_steps.len() * mem::size_of::<SatState>();
            if vec_size_in_bytes > max_vec_size { //we flush the content of time_steps to a new file
                let mut encoder: Encoder<'static, BufWriter<File>> = Encoder::new(writer, compression_level)?;
                let _ = save_time_steps_zstd(encoder, time_steps);
                let destination = format!("/mnt/IronWolfPro8TB/SWARM/data/output/raw/{}", &filename);
                time_steps.clear();
            }
        }
        time_steps.push(make_sat_state(end, result.state_end));
    }
    if !time_steps.is_empty() {
        let _ = save_time_steps_zstd(id, &time_steps);
    }
    Ok(())
}

fn write_TLE_data(encoder: Encoder<'static, BufWriter<File>>, tle:TLE) -> Result<()>{
    //write line1
    let mut line1: String = String::from_str("1 ")?;

    //indices 2-7 (excluded) are the satellite catalog number
    let sat_num: i32 = tle.sat_num;
    let num_digits: i32 = i32::ilog10(sat_num) as i32;
    let mut sat_num_string = String::from_str("")?;
    if num_digits < 5 {
        let num_zeroes: usize = 5 - (num_digits as usize);
        let zeroes = "0".repeat(num_zeroes);
        sat_num_string.push_str(&zeroes);
        sat_num_string.push_str(&sat_num.to_string());
    } else {
        sat_num_string.push_str(&sat_num.to_string());
    }
    line1.push_str(&sat_num_string);
    line1.push_str("U "); //index 7 is the classification, hardcoded because there are no classified satellites in data

    //indices 9-17 make up the international designator
    let international_designator: String = tle.intl_desig;
    let len: usize = international_designator.chars().count();
    line1.push_str(&international_designator);
    if len < 8 {
        let padding = len - 8;
        line1.push_str(&" ".repeat(padding))
    }
    line1.push_str(" ");

    //indices 18-20 are the last two digits of the launch year
    let year = tle.desig_year;
    line1.push_str(&year.to_string());

    //20-32 is the day of the year + fractional part of day
    let day = tle.epoch.as_unixtime() / (60.0 * 60.0 * 24.0) ;
    if year > 30 {
        let day = day - (20.0 + year as f64);
    }


    //write line2


    Ok(())
}