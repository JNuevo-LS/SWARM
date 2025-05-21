use sgp4::chrono::NaiveDateTime;
use core::num;

//saved just in case its needed again in the future

fn format_datetime(year:u16, day:f64) -> Result<String> {
    let year = year+2000;
    let leap_year = is_leap_year(year);
    let (month, day_string) = find_month_and_day(day, leap_year)?;
    let hour = (day*24.0) as u32 % 24;
    let minute = ((day*24.0*60.0)%60.0).floor() as u32;
    let second = (day*24.0*60.0*60.0)%60.0;
    let dt = format!("{year:04}-{month:02}-{day_string}T{hour:02.0}:{minute:02.0}:{second:09.6}");
    Ok(dt)
}


fn parse_datetime(datetime: &String) -> Result<u32> {
    let naive_dt = NaiveDateTime::parse_from_str(datetime, "%Y-%m-%dT%H:%M:%S%.6f")?;
    Ok(naive_dt.and_utc().timestamp() as u32)
}

fn is_leap_year(year: u16) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}

fn find_month_and_day(day:f64, leap_year:bool) -> Result<(String, String)> {
    let months: [u16; 12] = if leap_year {
        [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    } else {
        [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    };

    let mut day_int: u16  = day.floor() as u16;


    let max_day: u16 = if leap_year {367} else {366};
    if day_int > max_day {
            bail!("Day {} is outside of range {}", day, max_day);
        }
    

    let mut month_index: u8 = 1;

    for &days_in_month in &months {
        if day_int <= days_in_month {
            break;
        } else {
            day_int -= days_in_month;
            month_index += 1;
        }
    }

    let month_string = String::from(format!("{:02}", month_index));
    let day_string = String::from(format!("{:02}", day_int));
    Ok((month_string, day_string))

}

pub fn hour_difference_between_epochs(datetime1:&String, datetime2:&String) -> Result<u32> {
    let seconds_dt1 = parse_datetime(datetime1)?;
    let seconds_dt2 = parse_datetime(datetime2)?;
    if seconds_dt1 > seconds_dt2 { //makes sure output is never negative
        Ok((seconds_dt1 - seconds_dt2) / 3600)
    } else {
        Ok((seconds_dt2 - seconds_dt1) / 3600)
    }
}

fn add_up(chars:&Vec<char> , start_i: usize, end_shift: usize) -> Result<u64> { //TODO: FIX THIS
    if chars.len() < start_i + end_shift {
        bail!("String too short in add_up");
    }
    let mut n: u64 = 0;
    for i in start_i..(chars.len() - end_shift) {
        n *= 10;
        if chars[i].is_digit(10) {
            //convert the char to its numeric value value
            if let Some(digit) = chars[i].to_digit(10) {
                n += digit as u64;
            }
        }
    }
    Ok(n)
}

fn convert_scientific(value: &str) -> Result<f64> {
    let value = value.trim();
    if value.is_empty() {
        bail!("Empty input");
    }

    let chars: Vec<char> = value.chars().collect();
    if chars.len() < 3 {
        bail!("Input too short");
    }

    let mut negative = false;
    let numeric_value: u64;

    if chars[0] == '-' {
        negative = true;
        if chars[chars.len() - 3] == 'e' { // deals with different formats
            numeric_value = add_up(&chars, 1, 3)?;
        } else {
            numeric_value = add_up(&chars, 1, 2)?;
        }
    } else {
        if chars[chars.len() - 3] == 'e' {
            numeric_value = add_up(&chars, 0, 3)?;
        } else {
            numeric_value = add_up(&chars, 0, 2)?;
        }
    }

    let exponent: String = chars[chars.len()-2..].iter().collect();

    let result_str = if negative {
        format!("-0.{}e{}", numeric_value, exponent)
    } else {
        format!("0.{}e{}", numeric_value, exponent)
    };

    Ok(result_str.parse::<f64>()?)

}