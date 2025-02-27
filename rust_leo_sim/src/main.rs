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
            let _satellites = read::read_txt_for_satkit("./data/tle2006.txt");
        }
    } else { //defaults to reading and propagating
        pyo3::prepare_freethreaded_python();
        let satellites = read::read_txt_files(6, 7);
        let _ = propagate::propagate_satellites(satellites);
    }
}