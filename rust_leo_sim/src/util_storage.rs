// code that may or may not be needed later
use std::cmp::Ordering;

#[allow(dead_code)]
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

#[allow(dead_code)]
fn combine_into_one_vec(map: HashMap<String, Vec<SatState>>) -> Vec<SatState> {
    map.into_par_iter()
        .flat_map_iter(|(_id, state_vec)| state_vec)
        .collect()
}

#[allow(dead_code)]
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