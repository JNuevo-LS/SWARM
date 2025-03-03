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
            let satellites = read::read_txt_for_integration("./data/tle2024.txt").unwrap();
            let _sim_result_streamed = numerical_integration::integrate(satellites, 10000).unwrap();
        } else if args[1] == "t" { //key for training model for now
            println!("Nothing yet");
        } else if args[1] == "p" { //key for reading and propagating
            pyo3::prepare_freethreaded_python();
            let satellites = read::read_txt_files(6, 7);
            let _ = propagate::propagate_satellites(satellites);
        } else {
            println!("Did not recognize commands");
        }
    } else { 
        println!("Need args")
    }
}