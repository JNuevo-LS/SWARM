use std::{cmp::Ordering, collections::HashMap, fs::File, io::{BufWriter, Write}};
use rayon::prelude::*;
use satkit::{frametransform::qteme2gcrf, orbitprop::{propagate, PropSettings, PropagationResult, SatState}, sgp4::sgp4, types::Vector3, Duration, Instant, TLE};
use anyhow::Result;
use nalgebra::SVector;

pub(crate) fn integrate(map:HashMap<String, Vec<TLE>>, density:u16) -> Result<HashMap<String, Vec<SatState>>> {
    println!("Converting to SatStates");
    let time = std::time::Instant::now();
    let map: HashMap<String, Vec<SatState>> = convert_map_to_gcrf(map)?;
    println!("Converted in {}", time.elapsed().as_secs_f64());

    let settings = PropSettings::default();
    // settings.gravity_order = 8;

    println!("Starting Numerical Integration Process");
    let time = std::time::Instant::now();
    let results_map: HashMap<String, Vec<PropagationResult<1>>> = parallel_integrate_between_gaps(map, &settings)?;
    println!("Integrated in {}", time.elapsed().as_secs_f64());

    println!("Getting all time steps");
    let time = std::time::Instant::now();
    let time_steps = parallel_get_time_steps(results_map, density)?;
    println!("Finished in {}", time.elapsed().as_secs_f64());

    Ok(time_steps)
}

pub(crate) fn integrate_streaming(map: HashMap<String, Vec<TLE>>, density:u16) -> Result<()> { //integration using streaming for lower memory machines
    println!("Converting to SatStates");
    let time = std::time::Instant::now();
    let map: HashMap<String, Vec<SatState>> = convert_map_to_gcrf(map)?;
    println!("Converted in {}", time.elapsed().as_secs_f64());

    let settings = PropSettings::default();
    // settings.gravity_order = 8;

    println!("Starting Numerical Integration Process");
    let time = std::time::Instant::now();
    let results_map: HashMap<String, Vec<PropagationResult<1>>> = parallel_integrate_between_gaps(map, &settings)?;
    println!("Integrated in {}", time.elapsed().as_secs_f64());

    println!("Saving all time steps");
    let _time_steps = parallel_save_time_steps_individual(results_map, density)?;
    println!("Finished in {}", time.elapsed().as_secs_f64());

    Ok(())
}

pub fn save_time_steps_map(map: HashMap<String, Vec<SatState>>) -> Result<()> {
    const MAX_FILE_SIZE:usize = 1_048_576_000; //1 GB change as needed
    let mut current_file_size:usize = 0;
    let mut file_index:usize = 0;

    let open_new_file = |file_index: usize| -> Result<BufWriter<File>> {
        let filepath = format!("./data/output/integration_{}.txt", &file_index);
        let file = File::create(filepath)?;
        Ok(BufWriter::new(file))
    };

    let mut writer = open_new_file(file_index)?;

    println!("Combining to one vector");
    let time = std::time::Instant::now();
    let mut combined_steps = combine_into_one_vec(map);
    println!("Finished combining in {}", time.elapsed().as_secs());

    //sorts combined_steps by time in reverse chronological order (newest last)
    println!("Sorting Combined Steps");
    let time  = std::time::Instant::now();
    combined_steps.par_sort_unstable_by(|a, b| compare_time_steps(a, b));
    println!("Finished sorting in {} seconds", time.elapsed().as_secs());

    println!("Writing to file now...");
    let time = std::time::Instant::now();
    for step in combined_steps.into_iter() {
        let formatted_step: String = format_step(step);
        let current_line_size: usize = formatted_step.len();

        let _ = writeln!(writer, "{}", formatted_step);
        
        if current_file_size + current_line_size > MAX_FILE_SIZE {
            writer.flush()?;

            //creates a new file
            file_index += 1;
            current_file_size = 0;
            writer = open_new_file(file_index)?;
        } else {
            current_file_size += current_line_size
        }
    }
    println!("Finished writing in {}", time.elapsed().as_secs());
    

    Ok(())
}

