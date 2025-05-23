use std::{collections::{HashMap, VecDeque}, fs::File, io::{BufWriter, Write}};
use rayon::prelude::*;
use satkit::{frametransform::qteme2gcrf, orbitprop::{propagate, PropSettings, PropagationResult, SatState}, sgp4::sgp4, types::Vector3, Duration, Instant, TLE};
use anyhow::Result;
use nalgebra::SVector;
use std::mem;
use zstd::Encoder;
use chrono::{Datelike, TimeZone, Utc};

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

fn stream(records: (Vec<TLE>, Vec<SatState>), settings: &PropSettings, id: &String, density:u16, max_vec_size: usize, compression_level: i32) -> Result<()>{
    let (tles, states) = records;
    let results = integrate_between_gaps(states, settings)?; //this generates a propagation result object in between every SatState (instance in time)
    
    let mut time_batches: Vec<Vec<SatState>> = Vec::new(); //stores each "step"
    let filename: String = format!("integration_{}.txt.zst", &id);
    let file: File = create_file(&filename)?;
    let writer: BufWriter<File> = BufWriter::new(file);
    let mut encoder: Encoder<'static, BufWriter<File>> = Encoder::new(writer, compression_level)?; //used to compress data with

    let mut tle_iter = tles.into_iter(); //consuming iterator for TLEs
    let mut queue: VecDeque<TLE> = VecDeque::new(); //used to store TLE order before writing to buffer

    for result in results.into_iter() { //this then uses the propagation results generated to save n = density instances in time between each interval
        let start: Instant = result.time_start;                                       //each instance contains the time, position, and velocity of the satellite (i.e they're all SatStates)
        let end: Instant = result.time_end;
        let dt: Duration = end -  result.time_start;

        let current_tle = tle_iter.next().unwrap(); //writes the TLE lines for this specific instance, to then be used in training (as needed by the DSGP4 model)
        queue.push_back(current_tle);

        let interval: f64 = dt.as_seconds() / density as f64;
        let mut steps: Vec<SatState> = Vec::new();
        for j in 0..density {
            let shift: f64 = interval * j as f64;
            let time: Instant = start + Duration::from_seconds(shift);
            let matrix_at_time = result.interp(&time).unwrap();
            let state_at_time: SatState = make_sat_state(time, matrix_at_time);
            steps.push(state_at_time);
        }
        steps.push(make_sat_state(end, result.state_end));
        time_batches.push(steps);

        let vec_size_in_bytes = (time_batches.len() * mem::size_of::<Vec<SatState>>()) + time_batches.iter()
        .map(|batch| batch.capacity() * mem::size_of::<SatState>()).sum::<usize>();
        let queue_size_in_bytes = queue.len() * mem::size_of::<TLE>();
        let total_size_in_bytes = vec_size_in_bytes + queue_size_in_bytes;

        if total_size_in_bytes > max_vec_size { //we flush the data generated to a new file
            let _ = dump_data_batches(&mut encoder, &mut queue, &time_batches);
            time_batches.clear();
        }
    }
    if !time_batches.is_empty() {
        let _ = dump_data_batches(&mut encoder, &mut queue, &time_batches);
    }

    let mut inner_writer = encoder.finish()?;
    let _flush = inner_writer.flush()?;
    // let destination: String = format!("/mnt/IronWolfPro8TB/SWARM/data/output/raw/{}", &filename);
    // let _ = move_file(&filename, &destination);

    Ok(())
}

fn dump_data_batches(encoder: &mut Encoder<'static, BufWriter<File>>, queue: &mut VecDeque<TLE>, batches: &Vec<Vec<SatState>>) {
    for batch in batches {
        let corresponding_tle = queue.pop_front().unwrap();
        let _ = write_tle_data(encoder, &corresponding_tle);
        let _ = write_time_steps_zstd(encoder, &batch);
    }
}


fn write_time_steps_zstd(encoder: &mut Encoder<'static, BufWriter<File>>, steps: &Vec<SatState>) -> Result<()> {
    for step in steps.into_iter() {
        let formatted_step: String = format_step(&step);
        let _ = writeln!(encoder, "{}", formatted_step);
    }
    Ok(())
}

fn create_file(filename: &String) -> Result<File> {
    let path = format!("/mnt/IronWolfPro8TB/SWARM/data/output/raw/{}", filename);
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
    const MAX_VEC_SIZE:usize = 1_073_741_824 ; //1 GB in mem change as needed
    map.into_par_iter()
        .try_for_each(|(id, records)| -> Result<()>{
            Ok(stream(records, settings, &id, density, MAX_VEC_SIZE, compression_level)?)
        })?;
    Ok(())
}

