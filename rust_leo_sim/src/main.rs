use std::env;
pub mod read;
pub mod merge;
pub mod satellite;
pub mod propagate;
pub mod numerical_integration;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() > 1 {
        if args[1] == "n" { //key for numerical integration for now
            let satellites = read::read_txt_for_integration("./data/tle2006.txt").unwrap();
            if args.len() > 2 && args[2] == "s" { //key for streaming
                let _sim_result_streamed = numerical_integration::integrate_streaming(satellites, 10000).unwrap();
            } else { 
                let sim_result = numerical_integration::integrate(satellites, 10000).unwrap();
                println!("Size of results: {}", sim_result.len());
                let _saved_results = numerical_integration::save_time_steps_map(sim_result);
            }
        }
    } else { //defaults to reading and propagating
        pyo3::prepare_freethreaded_python();
        let satellites = read::read_txt_files(6, 7);
        let _ = propagate::propagate_satellites(satellites);
    }
}