fn parallel_save_time_steps_individual(map: HashMap<String, Vec<PropagationResult<1>>>, density:u16) -> Result<()> {
    map.into_par_iter()
        .try_for_each(|(id, results)| -> Result<()>{
            let steps = get_time_steps(results, density)?;
            save_time_steps_individual(&id, steps)?;
            Ok(())
        })?;

    Ok(())
}

fn save_time_steps_individual(id: &String, steps: Vec<SatState>) -> Result<()> {
    const MAX_FILE_SIZE:usize = 1_048_576_000; //1 GB change as needed
    let mut current_file_size:usize = 0;
    let mut file_index:usize = 0;

    let open_new_file = |file_index: usize| -> Result<BufWriter<File>> {
        let filepath = format!("./data/output/raw/integration_{}_{}.txt", &id, &file_index);
        let file = File::create(filepath)?;
        Ok(BufWriter::new(file))
    };

    let mut writer = open_new_file(file_index)?;

    for step in steps.into_iter() {
        let formatted_step: String = format_step(step);
        let current_line_size: usize = formatted_step.len();

        let _ = writeln!(writer, "{}", formatted_step);
        
        if current_file_size + current_line_size > MAX_FILE_SIZE {
            writer.flush()?;

            //creates a new file
            file_index += 1;
            current_file_size = 0;
            writer = open_new_file(file_index)?;
        } else {
            current_file_size += current_line_size
        }
    }
    Ok(())
}

fn format_step(step: SatState) -> String {
    let time = step.time.as_unixtime();
    let pos_gcrf = step.pos_gcrf();
    let vel_gcrf = step.vel_gcrf();
    let formatted_step = format!("{},{},{},{},{},{},{}", time, pos_gcrf[0], pos_gcrf[1], pos_gcrf[2], vel_gcrf[0], vel_gcrf[1], vel_gcrf[2]);
    return formatted_step;
}

fn compare_time_steps(a: &SatState, b: &SatState) -> Ordering {
    let time_a = &a.time;
    let time_b = &b.time;
    if time_a > time_b {
        return Ordering::Greater;
    } else if time_b < time_a {
        return Ordering::Less;
    } else {
        return Ordering::Equal;
    }
}

fn combine_into_one_vec(map: HashMap<String, Vec<SatState>>) -> Vec<SatState> {
    map.into_par_iter()
        .flat_map_iter(|(_id, state_vec)| state_vec)
        .collect()
}

fn parallel_get_time_steps(map: HashMap<String, Vec<PropagationResult<1>>>, density:u16) -> Result<HashMap<String, Vec<SatState>>> {
    map.into_par_iter()
        .map(|(id, results)| {
            get_time_steps(results, density).map(|states| (id, states))
        })
        .collect()
}

fn get_time_steps(results: Vec<PropagationResult<1>>, density:u16) -> Result<Vec<SatState>> {
    let mut time_steps: Vec<SatState> = Vec::new();
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
        }
        time_steps.push(make_sat_state(end, result.state_end));
    }
    Ok(time_steps)
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

fn teme_to_gcrf(records:Vec<TLE>) -> Result<Vec<SatState>> {
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

fn convert_map_to_gcrf(map:HashMap<String, Vec<TLE>>) -> Result<HashMap<String, Vec<SatState>>> {
    map.into_par_iter()
        .map(|(id, records)| {
            teme_to_gcrf(records).map(|states| (id, states))
        })
        .collect()
}

fn parallel_integrate_between_gaps(map: HashMap<String, Vec<SatState>>, settings: &PropSettings) -> Result<HashMap<String, Vec<PropagationResult<1>>>> {
    map.into_par_iter()
        .map(|(id, records)| {
            integrate_between_gaps(records, &settings).map(|results| (id, results))
        })
        .collect()
}