#[allow(dead_code)]
fn move_file(filepath: &str, destination_filepath: &str) -> Result<()> {
    let _copy = std::fs::copy(filepath, destination_filepath)?;
    let deleted: () = std::fs::remove_file(filepath)?;
    Ok(deleted)
}

fn write_tle_data(encoder: &mut Encoder<'static, BufWriter<File>>, tle:&TLE) -> Result<()>{
    let line1: String = write_line1(tle)?;
    let line2: String = write_line2(tle)?;

    let two_lines: String = format!("{} \n{} ", line1, line2);

    let _ = writeln!(encoder, "{}", two_lines);

    Ok(())
}

fn write_line1(tle:&TLE) -> Result<String> {
    use std::fmt::Write;

    //write line1
    let mut line1: String = String::with_capacity(70);

    //satellite catalog number
    let sat_num: i32 = tle.sat_num;
    let sat_num_string = format!("{:05}U", sat_num);

    let international_designator: String = tle.intl_desig.clone();

    //last two digits of the launch year
    let mut year: i32 = tle.epoch.as_datetime().0;
    if year > 2000 {
        year = year - 2000
    } else {
        year = year - 1900
    }

    //day of the year + fractional part of day
    let unix_t = tle.epoch.as_unixtime();
    let unix_t_ns = (unix_t.fract() * 1_000_000.0) as u32; //integer number of nanoseconds
    let unix_t_int = unix_t.trunc() as i64;
    let datetime = Utc.timestamp_opt(unix_t_int, unix_t_ns).unwrap();
    let ordinal = datetime.ordinal();
    let nanoseconds_in_day = 24.0 * 60.0 * 60.0 * 1_000_000_000.0;
    let fractional_part_of_day = (datetime.timestamp_subsec_nanos() as f64) / nanoseconds_in_day;
    let fractional_ordinal = (ordinal as f64) + fractional_part_of_day;

    //first derivative of mean motion
    let first_derivative = tle.mean_motion_dot;
    let mut first_dt_string = format!("{:09.8}", first_derivative);
    if first_dt_string.starts_with("-0.") {
        first_dt_string.replace_range(1..2, ""); //removes zero in negative values
    } else {
        first_dt_string.replace_range(0..1, "+"); //removes zero in positive values
    }
    
    //second derivative of mean motion
    let (second_dt_sign, second_dt_val) = if tle.mean_motion_dot_dot < 0.0 {
        ('-', -tle.mean_motion_dot_dot)
    } else {
        ('+', tle.mean_motion_dot_dot)
    };
    let (second_dt_mantissa, second_dt_exp) = to_tle_scientific(second_dt_val);

    //the bstar drag term
    let (bstar_sign, bstar_val) = if tle.bstar < 0.0 {
        ('-', -tle.bstar)
    } else {
        (' ', tle.bstar)
    };
    let (bstar_mantissa, bstar_exp) = to_tle_scientific(bstar_val);

    //now we build line1
    write!(&mut line1, "1 {} {:8} {:02}{:012.8} {} {}{:5}-{} {}{:4}{} {} {:04}",
        sat_num_string,
        international_designator,
        year,
        fractional_ordinal,
        first_dt_string,
        second_dt_sign,
        second_dt_mantissa,
        second_dt_exp,
        bstar_sign,
        bstar_mantissa,
        bstar_exp,
        tle.ephem_type,
        tle.element_num
    ).unwrap();

    Ok(line1)
}

fn write_line2(tle:&TLE) -> Result<String> {
    use std::fmt::Write;

    let mut line2 = String::with_capacity(70);

    write!(&mut line2, "2 {:5} {:8.4} {:8.4} ",
        tle.sat_num,
        tle.inclination,
        tle.raan
    ).unwrap();

    write!(&mut line2, "{:07.7}", tle.eccen).unwrap();
    if tle.eccen < 1.0 {
        //removes the "0."
        line2.replace_range(line2.len()-9..line2.len()-7, "");
    }

    write!(&mut line2, " {:8.4} {:8.4} {:11.8}{:05}",
        tle.arg_of_perigee,
        tle.mean_anomaly,
        tle.mean_motion,
        tle.rev_num
    ).unwrap();

    Ok(line2)
}

fn to_tle_scientific(value: f64) -> (String, i32) {
    if value == 0.0 {
        return ("00000".to_string(), 0);
    }
    
    // Convert to scientific notation
    let log10 = value.log10();
    let exp = log10.floor() as i32;
    let mantissa = value / 10f64.powi(exp);
    
    // Format mantissa to 5 digits without decimal point
    let mantissa_scaled = mantissa * 10000.0;
    let mantissa_int = mantissa_scaled.round() as i32;
    let mantissa_str = format!("{:05}", mantissa_int);
    
    // Adjust exponent for the scaling
    let final_exp = exp - 4;
    
    (mantissa_str, final_exp)
}